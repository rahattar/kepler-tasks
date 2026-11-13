#!/usr/bin/env python3
"""Airflow at every survey point of a district package, to VS-4.

Usage: python3 airflow.py PACKAGE_DIR OUT_CSV

Network: branch flows q and node pressures p (ATM = 0), with
  p_from - p_to = R q|q| - P_fan(q)  on every branch, and flow balance at every node.
Main fans in parallel with a stalling (humped) characteristic can have more than one
steady state for the same settings, so the state actually reached depends on history.
Each change of settings is therefore followed from the previous steady state by a
pseudo-transient (implicit Euler with air inertia in every branch) until the flow is
steady again, which picks the state the district really settles into.
"""
import sys, os, json, csv, subprocess
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    pkg, out_csv = sys.argv[1], sys.argv[2]
    rd = lambda n: read_csv(os.path.join(pkg, n))
    district = json.load(open(os.path.join(pkg, "district.json")))
    allowance = int(district.get("survey_allowance", 0))
    branches = rd("branches.csv")
    surveys = rd("surveys.csv")
    work = rd("work_log.csv")
    regs = {(r["regulator"], int(float(r["setting"]))): float(r["resistance_Ns2_m8"])
            for r in rd("regulators.csv")}
    doors = {r["door"]: (float(r["resistance_closed_Ns2_m8"]), float(r["resistance_open_Ns2_m8"]))
             for r in rd("doors.csv")}
    fans = {r["branch"]: r for r in rd("fans.csv")}
    curves = {}
    for r in rd("fan_curves.csv"):
        curves.setdefault((r["model"], r["blade_setting"].strip()), []).append(
            (float(r["flow_m3_s"]), float(r["pressure_Pa"])))
    log = rd("log.csv")
    points = rd("points.csv")

    # ---- airway resistances (VS-4 s.3) ----
    latest = {}  # branch -> (date, R)
    for i, r in enumerate(surveys):
        q = float(r["q_m3_s"]); dp = float(r["dp_Pa"])
        if q == 0:
            continue
        key = (r["date"], i)
        if r["branch"] not in latest or key >= latest[r["branch"]][0]:
            latest[r["branch"]] = (key, dp / (q * abs(q)))
    lastwork = {}
    for r in work:
        if r["work"].strip().upper() in ("RESUPPORTED", "ENLARGED"):
            b = r["branch"]
            lastwork[b] = max(lastwork.get(b, ""), r["date"])
    airways = [b["branch"] for b in branches if b["kind"] == "airway"]
    need = [b for b in airways
            if b not in latest or (b in lastwork and latest[b][0][0] <= lastwork[b])]
    Rair = {b: latest[b][1] for b in airways if b in latest}

    # ---- network arrays ----
    names = [b["branch"] for b in branches]
    bidx = {n: i for i, n in enumerate(names)}
    nodes = sorted({b[k] for b in branches for k in ("from_node", "to_node")} - {"ATM"})
    nidx = {n: i for i, n in enumerate(nodes)}
    nb, nn = len(branches), len(nodes)
    fi = np.array([nidx.get(b["from_node"], -1) for b in branches])
    ti = np.array([nidx.get(b["to_node"], -1) for b in branches])
    fan_k = [k for k, b in enumerate(branches) if b["kind"] == "fan"]
    fan_tab = {}
    for k in fan_k:
        f = fans.get(names[k])
        if f is None:
            f = next(x for x in fans.values() if x["fan"] == branches[k]["item"])
        tab = sorted(curves[(f["model"], f["blade_setting"].strip())])
        fan_tab[k] = (np.array([t[0] for t in tab]), np.array([t[1] for t in tab]))

    # incidence (nodes x branches): +1 leaving from-node, -1 entering to-node
    rows, cols, vals = [], [], []
    for k in range(nb):
        if fi[k] >= 0: rows.append(fi[k]); cols.append(k); vals.append(1.0)
        if ti[k] >= 0: rows.append(ti[k]); cols.append(k); vals.append(-1.0)
    A = sp.csr_matrix((vals, (rows, cols)), shape=(nn, nb))
    At = A.T.tocsr()

    def fan_eval(k, q):
        fq, fp = fan_tab[k]
        if q <= fq[0]:
            i = 1
        elif q >= fq[-1]:
            i = len(fq) - 1
        else:
            i = int(np.searchsorted(fq, q))
            i = min(max(i, 1), len(fq) - 1)
        s = (fp[i] - fp[i - 1]) / (fq[i] - fq[i - 1])
        return fp[i - 1] + s * (q - fq[i - 1]), s

    def branch_res(R, q):
        h = R * q * np.abs(q); d = 2 * R * np.abs(q)
        for k in fan_k:
            pf, s = fan_eval(k, q[k]); h[k] -= pf; d[k] -= s
        return h, d

    Lin = 1.0  # air inertia per branch (uniform)
    Znn = sp.csr_matrix((nn, nn))

    def step(R, x_old, dt, x_start):
        """Implicit Euler step; returns new x or None."""
        q_old = x_old[:nb]
        x = x_start.copy()
        for it in range(30):
            q = x[:nb]; p = x[nb:]
            h, d = branch_res(R, q)
            # branch: L(q-q_old)/dt + h(q) - (A^T p) = 0 ; node: A q = 0
            r1 = Lin * (q - q_old) / dt + h - At @ p
            r2 = A @ q
            res = np.concatenate([r1, r2])
            scale = 1.0 + np.abs(h).max()
            if np.abs(r1).max() < 1e-9 * scale and np.abs(r2).max() < 1e-10:
                return x
            J = sp.bmat([[sp.diags(Lin / dt + d), -At], [A, Znn]], format="csc")
            try:
                dx = splu(J).solve(-res)
            except Exception:
                return None
            # limit change of flow per iteration
            m = np.abs(dx[:nb]).max()
            lim = 20.0 + np.abs(q).max()
            if m > lim:
                dx *= lim / m
            x = x + dx
            if not np.all(np.isfinite(x)):
                return None
        return None

    def steady(R, x0):
        x = x0.copy(); dt = 1e-3; tsum = 0.0
        while True:
            xn = step(R, x, dt, x)
            if xn is None:
                dt *= 0.25
                if dt < 1e-9:
                    raise RuntimeError("no convergence")
                continue
            change = np.abs(xn[:nb] - x[:nb]).max()
            if change > 2.0 and dt > 1e-6:
                dt *= 0.5          # keep the trajectory resolved
                continue
            x = xn; tsum += dt
            if dt >= 1e5 and change < 1e-9:
                return x
            if change < 0.5:
                dt = min(dt * 2.0, 1e6)

    def resistances(state):
        R = np.zeros(nb)
        for k, b in enumerate(branches):
            kind = b["kind"]
            if kind == "airway":
                R[k] = Rair[b["branch"]]
            elif kind in ("stopping", "fan"):
                R[k] = float(b["resistance_Ns2_m8"])
            elif kind == "regulator":
                R[k] = regs[(b["item"], int(float(state[b["item"]])))]
            elif kind == "door":
                c, o = doors[b["item"]]
                R[k] = c if state[b["item"]].strip().lower() == "closed" else o
        return R

    # ---- settings over time ----
    times = sorted({r["time"] for r in log})
    by_time = {}
    for r in log:
        by_time.setdefault(r["time"], []).append(r)
    states = []
    st = {}
    for t in times:
        for r in by_time[t]:
            st[r["item"]] = r["setting"].strip()
        states.append(dict(st))

    # ---- the survey order: airways worked on since their latest survey ----
    if need:
        order = need
        if len(order) > allowance:
            # survey the ones carrying most of the pressure drop first (old R x flow^2)
            R0 = resistances(states[-1])
            for b in order:
                if b not in Rair:
                    R0[bidx[b]] = 1e-3
            x = steady(R0, np.concatenate([np.full(nb, 1.0), np.zeros(nn)]))
            order = sorted(order, key=lambda b: -R0[bidx[b]] * x[bidx[b]] ** 2)[:allowance]
        if order:
            try:
                out = subprocess.run(["pqsurvey", pkg] + order, capture_output=True,
                                     text=True, timeout=20).stdout
                for r in csv.DictReader(out.splitlines()):
                    q = float(r["q_m3_s"]); dp = float(r["dp_Pa"])
                    if q != 0:
                        Rair[r["branch"].strip()] = dp / (q * abs(q))
            except Exception as e:
                print("survey order failed:", e, file=sys.stderr)
        for b in need:
            Rair.setdefault(b, 1e-3)

    # ---- follow the record ----
    def newton(R, x0):
        """Steady Newton solve from x0; None unless it converges close to x0."""
        x = x0.copy()
        for it in range(25):
            q = x[:nb]; p = x[nb:]
            h, d = branch_res(R, q)
            r1 = h - At @ p; r2 = A @ q
            if np.abs(r1).max() < 1e-9 * (1 + np.abs(h).max()) and np.abs(r2).max() < 1e-10:
                return x
            J = sp.bmat([[sp.diags(d + 1e-12), -At], [A, Znn]], format="csc")
            try:
                dx = splu(J).solve(-np.concatenate([r1, r2]))
            except Exception:
                return None
            x = x + dx
            if not np.all(np.isfinite(x)) or np.abs(x[:nb] - x0[:nb]).max() > 0.05 * (5 + np.abs(x0[:nb]).max()):
                return None
        return None

    # cycle space of the network: flows that satisfy the node balances
    Ad = A.toarray()
    u, sv, vt = np.linalg.svd(Ad)
    rank = int((sv > 1e-9 * sv.max()).sum())
    C = vt[rank:].T  # nb x ncycles
    fan_arr = np.array(fan_k)

    def stable(x):
        """Linear stability of the steady state (air inertia in every branch)."""
        q = x[:nb]
        _, d = branch_res(np.asarray(Rcur[0]), q)
        if np.all(d[fan_arr] > 0):
            return True
        M = C.T @ (d[:, None] * C)
        return np.linalg.eigvalsh(M).min() > 0

    Rcur = [None]
    fan_peak = {k: fan_tab[k][0][int(np.argmax(fan_tab[k][1][1:])) + 1] for k in fan_k}

    def kick(R, x):
        """Nudge a state at the edge of stability along its least stable mode, in the
        sense that takes the fan nearest its stall point (lowest flow relative to the
        flow at its pressure peak) towards stall."""
        q = x[:nb]
        _, d = branch_res(R, q)
        kf = min(fan_k, key=lambda k: q[k] / fan_peak[k])
        e = np.zeros(nb); e[kf] = 1.0
        v = -(C @ (C.T @ e))
        v = v / max(abs(v[kf]), 1e-12)
        y = x.copy()
        y[:nb] += 3.0 * v
        return y

    def follow(R0, R1, x):
        """Quasi-static continuation from the steady state x at R0 to R1 along a
        geometric path; at a fold the flow is let go by the transient to its new state."""
        lr0, lr1 = np.log(R0), np.log(R1)
        lam, h = 0.0, 0.25
        while lam < 1.0:
            l2 = min(1.0, lam + h)
            R = np.exp(lr0 + (lr1 - lr0) * l2)
            Rcur[0] = R
            xn = newton(R, x)
            if xn is not None and not stable(xn):
                xn = None
            if xn is not None:
                x, lam = xn, l2
                h = min(h * 2, 1.0)
            else:
                h *= 0.5
                if h < 1e-5:
                    # fold: the steady branch ends here; flow moves to another state
                    xo = x; x = steady(R, kick(R, x))
                    for _ in range(3):
                        if stable(x):
                            break
                        x = steady(R, kick(R, x))
                    if os.environ.get("DBG"): print("KICK", l2, [(round(xo[k],1), round(x[k],1)) for k in fan_k], file=sys.stderr)
                    lam, h = l2, 0.25
        return x

    sols = []
    R = resistances(states[0])
    x = steady(R * 1e-3, np.zeros(nb + nn))
    x = follow(R * 1e-3, R, x)
    prevR = R
    sols.append(x[:nb].copy())
    for s in states[1:]:
        R = resistances(s)
        if not np.array_equal(R, prevR):
            x = follow(prevR, R, x)
        prevR = R
        sols.append(x[:nb].copy())
        if os.environ.get("DBG"): print(s.get("AL-1"), ["%.1f" % x[k] for k in fan_k], file=sys.stderr)

    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["point", "flow_m3_s"])
        for p in points:
            i = int(np.searchsorted(np.array(times), p["time"], side="right")) - 1
            i = max(i, 0)
            w.writerow([p["point"], "%.4f" % sols[i][bidx[p["branch"]]]])


if __name__ == "__main__":
    main()
