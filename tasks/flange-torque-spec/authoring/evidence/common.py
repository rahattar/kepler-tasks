"""Shared helpers for the evidence studies. Everything here reads the agent's documents (environment/data) and the
sealed definition (tests/sealed) and emulates the rig exactly as environment/rig/trial.py does: a budget of 8 slots, a
single-bolt trial uses one and a pattern trial two, and the measurement noise is seeded by (seed, first slot index,
joint). So the numbers below are what the shipped scenario gives. All percentages are percent of the target preload;
the window is +/-6 percent; the gate is 15 of 16.
"""
import csv
import os
import re
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DATA = os.path.join(ROOT, "environment", "data")
sys.path.insert(0, os.path.join(ROOT, "tests", "sealed"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import jointsim as J  # noqa: E402
import grade_torques  # noqa: E402

SEED = grade_torques.SEED
TRUTH = J.seal(SEED)
IDS = [j[0] for j in J.JOINTS]
BUDGET = 8
# coating allowance of a 6g external thread, |es|/4 (ISO 965-1 fundamental deviations; ISO 4042). Public data.
ALLOW_UM = {"M12": 8.5, "M16": 9.5, "M20": 10.5, "M24": 12.0}


def rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def items(path):
    return {r["item"]: r["value"] for r in rows(path)}


SCHED = {r["joint_id"]: r for r in rows(os.path.join(DATA, "joint_schedule.csv"))}
HB = items(os.path.join(DATA, "fastener_handbook.csv"))
K_HB = float(HB["nut_factor_K_zinc_plated"])
REUSED = {r["joint_id"]: len(re.findall(r"\d{4}-\d{2}", r["note"])) for r in rows(os.path.join(DATA, "maintenance_log.csv"))}
RECORDS = {}
for _name in sorted(os.listdir(os.path.join(DATA, "examples"))):
    _e = items(os.path.join(DATA, "examples", _name))
    RECORDS[_e["joint_id"]] = _e


def feat(j):
    """(thread, Ra, plating, earlier assemblies) for a schedule joint or an example record"""
    r = SCHED.get(j) or RECORDS[j]
    return (r["thread"], float(r["flank_roughness_Ra_um"]), float(r["plating_thickness_um"]),
            int(REUSED.get(j, 0)))


def d_m(j):
    return float(SCHED[j]["thread"][1:]) * 1e-3


def target_N(j):
    return float(SCHED[j]["target_preload_per_bolt_kN"]) * 1e3


def proof_N(j):
    return float(HB["proof_load_kN_%s_grade_%s" % (SCHED[j]["thread"], SCHED[j]["grade"])]) * 1e3


def record_ratios():
    """assembled / single-bolt preload per flange class, as read from the example records (their own sequence)"""
    out = {}
    for e in RECORDS.values():
        single = float(e["trial_bolt_preload_kN"]) * float(e["assembly_torque_Nm"]) / float(e["trial_torque_Nm"])
        out[e["flange_class"]] = float(e["assembled_preload_per_bolt_kN_measured"]) / single
    return out


def record_k():
    """the records' trials are single-bolt trials: K = T / (F d)"""
    return {eid: float(e["trial_torque_Nm"]) / (float(e["trial_bolt_preload_kN"]) * 1e3 * float(e["thread"][1:]) * 1e-3)
            for eid, e in RECORDS.items()}


class Rig:
    """emulates /opt/rig/trial.py"""

    def __init__(self, seed=SEED, truth=None):
        self.seed, self.used, self.truth = seed, 0, truth or TRUTH

    def trial(self, jid, torque=None, pattern=False):
        cost = J.PATTERN_COST if pattern else 1
        if self.used + cost > BUDGET:
            raise RuntimeError("budget exhausted")
        idx = self.used + 1
        self.used += cost
        rng = np.random.default_rng([self.seed, idx, int(jid[1:])])
        return J.trial(self.truth, jid, rng, torque, pattern)


def default_torque(j):
    return K_HB * d_m(j) * target_N(j)


def singles(rig, campaign, fraction):
    """single-bolt trials at fraction x default torque (None = default); {joint: K}"""
    out = {}
    for j in campaign:
        T, F = rig.trial(j, None if fraction is None else fraction * default_torque(j))
        out[j] = T / (F * d_m(j))
    return out


def pattern(rig, j, fraction):
    """pattern trial; returns T / (F_monitored d) = K / crew ratio"""
    T, F = rig.trial(j, None if fraction is None else fraction * default_torque(j), pattern=True)
    return T / (F * d_m(j))


def fit(meas, kind="iso", reuse="pwl", records=True):
    """reuse='pwl' (the reference): the new-thread model first, then each reused trial's excess over it against its
    number of earlier assemblies, interpolated through (0, 0) and held flat beyond the largest count measured."""
    if reuse == "pwl":
        new = {j: v for j, v in meas.items() if feat(j)[3] == 0}
        base = fit(new, kind, reuse=False, records=records)
        by_n = {}
        for j, v in meas.items():
            n = feat(j)[3]
            if n:
                by_n.setdefault(n, []).append(v - base(j))
        ns = [0] + sorted(by_n)
        dk = [0.0] + [float(np.mean(by_n[n])) for n in sorted(by_n)]
        f = lambda j: base(j) + (float(np.interp(feat(j)[3], ns, dk)) if feat(j)[3] <= ns[-1] else dk[-1])  # noqa: E731
        f.th, f.coef, f.reuse = base.th, base.coef, dict(zip(ns, dk))
        return f
    return _fit(meas, kind, reuse, records)


def _fit(meas, kind="iso", reuse=True, records=True):
    """least-squares nut-factor model on the trialled joints (and the records' single-bolt trials).
    kind: 'iso'    a + b(Ra-2) + c max(0, tp - allowance(thread)) + r n   (the reference; n earlier assemblies)
          'hinge'  one plating threshold for every size, chosen on a grid
          'linear' plating linear;  'quad' plating quadratic
    reuse: True (r n, straight line), 'sqrt' (r sqrt(n)), 'flag' (one constant offset for any reused joint), False"""
    pts = dict(meas)
    if records:
        pts.update(record_k())
    ids = list(pts)
    y = np.array([pts[j] for j in ids])

    def X(js, th):
        out = []
        for j in js:
            thr, Ra, tp, nre = feat(j)
            if kind == "iso":
                p = max(0.0, tp - ALLOW_UM[thr])
            elif kind == "hinge":
                p = max(0.0, tp - th)
            elif kind == "linear":
                p = tp - 8.0
            else:
                p = (tp - 8.0) ** 2
            row = [1.0, Ra - 2.0, p]
            if reuse == "flag":
                row.append(1.0 if nre else 0.0)
            elif reuse == "sqrt":
                row.append(float(np.sqrt(nre)))
            elif reuse:
                row.append(float(nre))
            out.append(row)
        return np.array(out)

    best = None
    for th in (np.arange(6.0, 14.01, 0.25) if kind == "hinge" else [0.0]):
        A = X(ids, th)
        b, *_ = np.linalg.lstsq(A, y, rcond=None)
        sse = float(np.sum((A @ b - y) ** 2))
        if best is None or sse < best[0]:
            best = (sse, th, b)
    _, th, b = best
    f = lambda j: float(X([j], th)[0] @ b)  # noqa: E731
    f.th, f.coef = th, b
    return f


def crew_ratios(k_single, k_eff, cls):
    """crew ratio for the measured class from a pattern trial; the other class's crew loss is its recorded loss scaled
    by the same factor (the records' check passes leave the same fraction of the loss on both flanges)"""
    rec = record_ratios()
    out = {cls: k_single / k_eff}
    m = (1.0 - out[cls]) / (1.0 - rec[cls])
    for c in rec:
        out.setdefault(c, 1.0 - m * (1.0 - rec[c]))
    return out, m


def commit(meas, pred, ratios):
    """torques for all joints: a trialled joint's measured K, the fit otherwise; divided by its class ratio"""
    return {j: (meas[j] if j in meas else pred(j)) * d_m(j) * target_N(j) / ratios[SCHED[j]["flange_class"]]
            for j in IDS}


def reference(campaign=("J01", "J03", "J06", "J08", "J09", "J13"), pj="J06", fraction=0.6, kind="iso", reuse="pwl",
              b_from_records=False, order=None):
    """the reference method with its choices exposed: single-bolt trials, one pattern trial, a fit, crew ratios"""
    rig = Rig()
    meas = singles(rig, list(order or campaign), fraction)
    k_eff = pattern(rig, pj, fraction)
    pred = fit(meas, kind, reuse)
    ks = meas[pj] if pj in meas else pred(pj)
    cls = SCHED[pj]["flange_class"]
    ratios, m = crew_ratios(ks, k_eff, cls)
    if b_from_records:
        rec = record_ratios()
        ratios = {c: (ratios[c] if c == cls else rec[c]) for c in rec}
    return commit(meas, pred, ratios), ratios, m, pred


def grade(torques):
    g = J.grade(TRUTH, torques)
    errs = {j: g["joints"][j]["err_pct"] for j in IDS}
    bad = [j for j in IDS if not g["joints"][j]["ok"]]
    return g["npass"], bad, errs, g["joints"]
