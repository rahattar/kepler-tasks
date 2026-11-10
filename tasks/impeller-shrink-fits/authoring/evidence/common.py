"""Shared machinery for the evidence scripts: an in-process copy of the laboratory (same readings as
environment/rig/lab.py for the same seed and test order), the reference's model with switches for the routes, and
grading against the sealed definition.
"""
import json
import math
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
sys.path.insert(0, os.path.join(ROOT, "solution"))
import isim as S  # noqa: E402
import solve  # noqa: E402

DATA = os.path.join(ROOT, "environment", "data")
SEED = json.load(open(os.path.join(ROOT, "authoring", "provenance", "seed.json")))["seed"]
IDS = list(S.PARTS)
SEEDS = list(range(5301, 5321))
REF_PLAN = [("26NiCrMoV14-5", 190), ("FV520B", 375), ("Ti-6Al-4V", 285)]   # the order solution/solve.py runs them
PART_PLAN = [("FV520B", 375), ("Ti-6Al-4V", 285), ("26NiCrMoV14-5", 190)]


class Lab:
    """the laboratory of environment/rig/lab.py, in process"""

    def __init__(self, seed=SEED):
        self.seed, self.n, self.log = seed, 0, []

    def cte(self, mat, T):
        self.n += 1
        if self.n > S.BUDGET:
            raise RuntimeError("over the booking")
        rng = np.random.default_rng([self.seed, self.n, 2, list(S.LABMAT).index(mat), int(T)])
        v = S.lab_cte(S.LABMAT[mat], int(T), rng)
        self.log.append((mat, int(T), v))
        return v


def grade(sheet):
    res = {k: S.part_ok(k, *sheet[k]) for k in IDS}
    n = sum(ok for ok, _ in res.values())
    worst = min(IDS, key=lambda k: min(res[k][1].values()))
    wq = min(res[worst][1], key=lambda q: res[worst][1][q])
    return n, res, (worst, wq, res[worst][1][wq])


def least(res, q):
    return min(m[q] for _, m in res.values())


class Agent(solve.Model):
    """the reference model with switches"""

    def __init__(self, mats, P, C, bay=True, bay_clear=True, seat_growth=True, flat=False, assumed=None, use_mill=True):
        super().__init__(mats, P, C, None, bay, use_mill)
        self.bay_clear, self.sg, self.flat, self.assumed = bay_clear, seat_growth, flat, assumed or {}

    def cte(self, mat, T):
        if mat in self.assumed:
            Tm, am = self.assumed[mat]
            a100 = self.m[mat]["a100"]
            return a100 + (am - a100) * (T - 100.0) / (Tm - 100.0)
        if self.flat and mat == "FV520B" and mat in self.meas and T > 100:
            return self.meas[mat][1]
        return super().cte(mat, T)

    def seat_bay(self, j):
        return j["seat_meas"] if self.bay_clear else self.seat20(j)

    def running(self, j):
        dd, hoop = super().running(j)
        if not self.sg:
            f = self.C["trip"]
            w = self.omega(f)
            s = self.m[solve.ROTOR]
            b = j["d"] / 2e3
            dd += 2e3 * s["rho"] * w * w * b ** 3 * (1 - s["nu"]) / (4 * s["E"] * 1e6)
        return dd, hoop


def solve_route(seed=SEED, plan=REF_PLAN, use_log=True, trip=None, bay=True, bay_clear=True, seat_growth=True,
                flat=False, assumed=None, pick="top", allowance=0.006, oven="need+20", use_mill=True,
                mic=True, spin=True, recoat=True):
    """one route: returns ({part: (bore mm, oven C)}, lab log)

    plan: the dilatometer tests [(lab material, T)], in order
    pick: "top" (top less 2 um, or less allowance x oven expansion if clearance-limited), "mid" or "min+2" of the
          window the route computes
    """
    mats, P, C = solve.load(DATA, use_log, mic, spin, recoat)
    if trip:
        C["trip"] = trip
    A = Agent(mats, P, C, bay, bay_clear, seat_growth, flat, assumed, use_mill)
    lab = Lab(seed)
    for mat, T in plan:
        A.meas[mat] = (T, lab.cte(mat, T) * 1e-6)
    sheet = {}
    for k, j in P.items():
        if pick == "top":
            um = solve.pick(A, j, allowance)
        else:
            W = [um for um in range(1, 700) if A.ret_ok(j, um) and A.stress_ok(j, um) and A.clear_ok(j, um, j["Tlim"])]
            if not W:
                um = solve.pick(A, j, allowance)
            elif pick == "mid":
                um = W[len(W) // 2]
            else:
                um = W[0] + 2
        T = int(j["Tlim"]) if oven == "limit" else (A.oven(j, um) - 20 if oven == "need" else A.oven(j, um))
        sheet[k] = (round(A.seat20(j) - um * 1e-3, 3), int(T))
    return sheet, lab.log
