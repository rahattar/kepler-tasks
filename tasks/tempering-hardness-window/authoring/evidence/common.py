"""Shared helpers for the evidence scripts: the sealed definition, a laboratory emulator that gives exactly the
readings the real laboratory (environment/rig/lab.py) gives for the same tests in the same order, the reference
solution's model, and grading.
"""
import json
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
sys.path.insert(0, os.path.join(ROOT, "solution"))
import tsim as S  # noqa: E402
import solve  # noqa: E402

DATA = os.path.join(ROOT, "environment", "data")
SEED = json.load(open(os.path.join(ROOT, "authoring", "provenance", "seed.json")))["seed"]


class Lab:
    """the laboratory's readings and allowance, as lab.py gives them"""

    def __init__(self, seed=SEED, budget=None, truth=None):
        self.seed, self.idx, self.used = seed, 0, 0
        self.budget = S.BUDGET if budget is None else budget
        self.truth = truth          # optional replacement for S.tempered (alternative truths in the hedge study)
        self.log = []

    def __call__(self, heat, T, D=25.0, loc="half-radius", double=False):
        n = 2 if double else 1
        T, D = int(T), float(D)
        assert S.LAB_T[0] <= T <= S.LAB_T[1] and S.LAB_D[0] <= D <= S.LAB_D[1]
        if self.used + n > self.budget:
            raise RuntimeError("allowance exhausted")
        self.idx += 1
        self.used += n
        rng = np.random.default_rng([self.seed, self.idx, list(S.HEATS).index(heat), T, int(D),
                                     0 if loc == "surface" else 1, n])
        if self.truth is None:
            h = S.lab_temper(heat, T, rng, D, loc, n)
        else:
            h = round(self.truth(heat, T, D, loc, 2.0, n) + rng.normal(0, S.NOISE), 1)
        self.log.append((heat, T, D, loc, n, h))
        return h


def grade(temps):
    """per-batch (ok, hardness) and the number right"""
    res = {b: S.batch_ok(b, int(temps[b])) for b in S.BATCHES}
    return res, sum(ok for ok, h in res.values())


def margin(b, T):
    """signed margin to the nearer limit of the range, HRC (negative outside; -99 below the grade's minimum)"""
    part, heat, D, loc, (lo, hi) = S.BATCHES[b]
    if T < S.TMIN[S.HEATS[heat][0]]:
        return -99.0
    h = S.batch_hardness(b, T)
    return min(h - lo, hi - h)


def run_reference(seed=SEED, plan=None, quiet=True, **kw):
    lab = Lab(seed)
    temps, tests = solve.solve(DATA, None, lab=lab, plan=plan or solve.PLAN, log=(lambda *a: None) if quiet else print, **kw)
    return temps, tests, lab


def run(plan, seed=SEED, rec_fn=None, model_cls=None, model_kw=None, lab_dT=0, after=None, budget=None):
    """the reference's procedure with replaceable parts: plan is a list of (batch, double) (the heat is the batch's
    heat in the records used), rec_fn edits the records, model_cls replaces the model, after(model, tests) edits the
    offsets once the tests are in. Returns the setpoints and the laboratory."""
    rec = solve.Records(DATA)
    if rec_fn:
        rec_fn(rec)
    model = (model_cls or solve.Model)(rec, **(model_kw or {}))
    lab = Lab(seed, budget=budget)
    tests = []
    for b, double in plan:
        r = rec.batches[b]
        heat, D, loc = r["heat"], float(r["ruling_section_diameter_mm"]), r["hardness_location"]
        Dl, locl = getattr(model, "test_piece", lambda D, loc: (D, loc))(D, loc)
        Tp = model.choose(b)
        Tl = model.lab_temperature(b, Tp, double) + lab_dT
        h = lab(heat, Tl, Dl, locl, double)
        model.offset[heat] = model.boff[b] = h - model.raw(heat, Tl, Dl, locl, 4.0 if double else 2.0)
        tests.append((heat, b, Tl, Dl, locl, double, h))
    if after:
        after(model, tests)
    return {b: int(model.choose(b)) for b in rec.batches}, lab


REF_PLAN = [(b, d) for h, b, d in solve.PLAN]


def summary(temps):
    res, n = grade(temps)
    worst = min(S.BATCHES, key=lambda b: margin(b, temps[b]))
    return n, worst, margin(worst, temps[worst]), [b for b in S.BATCHES if not res[b][0]]
