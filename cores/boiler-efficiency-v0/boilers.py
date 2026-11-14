"""Boiler packages for the BE-3 core, and their results.

    python3 boilers.py OUT_ROOT

writes OUT_ROOT/environment/data/{examples,pending}/<boiler>, OUT_ROOT/tests/boilers/<boiler>,
OUT_ROOT/tests/sealed/results/<boiler>.csv, OUT_ROOT/environment/data/examples/<boiler>/expected.csv,
OUT_ROOT/authoring/provenance/pending_results/<boiler>.csv and OUT_ROOT/authoring/provenance/conditions.json.

What a boiler is, hour by hour (the truth): a load, the excess air and CO the burners ran at, the delivery
being fired, the air heater's leakage, the gas temperature without leakage, the air entering and its humidity.
The flue gas follows from these by BE-3's own stoichiometry, and the results are BE-3 applied to them.
What the package records is that state read by the plant's instruments and logs. Two things can come between:
  - drift: the CO2 analyser's zero drifts away from an onset, linearly up to a cap (an additive offset);
  - mislabel: a bunker log entry names a delivery other than the one fired from that entry on.
Everything else is read within the accuracies BE-3 states.
"""
import csv
import json
import math
import os
import sys

import numpy as np

YEAR = 2025
HOURS = 8760
FLY = 0.8
MINES = {   # as-fired C, H, O, N, S, ash, moisture (mass fractions)
    "A": [0.655, 0.050, 0.068, 0.014, 0.013, 0.100, 0.100],   # high-volatile bituminous
    "B": [0.640, 0.041, 0.065, 0.013, 0.006, 0.140, 0.095],   # export bituminous
    "C": [0.495, 0.035, 0.128, 0.007, 0.004, 0.056, 0.275],   # sub-bituminous
    "D": [0.350, 0.024, 0.112, 0.006, 0.007, 0.071, 0.430],   # lignite
    "E": [0.770, 0.036, 0.028, 0.012, 0.009, 0.100, 0.045],   # low-volatile bituminous
}
LOI_BASE = {"A": 0.045, "B": 0.040, "C": 0.015, "D": 0.010, "E": 0.065}
EA_EXTRA = {"A": 0.0, "B": 0.0, "C": 0.01, "D": 0.04, "E": 0.02}

# name, place, seed, rated MW, mines, conditions
BOILERS = [
    ("kestrel_1", "examples", 101, 410.0, "AC", {}),
    ("kestrel_2", "examples", 102, 365.0, "AE", {}),
    ("harrow_3", "pending", 103, 520.0, "AC", {"drift": dict(onset_day=150, rate=0.016, cap=1.6)}),
    ("harrow_4", "pending", 104, 480.0, "AC", {"mislabel": [dict(kind="lag", day=60, fills=4)]}),
    ("b01", "hidden", 201, 450.0, "AE", {"drift": dict(onset_day=95, rate=-0.014, cap=1.4)}),
    ("b02", "hidden", 202, 395.0, "AC", {"mislabel": [dict(kind="phantom", day=50, fills=3), dict(kind="lag", day=190, fills=5)]}),
    ("b03", "hidden", 203, 610.0, "AC", {"drift": dict(onset_day=170, rate=0.02, cap=1.8),
                                         "mislabel": [dict(kind="lag", day=205, fills=4)]}),
    ("b04", "hidden", 204, 330.0, "AE", {"drift": dict(onset_day=230, rate=0.012, cap=1.2),
                                         "mislabel": [dict(kind="phantom", day=60, fills=4)]}),
    ("b05", "hidden", 205, 500.0, "AC", {}),
    ("b06", "hidden", 206, 280.0, "BD", {"mislabel": [dict(kind="lag", day=100, fills=4)]}),
]


def hhv_of(a):
    C, H, O, N, S, A, M = [100.0 * v for v in a]
    return 349.1 * C + 1178.3 * H + 100.5 * S - 103.4 * O - 15.1 * N - 21.1 * A


def gas(a, u, EA, x):
    """Dry flue gas per kg fuel for analysis a, unburnt carbon u (kg/kg), excess air EA, CO share x of burnt C."""
    C, H, O, N, S, A, M = a
    nC = (C - u) / 12.011
    nH2, nS, nO2f, nN2f = H / 2.016, S / 32.06, O / 31.998, N / 28.013
    nth = nC + nH2 / 2 + nS - nO2f
    co2, co, so2 = nC * (1 - x), nC * x, nS + 0 * EA
    o2 = EA * nth + nC * x / 2
    n2 = 3.773 * (1 + EA) * nth + nN2f
    D = co2 + co + so2 + o2 + n2
    mass = 44.010 * co2 + 28.010 * co + 64.060 * so2 + 31.998 * o2 + 28.013 * n2
    return dict(co2=100 * co2 / D, o2=100 * o2 / D, co_ppm=1e6 * co / D, m_dg=mass, m_co=28.010 * co,
                m_air=137.69 * (1 + EA) * nth)


def be3_hour(a, hhv, loi_f, loi_b, EA, x, t_corr, t_ref, omega, load, rad):
    """BE-3 efficiency (per cent, HHV) of one hour, from the state itself."""
    C, H, O, N, S, A, M = a
    u = A * (FLY * loi_f / (1 - loi_f) + (1 - FLY) * loi_b / (1 - loi_b))
    g = gas(a, u, EA, x)
    dT = t_corr - t_ref
    L = g["m_dg"] * 1.02 * dT
    L = L + (9 * H + M) * (2501.0 + 1.88 * t_corr - 4.19 * t_ref)
    L = L + g["m_air"] * omega * 1.88 * dT
    L = L + u * 33700.0 + g["m_co"] * 10110.0
    L = L + FLY * A / (1 - loi_f) * 0.84 * dT + (1 - FLY) * A / (1 - loi_b) * 0.84 * (800.0 - t_ref)
    return 100.0 - 100.0 * L / hhv - np.interp(load, rad[:, 0], rad[:, 1])


def ar1(rng, n, phi, sd):
    e = rng.normal(0, sd * math.sqrt(1 - phi * phi), n)
    out = np.empty(n)
    out[0] = rng.normal(0, sd)
    for i in range(1, n):
        out[i] = phi * out[i - 1] + e[i]
    return out


def build(name, seed, rated, mines, cond):
    rng = np.random.default_rng(seed)
    h = np.arange(HOURS)
    day = h // 24
    hod = h % 24
    doy = day.astype(float)
    # outage: a block of days with no records
    o0 = int(rng.integers(40, 300))
    olen = int(rng.integers(4, 10))
    run = ~((day >= o0) & (day < o0 + olen))
    # deliveries: each mine delivers every 45 to 75 days, the first before the year opens
    deliveries = []
    for m in mines:
        t = -int(rng.integers(5, 30))
        while t < 365:
            a = np.array(MINES[m], float)
            # a contract coal: a mine's deliveries differ by little more than the laboratory's repeatability
            a[1] *= 1 + rng.normal(0, 0.002)
            a[2] *= 1 + rng.normal(0, 0.002)
            a[5] += rng.normal(0, 0.0008)
            a[6] += rng.normal(0, 0.0008)
            a[0] += 1.0 - a.sum()
            hhv = hhv_of(a) * (1 + rng.normal(0, 0.0003))
            deliveries.append(dict(mine=m, received=t, a=a, hhv=round(hhv)))
            t += int(rng.integers(45, 76))
    deliveries.sort(key=lambda d: d["received"])
    for i, d in enumerate(deliveries):
        d["id"] = "%s-%02d" % (name[0].upper() + name[-1], i + 1)
        d["a"] = np.round(d["a"], 4)
        d["a"][0] = round(1.0 - d["a"][1:].sum(), 4)

    def latest(m, hour):
        best = None
        for i, d in enumerate(deliveries):
            if d["mine"] == m and d["received"] * 24 <= hour - 24:
                best = i
        return best

    # campaigns of 4 to 12 days on one mine; within a campaign the bunkers are filled every 8 to 30 hours,
    # and the burners fire the latest filling from the hour of its entry
    entries, camp = [], []
    t, k, c = 0, int(rng.integers(0, len(mines))), 0
    while t < HOURS:
        m = mines[k % len(mines)]
        end = t + int(rng.integers(4 * 24, 12 * 24))
        while t < min(end, HOURS):
            entries.append([t, latest(m, max(t, 24)), latest(m, max(t, 24))])   # hour, fired, logged
            camp.append(c)
            t += int(rng.integers(8, 31))
        k += 1 if len(mines) == 2 else int(rng.integers(1, len(mines)))
        c += 1
    # mislabels touch only the log: n fillings logged as a delivery of another mine
    #   lag: the first n fillings of the first campaign to open after `day` are logged as the previous campaign's
    #   phantom: n fillings from the middle of the first campaign to open after `day` are logged as the other mine's
    labels = []
    for ml in cond.get("mislabel", []):
        first = min(i for i, e in enumerate(entries) if e[0] >= ml["day"] * 24 and camp[i] != camp[i - 1])
        if ml["kind"] == "phantom":
            first += max(1, sum(1 for i in range(len(entries)) if camp[i] == camp[first]) // 3)
        for j in range(first, first + ml["fills"]):
            fired_mine = deliveries[entries[j][1]]["mine"]
            if ml["kind"] == "lag":
                entries[j][2] = entries[first - 1][2]
            else:
                entries[j][2] = latest([m for m in mines if m != fired_mine][0], entries[j][0])
            if deliveries[entries[j][2]]["mine"] == fired_mine:
                raise SystemExit("%s: filling %d is not mislabelled" % (name, j))
        labels.append(dict(kind=ml["kind"], first=first, fills=ml["fills"], hour=entries[first][0],
                           hours=entries[first + ml["fills"]][0] - entries[first][0],
                           fired=deliveries[entries[first][1]]["id"], logged=deliveries[entries[first][2]]["id"]))
    starts = np.array([e[0] for e in entries])
    seg = np.searchsorted(starts, h, side="right") - 1
    fired = np.array([entries[s][1] for s in seg])
    mine_h = np.array([deliveries[i]["mine"] for i in fired])

    # load and firing state
    week = np.where((day + 2) % 7 >= 5, -0.10, 0.0)
    load = 0.74 + 0.16 * np.sin(2 * np.pi * (hod - 9) / 24) + week + ar1(rng, HOURS, 0.97, 0.07)
    load = np.clip(load, 0.38, 1.0)
    extra = np.array([EA_EXTRA[m] for m in mine_h])
    EA = 0.17 + 0.24 * (1 - load) + extra + ar1(rng, HOURS, 0.9, 0.02)
    EA = np.clip(EA, 0.10, 0.60)
    co_target = 25 + 70 * (1 - load) + np.abs(rng.normal(0, 12, HOURS))
    x = co_target / (1e4 * 14.0)
    t_air = 13 + 10 * np.sin(2 * np.pi * (doy - 110) / 365) + 4 * np.sin(2 * np.pi * (hod - 9) / 24) + ar1(rng, HOURS, 0.95, 1.5) + 3.0
    omega = np.clip(0.0065 + 0.004 * np.sin(2 * np.pi * (doy - 120) / 365) + ar1(rng, HOURS, 0.97, 0.0012), 0.0015, 0.02)
    L0 = rng.uniform(0.06, 0.10)
    Lm = L0 * (1 + 0.3 * (1 - load)) * (1 + 0.15 * np.sin(2 * np.pi * doy / rng.uniform(60, 120))) + ar1(rng, HOURS, 0.8, 0.003)
    soot = (h % 8) / 8.0 * rng.uniform(3, 7)
    t_corr = 116 + 32 * load + 0.45 * (t_air - 15) + soot + rng.uniform(0, 8) + ar1(rng, HOURS, 0.9, 1.0)

    # daily fly ash LOI, from the mine fired most that day
    loi_b = round(float(rng.uniform(0.02, 0.08)), 3)
    loi_day = np.zeros(365)
    for dd in range(365):
        ms = mine_h[dd * 24:(dd + 1) * 24]
        m = max(set(ms), key=list(ms).count)
        loi_day[dd] = np.clip(LOI_BASE[m] + 0.02 * (1 - load[dd * 24:(dd + 1) * 24].mean()) + rng.normal(0, 0.004), 0.004, 0.12)
    loi_day = np.round(loi_day, 4)
    loi_f = loi_day[day]

    # the true gas, hour by hour
    a_h = np.array([deliveries[i]["a"] for i in fired]).T
    hhv_h = np.array([deliveries[i]["hhv"] for i in fired], float)
    C, H, O, N, S, A, M = a_h
    u = A * (FLY * loi_f / (1 - loi_f) + (1 - FLY) * loi_b / (1 - loi_b))
    g = gas(a_h, u, EA, x)
    o2_out = (Lm * 20.95 / 0.9 + g["o2"]) / (1 + Lm / 0.9)
    k = Lm * 1.005 / 1.05
    t_out = (t_corr + k * t_air) / (1 + k)
    rad = np.array([[0.3, round(rng.uniform(0.70, 0.85), 2)], [0.5, round(rng.uniform(0.45, 0.55), 2)],
                    [0.75, round(rng.uniform(0.32, 0.38), 2)], [1.0, round(rng.uniform(0.24, 0.29), 2)]])
    eta = be3_hour(a_h, hhv_h, loi_f, loi_b, EA, x, t_corr, t_air, omega, load, rad)

    # the instruments
    drift = np.zeros(HOURS)
    if "drift" in cond:
        dr = cond["drift"]
        drift = np.sign(dr["rate"]) * np.clip((h / 24.0 - dr["onset_day"]) * abs(dr["rate"]), 0, dr["cap"])
    co2_m = g["co2"] + rng.normal(0, 0.03) + drift + rng.normal(0, 0.04, HOURS)
    o2a = g["o2"] + rng.normal(0, 0.015) + rng.normal(0, 0.03, HOURS)
    o2b = g["o2"] + rng.normal(0, 0.015) + rng.normal(0, 0.03, HOURS)
    o2o = o2_out + rng.normal(0, 0.015) + rng.normal(0, 0.03, HOURS)
    co_m = np.maximum(g["co_ppm"] + rng.normal(0, 4, HOURS), 0)
    Q = load * rated
    rows = []
    for i in np.nonzero(run)[0]:
        stamp = np.datetime64("%d-01-01T00:00" % YEAR) + np.timedelta64(int(i), "h")
        rows.append([str(stamp).replace("T", " "), "%.2f" % Q[i], "%.2f" % co2_m[i], "%.2f" % o2a[i], "%.2f" % o2b[i],
                     "%.2f" % o2o[i], "%d" % round(co_m[i]), "%.1f" % (t_out[i] + rng.normal(0, 0.4)),
                     "%.1f" % (t_air[i] + rng.normal(0, 0.3)), "%.5f" % (omega[i] * (1 + rng.normal(0, 0.02)))])
    # results, day by day
    fuel_kg_s = Q * 1000.0 / (eta / 100.0 * hhv_h)
    results = []
    for dd in range(365):
        sl = np.arange(dd * 24, dd * 24 + 24)
        sl = sl[run[sl]]
        if len(sl) == 0:
            continue
        date = str(np.datetime64("%d-01-01" % YEAR) + np.timedelta64(dd, "D"))
        e_day = 100.0 * Q[sl].sum() / (100.0 * Q[sl] / eta[sl]).sum()
        coal = (fuel_kg_s[sl] * 3600.0).sum() / 1000.0
        results.append([date, "%.4f" % e_day, "%.3f" % coal])
    pkg = dict(
        boiler=dict(boiler=name, rated_output_MW=rated, bottom_ash_loi=loi_b,
                    radiation_loss=[dict(load_fraction=float(r[0]), loss_pct=float(r[1])) for r in rad]),
        hourly=rows,
        deliveries=[[d["id"], str(np.datetime64("%d-01-01" % YEAR) + np.timedelta64(d["received"], "D"))]
                    + ["%.4f" % v for v in d["a"]] + ["%d" % d["hhv"]] for d in deliveries if d["received"] < 365],
        log=[[str(np.datetime64("%d-01-01T00:00" % YEAR) + np.timedelta64(int(e[0]), "h")).replace("T", " "),
              deliveries[e[2]]["id"]] for e in entries],
        loi=[[str(np.datetime64("%d-01-01" % YEAR) + np.timedelta64(dd, "D")), "%.4f" % loi_day[dd]]
             for dd in range(365) if run[dd * 24:(dd + 1) * 24].any()],
    )
    info = dict(mines=mines, outage=[o0, olen], drift=cond.get("drift"), mislabels=labels,
                entries=len(entries), eta_mean=round(float(eta[run].mean()), 3))
    return pkg, results, info


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_package(d, pkg):
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "boiler.json"), "w") as f:
        json.dump(pkg["boiler"], f, indent=1)
        f.write("\n")
    write_csv(os.path.join(d, "hourly.csv"), ["hour", "heat_output_MW", "co2_pct", "o2_a_pct", "o2_b_pct",
              "o2_outlet_pct", "co_ppm", "gas_outlet_C", "air_inlet_C", "humidity_kg_kg"], pkg["hourly"])
    write_csv(os.path.join(d, "deliveries.csv"), ["delivery", "received", "C", "H", "O", "N", "S", "ash",
              "moisture", "hhv_kJ_kg"], pkg["deliveries"])
    write_csv(os.path.join(d, "bunker_log.csv"), ["hour", "delivery"], pkg["log"])
    write_csv(os.path.join(d, "fly_ash.csv"), ["date", "loi"], pkg["loi"])


def main(root):
    conditions = {}
    for name, place, seed, rated, mines, cond in BOILERS:
        pkg, results, info = build(name, seed, rated, mines, cond)
        conditions[name] = info
        header = ["date", "efficiency_pct", "coal_t"]
        if place == "hidden":
            write_package(os.path.join(root, "tests", "boilers", name), pkg)
            os.makedirs(os.path.join(root, "tests", "sealed", "results"), exist_ok=True)
            write_csv(os.path.join(root, "tests", "sealed", "results", name + ".csv"), header, results)
        else:
            d = os.path.join(root, "environment", "data", place, name)
            write_package(d, pkg)
            if place == "examples":
                write_csv(os.path.join(d, "expected.csv"), header, results)
            else:
                os.makedirs(os.path.join(root, "authoring", "provenance", "pending_results"), exist_ok=True)
                write_csv(os.path.join(root, "authoring", "provenance", "pending_results", name + ".csv"), header, results)
        print(name, place, json.dumps(info))
    with open(os.path.join(root, "authoring", "provenance", "conditions.json"), "w") as f:
        json.dump(conditions, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
