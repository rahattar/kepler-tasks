#!/usr/bin/env python3
"""Airflow at every survey point of a district package, to VS-4."""
import sys, os, json, subprocess
import numpy as np
import pandas as pd

BIGWORK = ("RESUPPORTED", "ENLARGED")


def load(pkg):
    rd = lambda f: pd.read_csv(os.path.join(pkg, f), dtype=str, keep_default_na=False)
    d = {k: rd(k + ".csv") for k in ["branches", "surveys", "work_log", "regulators", "doors",
                                     "fans", "fan_curves", "log", "points"]}
    with open(os.path.join(pkg, "district.json")) as f:
        d["district"] = json.load(f)
    return d


class Net:
    def __init__(self, br):
        self.names = list(br["branch"])
        self.idx = {b: i for i, b in enumerate(self.names)}
        nodes = sorted(set(br["from_node"]) | set(br["to_node"]))
        nodes.remove("ATM")
        self.nodes = nodes
        nid = {n: i for i, n in enumerate(nodes)}
        self.fr = np.array([nid.get(n, -1) for n in br["from_node"]])
        self.to = np.array([nid.get(n, -1) for n in br["to_node"]])
        nb, nn = len(self.names), len(nodes)
        A = np.zeros((nn, nb))  # outflow positive
        for j in range(nb):
            if self.fr[j] >= 0: A[self.fr[j], j] += 1
            if self.to[j] >= 0: A[self.to[j], j] -= 1
        self.A = A
        self.nb, self.nn = nb, nn
        self.fans = {}  # branch index -> (x, y)

    def fanP(self, q):
        P = np.zeros(self.nb); dP = np.zeros(self.nb)
        for j, (x, y) in self.fans.items():
            k = int(np.clip(np.searchsorted(x, q[j]) - 1, 0, len(x) - 2))
            s = (y[k + 1] - y[k]) / (x[k + 1] - x[k])
            P[j] = y[k] + s * (q[j] - x[k]); dP[j] = s
        return P, dP

    def solve(self, R, q0=None):
        nb, nn, A = self.nb, self.nn, self.A
        q = np.full(nb, 1.0) if q0 is None else q0.copy()
        p = np.zeros(nn)
        # branch eq: p_fr - p_to - (R q|q| - P(q)) = 0 ; A^T p = p_fr - p_to (ATM=0)
        def resid(q, p):
            P, _ = self.fanP(q)
            return np.concatenate([A @ q, A.T @ p - (R * q * np.abs(q) - P)])
        if q0 is None:
            # initial: linear solve with R*|q|~R*20
            for _ in range(3):
                q, p = self._newton_step(R, q, p, lin=True)
        r = resid(q, p); nr = np.linalg.norm(r)
        for it in range(200):
            dq, dpp = self._newton_step(R, q, p, delta=True)
            t = 1.0
            while True:
                qn, pn = q + t * dq, p + t * dpp
                rn = resid(qn, pn); nrn = np.linalg.norm(rn)
                if nrn < nr or t < 1e-4: break
                t *= 0.5
            q, p, r, nr = qn, pn, rn, nrn
            if np.max(np.abs(t * dq)) < 1e-9 * max(1, np.max(np.abs(q))) and nr < 1e-6:
                break
        return q, p

    def _newton_step(self, R, q, p, lin=False, delta=False):
        nb, nn, A = self.nb, self.nn, self.A
        P, dP = self.fanP(q)
        J = np.zeros((nn + nb, nn + nb))
        J[:nn, :nb] = A
        J[nn:, nb:] = A.T
        g = 2 * R * np.abs(q) - dP
        g = np.maximum(g, 1e-9 + 1e-6 * R)
        J[nn:, :nb] = -np.diag(g)
        F = np.concatenate([A @ q, A.T @ p - (R * q * np.abs(q) - P)])
        if lin:
            g2 = R * np.maximum(np.abs(q), 10.0)
            J[nn:, :nb] = -np.diag(g2)
            # solve A q = 0, A^T p - g2 q = -(P - dP q)... approximate fan as P at q
            rhs = np.concatenate([np.zeros(nn), -(P - dP * q) * 0 - P])
            rhs = np.concatenate([np.zeros(nn), -P])
            s = np.linalg.solve(J, rhs)
            return s[:nb], s[nb:]
        s = np.linalg.solve(J, -F)
        return s[:nb], s[nb:]


def main(pkg, out):
    d = load(pkg)
    br = d["branches"]
    net = Net(br)
    kind = dict(zip(br["branch"], br["kind"]))
    item = dict(zip(br["branch"], br["item"]))
    R = np.zeros(net.nb)
    for i, r in br.iterrows():
        if r["kind"] in ("stopping", "fan"):
            R[i] = float(r["resistance_Ns2_m8"])
    # airways
    sv = d["surveys"].copy()
    sv["dp"] = sv["dp_Pa"].astype(float); sv["q"] = sv["q_m3_s"].astype(float)
    wl = d["work_log"]
    lastwork = {}
    for _, r in wl.iterrows():
        if r["work"].strip() in BIGWORK:
            lastwork[r["branch"]] = max(lastwork.get(r["branch"], ""), r["date"])
    need = []
    for b in net.names:
        if kind[b] != "airway": continue
        s = sv[sv["branch"] == b].sort_values("date")
        if len(s) and s["date"].iloc[-1] > lastwork.get(b, ""):
            r = s.iloc[-1]; R[net.idx[b]] = r["dp"] / (r["q"] * abs(r["q"]))
        else:
            need.append(b)
    if need:
        allow = int(d["district"].get("survey_allowance", 0))
        order = need[:allow]
        try:
            res = subprocess.run(["pqsurvey", pkg] + order, capture_output=True, text=True, timeout=20)
            for line in res.stdout.strip().splitlines():
                f = line.split(",")
                if len(f) == 3 and f[0] in net.idx:
                    try:
                        dp, q = float(f[1]), float(f[2])
                        R[net.idx[f[0]]] = dp / (q * abs(q)); need.remove(f[0])
                    except ValueError:
                        pass
        except Exception as e:
            print("pqsurvey failed:", e, file=sys.stderr)
        for b in need:  # fallback: stale survey
            s = sv[sv["branch"] == b].sort_values("date")
            if len(s):
                r = s.iloc[-1]; R[net.idx[b]] = r["dp"] / (r["q"] * abs(r["q"]))
            print("no current survey for", b, file=sys.stderr)
    # fans
    fc = d["fan_curves"]
    for _, r in d["fans"].iterrows():
        c = fc[(fc["model"] == r["model"]) & (fc["blade_setting"].astype(float) == float(r["blade_setting"]))]
        x = c["flow_m3_s"].astype(float).values; y = c["pressure_Pa"].astype(float).values
        o = np.argsort(x, kind="stable")
        net.fans[net.idx[r["branch"]]] = (x[o], y[o])
    regs = {}
    for _, r in d["regulators"].iterrows():
        regs[(r["regulator"], int(float(r["setting"])))] = float(r["resistance_Ns2_m8"])
    doors = {r["door"]: (float(r["resistance_closed_Ns2_m8"]), float(r["resistance_open_Ns2_m8"]))
             for _, r in d["doors"].iterrows()}
    fanj = sorted(net.fans)
    passive = Passive(net, fanj)
    log = d["log"].sort_values("time", kind="stable")
    logrows = list(log.itertuples(index=False))
    t0 = logrows[0].time
    state = {}
    def Rstate():
        Rt = R.copy()
        for j, b in enumerate(net.names):
            k = kind[b]
            if k == "regulator":
                Rt[j] = regs[(item[b], int(float(state[item[b]])))]
            elif k == "door":
                c, o = doors[item[b]]
                Rt[j] = o if state[item[b]].lower() == "open" else c
        return Rt
    # group log by time
    groups = []
    for r in logrows:
        if groups and groups[-1][0] == r.time:
            groups[-1][1].append(r)
        else:
            groups.append((r.time, [r]))
    for r in groups[0][1]:
        state[r.item] = r.setting.strip()
    curves = [net.fans[j] for j in fanj]
    rduct = np.array([R[j] for j in fanj])
    ucache = {}
    def unit(Rt):
        key = Rt.tobytes()
        if key not in ucache:
            ucache[key] = passive.unit(Rt)
        return ucache[key]
    Rt = Rstate()
    qu, Qu = unit(Rt)  # flows at unit FH suction (1 Pa), total Q at 1 Pa
    Req = 1.0 / Qu ** 2
    qf = np.array([c[0][-1] for c in curves]) * 0.98
    qf = fans_settle(curves, rduct, Req, Req, qf)
    snaps = [(t0, qf.copy(), qu, Qu)]
    for tm, rows in groups[1:]:
        for r in rows:
            state[r.item] = r.setting.strip()
        Rt = Rstate()
        qu2, Qu2 = unit(Rt)
        Req2 = 1.0 / Qu2 ** 2
        qf = fans_settle(curves, rduct, Req, Req2, qf)
        Req, qu, Qu = Req2, qu2, Qu2
        snaps.append((tm, qf.copy(), qu, Qu))
    stimes = [s[0] for s in snaps]
    import bisect
    pts = d["points"]
    with open(out, "w") as f:
        f.write("point,flow_m3_s\n")
        for _, r in pts.iterrows():
            k = bisect.bisect_right(stimes, r["time"]) - 1
            _, qf_, qu_, Qu_ = snaps[max(k, 0)]
            j = net.idx[r["branch"]]
            Qt = qf_.sum()
            if j in fanj:
                v = qf_[fanj.index(j)]
            else:
                v = qu_[j] * Qt / Qu_
            f.write("%s,%.6f\n" % (r["point"], v))


def fanP(c, q):
    x, y = c
    k = int(np.clip(np.searchsorted(x, q) - 1, 0, len(x) - 2))
    s = (y[k + 1] - y[k]) / (x[k + 1] - x[k])
    return y[k] + s * (q - x[k])


def fan_eval(c, q):
    x, y = c
    k = int(np.clip(np.searchsorted(x, q, side="right") - 1, 0, len(x) - 2))
    s = (y[k + 1] - y[k]) / (x[k + 1] - x[k])
    return y[k] + s * (q - x[k]), s


def fans_settle(curves, rd, Ra, Rb, q):
    """Fan flows follow the network resistance continuously from Ra to Rb (quasi-static change),
    dropping to another stable state where the one they are on ceases to exist."""
    q = q.astype(float).copy()
    n = len(q)
    def F(q, Req):
        Q = q.sum(); s = Req * Q * abs(Q)
        f = np.empty(n); J = np.empty((n, n))
        for i in range(n):
            P, dP = fan_eval(curves[i], q[i])
            f[i] = P - rd[i] * q[i] * abs(q[i]) - s
            J[i, :] = -2 * Req * abs(Q)
            J[i, i] += dP - 2 * rd[i] * abs(q[i])
        return f, J
    def transient(q, Req):
        for it in range(200000):
            f, J = F(q, Req)
            lam = np.max(np.abs(np.linalg.eigvals(J)))
            h = 0.2 / max(lam, 1e-6)
            q = q + h * f
            if np.max(np.abs(f)) < 1e-6:
                return q, True
            if it > 50 and np.max(np.abs(f)) < 1e-2:
                break
        return q, False
    def stable_newton(q, Req):
        for it in range(50):
            f, J = F(q, Req)
            dq = np.linalg.solve(J, -f)
            q = q + dq
            if np.max(np.abs(dq)) < 1e-10:
                f, J = F(q, Req)
                return q, np.all(np.linalg.eigvals(J).real < 0)
        return q, False
    nramp = 1 if Ra == Rb else 40
    for k in range(1, nramp + 1):
        Req = np.exp(np.log(Ra) + (np.log(Rb) - np.log(Ra)) * k / nramp)
        qn, ok = stable_newton(q, Req)
        if not ok or np.max(np.abs(qn - q)) > 3.0:
            qt = q
            for rep in range(20):
                qt, conv = transient(qt, Req)
                qn, ok = stable_newton(qt, Req)
                if ok and np.max(np.abs(qn - qt)) < 1.0:
                    break
        q = qn
    return q


class Passive:
    """The district without its fans: unit suction at the fan house node."""
    def __init__(self, net, fanj):
        self.net = net
        self.keep = [j for j in range(net.nb) if j not in fanj]
        fh = net.fr[fanj[0]]
        self.fh = fh
        self.nodes = [i for i in range(net.nn) if i != fh]
        self.A = net.A[np.ix_(self.nodes, self.keep)]
        # pressure contribution: A^T p, with p_FH = -1 fixed
        self.b = -net.A[fh, self.keep]  # column for p_FH ; times p_FH(-1)
    def unit(self, Rfull):
        R = Rfull[self.keep]; A = self.A; nn, nb = A.shape
        pfh = -1.0
        q = np.ones(nb); p = np.zeros(nn)
        J = np.zeros((nn + nb, nn + nb)); J[:nn, :nb] = A; J[nn:, nb:] = A.T
        cst = -self.b * pfh  # A_full^T p includes A[fh]^T * pfh
        # linear start
        for it in range(100):
            F = np.concatenate([A @ q, A.T @ p + cst - R * q * np.abs(q)])
            if it == 0:
                g = R * 1.0
                J[nn:, :nb] = -np.diag(g)
                s = np.linalg.solve(J, np.concatenate([np.zeros(nn), -cst]))
                q, p = s[:nb], s[nb:]
                continue
            g = np.maximum(2 * R * np.abs(q), 1e-12)
            J[nn:, :nb] = -np.diag(g)
            s = np.linalg.solve(J, -F)
            q = q + s[:nb]; p = p + s[nb:]
            if np.max(np.abs(s[:nb])) < 1e-12 * max(1.0, np.abs(q).max()):
                break
        qf = np.zeros(self.net.nb); qf[self.keep] = q
        # total into FH
        Q = (net_in := -(self.net.A[self.fh] @ qf))
        return qf, Q


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
