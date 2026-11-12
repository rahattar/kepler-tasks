"""Sealed definition of the bare alignment core. Lengths in mm, temperatures in C."""
import math, random

ALPHA = 11.5e-6
TOL = 0.05                 # mm between the centrelines at each hub's reading plane, running
BUDGET = 5
SEED = 4107

# bracket sag of each bar set: half the mandrel bottom reading, positive
SAG = {("A", 1): 0.02, ("A", 2): 0.05, ("A", 3): 0.11,
       ("B", 1): 0.03, ("B", 2): 0.33, ("B", 3): 0.40,       # B2, B3 as they are since the bars were replaced
       ("C", 1): 0.48, ("C", 2): 0.19, ("C", 3): 0.26}
SAG_B_OLD = {2: 0.05, 3: 0.10}                               # as carded in 2025, before the replacement
B_REPLACED = "2026-10-15"
CARDS = [("A", 1, "2025-03-11", 0.02), ("A", 2, "2025-03-11", 0.05), ("A", 3, "2025-03-11", 0.11),
         ("B", 1, "2025-03-12", 0.03), ("B", 2, "2025-03-12", 0.05), ("B", 3, "2025-03-12", 0.10)]

def bar_for(span):
    return 1 if span <= 160 else (2 if span <= 320 else 3)

# running position change, cold to hot: (rise, lateral)
GEAR_OEM = {"GR-800": (0.26, 0.14), "GR-450": (0.15, -0.09)}   # GR-450 as supplied
GEAR_NOW = {"GR-800": (0.26, 0.14), "GR-450": (0.36, -0.21)}   # GR-450 with the re-rated set
TURB_2023 = {"TP-301A": (0.41, 0.12), "TP-301B": (0.55, -0.08), "TP-301C": (0.33, 0.20)}
TURB_NOW = {"TP-301A": (0.58, -0.05), "TP-301B": (0.37, 0.16), "TP-301C": (0.52, 0.31)}

# tag, kind, kit, span, sheet date, fitter
ROWS = [
 ("K-201A", "comp", "A", 300, "2026-10-13", "RK"), ("K-201B", "comp", "A", 345, "2026-10-14", "RK"),
 ("K-201C", "comp", "A", 285, "2026-10-27", "RK"),
 ("GF-401", "gear", "B", 240, "2026-10-20", "TS"), ("GF-402", "gear", "A", 250, "2026-10-21", "JM"),
 ("GF-403", "gear", "A", 245, "2026-10-28", "RK"), ("GF-404", "gear", "C", 235, "2026-10-15", "DW"),
 ("TP-301A", "turb", "B", 420, "2026-10-29", "DW"), ("TP-301B", "turb", "C", 395, "2026-10-28", "JM"),
 ("TP-301C", "turb", "A", 410, "2026-11-03", "TS"),
 ("P-121A", "pump", "B", 210, "2026-10-19", "TS"), ("P-121B", "pump", "B", 210, "2026-10-19", "TS"),
 ("P-126", "pump", "B", 275, "2026-10-27", "DW"), ("FN-512", "fan", "B", 305, "2026-11-02", "DW"),
 ("P-131", "pump", "B", 350, "2026-10-22", "TS"), ("P-140A", "pump", "B", 365, "2026-10-30", "DW"),
 ("P-140B", "pump", "B", 365, "2026-10-30", "DW"),
 ("P-102A", "pump", "C", 125, "2026-10-13", "DW"), ("P-102B", "pump", "C", 125, "2026-10-13", "DW"),
 ("P-109", "pump", "C", 150, "2026-10-29", "JM"), ("P-117", "pump", "C", 140, "2026-11-04", "JM"),
 ("P-133", "pump", "C", 340, "2026-10-16", "DW"), ("FN-520", "fan", "C", 380, "2026-10-30", "JM"),
 ("P-141", "pump", "C", 355, "2026-11-03", "JM"),
 ("P-114", "pump", "C", 230, "2026-10-20", "DW"), ("P-118A", "pump", "C", 265, "2026-10-21", "DW"),
 ("P-118B", "pump", "C", 265, "2026-10-21", "DW"), ("P-125", "pump", "C", 290, "2026-11-02", "JM"),
 ("P-101A", "pump", "A", 120, "2026-10-12", "RK"), ("P-101B", "pump", "A", 120, "2026-10-12", "RK"),
 ("P-105", "pump", "A", 145, "2026-10-20", "JM"),
 ("P-111", "pump", "A", 225, "2026-10-29", "RK"), ("P-123", "pump", "B", 255, "2026-10-13", "JM"),
 ("FN-530", "fan", "A", 400, "2026-11-04", "TS"),
 ("P-106", "pump", "B", 135, "2026-10-14", "JM"), ("P-108", "pump", "B", 150, "2026-10-21", "TS"),
]
REPEAT = ("P-114", "A", "2026-10-22", "JM")        # second sheet on the same train, machine not moved between
CRIB = [("A", "RK", "2026-10-12", "2026-10-16"), ("A", "JM", "2026-10-19", "2026-10-23"),
        ("A", "RK", "2026-10-26", "2026-10-30"), ("A", "TS", "2026-11-02", "2026-11-05"),
        ("B", "JM", "2026-10-12", "2026-10-14"), ("B", "TS", "2026-10-16", "2026-10-23"),
        ("B", "DW", "2026-10-26", "2026-11-03"),
        ("C", "DW", "2026-10-12", "2026-10-23"), ("C", "JM", "2026-10-26", "2026-11-05")]

def kit_for(fitter, date):
    hit = [k for k, f, a, b in CRIB if f == fitter and a <= date <= b]
    assert len(hit) == 1, (fitter, date, hit)
    return hit[0]

def sag_of(kit, bar, date):
    if kit == "B" and bar in (2, 3) and date < B_REPLACED:
        return SAG_B_OLD[bar]
    return SAG[(kit, bar)]

def build():
    rng = random.Random(SEED)
    trains = {}
    for tag, kind, kit, span, date, fitter in ROWS:
        assert kit_for(fitter, date) == kit, tag
        t = dict(tag=tag, kind=kind, kit=kit, span=float(span), date=date, fitter=fitter)
        t["a"] = float(rng.randrange(150, 401, 5)); t["b"] = float(rng.randrange(520, 1201, 10))
        t["h_mov"] = float(rng.randrange(280, 801, 10)); t["h_stat"] = float(rng.randrange(280, 801, 10))
        t["amb"] = rng.choice([18.0, 19.0, 20.0, 21.0, 22.0, 23.0])
        t["t_mov"] = float(rng.randrange(52, 74)); t["t_stat"] = float(rng.randrange(38, 165))
        t["speed"] = rng.choice([1480, 1780, 2960, 3560])
        if kind == "turb":
            t["t_mov"] = float(rng.randrange(84, 98)); t["speed"] = rng.choice([4200, 4650])
        if kind in ("gear", "comp"):
            t["t_stat"] = float(rng.randrange(62, 80))
            t["model"] = "GR-800" if kind == "comp" else "GR-450"
        t["ys"], t["ym"], t["zs"], t["zm"] = [round(rng.uniform(-0.60, 0.60), 3) for _ in range(4)]
        t["crit"] = "A" if kind in ("comp",) else ("B" if kind in ("turb", "gear") or rng.random() < 0.25 else "C")
        trains[tag] = t
    return trains

def growth(h, t, amb):
    return ALPHA * h * (t - amb)

def running_change(t):
    """(stationary rise, stationary lateral, movable rise, movable lateral), cold to hot."""
    if t["kind"] in ("gear", "comp"):
        sr, sl = GEAR_NOW[t["model"]]
    else:
        sr, sl = growth(t["h_stat"], t["t_stat"], t["amb"]), 0.0
    if t["kind"] == "turb":
        mr, ml = TURB_NOW[t["tag"]]
    else:
        mr, ml = growth(t["h_mov"], t["t_mov"], t["amb"]), 0.0
    return sr, sl, mr, ml

def true_moves(t):
    sr, sl, mr, ml = running_change(t)
    cv, ch = mr - sr, ml - sl
    D, a, b = t["span"], t["a"], t["b"]
    def at(x, s, m): return s + (m - s) * x / D
    xf, xr = D + a, D + a + b
    return (-(at(xf, t["ys"], t["ym"]) + cv), -(at(xr, t["ys"], t["ym"]) + cv),
            -(at(xf, t["zs"], t["zm"]) + ch), -(at(xr, t["zs"], t["zm"]) + ch))

def residual(t, moves):
    """Running position of the movable centreline relative to the stationary one after the moves:
    (y at the stationary hub's plane, y at the movable hub's, z at the stationary hub's, z at the movable hub's)."""
    vf, vr, hf, hr = moves
    sr, sl, mr, ml = running_change(t)
    D, a, b = t["span"], t["a"], t["b"]
    xf = D + a
    out = []
    for s, m, c, mf, mrr in ((t["ys"], t["ym"], mr - sr, vf, vr), (t["zs"], t["zm"], ml - sl, hf, hr)):
        def rho(x): return s + (m - s) * x / D + c + mf + (mrr - mf) * (x - xf) / b
        out += [rho(0.0), rho(D)]
    return out

def passes(t, moves):
    return max(abs(v) for v in residual(t, moves)) <= TOL

def readings(t, kit, date, rng):
    """Dial sheet: (T, R, B, L) for the indicator on the stationary shaft reading the movable hub (SM) and for the
    one on the movable shaft reading the stationary hub (MS). Zeroed at top, stem in positive, positions as seen
    from the movable machine looking at the stationary one."""
    s = sag_of(kit, bar_for(t["span"]), date)
    n = lambda: rng.gauss(0.0, 0.002)
    ys, ym, zs, zm = t["ys"], t["ym"], t["zs"], t["zm"]
    sm = (0.0, -ym + zm - s + n(), -2 * ym - 2 * s + n(), -ym - zm - s + n())
    ms = (0.0, ys - zs - s + n(), 2 * ys - 2 * s + n(), ys + zs - s + n())
    return [round(v, 2) for v in sm], [round(v, 2) for v in ms]
