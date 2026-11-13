#!/usr/bin/env python3
"""Airflow at every survey point of a district package, to VS-4."""
import sys, os, json, subprocess
import numpy as np
import pandas as pd

RHO_NOTE = "incompressible, no NVP"


def load(pkg):
    rd = lambda f: pd.read_csv(os.path.join(pkg, f), dtype=str, keep_default_na=False)
    P = {f[:-4]: rd(f) for f in ["branches.csv", "surveys.csv", "work_log.csv", "regulators.csv",
                                  "doors.csv", "fans.csv", "fan_curves.csv", "log.csv", "points.csv"]}
    with open(os.path.join(pkg, "district.json")) as fh:
        P["district"] = json.load(fh)
    return P


def airway_resistances(P, pkg, order=True):
    br = P["branches"]
    sv = P["surveys"].copy()
    sv["dp"] = sv["dp_Pa"].astype(float)
    sv["q"] = sv["q_m3_s"].astype(float)
    sv = sv[(sv["q"].abs() > 1e-6) & (sv["dp"] * sv["q"] > 0)]
    wl = P["work_log"]
    wl = wl[wl["work"].str.strip().str.upper().isin(["RESUPPORTED", "ENLARGED"])]
    lastwork = wl.groupby("branch")["date"].max().to_dict()
    R = {}
    need = []
    for b in br.loc[br["kind"] == "airway", "branch"]:
        s = sv[sv["branch"] == b]
        if b in lastwork:
            # a survey on the day of the work cannot be placed before or after it: not used
            s = s[s["date"] > lastwork[b]]
        if len(s) == 0:
            need.append(b)
            continue
        s = s.sort_values("date", kind="stable")
        r = s.iloc[-1]
        R[b] = r["dp"] / (r["q"] * abs(r["q"]))
    if need and order:
        allow = int(P["district"].get("survey_allowance", 0))
        req = need[:allow]
        try:
            out = subprocess.run(["pqsurvey", pkg] + req, capture_output=True, text=True,
                                 timeout=20).stdout
            for line in out.strip().splitlines():
                parts = [x.strip() for x in line.split(",")]
                if len(parts) != 3 or parts[0] == "branch":
                    continue
                try:
                    dp, q = float(parts[1]), float(parts[2])
                except ValueError:
                    continue
                if parts[0] in need and q != 0:
                    R[parts[0]] = dp / (q * abs(q))
        except Exception as e:
            sys.stderr.write("pqsurvey failed: %s\n" % e)
    missing = [b for b in need if b not in R]
    for b in missing:  # last resort: the latest survey on file, though it predates the work
        s = sv[sv["branch"] == b].sort_values("date", kind="stable")
        if len(s):
            r = s.iloc[-1]; R[b] = r["dp"] / (r["q"] * abs(r["q"]))
    return R, missing


class Net:
    def __init__(self, P, Rair):
        br = P["branches"]
        self.names = list(br["branch"])
        self.bidx = {b: i for i, b in enumerate(self.names)}
        nodes = sorted(set(br["from_node"]) | set(br["to_node"]))
        nodes = [n for n in nodes if n != "ATM"]
        self.nidx = {n: i for i, n in enumerate(nodes)}
        self.nb, self.nn = len(self.names), len(nodes)
        self.fi = np.array([self.nidx.get(n, -1) for n in br["from_node"]])
        self.ti = np.array([self.nidx.get(n, -1) for n in br["to_node"]])
        A = np.zeros((self.nn, self.nb))  # node balance: inflow - outflow
        for j in range(self.nb):
            if self.fi[j] >= 0: A[self.fi[j], j] -= 1
            if self.ti[j] >= 0: A[self.ti[j], j] += 1
        self.A = A
        # incidence for pressure drop: dp_j = p_from - p_to = D @ p
        self.D = -A.T
        from scipy.linalg import null_space
        self.C = null_space(A)
        self.kind = list(br["kind"])
        self.item = list(br["item"])
        self.Rbase = np.zeros(self.nb)
        for j, b in enumerate(self.names):
            k = self.kind[j]
            if k == "airway":
                self.Rbase[j] = Rair.get(b, np.nan)
            elif k in ("stopping", "fan"):
                self.Rbase[j] = float(br["resistance_Ns2_m8"].iloc[j])
        reg = P["regulators"]
        self.regtab = {}
        for r, g in reg.groupby("regulator"):
            self.regtab[r] = {int(float(s)): float(v) for s, v in zip(g["setting"], g["resistance_Ns2_m8"])}
        self.doortab = {r["door"]: (float(r["resistance_closed_Ns2_m8"]), float(r["resistance_open_Ns2_m8"]))
                        for _, r in P["doors"].iterrows()}
        # fans
        fc = P["fan_curves"]
        self.fan = {}
        for _, f in P["fans"].iterrows():
            g = fc[(fc["model"] == f["model"]) &
                   (fc["blade_setting"].astype(float) == float(f["blade_setting"]))]
            x = g["flow_m3_s"].astype(float).values
            y = g["pressure_Pa"].astype(float).values
            self.fan[self.bidx[f["branch"]]] = (x, y)
        self.fanidx = np.array(sorted(self.fan))

    def resist(self, state):
        R = self.Rbase.copy()
        for j in range(self.nb):
            k = self.kind[j]
            if k == "regulator":
                R[j] = self.regtab[self.item[j]][int(float(state[self.item[j]]))]
            elif k == "door":
                c, o = self.doortab[self.item[j]]
                R[j] = o if str(state[self.item[j]]).strip().lower() == "open" else c
        return R

    def fanp(self, q):
        Pf = np.zeros(self.nb); dPf = np.zeros(self.nb)
        for j, (x, y) in self.fan.items():
            k = np.searchsorted(x, q[j]) - 1
            k = min(max(k, 0), len(x) - 2)
            s = (y[k + 1] - y[k]) / (x[k + 1] - x[k])
            Pf[j] = y[k] + s * (q[j] - x[k]); dPf[j] = s
        return Pf, dPf

    def residual(self, q, p, R, L, qold, dt):
        Pf, dPf = self.fanp(q)
        dp = self.D @ p
        F1 = dp + Pf - R * q * np.abs(q)
        if dt is not None:
            F1 = F1 - L * (q - qold) / dt
        F2 = self.A @ q
        return F1, F2, dPf

    def step(self, q, p, R, L=None, qold=None, dt=None, tol=1e-10, maxit=60):
        """Newton on (q,p). With dt: one implicit-Euler step of the inertial dynamics."""
        nb, nn = self.nb, self.nn
        for it in range(maxit):
            F1, F2, dPf = self.residual(q, p, R, L, qold, dt)
            err = max(np.abs(F1).max() / (1 + np.abs(R * q * q).max()), np.abs(F2).max() / (1 + np.abs(q).max()))
            if err < tol:
                return q, p, True
            dg = dPf - 2 * R * np.abs(q)
            if dt is not None:
                dg = dg - L / dt
            dg = np.where(np.abs(dg) < 1e-12, -1e-12, dg)
            # block elimination: dg*dq + D dpv = -F1 ; A dq = -F2
            # dq = (-F1 - D dpv)/dg ; A(-F1 - D dpv)/dg = -F2
            Ad = self.A / dg
            M = Ad @ self.D
            rhs = F2 - Ad @ F1
            try:
                dpv = np.linalg.solve(M, rhs)
            except np.linalg.LinAlgError:
                return q, p, False
            dq = (-F1 - self.D @ dpv) / dg
            # damping
            lam = 1.0
            mx = np.abs(dq).max()
            lim = 0.5 * (1 + np.abs(q).max())
            if mx > lim:
                lam = lim / mx
            q = q + lam * dq; p = p + lam * dpv
        return q, p, False


def stable(net, q):
    Pf, dPf = net.fanp(q)
    g = dPf - 2 * net.Rcur * np.abs(q)
    M = net.C.T @ (g[:, None] * net.C)
    try:
        np.linalg.cholesky(-M)
        return True
    except np.linalg.LinAlgError:
        return False


def transient(net, R, q, p):
    """Let the air settle from (q, p) under resistances R: implicit Euler on the inertial dynamics."""
    L = np.ones(net.nb)
    dt = 0.01
    for k in range(3000):
        qn, pn, ok = net.step(q.copy(), p.copy(), R, L, q, dt, tol=1e-9, maxit=30)
        if not ok:
            dt = max(dt * 0.3, 1e-6)
            continue
        change = np.abs(qn - q).max()
        q, p = qn, pn
        if change < 1e-7 and dt > 1:
            break
        dt = min(dt * 1.3, 50.0)
    return q, p


def solve_state(net, R0, R1, q, p, nsteps=20):
    """Follow the air from the steady state (q, p) under R0 while the resistances move to R1."""
    lr0, lr1 = np.log(R0), np.log(R1)
    if np.allclose(lr0, lr1):
        nsteps = 1
    for i in range(1, nsteps + 1):
        R = np.exp(lr0 + (lr1 - lr0) * i / nsteps)
        net.Rcur = R
        qn, pn, ok = net.step(q.copy(), p.copy(), R, tol=1e-11, maxit=40)
        if ok and np.abs(qn - q).max() < 0.2 * (1 + np.abs(q).max()) and stable(net, qn):
            q, p = qn, pn
            continue
        # the operating point is lost: the air finds its own way
        q, p = transient(net, R, q, p)
        q, p, ok = net.step(q.copy(), p.copy(), R, tol=1e-12, maxit=40)
    return q, p


def initial(net, R):
    """Steady state from a start where each fan is on the falling side of its curve."""
    q = np.zeros(net.nb); p = np.zeros(net.nn)
    saved = dict(net.fan)
    for j, (x, y) in saved.items():
        k = int(np.argmax(y[len(y)//3:])) + len(y)//3
        xs, ys = x[k:], y[k:]
        # extend the falling side linearly back to zero flow
        s = (ys[1] - ys[0]) / (xs[1] - xs[0])
        net.fan[j] = (np.r_[0.0, xs], np.r_[ys[0] - s * xs[0], ys])
    for j in saved:
        q[j] = 1.0
    q, p, ok = net.step(q, p, R, tol=1e-10, maxit=500)
    net.fan = saved
    return q, p


def main(pkg, out):
    P = load(pkg)
    Rair, missing = airway_resistances(P, pkg, order=not os.environ.get("NO_ORDER"))
    if missing:
        sys.stderr.write("no valid survey for %s\n" % missing)
    net = Net(P, Rair)
    log = P["log"].copy()
    log["t"] = pd.to_datetime(log["time"])
    log = log.sort_values("t", kind="stable")
    t0 = log["t"].iloc[0]
    state = {}
    for _, r in log[log["t"] == t0].iterrows():
        state[r["item"]] = r["setting"]
    changes = log[log["t"] > t0]
    pts = P["points"].copy()
    pts["t"] = pd.to_datetime(pts["time"])
    times = sorted(set(changes["t"]))
    # start-up: fans brought up from rest with the opening settings
    R = net.resist(state)
    q, p = initial(net, R)
    q, p, ok = net.step(q, p, R, tol=1e-12, maxit=100)
    net.Rcur = R
    if not ok or not stable(net, q):
        q, p = transient(net, R, np.where(np.isfinite(q), q, 0.0), np.where(np.isfinite(p), p, 0.0))
        q, p, ok = net.step(q, p, R, tol=1e-12, maxit=100)
    epochs = [(t0, q.copy())]
    for t in times:
        for _, r in changes[changes["t"] == t].iterrows():
            state[r["item"]] = r["setting"]
        Rn = net.resist(state)
        q, p = solve_state(net, R, Rn, q, p)
        R = Rn
        epochs.append((t, q.copy()))
    et = np.array([e[0].value for e in epochs])
    res = []
    for _, r in pts.iterrows():
        k = np.searchsorted(et, r["t"].value, side="right") - 1
        k = max(k, 0)
        res.append((r["point"], epochs[k][1][net.bidx[r["branch"]]]))
    with open(out, "w") as fh:
        fh.write("point,flow_m3_s\n")
        for a, v in res:
            fh.write("%s,%.4f\n" % (a, v))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
