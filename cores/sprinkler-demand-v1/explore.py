"""Exploration on the truth-side solver: what a program that takes the records at their word gets, against one
that lets the readings overrule them. Not shipped to probes; it sizes the faults.

    python3 explore.py            every spec of specs.py, a table of errors

Variants:
- blind:    fits the groups the register leaves open; readings taken as written (absolute pressures)
- zeroed:   the same, each gauge referred to its own static readings
- register: every group's C free (zeroed)
- valves:   every group's C and every valve's factor free (zeroed)
"""
import math
import sys

import numpy as np
from scipy.optimize import least_squares

import gen
import hyd

SD = 0.12


def parse(system, rows):
    runs = {}
    for k, outlet, q, port, val in rows:
        r = runs.setdefault(int(k), {"outlet": outlet or None, "flow": float(q), "read": {}})
        r["read"][port] = float(val)
    return [runs[k] for k in sorted(runs)]


def offsets(system, runs):
    """Each port's reading against the base gauge's with no flow, less the elevation head: zero where the two
    gauges agree."""
    z = {n: system["nodes"][n]["z"] for n in system["nodes"]}
    base = system["riser_base"]
    st = [r for r in runs if r["outlet"] is None]
    return {p: float(np.mean([r["read"][p] - r["read"][base] + hyd.PSI_PER_FT * (z[p] - z[base]) for r in st]))
            for p in system["gauge_ports"]}


def valve_pipes(system):
    return [p["id"] for p in system["pipes"] if any(f in ("gate valve", "butterfly valve") for f in p["fittings"])]


class Fit:
    def __init__(self, system, runs, free_C, free_valves=(), zeroed=True, drop_runs=(), drop_ports=()):
        self.system, self.zeroed = system, zeroed
        self.free_C, self.free_valves = list(free_C), list(free_valves)
        self.base = system["riser_base"]
        self.ports = [p for p in system["gauge_ports"] if p not in drop_ports]
        self.flow_runs = [(k, r) for k, r in enumerate(runs, start=1) if r["outlet"] is not None
                          and k not in drop_runs]
        self.off = offsets(system, runs) if zeroed else {p: 0.0 for p in system["gauge_ports"]}
        self.outs = {o["id"]: o for o in system["outlets"]}
        self.reg = {g: (v["C"] if v["C"] is not None else 100.0) for g, v in system["groups"].items()}
        self.q0 = {}

    def unpack(self, x):
        C = dict(self.reg)
        for g, v in zip(self.free_C, x[:len(self.free_C)]):
            C[g] = float(math.exp(v))
        vf = {p: float(math.exp(v)) for p, v in zip(self.free_valves, x[len(self.free_C):])}
        return C, vf

    def resid(self, x):
        C, vf = self.unpack(x)
        net = hyd.Network(self.system, C, vf)
        out = []
        for k, r in self.flow_runs:
            pb = r["read"][self.base]
            p, _a, _b, Q = net.solve({self.base: pb}, demand={self.outs[r["outlet"]]["node"]: r["flow"]},
                                     q0=self.q0.get(k))
            self.q0[k] = Q
            out += [(r["read"][n] - self.off[n] - p[n]) / SD for n in self.ports]
        return np.array(out)

    def run(self):
        x0 = [math.log(self.reg[g]) for g in self.free_C] + [math.log(3.0)] * len(self.free_valves)
        lo = [math.log(40.0)] * len(self.free_C) + [0.0] * len(self.free_valves)
        hi = [math.log(150.0)] * len(self.free_C) + [math.log(5000.0)] * len(self.free_valves)
        if not x0:
            r = self.resid(np.array([]))
            return self.unpack([]), r
        sol = least_squares(self.resid, x0, bounds=(lo, hi), x_scale=0.1, diff_step=1e-3)
        return self.unpack(sol.x), sol.fun


def rate(system, C, vf):
    return hyd.design_demand(system, C, vf)


def report(spec, seed=1, variants=("blind", "zeroed", "register", "valves")):
    system, truth, rows, actual, res = gen.make(spec, seed)
    runs = parse(system, rows)
    null = [g for g, v in system["groups"].items() if v["C"] is None]
    allg = sorted(system["groups"])
    line = "%-6s P %6.1f Q %6.0f |" % (spec["tag"], res["pressure_psi"], res["flow_gpm"])
    out = {}
    for v in variants:
        if v == "blind":
            f = Fit(system, runs, null, zeroed=False)
        elif v == "zeroed":
            f = Fit(system, runs, null)
        elif v == "register":
            f = Fit(system, runs, allg)
        else:
            f = Fit(system, runs, allg, valve_pipes(system))
        (C, vf), r = f.run()
        d = rate(system, C, vf)
        dp = 100 * (d["pressure_psi"] / res["pressure_psi"] - 1)
        dq = 100 * (d["flow_gpm"] / res["flow_gpm"] - 1)
        rms = float(np.sqrt(np.mean(r ** 2)))
        out[v] = (dp, dq, rms, float(np.max(np.abs(r))) * SD)
        line += " %s %+5.1f%% %+4.1f%% rms %4.1f max %4.1f psi |" % (v, dp, dq, rms, out[v][3])
    print(line, flush=True)
    return out


if __name__ == "__main__":
    import specs
    which = sys.argv[1:] or None
    for spec in specs.EXAMPLES + specs.HIDDEN_SPECS:
        if which is None or spec["tag"] in which:
            report(spec)
