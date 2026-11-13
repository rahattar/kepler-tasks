"""Builds the fields of the rod-pump core from sealed descriptions: the visible fields (two with results, one
without) and the hidden fields with their shift. python3 gen.py [field ...] [--refine N]"""
import csv, json, os, sys
import numpy as np
import rodsim as rs

HERE = os.path.dirname(os.path.abspath(__file__))
SPEEDS = np.arange(4.0, 10.01, 0.25)
UNITS = {"A": [1.83, 2.13, 2.44, 2.74], "B": [2.44, 2.74, 3.05, 3.66], "C": [3.05, 3.66, 4.27, 4.88]}

# role: example (results beside it), pending (visible, no results), hidden (the program is run on it).
# loose: wells whose registered anchor does not hold the tubing. depth: range of pump depths, m.
FIELDS = {
    "north_lease": dict(role="example", seed=11, tag="NL", wells=22, depth=(850, 2100), loose=0, fibre=1, high=3, bare=3),
    "creek_unit":  dict(role="example", seed=12, tag="CU", wells=20, depth=(900, 2150), loose=0, fibre=1, high=2, bare=2),
    "mesa_block":  dict(role="pending", seed=13, tag="MB", wells=18, depth=(950, 2200), loose=2, fibre=1, high=2, bare=2),
    "harlan_flat": dict(role="hidden", seed=21, tag="HF", wells=24, depth=(1000, 2900), loose=4, fibre=3, high=3, bare=2),
    "tule_draw":   dict(role="hidden", seed=22, tag="TD", wells=24, depth=(1100, 2850), loose=3, fibre=2, high=2, bare=3),
    "stone_ranch": dict(role="hidden", seed=23, tag="SR", wells=22, depth=(900, 2600), loose=0, fibre=2, high=3, bare=2),
    "pike_bend":   dict(role="hidden", seed=24, tag="PB", wells=24, depth=(1200, 2900), loose=5, fibre=3, high=2, bare=2),
    "cedar_point": dict(role="hidden", seed=25, tag="CP", wells=23, depth=(1000, 2800), loose=3, fibre=2, high=3, bare=3),
    "ash_hollow":  dict(role="hidden", seed=26, tag="AH", wells=24, depth=(1100, 2900), loose=4, fibre=4, high=2, bare=2),
}


def string_for(rng, L, plunger, fibre):
    if fibre:
        f = rng.uniform(0.52, 0.66)
        parts = [("fibreglass", 31.8, f), ("steel", 25.4, 1 - f)]
    elif L < 1150:
        parts = [("steel", 22.2 if plunger > 45 else 19.1, 1.0)]
    elif L < 1800 and plunger < 50:
        f = rng.uniform(0.40, 0.52)
        parts = [("steel", 22.2, f), ("steel", 19.1, 1 - f)]
    else:
        f1 = rng.uniform(0.27, 0.34); f2 = rng.uniform(0.30, 0.36)
        parts = [("steel", 25.4, f1), ("steel", 22.2, f2), ("steel", 19.1, 1 - f1 - f2)]
    out = []; used = 0.0
    for i, (m, d, f) in enumerate(parts):
        ln = round(L * f) if i < len(parts) - 1 else L - used
        out.append((m, d, float(ln))); used += ln
    return out


def make_well(rng, spec, kind):
    lo, hi = spec["depth"]
    if kind == "bare":
        L = rng.uniform(lo, min(hi, 1250))
    elif kind == "loose":
        L = rng.uniform(max(lo, 1500), hi)
    else:
        L = rng.uniform(lo, hi)
    L = float(5 * round(L / 5))
    if L < 1300:
        plunger = rng.choice([44.5, 50.8, 57.2])
    elif L < 2000:
        plunger = rng.choice([38.1, 44.5, 50.8])
    else:
        plunger = rng.choice([38.1, 44.5]) if kind == "loose" else rng.choice([31.8, 38.1, 44.5])
    if plunger >= 57:
        tub = "88.9" if rng.random() < 0.5 else "73.0"
    elif plunger <= 38.5 and rng.random() < 0.4:
        tub = "60.3"
    else:
        tub = "73.0"
    if kind == "loose" and tub == "88.9":
        tub = "73.0"
    sections = string_for(rng, L, plunger, kind == "fibre")
    if kind == "bare":
        anchor = None
    elif kind == "high":
        anchor = float(round(L - rng.uniform(300, 600)))
    else:
        anchor = float(round(L - rng.uniform(15, 45)))
    unit = "A" if L < 1200 else ("C" if (L > 2000 or kind == "fibre") else "B")
    return dict(L=L, plunger=float(plunger), tubing=tub, sections=sections, anchor=anchor,
                holds=(kind != "loose"), p_th=float(round(rng.uniform(400, 1500), -1)) * 1e3,
                p_i=float(round(rng.uniform(0.6, 3.5), 2)) * 1e6, unit=unit,
                lam=float(round(rng.uniform(0.08, 0.30), 2)),
                found_hole=int(rng.integers(0, 4)), found_spm=float(round(rng.uniform(5.0, 8.5), 1)),
                fill=(None if rng.random() < 0.55 else float(rng.uniform(0.45, 0.85))), kind=kind)


def well_physics(w, c, rho_f):
    Ap = rs.area(w["plunger"]); pd = w["p_th"] + rho_f * rs.G * w["L"]
    At = rs.tubing_area(w["tubing"])
    free = w["L"] / (rs.E_TUBING * At)
    if w["anchor"] is None or not w["holds"]:
        comp = free
    else:
        comp = (w["L"] - w["anchor"]) / (rs.E_TUBING * At)
    return Ap, pd, comp, free


def build(name, refine=2, quiet=False):
    spec = FIELDS[name]; rng = np.random.default_rng(spec["seed"])
    c = float(round(rng.uniform(0.25, 0.55), 2)); rho_f = float(round(rng.uniform(900, 1010)))
    kinds = (["loose"] * spec["loose"] + ["fibre"] * spec["fibre"] + ["high"] * spec["high"] + ["bare"] * spec["bare"])
    kinds += ["plain"] * (spec["wells"] - len(kinds))
    order = rng.permutation(len(kinds))
    wells = []; log = []
    for slot in range(len(kinds)):
        kind = kinds[order[slot]]
        for attempt in range(60):
            w = make_well(rng, spec, kind)
            Ap, pd, comp, free = well_physics(w, c, rho_f)
            stroke = UNITS[w["unit"]][w["found_hole"]]
            st = np.repeat(UNITS[w["unit"]], SPEEDS.size); sp = np.tile(SPEEDS, 4)
            # liquid supply: from the stroke the well would make full at its found setting
            o = rs.simulate(w["sections"], c, Ap, pd, w["p_i"], 1 / comp, rho_f, [stroke], [w["found_spm"]], w["lam"], np.inf, refine=1)
            Fo = o["Fo"]
            w["q_in"] = np.inf if w["fill"] is None else float(w["fill"] * Ap * o["stroke"][0] * w["found_spm"] / 60.0)
            frac = Fo * free / o["stroke"][0]
            if kind == "loose" and frac < 0.085:
                continue
            if kind == "bare" and frac > 0.07:
                continue
            if w["fill"] is not None:
                # a found pump is either full or plainly short of liquid
                f0 = rs.simulate(w["sections"], c, Ap, pd, w["p_i"], 1 / comp, rho_f, [stroke], [w["found_spm"]], w["lam"], w["q_in"], refine=1)
                if f0["h_liq"][0] / f0["stroke"][0] > 0.90:
                    continue
            res = rs.simulate(w["sections"], c, Ap, pd, w["p_i"], 1 / comp, rho_f, st, sp, w["lam"], w["q_in"], refine=refine)
            ok = (res["n_tv"] == 1).all() and (res["n_bad"] == 0).all() and (res["mprl"] > 2e3).all() and (res["stroke"] > 0.5).all()
            # a loose anchor has to matter at every setting of the table: more than twice the band on the stroke
            if kind == "loose" and (Fo * free / res["stroke"]).min() < 0.065:
                ok = False
            if ok:
                break
        else:
            raise SystemExit("no well for slot %d of %s" % (slot, name))
        fnd = rs.simulate(w["sections"], c, Ap, pd, w["p_i"], 1 / comp, rho_f, [stroke], [w["found_spm"]], w["lam"], w["q_in"], refine=refine, record=200)
        w["well"] = "%s-%02d" % (spec["tag"], slot + 1)
        w["found_stroke"] = stroke; w["res"] = res; w["card"] = fnd["card"]; w["st"] = st; w["sp"] = sp
        w["found_fill"] = float(fnd["h_liq"][0] / fnd["stroke"][0]); w["stretch_frac"] = float(frac)
        w["Fo"] = float(Fo); w["found_S"] = float(fnd["stroke"][0])
        wells.append(w)
        if not quiet:
            print("%s %-6s L %4.0f pl %.1f tub %s Fo %5.1f kN free stretch %4.1f%% of stroke, found fill %.2f, attempts %d" %
                  (w["well"], kind, w["L"], w["plunger"], w["tubing"], Fo / 1e3, 100 * frac, w["found_fill"], attempt + 1), flush=True)
    role = spec["role"]
    base = os.path.join(HERE, "core")
    d = {"example": os.path.join(base, "environment", "data", "examples", name),
         "pending": os.path.join(base, "environment", "data", "pending", name),
         "hidden": os.path.join(base, "hidden", name)}[role]
    os.makedirs(d, exist_ok=True)
    json.dump({"field": name, "damping_per_s": c, "liquid_density_kg_m3": rho_f}, open(os.path.join(d, "field.json"), "w"), indent=1)
    def wr(fn, head, rows):
        with open(os.path.join(d, fn), "w", newline="") as f:
            x = csv.writer(f, lineterminator="\n"); x.writerow(head); x.writerows(rows)
    wr("wells.csv", ["well", "pump_depth_m", "plunger_mm", "tubing_od_mm", "anchor_depth_m", "tubing_head_pressure_kPa",
                     "unit_factor", "found_surface_stroke_m", "found_spm"],
       [[w["well"], "%.0f" % w["L"], "%.1f" % w["plunger"], w["tubing"], "" if w["anchor"] is None else "%.0f" % w["anchor"],
         "%.0f" % (w["p_th"] / 1e3), "%.2f" % w["lam"], "%.2f" % w["found_stroke"], "%.1f" % w["found_spm"]] for w in wells])
    wr("rods.csv", ["well", "taper", "material", "diameter_mm", "length_m"],
       [[w["well"], i + 1, m, "%.1f" % dd, "%.0f" % ln] for w in wells for i, (m, dd, ln) in enumerate(w["sections"])])
    crng = np.random.default_rng(spec["seed"] + 5000)
    rows = []
    for w in wells:
        for k in range(2):
            pos = w["card"][:, 0] + crng.normal(0, 0.001, 200)
            load = w["card"][:, 1] + crng.normal(0, 150.0, 200)
            rows += [[w["well"], k + 1, i, "%.4f" % pos[i], "%.3f" % (load[i] / 1e3)] for i in range(200)]
    wr("cards.csv", ["well", "card", "sample", "position_m", "load_kN"], rows)
    srows = []; trows = []
    for w in wells:
        Ap = rs.area(w["plunger"]); r = w["res"]
        for i in range(w["st"].size):
            sid = "%s-%03d" % (w["well"], i + 1)
            srows.append([sid, w["well"], "%.2f" % w["st"][i], "%.2f" % w["sp"][i]])
            trows.append([sid, "%.4f" % r["stroke"][i], "%.3f" % (Ap * r["h_liq"][i] * w["sp"][i] * 1440.0),
                          "%.3f" % (r["pprl"][i] / 1e3), "%.3f" % (r["mprl"][i] / 1e3)])
    wr("settings.csv", ["setting", "well", "surface_stroke_m", "spm"], srows)
    head = ["setting", "plunger_stroke_m", "liquid_m3_d", "pprl_kN", "mprl_kN"]
    if role == "example":
        wr("expected.csv", head, trows)
    else:
        os.makedirs(os.path.join(base, "truth"), exist_ok=True)
        with open(os.path.join(base, "truth", name + ".csv"), "w", newline="") as f:
            x = csv.writer(f, lineterminator="\n"); x.writerow(head); x.writerows(trows)
    os.makedirs(os.path.join(base, "sealed"), exist_ok=True)
    json.dump({"field": name, "role": role, "damping_per_s": c, "liquid_density_kg_m3": rho_f,
               "wells": [{k: (None if (k == "q_in" and np.isinf(w[k])) else w[k]) for k in
                          ("well", "kind", "L", "plunger", "tubing", "sections", "anchor", "holds", "p_th", "p_i", "unit",
                           "lam", "found_stroke", "found_spm", "q_in", "found_fill", "stretch_frac", "Fo", "found_S")} for w in wells]},
              open(os.path.join(base, "sealed", name + ".json"), "w"), indent=1)
    return name, len(wells), len(srows)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    refine = 2
    for a in sys.argv[1:]:
        if a.startswith("--refine="):
            refine = int(a.split("=")[1])
    for nm in (args or list(FIELDS)):
        print(build(nm, refine=refine), flush=True)
