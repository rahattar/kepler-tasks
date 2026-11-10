"""Shared machinery for the evidence scripts.

- The laboratory, simulated exactly as environment/rig/lab.py runs it: each test's readings come from numpy's
  generator seeded with (seed, slot, key), so a plan gives the same reports here as in the agent's container.
- The reference solution's model (solution/solve.py), run on any plan, with variants of the hoist records, of the
  friction and engagement fits, and of the physics (VARIANT_FLAGS), for the route study and the method spread.
- The verdict of the sealed definition (authoring/provenance/hbsim.py) on a selection.
"""
import contextlib
import copy
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(BUNDLE, "authoring", "provenance"))
sys.path.insert(0, os.path.join(BUNDLE, "solution"))
import hbsim as S  # noqa: E402
import solve as R  # noqa: E402

R.DT = 2e-3            # evidence runs: emergency-stop time step 2 ms (the reference's 0.4 ms gives the same picks)
DATA = os.path.join(BUNDLE, "environment", "data")
SEED = json.load(open(os.path.join(BUNDLE, "authoring", "provenance", "seed.json")))["seed"]
H0 = R.hoists(DATA)
CAT = R.catalogue(DATA)
IDS = list(H0)
REF_PLAN = list(R.PLAN)
REQ = R.REQ


# ------------------------------------------------------------------ laboratory
def lab_key(test):
    if test[0] == "friction":
        T = round(float(test[1]), 1)
        return [int(round(T * 10)), int(test[2][1])]
    return [1000 + list(S.SIZES).index(test[1]), int(test[2]), 1 if test[3] == "AC" else 0]


def lab(plan, seed=SEED):
    """the reports of a plan run in order from a fresh laboratory"""
    out = []
    for idx, test in enumerate(plan, start=1):
        rng = np.random.default_rng([seed, idx] + lab_key(test))
        if test[0] == "friction":
            vals = [round(v, 4) for v in S.lab_friction(round(float(test[1]), 1), rng, test[2])]
        else:
            vals = [round(v, 1) for v in S.lab_engage(test[1], int(test[2]), test[3], rng)]
        out.append((tuple(str(x) for x in test), vals))
    return out


def F(T, lining="O1"):
    return ("friction", str(T), lining)


def E(size, setting, sw):
    return ("engage", size, str(setting), sw)


# ------------------------------------------------------------------ verdict of the sealed definition
def grade(picks):
    """picks {hoist: (size, setting)} or the reference's select() output; returns (n meeting all, failures)"""
    n, fails = 0, []
    for hid in IDS:
        p = picks[hid]
        size, st = (p[1], p[2]) if len(p) == 4 else p
        ok, r = S.meets(hid, size, st)
        n += ok
        if not ok:
            bad = [k for k in S.REQUIREMENTS if r[k] < 0]
            fails.append("%s %s/%d %s %+.3f" % (hid, size, st, ",".join(bad), min(r[k] for k in S.REQUIREMENTS)))
    return n, fails


def truth_margin(hid, size, st):
    r = S.margins(hid, size, st)
    return min(r[k] for k in S.REQUIREMENTS)


# ------------------------------------------------------------------ model variants
class Pchip(R.Model):
    """shape-preserving cubic through the tested temperatures instead of straight lines"""
    def ratio(self, T, lining):
        from scipy.interpolate import PchipInterpolator
        x, y = self.curve[lining]
        Tc = np.clip(T, x[0], x[-1])
        return PchipInterpolator(x, y)(Tc)


class LogLaw(R.Model):
    """engagement time t100 (1 + kappa ln(100 / setting)) instead of a power of the setting"""
    def engage(self, size, st, sw):
        return self.cat[size]["t"][sw] * (1 + self.p[sw] * np.log(100.0 / st))


def model(tests, cls=R.Model, same_lining=False, engagement=None):
    """the reference fit of a plan's reports. same_lining: O2 taken to behave as O1 (only O1 tested).
    engagement: 'catalogue' ignores the engagement test (times as at 100 %)."""
    M = cls(tests, CAT)
    if same_lining:
        M.curve["O2"] = M.curve["O1"]
    if engagement == "catalogue" or M.p["AC"] is None:
        M.p = {"AC": 0.0, "DC": 0.0}
    if cls is LogLaw and engagement != "catalogue":
        # refit the AC test in the log form
        for test, vals in tests:
            if test[0] == "engage":
                st = float(test[2])
                k = (np.mean(vals) / 1000 / CAT[test[1]]["t"][test[3]] - 1) / np.log(100.0 / st)
                M.p = {"AC": k, "DC": k}
    return M


def catalogue_model():
    """no tests: the catalogue's rated torque at every temperature and its engagement times"""
    tests = [(F(t, lin), [1.0]) for lin in ("O1", "O2") for t in (20, 320)]
    M = R.Model(tests, CAT)
    M.p = {"AC": 0.0, "DC": 0.0}
    return M


# ------------------------------------------------------------------ hoist record variants
def hoists(miss=()):
    """the hoists with some of the record readings missed:
    'log' the whole maintenance log; 'reeve' H05's re-reeving; 'inverter' the three inverter retrofits (and with them
    the fast lowering); 'fast' only the fast lowering; 'twospeed' the slow-speed working stops of H02 and H09;
    'lower_speed' contactor hoists' emergency stop lowering at the motor's rated speed instead of the register's
    lowering speed; 'fast_base' fast lowering taken from the register's lowering speed"""
    H = copy.deepcopy(H0)
    if "log" in miss or "reeve" in miss:
        H["H05"].update(falls=4.0, load=20000.0, hook=420.0)
    if "log" in miss or "inverter" in miss:
        for hid in ("H04", "H08", "H12"):
            h = H[hid]
            h["inverter"] = False
            h["fast"] = None
    if "fast" in miss:
        for hid in ("H04", "H08"):
            H[hid]["fast"] = None
    if "twospeed" in miss:
        for h in H.values():
            h["slow"] = 1.0
    reg = {r["hoist"]: r for r in R.rows(DATA, "hoist_register.csv")}
    for hid, h in H.items():
        h["k"] = h["D"] / (2 * h["falls"] * h["ratio"])
        if not h["inverter"]:
            r = reg[hid]
            k_reg = float(r["drum_pitch_diameter_mm"]) / 1000 / (2 * float(r["falls"]) * float(r["gearbox_ratio"]))
            h["w_low"] = float(r["lowering_speed_rated_load_m_per_min"]) / 60 / k_reg
            if "lower_speed" in miss:
                h["w_low"] = h["w0"]
        if "fast_base" in miss and h["fast"]:
            h["fast_base"] = True
    return H


# ------------------------------------------------------------------ physics variants
VARIANT_FLAGS = dict(
    hold_eff=False,        # holding with the gear's efficiency credited (MS-14 says without)
    backdrive="retro",     # 'retro': 2 - 1/eta; 'eta': the forward efficiency for the load driving the gear
    engage_phase=True,     # the engagement delay in the working stops and the emergency stops
    stop_heating=True,     # the disc heats through an emergency stop (False: friction held at the duty temperature)
    decel_case="hoist",    # 'hoist': hoisting the rated load; 'empty': the empty hook only; 'lower': lowering rated
    decel_T="reached",     # 'reached': highest torque over the temperatures reached; 'duty': at the duty temperature
    duty_T="peak",         # 'peak': the periodic peak; 'mean': the time-average lining temperature
)


def margins_variant(M, h, size, st=R.SETTINGS, **flags):
    """solve.margins with VARIANT_FLAGS switches; with the defaults it is solve.margins"""
    f = dict(VARIANT_FLAGS)
    f.update(flags)
    b = M.cat[size]
    lin = b["lining"]
    st = np.asarray(st, float)

    def torque(T):
        return st / 100 * b["Mr"] * M.ratio(T, lin)

    eb = 2 - 1 / h["eta"] if f["backdrive"] == "retro" else h["eta"]
    te = M.engage(size, st, h["sw"]) if f["engage_phase"] else np.zeros_like(st)
    Tp = np.full_like(st, h["Tamb"])
    if not h["inverter"]:
        m = h["lf"] * h["load"]
        J = R.inertia(h, m, b)
        Lh, Ll = R.static(h, m) / h["eta"], R.static(h, m) * eb
        wh = np.maximum(h["w0"] * h["slow"] - Lh / J * te, 0.0)
        wl = h["w_low"] * h["slow"] + Ll / J * te
        dt = 3600.0 / h["stops"]
        a = np.exp(-dt * b["H"] / b["C"])
        T = Tp.copy()
        for _ in range(100):
            tb = torque(T)
            runaway = tb <= Ll
            eh = tb * J * wh ** 2 / (2 * (tb + Lh))
            el = tb * J * wl ** 2 / (2 * np.maximum(tb - Ll, 1e-9))
            if f["duty_T"] == "peak":
                rise = np.maximum(eh + a * el, el + a * eh) / (b["C"] * (1 - a * a))
            else:
                rise = (eh + el) / (2 * dt) / b["H"]
            T = 0.5 * T + 0.5 * np.where(runaway, 5000.0, np.minimum(h["Tamb"] + rise, 5000.0))
        Tp = T
    load_hold = R.static(h, h["load"]) * (h["eta"] if f["hold_eff"] else 1.0)
    hold = torque(Tp) / (R.HOLD * load_hold) - 1
    cases = [(h["load"], h["w_low"])]
    if h["fast"]:
        base = h["w_low"] if h.get("fast_base") else h["w0"]
        cases.append((h["fast"][1] * h["load"], h["fast"][0] * base))
    travel = np.full_like(st, np.inf)
    Tend = Tp.copy()
    for m, w in cases:
        J = R.inertia(h, m, b)
        L = R.static(h, m) * eb
        w1 = w + L / J * te
        ang = w * te + 0.5 * L / J * te ** 2
        T = Tp.copy()
        live = np.ones_like(st, bool)
        for _ in range(60000):
            tb = torque(T if f["stop_heating"] else Tp)
            acc = (L - tb) / J
            stuck = live & ((acc >= 0) | (T > 1500))
            ang[stuck] = np.inf
            live &= ~stuck
            if not live.any():
                break
            dts = np.where(live, np.minimum(R.DT, w1 / np.maximum(-acc, 1e-9)), 0.0)
            ang += np.where(live, (w1 + 0.5 * acc * dts) * dts, 0.0)
            T = T + np.where(live, tb * w1 * dts / b["C"], 0.0)
            w1 = w1 + np.where(live, acc * dts, 0.0)
            live &= w1 > 1e-9
        travel = np.minimum(travel, h["slim"] / (h["k"] * ang) - 1)
        Tend = np.maximum(Tend, T)
    temp = R.TLIM / np.maximum(Tp, Tend) - 1
    hi = np.minimum(np.maximum(Tp, Tend), 1500)
    Ts = h["Tamb"] + np.linspace(0, 1, 120)[:, None] * (hi - h["Tamb"])[None, :]
    tmax = np.max(torque(Ts), axis=0) if f["decel_T"] == "reached" else torque(Tp)
    gearbox = h["glim"] / tmax - 1
    if f["decel_case"] == "hoist":
        J = R.inertia(h, h["load"], b)
        decel = h["amax"] / ((tmax + R.static(h, h["load"]) / h["eta"]) * h["k"] / J) - 1
    elif f["decel_case"] == "empty":
        J = R.inertia(h, 0.0, b)
        decel = h["amax"] / ((tmax + R.static(h, 0.0) / h["eta"]) * h["k"] / J) - 1
    else:
        J = R.inertia(h, h["load"], b)
        decel = h["amax"] / ((tmax - R.static(h, h["load"]) * eb) * h["k"] / J) - 1
    return dict(hold=hold, travel=travel, decel=decel, temp=temp, gearbox=gearbox, Tp=Tp, Tend=Tend)


@contextlib.contextmanager
def physics(**flags):
    saved = R.margins
    if flags:
        R.margins = lambda M, h, size, st=R.SETTINGS: margins_variant(M, h, size, st, **flags)
    try:
        yield
    finally:
        R.margins = saved


def run(plan=None, seed=SEED, cls=R.Model, H=None, reach=R.REACH, tests=None, M=None, same_lining=False,
        engagement=None, **flags):
    """select with the reference's rule on a plan (or given reports / model) and return (picks, n, fails)"""
    if M is None:
        tests = tests if tests is not None else lab(plan or REF_PLAN, seed)
        M = model(tests, cls, same_lining=same_lining, engagement=engagement)
    with physics(**flags):
        picks = R.select(M, H or H0, reach=reach)
    n, fails = grade(picks)
    return picks, n, fails


def fmt_picks(picks):
    return " ".join("%s:%s/%d" % (hid, p[1], p[2]) for hid, p in picks.items())
