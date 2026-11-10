"""Sealed definition for hoist-brake-sizing: the truth that the documents, the friction laboratory and the
verifier share. Nothing here is visible to the agent."""
import numpy as np

G = 9.81
# size: rated torque N m (100 % setting, bedded organic lining at 20 C), rotor inertia kg m2, heat capacity J/K,
#       heat dissipation W/K, engagement time with DC-side / AC-side switching s
SIZES = {"S08": (60, 0.0025, 480, 0.55, 0.020, 0.090),
         "S10": (100, 0.0045, 700, 0.70, 0.025, 0.110),
         "S12": (160, 0.0070, 950, 0.85, 0.030, 0.140),
         "S14": (250, 0.012, 1300, 1.05, 0.035, 0.170),
         "S16": (400, 0.020, 1800, 1.30, 0.045, 0.220),
         "S18": (630, 0.035, 2600, 1.65, 0.055, 0.280),
         "S20": (1000, 0.060, 3600, 2.10, 0.070, 0.350),
         "S22": (1250, 0.082, 4300, 2.40, 0.080, 0.400),
         "S25": (1600, 0.110, 5200, 2.70, 0.090, 0.450)}
MU_REF, TMAX = 0.40, 300.0
SETTINGS = tuple(range(50, 101))
HOLD_FACTOR = 1.6

# friction lining fitted to each size
LINING = {"S08": "O1", "S10": "O1", "S12": "O1", "S14": "O1", "S16": "O2", "S18": "O2", "S20": "O2", "S22": "O2",
          "S25": "O2"}


def mu_true(T, lining="O1"):
    """bedded organic linings. O1: 0.40 cold, a friction peak of 0.52 near 160 C, fade above 200 C.
    O2: 0.38 cold, a peak of 0.48 near 200 C, fade above 240 C."""
    T = np.asarray(T, float)
    if lining == "O1":
        return (0.40 + 0.02 * np.clip((T - 20.0) / 90.0, 0, 1) + 0.10 * np.exp(-((T - 160.0) / 26.0) ** 2)
                - 0.0016 * np.maximum(0.0, T - 200.0))
    return (0.38 + 0.02 * np.clip((T - 20.0) / 120.0, 0, 1) + 0.08 * np.exp(-((T - 200.0) / 28.0) ** 2)
            - 0.0014 * np.maximum(0.0, T - 240.0))


# engagement time grows at reduced spring settings: t = t_catalogue (1 + KAPPA ln(100 / setting))
KAPPA = {"DC": 0.15, "AC": 0.45}


def engagement(size, setting, sw):
    st = np.asarray(setting, float)
    t = SIZES[size][4] if sw == "DC" else SIZES[size][5]
    return t * (1 + KAPPA[sw] * np.log(100.0 / st))


def w_lower(h):
    """motor speed lowering the rated load: above synchronous (1500 rpm) on contactor control, as set on an inverter"""
    if h["ctrl"] == "vfd":
        return 2 * np.pi * h["n"] / 60
    return 2 * np.pi * (3000.0 - h["n"]) / 60

# the hoists as they are now (after every entry of the maintenance log); slim m, amax m/s2, glim N m
HOISTS = {
    'H01': {'load': 10000.0, 'hook': 300.0, 'falls': 4.0, 'D': 0.4, 'ratio': 57.5, 'eta': 0.94, 'P': 18.5, 'n': 1465.0, 'Jm': 0.12, 'Jg': 0.0168, 'glim': 360.0, 'ctrl': 'contactor', 'slow': 1.0, 'sw': 'DC', 'Tamb': 25.0, 'stops': 60.0, 'lf': 0.6, 'fast': None, 'slim': 0.061, 'amax': 1.43, 'v': 8.0, 'name': 'Maintenance workshop crane, main hoist', 'bay': 'workshop'},
    'H02': {'load': 5000.0, 'hook': 150.0, 'falls': 2.0, 'D': 0.3, 'ratio': 68.6, 'eta': 0.94, 'P': 11.0, 'n': 1455.0, 'Jm': 0.06, 'Jg': 0.0084, 'glim': 220.0, 'ctrl': 'twospeed', 'slow': 0.16666666666666666, 'sw': 'AC', 'Tamb': 25.0, 'stops': 360.0, 'lf': 0.6, 'fast': None, 'slim': 0.11, 'amax': 2.23, 'v': 10.0, 'name': 'Pattern shop crane, main hoist', 'bay': 'pattern shop'},
    'H03': {'load': 25000.0, 'hook': 750.0, 'falls': 4.0, 'D': 0.55, 'ratio': 63.9, 'eta': 0.93, 'P': 55.0, 'n': 1480.0, 'Jm': 0.58, 'Jg': 0.0812, 'glim': 1060.0, 'ctrl': 'contactor', 'slow': 1.0, 'sw': 'DC', 'Tamb': 50.0, 'stops': 165.0, 'lf': 0.7, 'fast': None, 'slim': 0.085, 'amax': 1.82, 'v': 10.0, 'name': 'Melt shop charging crane, auxiliary hoist', 'bay': 'melt shop'},
    'H04': {'load': 16000.0, 'hook': 480.0, 'falls': 4.0, 'D': 0.45, 'ratio': 64.9, 'eta': 0.94, 'P': 30.0, 'n': 1470.0, 'Jm': 0.24, 'Jg': 0.0336, 'glim': 580.0, 'ctrl': 'vfd', 'slow': 1.0, 'sw': 'DC', 'Tamb': 30.0, 'stops': 120.0, 'lf': 0.6, 'fast': (1.5, 0.5), 'slim': 0.053, 'amax': 1.19, 'v': 8.0, 'name': 'Machine hall crane 1, main hoist', 'bay': 'machine hall'},
    'H05': {'load': 10000.0, 'hook': 300.0, 'falls': 2.0, 'D': 0.45, 'ratio': 65.2, 'eta': 0.94, 'P': 37.0, 'n': 1475.0, 'Jm': 0.31, 'Jg': 0.0434, 'glim': 720.0, 'ctrl': 'contactor', 'slow': 1.0, 'sw': 'AC', 'Tamb': 30.0, 'stops': 95.0, 'lf': 0.6, 'fast': None, 'slim': 0.265, 'amax': 2.29, 'v': 16.0, 'name': 'Despatch bay crane, main hoist', 'bay': 'despatch bay'},
    'H06': {'load': 3200.0, 'hook': 100.0, 'falls': 2.0, 'D': 0.25, 'ratio': 93.6, 'eta': 0.72, 'P': 5.5, 'n': 1430.0, 'Jm': 0.024, 'Jg': 0.0034, 'glim': 110.0, 'ctrl': 'contactor', 'slow': 1.0, 'sw': 'DC', 'Tamb': 25.0, 'stops': 120.0, 'lf': 0.6, 'fast': None, 'slim': 0.024, 'amax': 1.48, 'v': 6.0, 'name': 'Tool room jib crane hoist', 'bay': 'tool room'},
    'H07': {'load': 20000.0, 'hook': 600.0, 'falls': 4.0, 'D': 0.5, 'ratio': 57.9, 'eta': 0.93, 'P': 45.0, 'n': 1475.0, 'Jm': 0.4, 'Jg': 0.056, 'glim': 870.0, 'ctrl': 'contactor', 'slow': 1.0, 'sw': 'AC', 'Tamb': 45.0, 'stops': 55.0, 'lf': 0.6, 'fast': None, 'slim': 0.215, 'amax': 1.43, 'v': 10.0, 'name': 'Casting bay crane, main hoist', 'bay': 'casting bay'},
    'H08': {'load': 8000.0, 'hook': 240.0, 'falls': 4.0, 'D': 0.35, 'ratio': 40.3, 'eta': 0.94, 'P': 18.5, 'n': 1465.0, 'Jm': 0.12, 'Jg': 0.0168, 'glim': 360.0, 'ctrl': 'vfd', 'slow': 1.0, 'sw': 'AC', 'Tamb': 25.0, 'stops': 200.0, 'lf': 0.6, 'fast': (1.6, 0.4), 'slim': 0.122, 'amax': 1.87, 'v': 10.0, 'name': 'Machine hall crane 2, main hoist', 'bay': 'machine hall'},
    'H09': {'load': 32000.0, 'hook': 960.0, 'falls': 6.0, 'D': 0.6, 'ratio': 77.2, 'eta': 0.93, 'P': 45.0, 'n': 1475.0, 'Jm': 0.4, 'Jg': 0.056, 'glim': 870.0, 'ctrl': 'twospeed', 'slow': 0.25, 'sw': 'DC', 'Tamb': 35.0, 'stops': 200.0, 'lf': 0.6, 'fast': None, 'slim': 0.063, 'amax': 0.79, 'v': 6.0, 'name': 'Assembly hall crane, main hoist', 'bay': 'assembly hall'},
    'H10': {'load': 12500.0, 'hook': 380.0, 'falls': 4.0, 'D': 0.4, 'ratio': 46.2, 'eta': 0.94, 'P': 30.0, 'n': 1470.0, 'Jm': 0.24, 'Jg': 0.0336, 'glim': 580.0, 'ctrl': 'contactor', 'slow': 1.0, 'sw': 'DC', 'Tamb': 40.0, 'stops': 265.0, 'lf': 0.55, 'fast': None, 'slim': 0.099, 'amax': 1.89, 'v': 10.0, 'name': 'Fettling shop crane, main hoist', 'bay': 'fettling shop'},
    'H11': {'load': 6300.0, 'hook': 190.0, 'falls': 2.0, 'D': 0.32, 'ratio': 61.4, 'eta': 0.94, 'P': 18.5, 'n': 1465.0, 'Jm': 0.12, 'Jg': 0.0168, 'glim': 360.0, 'ctrl': 'contactor', 'slow': 1.0, 'sw': 'DC', 'Tamb': 35.0, 'stops': 190.0, 'lf': 0.5, 'fast': None, 'slim': 0.092, 'amax': 2.06, 'v': 12.0, 'name': 'Core shop crane, main hoist', 'bay': 'core shop'},
    'H12': {'load': 40000.0, 'hook': 1200.0, 'falls': 8.0, 'D': 0.7, 'ratio': 81.1, 'eta': 0.93, 'P': 45.0, 'n': 1475.0, 'Jm': 0.4, 'Jg': 0.056, 'glim': 870.0, 'ctrl': 'vfd', 'slow': 1.0, 'sw': 'DC', 'Tamb': 35.0, 'stops': 160.0, 'lf': 0.6, 'fast': None, 'slim': 0.048, 'amax': 0.69, 'v': 5.0, 'name': 'Heavy assembly crane, main hoist', 'bay': 'assembly hall'},
}
# what the register (dated before the log entries) still shows, where it differs
REGISTER = {"H04": dict(ctrl="contactor"), "H08": dict(ctrl="contactor"), "H12": dict(ctrl="contactor"),
            "H05": dict(falls=4, load=20000.0, v=8.0, hook=420.0)}
GEAR = {"H06": "worm"}


def k_w(h):
    return h["D"] / (2 * h["falls"] * h["ratio"]), 2 * np.pi * h["n"] / 60


def static_torque(h, m):
    return (m + h["hook"]) * G * k_w(h)[0]


def inertia(h, m, size):
    k = k_w(h)[0]
    return h["Jm"] + h["Jg"] + SIZES[size][1] + (m + h["hook"]) * k * k


def margins(hid, size, setting):
    """requirement margins (>= 0 meets it) of a brake size and setting (%) on a hoist, under the truth"""
    h = HOISTS[hid]
    st = np.atleast_1d(np.asarray(setting, float))
    Mr, Jb, C, H, tdc, tac = SIZES[size]

    lin = LINING[size]
    mu20 = float(mu_true(20.0, lin))

    def MB(T):
        return st / 100 * Mr * mu_true(T, lin) / mu20
    k, w0 = k_w(h)
    er = 2 - 1 / h["eta"]                      # efficiency of the gear driven backwards (load lowering)
    # working duty: peak lining temperature of the periodic steady state
    Tp = np.full_like(st, h["Tamb"])
    if h["ctrl"] != "vfd":
        m = h["lf"] * h["load"]
        J = inertia(h, m, size)
        Lh, Ll = static_torque(h, m) / h["eta"], static_torque(h, m) * er
        trw = engagement(size, st, h["sw"])
        wh = np.maximum(w0 * h["slow"] - Lh / J * trw, 0.0)
        wl = w_lower(h) * h["slow"] + Ll / J * trw
        a = np.exp(-3600.0 / h["stops"] / (C / H))
        T = Tp.copy()
        for _ in range(80):
            mb = MB(T)
            bad = mb <= Ll * 1.0001
            eh = mb * J * wh * wh / (2 * (mb + Lh))
            el = mb * J * wl * wl / (2 * np.maximum(mb - Ll, 1e-6))
            th = (eh / C + a * el / C) / (1 - a * a)
            tl = (el / C + a * eh / C) / (1 - a * a)
            Tn = np.where(bad, 5000.0, np.minimum(h["Tamb"] + np.maximum(th, tl), 5000.0))
            T = 0.5 * T + 0.5 * Tn
        Tp = T
    hold = MB(Tp) / (HOLD_FACTOR * static_torque(h, h["load"])) - 1
    # emergency stop while lowering, from the duty temperature, at every permitted load and speed
    cases = [(h["load"], 1.0)] + ([(h["fast"][1] * h["load"], h["fast"][0])] if h["fast"] else [])
    trav = np.full_like(st, np.inf)
    Tend = Tp.copy()
    tr = engagement(size, st, h["sw"])
    for m, vf in cases:
        J = inertia(h, m, size)
        L = static_torque(h, m) * er
        a1 = L / J
        w = w_lower(h) if vf == 1.0 else w0 * vf
        w1 = w + a1 * tr
        ang = w * tr + 0.5 * a1 * tr * tr
        T = Tp.copy()
        alive = np.ones_like(st, bool)
        for _ in range(40000):
            mb = MB(T)
            acc = (L - mb) / J
            stuck = alive & ((acc >= 0) | (T > 1500))
            ang = np.where(stuck, np.inf, ang)
            alive &= ~stuck
            if not alive.any():
                break
            step = np.where(alive, np.minimum(5e-4, w1 / np.maximum(-acc, 1e-9)), 0.0)
            ang = np.where(alive, ang + (w1 + 0.5 * acc * step) * step, ang)
            T = np.where(alive, T + mb * w1 * step / C, T)
            w1 = np.where(alive, w1 + acc * step, w1)
            alive &= w1 > 1e-9
        trav = np.minimum(trav, h["slim"] / (ang * k) - 1)
        Tend = np.maximum(Tend, T)
    temp = TMAX / np.maximum(Tend, 1e-9) - 1
    # highest torque over the lining temperatures reached in service
    Ts = np.linspace(0, 1, 60)[:, None] * (np.maximum(Tp, np.minimum(Tend, 1500)) - h["Tamb"])[None, :] + h["Tamb"]
    mbmax = np.max(st / 100 * Mr * mu_true(Ts, lin) / mu20, axis=0)
    gearbox = h["glim"] / mbmax - 1
    J = inertia(h, h["load"], size)
    decel = h["amax"] / ((mbmax + static_torque(h, h["load"]) / h["eta"]) * k / J) - 1
    out = dict(gearbox=gearbox, decel=decel, hold=hold, travel=trav, temp=temp, Tpeak=Tp, Testop=Tend)
    return {kk: (float(v[0]) if np.ndim(setting) == 0 else v) for kk, v in out.items()}


REQUIREMENTS = ("hold", "travel", "decel", "temp", "gearbox")


def meets(hid, size, setting):
    r = margins(hid, size, setting)
    return all(r[k] >= 0 for k in REQUIREMENTS), r


# laboratory: friction coefficient of the lining at a disc temperature; engagement time of a catalogue brake on
# the test bench at a setting and a switching. One allowance for both.
LAB_T = (20.0, 320.0)
FRICTION_POINTS, ENGAGE_POINTS = 8, 5
NOISE_MU, NOISE_T = 0.02, 0.03
BUDGET = 8


def lab_friction(T, rng, lining="O1"):
    mu = float(mu_true(float(T), lining))
    return [round(mu * float(np.exp(rng.normal(0.0, NOISE_MU))), 4) for _ in range(FRICTION_POINTS)]


def lab_engage(size, setting, sw, rng):
    t = float(engagement(size, setting, sw))
    return [round(1000 * t * float(np.exp(rng.normal(0.0, NOISE_T))), 1) for _ in range(ENGAGE_POINTS)]
