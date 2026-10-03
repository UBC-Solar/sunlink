# Dashboard Preview Sandbox

See exactly how a Grafana dashboard looks with data before it goes anywhere near the car. It runs the
**same Grafana (9.5.2) and InfluxDB (2.7.1)** as the real stack, provisions the repo's `dashboards/`
folder the same way, and fills InfluxDB with data decoded through `dbc/brightside.dbc` using the
same schema as the parser. The sandbox is separate from the real stack: it has its own ports and
volumes, and nothing it writes reaches `CAN_prod` on the real InfluxDB.

```
CAN frames ──► dbc/brightside.dbc ──► InfluxDB (sandbox) ──► Grafana (sandbox)
   ▲ synth: generated                  measurement = sender (HVC, MST, ...)
   ▲ upload: candump / CSV             tags car, class = message name; field = signal
```

## 1. Start it

Docker runs inside WSL, so run this from a WSL terminal in the repo:

```bash
sudo docker compose -f tools/dashboard_preview/docker-compose.yaml up -d
```

- Grafana: <http://localhost:3001> (no login needed)
- InfluxDB UI: <http://localhost:8087> (`admin` / `sunlink-preview`)

The script needs Python 3.9+ and `cantools`. The Sunlink virtualenv already has it; otherwise run
`pip install -r tools/dashboard_preview/requirements.txt`. It runs from Windows or WSL.

## 2. Put data in

```bash
# Realistic data for every signal a dashboard uses (last 15 min), then keep it streaming live
python tools/dashboard_preview/preview.py synth -d dashboards/PROD/PROD_BMS_CASCADIA.json --live

# A real CAN log: candump, PCAN-View / Kvaser CSV, a memorator_upload*.csv, or signal columns
python tools/dashboard_preview/preview.py upload my_log.csv --shift-to-now
python tools/dashboard_preview/preview.py upload candump-2026-09-29.log --replay 5   # animate at 5x
```

Each command prints a link that opens the matching dashboard at the right time range.

## 3. Check a dashboard against the DBC

```bash
python tools/dashboard_preview/preview.py check dashboards/PROD/PROD_BMS_CASCADIA.json
```

This reports queries that can never return data, like a field that isn't in the DBC, the wrong
`_measurement`, or a `class` filter that doesn't match. It also flags things that make panels look
wrong: fault flags averaged with `fn: mean`, override matchers for non-existent classes, missing
units, and numbered signals the dashboard never shows. With no file argument it checks every dashboard.
The exit code is 1 if there are errors, so it can run in CI.

## Commands

| Command | What it does |
| --- | --- |
| `check [FILES]` | Cross-check Flux queries against the DBC. `-q` hides notes. |
| `synth -d DASH` | Generate frames for the messages `DASH` queries, encode + decode them through the DBC, write them. `--minutes`, `--hz`, `--live`, `--fill-missing` (fake fields the DBC lacks), `--out FILE` (write a candump log instead). Without `-d` it generates every DBC message. |
| `upload FILE` | Decode and write a log. `--shift-to-now` moves it into the dashboard's default "last 15 min" window, `--replay [SPEED]` streams it in real time so the 1 s refresh animates. `.gz` files work. |
| `draft FILE` | Copy a dashboard JSON (e.g. exported from the production Grafana, or `-` to paste it) into a **Drafts** folder with its own uid, so it can sit next to the repo version. |
| `wipe` | Delete everything in the sandbox bucket(s). |

Options shared by the data commands include `--bucket` (default: whatever the dashboard queries,
otherwise `CAN_prod`), `--dbc`, and `--schema cellular` (the tag layout of `parser/cellular_parser.py`:
no `car` tag, plus a `can_timestamp` field).

### Upload formats (auto-detected, or pass `--format`)

| Format | Example |
| --- | --- |
| `candump` | `(1727600000.123456) can0 320#0000312C` (`candump -l`), or `can0 320 [4] 00 00 31 2C` with `-ta`/`-td`/no timestamps |
| `frames` | CSV with an ID column (`id`, `can_id`, `arbitration_id`, ...) plus a `data` column or `D0..D7` byte columns. Hex or decimal IDs are detected automatically. |
| `influx` | InfluxDB annotated CSV: the `memorator_upload_*.csv` link_telemetry writes, or an export from the InfluxDB UI |
| `wide` | `time` column plus one column per signal (`PackCurrent`, `MST.AvgTemp`, `PackCurrent (mA)`) |

Timestamps can be epoch s/ms/us/ns or ISO-8601 (naive = local time). Relative timestamps are placed
so the data ends now.

## How faithful is it?

- Frames are decoded with `cantools` and the same DBC, so the Influx schema matches `parser/main.py`. If a frame
  ID is defined twice, the last definition wins, same as the parser. Frames whose length doesn't
  match the DBC are dropped and counted, which the parser does too.
- Values are always written as floats. The two parsers disagree on int vs float, and mixing types in
  one bucket makes InfluxDB reject writes. Grafana displays them identically.
- `synth` values aren't random noise. Module voltages, `TotalVoltage`, min/max indices,
  temperatures and the balance bitmap all come from one pack model, so they agree with each other.
  A couple of modules run high and one runs hot, so thresholds get exercised, and each fault flag
  briefly turns on every few minutes so you can see the "Bad" state.

## Editing dashboards

Repo dashboards are mounted read-only and reloaded every 5 s, so the loop is: edit the JSON in
`dashboards/`, then refresh the browser. If you'd rather edit in the Grafana UI, save there (it lives in
the sandbox only), then copy **Dashboard settings → JSON Model** back into the repo file.

## Stop / reset

```bash
sudo docker compose -f tools/dashboard_preview/docker-compose.yaml down      # keeps data
sudo docker compose -f tools/dashboard_preview/docker-compose.yaml down -v   # wipes everything
```

## Troubleshooting

- **`can't reach InfluxDB at http://127.0.0.1:8087`**: the stack isn't running (step 1), or WSL
  was shut down since.
- **A panel says "No data"**: run `check` on the dashboard first. Also make sure the time picker
  covers the data (the printed links set it for you).
- **`field type conflict`**: that bucket already has the field with another type, e.g. from an
  older write. `preview.py wipe` clears it.
- **Writing to something other than the sandbox** needs `--allow-non-sandbox`, so test data can't
  end up in real telemetry by accident.
