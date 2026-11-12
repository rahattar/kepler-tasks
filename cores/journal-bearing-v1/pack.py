"""Bare core v1: the v0 cases wrapped in plant records. usage: pack.py OUT

Each hidden case keeps its v0 operating points. What changes is how the bearing, its oil and the inlet
temperature have to be established: from a datasheet as built, a maintenance history, oil analyses and two
inlet RTDs. Points whose bearing state differs from v0's are solved again with the truth model.
"""
import csv, json, os, random, sys
import gen
from model import Bearing

V0 = "/home/claude/work/jb0/core"
HEAD = ["point", "h_min_um", "attitude_deg", "power_kW", "t_eff_C", "p_max_MPa"]
ROUTINE = [("INSPECTED", "bearing inspected, no findings"), ("ALIGNED", "coupling alignment checked"),
           ("SEAL_REPLACED", "oil seal replaced"), ("PROBE_REPLACED", "vibration probe replaced")]

def load(folder, name, truthfile):
    d = os.path.join(V0, folder, name)
    brg = json.load(open(d + "/bearing.json"))
    pts = list(csv.DictReader(open(d + "/points.csv")))
    truth = {r["point"]: r for r in csv.DictReader(open(os.path.join(d, truthfile)))}
    return brg, pts, truth

def row(pt, s):
    return {"point": pt, "h_min_um": "%.3f" % s["hmin_um"], "attitude_deg": "%.2f" % s["attitude"],
            "power_kW": "%.4f" % (s["power"] / 1e3), "t_eff_C": "%.2f" % s["t_eff"], "p_max_MPa": "%.4f" % (s["pmax"] / 1e6)}

def day(rng, a, b):
    """A date between two ISO dates, exclusive of both."""
    import datetime
    A, B = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    return (A + datetime.timedelta(days=rng.randrange(1, (B - A).days))).isoformat()

# what each hidden case's records say. "pre" is the bearing state for points dated before `split`.
SPEC = {
 "gearbox_G-301": dict(sheet=dict(radial_clearance_um=80), split="2025-02-10", pre=dict(radial_clearance_um=80),
     history=[("2024-03-18", "NDE", "SHELL_FITTED", "0.17", "re-metalled shell fitted"),
              ("2025-02-10", "DE", "SHELL_FITTED", "0.19", "new shell fitted, lead wire check")]),
 "mill_pinion_Z-12": dict(sheet=dict(diameter_mm=200.04, radial_clearance_um=120), split="2025-01-20",
     pre=dict(diameter_mm=200.04, radial_clearance_um=110),
     history=[("2023-05-08", "DE", "SHELL_FITTED", "0.22", "re-metalled shell fitted"),
              ("2025-01-20", "DE", "JOURNAL_GROUND", "200.00", "journal scored, ground and polished")],
     first="2023-06-01"),
 "blower_B-77": dict(sheet=dict(diameter_mm=100.03, radial_clearance_um=75),
     history=[("2022-09-12", "DE", "JOURNAL_GROUND", "100.00", "journal ground after wire-wool damage"),
              ("2024-04-22", "DE", "SHELL_FITTED", "0.15", "new shell fitted to the ground journal"),
              ("2024-04-22", "NDE", "SHELL_FITTED", "0.17", "new shell fitted")], first="2024-05-01"),
 "turbine_T-1": dict(sheet=dict(oil_grade="ISO VG 46"), oil=(33.1, 5.5, 866.0),
     history=[("2025-03-03", "-", "OIL_CHANGED", "32", "charge renewed at the outage, grade changed on the maker's advice")],
     samples=[("2024-11-20", "46.9", "6.9", "871", "routine"), ("2025-04-07", "33.1", "5.5", "866", "routine")],
     first="2025-04-10"),
 "compressor_C-9": dict(sheet=dict(groove_angles_deg=[90, 270]),
     history=[("2024-02-05", "DE", "SPLIT_SET", "-30", "housing rebuilt with the split line 30 degrees against rotation"),
              ("2024-02-05", "NDE", "SPLIT_SET", "-30", "housing rebuilt with the split line 30 degrees against rotation")],
     first="2024-03-01"),
 "vertical_V-3": dict(sheet={}, history=[], flagged="a"),
 "startup_S-5": dict(sheet={}, history=[], frozen=45.3),
 "survey_U-200": dict(sheet=dict(oil_grade="ISO VG 68", oil_flow_L_min=120.0),
     history=[("2023-10-16", "-", "OIL_CHANGED", "46", "charge renewed"),
              ("2023-10-18", "DE", "ORIFICE_CHANGED", "150", "supply orifice bored out"),
              ("2023-10-18", "NDE", "ORIFICE_CHANGED", "110", "supply orifice bored out")],
     samples=[("2023-06-12", "66.2", "8.6", "876", "routine")], first="2023-11-01", flagged="b"),
}

def package(out, folder, name, truthfile, rng, spec=None):
    brg, pts, truth = load(folder, name, truthfile)
    spec = spec or dict(sheet={}, history=[])
    first, last = spec.get("first", "2024-01-08"), "2026-10-30"
    sheet = dict(tag=brg["tag"], machine=name.split("_")[0], position="DE", journal_diameter_mm=brg["diameter_mm"],
                 length_mm=brg["length_mm"], radial_clearance_um=brg["radial_clearance_um"],
                 groove_angles_deg=brg["groove_angles_deg"], oil_grade=brg["oil"]["grade"],
                 oil_flow_L_min=brg["oil_flow_L_min"])
    for k, v in spec["sheet"].items():
        sheet["journal_diameter_mm" if k == "diameter_mm" else k] = v
    # dates, and the points that fall before a change of state
    split = spec.get("split")
    rows, redo = [], []
    order = list(range(len(pts))); rng.shuffle(order)
    early = set(order[:len(pts) // 2]) if split else set()
    for i, p in enumerate(pts):
        d = day(rng, first, split) if i in early else day(rng, split or first, last)
        t = float(p["inlet_C"]); dlt = rng.choice([-0.2, -0.1, 0.0, 0.1, 0.2])
        a, b = "%.1f" % (t + dlt), "%.1f" % (t - dlt)
        if "frozen" in spec:
            a, b = "%.1f" % t, "%.1f" % spec["frozen"]
        if spec.get("flagged") and rng.random() < 0.15:
            if spec["flagged"] == "a": a, b = "-999", "%.1f" % t
            else: a, b = "%.1f" % t, "-999"
        rows.append(dict(point=p["point"], date=d, speed_rpm=p["speed_rpm"], load_N=p["load_N"],
                         load_angle_deg=p["load_angle_deg"], inlet_a_C=a, inlet_b_C=b))
        if i in early or "oil" in spec:
            redo.append(i)
    # points whose state differs from v0: solve again
    out_truth = dict(truth)
    if redo:
        pre = dict(brg)
        if "oil" in spec:
            pre["oil"] = dict(grade="in service", nu40_cSt=spec["oil"][0], nu100_cSt=spec["oil"][1], rho15_kg_m3=spec["oil"][2])
        coarse = Bearing(dict(pre, **(spec.get("pre", {}) if True else {})), 96, 12)
        fine = Bearing(dict(pre, **spec.get("pre", {})), 240, 32)
        for i in redo:
            p = pts[i]; args = (float(p["speed_rpm"]), float(p["load_N"]), float(p["load_angle_deg"]), float(p["inlet_C"]))
            if not gen.acceptable(coarse, *args):
                if "oil" in spec: raise SystemExit("%s %s is not acceptable with the oil in service" % (name, p["point"]))
                rows[i]["date"] = day(rng, split, last)          # leave it in the later state
                continue
            fine.guess = None
            out_truth[p["point"]] = row(p["point"], fine.point(*args))
    rows.sort(key=lambda r: (r["date"], r["point"]))
    hist = list(spec["history"])
    for _ in range(rng.randrange(3, 6)):
        w, rem = rng.choice(ROUTINE)
        hist.append((day(rng, "2022-01-10", last), rng.choice(["DE", "NDE"]), w, "", rem))
    hist.sort()
    d = os.path.join(out, "data/examples" if folder != "hidden" else "hidden", name); os.makedirs(d, exist_ok=True)
    json.dump(sheet, open(d + "/datasheet.json", "w"), indent=1)
    with open(d + "/history.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "position", "work", "value", "remarks"]); w.writerows(hist)
    with open(d + "/oil_samples.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "nu40_cSt", "nu100_cSt", "rho15_kg_m3", "remarks"]); w.writerows(spec.get("samples", []))
    with open(d + "/points.csv", "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
    with open(os.path.join(d, truthfile), "w", newline="") as f:
        w = csv.DictWriter(f, HEAD); w.writeheader()
        for r in rows: w.writerow({k: out_truth[r["point"]][k] for k in HEAD})
    print("%-18s %3d points, %3d solved again" % (name, len(rows), len(redo)), flush=True)

if __name__ == "__main__":
    out = sys.argv[1]; rng = random.Random(907)
    for name in ("motor_M-410", "pump_P-220", "fan_K-105"):
        package(out, "data/examples", name, "expected.csv", rng)
    for name in SPEC:
        if len(sys.argv) > 2 and name not in sys.argv[2:]: continue
        package(out, "hidden", name, "truth.csv", rng, SPEC[name])
