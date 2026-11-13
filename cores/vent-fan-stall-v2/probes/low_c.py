#!/usr/bin/env python3
"""Airflow at every survey point of a district package, to VS-4.

Usage: python3 airflow.py PACKAGE_DIR OUT_CSV
"""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd


def read(pkg, name, **kw):
    return pd.read_csv(os.path.join(pkg, name), dtype=str, **kw)


def airway_resistances(pkg, branches):
    surveys = read(pkg, "surveys.csv")
    work = read(pkg, "work_log.csv")
    allowance = int(json.load(open(os.path.join(pkg, "district.json")))["survey_allowance"])
    surveys["dp"] = surveys.dp_Pa.astype(float)
    surveys["q"] = surveys.q_m3_s.astype(float)
    airways = list(branches.loc[branches.kind == "airway", "branch"])
    latest = {}
    for _, r in surveys.sort_values("date", kind="stable").iterrows():
        latest[r.branch] = (r.date, r.dp, r.q)
    changing = work[work.work.str.strip().isin(["RESUPPORTED", "ENLARGED"])]
    lastwork = changing.groupby("branch").date.max().to_dict()

    stale, sameday = [], []
    for a in airways:
        if a not in latest:
            stale.append((a, "9999"))
        elif a in lastwork:
            if latest[a][0] < lastwork[a]:
                stale.append((a, lastwork[a]))
            elif latest[a][0] == lastwork[a]:
                sameday.append((a, lastwork[a]))
    # most recent work first: if the order cannot cover all, older ones are taken
    order = [a for a, _ in sorted(stale, key=lambda x: x[1], reverse=True)]
    order += [a for a, _ in sameday]
    order = order[:allowance]
    fresh = {}
    if order:
        try:
            out = subprocess.run(["pqsurvey", pkg] + order, capture_output=True,
                                 text=True, timeout=20).stdout
            for line in out.strip().splitlines():
                parts = line.strip().split(",")
                if len(parts) != 3 or parts[0] == "branch":
                    continue
                try:
                    fresh[parts[0]] = (float(parts[1]), float(parts[2]))
                except ValueError:
                    pass
        except Exception as e:  # pragma: no cover
            print("pqsurvey failed:", e, file=sys.stderr)
    missing = [a for a, _ in stale if a not in fresh]
    if missing:
        print("warning: no current survey for", missing, file=sys.stderr)
    R = {}
    for a in airways:
        if a in fresh:
            dp, q = fresh[a]
        elif a in latest:
            _, dp, q = latest[a]
        else:
            raise SystemExit("airway %s has no survey" % a)
        R[a] = dp / (q * abs(q))
    return R


class Network:
    def __init__(self, branches, fixedR, fans, curves):
        nodes = sorted(set(branches.from_node) | set(branches.to_node) - {"ATM"})
        nodes = [n for n in nodes if n != "ATM"]
        self.idx = {n: i for i, n in enumerate(nodes)}
        self.nn = len(nodes)
        self.names = list(branches.branch)
        self.nb = len(self.names)
        self.fi = np.array([self.idx.get(n, -1) for n in branches.from_node])
        self.ti = np.array([self.idx.get(n, -1) for n in branches.to_node])
        self.R = np.array([fixedR.get(b, np.nan) for b in self.names], dtype=float)
        # fans: index -> (flows, pressures)
        self.fans = {}
        for _, f in fans.iterrows():
            c = curves[(curves.model == f.model) &
                       (curves.blade_setting.astype(float) == float(f.blade_setting))]
            qs = c.flow_m3_s.astype(float).values
            ps = c.pressure_Pa.astype(float).values
            o = np.argsort(qs)
            self.fans[self.names.index(f.branch)] = (qs[o], ps[o])
        # incidence (nodes x branches): +1 leaving from-node, -1 into to-node
        A = np.zeros((self.nn, self.nb))
        for j in range(self.nb):
            if self.fi[j] >= 0:
                A[self.fi[j], j] += 1
            if self.ti[j] >= 0:
                A[self.ti[j], j] -= 1
        self.A = A

    @staticmethod
    def fanP(qs, ps, q):
        # linear interpolation, linear extrapolation beyond the table
        k = np.clip(np.searchsorted(qs, q) - 1, 0, len(qs) - 2)
        s = (ps[k + 1] - ps[k]) / (qs[k + 1] - qs[k])
        return ps[k] + s * (q - qs[k]), s

    def setup(self):
        A = self.A
        fj = np.array(sorted(self.fans))
        self.fj = fj
        self.nf = len(fj)
        mask = np.ones(self.nb, bool)
        mask[fj] = False
        self.mask = mask
        G = A.T.copy()  # dp = G @ p
        self.Gn, self.An = G[mask], A[:, mask]
        self.Gf, self.Af = G[fj], A[:, fj]
        self.tabs = [self.fans[j] for j in fj]
        smax = 0.0
        for qs, ps in self.tabs:
            sl = np.diff(ps) / np.diff(qs)
            smax = max(smax, sl.max())
        self.c_pseudo = 2.0 * max(smax, 1.0) + 5.0

    def F(self, x, R, c=0.0, qold=None):
        nn, nf = self.nn, self.nf
        p, qf = x[:nn], x[nn:]
        Rn = R[self.mask]
        Rf = R[self.fj]
        dp = self.Gn @ p
        q = np.sign(dp) * np.sqrt(np.abs(dp) / Rn)
        d = 1.0 / (2.0 * Rn * np.maximum(np.abs(q), 1e-6))
        P = np.empty(nf); S = np.empty(nf)
        for i, (qs, ps) in enumerate(self.tabs):
            P[i], S[i] = self.fanP(qs, ps, qf[i])
        r1 = self.An @ q + self.Af @ qf
        r2 = Rf * qf * np.abs(qf) - P - self.Gf @ p
        J = np.empty((nn + nf, nn + nf))
        J[:nn, :nn] = (self.An * d) @ self.Gn
        J[:nn, nn:] = self.Af
        J[nn:, :nn] = -self.Gf
        J[nn:, nn:] = np.diag(2 * Rf * np.abs(qf) - S)
        if c:
            r2 = r2 + c * (qf - qold)
            J[nn:, nn:] += c * np.eye(nf)
        return np.concatenate([r1, r2]), J, q

    def newton(self, x, R, c=0.0, qold=None, maxit=60, tol=1e-9):
        r, J, q = self.F(x, R, c, qold)
        for it in range(maxit):
            if np.abs(r).max() < tol:
                return x, r, J, q, True
            try:
                step = np.linalg.solve(J, -r)
            except np.linalg.LinAlgError:
                step = np.linalg.lstsq(J, -r, rcond=None)[0]
            n0 = np.linalg.norm(r)
            t = 1.0
            while True:
                xn = x + t * step
                rn, Jn, qn = self.F(xn, R, c, qold)
                if np.linalg.norm(rn) < (1 - 1e-4 * t) * n0 or t < 1e-6:
                    break
                t *= 0.5
            x, r, J, q = xn, rn, Jn, qn
        return x, r, J, q, np.abs(r).max() < tol

    def stable(self, J):
        nn = self.nn
        Jpp, Jpf = J[:nn, :nn], J[:nn, nn:]
        Jfp, Jff = J[nn:, :nn], J[nn:, nn:]
        Sc = Jff - Jfp @ np.linalg.solve(Jpp, Jpf)
        return np.linalg.eigvals(Sc).real.min() > 0

    def relax(self, x, R):
        """Follow the fans' own dynamics to the steady state they settle at."""
        c = self.c_pseudo
        for it in range(5000):
            qold = x[self.nn:].copy()
            x, r, J, q, ok = self.newton(x, R, c, qold, maxit=30)
            dq = np.abs(x[self.nn:] - qold).max()
            if dq < 1e-4:
                break
            if it % 20 == 19:
                # try to finish with plain Newton
                xn, rn, Jn, qn, okn = self.newton(x.copy(), R, maxit=30)
                if okn and self.stable(Jn) and np.abs(xn[self.nn:] - x[self.nn:]).max() < 1.0:
                    return xn
        xn, rn, Jn, qn, okn = self.newton(x, R)
        return xn

    def track(self, x, R):
        """Newton step on the branch from x; relax if the branch is lost."""
        if x is None:
            qf0 = np.array([qs[0] + 0.8 * (qs[-1] - qs[0]) for qs, ps in self.tabs])
            P0 = np.array([self.fanP(qs, ps, qq)[0] for (qs, ps), qq in zip(self.tabs, qf0)])
            x = np.concatenate([np.full(self.nn, -0.5 * P0.mean()), qf0])
            x = self.relax(x, R)
            return x
        xn, r, J, q, ok = self.newton(x.copy(), R)
        span = max(qs[-1] - qs[0] for qs, ps in self.tabs)
        if ok and self.stable(J) and np.abs(xn[self.nn:] - x[self.nn:]).max() < 0.05 * span:
            return xn
        return self.relax(x, R)

    def flows(self, x, R):
        r, J, q = self.F(x, R)
        full = np.empty(self.nb)
        full[self.mask] = q
        full[self.fj] = x[self.nn:]
        return full, np.abs(r).max()


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    pkg = os.path.abspath(pkg)
    br = read(pkg, "branches.csv")
    for c in br.columns:
        br[c] = br[c].fillna("").str.strip()
    regs = read(pkg, "regulators.csv")
    doors = read(pkg, "doors.csv")
    fans = read(pkg, "fans.csv")
    curves = read(pkg, "fan_curves.csv")
    log = read(pkg, "log.csv")
    pts = read(pkg, "points.csv")

    fixedR = airway_resistances(pkg, br)
    for _, r in br.iterrows():
        if r.kind in ("stopping", "fan"):
            fixedR[r.branch] = float(r.resistance_Ns2_m8)
    net = Network(br, fixedR, fans, curves)

    regR = {(r.regulator, int(float(r.setting))): float(r.resistance_Ns2_m8)
            for _, r in regs.iterrows()}
    doorR = {r.door: (float(r.resistance_closed_Ns2_m8), float(r.resistance_open_Ns2_m8))
             for _, r in doors.iterrows()}
    item_branches = {}
    for j, r in br.iterrows():
        if r.kind in ("regulator", "door"):
            item_branches.setdefault(r["item"], []).append((j, r.kind))

    log["t"] = pd.to_datetime(log.time.str.strip())
    log = log.reset_index().sort_values(["t", "index"], kind="stable")
    times = sorted(log.t.unique())
    state = {}
    states = []  # (time, R vector)
    for t in times:
        for _, r in log[log.t == t].iterrows():
            state[r["item"].strip()] = r.setting.strip()
        Rv = net.R.copy()
        for it, lst in item_branches.items():
            s = state.get(it)
            for j, kind in lst:
                if kind == "regulator":
                    Rv[j] = regR[(it, int(float(s)))]
                else:
                    c, o = doorR[it]
                    Rv[j] = c if s.lower() == "closed" else o
        states.append((t, Rv))

    pts["t"] = pd.to_datetime(pts.time.str.strip())
    tarr = np.array([s[0] for s in states], dtype="datetime64[ns]")
    k = np.searchsorted(tarr, pts.t.values.astype("datetime64[ns]"), side="right") - 1
    k = np.maximum(k, 0)
    bidx = {b: j for j, b in enumerate(net.names)}
    flows = np.zeros(len(pts))
    net.setup()
    cache = {}
    x = None
    NSUB = 12
    for kk in range(len(states)):
        Rnew = states[kk][1]
        if x is None:
            x = net.track(None, Rnew)
        else:
            Rold = states[kk - 1][1]
            # a change is made by hand over a minute or more: follow it through
            for s_ in range(1, NSUB + 1):
                lam = s_ / NSUB
                Rl = np.exp((1 - lam) * np.log(Rold) + lam * np.log(Rnew))
                x = net.track(x, Rl)
        q, res = net.flows(x, Rnew)
        if res > 1e-6:
            print("warning: state", kk, "residual", res, file=sys.stderr)
        cache[kk] = q
    for i, (kk, b) in enumerate(zip(k, pts.branch.str.strip())):
        flows[i] = cache[kk][bidx[b]]
    pd.DataFrame({"point": pts.point.str.strip(), "flow_m3_s": np.round(flows, 6)}).to_csv(out, index=False)


if __name__ == "__main__":
    main()
