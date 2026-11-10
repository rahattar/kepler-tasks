"""Shared machinery for the evidence scripts: an in-process copy of the laboratory (same readings as
environment/rig/lab.py for the same seed and test order), the reference's model with switches for the routes, and
grading against the sealed definition.
"""
import copy
import json
import math
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
sys.path.insert(0, os.path.join(ROOT, "solution"))
import sfsim as S  # noqa: E402
import solve  # noqa: E402

DATA = os.path.join(ROOT, "environment", "data")
SEED = json.load(open(os.path.join(ROOT, "authoring", "provenance", "seed.json")))["seed"]
IDS = list(S.JOINTS)
CONDS = ("dry", "oiled", "paste")
SEEDS = list(range(7101, 7121))


class Lab:
    """the laboratory of environment/rig/lab.py, in process"""

    def __init__(self, seed=SEED):
        self.seed, self.n, self.log = seed, 0, []

    def _rng(self, key):
        self.n += 1
        if self.n > S.BUDGET:
            raise RuntimeError("over the booking")
        return np.random.default_rng([self.seed, self.n] + key)

    def slip(self, mat, prep, p, shrink=True):
        p = int(max(S.LAB_P[0], min(S.LAB_P[1], round(p))))
        rng = self._rng([1, list(S.LABMAT).index(mat), CONDS.index(prep), p, int(shrink)])
        v = S.lab_slip(S.LABMAT[mat], prep, p, shrink, rng)
        self.log.append(("slip", mat, prep, p, shrink, v))
        return v

    def cte(self, mat, T):
        rng = self._rng([2, list(S.LABMAT).index(mat), int(T)])
        v = S.lab_cte(S.LABMAT[mat], int(T), rng)
        self.log.append(("cte", mat, int(T), v))
        return v


def grade(fits):
    res = {k: S.joint_ok(k, *fits[k]) for k in IDS}
    n = sum(ok for ok, _ in res.values())
    worst = min(IDS, key=lambda k: min(res[k][1][q] for q in ("slip", "stress", "clear", "limit")))
    wm = res[worst][1]
    wq = min(("slip", "stress", "clear", "limit"), key=lambda q: wm[q])
    return n, res, (worst, wq, wm[wq])


def smallest_margin(res):
    return min(min(m[q] for q in ("slip", "stress", "clear")) for _, m in res.values())




class Agent(solve.Model):
    """the reference model with switches"""

    def __init__(self, mats, J, steel_cte=None, smooth=True, running_stress=True, clip_gain=False, running=True,
                 cte_assumed=None, cte_T=solve.CTE_T):
        super().__init__(mats, J, steel_cte)
        self.sm, self.rs, self.clip, self.run_, self.assumed, self.cte_T = smooth, running_stress, clip_gain, running, cte_assumed, cte_T

    def cte(self, mat, T):
        if mat == "steel" and self.assumed is not None and T > 100:
            a100 = self.m[mat]["a100"]
            return a100 + (self.assumed - a100) * (T - 100.0) / (self.cte_T - 100.0)
        if mat == "steel" and self.meas is not None and T > 100:
            a100 = self.m[mat]["a100"]
            return a100 + (self.meas - a100) * (T - 100.0) / (self.cte_T - 100.0)
        return self.m[mat]["a100"]

    def smooth(self, j):
        return super().smooth(j) if self.sm else 0.0

    def states(self, j):
        dd, hoop = self.running(j)
        if self.clip:
            dd = min(dd, 0.0)
        if not self.run_:
            return [(0.0, 0.0)]
        return [(0.0, 0.0), (dd, hoop)]

    def stress_ok(self, j, m):
        dmax = m * 1e-3 + solve.span_mm(j["d"]) / 2 - self.smooth(j)
        sts = self.states(j) if self.rs else [(0.0, 0.0)]
        return all(self.vm(j, self.p(j, dmax + dd), rot) <= j["Re"] / 1.2 for dd, rot in sts)

    def torque_ok(self, j, m, mu_fn):
        dmin = m * 1e-3 - solve.span_mm(j["d"]) / 2 - self.smooth(j)
        for dd, _ in self.states(j):
            p = self.p(j, dmin + dd)
            if mu_fn(j, p) * p * math.pi * j["d"] ** 2 * j["L"] / 2e3 < 1.5 * j["T"]:
                return False
        return True


def load(log=("J07", "J10", "J11")):
    mats, J = solve.load(DATA)
    if "J10" not in log:
        J["J10"]["di"] = 0.0
    if "J11" not in log:
        J["J11"]["T"] *= 55.0 / 75.0
    if "J07" not in log:
        J["J07"]["prep"] = "oiled"
    return mats, J


def pairs(J):
    out = {}
    for k, j in J.items():
        out.setdefault((j["mat"], j["prep"]), []).append(k)
    return out


def solve_route(seed=SEED, log=("J07", "J10", "J11"), cte="measure", cte_T=solve.CTE_T, cte_assumed=None,
                smooth=True, running_stress=True, clip_gain=False, running=True, friction="lowest", kpair=None,
                shrink=True, flat_p=None, handbook=None, pick="top", allowance=0.02, oven="need+20", order=1):
    """one route: returns ({joint: (um, C)}, lab log)

    cte: "measure" (one dilatometer test of steel at cte_T), "table" (the 20-100 C value), "assume" (cte_assumed, 1/K)
    friction: "lowest" / "highest" / "median" (each pair at that joint pressure of the pair), "flat" (all at flat_p),
              "handbook" (no tests: handbook[prep]), "none" (no tests, top pick only)
    kpair: None, or (p1, p2): steel-dry tested at both pressures and the power law fitted applied to every pair
    pick: "top" (top less 1 um, or less allowance x oven expansion if clearance-limited), "mid" or "min+3" of the window
          computed with the friction law
    """
    mats, J = load(log)
    lab = Lab(seed)
    A = Agent(mats, J, None, smooth, running_stress, clip_gain, running, cte_assumed, cte_T)
    if cte == "measure" and order == 1:
        A.meas = lab.cte("steel", cte_T) * 1e-6
    # the top of each range (independent of friction)
    tops = {}

    def find_tops():
        for k, j in J.items():
            ts = [m for m in range(1, 2000) if A.stress_ok(j, m) and A.clear_ok(j, m, j["Tlim"])]
            if not ts:
                tops[k] = (1, False)
                continue
            m = max(ts)
            tops[k] = (m, not A.clear_ok(j, m + 1, j["Tlim"]))
    find_tops()

    def top_pick(k):
        m, heat = tops[k]
        j = J[k]
        if heat:
            return m - int(math.ceil(allowance * j["d"] * A.cte(j["mat"], j["Tlim"]) * (j["Tlim"] - 20) * 1e3))
        return m - 1

    # friction tests
    P = pairs(J)
    tab = {}
    fit_k = None
    if friction not in ("handbook", "none"):
        if kpair:
            a = lab.slip("steel", "dry", kpair[0], shrink)
            b = lab.slip("steel", "dry", kpair[1], shrink)
            fit_k = -math.log(b / a) / math.log(kpair[1] / kpair[0])
            tab[("steel", "dry")] = (kpair[0], a)
        for key, ks in P.items():
            if key in tab:
                continue
            ps = [A.least_p(J[k], top_pick(k)) for k in ks]
            p = {"lowest": min(ps), "highest": max(ps), "median": float(np.median(ps)), "flat": flat_p}[friction]
            tab[key] = (int(max(10, min(200, round(p)))), lab.slip(solve.LABMAT[key[0]], key[1], p, shrink))
    if cte == "measure" and order == 2:
        A.meas = lab.cte("steel", cte_T) * 1e-6
        find_tops()

    def mu_fn(j, p):
        if friction == "handbook":
            return handbook[j["prep"]]
        p0, m0 = tab[(j["mat"], j["prep"])]
        return m0 * (max(p, 1.0) / p0) ** (-fit_k) if fit_k is not None else m0

    fits = {}
    for k, j in J.items():
        if pick == "top" or friction == "none":
            m = top_pick(k)
        else:
            W = [m for m in range(max(1, tops[k][0] - 400), tops[k][0] + 1) if A.torque_ok(j, m, mu_fn)
                 and A.stress_ok(j, m) and A.clear_ok(j, m, j["Tlim"])]
            if not W:
                m = top_pick(k)
            elif pick == "mid":
                m = W[len(W) // 2]
            else:
                m = W[0] + 3
        T = int(j["Tlim"]) if oven == "limit" else A.oven(j, m)
        fits[k] = (int(m), int(T))
    return fits, lab.log


def show(fits):
    return " ".join("%s:%d/%d" % (k[1:], *fits[k]) for k in IDS)


def least(res, q):
    return min(m[q] for _, m in res.values())
