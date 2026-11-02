# Cascadia data simulator

Generates realistic Cascadia CAN data for the **TEL, MDI, DRD and STR** boards and writes it to your
local InfluxDB. Use it to look at the Cascadia Grafana dashboards without the car. It sends the same
frame IDs, rates and fault logic as `firmware_v4`. Each frame is encoded with `dbc/cascadia.dbc` and
then decoded the way the parser does. Points are written with sunlink's layout: measurement = sender,
field = signal, tags `car` and `class`.

A control panel lets you change what's happening while it runs: drive state, throttle, GPS fix,
temperatures, supply voltages, faults and so on. Presets jump straight to common cases.

## 1. Install

You need the normal sunlink setup: Docker running InfluxDB and Grafana, the `environment` venv, and a
`.env` file in the sunlink root. If you haven't done that yet, follow the main [README](../../README.md)
(`MacOS_setup.sh` on Mac, `setup.sh` on Linux).

Then, from the sunlink root:

```bash
source environment/bin/activate
pip install -r requirements.txt          # Mac: requirements_MacOS.txt
```

The simulator only uses `cantools`, `influxdb-client` and `python-dotenv` from that list. The Tk
window (`--tk`) also needs a Python with Tk support. Most installs have it. If yours doesn't, use the
browser panel.

Check that:

- the containers are up: `docker compose up -d`. InfluxDB should be on `localhost:8086` and Grafana
  on `localhost:3000`.
- `.env` contains `INFLUX_TOKEN` and `INFLUX_ORG`. The setup script writes both.
- the `CAN_prod` bucket exists. The setup script creates it.

The Cascadia dashboards (`dashboards/PROD/PROD_*_Cascadia.json`) are mounted into Grafana
automatically. If they don't appear, run `docker compose restart grafana`.

## 2. Run

Run every command from the sunlink root with the venv active.

```bash
python tools/cascadia_sim/cascadia_sim.py
```

This starts writing data and opens the control panel at <http://localhost:8090>. The panel has
scenario buttons, toggles and sliders for every input, a live readout, and links to the four
dashboards. Stop it with Ctrl+C.

Other ways to run it:

```bash
python tools/cascadia_sim/cascadia_sim.py --tk                    # same controls in a Tk window
python tools/cascadia_sim/cascadia_sim.py --list-scenarios        # show the presets
python tools/cascadia_sim/cascadia_sim.py --scenario gps_lost --headless --duration 120   # no UI, 2 minutes
```

Then open a dashboard. Set the time range to the last 5 minutes and refresh to 1 s:

| Board | URL |
|---|---|
| TEL | <http://localhost:3000/d/cascadia-prod-tel> |
| MDI | <http://localhost:3000/d/cascadia-prod-mdi> |
| DRD | <http://localhost:3000/d/cascadia-prod-drd> |
| STR | <http://localhost:3000/d/cascadia-prod-str> |

### Options

| Flag | Default | What it does |
|---|---|---|
| `--scenario NAME` | `normal` | Preset to start in (see below) |
| `--headless` | off | No window or panel. Runs the scenario and prints how many frames were written |
| `--duration SECONDS` | forever | How long a headless run lasts |
| `--tk` | off | Tk window instead of the browser panel |
| `--port N` | `8090` | Port for the browser panel (bound to 127.0.0.1 only) |
| `--url URL` | `http://localhost:8086` | InfluxDB to write to |
| `--bucket NAME` | `CAN_prod` | Bucket to write to |
| `--dbc PATH` | `dbc/cascadia.dbc` | DBC used to encode and decode |
| `--allow-remote` | off | Allow writing to an InfluxDB that isn't on localhost |

### Scenarios

| Name | Situation |
|---|---|
| `normal` | Normal driving: 3D fix, everything in band |
| `parked` | Parked on the bench, no throttle |
| `cruise` | Cruise at 60 km/h |
| `gps_lost` | GPS lost (no fix, few satellites) |
| `motor_overheat` | Hard driving, motor temperature climbs past 100 °C |
| `rtd_failure` | Motor RTD open circuit |
| `drd_mcu_hot` | DRD MCU over temperature |
| `str_brownout` | STR supply sagging below 2400 mV |
| `tel_link_down` | TEL stops sending (radio/CAN down) |
| `drd_reset` | DRD watchdog reset |
| `pedal_mismatch` | Throttle sensors disagree |
| `timeouts` | DRD lost its cyclic inputs (BMS/MC silent) |
| `bus_overload` | CAN bus load 92 % |

## Safety

- **Local only by default.** The simulator refuses to write anywhere other than `localhost` unless you
  pass `--allow-remote`. Don't point it at a shared or race InfluxDB.
- **Simulated points are tagged.** Every point it writes has the tag `source=cascadia_sim`.
  **Reset everything to normal** in the panel restores normal inputs, clears latched faults, and
  deletes only points with that tag. Real data imported into the same bucket is left alone. The
  dashboards ignore the tag, so simulated and real data look the same on them.
- The `car` tag comes from `CAR_NAME` in `LINK_CONSTANTS.py`.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'cantools'` | The venv isn't active, or the requirements aren't installed (step 1) |
| `KeyError: 'INFLUX_TOKEN'` | `.env` is missing or incomplete. Re-run the setup script |
| `refusing to write simulated data to ...` | `--url` isn't localhost. Add `--allow-remote` only if you really mean it |
| Dashboards are empty | Check the time range is recent, the bucket is `CAN_prod`, and the panel's frame counter is going up |
| Port 8090 already in use | Pass `--port 8091` (or any free port) |
