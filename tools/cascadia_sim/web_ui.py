"""
web_ui.py: browser control panel for cascadia_sim (stdlib only).

Serves one page on http://localhost:8090 with scenario buttons, toggle buttons, sliders and
action buttons for every adjustable input, plus a live readout. Bound to 127.0.0.1 only.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GRAFANA = "http://localhost:3000/d/cascadia-prod-{}?orgId=1&from=now-5m&to=now&refresh=1s"


def controls(mod):
    """UI spec: (board, [controls]). Keys are State attributes, 'attr.sub' for dict entries."""
    boards = []
    for b in ("DRD", "MDI", "TEL", "STR"):
        c = [{"type": "toggle", "key": f"link.{b}", "label": "Sending (link up)"},
             {"type": "toggle", "key": f"watchdog.{b}", "label": "Watchdog reset flag", "bad": True},
             {"type": "action", "name": f"reboot.{b}", "label": "Reboot (uptime → 0)"}]
        if b in ("TEL", "DRD", "STR"):
            c += [{"type": "slider", "key": f"vdd.{b}", "label": "MCU Vdd", "unit": "mV", "min": 1800, "max": 3600,
                   "step": 10, "limit": mod.UV_MV[b], "limit_dir": "below"},
                  {"type": "slider", "key": f"mcu_temp.{b}", "label": "MCU temperature", "unit": "°C", "min": -20,
                   "max": 140, "step": 1, "limit": mod.OT_C[b], "limit_dir": "above"}]
        boards.append([b, c])
    extra = {
        "DRD": [{"type": "choice", "key": "drive_state", "label": "Drive state", "options": list(mod.DRIVE_STATES)},
                {"type": "slider", "key": "throttle", "label": "Throttle pedal", "unit": "%", "min": 0, "max": 100, "step": 1},
                {"type": "toggle", "key": "brake", "label": "Brake pressed"},
                {"type": "toggle", "key": "regen_enabled", "label": "Regen enabled"},
                {"type": "toggle", "key": "eco", "label": "Eco mode"},
                {"type": "toggle", "key": "kph", "label": "Units KPH"},
                {"type": "slider", "key": "soc", "label": "SOC", "unit": "%", "min": 0, "max": 104, "step": 1},
                {"type": "toggle", "key": "adc_mismatch", "label": "Throttle sensors mismatch", "bad": True},
                {"type": "toggle", "key": "adc_out_of_range", "label": "Throttle ADC out of range", "bad": True},
                {"type": "toggle", "key": "motor_comm_fault", "label": "Motor comm fault", "bad": True}]
               + [{"type": "toggle", "key": f"timeouts.{k}", "label": f"{k} timeout", "bad": True}
                  for k in ("Speed", "DriveState", "SOC", "Voltage", "Current", "Accel")],
        "MDI": [{"type": "slider", "key": "motor_heat", "label": "Motor heating factor", "unit": "×", "min": 0, "max": 10, "step": 0.1},
                {"type": "action", "name": "motor_temp.25", "label": "Motor temp → 25 °C"},
                {"type": "action", "name": "motor_temp.98", "label": "Motor temp → 98 °C"},
                {"type": "action", "name": "motor_temp.105", "label": "Motor temp → 105 °C"},
                {"type": "toggle", "key": "rtd_ok", "label": "RTD reads OK"},
                {"type": "choice", "key": "rtd_flags", "label": "RTD fault (when failing)", "options": list(mod.RTD_FLAGS)}],
        "TEL": [{"type": "choice", "key": "gps_fix", "label": "GPS fix", "options": list(mod.GPS_FIX)},
                {"type": "slider", "key": "sats", "label": "Satellites used", "unit": "", "min": 0, "max": 30, "step": 1},
                {"type": "slider", "key": "bus_load", "label": "CAN bus load", "unit": "%", "min": 0, "max": 100, "step": 1},
                {"type": "toggle", "key": "gps_read_fail", "label": "GPS read fail", "bad": True},
                {"type": "toggle", "key": "imu_read_fail", "label": "IMU read fail (no IMU frames)", "bad": True}],
        "STR": [{"type": "toggle", "key": "left", "label": "Left turn signal"},
                {"type": "toggle", "key": "right", "label": "Right turn signal"},
                {"type": "toggle", "key": "horn", "label": "Horn"},
                {"type": "toggle", "key": "ptt", "label": "Push to talk"},
                {"type": "toggle", "key": "cruise_inc", "label": "Cruise + (held)"},
                {"type": "toggle", "key": "cruise_dec", "label": "Cruise − (held)"},
                {"type": "slider", "key": "cruise_set", "label": "Cruise set speed", "unit": "km/h", "min": 0, "max": 150, "step": 1}],
    }
    for bc in boards:
        bc[1] += extra[bc[0]]
    return boards


def get_key(state, key):
    if "." in key:
        a, s = key.split(".", 1)
        return getattr(state, a)[s]
    return getattr(state, key)


def set_key(state, key, value):
    cur = get_key(state, key)
    if isinstance(cur, bool):
        value = bool(value)
    elif isinstance(cur, int):
        value = int(float(value))
    elif isinstance(cur, float):
        value = float(value)
    if "." in key:
        a, s = key.split(".", 1)
        getattr(state, a)[s] = value
    else:
        setattr(state, key, value)


def snapshot(sim, spec):
    vals = {c["key"]: get_key(sim.state, c["key"]) for _, cs in spec for c in cs if "key" in c}
    return {"values": vals, "speed": round(sim.speed * 3.6, 1), "motor_temp": round(sim.motor_temp, 1),
            "motor_ot": sim.motor_ot, "soc": round(sim.state.soc, 1), "frames": sim.frames,
            "scenario": getattr(sim, "scenario", "normal")}


def serve(sim, mod, port=8090):
    spec = controls(mod)
    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                return self._send(200, PAGE, "text/html; charset=utf-8")
            if self.path == "/api/spec":
                scen = [{"name": k, "desc": d} for k, (d, _) in mod.SCENARIOS.items()]
                return self._send(200, json.dumps({"boards": spec, "scenarios": scen, "grafana": GRAFANA}))
            if self.path == "/api/state":
                with lock:
                    return self._send(200, json.dumps(snapshot(sim, spec)))
            self._send(404, "{}")

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            with lock:
                try:
                    if self.path == "/api/set":
                        set_key(sim.state, body["key"], body["value"])
                    elif self.path == "/api/scenario":
                        mod.apply_scenario(sim, body["name"])
                        sim.scenario = body["name"]
                    elif self.path == "/api/action":
                        what, arg = body["name"].split(".", 1)
                        if what == "reboot":
                            sim.reset_board(arg)
                        elif what == "motor_temp":
                            sim.motor_temp = float(arg)
                    else:
                        return self._send(404, "{}")
                except (KeyError, ValueError, AttributeError) as e:
                    return self._send(400, json.dumps({"error": str(e)}))
                return self._send(200, json.dumps(snapshot(sim, spec)))

    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    return httpd


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cascadia Sim Controls</title>
<style>
:root{--bg:#f4f5f7;--card:#fff;--text:#1d2129;--muted:#6b7280;--line:#e3e5e8;--btn:#eef0f3;
 --on:#3b6fd8;--on-text:#fff;--bad:#d9363e;--warn:#d97a0b;--ok:#6b7280}
@media (prefers-color-scheme:dark){:root{--bg:#111317;--card:#1b1e24;--text:#e6e8eb;--muted:#9aa1ab;--line:#2b2f37;
 --btn:#262a32;--on:#5794f2;--on-text:#0b0d10;--bad:#f2495c;--warn:#ff9830}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.4 system-ui,-apple-system,sans-serif}
header{position:sticky;top:0;z-index:2;background:var(--bg);padding:12px 16px 8px;border-bottom:1px solid var(--line)}
h1{font-size:17px;margin:0 0 8px}.status{display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);font-variant-numeric:tabular-nums}
.status b{color:var(--text);font-weight:600}.status .alarm b{color:var(--bad)}
.scen{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
button{font:inherit;border:1px solid var(--line);background:var(--btn);color:var(--text);border-radius:8px;padding:7px 11px;cursor:pointer}
button:hover{border-color:var(--muted)}button.active{background:var(--on);color:var(--on-text);border-color:var(--on)}
button.bad.active{background:var(--bad);border-color:var(--bad);color:#fff}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:12px;padding:12px 16px 24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.card h2{font-size:15px;margin:0 0 10px;display:flex;justify-content:space-between;align-items:center}
.card h2 a{font-size:12px;font-weight:400;color:var(--on);text-decoration:none}
.row{display:flex;align-items:center;gap:10px;margin:7px 0}.row label{flex:0 0 118px;color:var(--muted)}
.row.choice{flex-direction:column;align-items:flex-start;gap:4px}.row.choice label{flex:none}
.row input[type=range]{flex:1;min-width:0}.val{flex:0 0 70px;text-align:right;font-variant-numeric:tabular-nums}
.val.alarm{color:var(--bad);font-weight:600}.toggles{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.seg{display:flex;flex-wrap:wrap;gap:4px}.seg button{padding:5px 9px}
.desc{color:var(--muted);margin-top:6px;min-height:1.4em}
</style></head><body>
<header><h1>Cascadia CAN simulator: what goes in</h1>
<div class="status" id="status"></div>
<div class="scen" id="scen"></div><div class="desc" id="desc"></div></header>
<main id="main"></main>
<script>
let spec, state = {values:{}};
const $ = s => document.querySelector(s);
const post = (p, b) => fetch(p, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(b)})
  .then(r => r.json()).then(s => { state = s; render(); });
function fmt(c, v){ return (c.step < 1 ? Number(v).toFixed(1) : Math.round(v)) + (c.unit ? " " + c.unit : ""); }
function alarmed(c, v){ return c.limit != null && (c.limit_dir === "below" ? v < c.limit : v > c.limit); }
function build(){
  $("#scen").innerHTML = "";
  spec.scenarios.forEach(s => { const b = document.createElement("button"); b.textContent = s.name.replace(/_/g," ");
    b.title = s.desc; b.dataset.scen = s.name; b.onclick = () => post("/api/scenario", {name:s.name}); $("#scen").append(b); });
  $("#main").innerHTML = "";
  spec.boards.forEach(([board, cs]) => {
    const card = document.createElement("section"); card.className = "card";
    card.innerHTML = `<h2>${board}<a href="${spec.grafana.replace("{}", board.toLowerCase())}" target="_blank">open dashboard ↗</a></h2>`;
    let tg = null;
    cs.forEach(c => {
      if (c.type === "toggle" || c.type === "action") {
        if (!tg) { tg = document.createElement("div"); tg.className = "toggles"; card.append(tg); }
        const b = document.createElement("button"); b.textContent = c.label;
        if (c.type === "toggle") { b.dataset.key = c.key; if (c.bad) b.classList.add("bad");
          b.onclick = () => post("/api/set", {key:c.key, value:!state.values[c.key]}); }
        else b.onclick = () => post("/api/action", {name:c.name});
        tg.append(b); return;
      }
      tg = null;
      const row = document.createElement("div"); row.className = "row";
      row.innerHTML = `<label>${c.label}</label>`;
      if (c.type === "slider") {
        const r = document.createElement("input"); Object.assign(r, {type:"range", min:c.min, max:c.max, step:c.step});
        r.dataset.key = c.key; const v = document.createElement("span"); v.className = "val"; v.dataset.val = c.key;
        r.oninput = () => { v.textContent = fmt(c, r.value); v.classList.toggle("alarm", alarmed(c, +r.value)); };
        r.onchange = () => post("/api/set", {key:c.key, value:+r.value});
        row.append(r, v);
      } else {
        row.classList.add("choice"); const seg = document.createElement("div"); seg.className = "seg";
        c.options.forEach(o => { const b = document.createElement("button"); b.textContent = o; b.dataset.key = c.key; b.dataset.opt = o;
          b.onclick = () => post("/api/set", {key:c.key, value:o}); seg.append(b); });
        row.append(seg);
      }
      card.append(row);
    });
    $("#main").append(card);
  });
}
function render(){
  const v = state.values, all = spec.boards.flatMap(b => b[1]);
  document.querySelectorAll("button[data-key]").forEach(b => {
    b.classList.toggle("active", b.dataset.opt ? v[b.dataset.key] === b.dataset.opt : !!v[b.dataset.key]); });
  document.querySelectorAll("input[data-key]").forEach(r => { if (document.activeElement !== r) {
    const c = all.find(x => x.key === r.dataset.key); r.value = v[c.key];
    const s = document.querySelector(`[data-val="${c.key}"]`); s.textContent = fmt(c, v[c.key]); s.classList.toggle("alarm", alarmed(c, v[c.key])); } });
  document.querySelectorAll("button[data-scen]").forEach(b => b.classList.toggle("active", b.dataset.scen === state.scenario));
  const sc = spec.scenarios.find(s => s.name === state.scenario); $("#desc").textContent = sc ? sc.desc : "";
  $("#status").innerHTML = `<span>speed <b>${state.speed} km/h</b></span>
    <span class="${state.motor_ot ? "alarm" : ""}">motor <b>${state.motor_temp} °C${state.motor_ot ? " OVERTEMP" : ""}</b></span>
    <span>SOC <b>${state.soc} %</b></span><span>frames written <b>${state.frames}</b></span>`;
}
fetch("/api/spec").then(r => r.json()).then(s => { spec = s; build();
  const tick = () => fetch("/api/state").then(r => r.json()).then(st => { state = st; render(); }).catch(() => {});
  tick(); setInterval(tick, 700); });
</script></body></html>
"""
