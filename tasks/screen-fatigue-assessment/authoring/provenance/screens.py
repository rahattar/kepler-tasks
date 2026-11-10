"""Sealed definition: ten vibrating screens, S1-S10, one monitored gusset weld toe each (exciter-beam gusset to side
plate, drive side). Units: MPa, Hz, s, hours, t/h.

Steady running at feed F (t/h), hot-spot stress at the weld toe:
    sigma(t) = A(F) [sin(theta) + h2 sin(2 theta + phi)],  A(F) = A0 (1 + beta (F/400 - 1)),  theta = w_op t
    (empty running is F = 0; one stress cycle per exciter revolution).
Starts and stops: the body on its coil springs has two modes (bounce f1, pitch f2, damping z1, z2); the exciter's
rotating unbalance drives both, q_i'' + 2 z_i w_i q_i' + w_i^2 q_i = w(t)^2 sin(theta(t)), and the gusset stress
follows x = q1 + w2 q2, scaled so that steady running at w_op gives A(0):
    sigma(t) = A(0) [-x(t) / |X(w_op)| + h2 (w/w_op)^2 sin(2 theta + phi)].
    start: w ramps 0 -> w_op over t_up (direct on line); braked stop (from 2026-03-02): w ramps w_op -> 0 over
    t_brake; unbraked coast-down (before 2026-03-02): w = w_op exp(-t / tau), tau from the coast-down time.
    Starts and braked stops draw amplitude x (1 + 0.04 N), t_up and t_brake x (1 + 0.10 N); coast-downs vary only in
    phase (a coast-down's damage is the same to within 0.1 % for any phase).
Damage (plant standard FS-07, IIW hot-spot method): rainflow ranges of the hot-spot stress, Miner sum, mean stress
ignored; N = 2e6 (FAT/dS)^3 down to the knee at 1e7 cycles, N = 1e7 (dS_knee/dS)^5 below it, no cut-off;
FAT x (25/t)^0.3 for plate over 25 mm.
Graded: D = steady (band hours x expected damage rate in the band, feed uniform within a band) + starts x E[start] +
stops before 2026-03-02 x E[coast-down] + stops after x E[braked stop], counted from commissioning (S6: from its
2025-11-14 replacement) to 2026-10-31 24:00. A0 is set so that D equals DAMAGE[u] (calibrate()).

Gauges: linear stress gradient through the plate, sigma(x) = sigma_hs (1 - g x / t); a gauge at x = p t reads
sigma_hs (1 - g p) / E; recorded microstrain = true x GF_true / 2.00 + noise (0.2 ue).

Records and their traps:
- S1: gauge G2 partly debonded from 2026-08-20 (reads 0.75); the log notes the wet gauge on 2026-09-08.
- S2: gauges at 0.5t and 1.5t; exciter bearings renewed 2021-10-05, coast-down re-timed (25.0 s to half speed).
- S4: gauge lot with gauge factor 2.12; the loggers use 2.00. S4's event records were never captured.
- S5: rev B gusset (FAT 100). Its logger never recorded: only a strain survey settles it.
- S6: gusset replaced 2025-11-14; lighter damping since; its event records were never captured: only a coast-down
  test settles its pre-brake stops (sibling proxies leave its total 58-74 % low).
- S7: channels swapped at the junction box.
- S8: logger at 200 Hz from 2026-07-01 (index says 500); new-historian pilot from 2024-07-01 counts start and stop
  commands (logged starts doubled).
- S8, S10: the larger drive, identical on both, coast-down never timed (27.0 s to half speed): one coast-down test
  on either settles both.
- S9: 32 mm plate; G1 drops to 0.80 from 2026-07-20 with nothing logged (an inspection on 2026-10-20 found no
  crack); 2024 missing from the historian, monthly totals in the production report.
- S3: coast-down never timed, standard drive: the standard-drive median is good enough (decoy).
"""
import numpy as np

UNITS = ["S%d" % i for i in range(1, 11)]
E_MPA = 207000.0
BANDS = [(0.0, 0.0), (0.0, 200.0), (200.0, 400.0), (400.0, 600.0), (600.0, 800.0)]
BAND_COLS = ["h_empty", "h_0_200", "h_200_400", "h_400_600", "h_600_800"]
END_DATE = "2026-10-31"
DAMAGE = {"S3": 0.0105, "S6": 0.0160, "S1": 0.0383, "S8": 0.0583, "S4": 0.140, "S10": 0.213, "S7": 0.511,
          "S5": 0.777, "S2": 1.865, "S9": 2.835}   # Miner sum to 2026-10-31: neighbours 1.52x or 2.4x apart, so no
          # constant satisfies two screens (window +-20 %) and every screen that needs a test sits between one gap
          # of each kind (filling it from its neighbours' spacing misses by 26 %)
TOL = 0.20
COMMISSIONED = {"S1": "2021-03-15", "S2": "2021-03-15", "S3": "2021-09-01", "S4": "2021-09-01", "S5": "2022-02-07",
                "S6": "2022-02-07", "S7": "2022-10-03", "S8": "2023-04-17", "S9": "2023-04-17", "S10": "2024-01-22"}
COUNT_FROM = dict(COMMISSIONED, S6="2025-11-14")
THICK = {u: 20.0 for u in UNITS}
THICK["S9"] = 32.0
FAT = {u: 90.0 for u in UNITS}
FAT["S5"] = 100.0
POS = {u: (0.4, 1.0) for u in UNITS}
POS["S2"] = (0.5, 1.5)
GF_TRUE = {u: 2.00 for u in UNITS}
GF_TRUE["S4"] = 2.12
DEBOND = ("S1", "2026-08-20", 0.75)
SWAPPED = "S7"
DEBOND2 = ("S9", "2026-07-20", 0.80)          # G1 partly debonded, nothing logged; only the G2/G1 ratio shows it
STARTS_DOUBLED = ("S8", "2024-07-01")         # new-historian pilot: its counter logs start and stop commands
GAP = ("S9", "2024-01-01", "2024-12-31")      # historian outage; monthly production report fills it
NO_RECORDS = "S5"                             # logger never recorded
NO_EVENTS = ("S4", "S6")                      # event trigger unwired: steady records only
UNTIMED = ("S3", "S8", "S10")                 # coast-down not timed at commissioning
FRAME_B = ("S8", "S10")                       # 37 kW drive (identical on both); the rest 30 kW
TAU_B_HALF = 27.0                             # full to half speed, s, frame B (never timed: needs a test)
TAU_CHANGE = ("S2", "2021-10-05", 25.0)       # exciter bearings renewed; coast-down re-timed: full to half speed, s
FS = {u: 500.0 for u in UNITS}
FS["S8"] = 200.0
RPM = {u: 960.0 for u in UNITS}
RPM.update({"S3": 980.0, "S4": 980.0, "S10": 940.0})


def fat_eff(u):
    t = THICK[u]
    return FAT[u] * ((25.0 / t) ** 0.3 if t > 25.0 else 1.0)


def cycles_to_failure(dS, fat):
    dS = np.asarray(dS, float)
    knee = fat * 0.2 ** (1.0 / 3.0)
    with np.errstate(divide="ignore"):
        hi = 2e6 * (fat / dS) ** 3
        lo = 1e7 * (knee / dS) ** 5
    return np.where(dS >= knee, hi, lo)


def miner(ranges, counts, fat):
    ranges = np.asarray(ranges, float)
    counts = np.asarray(counts, float)
    m = ranges > 0
    return float(np.sum(counts[m] / cycles_to_failure(ranges[m], fat)))


def turning_points(x):
    x = np.asarray(x, float)
    d = np.diff(x)
    keep = d != 0
    idx = np.r_[0, np.nonzero(keep)[0] + 1]
    x = x[idx]
    d = np.diff(x)
    s = np.sign(d)
    tp = np.r_[True, s[1:] != s[:-1], True]
    return x[tp]


def rainflow(x):
    """ASTM E1049 rainflow (stack form). Returns ranges and counts (1 full, 0.5 half)."""
    tp = turning_points(x)
    stack, rng, cnt = [], [], []
    for v in tp:
        stack.append(v)
        while len(stack) >= 3:
            X = abs(stack[-1] - stack[-2])
            Y = abs(stack[-2] - stack[-3])
            if X < Y:
                break
            if len(stack) == 3:
                rng.append(Y); cnt.append(0.5)
                stack.pop(0)
            else:
                rng.append(Y); cnt.append(1.0)
                last = stack.pop()
                stack.pop(); stack.pop()
                stack.append(last)
    for i in range(len(stack) - 1):
        rng.append(abs(stack[i + 1] - stack[i])); cnt.append(0.5)
    return np.array(rng), np.array(cnt)


def make_bank(seed=19):
    rng = np.random.default_rng(seed)
    bank = {}
    for u in UNITS:
        b = dict(unit=u)
        b["f_op"] = RPM[u] / 60.0
        b["h2"] = float(rng.uniform(0.06, 0.14))
        b["phi"] = float(rng.uniform(0, 2 * np.pi))
        b["beta"] = float(rng.uniform(0.15, 0.35))
        b["g"] = float(rng.uniform(0.35, 0.6))        # stress gradient across the plate thickness
        b["f1"] = float(rng.uniform(2.6, 3.0))        # bounce
        b["f2"] = float(rng.uniform(3.3, 3.8))        # pitch
        b["z1"] = float(rng.uniform(0.012, 0.024))
        b["z2"] = float(rng.uniform(0.012, 0.024))
        b["w2"] = float(rng.choice([-1, 1]) * rng.uniform(0.35, 0.8))
        b["t_up"] = float(rng.uniform(3.0, 5.0))      # direct-on-line run-up
        b["t_brake"] = float(rng.uniform(4.0, 6.0))   # motor brake (from 2026-03-02): linear to standstill
        b["tau"] = float(rng.uniform(14.0, 20.0))     # coast-down time constant before the brakes
        bank[u] = b
    bank["S10"]["z1"] = 0.011                        # little damping: harsh resonance passages
    bank["S10"]["tau"] = 18.0
    bank[TAU_CHANGE[0]]["tau2"] = TAU_CHANGE[2] / np.log(2.0)
    bank["S6"]["z1"], bank["S6"]["z2"] = 0.009, 0.010   # replacement panel: lighter damping, harsh passages
    for u in FRAME_B:                                # larger drive, heavier rotor: long coast-down
        bank[u]["tau"] = TAU_B_HALF / np.log(2.0)
    return bank


def wave(theta, b):
    return np.sin(theta) + b["h2"] * np.sin(2 * theta + b["phi"])


def ptp_factor(b):
    x = np.linspace(0, 2 * np.pi, 20001)
    w = wave(x, b)
    return float(w.max() - w.min())


def amp(b, F):
    return b["A0"] * (1.0 + b["beta"] * (np.asarray(F, float) / 400.0 - 1.0))


def steady_rate(b, A, fat):
    """Damage per running hour at amplitude A: one cycle per revolution, range = A x peak-to-peak factor."""
    return 3600.0 * b["f_op"] / cycles_to_failure(A * b["P"], fat)


def band_rate(b, lo, hi, fat):
    if hi == lo:
        return float(steady_rate(b, amp(b, lo), fat))
    F = np.linspace(lo, hi, 401)
    return float(np.trapezoid(steady_rate(b, amp(b, F), fat), F) / (hi - lo))


def modes(b):
    """Bounce and pitch modes of the suspended body: (frequency Hz, damping ratio, weight of the mode in the gusset
    stress per unit exciter forcing)."""
    return [(b["f1"], b["z1"], 1.0), (b["f2"], b["z2"], b["w2"])]


def body(b, w, fs):
    """Gusset-stress coordinate from rest: sum over modes of w_i q_i, q_i'' + 2 z_i wn_i q_i' + wn_i^2 q_i =
    w(t)^2 sin(theta(t)), each discretised exactly for a first-order-hold input. Returns x(t) and theta(t)."""
    from scipy.signal import cont2discrete, lfilter
    theta = np.cumsum(w) / fs + b["theta0"]
    u = w * w * np.sin(theta)
    x = np.zeros_like(u)
    for f, z, wt in modes(b):
        wn = 2 * np.pi * f
        num, den, _ = cont2discrete(([1.0], [1.0, 2 * z * wn, wn * wn]), 1.0 / fs, method="foh")
        x += wt * lfilter(np.ravel(num), den, u)
    return x, theta


def steady_x(b, w):
    """Steady amplitude of the stress coordinate at constant speed w."""
    H = sum(wt * w * w / complex((2 * np.pi * f) ** 2 - w * w, 2 * z * 2 * np.pi * f * w) for f, z, wt in modes(b))
    return abs(H), float(np.angle(H))


BRAKE_DATE = "2026-03-02"
EVENT_LEN = {"start": 10.0, "stop": 14.0, "coast": None}
LEAD = 15.0                     # s of steady running simulated ahead of a stop, so the body starts in steady state


def event(b, kind, fs, rng, length=None):
    """One start, braked stop, or unbraked coast-down: hot-spot stress, MPa. The body's motion scales the stress
    (steady running amplitude A(0) at f_op); a small local second harmonic rides on the exciter speed."""
    a_mult = 1.0 + 0.04 * rng.standard_normal()
    s_mult = 1.0 + 0.10 * rng.standard_normal()
    wop = 2 * np.pi * b["f_op"]
    th0 = rng.uniform(0, 2 * np.pi)
    if kind == "start":
        L = length or EVENT_LEN["start"]
        t = np.arange(int(round(L * fs))) / fs
        w = wop * np.clip((t - 0.5) / (b["t_up"] * s_mult), 0, 1)
        lead = 0
    else:
        if kind == "stop":
            L = length or EVENT_LEN["stop"]
        else:
            tau = b["tau2"] if kind == "coast2" else b["tau"]   # the timed coast-down; only the phase varies
            L = length or 5.5 * tau
        t = np.arange(int(round((LEAD + L) * fs))) / fs - LEAD
        if kind == "stop":
            w = wop * np.clip(1 - (t - 0.5) / (b["t_brake"] * s_mult), 0, 1)
        else:
            w = wop * np.exp(-np.maximum(t - 0.5, 0) / tau)
        lead = int(round(LEAD * fs))
    x, theta = body(dict(b, theta0=th0), w, fs)
    Xop, _ = steady_x(b, wop)
    A = b["A0"] * (1.0 - b["beta"]) * (1.0 if kind.startswith("coast") else a_mult)
    sig = A * (-x / Xop + b["h2"] * (w / wop) ** 2 * np.sin(2 * theta + b["phi"]))
    if kind == "start" or kind == "stop":
        return sig[lead:], (w / (2 * np.pi) * 60.0)[lead:]
    return sig[lead:]


def damage_total(b, log, fat, ev):
    """log: DataFrame for one unit with date, band hours and starts (each start ends in a stop)."""
    rates = [band_rate(b, lo, hi, fat) for lo, hi in BANDS]
    L = log[log.date >= COUNT_FROM[b["unit"]]]
    steady = sum(float(L[c].sum()) * r for c, r in zip(BAND_COLS, rates))
    pre = L.date < BRAKE_DATE
    if "coast2" in ev:                              # coast-down time changed (bearings renewed)
        late = L.date >= TAU_CHANGE[1]
        coast = float(L.starts[pre & ~late].sum()) * ev["coast"] + float(L.starts[pre & late].sum()) * ev["coast2"]
    else:
        coast = float(L.starts[pre].sum()) * ev["coast"]
    events = float(L.starts.sum()) * ev["start"] + coast + float(L.starts[~pre].sum()) * ev["stop"]
    return steady + events, steady, events


def operating_log(seed=23):
    """Daily operating log for every unit, commissioning to END_DATE: hours in each feed band and starts."""
    import pandas as pd
    rng = np.random.default_rng(seed)
    rows = []
    duty = {u: dict(mean_feed=float(rng.uniform(380, 520)), sd_feed=float(rng.uniform(90, 140)),
                    run_h=float(rng.uniform(17, 21)), starts=float(rng.uniform(2.0, 3.6))) for u in UNITS}
    duty["S10"].update(run_h=14.0, starts=7.5)                      # batch duty
    for u in UNITS:
        d = duty[u]
        for day in pd.date_range(COMMISSIONED[u], END_DATE, freq="D"):
            down = rng.random() < 0.06                              # planned or unplanned day off
            run = 0.0 if down else float(np.clip(rng.normal(d["run_h"], 2.0), 4.0, 23.5))
            st = 0 if run == 0 else max(1, int(rng.poisson(d["starts"])))
            empty = 0.0 if run == 0 else float(np.clip(rng.normal(0.08, 0.03), 0.02, 0.2)) * run
            loaded = run - empty
            fh = np.zeros(4)
            if loaded > 0:
                F = np.clip(rng.normal(d["mean_feed"] + rng.normal(0, 40), d["sd_feed"], 400), 1, 799)
                fh = np.histogram(F, bins=[0, 200, 400, 600, 800])[0] / 400.0 * loaded
            rows.append(dict(unit=u, date=day.strftime("%Y-%m-%d"), h_empty=round(empty, 2),
                             h_0_200=round(fh[0], 2), h_200_400=round(fh[1], 2), h_400_600=round(fh[2], 2),
                             h_600_800=round(fh[3], 2), starts=st))
    return pd.DataFrame(rows)


def event_ranges(b, n=100, seed=0):
    """Rainflow ranges of n starts, braked stops and coast-downs at unit amplitude A0 = 1 (ranges scale with A0)."""
    rng = np.random.default_rng(seed)
    bb = dict(b, A0=1.0)
    out = {}
    kinds = ("start", "stop", "coast", "coast2") if "tau2" in b else ("start", "stop", "coast")
    for kind in kinds:
        out[kind] = []
        for _ in range(n):
            sig = event(bb, kind, 1000.0, rng)
            r, c = rainflow(sig[0] if isinstance(sig, tuple) else sig)
            out[kind].append((r, c))
    return out


def calibrate(bank, log, n_ev=100):
    """Set each unit's A0 so the graded damage equals DAMAGE[u]."""
    from scipy.optimize import brentq
    for u in UNITS:
        b = bank[u]
        b["P"] = ptp_factor(b)
        fat = fat_eff(u)
        L = log[log.unit == u]
        evr = event_ranges(b, n_ev, seed=100 + UNITS.index(u))

        def total(A0):
            b["A0"] = A0
            ev = {k: float(np.mean([miner(A0 * r, c, fat) for r, c in evr[k]])) for k in evr}
            return damage_total(b, L, fat, ev), ev
        A0 = brentq(lambda a: total(a)[0][0] - DAMAGE[u], 1.0, 60.0, xtol=1e-6)
        (D, st, evd), ev = total(A0)
        b["A0"], b["ev"], b["D"], b["D_steady"], b["D_events"] = A0, ev, D, st, evd
    return bank


def truth(seed=19):
    log = operating_log()
    return calibrate(make_bank(seed), log), log


def grade(est, tol=TOL):
    res = {}
    for u in UNITS:
        e = est[u] / DAMAGE[u] - 1.0
        res[u] = (float(e), abs(e) <= tol + 1e-12)
    return res


def save_bank(bank, path):
    import json
    keep = {u: {k: v for k, v in b.items() if isinstance(v, (int, float, str, dict))} for u, b in bank.items()}
    with open(path, "w") as f:
        json.dump(keep, f, indent=1, sort_keys=True)


def load_bank(path):
    import json
    with open(path) as f:
        return json.load(f)
