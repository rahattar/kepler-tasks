"""Cases and documents for the journal-bearing bare core v0. usage: gen.py OUT [--truth]"""
import csv, json, os, random, sys
import numpy as np
from model import Bearing

OILS = {"ISO VG 22": (22.0, 4.3, 860.0), "ISO VG 32": (32.0, 5.4, 865.0), "ISO VG 46": (46.0, 6.8, 870.0),
        "ISO VG 68": (68.0, 8.7, 875.0), "ISO VG 100": (100.0, 11.4, 880.0), "ISO VG 150": (150.0, 15.0, 885.0)}
def oil(g): a, b, r = OILS[g]; return dict(grade=g, nu40_cSt=a, nu100_cSt=b, rho15_kg_m3=r)

# name, D mm, L mm, c um, grooves, oil, flow L/min, n points, speed range rpm, specific load range MPa, beta range, inlet range
VISIBLE = [
 ("motor_M-410", 110, 100, 70, [90, 270], "ISO VG 46", 5.0, 24, (1480, 3560), (0.6, 2.4), (0, 0), (40, 50)),
 ("pump_P-220", 80, 80, 50, [90, 270], "ISO VG 68", 2.5, 24, (1480, 2960), (0.8, 2.8), (0, 0), (40, 50)),
 ("fan_K-105", 160, 130, 110, [90, 270], "ISO VG 46", 9.0, 24, (900, 1780), (0.5, 2.0), (0, 0), (40, 50)),
]
HIDDEN = [
 ("gearbox_G-301", 140, 112, 95, [90, 270], "ISO VG 100", 9.0, 60, (900, 1800), (1.0, 3.2), (-55, 55), (45, 55)),
 ("mill_pinion_Z-12", 200, 200, 130, [90, 270], "ISO VG 68", 6.0, 60, (60, 180), (4.0, 6.5), (0, 0), (40, 50)),
 ("blower_B-77", 100, 35, 75, [90, 270], "ISO VG 32", 3.0, 60, (3000, 9000), (0.3, 1.6), (0, 0), (40, 50)),
 ("turbine_T-1", 560, 400, 420, [90, 270], "ISO VG 32", 900.0, 60, (3000, 3600), (0.6, 1.9), (0, 0), (42, 48)),
 ("compressor_C-9", 90, 72, 60, [60, 240], "ISO VG 46", 3.0, 60, (2960, 5900), (0.5, 2.2), (0, 0), (40, 50)),
 ("vertical_V-3", 70, 42, 50, [90, 270], "ISO VG 32", 2.0, 60, (6000, 12000), (0.02, 0.12), (-40, 40), (40, 50)),
 ("startup_S-5", 125, 110, 85, [90, 270], "ISO VG 46", 6.0, 60, (600, 2960), (0.6, 2.6), (0, 0), (12, 82)),
 ("survey_U-200", 300, 240, 240, [90, 270], "ISO VG 46", 150.0, 240, (300, 5200), (0.3, 3.4), (-30, 30), (35, 60)),
]

def make(case, rng):
    name, D, L, c, grooves, og, flow, n, sp, sl, be, ti = case
    brg = dict(tag=name.split("_")[-1], diameter_mm=D, length_mm=L, radial_clearance_um=c, groove_angles_deg=grooves,
               oil=oil(og), oil_flow_L_min=flow)
    pts = []
    coarse = Bearing(brg, 96, 12)
    i = 0
    while len(pts) < n:
        rpm = round(rng.uniform(*sp) / 10) * 10
        load = round(rng.uniform(*sl) * 1e6 * (D / 1000) * (L / 1000) / 100) * 100
        beta = round(rng.uniform(*be)) if be[0] != be[1] else 0
        if name.startswith("startup"):
            tin = round(rng.choice([rng.uniform(12, 24), rng.uniform(72, 82)]), 1)
        else:
            tin = round(rng.uniform(*ti), 1)
        if not acceptable(coarse, rpm, load, beta, tin):
            continue
        i += 1
        pts.append(dict(point="%s-%03d" % (brg["tag"], i), speed_rpm=rpm, load_N=load, load_angle_deg=beta, inlet_C=tin))
    return name, brg, pts

def acceptable(b, rpm, load, beta, tin):
    """One film state only, well away from the transition, inside the standard's scope."""
    valid = []
    for regime in (False, True):
        b.guess = None
        try:
            s = b.point(rpm, load, beta, tin, regime=regime)
        except Exception:
            continue
        if (s["margin"] > 1.0) == regime:
            valid.append(s)
    if len(valid) != 1:
        return False
    s = valid[0]
    return (s["margin"] < 0.75 or s["margin"] > 1.3) and 0.02 <= s["eps"] <= 0.965 and s["t_eff"] <= 105.0

def write(folder, name, brg, pts, results=None, fname="expected.csv"):
    d = os.path.join(folder, name); os.makedirs(d, exist_ok=True)
    json.dump(brg, open(os.path.join(d, "bearing.json"), "w"), indent=1)
    with open(os.path.join(d, "points.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["point", "speed_rpm", "load_N", "load_angle_deg", "inlet_C"]); w.writeheader(); w.writerows(pts)
    if results is not None:
        with open(os.path.join(d, fname), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["point", "h_min_um", "attitude_deg", "power_kW", "t_eff_C", "p_max_MPa"])
            for p, s in zip(pts, results):
                w.writerow([p["point"], "%.3f" % s["hmin_um"], "%.2f" % s["attitude"], "%.4f" % (s["power"] / 1e3),
                            "%.2f" % s["t_eff"], "%.3f" % (s["pmax"] / 1e6)])

def solve_case(brg, pts, grid=(240, 32)):
    b = Bearing(brg, *grid); out = []
    for p in pts:
        b.guess = None
        out.append(b.point(p["speed_rpm"], p["load_N"], p["load_angle_deg"], p["inlet_C"]))
    return out

if __name__ == "__main__":
    out = sys.argv[1]; rng = random.Random(4127)
    which = sys.argv[2] if len(sys.argv) > 2 else "all"
    for group, folder, fname in ((VISIBLE, "data/examples", "expected.csv"), (HIDDEN, "hidden", "truth.csv")):
        for case in group:
            name, brg, pts = make(case, rng)
            if which not in ("all", name): continue
            res = solve_case(brg, pts)
            write(os.path.join(out, folder), name, brg, pts, res, fname)
            e = [s["eps"] for s in res]; m = [s["margin"] for s in res]; t = [s["t_eff"] for s in res]
            print("%-18s eps %.3f-%.3f  Re/Ret %.2f-%.2f  Teff %.0f-%.0f  att %.0f-%.0f  bad margin %d" % (
                name, min(e), max(e), min(m), max(m), min(t), max(t), min(s["attitude"] for s in res),
                max(s["attitude"] for s in res), sum(0.8 < x < 1.25 for x in m)), flush=True)
