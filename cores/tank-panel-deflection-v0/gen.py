"""gen.py: builds the nine units of the core from the sealed definition (plate.py).
core/environment/data/examples/<unit>  two units with results (plate walls: deflection under a tenth of the thickness)
core/environment/data/pending/<unit>   one unit without results (plate and sheet walls)
core/hidden/<unit>                     six units with truth.csv (five with sheet walls, one plate only)
"""
import csv, json, os, sys
import numpy as np
from multiprocessing import Pool
from plate import Plate

HERE = os.path.dirname(os.path.abspath(__file__))
N_TRUTH = int(os.environ.get("N_TRUTH", "12"))

# material: (E GPa, Poisson, proof MPa [generator only])
MATERIALS = {
    "S235JR":  (210.0, 0.30, 235.0),
    "S355J2":  (210.0, 0.30, 355.0),
    "1.4301":  (193.0, 0.29, 210.0),
    "1.4462":  (200.0, 0.30, 450.0),
    "EN AW-5083": (71.0, 0.33, 125.0),
    "EN AW-6082": (70.0, 0.33, 250.0),
    "Ti Gr 2": (105.0, 0.34, 275.0),
}
PLATE_T = [6, 8, 10, 12, 15, 20, 25]
SHEET_T = [1.5, 2, 2.5, 3, 4, 5]

# unit: (seed, role, [(kind, material)...])   kind: P plate wall, S sheet wall, M in between
UNITS = {
    "brine_plant":  (11, "example", "PPPPPPPPPP", ["S235JR", "S355J2", "1.4301"]),
    "mill_house":   (12, "example", "PPPPPPPPPPPP", ["S235JR", "1.4301", "EN AW-5083"]),
    "dryer_hall":   (13, "pending", "PPPPPSSSSSMS", ["S235JR", "1.4301", "EN AW-5083", "Ti Gr 2"]),
    "kiln_line":    (21, "hidden", "PPPPSSSSSSMS", ["S235JR", "S355J2", "1.4301", "EN AW-6082"]),
    "press_shop":   (22, "hidden", "PPPPPPSSSSSM", ["S355J2", "1.4462", "EN AW-5083"]),
    "acid_plant":   (23, "hidden", "PPPPPPPPPPP", ["1.4301", "1.4462", "Ti Gr 2"]),
    "filter_house": (24, "hidden", "PPPSSSSSSSMM", ["S235JR", "1.4301", "EN AW-5083", "EN AW-6082"]),
    "paint_line":   (25, "hidden", "PPPPPSSSSSSS", ["S235JR", "EN AW-5083", "Ti Gr 2"]),
    "boiler_annex": (26, "hidden", "PPPPPPPSSSSM", ["S235JR", "S355J2", "1.4301", "1.4462"]),
}
TAG = {"P": "T", "S": "D", "M": "C"}      # tank, duct, casing

_design = {}
def design_curve(r):
    """coarse W(Q), S_e(Q) at nu = 0.3 for sizing the conditions."""
    key = round(r * 4) / 4
    if key not in _design:
        Qs = np.geomspace(0.5, 20000, 26)
        p = Plate(key, 0.30, n=6); out = []
        for Q in Qs:
            p.solve(Q); out.append(p.results())
        o = np.array(out)
        _design[key] = (np.log(Qs), np.log(o[:, 0]), np.log(o[:, 2]))
    return _design[key]

def Q_for_W(r, W):
    lq, lw, ls = design_curve(r)
    return float(np.exp(np.interp(np.log(W), lw, lq)))

def S_at_Q(r, Q):
    lq, lw, ls = design_curve(r)
    return float(np.exp(np.interp(np.log(Q), lq, ls)))

def describe(name):
    seed, role, kinds, mats = UNITS[name]
    rng = np.random.default_rng(seed)
    items, panels, rows = [], [], []
    for k, kind in enumerate(kinds):
        mat = mats[rng.integers(len(mats))]
        E, nu, proof = MATERIALS[mat]
        t = float(rng.choice(PLATE_T if kind == "P" else SHEET_T if kind == "S" else [3, 4, 5, 6]))
        tag = "%s-%d%02d" % (TAG[kind], 1 + k // 5, 1 + 7 * k % 40)
        npan = int(rng.integers(9, 22))
        if kind == "P":
            bs = rng.choice(np.arange(250, 701, 25), size=npan) * (t / 10.0) ** 0.5
        elif kind == "S":
            bs = rng.choice(np.arange(400, 1201, 50), size=npan) * (t / 2.5) ** 0.5
        else:
            bs = rng.choice(np.arange(300, 801, 25), size=npan)
        bs = np.round(bs / 5.0) * 5.0
        rs = rng.choice([1.0, 1.2, 1.25, 1.4, 1.5, 1.6, 1.75, 2.0, 2.2, 2.4, 2.5, 2.8, 3.0], size=npan)
        as_ = np.round(bs * rs / 5.0) * 5.0
        as_ = np.minimum(np.maximum(as_, bs), np.floor(3.0 * bs / 5.0) * 5.0)
        # the item's largest pressure: the most flexible panel reaches Wmax, no panel passes 0.85 proof at its edge
        Wmax = {"P": rng.uniform(0.012, 0.04), "S": rng.uniform(1.5, 4.5), "M": rng.uniform(0.25, 0.9)}[kind]
        pmax = 1e99
        for a, b in zip(as_, bs):
            r = a / b
            q_w = Q_for_W(r, Wmax) * E * 1e3 * (t / b) ** 4          # MPa
            # stress limit by bisection on Q
            lo, hi = 0.5, 20000.0
            for _ in range(50):
                mid = (lo * hi) ** 0.5
                if S_at_Q(r, mid) * E * 1e3 * (t / b) ** 2 > 0.85 * proof: hi = mid
                else: lo = mid
            q_s = lo * E * 1e3 * (t / b) ** 4
            pmax = min(pmax, q_w, q_s)
        pmax_kPa = pmax * 1e3
        ncond = int(rng.integers(8, 15))
        fr = np.sort(np.concatenate([[1.0], rng.uniform(0.08, 0.97, size=ncond - 1)]))
        dec = 2 if pmax_kPa < 20 else 1 if pmax_kPa < 200 else 0
        press = sorted(set(round(float(pmax_kPa * f), dec) for f in fr))
        press = [p for p in press if p > 0]
        items.append(dict(item=tag, material=mat, t_mm=t, conditions=press))
        for j, (a, b) in enumerate(zip(as_, bs)):
            pid = "%s/%02d" % (tag, j + 1)
            panels.append(dict(panel=pid, item=tag, a_mm=float(a), b_mm=float(b), t_mm=t, material=mat))
            for c, p in enumerate(press):
                rows.append(dict(panel=pid, condition="C%02d" % (c + 1), pressure_kPa=p))
    for i, r in enumerate(rows):
        r["row"] = "R%04d" % (i + 1)
    return dict(name=name, role=role, items=items, panels=panels, rows=rows, materials=mats)

def solve_panel(args):
    a, b, t, E, nu, press = args
    r = a / b
    p = Plate(r, nu, n=N_TRUTH)
    out = []
    for q in sorted(press):
        Q = q * 1e-3 * (b / t) ** 4 / (E * 1e3)
        p.solve(Q)
        W, Sc, Se = p.results()
        out.append((q, W, W * t, Se * E * 1e3 * (t / b) ** 2))
    return out

def fmt(x):
    s = "%.5g" % x
    if "e" in s: s = "%.8f" % x
    return s

def write_unit(d, truth):
    role = d["role"]
    base = {"example": "core/environment/data/examples", "pending": "core/environment/data/pending",
            "hidden": "core/hidden"}[role]
    out = os.path.join(HERE, base, d["name"]); os.makedirs(out, exist_ok=True)
    json.dump(dict(unit=d["name"], panels=len(d["panels"]), rows=len(d["rows"])), open(os.path.join(out, "unit.json"), "w"), indent=1)
    with open(os.path.join(out, "materials.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["material", "E_GPa", "poisson"])
        for m in d["materials"]:
            w.writerow([m, MATERIALS[m][0], MATERIALS[m][1]])
    with open(os.path.join(out, "panels.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["panel", "item", "a_mm", "b_mm", "t_mm", "material"])
        for p in d["panels"]:
            w.writerow([p["panel"], p["item"], "%g" % p["a_mm"], "%g" % p["b_mm"], "%g" % p["t_mm"], p["material"]])
    with open(os.path.join(out, "conditions.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["row", "panel", "condition", "pressure_kPa"])
        for r in d["rows"]:
            w.writerow([r["row"], r["panel"], r["condition"], "%g" % r["pressure_kPa"]])
    if truth is None: return
    fn = "expected.csv" if role == "example" else "truth.csv"
    if role == "pending":
        out = os.path.join(HERE, "core/pending_truth"); os.makedirs(out, exist_ok=True); fn = d["name"] + ".csv"
    with open(os.path.join(out, fn), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["row", "deflection_mm", "edge_stress_MPa"] + ([] if role == "example" else ["W"]))
        for r in d["rows"]:
            W, defl, se = truth[(r["panel"], r["pressure_kPa"])]
            w.writerow([r["row"], fmt(defl), fmt(se)] if role == "example" else [r["row"], repr(defl), repr(se), "%.4f" % W])

def build(name):
    d = describe(name)
    pan = {p["panel"]: p for p in d["panels"]}
    press = {}
    for r in d["rows"]:
        press.setdefault(r["panel"], []).append(r["pressure_kPa"])
    jobs = [(pan[k]["a_mm"], pan[k]["b_mm"], pan[k]["t_mm"], MATERIALS[pan[k]["material"]][0],
             MATERIALS[pan[k]["material"]][1], press[k]) for k in press]
    with Pool(int(os.environ.get("NPROC", "2"))) as pool:
        res = pool.map(solve_panel, jobs, chunksize=4)
    truth = {}
    for k, out in zip(press, res):
        for q, W, defl, se in out:
            truth[(k, q)] = (W, defl, se)
    write_unit(d, truth)
    Ws = np.array([truth[(r["panel"], r["pressure_kPa"])][0] for r in d["rows"]])
    Ss = np.array([truth[(r["panel"], r["pressure_kPa"])][2] for r in d["rows"]])
    print("%-13s %-8s panels %3d rows %4d  W %.3f..%.2f  rows W>0.3: %4d  W>1: %4d  stress %.0f..%.0f MPa" % (
        name, d["role"], len(d["panels"]), len(d["rows"]), Ws.min(), Ws.max(), (Ws > 0.3).sum(), (Ws > 1).sum(), Ss.min(), Ss.max()), flush=True)

if __name__ == "__main__":
    for n in (sys.argv[1:] or list(UNITS)):
        build(n)
