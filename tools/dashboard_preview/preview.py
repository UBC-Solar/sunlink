#!/usr/bin/env python3
"""
Preview Sunlink Grafana dashboards with real or synthetic CAN data.

Works with the sandbox stack in this folder (see README.md): Grafana 9.5.2 and
InfluxDB 2.7.1, the same versions as production, with dashboards/ provisioned
the same way as the real stack.

  check   cross-check dashboard queries against the DBC (no Influx needed)
  synth   generate CAN frames for the signals a dashboard uses, run them
          through the DBC and write them to Influx (optionally live)
  upload  decode a CAN log (candump / CSV) or load a decoded CSV into Influx
  draft   load a dashboard JSON (e.g. exported from Grafana) into the sandbox
  wipe    delete all data from a sandbox bucket

Points are written with the same schema as parser/main.py:
  measurement = message sender (HVC, MST, ...), tags car + class (message
  name), one field per signal.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import gzip
import hashlib
import io
import itertools
import json
import logging
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator, NamedTuple, Optional

try:
    import cantools
except ImportError:
    sys.exit("cantools is required: pip install -r tools/dashboard_preview/requirements.txt")

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DEFAULT_DBC = REPO_ROOT / "dbc" / "brightside.dbc"
DASHBOARDS_DIR = REPO_ROOT / "dashboards"
DRAFTS_DIR = HERE / "drafts"

# Sandbox defaults; these match docker-compose.yaml in this folder.
INFLUX_URL = os.environ.get("PREVIEW_INFLUX_URL", "http://127.0.0.1:8087")  # not "localhost": Windows tries IPv6 first, 2 s per request
INFLUX_TOKEN = os.environ.get("PREVIEW_INFLUX_TOKEN", "sunlink-preview-token")
INFLUX_ORG = os.environ.get("PREVIEW_INFLUX_ORG", "UBC Solar")
GRAFANA_URL = os.environ.get("PREVIEW_GRAFANA_URL", "http://localhost:3001")
SANDBOX_INFLUX_URLS = {"http://localhost:8087", "http://127.0.0.1:8087"}

DATASOURCE_UID = "P951FEA4DE68E13C5"
CAR_NAME = "Brightside"  # parser/main.py tags every point with this
DEFAULT_BUCKET = "CAN_prod"

GRAFANA_UNITS = {
    "mV": "mvolt", "V": "volt", "mA": "mamp", "A": "amp", "degC": "celsius", "C": "celsius",
    "W": "watt", "kW": "kwatt", "Wh": "watth", "%": "percent", "Hz": "hertz", "rpm": "rpm",
    "km/h": "velocitykmh", "m/s": "velocityms", "s": "s", "ms": "ms",
}

# <----- Terminal output ----->

_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ
if _COLOR and os.name == "nt":
    os.system("")  # turns on ANSI escape handling in the Windows console


def _paint(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def red(s): return _paint("1;31", s)
def yellow(s): return _paint("1;33", s)
def green(s): return _paint("1;32", s)
def bold(s): return _paint("1", s)
def dim(s): return _paint("2", s)


def rel(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


class PreviewError(Exception):
    """An error with a message meant for the user (no traceback)."""


# <----- DBC ----->

def sender_of(msg) -> str:
    return msg.senders[0] if msg.senders else "UNKNOWN"


@dataclass(frozen=True)
class SignalRef:
    measurement: str  # Influx measurement = the message's sender
    message: object   # cantools Message
    signal: object    # cantools Signal

    @property
    def where(self) -> str:
        return f"{self.measurement}/{self.message.name}"


class Dbc:
    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.is_file():
            raise PreviewError(f"DBC not found: {self.path}")
        logging.getLogger("cantools").setLevel(logging.ERROR)
        self.db = cantools.database.load_file(str(self.path), strict=False)
        # When a frame ID is defined twice, cantools (and so the parser) keeps the last definition.
        self._by_key = {}
        self._by_id = {}
        for m in self.db.messages:
            self._by_key[(m.frame_id, bool(m.is_extended_frame))] = m
            self._by_id[m.frame_id] = m
        live = {id(m) for m in self._by_key.values()}
        self.messages = [m for m in self.db.messages if id(m) in live]
        self.shadowed = [m for m in self.db.messages if id(m) not in live]
        self.signals = defaultdict(list)  # signal name -> [SignalRef]
        for m in self.messages:
            for s in m.signals:
                self.signals[s.name].append(SignalRef(sender_of(m), m, s))
        self.message_names = {m.name for m in self.messages}

    def lookup(self, frame_id: int, is_ext: Optional[bool] = None):
        if is_ext is not None:
            m = self._by_key.get((frame_id, bool(is_ext)))
            if m is not None:
                return m
        return self._by_id.get(frame_id)


def phys_range(sig) -> tuple:
    """Physical [min, max] a signal can carry: its DBC range clipped to what the raw bits can hold."""
    if sig.is_float:
        lo, hi = -3.4e38, 3.4e38
    else:
        if sig.is_signed:
            rlo, rhi = -(1 << (sig.length - 1)), (1 << (sig.length - 1)) - 1
        else:
            rlo, rhi = 0, (1 << sig.length) - 1
        a, b = rlo * sig.scale + sig.offset, rhi * sig.scale + sig.offset
        lo, hi = min(a, b), max(a, b)
    dmin, dmax = sig.minimum, sig.maximum
    if dmin is not None and dmax is not None and dmin < dmax:  # [0|0] means "unspecified"
        lo, hi = max(lo, dmin), min(hi, dmax)
    return lo, hi


def is_flag(sig) -> bool:
    return sig.length == 1 or phys_range(sig) == (0, 1)


# <----- Flux queries ----->

_COND_RE = re.compile(
    r'r(?:\[\s*"(?P<k1>[^"]+)"\s*\]|\.(?P<k2>\w+))\s*(?P<op>==|!=|=~|!~)\s*'
    r'(?:"(?P<v>(?:[^"\\]|\\.)*)"|/(?P<re>(?:[^/\\]|\\.)*)/)'
)


@dataclass
class ParsedQuery:
    bucket: Optional[str]
    filters: dict  # key -> set of allowed values; missing key = unconstrained
    agg_fn: Optional[str]
    raw: str


def parse_flux(query: str) -> ParsedQuery:
    """Pulls the bucket, tag/field equality filters and aggregate function out of a Flux query."""
    bucket = re.search(r'from\s*\(\s*bucket\s*:\s*"([^"]+)"', query)
    filters = {}
    for stage in query.split("|>"):
        if not stage.strip().startswith("filter"):
            continue
        eq = defaultdict(set)
        for m in _COND_RE.finditer(stage):
            value = m["v"]
            if m["op"] == "==" and value is not None and "$" not in value:
                eq[m["k1"] or m["k2"]].add(value)
        for key, values in eq.items():
            filters[key] = filters[key] & values if key in filters else values
    agg = re.search(r"aggregateWindow\s*\([^)]*?\bfn\s*:\s*(\w+)", query)
    return ParsedQuery(bucket[1] if bucket else None, filters, agg[1] if agg else None, query)


def iter_panels(dash: dict):
    for p in dash.get("panels") or []:
        yield p
        for child in p.get("panels") or []:  # panels inside collapsed rows
            yield child


def load_dashboard(path: Path) -> dict:
    try:
        dash = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise PreviewError(f"can't read dashboard {path}: {e}") from None
    if "panels" not in dash and isinstance(dash.get("dashboard"), dict):
        dash = dash["dashboard"]  # API export format
    return dash


# <----- check ----->

@dataclass
class Finding:
    level: str  # "error" | "warn" | "info"
    where: str
    text: str


@dataclass
class TargetInfo:
    panel: dict
    query: ParsedQuery
    refs: list     # SignalRefs this query returns
    missing: list  # (measurement, class, field) the query asks for but the DBC can't produce


@dataclass
class Analysis:
    path: Optional[Path]
    dash: dict
    targets: list
    findings: list

    @property
    def buckets(self) -> set:
        return {t.query.bucket for t in self.targets if t.query.bucket}


def _fmt_set(values) -> str:
    return "any" if values is None else " | ".join(f'"{v}"' for v in sorted(values))


def _ranges(nums) -> str:
    nums, out = sorted(nums), []
    for _, grp in itertools.groupby(enumerate(nums), lambda p: p[1] - p[0]):
        grp = [n for _, n in grp]
        out.append(str(grp[0]) if len(grp) == 1 else f"{grp[0]}-{grp[-1]}")
    return ", ".join(out)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def panel_label(p: dict) -> str:
    return f'"{p.get("title") or "(untitled)"}" #{p.get("id")}'


def resolve_query(q: ParsedQuery, dbc: Dbc, report: Callable[[str, str], None]):
    """Works out which DBC signals a query returns, reporting anything that can never match."""
    meas = q.filters.get("_measurement")
    fields = q.filters.get("_field")
    classes = q.filters.get("class")
    cars = q.filters.get("car")

    def matches(r: SignalRef) -> bool:
        return (meas is None or r.measurement in meas) and (classes is None or r.message.name in classes)

    if cars is not None and CAR_NAME not in cars:
        report("error", f'filters car == {_fmt_set(cars)}, but the parser tags every point car="{CAR_NAME}"')

    if fields is None:
        refs = [r for rs in dbc.signals.values() for r in rs if matches(r)]
        if not refs:
            report("error", f"no DBC signal matches _measurement == {_fmt_set(meas)}, class == {_fmt_set(classes)}")
        return refs, []

    refs, missing = [], []
    for f in sorted(fields):
        candidates = dbc.signals.get(f, [])
        hits = [r for r in candidates if matches(r)]
        if hits:
            refs.extend(hits)
            continue
        missing.append((sorted(meas)[0] if meas else "UNKNOWN", sorted(classes)[0] if classes else None, f))
        if candidates:
            where = ", ".join(sorted({r.where for r in candidates}))
            if meas is not None and not any(r.measurement in meas for r in candidates):
                report("error", f'"{f}" is sent by {where}, but the query filters _measurement == {_fmt_set(meas)}')
            else:
                report("error", f'"{f}" is in {where}, but the query filters class == {_fmt_set(classes)}')
            continue
        shadow = [m for m in dbc.shadowed if any(s.name == f for s in m.signals)]
        if shadow:
            m = shadow[0]
            report("error", f'"{f}" is only in {m.name} (0x{m.frame_id:X}), and a later definition of '
                            f"0x{m.frame_id:X} in the DBC replaces it, so it is never decoded")
            continue
        close = difflib.get_close_matches(f, list(dbc.signals), n=1, cutoff=0.6)
        hint = f'; did you mean "{close[0]}" ({dbc.signals[close[0]][0].where})?' if close else ""
        report("error", f'field "{f}" is not in the DBC{hint}')
    return refs, missing


def analyze(dash: dict, dbc: Dbc, path: Optional[Path] = None) -> Analysis:
    a = Analysis(path, dash, [], [])

    def add(level, panel, text):
        a.findings.append(Finding(level, panel_label(panel) if panel else "dashboard", text))

    seen_queries = {}
    car_filtered = set()
    for p in iter_panels(dash):
        defaults = (p.get("fieldConfig") or {}).get("defaults") or {}
        for t in p.get("targets") or []:
            raw = t.get("query") or ""
            if t.get("hide") or "from(" not in raw:
                continue
            q = parse_flux(raw)
            refs, missing = resolve_query(q, dbc, lambda level, text, p=p: add(level, p, text))
            a.targets.append(TargetInfo(p, q, refs, missing))

            if refs and q.agg_fn in ("mean", "median"):
                if defaults.get("mappings"):
                    add("warn", p, f"aggregateWindow(fn: {q.agg_fn}) averages samples, so values land between your "
                                   f"value mappings (e.g. 0.5 instead of 0/1) and show as raw numbers; "
                                   f"use fn: last (or max for faults)")
                elif all(is_flag(r.signal) for r in refs):
                    add("warn", p, f"aggregateWindow(fn: {q.agg_fn}) on 0/1 flags shows fractions (0.25, 0.5...) "
                                   f"whenever a flag changes inside a window; use fn: max (any fault in the window) or last")
            units = {r.signal.unit for r in refs if r.signal.unit}
            if refs and not defaults.get("unit") and len(units) == 1:
                unit = units.pop()
                if unit in GRAFANA_UNITS:
                    add("info", p, f'signals are in {unit} but the panel has no unit; set Unit to "{GRAFANA_UNITS[unit]}"')
            key = (p.get("type"), " ".join(raw.split()))
            if key in seen_queries and seen_queries[key] is not p:
                add("info", p, f"same query and panel type as {panel_label(seen_queries[key])}")
            seen_queries.setdefault(key, p)
            if "car" in q.filters:
                car_filtered.add(id(p))

        for ov in (p.get("fieldConfig") or {}).get("overrides") or []:
            options = str((ov.get("matcher") or {}).get("options") or "")
            for cls in re.findall(r'class=\\?"(\w+)', options):
                if cls not in dbc.message_names:
                    alt = [n for n in dbc.message_names if n.lower() == cls.lower()]
                    spelled = f' (the DBC spells it "{alt[0]}")' if alt else ""
                    add("warn", p, f'override matcher looks for class="{cls}", which is not a DBC message{spelled}, '
                                   f"so the override never applies")

    if car_filtered:
        add("info", None, f'{len(car_filtered)} panels filter car == "{CAR_NAME}": parser/main.py (link_telemetry) '
                          f"sets that tag but parser/cellular_parser.py does not, so they stay empty for cellular data")

    # Numbered signal families (Mod0Temp..Mod31Temp) that the dashboard only partly shows
    shown = defaultdict(set)
    for t in a.targets:
        for r in t.refs:
            m = re.fullmatch(r"(\D*)(\d+)(\D*)", r.signal.name)
            if m:
                shown[(r.measurement, m[1], m[3])].add(int(m[2]))
    for (meas, pre, post), nums in sorted(shown.items()):
        if len(nums) < 3:
            continue
        pattern = re.compile(rf"{re.escape(pre)}(\d+){re.escape(post)}")
        family = {int(m[1]) for name, rs in dbc.signals.items() if any(r.measurement == meas for r in rs)
                  for m in [pattern.fullmatch(name)] if m}
        hidden = family - nums
        if hidden:
            add("info", None, f"{meas} {pre}<n>{post}: panels show {_ranges(nums)} but never {_ranges(hidden)}")
    return a


def dbc_findings(dbc: Dbc) -> list:
    out = []
    groups = defaultdict(list)
    for m in dbc.db.messages:
        groups[(m.frame_id, bool(m.is_extended_frame))].append(m)
    for (frame_id, _), msgs in sorted(groups.items()):
        if len(msgs) > 1:
            defs = ", ".join(f"{m.name} ({m.length} B)" for m in msgs)
            out.append(Finding("warn", "DBC", f"frame 0x{frame_id:X} is defined {len(msgs)} times ({defs}); "
                                              f"the parser only uses the last one"))
    try:
        cantools.database.load_file(str(dbc.path), strict=True)
    except Exception as e:  # cantools raises plain Errors for overlapping / oversized signals
        out.append(Finding("warn", "DBC", f"strict load fails: {e}"))
    return out


_LEVEL_TAG = {"error": lambda: red("ERROR"), "warn": lambda: yellow("WARN "), "info": lambda: dim("note ")}
_LEVEL_RANK = {"error": 0, "warn": 1, "info": 2}


def print_findings(findings, quiet=False):
    for f in sorted(findings, key=lambda f: _LEVEL_RANK[f.level]):
        if quiet and f.level == "info":
            continue
        print(f"  {_LEVEL_TAG[f.level]()} {f.where}: {f.text}")


def cmd_check(args) -> int:
    dbc = Dbc(args.dbc)
    paths = args.dashboards or sorted(DASHBOARDS_DIR.rglob("*.json"))
    n_signals = sum(len(v) for v in dbc.signals.values())
    print(bold(f"DBC {rel(dbc.path)}") + f": {len(dbc.messages)} messages, {n_signals} signals")
    print_findings(dbc_findings(dbc), args.quiet)
    errors = 0
    for path in paths:
        dash = load_dashboard(path)
        a = analyze(dash, dbc, path)
        counts = Counter(f.level for f in a.findings)
        print(f"\n{bold(dash.get('title') or path.name)}  {dim(rel(path))}")
        print_findings(a.findings, args.quiet)
        summary = ", ".join(_plural(counts[k], word) for k, word in (("error", "error"), ("warn", "warning"), ("info", "note")))
        colour = red if counts["error"] else yellow if counts["warn"] else green
        print(f"  {sum(1 for _ in iter_panels(dash))} panels, {len(a.targets)} queries: {colour(summary)}")
        errors += counts["error"]
    return 1 if errors else 0


# <----- Frames, rows and Influx ----->

class Frame(NamedTuple):
    ts: float
    can_id: int
    is_ext: Optional[bool]
    data: bytes


class Row(NamedTuple):
    ts: float
    measurement: str
    tags: tuple    # ((key, value), ...)
    fields: dict   # {field: number}


def row_tags(schema: str, cls: str) -> tuple:
    return (("class", cls),) if schema == "cellular" else (("car", CAR_NAME), ("class", cls))


class FrameDecoder:
    """Decodes frames the way the parsers do and keeps count of what didn't decode."""

    def __init__(self, dbc: Dbc, schema: str = "link"):
        self.dbc, self.schema = dbc, schema
        self.frames = self.decoded = 0
        self.unknown = Counter()
        self.failed = Counter()

    def rows(self, fr: Frame) -> list:
        self.frames += 1
        msg = self.dbc.lookup(fr.can_id, fr.is_ext)
        if msg is None:
            self.unknown[fr.can_id] += 1
            return []
        try:
            values = msg.decode(bytes(fr.data), decode_choices=False)
        except Exception as e:  # cantools DecodeError and friends
            self.failed[(msg.name, str(e)[:100])] += 1
            return []
        self.decoded += 1
        fields = {k: v for k, v in values.items() if isinstance(v, (int, float))}
        if self.schema == "cellular":
            fields["can_timestamp"] = fr.ts
        return [Row(fr.ts, sender_of(msg), row_tags(self.schema, msg.name), fields)]

    def report(self):
        if not self.frames:
            return
        print(f"  frames: {self.frames}, decoded: {self.decoded}")
        if self.unknown:
            top = ", ".join(f"0x{i:X} ({n}x)" for i, n in self.unknown.most_common(10))
            print(yellow(f"  {sum(self.unknown.values())} frames have IDs not in the DBC: {top}"))
        for (name, why), n in self.failed.most_common(10):
            print(yellow(f"  {n} {name} frames failed to decode ({why}); the parser drops these too"))


def _esc_key(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace(",", "\\,").replace("=", "\\=").replace(" ", "\\ ")


def _esc_measurement(s: str) -> str:
    return str(s).replace("\\", "\\\\").replace(",", "\\,").replace(" ", "\\ ")


class Influx:
    """Just enough of the InfluxDB v2 HTTP API, using only the standard library."""

    def __init__(self, url: str, token: str, org: str):
        self.url, self.token, self.org = url.rstrip("/"), token, org

    def _request(self, method, path, params=None, body: Optional[bytes] = None,
                 content_type="application/json", compress=False):
        url = self.url + path + (f"?{urllib.parse.urlencode(params)}" if params else "")
        headers = {"Authorization": f"Token {self.token}"}
        if body is not None:
            headers["Content-Type"] = content_type
            if compress:
                body = gzip.compress(body)
                headers["Content-Encoding"] = "gzip"
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
                return json.loads(raw) if raw and "json" in resp.headers.get("Content-Type", "") else None
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            try:
                detail = json.loads(detail).get("message", detail)
            except ValueError:
                pass
            hint = ""
            if "field type conflict" in detail:
                hint = "\n  (the bucket already holds this field with another type; `preview.py wipe` clears it)"
            raise PreviewError(f"InfluxDB {method} {path} -> HTTP {e.code}: {detail}{hint}") from None
        except (urllib.error.URLError, OSError) as e:
            reason = getattr(e, "reason", e)
            raise PreviewError(f"can't reach InfluxDB at {self.url} ({reason}).\n"
                               f"  Is the sandbox running? See tools/dashboard_preview/README.md") from None

    def health(self):
        self._request("GET", "/health")

    def ensure_bucket(self, name: str):
        found = self._request("GET", "/api/v2/buckets", {"org": self.org, "name": name}) or {}
        if found.get("buckets"):
            return
        orgs = (self._request("GET", "/api/v2/orgs", {"org": self.org}) or {}).get("orgs") or []
        if not orgs:
            raise PreviewError(f'InfluxDB has no org "{self.org}"')
        body = json.dumps({"orgID": orgs[0]["id"], "name": name, "retentionRules": []}).encode()
        self._request("POST", "/api/v2/buckets", body=body)
        print(dim(f"  created bucket {name}"))

    def write(self, bucket: str, lines: list):
        self._request("POST", "/api/v2/write", {"org": self.org, "bucket": bucket, "precision": "ns"},
                      "\n".join(lines).encode(), content_type="text/plain; charset=utf-8", compress=True)

    def delete_all(self, bucket: str):
        body = json.dumps({"start": "1970-01-01T00:00:00Z", "stop": "2200-01-01T00:00:00Z"}).encode()
        self._request("POST", "/api/v2/delete", {"org": self.org, "bucket": bucket}, body)


class Writer:
    """Batches rows into line protocol and writes them to every target bucket."""

    def __init__(self, influx: Influx, buckets: list, batch: int = 5000):
        self.influx, self.buckets, self.batch = influx, buckets, batch
        self.buf = []
        self.points = self.fields = 0
        self.t_min, self.t_max = math.inf, -math.inf
        self.measurements = Counter()

    def add(self, row: Row):
        # Always floats: the parsers disagree (main.py writes ints, cellular_parser.py floats), and
        # mixing types for one field makes InfluxDB reject the write. Dashboards can't tell the difference.
        fields = [f"{_esc_key(k)}={float(v)!r}" for k, v in row.fields.items()
                  if v is not None and math.isfinite(v)]
        if not fields:
            return
        tags = "".join(f",{_esc_key(k)}={_esc_key(v)}" for k, v in row.tags if v)
        self.buf.append(f"{_esc_measurement(row.measurement)}{tags} {','.join(fields)} {int(round(row.ts * 1e6)) * 1000}")
        self.points += 1
        self.fields += len(fields)
        self.t_min, self.t_max = min(self.t_min, row.ts), max(self.t_max, row.ts)
        self.measurements[row.measurement] += 1
        if len(self.buf) >= self.batch:
            self.flush()

    def flush(self):
        if self.buf:
            for bucket in self.buckets:
                self.influx.write(bucket, self.buf)
            self.buf = []


def connect(args, buckets: list, create_buckets=True) -> Influx:
    url = args.influx_url.rstrip("/")
    if url not in SANDBOX_INFLUX_URLS and not args.allow_non_sandbox:
        raise PreviewError(f"{url} is not the preview sandbox. Test data written there would mix with real "
                           f"telemetry; pass --allow-non-sandbox if that's really what you want.")
    influx = Influx(url, args.token, args.org)
    influx.health()
    if create_buckets:
        for bucket in buckets:
            influx.ensure_bucket(bucket)
    return influx


# <----- Grafana links ----->

def dashboard_link(dash: dict, time_range: str) -> str:
    return f"{GRAFANA_URL}/d/{dash.get('uid')}?orgId=1&{time_range}"


def dashboards_touching(measurements, buckets) -> list:
    """Dashboards (repo + drafts) with a query on one of these measurements in one of these buckets."""
    found = []
    for path in sorted(DASHBOARDS_DIR.rglob("*.json")) + sorted(DRAFTS_DIR.glob("*.json")):
        try:
            dash = load_dashboard(path)
        except PreviewError:
            continue
        for p in iter_panels(dash):
            queries = [parse_flux(t.get("query") or "") for t in p.get("targets") or []]
            if any(q.bucket in buckets and (q.filters.get("_measurement") or set()) & set(measurements)
                   for q in queries):
                found.append(dash)
                break
    return found


def print_links(dashes: list, time_range: str):
    if not dashes:
        print(f"  Grafana: {GRAFANA_URL}/dashboards")
    for dash in dashes:
        print(f"  {dash.get('title')}: {dashboard_link(dash, time_range)}")


# <----- synth ----->

_FAULT_RE = re.compile(r"fault|error|(?:^|_)err|warn|timeout|fail|flag", re.I)
_UNIT_TYPICAL = {  # (centre, amplitude) for signals whose DBC range is too wide to be useful
    "mV": (3700, 300), "V": (100, 10), "mA": (2000, 1500), "A": (10, 8), "degC": (35, 8),
    "%": (60, 30), "rpm": (600, 300), "km/h": (40, 20), "W": (800, 600),
}


def _stable_hash(name: str) -> int:
    return int(hashlib.md5(name.encode()).hexdigest()[:8], 16)


def _from_mv(value_mv: float, unit: str) -> float:
    return value_mv / 1000 if unit == "V" else value_mv


class PackModel:
    """A battery pack whose module voltages, temperatures, current and balancing all agree."""

    def __init__(self, rng: random.Random, modules: int = 32):
        self.rng, self.n = rng, modules
        self.v_off = [rng.gauss(0, 25) for _ in range(modules)]
        self.t_off = [rng.uniform(-2.5, 2.5) for _ in range(modules)]
        for i in rng.sample(range(modules), 2):  # two high modules, so thresholds and balancing show up
            self.v_off[i] += rng.uniform(150, 260)
        self.t_off[rng.randrange(modules)] += 13  # one hot module
        self._t = None

    def at(self, t: float) -> "PackModel":
        if t == self._t:
            return self
        self._t = t
        g = self.rng.gauss
        self.current = (9000 * math.sin(2 * math.pi * t / 240) + 5000 * math.sin(2 * math.pi * t / 37 + 1)
                        + 3000 + g(0, 400))  # mA
        base = 3880 + 120 * math.sin(2 * math.pi * t / 1800)
        sag = self.current * 0.0025  # 2.5 mOhm per module
        self.v = [base + off - sag + g(0, 3) for off in self.v_off]  # mV
        ambient = 29 + 5 * math.sin(2 * math.pi * t / 900)
        self.temp = [ambient + off + g(0, 0.3) for off in self.t_off]  # degC
        median = sorted(self.v)[self.n // 2]
        self.balance = sum(1 << i for i, v in enumerate(self.v) if v - median > 60)
        return self


class SignalModel:
    """Plausible physical values for a signal, chosen from its name, unit and range."""

    def __init__(self, seed: int = 7):
        self.rng = random.Random(seed)
        self.pack = PackModel(self.rng)
        self.boot = 2 * 3600  # boards have been up for two hours when the preview starts

    def value(self, name: str, unit: str, lo: Optional[float], hi: Optional[float], t: float, hz: float) -> float:
        p, u, low = self.pack.at(t), (unit or "").strip(), name.lower()
        m = re.fullmatch(r"Mod(\d+)Voltage", name)
        if m:
            return _from_mv(p.v[int(m[1]) % p.n], u)
        m = re.fullmatch(r"Mod(\d+)Temp", name)
        if m:
            return p.temp[int(m[1]) % p.n]
        pack_values = {
            "TotalVoltage": lambda: _from_mv(sum(p.v), u),
            "MinVoltModuleIdx": lambda: min(range(p.n), key=p.v.__getitem__),
            "MaxVoltModuleIdx": lambda: max(range(p.n), key=p.v.__getitem__),
            "AvgTemp": lambda: sum(p.temp) / p.n,
            "MinTempModuleIdx": lambda: min(range(p.n), key=p.temp.__getitem__),
            "MaxTempModuleIdx": lambda: max(range(p.n), key=p.temp.__getitem__),
            "PackCurrent": lambda: p.current / 1000 if u == "A" else p.current,
            "BalanceBitmap": lambda: p.balance,
            "BalancingActive": lambda: int(p.balance != 0),
        }
        if name in pack_values:
            return pack_values[name]()

        wraps = int(hi) + 1 if hi is not None and hi < 2 ** 32 else 2 ** 16
        if _FAULT_RE.search(name):  # each fault blips on for 15 s every 4 min, at its own phase
            h = _stable_hash(name)
            if (t + h % 240) % 240 >= 15:
                return 0
            return 1 if hi is None or hi < 2 else min(hi, 1 << (h % 8))  # one bit of a fault bitfield
        if lo == 0 and hi == 1:
            return 1  # Enable / Active / On style flags
        if "precharge" in low and "volt" in low:  # charges towards pack voltage, restarting every 10 min
            return _from_mv(sum(p.v) * (1 - math.exp(-(t % 600) / 5)), u)
        if "supp" in low and "volt" in low:
            return _from_mv(12600 - 300 * math.sin(2 * math.pi * t / 1200) + self.rng.gauss(0, 15), u)
        if re.search(r"counter|tick", low) or ("heartbeat" in low and (hi or 0) > 1):
            return int(t * hz) % wraps
        if re.search(r"timesinceboot|uptime", low):
            return int(self.boot + t) % wraps
        if re.search(r"state$|mode$", low) and hi is not None and hi - (lo or 0) <= 32:
            return min(int(t // 45), int(min(hi, 4)))  # steps through start-up states, then holds
        return self._wave(name, u, lo, hi, t)

    def _wave(self, name, unit, lo, hi, t):
        if lo is None or hi is None:
            lo, hi = 0.0, 100.0
        h = _stable_hash(name)
        period, phase = 60 + h % 240, (h >> 8) % 628 / 100
        if hi - lo > 1e5 and unit in _UNIT_TYPICAL:
            centre, amp = _UNIT_TYPICAL[unit]
        else:
            centre, amp = lo + (hi - lo) * 0.45, (hi - lo) * 0.25
        v = centre + amp * math.sin(2 * math.pi * t / period + phase) + self.rng.gauss(0, amp * 0.04)
        return min(hi, max(lo, v))


class FrameSynth:
    """Generates frames for a set of messages at a fixed rate, encoded with the DBC."""

    def __init__(self, messages, model: SignalModel, hz: float, t0: float, missing=(), schema="link"):
        self.messages, self.model, self.hz, self.t0 = messages, model, hz, t0
        self.missing, self.schema = missing, schema
        self.next_t = t0
        self._encode_failed = set()

    def until(self, t_end: float) -> Iterator:
        step, n = 1 / self.hz, max(1, len(self.messages))
        while self.next_t <= t_end:
            t = self.next_t
            for i, msg in enumerate(self.messages):
                ts = t + step * 0.8 * i / n  # spread messages across the tick like a real bus
                data = self._encode(msg, ts - self.t0)
                if data is not None:
                    yield Frame(ts, msg.frame_id, bool(msg.is_extended_frame), data)
            for meas, cls, fld in self.missing:  # queried fields the DBC can't produce (--fill-missing)
                value = self.model.value(fld, "", None, None, t - self.t0, self.hz)
                yield Row(t, meas, row_tags(self.schema, cls or "Synthetic"), {fld: value})
            self.next_t += step

    def _encode(self, msg, t: float) -> Optional[bytes]:
        values = {}
        for s in msg.signals:
            lo, hi = phys_range(s)
            values[s.name] = min(hi, max(lo, self.model.value(s.name, s.unit, lo, hi, t, self.hz)))
        try:
            return msg.encode(values, scaling=True, padding=False, strict=False)
        except Exception as e:  # cantools EncodeError, bitstruct errors
            if msg.name not in self._encode_failed:
                self._encode_failed.add(msg.name)
                print(yellow(f"  can't encode {msg.name}: {e}"))
            return None


def _candump_line(fr: Frame) -> str:
    can_id = f"{fr.can_id:08X}" if fr.is_ext else f"{fr.can_id:03X}"
    return f"({fr.ts:.6f}) can0 {can_id}#{fr.data.hex().upper()}"


def cmd_synth(args) -> int:
    dbc = Dbc(args.dbc)
    analyses = [analyze(load_dashboard(p), dbc, p) for p in args.dashboard]
    if analyses:
        seen, messages, missing = set(), [], []
        for a in analyses:
            for t in a.targets:
                for r in t.refs:
                    if id(r.message) not in seen:
                        seen.add(id(r.message))
                        messages.append(r.message)
                missing.extend(m for m in t.missing if m not in missing)
        buckets = args.bucket or sorted(set().union(*(a.buckets for a in analyses))) or [DEFAULT_BUCKET]
    else:
        messages, missing, buckets = list(dbc.messages), [], args.bucket or [DEFAULT_BUCKET]
    if args.messages:
        messages = [m for m in messages if re.search(args.messages, m.name)]
    muxed = [m.name for m in messages if m.is_multiplexed()]
    messages = [m for m in messages if not m.is_multiplexed()]
    if muxed:
        print(dim(f"  skipping multiplexed messages: {', '.join(muxed)}"))
    if missing and not args.fill_missing:
        names = ", ".join(sorted({f for _, _, f in missing}))
        print(yellow(f"  {len(missing)} queried fields aren't in the DBC ({names}); run `check` for details, "
                     f"or pass --fill-missing to fake them"))
        missing = []
    if not messages and not missing:
        raise PreviewError("nothing to generate: no DBC messages matched")

    now = time.time()
    t0 = now - args.minutes * 60
    synth = FrameSynth(messages, SignalModel(args.seed), args.hz, t0, missing, args.schema)
    print(f"Generating {len(messages)} messages at {args.hz:g} Hz for {args.minutes:g} min"
          + (f" (+{len(missing)} faked fields)" if missing else ""))

    if args.out:
        n = 0
        with open(args.out, "w", encoding="ascii", newline="\n") as f:
            for item in synth.until(now):
                if isinstance(item, Frame):
                    f.write(_candump_line(item) + "\n")
                    n += 1
        print(green(f"Wrote {n} frames to {args.out}") + f"  (load it with: preview.py upload {args.out})")
        return 0

    influx = connect(args, buckets)
    writer = Writer(influx, buckets)
    decoder = FrameDecoder(dbc, args.schema)

    def pump(t_end):
        for item in synth.until(t_end):
            for row in decoder.rows(item) if isinstance(item, Frame) else [item]:
                writer.add(row)
        writer.flush()

    pump(now)
    decoder.report()
    print(green(f"Wrote {writer.points} points ({writer.fields} values) to {', '.join(buckets)}"))
    dashes = [a.dash for a in analyses] or dashboards_touching(writer.measurements, buckets)
    print_links(dashes, f"from=now-{max(args.minutes, 5):g}m&to=now")
    if not args.live:
        return 0
    print(f"Streaming live at {args.hz:g} Hz - Ctrl+C to stop")
    try:
        while True:
            time.sleep(max(0.05, synth.next_t - time.time()))
            pump(time.time())
    except KeyboardInterrupt:
        writer.flush()
        print(f"\nStopped after {writer.points} points")
    return 0


# <----- upload ----->

_CANDUMP_LOG = re.compile(r"^\s*\((?P<ts>[^)]+)\)\s+(?P<ifc>\S+)\s+(?P<id>[0-9A-Fa-f]{1,8})#(?!#)(?P<rtr>R)?(?P<data>[0-9A-Fa-f]*)")
_CANDUMP_TXT = re.compile(r"^\s*(?:\((?P<ts>[^)]+)\)\s+)?(?P<ifc>\w+)\s+(?P<id>[0-9A-Fa-f]{3,8})\s+\[(?P<dlc>\d+)\]\s+"
                          r"(?P<data>(?:[0-9A-Fa-f]{2}\s*)*)")
_ISO_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:[.,](\d+))?\s*(Z|[+-]\d{2}:?\d{2})?$", re.I)

_ID_COLS = {"id", "canid", "arbitrationid", "arbid", "frameid", "identifier", "msgid", "messageid", "idhex"}
_DATA_COLS = {"data", "payload", "bytes", "datahex", "databytes", "hexdata", "rawdata"}
_TIME_COLS = {"timestamp", "time", "ts", "t", "times", "unixtime", "epoch", "datetime", "timestamps", "timesec"}
_EXT_COLS = {"ext", "extended", "isextended", "isextendedid", "ide"}
_BYTE_COL = re.compile(r"^(?:d|b|data|byte|db)([0-7])$")
_INFLUX_RESERVED = {"", "result", "table", "_start", "_stop", "_time", "_value", "_field", "_measurement"}


def parse_time(text: str) -> float:
    """Epoch seconds from epoch s/ms/us/ns or an ISO-8601 string (naive = local time)."""
    s = text.strip().strip('"')
    try:
        x = float(s)
    except ValueError:
        m = _ISO_RE.match(s)
        if not m:
            raise ValueError(f"unrecognised timestamp {text!r}") from None
        date, clock, frac, tz = m.groups()
        dt = datetime.fromisoformat(f"{date}T{clock}")
        if tz and tz.upper() == "Z":
            dt = dt.replace(tzinfo=timezone.utc)
        elif tz:
            tz = tz.replace(":", "")
            offset = timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5]))
            dt = dt.replace(tzinfo=timezone(offset if tz[0] == "+" else -offset))
        return dt.timestamp() + (float("0." + frac) if frac else 0.0)
    if x > 1e17:
        return x / 1e9
    if x > 1e14:
        return x / 1e6
    if x > 1e11:
        return x / 1e3
    return x


def _norm(col: str) -> str:
    return re.sub(r"[\s_()\[\]]+", "", col.strip().lower())


def _open_text(path: Path):
    if path.suffix == ".gz":
        return io.TextIOWrapper(gzip.open(path), encoding="utf-8-sig", errors="replace", newline="")
    return open(path, encoding="utf-8-sig", errors="replace", newline="")


def _delimiter(header_line: str) -> str:
    return max(",;\t", key=header_line.count)


def _csv_rows(path: Path):
    with _open_text(path) as f:
        delim = _delimiter(f.readline())
    with _open_text(path) as f:
        yield from csv.reader(f, delimiter=delim)


def _first_col(header, names) -> Optional[int]:
    return next((i for i, c in enumerate(header) if c in names), None)


@dataclass
class Source:
    kind: str
    items: Callable[[], Iterator]  # re-iterable: yields Frame or Row
    notes: list


def _sniff(path: Path) -> str:
    with _open_text(path) as f:
        lines = [line.strip() for line in itertools.islice(f, 50) if line.strip()]
    if not lines:
        raise PreviewError(f"{path} is empty")
    if lines[0].startswith("#") or any("_measurement" in l and "_field" in l for l in lines[:5]):
        return "influx"
    if any(_CANDUMP_LOG.match(l) or _CANDUMP_TXT.match(l) for l in lines[:10]):
        return "candump"
    header = {_norm(c) for c in next(csv.reader([lines[0]], delimiter=_delimiter(lines[0])))}
    if header & _ID_COLS and (header & _DATA_COLS or any(_BYTE_COL.match(c) for c in header)):
        return "frames"
    return "wide"


def _candump_source(path: Path) -> Source:
    def raw():
        with _open_text(path) as f:
            for i, line in enumerate(f):
                m = _CANDUMP_LOG.match(line)
                if m:
                    if m["rtr"]:
                        continue
                    data = bytes.fromhex(m["data"])
                else:
                    m = _CANDUMP_TXT.match(line)
                    if not m:
                        continue
                    data = bytes.fromhex("".join(m["data"].split()))
                ts = parse_time(m["ts"]) if m["ts"] else i * 0.001
                yield Frame(ts, int(m["id"], 16), len(m["id"]) > 3, data)

    head = [fr.ts for fr in itertools.islice(raw(), 500)]
    deltas = bool(head) and max(head) < 1e8 and any(b < a for a, b in zip(head, head[1:]))

    def items():
        if not deltas:
            yield from raw()
            return
        acc = 0.0
        for fr in raw():  # candump -td prints the gap since the previous frame
            acc += fr.ts
            yield fr._replace(ts=acc)

    return Source("candump log", items, ["timestamps are deltas (candump -td); accumulated"] if deltas else [])


def _frames_source(path: Path, id_base: str, dbc: Dbc) -> Source:
    rows = _csv_rows(path)
    header = [_norm(c) for c in next(rows)]
    sample = list(itertools.islice(rows, 5000))
    rows.close()
    ti, ii = _first_col(header, _TIME_COLS), _first_col(header, _ID_COLS)
    di, ei = _first_col(header, _DATA_COLS), _first_col(header, _EXT_COLS)
    byte_cols = [] if di is not None else sorted(
        (int(m[1]), j) for j, c in enumerate(header) for m in [_BYTE_COL.match(c)] if m)
    notes = []

    if id_base == "auto":
        ids = [r[ii].strip() for r in sample if len(r) > ii and r[ii].strip()]
        if any(re.search(r"0x|[a-fA-F]|h$", s) for s in ids):
            id_base = "hex"
        else:
            def known(base):
                return sum(1 for s in ids if s.isdigit() and dbc.lookup(int(s, base)) is not None)
            id_base = "dec" if known(10) > known(16) else "hex"
        notes.append(f"CAN IDs read as {id_base}")
    byte_base = 16
    if byte_cols:
        cells = [r[j].strip() for r in sample for _, j in byte_cols if len(r) > j and r[j].strip()]
        if not any(re.search(r"[a-fA-F]", c) for c in cells) and any(len(c) == 3 for c in cells):
            byte_base = 10
            notes.append("data bytes read as decimal")

    def parse_id(s: str) -> int:
        s = s.strip().lower().removesuffix("h").removeprefix("0x").rstrip("x")
        return int(s, 16 if id_base == "hex" else 10)

    def parse_data(row) -> bytes:
        if byte_cols:
            return bytes(int(row[j], byte_base) for _, j in byte_cols if len(row) > j and row[j].strip())
        s = row[di].strip().replace("0x", "")
        parts = [p for p in re.split(r"[\s:,-]+", s) if p]
        if len(parts) > 1:
            return bytes(int(p, 16) for p in parts)
        return bytes.fromhex(s if len(s) % 2 == 0 else "0" + s)

    def items():
        for n, row in enumerate(itertools.islice(_csv_rows(path), 1, None)):
            if len(row) <= ii or not row[ii].strip():
                continue
            try:
                can_id, data = parse_id(row[ii]), parse_data(row)
                ts = parse_time(row[ti]) if ti is not None and row[ti].strip() else n * 0.001
            except ValueError:
                continue  # stray header / comment row
            is_ext = row[ei].strip().lower() in ("1", "true", "yes", "x", "ext") if ei is not None else can_id > 0x7FF
            yield Frame(ts, can_id, is_ext, data)

    return Source("CSV of raw CAN frames", items, notes)


def _influx_source(path: Path) -> Source:
    def items():
        header = None
        for rec in _csv_rows(path):
            if not rec or not any(c.strip() for c in rec) or rec[0].startswith("#"):
                header = None  # a blank or annotation line starts a new table
                continue
            if header is None:
                header = {c: i for i, c in enumerate(rec)}
                tag_cols = [(c, i) for c, i in header.items() if c not in _INFLUX_RESERVED]
                continue
            try:
                value = float(rec[header["_value"]])
                ts = parse_time(rec[header["_time"]])
                meas, fld = rec[header["_measurement"]], rec[header["_field"]]
            except (KeyError, IndexError, ValueError):
                continue  # non-numeric value or malformed row
            tags = tuple(sorted((c, rec[i]) for c, i in tag_cols if i < len(rec) and rec[i]))
            yield Row(ts, meas, tags, {fld: value})

    return Source("InfluxDB annotated CSV (already decoded)", items, [])


def _wide_source(path: Path, dbc: Dbc, schema: str) -> Source:
    rows = _csv_rows(path)
    raw_header = next(rows)
    rows.close()
    header = [_norm(c) for c in raw_header]
    ti = _first_col(header, _TIME_COLS)
    if ti is None:
        raise PreviewError(f"couldn't recognise {path.name}: expected a candump log, a CSV with id + data columns, "
                           f"an InfluxDB CSV, or a CSV with a time column plus one column per signal")
    groups, unknown, notes = defaultdict(list), [], []
    for j, col in enumerate(raw_header):
        if j == ti:
            continue
        name = re.sub(r"\s*[\[(].*?[\])]\s*$", "", col.strip())  # "PackCurrent (mA)" -> "PackCurrent"
        *qualifiers, sig = re.split(r"[./:]", name)
        refs = [r for r in dbc.signals.get(sig, [])
                if all(q in (r.measurement, r.message.name) for q in qualifiers)]
        if not refs:
            unknown.append(col)
            continue
        if len(refs) > 1:
            notes.append(f"{col} is ambiguous ({', '.join(r.where for r in refs)}); using {refs[0].where} "
                         f"- write it as Message.Signal to choose")
        groups[(refs[0].measurement, refs[0].message.name)].append((j, sig))
    if not groups:
        raise PreviewError(f"none of the columns in {path.name} are DBC signals")
    if unknown:
        notes.append(f"ignoring columns that aren't DBC signals: {', '.join(unknown)}")

    def items():
        for row in itertools.islice(_csv_rows(path), 1, None):
            if len(row) <= ti or not row[ti].strip():
                continue
            try:
                ts = parse_time(row[ti])
            except ValueError:
                continue
            for (meas, cls), cols in groups.items():
                fields = {}
                for j, sig in cols:
                    try:
                        fields[sig] = float(row[j])
                    except (IndexError, ValueError):
                        pass
                if fields:
                    yield Row(ts, meas, row_tags(schema, cls), fields)

    return Source(f"CSV of signal values ({sum(len(c) for c in groups.values())} signals)", items, notes)


def open_source(path: Path, fmt: str, dbc: Dbc, args) -> Source:
    if not path.is_file():
        raise PreviewError(f"no such file: {path}")
    fmt = _sniff(path) if fmt == "auto" else fmt
    if fmt == "candump":
        return _candump_source(path)
    if fmt == "frames":
        return _frames_source(path, args.id_base, dbc)
    if fmt == "influx":
        return _influx_source(path)
    return _wide_source(path, dbc, args.schema)


def cmd_upload(args) -> int:
    dbc = Dbc(args.dbc)
    src = open_source(args.file, args.format, dbc, args)
    print(f"{args.file.name}: {src.kind}")
    for note in src.notes:
        print(dim(f"  {note}"))
    buckets = args.bucket or [DEFAULT_BUCKET]
    influx = connect(args, buckets)

    first, last, count = math.inf, -math.inf, 0
    for item in src.items():
        first, last, count = min(first, item.ts), max(last, item.ts), count + 1
    if not count:
        raise PreviewError(f"no CAN frames or values found in {args.file}")
    now = time.time()
    relative = last < 1e8
    if args.replay:
        offset = 0.0  # computed per row below
    elif args.shift_to_now or relative:
        offset = now - last
        print(dim(f"  {'timestamps are relative; ' if relative else ''}shifting so the data ends now"))
    else:
        offset = 0.0

    writer = Writer(influx, buckets)
    decoder = FrameDecoder(dbc, args.schema)
    start = time.time()
    if args.replay:
        print(f"Replaying {last - first:.0f} s of data at {args.replay:g}x - Ctrl+C to stop")
    try:
        for item in src.items():
            for row in decoder.rows(item) if isinstance(item, Frame) else [item]:
                if args.replay:
                    ts = start + (row.ts - first) / args.replay
                    wait = ts - time.time()
                    if wait > 0.25:
                        writer.flush()
                        time.sleep(wait)
                else:
                    ts = row.ts + offset
                writer.add(row._replace(ts=ts))
    except KeyboardInterrupt:
        print("\nStopped")
    writer.flush()

    decoder.report()
    if not writer.points:
        raise PreviewError("nothing was written")
    span = f"{datetime.fromtimestamp(writer.t_min):%Y-%m-%d %H:%M:%S} .. {datetime.fromtimestamp(writer.t_max):%H:%M:%S}"
    print(green(f"Wrote {writer.points} points ({writer.fields} values) to {', '.join(buckets)}") + f"  {span}")
    print(dim(f"  measurements: {', '.join(f'{m} ({n})' for m, n in writer.measurements.most_common())}"))
    dashes = [load_dashboard(p) for p in args.dashboard] or dashboards_touching(writer.measurements, buckets)
    time_range = f"from={int(writer.t_min * 1000) - 5000}&to={int(writer.t_max * 1000) + 5000}"
    print_links(dashes, time_range)
    return 0


# <----- draft / wipe ----->

def cmd_draft(args) -> int:
    text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8-sig")
    try:
        dash = json.loads(text)
    except ValueError as e:
        raise PreviewError(f"not valid JSON: {e}") from None
    if "panels" not in dash and isinstance(dash.get("dashboard"), dict):
        dash = dash["dashboard"]
    # "Export for sharing externally" swaps the datasource for ${DS_INFLUXDB}; point it back at ours
    dash = json.loads(json.dumps(dash).replace("${DS_INFLUXDB}", DATASOURCE_UID))
    dash.pop("__inputs", None)
    title = str(dash.get("title") or "Untitled")
    title = title if title.startswith("[DRAFT] ") else f"[DRAFT] {title}"
    uid = "draft-" + hashlib.sha1(str(dash.get("uid") or title).encode()).hexdigest()[:12]
    dash.update(id=None, uid=uid, title=title)

    DRAFTS_DIR.mkdir(exist_ok=True)
    out = DRAFTS_DIR / (re.sub(r"\W+", "_", title[len("[DRAFT] "):]).strip("_") + ".json")
    out.write_text(json.dumps(dash, indent=2), encoding="utf-8")
    print(green(f"Wrote {rel(out)}") + "  (Grafana picks it up within ~5 s)")
    print(f"  {dashboard_link(dash, 'from=now-15m&to=now')}")
    a = analyze(dash, Dbc(args.dbc), out)
    if a.findings:
        print_findings(a.findings, quiet=True)
    return 0


def cmd_wipe(args) -> int:
    buckets = args.bucket or [DEFAULT_BUCKET]
    influx = connect(args, buckets, create_buckets=False)
    if not args.yes:
        answer = input(f"Delete ALL data in {', '.join(buckets)} at {influx.url}? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Nothing deleted")
            return 1
    for bucket in buckets:
        influx.delete_all(bucket)
        print(green(f"Emptied {bucket}"))
    return 0


# <----- CLI ----->

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dbc", type=Path, default=DEFAULT_DBC, help=f"DBC file (default: {rel(DEFAULT_DBC)})")

    influx = argparse.ArgumentParser(add_help=False)
    influx.add_argument("--influx-url", default=INFLUX_URL, help="default: %(default)s (the sandbox)")
    influx.add_argument("--token", default=INFLUX_TOKEN, help="InfluxDB token (default: the sandbox's)")
    influx.add_argument("--org", default=INFLUX_ORG, help="default: %(default)s")
    influx.add_argument("--bucket", action="append",
                        help="bucket to write; repeatable (default: what the dashboard queries, else CAN_prod)")
    influx.add_argument("--schema", choices=["link", "cellular"], default="link",
                        help="tag layout: link = parser/main.py (car + class tags, default); "
                             "cellular = parser/cellular_parser.py (class only, plus can_timestamp)")
    influx.add_argument("--allow-non-sandbox", action="store_true",
                        help="allow writing to an InfluxDB other than the sandbox")

    parser = argparse.ArgumentParser(prog="preview.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check", parents=[common], help="cross-check dashboard queries against the DBC")
    p.add_argument("dashboards", nargs="*", type=Path, help="dashboard JSON files (default: all in dashboards/)")
    p.add_argument("-q", "--quiet", action="store_true", help="only errors and warnings")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("synth", parents=[common, influx], help="write realistic synthetic data")
    p.add_argument("-d", "--dashboard", action="append", type=Path, default=[],
                   help="only generate the messages this dashboard queries (repeatable)")
    p.add_argument("--minutes", type=float, default=15, help="history to backfill (default: %(default)s)")
    p.add_argument("--hz", type=float, default=2, help="frames per second per message (default: %(default)s)")
    p.add_argument("--live", action="store_true", help="keep streaming after the backfill")
    p.add_argument("--messages", metavar="REGEX", help="only messages whose name matches")
    p.add_argument("--fill-missing", action="store_true",
                   help="also fake fields the dashboard queries but the DBC doesn't define")
    p.add_argument("--seed", type=int, default=7, help="random seed (default: %(default)s)")
    p.add_argument("--out", type=Path, help="write a candump log file instead of writing to InfluxDB")
    p.set_defaults(func=cmd_synth)

    p = sub.add_parser("upload", parents=[common, influx], help="decode and write a CAN log or CSV")
    p.add_argument("file", type=Path, help="candump log, CSV (raw frames, signal columns or InfluxDB CSV); .gz ok")
    p.add_argument("--format", choices=["auto", "candump", "frames", "influx", "wide"], default="auto")
    p.add_argument("--shift-to-now", action="store_true", help="move timestamps so the data ends now")
    p.add_argument("--replay", type=float, nargs="?", const=1.0, metavar="SPEED",
                   help="stream the data in real time (optionally sped up) so live panels animate")
    p.add_argument("--id-base", choices=["auto", "hex", "dec"], default="auto", help="CAN ID base in CSVs")
    p.add_argument("-d", "--dashboard", action="append", type=Path, default=[], help="dashboard to link to")
    p.set_defaults(func=cmd_upload)

    p = sub.add_parser("draft", parents=[common], help="load a dashboard JSON into the sandbox's Drafts folder")
    p.add_argument("file", help="dashboard JSON, or - to read it from stdin")
    p.set_defaults(func=cmd_draft)

    p = sub.add_parser("wipe", parents=[influx], help="delete all data from sandbox buckets")
    p.add_argument("-y", "--yes", action="store_true", help="don't ask for confirmation")
    p.set_defaults(func=cmd_wipe)
    return parser


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")  # don't die on odd characters in a legacy Windows console
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except PreviewError as e:
        sys.stdout.flush()
        print(red("error: ") + str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
