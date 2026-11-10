"""Cooler replacement case packages: one example with the engineer's selection, eight hidden cases.

    python3 gen3.py OUT_ROOT     -> OUT_ROOT/data/{docs,examples/<case>}, OUT_ROOT/hidden/<case>, OUT_ROOT/hidden/truth.json
"""
import csv
import json
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catalog  # noqa: E402
import rate     # noqa: E402

GRADES = {"ISO VG 32": (861.0, 32.0, 5.45), "ISO VG 46": (868.0, 46.0, 6.80), "ISO VG 68": (875.0, 68.0, 8.70),
          "ISO VG 100": (882.0, 100.0, 11.2)}

# case definitions. faults: frozen (primary CW transmitter flat through the heat wave), glitch (one bad 10-minute value
# on 'cw', 'oil_in' or 'flow'), ft_cal (flowmeter as-found error, % of reading, adjusted mid-summer), ti_cal (primary CW
# transmitter as-found error, K), oil_change (grade changed after the latest analysis)
CASES = {
    "e410-k400-lube": dict(seed=410, tags=("FT-301", "TI-301", "TI-201", "TI-202"), grade="ISO VG 68", flow=21.0,
                           bump=2.1, oil_in=80.5, cw_base=26.0, wave=5.2, allot=40.0, out_max=50.0, dp_oil=100.0,
                           dp_cw=70.0, ft_cal=-12.0, analysis_grades=["ISO VG 46", "ISO VG 46", "ISO VG 68", "ISO VG 68"]),
    "e120-k100-lube": dict(seed=121, tags=("FT-121", "TI-122", "TI-123", "TI-124"), grade="ISO VG 46", flow=15.5,
                           bump=1.2, oil_in=78.0, cw_base=25.0, wave=5.8, allot=32.0, out_max=48.0, dp_oil=90.0,
                           dp_cw=60.0, pulled=True, ft_cal=-9.0, analysis_grades=["ISO VG 46"] * 3),
    "e230-g200-lube": dict(seed=232, tags=("FT-230", "TI-231", "TI-232", "TI-233"), grade="ISO VG 32", flow=26.0,
                           bump=1.5, oil_in=72.0, cw_base=24.5, wave=4.6, allot=55.0, out_max=46.0, dp_oil=110.0,
                           dp_cw=70.0, glitch="cw", analysis_grades=["ISO VG 32"] * 3),
    "e340-k300-seal": dict(seed=343, tags=("FT-340", "TI-341", "TI-342", "TI-343"), grade="ISO VG 68", flow=11.5,
                           bump=0.9, oil_in=84.0, cw_base=27.0, wave=4.9, allot=26.0, out_max=52.0, dp_oil=100.0,
                           dp_cw=60.0, frozen=True, oil_change="ISO VG 68", analysis_grades=["ISO VG 46"] * 3),
    "e450-c400-lube": dict(seed=454, tags=("FT-450", "TI-451", "TI-452", "TI-453"), grade="ISO VG 46", flow=19.0,
                           bump=1.6, oil_in=82.0, cw_base=25.5, wave=5.5, allot=38.0, out_max=49.0, dp_oil=95.0,
                           dp_cw=70.0, glitch="oil_in", ft_cal=-10.0, analysis_grades=["ISO VG 46"] * 3),
    "e560-k500-lube": dict(seed=565, tags=("FT-560", "TI-561", "TI-562", "TI-563"), grade="ISO VG 46", flow=23.0,
                           bump=1.8, oil_in=79.0, cw_base=26.5, wave=5.0, allot=48.0, out_max=50.0, dp_oil=100.0,
                           dp_cw=75.0, frozen=True, ti_cal=-0.9, analysis_grades=["ISO VG 46"] * 3),
    "e670-t600-lube": dict(seed=676, tags=("FT-670", "TI-671", "TI-672", "TI-673"), grade="ISO VG 100", flow=13.0,
                           bump=1.0, oil_in=86.0, cw_base=25.0, wave=4.8, allot=30.0, out_max=55.0, dp_oil=120.0,
                           dp_cw=70.0, glitch="flow", oil_change="ISO VG 100", analysis_grades=["ISO VG 68"] * 3),
    "e780-k700-lube": dict(seed=787, tags=("FT-780", "TI-781", "TI-782", "TI-783"), grade="ISO VG 68", flow=17.5,
                           bump=1.4, oil_in=81.0, cw_base=26.0, wave=5.3, allot=36.0, out_max=50.0, dp_oil=100.0,
                           dp_cw=70.0, ft_cal=-11.0, ti_cal=0.7, pulled=True, analysis_grades=["ISO VG 68"] * 3),
    "e890-k800-lube": dict(seed=898, tags=("FT-890", "TI-891", "TI-892", "TI-893"), grade="ISO VG 46", flow=20.0,
                           bump=1.7, oil_in=80.0, cw_base=25.8, wave=5.6, allot=42.0, out_max=49.0, dp_oil=100.0,
                           dp_cw=70.0, glitch="cw", ft_cal=-8.0, analysis_grades=["ISO VG 46"] * 3),
}
EXAMPLE = "e410-k400-lube"


def signals(c, rng):
    t = np.arange(np.datetime64("2026-06-01T00:00"), np.datetime64("2026-09-16T00:00"), np.timedelta64(10, "m"))
    n = len(t)
    day = (t - t[0]).astype("timedelta64[m]").astype(float) / 1440.0
    hour = (day % 1.0) * 24
    peak_day = float(rng.uniform(50, 72))
    season = c["cw_base"] + 2.5 * np.sin(np.pi * (day - 5) / 110.0)
    weather = np.convolve(rng.normal(0, 0.35, n), np.ones(144) / 12.0, mode="same")
    cw = season + weather + c["wave"] * np.exp(-((day - peak_day) / 2.6) ** 2) + 1.1 * np.sin(2 * np.pi * (hour - 10) / 24)
    bump_day = float(rng.uniform(15, 40))
    flow = c["flow"] + 0.25 * np.sin(2 * np.pi * day / 7) + rng.normal(0, 0.05, n) \
        + c["bump"] * np.exp(-((day - bump_day) / 0.6) ** 2)
    oil_in = c["oil_in"] + 2.5 * np.sin(2 * np.pi * (hour - 14) / 24) + 0.36 * (cw - c["cw_base"]) + rng.normal(0, 0.15, n)
    for d0 in rng.uniform(5, 100, 5):
        i = int(d0 * 144)
        oil_in[i:i + 2] += 8.0                      # short real upsets (part of the true process values)
    return t, day, flow, oil_in, cw, peak_day, bump_day


def hour_max(x):
    return float(np.max(np.convolve(x, np.ones(6) / 6, mode="valid")))


def write_case(d, name, c):
    rng = np.random.default_rng(c["seed"])
    os.makedirs(d, exist_ok=True)
    t, day, flow, oil_in, cw, peak_day, bump_day = signals(c, rng)
    stamp = np.char.replace(t.astype("datetime64[m]").astype(str), "T", " ")
    ftag, otag, ctag, htag = c["tags"]
    # instruments as recorded
    cal_day = float(rng.uniform(bump_day + 5, 95)) if c.get("ft_cal") else None
    ft = flow.copy()
    if c.get("ft_cal"):
        ft = np.where(day < cal_day, flow * (1 + c["ft_cal"] / 100.0), flow)
    ti_p = cw + rng.normal(0, 0.05, len(t))
    ti_cal_day = float(rng.uniform(peak_day + 4, 100)) if c.get("ti_cal") else None
    if c.get("ti_cal"):
        ti_p = np.where(day < ti_cal_day, ti_p + c["ti_cal"], ti_p)
    ti_h = cw - 0.10 + rng.normal(0, 0.05, len(t))
    pulled = frozen = None
    if c.get("pulled"):                             # transmitter out of its thermowell: reads the air in the pipe rack
        a, b = peak_day - float(rng.uniform(6.0, 9.0)), peak_day + float(rng.uniform(3.0, 5.0))
        pulled = (a, b)
        hourp = (day % 1.0) * 24
        air = cw + 2.2 + 4.5 * np.sin(2 * np.pi * (hourp - 9) / 24) + rng.normal(0, 0.25, len(t))
        ti_p = np.where((day >= a) & (day < b), air, ti_p)
    if c.get("frozen"):
        a, b = peak_day - float(rng.uniform(2.0, 3.0)), peak_day + float(rng.uniform(2.0, 3.5))
        frozen = (a, b)
        fr = (day >= a) & (day < b)
        i0 = int(np.argmax(fr))
        ti_p = np.where(fr, round(float(ti_p[i0 - 1]), 2), ti_p)
    oi = oil_in.copy()
    g = c.get("glitch")
    if g:
        j = int(rng.uniform(20, 95) * 144)
        if g == "cw":
            j = int((peak_day + float(rng.uniform(-1.5, 1.5))) * 144)
            ti_p[j] = 61.37
            ti_h[j] = cw[j] - 0.1
        elif g == "oil_in":
            oi[j] = 171.8
        elif g == "flow":
            ft[j] = ft[j] * 2.9
    with open(os.path.join(d, "trend.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", ftag, otag, ctag, htag])
        for row in zip(stamp, ft, oi, ti_p, ti_h):
            w.writerow([row[0]] + ["%.2f" % v for v in row[1:]])
    with open(os.path.join(d, "instruments.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tag", "measurement", "unit", "location"])
        w.writerow([ftag, "oil flow", "kg/s", "Coriolis meter, oil supply to the cooler"])
        w.writerow([otag, "oil temperature", "degC", "cooler oil inlet nozzle"])
        w.writerow([ctag, "cooling water temperature", "degC", "cooler water inlet nozzle"])
        w.writerow([htag, "cooling water temperature", "degC",
                    "cooling tower basin outlet, upstream of the CW pumps; the cooler is the first user on the pumps' "
                    "discharge header"])

    def date_of(dd):
        return str(np.datetime64("2026-06-01") + np.timedelta64(int(dd), "D"))
    cals = [("2026-02-%02d" % int(rng.integers(3, 25)), tag, "0.0" if tag == ftag else "0.0",
             "% of reading" if tag == ftag else "K", "no") for tag in (ftag, otag, ctag, htag)]
    if c.get("ft_cal"):
        cals.append((date_of(cal_day), ftag, "%.1f" % c["ft_cal"], "% of reading", "yes"))
    if c.get("ti_cal"):
        cals.append((date_of(ti_cal_day), ctag, "%.1f" % c["ti_cal"], "K", "yes"))
    cals.sort()
    with open(os.path.join(d, "calibration.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "tag", "as_found_error", "error_unit", "adjusted"])
        for r in cals:
            w.writerow(r)
    # oil analyses and the oil in service
    an_dates = ["2025-09-%02d" % int(rng.integers(2, 28)), "2026-01-%02d" % int(rng.integers(2, 28)),
                "2026-0%d-%02d" % (int(rng.integers(4, 6)), int(rng.integers(2, 28)))]
    grades = c["analysis_grades"][-3:]
    rows = []
    for dt, gr in zip(an_dates, grades):
        r15, n40, n100 = GRADES[gr]
        rows.append((dt, gr, r15, round(n40 * float(rng.uniform(0.98, 1.02)), 1), round(n100 * float(rng.uniform(0.985, 1.015)), 2)))
    with open(os.path.join(d, "oil_analysis.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sample_date", "oil", "density_15c_kg_m3", "viscosity_40c_cst", "viscosity_100c_cst"])
        for r in rows:
            w.writerow(r)
    log = [("2026-0%d-%02d" % (int(rng.integers(6, 9)), int(rng.integers(2, 28))), c["tags"][0][:2] + "-filter",
            "Duplex oil filter changeout.")]
    if c.get("oil_change"):
        log.append(("2026-08-%02d" % int(rng.integers(2, 28)), "oil system",
                    "Oil system drained and refilled with %s (grade change)." % c["oil_change"]))
    if c.get("frozen"):
        log.append((date_of(frozen[1]), ctag, "Operations report the transmitter stuck; restarted, reading again."))
    if pulled:
        log.append((date_of(pulled[1]), ctag, "Pipe insulation work completed; transmitter put back in its thermowell."))
    for r in cals:
        if r[4] == "yes":
            log.append((r[0], r[1], "Calibrated and adjusted (see calibration records)."))
    log.sort()
    with open(os.path.join(d, "maintenance.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "tag", "text"])
        for r in log:
            w.writerow(r)
    case = dict(cooler=name.split("-")[0].upper(), service="lube oil cooler of %s" % name.split("-")[1].upper(),
                period=["2026-06-01", "2026-09-15"], cw_allotment_kg_s=c["allot"], oil_outlet_max_c=c["out_max"],
                oil_dp_max_kpa=c["dp_oil"], cw_dp_max_kpa=c["dp_cw"], cw_velocity_m_s=[0.6, 2.4])
    with open(os.path.join(d, "case.json"), "w") as f:
        json.dump(case, f, indent=1)
    # the oil in service and its properties, per the procedure
    if c.get("oil_change"):
        r15, n40, n100 = GRADES[c["oil_change"]]
        oil = dict(grade=c["oil_change"], rho15=r15, nu40=n40, nu100=n100)
    else:
        last = rows[-1]
        oil = dict(grade=last[1], rho15=last[2], nu40=last[3], nu100=last[4])
    basis = dict(oil=oil, oil_kg_s=round(hour_max(flow), 3), oil_in_c=round(hour_max(oil_in), 3),
                 cw_in_c=round(hour_max(cw), 3), cw_kg_s=c["allot"], fouling_oil=0.000176)
    return basis, case


def optimum(basis, case):
    """Cheapest design meeting the case (price order, every baffle cut and 5 mm spacing step)."""
    cands = {}
    for dsg in catalog.designs(spacing_step_mm=5):
        key = tuple(dsg[k] for k in ("shell_id_mm", "tube", "tube_length_m", "tube_passes", "layout_deg", "shells_in_series"))
        cands.setdefault(key, []).append(dsg)
    order = sorted(cands, key=lambda k: catalog.price(k[0], k[2], cands[k][0]["tubes"], cands[k][0]["tube_od_mm"], k[3], k[4]) * k[5])
    for key in order:
        p = catalog.price(key[0], key[2], cands[key][0]["tubes"], cands[key][0]["tube_od_mm"], key[3], key[4]) * key[5]
        for dsg in cands[key]:
            try:
                r = rate.rate(dsg, basis)
            except Exception:
                continue
            if not (case["cw_velocity_m_s"][0] <= r["tube_velocity"] <= case["cw_velocity_m_s"][1]) or \
                    r["dp_tube_kpa"] > case["cw_dp_max_kpa"]:
                break
            if meets(r, case):
                return p, dsg, r
    return None


def meets(r, case, tol_t=0.0, tol_p=0.0):
    return (r["oil_out_c"] <= case["oil_outlet_max_c"] + tol_t and r["dp_shell_kpa"] <= case["oil_dp_max_kpa"] * (1 + tol_p)
            and r["dp_tube_kpa"] <= case["cw_dp_max_kpa"] * (1 + tol_p)
            and case["cw_velocity_m_s"][0] <= r["tube_velocity"] <= case["cw_velocity_m_s"][1])


def main(root):
    docs = os.path.join(root, "data", "docs")
    shutil.copytree(os.path.join(HERE, "docs"), docs, dirs_exist_ok=True)
    with open(os.path.join(docs, "oil_grades.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["oil", "density_15c_kg_m3", "viscosity_40c_cst", "viscosity_100c_cst"])
        for g, v in GRADES.items():
            w.writerow([g, *v])
    with open(os.path.join(docs, "vendor_catalogue_tube_counts.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["shell_id_mm", "tube", "layout_deg", "tube_passes", "tubes"])
        for s in catalog.SHELLS_MM:
            for tk, (od, wall) in catalog.TUBES.items():
                for lay in catalog.LAYOUTS:
                    for p in catalog.PASSES:
                        n = catalog.tube_count(s, od, lay, p)
                        if n >= 20:
                            w.writerow([s, tk, lay, p, n])
    truth = {}
    for name, c in CASES.items():
        hidden = name != EXAMPLE
        d = os.path.join(root, "hidden" if hidden else os.path.join("data", "examples"), name)
        basis, case = write_case(d, name, c)
        p, dsg, r = optimum(basis, case)
        sel = {k: dsg[k] for k in ("shell_id_mm", "tube", "tube_length_m", "tube_passes", "layout_deg",
                                   "baffle_cut_pct", "baffle_spacing_mm", "shells_in_series")}
        if hidden:
            truth[name] = dict(basis=basis, case=case, min_price=p, reference_design=sel)
        else:
            with open(os.path.join(d, "selection.json"), "w") as f:
                json.dump(dict(sel, price_usd=p, design_case=dict(oil=basis["oil"]["grade"], oil_kg_s=basis["oil_kg_s"],
                                                                 oil_in_c=basis["oil_in_c"], cw_in_c=basis["cw_in_c"])), f,
                          indent=1)
        print(name, p, sel, round(r["oil_out_c"], 2), {k: basis[k] for k in ("oil_kg_s", "oil_in_c", "cw_in_c")})
    with open(os.path.join(root, "hidden", "truth.json"), "w") as f:
        json.dump(truth, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
