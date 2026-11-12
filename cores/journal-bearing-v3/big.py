"""Two long packages for v3: hourly operating records. usage: big.py NAME   (writes core/hidden/NAME)"""
import csv, datetime, json, math, os, random, sys
import numpy as np
import ref_bearing as rb

rb.GRIDS = ((240, 24), (240, 24))          # the truth grid
SPEC = {
 "pipeline_L-7": dict(seed=71, days=1280, start="2024-06-03", sheet=dict(tag="L-7", machine="pipeline", position="DE",
     journal_diameter_mm=180.0, length_mm=150.0, radial_clearance_um=110, groove_angles_deg=[90, 270],
     oil_grade="ISO VG 46", oil_flow_L_min=14.0),
     history=[(400, "DE", "SHELL_FITTED", "0.24", "new shell fitted, lead wire check"),
              (401, "NDE", "SHELL_FITTED", "0.22", "new shell fitted"),
              (800, "-", "OIL_CHANGED", "68", "charge renewed, grade raised")],
     samples=[(300, "45.1", "6.7", "869", "routine"), (900, "66.4", "8.6", "874", "routine")],
     speed=(1300, 3300), sload=(0.6, 2.2), beta=(0, 0), inlet=(38, 52),
     fault=("bias", "a", 4.8, 1000, 1080), flag="b"),
 "fan_ID-2": dict(seed=72, days=1280, start="2024-09-02", sheet=dict(tag="ID-2", machine="fan", position="NDE",
     journal_diameter_mm=220.0, length_mm=200.0, radial_clearance_um=150, groove_angles_deg=[90, 270],
     oil_grade="ISO VG 68", oil_flow_L_min=11.0),
     history=[(600, "NDE", "JOURNAL_GROUND", "219.94", "journal scored, ground and polished"),
              (601, "DE", "SHELL_FITTED", "0.31", "new shell fitted"),
              (200, "NDE", "ORIFICE_CHANGED", "13", "supply orifice bored out")],
     samples=[],
     speed=(620, 990), sload=(0.8, 2.0), beta=(-15, 15), inlet=(40, 54),
     fault=("stuck", "b", 58.4, 900, 960), flag="a"),
}

def main(name):
    sp = SPEC[name]; rng = random.Random(sp["seed"]); sheet = sp["sheet"]
    d0 = datetime.date.fromisoformat(sp["start"])
    off = {h[0] for h in sp["history"]} | {s[0] for s in sp["samples"]}
    history = [((d0 + datetime.timedelta(days=h[0])).isoformat(),) + h[1:] for h in sp["history"]]
    for k in range(5):
        dd = rng.randrange(5, sp["days"] - 5); off.add(dd)
        history.append(((d0 + datetime.timedelta(days=dd)).isoformat(), rng.choice(["DE", "NDE"]), "INSPECTED", "", "bearing inspected, no findings"))
    history.sort()
    samples = [((d0 + datetime.timedelta(days=s[0])).isoformat(),) + s[1:] for s in sp["samples"]]
    hist_rows = [dict(zip(["date", "position", "work", "value", "remarks"], h)) for h in history]
    samp_rows = [dict(zip(["date", "nu40_cSt", "nu100_cSt", "rho15_kg_m3", "remarks"], s)) for s in samples]
    D, L = sheet["journal_diameter_mm"], sheet["length_mm"]
    rows, truth = [], []
    x = [0.5, 0.5, 0.5]                       # slow random walks for speed, load, load angle
    brgs = {}; guess = None; last_state = None
    n = 0
    for day in range(sp["days"]):
        if day in off:
            continue
        date = (d0 + datetime.timedelta(days=day)).isoformat()
        season = 0.5 + 0.5 * math.sin(2 * math.pi * (day - 40) / 365.0)
        for hour in range(24):
            x = [min(1.0, max(0.0, v + rng.gauss(0, 0.035))) for v in x]
            rpm = round((sp["speed"][0] + x[0] * (sp["speed"][1] - sp["speed"][0])) / 10) * 10
            sl = sp["sload"][0] + (0.6 * x[1] + 0.4 * x[0] ** 2) * (sp["sload"][1] - sp["sload"][0])
            load = round(sl * 1e6 * D * L / 1e6 / 100) * 100
            beta = round(sp["beta"][0] + x[2] * (sp["beta"][1] - sp["beta"][0]))
            t = round(sp["inlet"][0] + (0.75 * season + 0.25 * (0.5 + 0.5 * math.sin(2 * math.pi * (hour - 9) / 24))) * (sp["inlet"][1] - sp["inlet"][0]) + rng.gauss(0, 0.3), 1)
            state = rb.state_at(sheet, hist_rows, samp_rows, date)
            if state not in brgs:
                brgs[state] = rb.Bearing(state)
            b = brgs[state]
            if state != last_state: guess = None
            last_state = state
            w = rpm * 2 * math.pi / 60.0; thL = math.pi + math.radians(beta)
            b.lands = b.grids[0]
            xs, aux = b.solve_regime(w, load, thL, t, False, guess if guess is not None else (0.0, 0.9, t + 8.0))
            eps, psi, T, power, pmax, Rec = aux
            res = abs(b.residual(xs, w, load, thL, t, False)[0]).max()
            if not (res < 1e-7 and Rec < 0.7 * b.Ret and 0.04 < eps < 0.95):
                guess = None
                continue
            guess = xs
            n += 1
            pt = "%s-%05d" % (sheet["tag"], n)
            dlt = rng.choice([-0.1, 0.0, 0.1]); va, vb = t + dlt, t - dlt
            what, which, val, f0, f1 = sp["fault"]; faulty = f0 <= day < f1
            if faulty:
                if what == "stuck": va, vb = (val, vb) if which == "a" else (va, val)
                else: va, vb = (va + val, vb) if which == "a" else (va, vb + val)
            a_txt, b_txt = "%.1f" % va, "%.1f" % vb
            drain = "%.1f" % (2 * T - t + rng.choice([-0.2, -0.1, 0.0, 0.1, 0.2]))
            if not faulty and rng.random() < 0.03:
                if sp["flag"] == "a": a_txt, b_txt = "-999", "%.1f" % t
                else: a_txt, b_txt = "%.1f" % t, "-999"
            elif not faulty and rng.random() < 0.02:
                drain = "-999"
            rows.append(dict(point=pt, date=date, speed_rpm=rpm, load_N=load, load_angle_deg=beta, inlet_a_C=a_txt, inlet_b_C=b_txt, drain_C=drain))
            truth.append([pt, "%.3f" % (b.c * (1 - eps) * 1e6), "%.2f" % math.degrees(psi - thL), "%.4f" % (power / 1e3), "%.2f" % T, "%.4f" % (pmax / 1e6)])
        if day % 160 == 0: print(name, day, n, flush=True)
    d = os.path.join("core/hidden", name); os.makedirs(d, exist_ok=True)
    json.dump(sheet, open(d + "/datasheet.json", "w"), indent=1)
    with open(d + "/history.csv", "w", newline="") as f:
        w_ = csv.writer(f); w_.writerow(["date", "position", "work", "value", "remarks"]); w_.writerows(history)
    with open(d + "/oil_samples.csv", "w", newline="") as f:
        w_ = csv.writer(f); w_.writerow(["date", "nu40_cSt", "nu100_cSt", "rho15_kg_m3", "remarks"]); w_.writerows(samples)
    with open(d + "/points.csv", "w", newline="") as f:
        w_ = csv.DictWriter(f, list(rows[0])); w_.writeheader(); w_.writerows(rows)
    with open(d + "/truth.csv", "w", newline="") as f:
        w_ = csv.writer(f); w_.writerow(["point", "h_min_um", "attitude_deg", "power_kW", "t_eff_C", "p_max_MPa"]); w_.writerows(truth)
    print(name, "done", n, flush=True)

if __name__ == "__main__":
    main(sys.argv[1])
