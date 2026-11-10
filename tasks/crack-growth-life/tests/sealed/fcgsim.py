"""Sealed definition of crack-growth-life: the true crack growth behaviour, components and loading.

The verifier (tests/grade_intervals.py) takes each crack's true remaining life from here, and the laboratory
(/opt/lab/fcgr.py) draws its test data from here. authoring/provenance/gen.py writes the agent's documents from it.

Cracks: long (2D) cracks at the toes of transverse non-load-carrying fillet-welded attachments, growing through the
chord flange thickness T, under the nominal flange stress S:
    K = Mk(a/T, L/T) Y(a/T) S sqrt(pi a)
  Y   edge crack in a plate under tension (Tada), as in the handbook.
  Mk  weld toe magnification factor for 2D flaws at transverse attachments (PD 6493:1991, BS 7910, IIW
      recommendations), L = attachment thickness + 2 fillet legs (toe to toe), held at its L/T = 2 value beyond
      L/T = 2, and never below 1.
Residual stress at the weld toe (BS 7910): as welded = yield of the flange heat; furnace PWHT = 0.2 yield;
vibratory stress relief is not credited; an attachment welded on site after the member's PWHT is as welded.
Stress cycles rise from the dead-load stress, so each rainflow bin has R = (smin + sres) / (smin + sres + ds), <= 0.95.
Growth (m/cycle, MPa sqrt(m)):
    da/dN = C (U(R) dK)^M [1 - dKth(R)/dK]^P   for dK > dKth(R)
  U(R)    = U0 + (1 - U0) R / RCL below RCL, 1 above              (crack closure in the Paris regime, linear in R as
                                                                  in Elber's form; this steel is closure-free from
                                                                  R = RCL = 0.40, below BS 7910's R = 0.5 split)
  dKth(R) = max(5.38 - 6.77 R, DKTH_EFF)                          (BS 7910's recommended threshold line at low R,
                                                                  levelling off at this steel's closure-free threshold
                                                                  DKTH_EFF = 2.4 rather than BS 7910's floor of 2.0)
  Heats: each heat's plate grows HEAT_RATE times as fast as heat H1's at the same U dK, with the same closure and
  threshold: H2 (S355J2, the same grade as H1) 1.25, the S460NL heats H3 and H4 1.35. Heat-to-heat and grade-to-grade
  differences of this size are common between steels and lie inside the scatter that BS 7910's single upper-bound
  law for ferritic steels covers.
Critical depth: Kmax from the dead-load stress plus the largest range (primary stresses, with Mk) reaches the heat's
Kmat, or half the flange thickness, whichever comes first.
Loading from now on: the survey's counts per operating day (unloader 1 operated 28 of the survey's 35 days), with
unloader 2's live-load ranges raised by LOAD_CHANGE for its heavier grab and its grab cycles reduced by CYCLE_CHANGE,
since the berth conveyor fixes the throughput (cycles go with 1 / payload). A month of operation is a twelfth of an
operating year of 300 days.
"""
import numpy as np

C, M, P = 8.0e-12, 3.10, 0.5          # closure-free growth, below the BS 7910 mean + 2 SD law (1.65e-11 dK^3)
U0, RCL = 0.65, 0.40                    # Paris-regime closure: U = U0 + (1 - U0) R / RCL below RCL, 1 above
DKTH_EFF = 2.4                          # closure-free threshold of this steel (asymptote of the growth law)
BS_TH = (5.38, 6.77)                    # BS 7910 recommended threshold line 5.38 - 6.77 R (MPa sqrt(m)), R < 0.5
NOISE = 0.08                            # scatter of a laboratory growth-rate reading (log-normal sd)
LAB_HEAT = "H1"                         # the laboratory's specimens are cut from retained plate of this heat


def U(R, U0=U0, RCL=RCL):
    R = np.asarray(R, float)
    return np.where(R < RCL, U0 + (1 - U0) * R / RCL, 1.0)


def dkth(R):
    R = np.asarray(R, float)
    return np.maximum(BS_TH[0] - BS_TH[1] * R, DKTH_EFF)


def make_law(C=C, M=M, P=P, Uf=None, th=None):
    Uf = Uf or U
    th = th or dkth

    def law(dK, R):
        dK = np.asarray(dK, float); R = np.asarray(R, float)
        k = th(R)
        out = C * (Uf(R) * dK) ** M * np.clip(1 - k / np.maximum(dK, 1e-9), 0, None) ** P
        return np.where(dK > k, out, 0.0)
    return law


rate = make_law()
HEAT_RATE = {"H1": 1.0, "H2": 1.25, "H3": 1.35, "H4": 1.35}


def true_rate(heat):
    """the growth law of a heat's plate: heat H1's law above, scaled by the heat's HEAT_RATE"""
    f = HEAT_RATE[heat]
    return lambda dK, R: f * rate(dK, R)


def Y(aT):
    aT = np.asarray(aT, float)
    return 1.12 - 0.231 * aT + 10.55 * aT ** 2 - 21.72 * aT ** 3 + 30.39 * aT ** 4


def Mk(aT, LT):
    """BS 7910 / PD 6493 2D weld toe magnification factor, transverse non-load-carrying attachment; >= 1"""
    aT = np.asarray(aT, float)
    if LT <= 2.0:
        t = 0.05 * LT ** 0.55
        v = np.where(aT <= t, 0.51 * LT ** 0.27 * aT ** -0.31, 0.83 * aT ** (-0.15 * LT ** 0.46))
    else:
        v = np.where(aT <= 0.073, 0.615 * aT ** -0.31, 0.83 * aT ** -0.2)
    return np.maximum(v, 1.0)


FRAC = np.array([1.00, 0.85, 0.70, 0.56, 0.44, 0.33, 0.24, 0.16])
SPECTRA = {"A": np.array([2e-4, 1e-3, 4e-3, 1.4e-2, 4.5e-2, 0.12, 0.28, 0.5357]),     # hoisting, many small cycles
           "B": np.array([1e-3, 5e-3, 2e-2, 6e-2, 0.12, 0.20, 0.27, 0.324]),          # heavier
           "C": np.array([5e-5, 2e-4, 1e-3, 4e-3, 1.5e-2, 6e-2, 0.25, 0.6698])}       # vibration dominated
SRES = {"AW": 1.0, "PWHT": 0.2, "VSR": 1.0}

HEATS = {"H1": ("S355J2", 372.0, 125.0), "H2": ("S355J2", 395.0, 110.0),
         "H3": ("S460NL", 478.0, 150.0), "H4": ("S460NL", 501.0, 140.0)}
HEAT_OF = {"C01": "H1", "C02": "H1", "C03": "H2", "C04": "H3", "C05": "H1", "C06": "H2", "C07": "H3", "C08": "H2",
           "C09": "H2", "C10": "H4", "C11": "H1", "C12": "H1", "C13": "H4", "C14": "H2", "C15": "H2", "C16": "H1",
           "E01": "H1", "E02": "H2"}
# id, fabrication (as registered), flange T mm, attachment thickness mm, fillet leg mm, depth a0 mm, dead-load stress MPa,
# largest survey range MPa, spectrum, location (B1/T1 ship loader 1 boom/tower, B2/T2 loader 2), survey cycles per day,
# attachment, position (frame, flange)
COMPS = [("C01", "AW",   25, 15, 10, 3.0, 40, 155, "A", "B1", 3000, "stiffener", "frame 4, top flange"),
         ("C02", "PWHT", 25, 15, 10, 3.0, -30, 160, "B", "T1", 1500, "stiffener", "leg D, inner flange"),
         ("C03", "AW",   16, 36, 10, 2.0, 25, 115, "A", "T1", 5200, "lug",       "leg A, outer flange"),
         ("C04", "AW",   50, 20, 10, 1.5, 60, 170, "B", "B2", 1400, "diaphragm", "frame 2, top flange"),
         ("C05", "PWHT", 30, 16, 10, 2.5, -35, 170, "B", "T1", 3000, "bracket",   "leg B, inner flange"),
         ("C06", "VSR",  25, 20, 10, 3.0, -40, 150, "B", "T1", 1600, "lug",       "leg B, outer flange"),
         ("C07", "PWHT", 45, 16, 10, 2.0, -40, 190, "B", "T2", 1300, "stiffener", "leg D, outer flange"),
         ("C08", "AW",   16, 15,  9, 6.0, 35,  95, "B", "B1", 1800, "cleat",     "frame 11, top flange"),
         ("C09", "PWHT", 16, 32, 10, 2.0, -35, 120, "B", "T2", 3000, "lug",       "leg A, inner flange"),
         ("C10", "VSR",  35, 25, 10, 3.0, -45, 150, "B", "T2", 1600, "bracket",   "leg B, inner flange"),
         ("C11", "AW",   20, 25, 10, 7.0, 50,  70, "A", "T2", 4400, "diaphragm", "leg B, outer flange"),
         ("C12", "PWHT", 30, 16, 10, 3.0, -45, 160, "B", "T1", 1500, "bracket",   "leg A, inner flange"),
         ("C13", "AW",   50, 15, 10, 1.5, 40, 230, "C", "B1", 6000, "cleat",     "frame 3, top flange"),
         ("C14", "PWHT", 20, 40, 10, 3.0, -35, 150, "B", "T1", 2000, "lug",       "leg C, outer flange"),
         ("C15", "AW",   20, 24, 10, 4.5, 30, 145, "B", "B2", 2000, "lug",       "frame 10, top flange"),
         ("C16", "PWHT", 25, 16, 10, 3.0, -45, 140, "B", "T2", 2000, "cleat",     "leg C, inner flange")]
EXAMPLES = [("E01", "AW",   30, 16, 10, 3.0,   0, 170, "A", "B1", 3000, "stiffener", "frame 12, top flange"),
            ("E02", "AW",   20, 24, 10, 3.5, -30, 145, "B", "T1", 2000, "lug",       "leg D, outer flange")]
# attachments welded on site after the members' furnace PWHT (maintenance log): their weld toes are as welded
REWELDED = {"C12": "2022-05-16", "C16": "2023-08-29"}
# operating days between the find and the re-inspection of the examples
EXAMPLE_DAYS = {"E01": 211, "E02": 115}
# FA-3 repairs grind the crack out to the last magnetic-particle indication and then this much deeper; the examples'
# records give that excavation depth, not the crack depth at repair
REPAIR_MARGIN_MM = 1.0
# unloader 2 received the heavier grab after the survey: the live-load ranges of all its members rise with the
# suspended weight, and since the berth conveyor fixes the throughput, its grab cycles fall with the payload
LOAD_CHANGE = {"B2": 1.25, "T2": 1.25}
CYCLE_CHANGE = {"B2": 0.80, "T2": 0.80}
# operating days covered by the survey's counts: unloader 1 was out of service 7 of the 35 survey days
SURVEY_OPERATING_DAYS = {"B1": 28, "T1": 28, "B2": 35, "T2": 35}
OPERATING_DAYS = 300.0                  # a month of operation is a twelfth of this: 25 operating days
LO, HI, GATE = 0.40, 0.50, 16
SURVEY_DAYS = 35


def comp(t, future=True):
    k = LOAD_CHANGE.get(t[9], 1.0) if future else 1.0
    h = HEATS[HEAT_OF[t[0]]]
    return dict(id=t[0], heat=HEAT_OF[t[0]], grade=h[0], sy=h[1], Kmat=h[2], fab=t[1], T=t[2], tatt=t[3], leg=t[4],
                L=t[3] + 2 * t[4], a0=t[5], smin=t[6], dsmax=t[7] * k, spec=t[8], loc=t[9], per_day=t[10],
                detail=t[11], position=t[12], resid=1.0 if t[0] in REWELDED else SRES[t[1]])


def counts(c):
    """the survey's rainflow counts as written in the survey file (the days the unloader actually operated)"""
    return np.round(c["per_day"] * survey_days(c) * SPECTRA[c["spec"]])


def survey_days(c):
    """operating days behind a component's survey counts; the examples' records come from the 2023 survey (35 days)"""
    return SURVEY_OPERATING_DAYS[c["loc"]] if c["id"].startswith("C") else SURVEY_DAYS


def shares(c):
    n = counts(c)
    return n / n.sum()


def geom(c, mk=True, L=None):
    T = c["T"] * 1e-3; LT = (c["L"] if L is None else L) / c["T"]
    return lambda a: Y(a / T) * np.sqrt(np.pi * a) * (Mk(a / T, LT) if mk else 1.0)


def bins(c, sres_frac=None):
    frac = c["resid"] if sres_frac is None else sres_frac
    sres = frac * c["sy"]; ds = c["dsmax"] * FRAC
    return ds, np.minimum((c["smin"] + sres) / (c["smin"] + sres + ds), 0.95)


def crit(c, g):
    T = c["T"] * 1e-3
    aa = np.linspace(c["a0"] * 1e-3, 0.5 * T, 20000)
    hit = np.nonzero((c["smin"] + c["dsmax"]) * g(aa) >= c["Kmat"])[0]
    return aa[hit[0]] if len(hit) else 0.5 * T


def life(c, law=None, sres_frac=None, mk=True, L=None, nsteps=3000, a_end=None):
    law = law or true_rate(c["heat"])
    g = geom(c, mk, L)
    ds, R = bins(c, sres_frac)
    ac = crit(c, g) if a_end is None else a_end * 1e-3
    a = np.linspace(c["a0"] * 1e-3, ac, nsteps)
    dK = ds[None, :] * g(a)[:, None]
    r = (law(dK, R[None, :]) * shares(c)[None, :]).sum(1)
    with np.errstate(divide="ignore"):
        inv = np.where(r > 0, 1 / r, np.inf)
    return float(np.trapezoid(inv, a)), ac * 1e3


def per_month(c, future=True):
    days = survey_days(c)
    k = CYCLE_CHANGE.get(c["loc"], 1.0) if (future and c["id"].startswith("C")) else 1.0
    return k * counts(c).sum() / days * OPERATING_DAYS / 12.0


def life_months(c, **kw):
    N, ac = life(c, **kw)
    return N / per_month(c), N, ac


def grow(c, N, law=None, sres_frac=None, mk=True, L=None, nsteps=4000):
    law = law or true_rate(c["heat"])
    g = geom(c, mk, L)
    ds, R = bins(c, sres_frac)
    a = np.linspace(c["a0"] * 1e-3, 0.5 * c["T"] * 1e-3, nsteps)
    dK = ds[None, :] * g(a)[:, None]
    r = (law(dK, R[None, :]) * shares(c)[None, :]).sum(1)
    with np.errstate(divide="ignore"):
        inv = np.where(r > 0, 1 / r, np.inf)
    Ncum = np.concatenate([[0], np.cumsum(np.diff(a) * 0.5 * (inv[1:] + inv[:-1]))])
    return float(np.interp(N, Ncum, a) * 1e3)


KMAX_LAB = 75.0                         # the laboratory keeps Kmax = dK / (1 - R) below this, under every heat's Kmat


def lab(kind, R, rng, heat=None):
    """A laboratory test at load ratio R on a CT specimen of the given heat (default LAB_HEAT). 'paris': ten points spaced evenly in log dK from top / 3.75 to top, where
    top = min(45, KMAX_LAB (1 - R)); 'threshold': fourteen points K-decreasing from min(14, top) to 1.02 dKth(R).
    Points that would grow slower than 1e-11 m/cycle are not reported. Each rate carries log-normal scatter NOISE."""
    top = min(45.0, KMAX_LAB * (1 - R))
    if kind == "paris":
        dK = np.geomspace(top / 3.75, top, 10)
    else:
        th = float(dkth(R))
        dK = np.geomspace(min(14.0, top), th * 1.02, 14)
    r = true_rate(heat or LAB_HEAT)(dK, np.full_like(dK, R))
    keep = r > 1e-11
    dK, r = dK[keep], r[keep]
    return dK, r * np.exp(rng.normal(0, NOISE, len(r)))
