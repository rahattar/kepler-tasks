"""v2 = v1 packages plus a drain RTD, with supply RTDs that read wrong in ways the control system does not flag.
The true inlet temperature of every point, and so the truth, is v1's. usage: pack2.py (run in this folder)"""
import csv, glob, os, random, shutil
rng = random.Random(31)
V0 = "/home/claude/work/jb0/core"; V1 = "/home/claude/work/jb1/core"
# package: (kind, sensor, value, after this date, before this date)
FAULT = {"startup_S-5": [("stuck", "b", 45.3, "0", "9")],
         "blower_B-77": [("bias", "b", -4.6, "0", "2025-03-01"), ("bias", "a", 3.8, "2026-01-01", "9")],
         "gearbox_G-301": [("bias", "a", 5.2, "2025-06-01", "2025-12-31"), ("bias", "b", -4.4, "2026-04-01", "9")],
         "mill_pinion_Z-12": [("bias", "a", -5.5, "2024-01-01", "2024-12-31")],
         "compressor_C-9": [("bias", "b", 4.2, "2025-09-01", "9")]}
shutil.rmtree("core", ignore_errors=True); shutil.copytree(V1, "core")
for d in sorted(glob.glob("core/hidden/*")) + sorted(glob.glob("core/data/examples/*")):
    name = os.path.basename(d); hidden = "hidden" in d
    v0 = os.path.join(V0, "hidden" if hidden else "data/examples", name)
    true = {r["point"]: float(r["inlet_C"]) for r in csv.DictReader(open(v0 + "/points.csv"))}
    res = {r["point"]: float(r["t_eff_C"]) for r in csv.DictReader(open(os.path.join(d, "truth.csv" if hidden else "expected.csv")))}
    rows = list(csv.DictReader(open(d + "/points.csv")))
    faults = FAULT.get(name)
    for r in rows:
        t = true[r["point"]]; a, b = r["inlet_a_C"], r["inlet_b_C"]
        flagged = a == "-999" or b == "-999"
        if faults:
            dlt = rng.choice([-0.1, 0.0, 0.1]); va, vb = t + dlt, t - dlt
            for what, which, val, since, until in faults:
                if since < r["date"] < until:
                    if what == "stuck":
                        va, vb = (val, vb) if which == "a" else (va, val)
                    else:
                        va, vb = (va + val, vb) if which == "a" else (va, vb + val)
            r["inlet_a_C"], r["inlet_b_C"] = "%.1f" % va, "%.1f" % vb
        drain = "%.1f" % (2 * res[r["point"]] - t + rng.choice([-0.2, -0.1, 0.0, 0.1, 0.2]))
        if hidden and not faults and not flagged and rng.random() < 0.06:
            drain = "-999"
        r["drain_C"] = drain
    with open(d + "/points.csv", "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)
s = open("core/data/docs/package_format.md").read()
a = "One row for each point: `point,date,speed_rpm,load_N,load_angle_deg,inlet_a_C,inlet_b_C`."
assert a in s
s = s.replace(a, "One row for each point: `point,date,speed_rpm,load_N,load_angle_deg,inlet_a_C,inlet_b_C,drain_C`.")
a = """- `inlet_a_C`, `inlet_b_C`: the readings of the two RTDs in the oil supply to the bearing. A reading the control
  system marked bad is recorded as -999. The control system marks only the failures it detects."""
assert a in s
s = s.replace(a, """- `inlet_a_C`, `inlet_b_C`: the readings of the two RTDs in the oil supply to the bearing
- `drain_C`: the reading of the RTD in the oil drain from the bearing

A reading the control system marked bad is recorded as -999. The control system marks only the failures it
detects.""")
open("core/data/docs/package_format.md", "w").write(s)
