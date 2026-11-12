"""Prototype of the full method on the truth-side solver (slow, plain): the readings overrule the records.

Every reading is modelled as   run level + gauge zero - elevation head - friction loss(theta) + scatter,
with a level for every run and a zero for every gauge fitted along with theta (a two-way layout, so the residual
is the doubly centred matrix of reading + head + loss). theta starts as the C of the groups the register leaves
open. If the fit is not as good as the gauges' scatter allows, one more thing is let go at a time: a registered
C, a valve's factor, two ports entered against each other, a run's flow; the one that restores the fit is kept.

    python3 isolate.py TAG [SEED]
"""
import itertools
import math
import sys

import numpy as np
from scipy.optimize import least_squares

import gen
import hyd
from explore import parse, valve_pipes

SD = 0.105            # scatter 0.1 psi and reading to 0.1 psi
GOOD = 1.6            # a fit is as good as the gauges allow below this reduced chi-square


class Model:
    def __init__(self, system, runs):
        self.system = system
        self.base = system["riser_base"]
        self.g = [self.base] + list(system["gauge_ports"])
        self.runs = runs
        z = {n: system["nodes"][n]["z"] for n in system["nodes"]}
        self.h = np.array([hyd.PSI_PER_FT * (z[n] - z[self.base]) for n in self.g])
        self.Y = np.array([[r["read"][n] for n in self.g] for r in runs])
        self.outs = {o["id"]: o for o in system["outlets"]}
        self.reg = {g: (v["C"] if v["C"] is not None else 100.0) for g, v in system["groups"].items()}
        self.null = [g for g, v in system["groups"].items() if v["C"] is None]
        self.cache = {}
        self.nsolve = 0

    def losses(self, C, vf, flows):
        """Friction loss from the base to every gauge, each run (zero rows for static runs)."""
        net = hyd.Network(self.system, C, vf)
        L = np.zeros(self.Y.shape)
        for k, r in enumerate(self.runs):
            if r["outlet"] is None:
                continue
            q = flows.get(k, r["flow"])
            p, _a, _b, Q = net.solve({self.base: 100.0}, demand={self.outs[r["outlet"]]["node"]: q},
                                     q0=self.cache.get(k))
            self.nsolve += 1
            self.cache[k] = Q
            L[k] = [100.0 - self.h[i] - p[n] for i, n in enumerate(self.g)]
        return L

    def fit(self, free_C=(), free_valves=(), swap=None, free_flow=None):
        free_C = list(self.null) + [g for g in free_C if g not in self.null]
        free_valves = list(free_valves)
        Y = self.Y.copy()
        if swap:
            i, j = self.g.index(swap[0]), self.g.index(swap[1])
            Y[:, [i, j]] = Y[:, [j, i]]
        nC, nV = len(free_C), len(free_valves)

        def unpack(x):
            C = dict(self.reg)
            for g, v in zip(free_C, x[:nC]):
                C[g] = float(math.exp(v))
            vf = {p: float(math.exp(v)) for p, v in zip(free_valves, x[nC:nC + nV])}
            fl = {free_flow: self.runs[free_flow]["flow"] * float(math.exp(x[-1]))} if free_flow is not None else {}
            return C, vf, fl

        def resid(x):
            C, vf, fl = unpack(x)
            E = Y + self.h[None, :] + self.losses(C, vf, fl)
            E = E - E.mean(axis=1, keepdims=True) - E.mean(axis=0, keepdims=True) + E.mean()
            return E.ravel() / SD

        x0 = [math.log(self.reg[g]) for g in free_C] + [math.log(3.0)] * nV + ([0.0] if free_flow is not None else [])
        lo = [math.log(40.0)] * nC + [0.0] * nV + ([math.log(0.3)] if free_flow is not None else [])
        hi = [math.log(150.0)] * nC + [math.log(5000.0)] * nV + ([math.log(3.0)] if free_flow is not None else [])
        R, P = Y.shape
        dof = R * P - R - P + 1 - len(x0)
        if not x0:
            r = resid(np.array([]))
            return dict(C=dict(self.reg), vf={}, fl={}, chi=float(r @ r) / dof, r=r)
        sol = least_squares(resid, x0, bounds=(lo, hi), x_scale=0.1, diff_step=1e-3)
        C, vf, fl = unpack(sol.x)
        return dict(C=C, vf=vf, fl=fl, chi=float(sol.fun @ sol.fun) / dof, r=sol.fun)

    def candidates(self):
        out = [("C", g) for g in sorted(self.system["groups"]) if g not in self.null]
        out += [("valve", p) for p in valve_pipes(self.system)]
        out += [("swap", pair) for pair in itertools.combinations(self.g[1:], 2)]
        out += [("flow", k) for k, r in enumerate(self.runs) if r["outlet"] is not None]
        return out

    def with_(self, found):
        kw = dict(free_C=[v for k, v in found if k == "C"], free_valves=[v for k, v in found if k == "valve"])
        for k, v in found:
            if k == "swap":
                kw["swap"] = v
            if k == "flow":
                kw["free_flow"] = v
        return self.fit(**kw)

    def isolate(self, depth=2, verbose=True):
        found = []
        best = self.with_(found)
        if verbose:
            print("  as recorded: chi %.1f" % best["chi"])
        while best["chi"] > GOOD and len(found) < depth:
            trials = []
            for c in self.candidates():
                if c in found or (c[0] in ("swap", "flow") and any(f[0] == c[0] for f in found)):
                    continue
                t = self.with_(found + [c])
                trials.append((t["chi"], c, t))
            trials.sort(key=lambda t: t[0])
            if verbose:
                print("  best five: " + "; ".join("%s %s chi %.1f" % (c[0], c[1], chi) for chi, c, _t in trials[:5]))
            found.append(trials[0][1])
            best = trials[0][2]
        return found, best


def main(tag, seed=1):
    import specs
    spec = [s for s in specs.EXAMPLES + specs.HIDDEN_SPECS if s["tag"] == tag][0]
    system, truth, rows, actual, res = gen.make(spec, seed)
    m = Model(system, parse(system, rows))
    found, best = m.isolate()
    d = hyd.design_demand(system, best["C"], best["vf"])
    print("%s found %s chi %.2f  P %+.2f%% Q %+.2f%%  (%d solves)" % (
        tag, found, best["chi"], 100 * (d["pressure_psi"] / res["pressure_psi"] - 1),
        100 * (d["flow_gpm"] / res["flow_gpm"] - 1), m.nsolve), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1)
