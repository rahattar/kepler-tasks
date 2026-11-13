#!/usr/bin/env python3
"""The unoptimised program of the core: the same card analysis as the reference, then every setting stepped
through time on its own as a chain of rod elements until its cycle repeats. Right, and far over the limit."""
import csv, json, os, sys
import numpy as np
sys.path.insert(0, os.environ.get("RP_CORE", os.path.dirname(os.path.abspath(__file__))))
import ref_rodlift as rf
import rodsim as rs


def main(field_dir, out_csv, only=None):
    fld = json.load(open(os.path.join(field_dir, "field.json")))
    c = fld["damping_per_s"]; rho_f = fld["liquid_density_kg_m3"]
    rd = lambda name: list(csv.DictReader(open(os.path.join(field_dir, name))))
    wells = {w["well"]: w for w in rd("wells.csv")}
    rods = {}
    for r in rd("rods.csv"):
        rods.setdefault(r["well"], []).append((int(r["taper"]), r["material"], float(r["diameter_mm"]), float(r["length_m"])))
    cards = {}
    for r in rd("cards.csv"):
        cards.setdefault(r["well"], {}).setdefault(r["card"], []).append((int(r["sample"]), float(r["position_m"]), float(r["load_kN"])))
    per = {}
    for name, w in wells.items():
        sections = [(m, d, L) for _, m, d, L in sorted(rods[name])]
        L = float(w["pump_depth_m"]); Ap = rf.area(float(w["plunger_mm"]))
        At = rs.tubing_area("%.1f" % float(w["tubing_od_mm"]))
        pd = float(w["tubing_head_pressure_kPa"]) * 1e3 + rho_f * rf.G * L
        W = rs.buoyant_weight(sections, rho_f)
        free = L / (rf.E_TUBING * At)
        reg = free if w["anchor_depth_m"] == "" else (L - float(w["anchor_depth_m"])) / (rf.E_TUBING * At)
        cs = []
        for cid, rows in cards[name].items():
            rows.sort()
            cs.append((np.array([p for _, p, _ in rows]), np.array([f for _, _, f in rows]) * 1e3))
        Fo, pi, comp, meas, q_in = rf.diagnose(sections, c, W, Ap, pd, cs, float(w["found_spm"]), reg, free)
        per[name] = (sections, Ap, pd, pi, comp, float(w["unit_factor"]), q_in)
    out = []
    sets = rd("settings.csv")
    for r in sets[:only]:
        sections, Ap, pd, pi, comp, lam, q_in = per[r["well"]]
        o = rs.simulate(sections, c, Ap, pd, pi, 1 / comp, rho_f, [float(r["surface_stroke_m"])], [float(r["spm"])], lam, q_in)
        out.append((r["setting"], o["stroke"][0], Ap * o["h_liq"][0] * float(r["spm"]) * 1440.0, o["pprl"][0] / 1e3, o["mprl"][0] / 1e3))
    with open(out_csv, "w", newline="") as f:
        x = csv.writer(f); x.writerow(["setting", "plunger_stroke_m", "liquid_m3_d", "pprl_kN", "mprl_kN"])
        for row in out:
            x.writerow([row[0]] + ["%.5f" % v for v in row[1:]])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(os.environ["ONLY"]) if "ONLY" in os.environ else None)
