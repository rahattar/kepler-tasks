"""Sealed definition of Unit 3's coupled trains at the 2026 turnaround. Lengths in mm, temperatures in C.

Everything a submission is judged against comes from here: the as-found position of every train, how far each
machine's shaft moves between cold and running as the unit now runs, and the acceptance of AP-12 section 7.
The seed drives the scatter of the records and the trains' dimensions; the physics is in the constants.
"""
import random

ALPHA = 11.5e-6
TOL = 0.05
BUDGET = 6
T_REF = 25.0               # the ambient the support temperatures are quoted at

SAG = {("A", 1): 0.02, ("A", 2): 0.05, ("A", 3): 0.11, ("B", 1): 0.03, ("B", 2): 0.07, ("B", 3): 0.14,
       ("C", 1): 0.04, ("C", 2): 0.09, ("C", 3): 0.17}
CARD_DATE = {"A": "2025-03-11", "B": "2025-03-12", "C": "2026-08-25"}
def bar_for(span): return 1 if span <= 160 else (2 if span <= 320 else 3)

GEAR = {"GR-800": (0.26, 0.14)}
TURB_2023 = {"TP-301A": (0.41, 0.12), "TP-301B": (0.55, -0.08)}
TURB_NOW = {"TP-301A": (0.58, -0.05), "TP-301B": (0.37, 0.16)}

# pump constructions: how far the support follows the pumped temperature above 25 C
K_2019 = {"F": 0.62, "Fc": 0.38, "Fd": 0.47, "C": 0.30, "Cc": 0.16, "W": 0.62}
K_NOW = {("F", "lag"): 0.72, ("Fc", "dry"): 0.80, ("Fd", "dry"): 0.66, ("Cc", "dry"): 0.43}
MODELS = {"HS-200": "F", "HS-300": "F", "HSC-250": "Fc", "HSC-400": "Fd", "CL-150": "C", "CL-300": "C",
          "CLC-200": "Cc", "CLC-350": "Cc", "WP-100": "W"}
BUILD = {"F": ("foot", "plain"), "Fc": ("foot", "water-cooled"), "Fd": ("foot", "water-cooled"), "C": ("centreline", "plain"),
         "Cc": ("centreline", "water-cooled"), "W": ("foot", "plain")}

# tag, kind, pump model, change, kit, span, date, fitter, pumped temperature 2019, now
ROWS = [
 ("K-201A", "comp", None, None, "A", 300, "2026-10-13", "RK", None, None),
 ("K-201B", "comp", None, None, "A", 345, "2026-10-14", "RK", None, None),
 ("K-201C", "comp", None, None, "A", 285, "2026-10-27", "RK", None, None),
 ("TP-301A", "turb", "HS-300", None, "B", 420, "2026-10-29", "DW", 142, 142),
 ("TP-301B", "turb", "HS-300", None, "C", 395, "2026-10-28", "JM", 142, 142),
 ("P-301A", "pump", "HS-200", "lag", "B", 210, "2026-10-19", "TS", 305, 342), ("P-301B", "pump", "HS-200", "lag", "B", 210, "2026-10-19", "TS", 305, 342),
 ("P-304", "pump", "HS-300", "lag", "C", 275, "2026-10-21", "DW", 288, 331), ("P-310A", "pump", "HS-300", "lag", "A", 305, "2026-10-28", "RK", 322, 356),
 ("P-310B", "pump", "HS-300", "lag", "A", 305, "2026-10-28", "RK", 322, 356),
 ("P-302", "pump", "HS-200", None, "A", 225, "2026-10-29", "RK", 296, 338), ("P-306A", "pump", "HS-300", None, "B", 350, "2026-10-22", "TS", 310, 268),
 ("P-306B", "pump", "HS-300", None, "B", 350, "2026-10-22", "TS", 310, 268), ("P-312", "pump", "HS-200", None, "C", 230, "2026-10-20", "DW", 285, 330),
 ("P-320A", "pump", "HSC-250", "dry", "C", 265, "2026-10-21", "DW", 318, 349), ("P-320B", "pump", "HSC-250", "dry", "C", 265, "2026-10-21", "DW", 318, 349),
 ("P-322", "pump", "HSC-400", "dry", "B", 365, "2026-10-30", "DW", 334, 362), ("P-325A", "pump", "HSC-400", "dry", "A", 400, "2026-11-04", "TS", 300, 341),
 ("P-325B", "pump", "HSC-400", "dry", "A", 400, "2026-11-04", "TS", 300, 341),
 ("P-330A", "pump", "CL-300", None, "C", 340, "2026-10-16", "DW", 325, 352), ("P-330B", "pump", "CL-300", None, "C", 340, "2026-10-16", "DW", 325, 352),
 ("P-333", "pump", "CL-150", None, "A", 145, "2026-10-20", "JM", 298, 344), ("P-336", "pump", "CL-300", None, "B", 305, "2026-11-02", "DW", 312, 350),
 ("P-331", "pump", "CL-150", None, "B", 150, "2026-10-21", "TS", 330, 288), ("P-338A", "pump", "CL-300", None, "C", 355, "2026-11-03", "JM", 306, 348),
 ("P-338B", "pump", "CL-300", None, "C", 355, "2026-11-03", "JM", 306, 348),
 ("P-340A", "pump", "CLC-350", "dry", "C", 380, "2026-10-30", "JM", 340, 365), ("P-340B", "pump", "CLC-350", "dry", "C", 380, "2026-10-30", "JM", 340, 365),
 ("P-342", "pump", "CLC-200", "dry", "B", 255, "2026-10-13", "JM", 315, 351), ("P-345A", "pump", "CLC-200", "dry", "A", 250, "2026-10-21", "JM", 328, 357),
 ("P-345B", "pump", "CLC-200", "dry", "A", 245, "2026-10-28", "RK", 328, 357),
 ("P-360A", "pump", "WP-100", None, "A", 120, "2026-10-12", "RK", 32, 32), ("P-360B", "pump", "WP-100", None, "A", 120, "2026-10-12", "RK", 32, 32),
 ("P-365", "pump", "WP-100", None, "B", 135, "2026-10-14", "JM", 58, 58),
 ("FN-370", "fan", None, None, "C", 125, "2026-10-13", "DW", None, None), ("FN-371", "fan", None, None, "C", 150, "2026-10-29", "JM", None, None),
]
CRIB = [("A", "RK", "2026-10-12", "2026-10-16"), ("A", "JM", "2026-10-19", "2026-10-23"),
        ("A", "RK", "2026-10-26", "2026-10-30"), ("A", "TS", "2026-11-02", "2026-11-05"),
        ("B", "JM", "2026-10-12", "2026-10-14"), ("B", "TS", "2026-10-16", "2026-10-23"),
        ("B", "DW", "2026-10-26", "2026-11-03"),
        ("C", "DW", "2026-10-12", "2026-10-23"), ("C", "JM", "2026-10-26", "2026-11-05")]

def kit_for(fitter, date):
    hit = [k for k, f, a, b in CRIB if f == fitter and a <= date <= b]
    assert len(hit) == 1, (fitter, date, hit)
    return hit[0]

def build(seed):
    rng = random.Random(seed)
    trains = {}
    for tag, kind, model, change, kit, span, date, fitter, tp19, tpnow in ROWS:
        assert kit_for(fitter, date) == kit, tag
        t = dict(tag=tag, kind=kind, model=model, change=change, kit=kit, span=float(span), date=date, fitter=fitter)
        t["a"] = float(rng.randrange(150, 401, 5)); t["b"] = float(rng.randrange(520, 1201, 10))
        t["h_mov"] = float(rng.randrange(300, 701, 10))
        t["h_stat"] = float(rng.randrange(620, 901, 10)) if (model and model != "WP-100") else float(rng.randrange(300, 601, 10))
        t["amb"] = rng.choice([18.0, 19.0, 20.0, 21.0, 22.0, 23.0])
        t["t_mov"] = float(rng.randrange(52, 74)) if kind != "turb" else float(rng.randrange(84, 98))
        t["speed"] = rng.choice([1480, 1780, 2960, 3560]) if kind != "turb" else 4650
        t["tp19"], t["tpnow"] = tp19, tpnow
        if kind == "comp":
            t["gear"] = "GR-800"; t["t_stat19"] = t["t_stat"] = float(rng.randrange(62, 80))
        elif kind == "fan":
            t["t_stat19"] = t["t_stat"] = float(rng.randrange(34, 46))
        else:
            c = MODELS[model]; t["cons"] = c
            k19 = K_2019[c]; know = K_NOW.get((c, change), k19)
            t["t_stat19"] = float(round(T_REF + k19 * (tp19 - T_REF) + rng.uniform(-1.0, 1.0)))
            t["t_stat"] = T_REF + know * (tpnow - T_REF)
        t["ys"], t["ym"], t["zs"], t["zm"] = [round(rng.uniform(-0.60, 0.60), 3) for _ in range(4)]
        t["crit"] = "A" if kind == "comp" else ("B" if kind == "turb" or rng.random() < 0.25 else "C")
        trains[tag] = t
    return trains

def growth(h, t, amb): return ALPHA * h * (t - amb)

def running_change(t):
    if t["kind"] == "comp": sr, sl = GEAR[t["gear"]]
    else: sr, sl = growth(t["h_stat"], t["t_stat"], t["amb"]), 0.0
    if t["kind"] == "turb": mr, ml = TURB_NOW[t["tag"]]
    else: mr, ml = growth(t["h_mov"], t["t_mov"], t["amb"]), 0.0
    return sr, sl, mr, ml

def true_moves(t):
    sr, sl, mr, ml = running_change(t); cv, ch = mr - sr, ml - sl
    D, a, b = t["span"], t["a"], t["b"]
    at = lambda x, s, m: s + (m - s) * x / D
    xf, xr = D + a, D + a + b
    return (-(at(xf, t["ys"], t["ym"]) + cv), -(at(xr, t["ys"], t["ym"]) + cv),
            -(at(xf, t["zs"], t["zm"]) + ch), -(at(xr, t["zs"], t["zm"]) + ch))

def residual(t, moves):
    vf, vr, hf, hr = moves
    sr, sl, mr, ml = running_change(t)
    D, a, b = t["span"], t["a"], t["b"]; xf = D + a
    out = []
    for s, m, c, mf, mrr in ((t["ys"], t["ym"], mr - sr, vf, vr), (t["zs"], t["zm"], ml - sl, hf, hr)):
        rho = lambda x: s + (m - s) * x / D + c + mf + (mrr - mf) * (x - xf) / b
        out += [rho(0.0), rho(D)]
    return out

def passes(t, moves): return max(abs(v) for v in residual(t, moves)) <= TOL

def readings(t, rng):
    s = SAG[(t["kit"], bar_for(t["span"]))]
    n = lambda: rng.gauss(0.0, 0.002)
    ys, ym, zs, zm = t["ys"], t["ym"], t["zs"], t["zm"]
    sm = (0.0, -ym + zm - s + n(), -2 * ym - 2 * s + n(), -ym - zm - s + n())
    ms = (0.0, ys - zs - s + n(), 2 * ys - 2 * s + n(), ys + zs - s + n())
    return [round(v, 2) for v in sm], [round(v, 2) for v in ms]


def laser_report(t):
    """What a laser visit to one train gives: the cold position at the two reading planes and both machines'
    movement from cold to running. The laser has no bracket, so no sag, and the figures are to a micrometre."""
    sr, sl, mr, ml = running_change(t)
    return [("y_stationary_plane", t["ys"]), ("y_movable_plane", t["ym"]), ("z_stationary_plane", t["zs"]),
            ("z_movable_plane", t["zm"]), ("stationary_rise", sr), ("stationary_lateral", sl),
            ("movable_rise", mr), ("movable_lateral", ml)]
