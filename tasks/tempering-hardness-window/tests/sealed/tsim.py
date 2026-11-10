"""Sealed definition: hardness of quenched-and-tempered alloy steel parts (truth for the laboratory and the verifier).

Hardness at a location of a part = f (Hm + fresh) + (1 - f) Hb, where
  f      martensite fraction after the oil quench at the location's equivalent Jominy distance (shop table in HT-4),
         f = 1 / (1 + (J / J50)^n) by grade;
  Hm     tempered martensite: from the as-quenched hardness 35 + 50 C (C in %) toward a floor of 18 HRC with the grade's
         tempering resistance, shifted by the heat's own resistance (TSH), plus the heat's secondary-hardening hump
         A exp(-((T - Tc) / W)^2) (HUMP);
  Hb     tempered bainite, by grade;
  fresh  G52 only, after a single temper: retained austenite that transforms to fresh, untempered martensite on
         cooling from a temper above about 520 C adds RA / (1 + exp(-(T - 520) / 10)) HRC; a second temper tempers it,
         so after a double temper it is zero.
Time at temperature enters through the Hollomon-Jaffe parameter T_K (20 + log10 t_h), referred to one 2 h temper; a
double temper counts as twice the time (that equivalence holds for the tempering of martensite, not for the fresh
martensite that a single temper leaves behind).

Production (HT-4): soak 1 h per 25 mm of ruling section, at least 2 h; G52 double tempered; lowest permitted
temperatures 400 C (G41, G43), 500 C (G32) and 540 C (G52). A batch is right when its setpoint is at or above its
grade's minimum and the hardness at the drawing's location is within the drawing's range.

The laboratory hardens a test piece of the heat as production does and tempers it once (or twice) for 2 h; its reading
is the mean of five indentations, with a scatter of NOISE HRC.
"""
import numpy as np

GRADES = {  # tempering resistance (T50 C at 2 h, width C), early softening, bainite hardness, hardenability J50 mm
    "G41": dict(T50=530.0, w=70.0, e1=0.10, HB=32.0, J50=22.0, n=3.0, desc="1 % Cr - 0.2 % Mo"),
    "G43": dict(T50=540.0, w=70.0, e1=0.10, HB=36.0, J50=55.0, n=3.0, desc="1.8 % Ni - 0.8 % Cr - 0.25 % Mo"),
    "G32": dict(T50=590.0, w=55.0, e1=0.08, HB=38.0, J50=40.0, n=3.0, desc="3 % Cr - 0.9 % Mo - V"),
    "G52": dict(T50=680.0, w=60.0, e1=0.06, HB=42.0, J50=110.0, n=3.0, desc="5 % Cr - 1.3 % Mo - 1 % V"),
}
# heats on the mill certificates: grade, C, Mn, Si, Cr, Mo, V, Ni (%)
HEATS = {
    "41-7731": ("G41", 0.41, 0.85, 0.25, 1.02, 0.21, 0.00, 0.10),
    "41-7864": ("G41", 0.40, 0.88, 0.27, 0.98, 0.20, 0.08, 0.12),
    "43-2210": ("G43", 0.39, 0.70, 0.25, 0.82, 0.26, 0.00, 1.78),
    "32-0458": ("G32", 0.32, 0.55, 0.28, 3.05, 0.92, 0.26, 0.20),
    "52-1250": ("G52", 0.39, 0.40, 0.98, 5.05, 1.38, 1.00, 0.12),
    "52-1312": ("G52", 0.38, 0.37, 1.05, 5.20, 1.50, 1.04, 0.18),
    "43-2288": ("G43", 0.38, 0.72, 0.24, 0.85, 0.48, 0.00, 1.82),
    "52-1377": ("G52", 0.42, 0.39, 1.00, 5.25, 1.58, 1.02, 0.16),
}
# the steel supplier's typical heat of each grade (its published curves); "52-typ" is not a heat on file
SUPPLIER_TYPICAL = {"G41": "41-7731", "G43": "43-2210", "G32": "32-0458", "G52": "52-typ"}
TYPICAL_HEATS = {"52-typ": ("G52", 0.39, 0.40, 0.98, 5.05, 1.45, 1.06, 0.12)}
# secondary hardening: amplitude HRC, centre C, width C (2 h equivalent temperature)
HUMP = {"41-7731": (0.0, 520.0, 34.0), "41-7864": (4.5, 565.0, 40.0), "43-2210": (0.0, 520.0, 34.0),
        "32-0458": (4.0, 530.0, 40.0), "52-1250": (4.0, 535.0, 60.0), "52-1312": (4.0, 545.0, 60.0),
        "43-2288": (3.0, 545.0, 40.0), "52-1377": (8.5, 575.0, 65.0), "52-typ": (6.0, 545.0, 60.0)}
RA = {"52-1250": 2.6, "52-1312": 3.0, "52-1377": 3.4, "52-typ": 2.6}     # fresh martensite after a single temper, HRC
TSH = {"52-1250": -40.0, "52-1312": -18.0, "52-1377": 4.0}               # heat's own tempering resistance shift, C
H_FLOOR = 18.0
# HT-4 shop table: equivalent Jominy distance (mm) of oil-quenched rounds by diameter (mm), surface and half-radius
JTAB_D = [25, 50, 75, 100, 150, 200, 250, 300]
JTAB = {"surface": [1.5, 3.0, 4.5, 6.0, 8.5, 11.0, 13.0, 15.0],
        "half-radius": [5.0, 10.0, 14.0, 18.0, 25.0, 32.0, 38.0, 44.0]}
JDIST = [1.5, 3, 5, 7, 9, 11, 13, 15, 20, 25, 30, 35, 40, 50]          # Jominy distances on the certificates, mm

# production batches: part, heat (as now, after the production log), ruling section diameter mm, location, range HRC
BATCHES = {
    "B01": ("drive shaft", "41-7731", 50.0, "half-radius", (32.0, 36.0)),
    "B02": ("crane wheel axle", "41-7864", 150.0, "half-radius", (28.0, 32.0)),
    "B03": ("gear blank", "43-2210", 200.0, "half-radius", (30.0, 34.0)),
    "B04": ("coupling hub", "43-2210", 75.0, "surface", (38.0, 42.0)),
    "B05": ("extruder screw", "32-0458", 100.0, "half-radius", (36.0, 40.0)),
    "B06": ("forging die insert", "52-1312", 200.0, "half-radius", (42.0, 46.0)),
    "B07": ("die-casting die block", "52-1250", 300.0, "half-radius", (38.0, 42.0)),
    "B08": ("hot shear blade", "52-1312", 150.0, "surface", (44.0, 48.0)),
    "B09": ("pinion", "41-7864", 25.0, "surface", (31.0, 35.0)),
    "B10": ("nitriding core shaft", "32-0458", 50.0, "surface", (40.0, 44.0)),
    "B11": ("punch holder", "52-1250", 100.0, "surface", (40.0, 44.0)),
    "B12": ("crane hook shank", "43-2288", 120.0, "half-radius", (33.0, 37.0)),
    "B13": ("trim die steel", "52-1377", 60.0, "surface", (50.0, 55.0)),
}
TMIN = {"G41": 400, "G43": 400, "G32": 500, "G52": 540}
NTEMPER = {"G41": 1, "G43": 1, "G32": 1, "G52": 2}
BUDGET = 11          # laboratory tempers; a double-tempered test uses 2
NOISE = 0.4          # HRC, scatter of a reading (mean of five indentations)
LAB_T = (400, 700)
LAB_D = (25, 300)


def _heat(h):
    return HEATS[h] if h in HEATS else TYPICAL_HEATS[h]


def hm(C):
    return 35.0 + 50.0 * C


def jeq(D, loc):
    return float(np.interp(D, JTAB_D, JTAB[loc]))


def fmart(heat, J):
    g = GRADES[_heat(heat)[0]]
    return 1.0 / (1.0 + (J / g["J50"]) ** g["n"])


def jominy(heat, J):
    g = GRADES[_heat(heat)[0]]
    f = fmart(heat, J)
    return f * hm(_heat(heat)[1]) + (1 - f) * g["HB"]


def t_equiv(T, hours, n=1):
    """temperature (C) of one 2 h temper with the same Hollomon-Jaffe parameter as n tempers of `hours` h at T"""
    TK = T + 273.15
    return TK * (20.0 + np.log10(hours * n)) / (20.0 + np.log10(2.0)) - 273.15


def tempered(heat, T, D=25.0, loc="half-radius", hours=2.0, n=1):
    """HRC at the location of a D mm round of the heat after n tempers of `hours` h at T C"""
    Tset = T
    T = t_equiv(T, hours, n)
    gname, C = _heat(heat)[0], _heat(heat)[1]
    g = GRADES[gname]
    f = fmart(heat, jeq(D, loc))
    Tm = T - TSH.get(heat, 0.0)
    R = (1 - g["e1"] * max(Tm - 150.0, 0.0) / 400.0) / (1 + np.exp((Tm - g["T50"]) / g["w"]))
    R0 = 1 / (1 + np.exp((150.0 - g["T50"]) / g["w"]))
    A, Tc, Wd = HUMP[heat]
    Hm = H_FLOOR + (hm(C) - H_FLOOR) * R / R0 + A * np.exp(-((T - Tc) / Wd) ** 2)
    Rb = 1 / (1 + np.exp((T - (g["T50"] + 30.0)) / (g["w"] * 1.2)))
    Rb0 = 1 / (1 + np.exp((150.0 - (g["T50"] + 30.0)) / (g["w"] * 1.2)))
    Hb = H_FLOOR + (g["HB"] - H_FLOOR) * Rb / Rb0
    fresh = RA.get(heat, 0.0) / (1 + np.exp(-(Tset - 520.0) / 10.0)) if n == 1 else 0.0
    return float(f * (Hm + fresh) + (1 - f) * Hb)


def supplier_curve(grade, T):
    """the supplier's typical curve: one 2 h temper of a 25 mm round, hardness at half-radius"""
    return tempered(SUPPLIER_TYPICAL[grade], T)


def soak_hours(D):
    return max(2.0, D / 25.0)


def batch_hardness(b, T, heat=None):
    part, h, D, loc, w = BATCHES[b]
    h = heat or h
    return tempered(h, T, D, loc, soak_hours(D), NTEMPER[HEATS[h][0]])


def batch_ok(b, T):
    part, heat, D, loc, (lo, hi) = BATCHES[b]
    if T < TMIN[HEATS[heat][0]]:
        return False, batch_hardness(b, T)
    h = batch_hardness(b, T)
    return lo <= h <= hi, h


def window(b):
    """whole-degree setpoints (TMIN to 700 C) that put the batch in its range"""
    part, heat, D, loc, (lo, hi) = BATCHES[b]
    return [T for T in range(TMIN[HEATS[heat][0]], 701) if lo <= batch_hardness(b, T) <= hi]


def lab_temper(heat, T, rng, D=25.0, loc="half-radius", n=1):
    """one laboratory reading: a D mm test piece of the heat, hardened as production, tempered n times 2 h at T"""
    return round(tempered(heat, T, D, loc, 2.0, n) + rng.normal(0, NOISE), 1)
