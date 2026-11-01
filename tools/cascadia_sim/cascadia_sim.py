#!/usr/bin/env python3
"""
cascadia_sim.py: adjustable, realistic Cascadia CAN data for TEL, MDI, DRD and STR.

Builds the frames each board sends (same IDs, rates and fault logic as firmware_v4),
encodes them with the DBC, decodes them back the way the parser does, and writes them to
InfluxDB with sunlink's layout (measurement = sender, field = signal, tags car/class).
A small window lets you change the situation while it runs; presets jump to common cases.

    python tools/cascadia_sim/cascadia_sim.py                      # browser control panel (localhost:8090)
    python tools/cascadia_sim/cascadia_sim.py --tk                 # same controls in a Tk window
    python tools/cascadia_sim/cascadia_sim.py --scenario gps_lost --headless --duration 120
    python tools/cascadia_sim/cascadia_sim.py --list-scenarios

Reads INFLUX_TOKEN / INFLUX_ORG from ./.env. Writes only to localhost unless --allow-remote.
"""
from __future__ import annotations

import argparse
import math
import random
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import cantools

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
try:
    from LINK_CONSTANTS import CAR_NAME
except Exception:  # noqa: BLE001
    CAR_NAME = "Brightside"

# Firmware limits (firmware_v4 origin/main, 2026-10-31)
UV_MV = {"TEL": 2000, "DRD": 2000, "STR": 2400}
OT_C = {"TEL": 125, "DRD": 125, "STR": 105}
MOTOR_OT_SET, MOTOR_OT_CLEAR = 100, 95

DRIVE_STATES = {"PARK": 3, "FORWARD": 1, "REVERSE": 4, "CRUISE": 2}
GPS_FIX = {"NoFix": 0, "DeadReckoning": 1, "Fix2D": 2, "Fix3D": 3, "GnssDeadReckoning": 4, "TimeOnly": 5}
RTD_FLAGS = {"none": 0, "RTD high (open)": 128, "RTD low (short)": 64, "OV/UV": 4}

TRACK_CENTER = (49.2606, -123.2460)   # generic oval near UBC; ~2.2 km lap
TRACK_A, TRACK_B = 450.0, 220.0       # semi-axes in metres


class State:
    """Everything you can adjust. The GUI and the presets only touch this."""

    def __init__(self):
        self.link = {b: True for b in ("TEL", "MDI", "DRD", "STR")}
        self.vdd = {"TEL": 3300.0, "DRD": 3300.0, "STR": 3300.0}
        self.mcu_temp = {"TEL": 38.0, "DRD": 34.0, "STR": 31.0}
        self.watchdog = {b: False for b in ("TEL", "MDI", "DRD", "STR")}
        # driving
        self.drive_state = "FORWARD"
        self.throttle = 35.0        # % pedal
        self.brake = False
        self.regen_enabled = True
        self.eco = False
        self.kph = True
        self.soc = 82.0
        self.cruise_set = 50
        # DRD diagnostics
        self.adc_mismatch = False
        self.adc_out_of_range = False
        self.motor_comm_fault = False
        self.timeouts = {k: False for k in ("Speed", "DriveState", "SOC", "Voltage", "Current", "Accel")}
        # MDI
        self.motor_heat = 1.0       # heating factor (1 = normal)
        self.rtd_ok = True
        self.rtd_flags = "none"
        # TEL
        self.gps_fix = "Fix3D"
        self.sats = 14
        self.gps_read_fail = False
        self.imu_read_fail = False
        self.bus_load = 35.0
        # STR
        self.left = self.right = self.horn = self.ptt = False
        self.cruise_inc = self.cruise_dec = False


SCENARIOS = {
    "normal":         ("Normal driving: 3D fix, everything in band", {}),
    "parked":         ("Parked on the bench, no throttle", {"drive_state": "PARK", "throttle": 0.0}),
    "cruise":         ("Cruise at 60 km/h", {"drive_state": "CRUISE", "cruise_set": 60}),
    "gps_lost":       ("GPS lost (no fix, few satellites)", {"gps_fix": "NoFix", "sats": 2}),
    "motor_overheat": ("Hard driving, motor temperature climbs past 100 °C", {"throttle": 90.0, "motor_heat": 6.0}),
    "rtd_failure":    ("Motor RTD open circuit", {"rtd_ok": False, "rtd_flags": "RTD high (open)"}),
    "drd_mcu_hot":    ("DRD MCU over temperature", {"mcu_temp.DRD": 128.0}),
    "str_brownout":   ("STR supply sagging below 2400 mV", {"vdd.STR": 2300.0}),
    "tel_link_down":  ("TEL stops sending (radio/CAN down)", {"link.TEL": False}),
    "drd_reset":      ("DRD watchdog reset", {"watchdog.DRD": True, "_reset": "DRD"}),
    "pedal_mismatch": ("Throttle sensors disagree", {"adc_mismatch": True}),
    "timeouts":       ("DRD lost its cyclic inputs (BMS/MC silent)",
                       {"timeouts": {k: True for k in ("Speed", "DriveState", "SOC", "Voltage", "Current", "Accel")}}),
    "bus_overload":   ("CAN bus load 92 %", {"bus_load": 92.0}),
}


def apply_scenario(sim: "Sim", name: str):
    sim.state = State()
    sim.motor_temp = 45.0
    for key, val in SCENARIOS[name][1].items():
        if key == "_reset":
            sim.reset_board(val)
        elif "." in key:
            attr, sub = key.split(".")
            getattr(sim.state, attr)[sub] = val
        else:
            setattr(sim.state, key, val)


class Sim:
    def __init__(self, dbc: str, writer, clear_history=None):
        self.db = cantools.database.load_file(dbc)
        self.write = writer
        self.clear_history = clear_history
        self.lock = threading.Lock()
        self.state = State()
        self.boot = {b: time.time() - random.uniform(300, 900) for b in ("TEL", "MDI", "DRD", "STR")}
        self.speed = 0.0            # m/s
        self.s = 0.0                # distance along track, m
        self.motor_temp = 45.0
        self.motor_ot = False
        self.rtd_bad = 0
        self.tick = 0
        self.frames = 0
        self.stop = threading.Event()

    def reset_board(self, b):
        self.boot[b] = time.time()

    def reset_all(self):
        """Back to normal and forget the past: normal inputs, latches cleared, and the simulated
        TEL/MDI/DRD/STR history deleted from the (local) bucket so no old faults show as CLEARED."""
        with self.lock:
            apply_scenario(self, "normal")
            self.scenario = "normal"
            self.motor_ot = False
            self.rtd_bad = 0
            if self.clear_history:
                self.clear_history()

    # ------------------------------------------------------------------ physics
    def step(self, dt):
        st = self.state
        target = 0.0
        if st.drive_state == "CRUISE":
            target = st.cruise_set / 3.6
        elif st.drive_state in ("FORWARD", "REVERSE") and not st.brake:
            target = (st.throttle / 100.0) * (80 if st.eco else 100) / 3.6
        tau = 1.5 if st.brake else 6.0
        accel = (target - self.speed) / tau
        self.prev_speed = self.speed
        self.speed = max(0.0, self.speed + accel * dt)
        self.accel = accel
        self.s += self.speed * dt
        power = (st.throttle / 100.0) * (self.speed / 25.0) if st.drive_state != "PARK" else 0.0
        heat_in = 4.0 * st.motor_heat * power
        self.motor_temp += (heat_in - 0.012 * (self.motor_temp - 25.0)) * dt
        if not self.motor_ot and self.motor_temp >= MOTOR_OT_SET:
            self.motor_ot = True
        elif self.motor_ot and self.motor_temp <= MOTOR_OT_CLEAR:
            self.motor_ot = False
        st.soc = max(0.0, st.soc - power * 0.002 * dt)
        st.cruise_set = max(0, min(150, st.cruise_set + (1 if st.cruise_inc else 0) - (1 if st.cruise_dec else 0)))

    def position(self):
        # ellipse parametrised by arc length (approximate)
        perim = math.pi * (3 * (TRACK_A + TRACK_B) - math.sqrt((3 * TRACK_A + TRACK_B) * (TRACK_A + 3 * TRACK_B)))
        th = 2 * math.pi * (self.s % perim) / perim
        x, y = TRACK_A * math.cos(th), TRACK_B * math.sin(th)
        dx, dy = -TRACK_A * math.sin(th), TRACK_B * math.cos(th)
        heading = (math.degrees(math.atan2(dx, dy)) + 360) % 360   # 0 = north, clockwise
        lat = TRACK_CENTER[0] + y / 111_320
        lon = TRACK_CENTER[1] + x / (111_320 * math.cos(math.radians(TRACK_CENTER[0])))
        # curvature radius for lateral accel / yaw rate
        r = ((dx * dx + dy * dy) ** 1.5) / abs(dx * (-TRACK_B * math.sin(th)) - dy * (-TRACK_A * math.cos(th)))
        return lat, lon, heading, r

    # ------------------------------------------------------------------ frames
    def frames_now(self):
        st, t, now = self.state, self.tick, time.time()
        n = lambda v, s: v + random.gauss(0, s)  # noqa: E731
        out = []
        every_s = t % 10 == 0  # 1 Hz at 10 Hz tick

        def mcu(b):
            v, c = n(st.vdd[b], 4), n(st.mcu_temp[b], 0.3)
            return round(v), round(c), int(c > OT_C[b]), int(v < UV_MV[b])

        # ---- TEL
        if st.link["TEL"]:
            v, c, ot, uv = mcu("TEL")
            lat, lon, heading, r = self.position()
            fix = GPS_FIX[st.gps_fix]
            out += [("TELDiagnostics", {"TELWatchdogReset": int(st.watchdog["TEL"]), "IMUReadFail": int(st.imu_read_fail),
                                        "IMUWriteFail": 0, "GPSReadFail": int(st.gps_read_fail), "GPSWriteFail": 0,
                                        "MCUOvertemp": ot, "MCUUndervoltage": uv}),
                    ("TELMCUHealth", {"MCU_Voltage": v, "MCU_Temperature": c}),
                    ("CANBusLoad", {"BusLoad": max(0, min(100, round(n(st.bus_load, 2))))})]
            if not st.imu_read_fail:
                lat_acc = self.speed ** 2 / r if r else 0.0
                yaw = self.speed / r if r else 0.0
                hd = math.radians(heading)
                out += [("TELImuAG_X", {"ImuAGXAccel": n(self.accel, 0.08), "ImuAGXGyro": n(0, 0.01)}),
                        ("TELImuAGY", {"ImuAGYAccel": n(lat_acc, 0.08), "ImuAGYGyro": n(0, 0.01)}),
                        ("TELImuAGZ", {"ImuAGZAccel": n(9.81, 0.05), "ImuAGZGyro": n(yaw, 0.005)}),
                        ("TELImuMX", {"ImuMXMag": n(18 * math.cos(hd), 0.4)}),
                        ("TELImuMY", {"ImuMYMag": n(-18 * math.sin(hd), 0.4)}),
                        ("TELImuMZ", {"ImuMZMag": n(-49, 0.4)})]
            if every_s:
                out.append(("TELTimeSinceBootup", {"TELTimeSinceBootUp": int(now - self.boot["TEL"])}))
                sats = st.sats
                pdop = max(0.8, 12 / max(sats, 1))
                acc = 0.6 * pdop if fix in (3, 4) else 25.0 if fix == 2 else 0
                gm = time.gmtime(now)
                out += [("TELGpsStatus", {"GpsFixType": fix, "GpsFixOk": int(fix in (2, 3, 4)), "GpsDiffCorrections": 0,
                                          "GpsUtcDateValid": int(fix != 0), "GpsUtcTimeValid": int(fix != 0),
                                          "GpsUtcTimeResolved": int(fix != 0), "GpsSatsUsed": sats if fix else 0,
                                          "GpsSatsHeard": sats + 6, "GpsPDOP": round(pdop, 2) if fix else 99.99,
                                          "GpsHorizAccuracy": round(acc, 2) if fix else 655.35}),
                        ("TELGpsUtcTime", {"GpsSecond": gm.tm_sec, "GpsMinute": gm.tm_min, "GpsHour": gm.tm_hour,
                                           "GpsDay": gm.tm_mday, "GpsMonth": gm.tm_mon, "GpsYear": gm.tm_year})]
                if fix in (2, 3, 4):   # firmware only sends position/motion with a fix
                    out += [("TELGpsPosition", {"GpsLatitude": lat + random.gauss(0, 2e-6), "GpsLongitude": lon + random.gauss(0, 2e-6)}),
                            ("TELGpsMotion", {"GpsAltitude": n(82, 0.3), "GpsGroundSpeed": max(0, n(self.speed * 3.6, 0.2)),
                                              "GpsHeading": round(heading, 2)})]
        # ---- MDI (1 Hz superloop)
        if st.link["MDI"] and every_s:
            if st.rtd_ok:
                self.rtd_bad = max(0, self.rtd_bad - 1)
            else:
                self.rtd_bad = min(5, self.rtd_bad + 1)
            out += [("MDITimeSinceBootup", {"MDITimeSinceBootUp": int(now - self.boot["MDI"])}),
                    ("MDIDiagnostics", {"MDIWatchdogReset": int(st.watchdog["MDI"]), "MDIVoltageOverThreshold": 0,
                                        "MDIMotorOverTemp": int(self.motor_ot), "MDIRTDFault": int(self.rtd_bad >= 5),
                                        "MDIRTDCommError": 0}),
                    ("MDIMotorTemperature", {"RTDReadSuccess": int(st.rtd_ok),
                                             "MotorTemperature": round(n(self.motor_temp, 0.2)) if st.rtd_ok else 0,
                                             "RTDFaultFlags": 0 if st.rtd_ok else RTD_FLAGS[st.rtd_flags]})]
        # ---- DRD
        if st.link["DRD"]:
            ds = DRIVE_STATES[st.drive_state]
            moving = st.drive_state in ("FORWARD", "REVERSE", "CRUISE")
            thr = 0 if (st.brake or not moving) else round(1023 * st.throttle / 100)
            adc1 = round(600 + 2800 * st.throttle / 100 + random.gauss(0, 6))
            adc2 = adc1 + (900 if st.adc_mismatch else round(random.gauss(0, 6)))
            if st.adc_out_of_range:
                adc1 = 4095
            out += [("MotorCommand", {"ThrottleDAC": min(thr, 1023), "RegenDAC": 1023 if (st.brake and st.regen_enabled) else 0,
                                      "Direction": 0 if st.drive_state == "REVERSE" else 1, "EcoModeOn": int(st.eco),
                                      "SpeedUnits": int(st.kph)}),
                    ("DRDDiagnostics", {"RawADC1": max(0, min(4095, adc1)), "RawADC2": max(0, min(4095, adc2)),
                                        "BrakePressed": int(st.brake), "RegenEnabled": int(st.regen_enabled),
                                        "ADCOutOfRange": int(st.adc_out_of_range), "ADCMismatch": int(st.adc_mismatch),
                                        "DRDWatchdogReset": int(st.watchdog["DRD"]), "MotorCommFault": int(st.motor_comm_fault),
                                        "DRDMCUOverTemp": mcu("DRD")[2], "DRDMCUUnderVoltage": mcu("DRD")[3], "DriveState": ds,
                                        **{f"{k}Timeout": int(v) for k, v in st.timeouts.items()},
                                        "SOC": round(st.soc)})]
            if every_s:
                v, c, _, _ = mcu("DRD")
                out += [("DRDMCUHealth", {"DRDMCUSupplyVoltage": v, "DRDMCUTemperature": c}),
                        ("DRDTimeSinceBootup", {"DRDTimeSinceBootUp": int(now - self.boot["DRD"])})]
        # ---- STR
        if st.link["STR"]:
            blink = int(now * 2) % 2   # turn signals blink at 1 Hz
            v, c, ot, uv = mcu("STR")
            out += [("STRDRDControl", {"STRRegenEnabled": int(st.regen_enabled), "STRCruiseEnabled": int(st.drive_state == "CRUISE"),
                                       "STRLCDScreenNextPage": 0, "STRLeftTurnSignalEnabled": int(st.left and blink),
                                       "STRRightTurnSignalEnabled": int(st.right and blink), "STRHornEnabled": int(st.horn),
                                       "STRPushToTalkEnabled": int(st.ptt), "STRCruiseSetVelocity": st.cruise_set,
                                       "STRCruiseIncrement": int(st.cruise_inc), "STRCruiseDecrement": int(st.cruise_dec)}),
                    ("STRMCUHealth", {"STRMCUVoltage": v, "STRMCUTemperature": c}),
                    ("STRFlags", {"STRMCUUnderVoltage": uv, "STRMCUOverTemp": ot})]
            if every_s:
                out.append(("STRTimeSinceBootup", {"STRTimeSinceBootUp": int(now - self.boot["STR"])}))
        return out

    def roundtrip(self, name, signals):
        """Encode with the DBC and decode back like the parser (raw ints for enums)."""
        msg = self.db.get_message_by_name(name)
        data = msg.encode(signals, scaling=True, padding=True, strict=False)
        return msg.senders[0], msg.decode(data, decode_choices=False)

    def run(self, hz=10.0, duration=None):
        t0 = time.time()
        while not self.stop.is_set() and (duration is None or time.time() - t0 < duration):
            start = time.time()
            self.step(1 / hz)
            pts = []
            for name, sigs in self.frames_now():
                sender, vals = self.roundtrip(name, sigs)
                pts.append((sender, name, vals))
            with self.lock:
                self.write(pts)
            self.frames += len(pts)
            self.tick += 1
            time.sleep(max(0.0, 1 / hz - (time.time() - start)))


# ---------------------------------------------------------------------- InfluxDB
def influx_writer(url, token, org, bucket):
    from influxdb_client import InfluxDBClient, Point
    from influxdb_client.client.write_api import SYNCHRONOUS
    w = InfluxDBClient(url=url, token=token, org=org).write_api(write_options=SYNCHRONOUS)

    def write(frames):
        pts = []
        for sender, cls, vals in frames:
            for k, v in vals.items():
                pts.append(Point(sender).tag("car", CAR_NAME).tag("class", cls).field(k, v))
        if pts:
            w.write(bucket=bucket, record=pts)
    return write


HISTORY_START = "2026-10-01T00:00:00Z"   # simulator era; older data (e.g. copied real logs) is kept


def influx_clearer(url, token, org, bucket):
    from datetime import datetime, timezone
    from influxdb_client import InfluxDBClient
    d = InfluxDBClient(url=url, token=token, org=org).delete_api()

    def clear():
        stop = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for m in ("TEL", "MDI", "DRD", "STR"):
            d.delete(HISTORY_START, stop, f'_measurement="{m}"', bucket=bucket, org=org)
    return clear


# ---------------------------------------------------------------------- GUI
def gui(sim: Sim):
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("Cascadia CAN simulator: TEL / MDI / DRD / STR")
    vars_ = []   # (tk var, getter-free setter) for refresh after presets

    def bind(var, setter, getter):
        var.trace_add("write", lambda *_: setter(var.get()))
        vars_.append((var, getter))
        return var

    def slider(parent, label, lo, hi, get, set_, res=1.0):
        f = ttk.Frame(parent); f.pack(fill="x", padx=6, pady=1)
        ttk.Label(f, text=label, width=22).pack(side="left")
        v = bind(tk.DoubleVar(value=get()), set_, get)
        tk.Scale(f, from_=lo, to=hi, resolution=res, orient="horizontal", variable=v, length=260).pack(side="left")

    def check(parent, label, get, set_):
        v = bind(tk.BooleanVar(value=get()), set_, get)
        ttk.Checkbutton(parent, text=label, variable=v).pack(anchor="w", padx=6)

    def choice(parent, label, options, get, set_):
        f = ttk.Frame(parent); f.pack(fill="x", padx=6, pady=1)
        ttk.Label(f, text=label, width=22).pack(side="left")
        v = bind(tk.StringVar(value=get()), set_, get)
        ttk.OptionMenu(f, v, get(), *options).pack(side="left")

    S = lambda: sim.state  # noqa: E731

    top = ttk.Frame(root); top.pack(fill="x", padx=6, pady=4)
    ttk.Label(top, text="Scenario:").pack(side="left")
    sc = tk.StringVar(value="normal")
    desc = ttk.Label(root, text=SCENARIOS["normal"][0], foreground="#555")

    def load(*_):
        apply_scenario(sim, sc.get())
        desc.config(text=SCENARIOS[sc.get()][0])
        for var, getter in vars_:
            var.set(getter())
    ttk.OptionMenu(top, sc, "normal", *SCENARIOS, command=load).pack(side="left")

    def reset_all():
        sim.reset_all()
        sc.set("normal")
        desc.config(text="Reset: normal inputs, fault history cleared")
        for var, getter in vars_:
            var.set(getter())
    ttk.Button(top, text="Reset everything (clear fault history)", command=reset_all).pack(side="left", padx=8)
    desc.pack(anchor="w", padx=8)

    nb = ttk.Notebook(root); nb.pack(fill="both", expand=True, padx=6, pady=6)
    tabs = {b: ttk.Frame(nb) for b in ("DRD", "MDI", "TEL", "STR")}
    for b, f in tabs.items():
        nb.add(f, text=b)
        check(f, f"{b} link up (sending)", lambda b=b: S().link[b], lambda v, b=b: S().link.__setitem__(b, v))
        check(f, f"{b} watchdog reset flag", lambda b=b: S().watchdog[b], lambda v, b=b: S().watchdog.__setitem__(b, v))
        ttk.Button(f, text=f"Reboot {b} (uptime → 0)", command=lambda b=b: sim.reset_board(b)).pack(anchor="w", padx=6, pady=2)
        if b in S().vdd:
            slider(f, "MCU Vdd (mV)", 1800, 3600, lambda b=b: S().vdd[b], lambda v, b=b: S().vdd.__setitem__(b, v), 10)
            slider(f, "MCU temperature (°C)", -20, 140, lambda b=b: S().mcu_temp[b], lambda v, b=b: S().mcu_temp.__setitem__(b, v))

    d = tabs["DRD"]
    choice(d, "Drive state", list(DRIVE_STATES), lambda: S().drive_state, lambda v: setattr(S(), "drive_state", v))
    slider(d, "Throttle pedal (%)", 0, 100, lambda: S().throttle, lambda v: setattr(S(), "throttle", v))
    for lbl, a in [("Brake pressed", "brake"), ("Regen enabled", "regen_enabled"), ("Eco mode", "eco"), ("Units KPH", "kph"),
                   ("Throttle sensors mismatch", "adc_mismatch"), ("Throttle ADC out of range", "adc_out_of_range"),
                   ("Motor comm fault", "motor_comm_fault")]:
        check(d, lbl, lambda a=a: getattr(S(), a), lambda v, a=a: setattr(S(), a, v))
    slider(d, "SOC (%)", 0, 104, lambda: S().soc, lambda v: setattr(S(), "soc", v))
    for k in S().timeouts:
        check(d, f"{k} timeout", lambda k=k: S().timeouts[k], lambda v, k=k: S().timeouts.__setitem__(k, v))

    m = tabs["MDI"]
    slider(m, "Motor heating factor", 0, 10, lambda: S().motor_heat, lambda v: setattr(S(), "motor_heat", v), 0.1)
    ttk.Button(m, text="Set motor temp to 25 °C", command=lambda: setattr(sim, "motor_temp", 25.0)).pack(anchor="w", padx=6)
    ttk.Button(m, text="Set motor temp to 98 °C", command=lambda: setattr(sim, "motor_temp", 98.0)).pack(anchor="w", padx=6)
    check(m, "RTD reads OK", lambda: S().rtd_ok, lambda v: setattr(S(), "rtd_ok", v))
    choice(m, "RTD fault flags (when failing)", list(RTD_FLAGS), lambda: S().rtd_flags, lambda v: setattr(S(), "rtd_flags", v))

    te = tabs["TEL"]
    choice(te, "GPS fix", list(GPS_FIX), lambda: S().gps_fix, lambda v: setattr(S(), "gps_fix", v))
    slider(te, "Satellites used", 0, 30, lambda: S().sats, lambda v: setattr(S(), "sats", int(v)))
    slider(te, "CAN bus load (%)", 0, 100, lambda: S().bus_load, lambda v: setattr(S(), "bus_load", v))
    check(te, "GPS read fail", lambda: S().gps_read_fail, lambda v: setattr(S(), "gps_read_fail", v))
    check(te, "IMU read fail (no IMU frames)", lambda: S().imu_read_fail, lambda v: setattr(S(), "imu_read_fail", v))

    s = tabs["STR"]
    for lbl, a in [("Left turn signal", "left"), ("Right turn signal", "right"), ("Horn", "horn"), ("Push to talk", "ptt"),
                   ("Cruise + (held)", "cruise_inc"), ("Cruise − (held)", "cruise_dec")]:
        check(s, lbl, lambda a=a: getattr(S(), a), lambda v, a=a: setattr(S(), a, v))
    slider(s, "Cruise set speed (km/h)", 0, 150, lambda: S().cruise_set, lambda v: setattr(S(), "cruise_set", int(v)))

    status = ttk.Label(root, text="", font=("Menlo", 11)); status.pack(anchor="w", padx=8, pady=4)

    def refresh():
        status.config(text=f"speed {sim.speed * 3.6:5.1f} km/h   motor {sim.motor_temp:5.1f} °C   "
                           f"SOC {sim.state.soc:5.1f} %   frames {sim.frames}")
        root.after(500, refresh)
    refresh()
    root.protocol("WM_DELETE_WINDOW", lambda: (sim.stop.set(), root.destroy()))
    root.mainloop()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dbc", default=str(ROOT / "dbc" / "cascadia.dbc"))
    ap.add_argument("--url", default="http://localhost:8086")
    ap.add_argument("--bucket", default="CAN_prod")
    ap.add_argument("--scenario", default="normal", choices=list(SCENARIOS))
    ap.add_argument("--headless", action="store_true", help="no window; run the scenario")
    ap.add_argument("--duration", type=float, help="seconds (headless)")
    ap.add_argument("--allow-remote", action="store_true", help="allow writing to a non-localhost InfluxDB")
    ap.add_argument("--list-scenarios", action="store_true")
    ap.add_argument("--tk", action="store_true", help="use the Tk window instead of the browser control panel")
    ap.add_argument("--port", type=int, default=8090, help="browser control panel port (localhost only)")
    a = ap.parse_args()
    if a.list_scenarios:
        for k, (d, _) in SCENARIOS.items():
            print(f"{k:16s} {d}")
        return
    if urlparse(a.url).hostname not in ("localhost", "127.0.0.1", "::1") and not a.allow_remote:
        sys.exit(f"refusing to write simulated data to {a.url}; pass --allow-remote if you really mean it")
    from dotenv import dotenv_values
    env = dotenv_values(ROOT / ".env")
    sim = Sim(a.dbc, influx_writer(a.url, env["INFLUX_TOKEN"], env["INFLUX_ORG"], a.bucket),
              influx_clearer(a.url, env["INFLUX_TOKEN"], env["INFLUX_ORG"], a.bucket))
    apply_scenario(sim, a.scenario)
    sim.scenario = a.scenario
    if a.headless:
        print(f"scenario {a.scenario}: {SCENARIOS[a.scenario][0]} -> {a.url} {a.bucket}")
        sim.run(duration=a.duration)
        print("frames written:", sim.frames)
    elif a.tk:
        threading.Thread(target=sim.run, daemon=True).start()
        gui(sim)
    else:
        import webbrowser
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import web_ui
        httpd = web_ui.serve(sim, sys.modules[__name__], a.port)
        threading.Thread(target=sim.run, daemon=True).start()
        url = f"http://localhost:{a.port}"
        print(f"control panel: {url}   (Ctrl+C to stop)")
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            sim.stop.set()


if __name__ == "__main__":
    main()
