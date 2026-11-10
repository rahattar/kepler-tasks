"""Reference solution for hoist-brake-sizing.

    python3 solve.py [DATA_DIR] [OUT_FILE]

Uses only the documents in DATA_DIR (default /app/data) and the laboratory's `friction` and `engage` commands, and
writes the selection to OUT_FILE (default /app/output/brakes.json).

1. The hoists as they are now: the register, with the maintenance log's changes applied (H05 re-reeved to 2 falls,
   10 t and a 300 kg hook block; H04, H08 and H12 on inverters, which stop the hoist before the brake is applied, with
   light-load fast lowering on H04 and H08). Two-speed hoists make their working stops from the slow speed and their
   emergency stops from full speed. Contactor hoists lower above synchronous speed, at the register's lowering speed;
   an inverter lowers at the set (rated) speed.
2. Eight tests (constant PLAN): each lining at 20 C, its reference temperature, and at the temperatures its hoists
   reach, from a first pass with the catalogue's friction (authoring/evidence/reference_run.txt prints it). O1 at
   60 C (H01, H02, H06) and 160 C (H11); O2 at 160 C (H07), 200 C (H05, whose duty and emergency stops span 185 to
   210 C) and 260 C (H03, H10, at 230 to 270 C). One engagement test on H05's brake near its candidate settings with
   AC-side switching: H05 is the hoist whose travel decides its setting, and the catalogue gives engagement times only
   at 100 %. A brake is selected only where its linings stay within 15 C of the tested temperatures (REACH): the
   tests say nothing about the friction beyond them.
3. Friction: the ratio of each test's mean to its lining's mean at 20 C, linear between the tested temperatures and
   held at the end values beyond them. Torque = rated torque x setting x ratio. Engagement: the catalogue's time at
   100 % x (100 / setting)^p, with p from the test (p for DC switching is taken equal to AC's, which is conservative:
   no DC hoist's selection turns on it).
4. The requirements (MS-14) on a lumped brake (heat capacity, heat dissipation to the bay air):
   - working duty: alternating hoisting and lowering stops at the survey's rate and mean load, each with its
     engagement delay (the load decelerates hoisting, accelerates lowering, before the brake acts); the lining
     temperature is the periodic steady state's peak (inverter hoists: no working stops on the brake);
   - holding: torque at that temperature >= 1.6 x the static torque of the rated load and hook block, no efficiency;
   - travel: emergency stop lowering, from the duty temperature, at every permitted load and speed, free acceleration
     through the engagement delay, then the brake, with the disc heating through the stop; the gear is driven
     backwards by the load, at efficiency 2 - 1/eta;
   - deceleration and gearbox: the highest torque over the temperatures reached (bay air to the end of an emergency
     stop); the worst deceleration is hoisting the rated load, gravity through the gear (1/eta) adding to the brake;
   - lining temperature below 300 C at the duty peak and at the end of every emergency stop.
5. For each hoist the size and setting with the largest smallest margin (the middle of the widest window).
"""
import csv
import json
import os
import re
import subprocess
import sys

import numpy as np

G = 9.81
TLIM = 300.0
HOLD = 1.6
SETTINGS = np.arange(50, 101, dtype=float)
PLAN = [("friction", "20", "O1"), ("friction", "60", "O1"), ("friction", "160", "O1"),
        ("friction", "20", "O2"), ("friction", "160", "O2"), ("friction", "200", "O2"), ("friction", "260", "O2"),
        ("engage", "S16", "65", "AC")]
REACH = 15.0     # a brake is selected only if its linings stay within 15 C of the tested temperatures
DT = 4e-4        # s, time step of the emergency-stop integration


def rows(data, name):
    with open(os.path.join(data, name), newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- the hoists as they are now
def hoists(data):
    wiring = {r["hoist"]: r for r in rows(data, "brake_wiring.csv")}
    duty = {r["hoist"]: r for r in rows(data, "duty_survey.csv")}
    H = {}
    for r in rows(data, "hoist_register.csv"):
        hid = r["hoist"]
        h = dict(load=float(r["rated_load_t"]) * 1000, hook=float(r["hook_block_kg"]), falls=float(r["falls"]),
                 D=float(r["drum_pitch_diameter_mm"]) / 1000, ratio=float(r["gearbox_ratio"]),
                 eta=float(r["gearbox_efficiency"]), glim=float(r["gearbox_peak_input_torque_Nm"]),
                 n=float(r["motor_rpm"]), J0=float(r["motor_rotor_inertia_kgm2"]) + float(r["gearbox_inertia_at_input_kgm2"]),
                 Tamb=float(r["bay_air_temperature_C"]), slim=float(r["emergency_stop_travel_limit_mm"]) / 1000,
                 amax=float(r["emergency_stop_deceleration_limit_m_per_s2"]), inverter=False, fast=None, slow=1.0)
        k_reg = h["D"] / (2 * h["falls"] * h["ratio"])
        h["w_low"] = float(r["lowering_speed_rated_load_m_per_min"]) / 60 / k_reg   # above synchronous (contactor)
        m = re.search(r"\((\d+)/(\d+) pole\)", r["control"])
        if m:                       # pole-changing: working stops from the slow speed
            h["slow"] = int(m.group(1)) / int(m.group(2))
        h["sw"] = "AC" if wiring[hid]["brake_switching"].startswith("AC") else "DC"
        d = duty[hid]
        h["stops"] = (float(d["brake_applications_hoisting"]) + float(d["brake_applications_lowering"])) / float(d["operating_hours"])
        h["lf"] = float(d["mean_load_percent_of_rated"]) / 100
        H[hid] = h
    for e in rows(data, "maintenance_log.csv"):
        h, t = H[e["hoist"]], e["entry"]
        m = re.search(r"Re-reeved from (\d+) falls to (\d+) falls", t)
        if m:
            h["falls"] = float(m.group(2))
        m = re.search(r"Rated load reduced to ([\d.]+) t", t)
        if m:
            h["load"] = float(m.group(1)) * 1000
        m = re.search(r"hook block \((\d+) kg\)", t)
        if m:
            h["hook"] = float(m.group(1))
        if "frequency inverter" in t:
            h["inverter"] = True
            h["w_low"] = 2 * np.pi * h["n"] / 60      # speed-controlled: lowers at the set speed
        m = re.search(r"up to (\d+) % of rated speed for loads up to (\d+) % of rated load", t)
        if m:
            h["fast"] = (int(m.group(1)) / 100, int(m.group(2)) / 100)
    for h in H.values():
        h["k"] = h["D"] / (2 * h["falls"] * h["ratio"])     # m of hook travel per rad of motor
        h["w0"] = 2 * np.pi * h["n"] / 60
    return H


def catalogue(data):
    C = {}
    for r in rows(data, "brake_catalogue.csv"):
        C[r["size"]] = dict(Mr=float(r["rated_torque_Nm"]), lining=r["friction_lining"], Jb=float(r["rotor_inertia_kgm2"]),
                            C=float(r["heat_capacity_J_per_K"]), H=float(r["heat_dissipation_W_per_K"]),
                            t={"DC": float(r["engagement_time_DC_switching_ms"]) / 1000,
                               "AC": float(r["engagement_time_AC_switching_ms"]) / 1000})
    return C


# ---------------------------------------------------------------- laboratory
def report_name(test):
    if test[0] == "friction":
        return r"^test_\d{2}_friction_%s_T%03d\.csv$" % (test[2], int(test[1]))
    return r"^test_\d{2}_engage_%s_%s_%s\.csv$" % test[1:]


def parse(text):
    return [float(line.split(",")[1]) for line in text.splitlines() if re.match(r"^\d+,", line)]


def run_tests(reports):
    """each planned test's readings: from its report if it was already run, otherwise by running it"""
    out = []
    for test in PLAN:
        have = sorted(f for f in (os.listdir(reports) if os.path.isdir(reports) else []) if re.match(report_name(test), f))
        if have:
            with open(os.path.join(reports, have[0])) as f:
                text = f.read()
        else:
            cmd = [os.path.join(os.environ["LAB_BIN"], test[0]) if os.environ.get("LAB_BIN") else test[0]] + list(test[1:])
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.dirname(reports.rstrip("/")) or ".")
            text = res.stdout
            if res.returncode != 0 or not parse(text):
                raise SystemExit("laboratory test %s failed: %s" % (" ".join(test), text.strip()))
        out.append((test, parse(text)))
    return out


class Model:
    def __init__(self, tests, cat):
        self.cat = cat
        pts = {}
        p = {}
        for test, vals in tests:
            if test[0] == "friction":
                pts.setdefault(test[2], []).append((float(test[1]), float(np.mean(vals))))
            else:
                size, st, sw = test[1], float(test[2]), test[3]
                p[sw] = np.log(np.mean(vals) / 1000 / cat[size]["t"][sw]) / np.log(100.0 / st)
        self.curve = {}
        for lin, pl in pts.items():
            pl.sort()
            ref = dict(pl)[20.0]
            self.curve[lin] = (np.array([t for t, _ in pl]), np.array([m / ref for _, m in pl]))
        self.p = {"AC": p.get("AC", p.get("DC")), "DC": p.get("DC", p.get("AC"))}

    def ratio(self, T, lining):
        x, y = self.curve[lining]
        return np.interp(T, x, y)

    def top(self, lining):
        return float(self.curve[lining][0][-1])

    def engage(self, size, st, sw):
        return self.cat[size]["t"][sw] * (100.0 / st) ** self.p[sw]


# ---------------------------------------------------------------- MS-14
def static(h, m):
    return (m + h["hook"]) * G * h["k"]


def inertia(h, m, b):
    return h["J0"] + b["Jb"] + (m + h["hook"]) * h["k"] ** 2


def margins(M, h, size, st=SETTINGS):
    b = M.cat[size]
    lin = b["lining"]
    st = np.asarray(st, float)

    def torque(T):
        return st / 100 * b["Mr"] * M.ratio(T, lin)

    eb = 2 - 1 / h["eta"]                       # gear driven backwards by the lowering load
    te = M.engage(size, st, h["sw"])
    # working duty: periodic steady state of alternating hoisting and lowering stops
    Tp = np.full_like(st, h["Tamb"])
    if not h["inverter"]:
        m = h["lf"] * h["load"]
        J = inertia(h, m, b)
        Lh, Ll = static(h, m) / h["eta"], static(h, m) * eb
        wh = np.maximum(h["w0"] * h["slow"] - Lh / J * te, 0.0)
        wl = h["w_low"] * h["slow"] + Ll / J * te
        a = np.exp(-3600.0 / h["stops"] * b["H"] / b["C"])
        T = Tp.copy()
        for _ in range(100):
            tb = torque(T)
            runaway = tb <= Ll
            eh = tb * J * wh ** 2 / (2 * (tb + Lh))
            el = tb * J * wl ** 2 / (2 * np.maximum(tb - Ll, 1e-9))
            peak = np.maximum(eh + a * el, el + a * eh) / (b["C"] * (1 - a * a))
            T = 0.5 * T + 0.5 * np.where(runaway, 5000.0, np.minimum(h["Tamb"] + peak, 5000.0))
        Tp = T
    hold = torque(Tp) / (HOLD * static(h, h["load"])) - 1
    # emergency stop lowering, from the duty temperature
    cases = [(h["load"], h["w_low"])]
    if h["fast"]:
        cases.append((h["fast"][1] * h["load"], h["fast"][0] * h["w0"]))
    travel = np.full_like(st, np.inf)
    Tend = Tp.copy()
    for m, w in cases:
        J = inertia(h, m, b)
        L = static(h, m) * eb
        w1 = w + L / J * te
        ang = w * te + 0.5 * L / J * te ** 2
        T = Tp.copy()
        live = np.ones_like(st, bool)
        for _ in range(60000):
            tb = torque(T)
            acc = (L - tb) / J
            stuck = live & ((acc >= 0) | (T > 1500))
            ang[stuck] = np.inf
            live &= ~stuck
            if not live.any():
                break
            dt = np.where(live, np.minimum(DT, w1 / np.maximum(-acc, 1e-9)), 0.0)
            ang += np.where(live, (w1 + 0.5 * acc * dt) * dt, 0.0)
            T = T + np.where(live, tb * w1 * dt / b["C"], 0.0)
            w1 = w1 + np.where(live, acc * dt, 0.0)
            live &= w1 > 1e-9
        travel = np.minimum(travel, h["slim"] / (h["k"] * ang) - 1)
        Tend = np.maximum(Tend, T)
    temp = TLIM / np.maximum(Tp, Tend) - 1
    hi = np.minimum(np.maximum(Tp, Tend), 1500)
    Ts = h["Tamb"] + np.linspace(0, 1, 120)[:, None] * (hi - h["Tamb"])[None, :]
    tmax = np.max(torque(Ts), axis=0)
    gearbox = h["glim"] / tmax - 1
    J = inertia(h, h["load"], b)
    decel = h["amax"] / ((tmax + static(h, h["load"]) / h["eta"]) * h["k"] / J) - 1
    return dict(hold=hold, travel=travel, decel=decel, temp=temp, gearbox=gearbox, Tp=Tp, Tend=Tend)


REQ = ("hold", "travel", "decel", "temp", "gearbox")


def select(M, H, sizes=None, reach=REACH):
    picks = {}
    for hid, h in H.items():
        best = None
        for size in (sizes or M.cat):
            r = margins(M, h, size)
            worst = np.min([r[k] for k in REQ], axis=0)
            if reach is not None:
                worst = np.where(np.maximum(r["Tp"], r["Tend"]) <= M.top(M.cat[size]["lining"]) + reach, worst, -np.inf)
            i = int(np.argmax(worst))
            if best is None or worst[i] > best[0]:
                best = (float(worst[i]), size, int(SETTINGS[i]), {k: float(r[k][i]) for k in r})
        picks[hid] = best
    return picks


def first_pass(H, cat):
    """the plan's basis: catalogue friction (ratio 1) and catalogue engagement times"""
    M = Model([(("friction", "20", lin), [1.0]) for lin in ("O1", "O2")] + [(("friction", "300", lin), [1.0]) for lin in ("O1", "O2")], cat)
    M.p = {"AC": 0.0, "DC": 0.0}
    return select(M, H, reach=None)


def main(data="/app/data", out="/app/output/brakes.json"):
    H = hoists(data)
    cat = catalogue(data)
    if os.environ.get("SHOW_FIRST_PASS"):
        for hid, (w, size, s, r) in first_pass(H, cat).items():
            print("first pass %s %s/%d (%s): duty %.0f C, emergency stop to %.0f C" % (hid, size, s, cat[size]["lining"], r["Tp"], r["Tend"]))
    reports = os.environ.get("REPORT_DIR", "/app/lab_reports")
    M = Model(run_tests(reports), cat)
    for lin, (x, y) in M.curve.items():
        print("friction ratio to 20 C, %s: %s" % (lin, ", ".join("%g C %.3f" % (t, v) for t, v in zip(x, y))))
    print("engagement time = catalogue time x (100 / setting)^p, p = %.3f (AC test; DC taken the same)" % M.p["AC"])
    picks = select(M, H)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        json.dump({"brakes": {hid: {"size": p[1], "setting": p[2]} for hid, p in picks.items()}}, f, indent=1)
    for hid, (w, size, s, r) in picks.items():
        print("%s %s %3d  worst margin %+.3f  duty %.0f C, e-stop %.0f C  %s" % (
            hid, size, s, w, r["Tp"], r["Tend"], " ".join("%s %+.3f" % (k, r[k]) for k in REQ)))
    return picks


if __name__ == "__main__":
    main(*(sys.argv[1:3]))
