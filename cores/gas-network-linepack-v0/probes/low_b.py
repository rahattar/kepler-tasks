#!/usr/bin/env python3
"""Design-day minimum governor pressures to GD-3 for one network package.

Usage: python3 designday.py PACKAGE_DIR OUT_CSV
"""
import csv
import json
import math
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.linalg as spla

PATM = 1.01325
EXP = 1.82          # Q|Q|^0.82
BUILD_WORK = {"RENEWED", "RELINED", "LAID"}


def read(pkg, name):
    return pd.read_csv(os.path.join(pkg, name), dtype=str, keep_default_na=False)


def k_from(p_from_g, dp, q):
    pf = float(p_from_g) + PATM
    pt = pf - float(dp)
    q = float(q)
    if abs(q) < 1e-9:
        return None
    k = (pf * pf - pt * pt) / (q * abs(q) ** 0.82)
    if not (k > 0 and math.isfinite(k)):
        return None
    return k


def order_survey(pkg, items):
    """Place the one order; returns dict of blocks {header0: {item: row}}."""
    out = {}
    if not items:
        return out
    try:
        r = subprocess.run(["gdsurvey", pkg] + items, capture_output=True,
                           text=True, timeout=60)
        text = r.stdout
    except Exception:
        return out
    cur = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        f = [x.strip() for x in line.split(",")]
        if f[0] in ("main", "valve", "meter"):
            cur = f[0]
            out.setdefault(cur, {})
            continue
        if cur is None:
            continue
        out[cur][f[0]] = f[1:]
    return out


def main():
    pkg, out_csv = sys.argv[1], sys.argv[2]
    pkg = os.path.abspath(pkg)
    with open(os.path.join(pkg, "network.json")) as fh:
        netinfo = json.load(fh)
    allowance = int(netinfo.get("survey_allowance", 0))

    mains = read(pkg, "mains.csv")
    surveys = read(pkg, "surveys.csv")
    work = read(pkg, "work_log.csv")
    prs = read(pkg, "prs.csv")
    govs = read(pkg, "governors.csv")
    dday = read(pkg, "design_day.csv")
    custs = read(pkg, "customers.csv")
    meters = read(pkg, "customer_meters.csv")
    valves = read(pkg, "boundary_valves.csv")

    # ---- K of each main from surveys on file ----------------------------
    last_build = {}
    for _, w in work.iterrows():
        if w["work"].strip().upper() in BUILD_WORK:
            d = w["date"].strip()
            m = w["main"].strip()
            if m not in last_build or d > last_build[m]:
                last_build[m] = d
    surv_by = {}
    for _, s in surveys.iterrows():
        surv_by.setdefault(s["main"].strip(), []).append(
            (s["date"].strip(), s["p_from_barg"], s["dp_bar"], s["q_m3h"]))
    Kmap = {}
    need_main = []
    for _, m in mains.iterrows():
        name = m["main"].strip()
        lb = last_build.get(name, "")
        cands = sorted(surv_by.get(name, []), key=lambda t: t[0], reverse=True)
        k = None
        for d, pf, dp, q in cands:
            if d <= lb:
                break
            k = k_from(pf, dp, q)
            if k is not None:
                break
        if k is None:
            need_main.append(name)
        else:
            Kmap[name] = k

    open_valves = valves[valves["state"].str.strip().str.lower() == "open"]
    need_valve = [v.strip() for v in open_valves["valve"]]

    # meter mean flows for prioritising proving
    meters = meters.copy()
    meters["q"] = meters["q_m3h"].astype(float)
    meters["t"] = pd.to_datetime(meters["time"].str.strip(), format="%Y-%m-%d %H:%M")
    meters["meter"] = meters["meter"].str.strip()
    mtr_flow = meters.groupby("meter")["q"].apply(lambda s: s.abs().mean()).to_dict()
    cust_meters = [c.strip() for c in custs["meter"]]
    cust_meters.sort(key=lambda m: -mtr_flow.get(m, 0.0))

    items = []
    for lst in (need_valve, need_main, cust_meters):
        for it in lst:
            if len(items) < allowance and it not in items:
                items.append(it)
    res = order_survey(pkg, items)
    if os.environ.get("DD_DEBUG"):
        print(items, res, file=sys.stderr)

    for name, row in res.get("main", {}).items():
        try:
            k = k_from(row[0], row[1], row[2])
        except Exception:
            k = None
        if k is not None:
            Kmap[name] = k

    # fallback for mains still without K: fit log K on log L, log D
    known = [(float(m["length_m"]), float(m["diameter_mm"]), Kmap[m["main"].strip()])
             for _, m in mains.iterrows() if m["main"].strip() in Kmap]
    coef = None
    if len(known) >= 3:
        A = np.array([[1.0, math.log(L), math.log(D)] for L, D, _ in known])
        b = np.array([math.log(k) for _, _, k in known])
        coef = np.linalg.lstsq(A, b, rcond=None)[0]
    for _, m in mains.iterrows():
        name = m["main"].strip()
        if name not in Kmap:
            L, D = float(m["length_m"]), float(m["diameter_mm"])
            if coef is not None:
                Kmap[name] = math.exp(coef[0] + coef[1] * math.log(L) + coef[2] * math.log(D))
            else:
                Kmap[name] = 1e-4 * L / (D / 100.0) ** 4.82

    # ---- nodes ----------------------------------------------------------
    nodes = {}

    def nid(n):
        n = n.strip()
        if n not in nodes:
            nodes[n] = len(nodes)
        return nodes[n]

    ef, et, ek = [], [], []
    vol = {}
    for _, m in mains.iterrows():
        a, b = nid(m["from_node"]), nid(m["to_node"])
        L, D = float(m["length_m"]), float(m["diameter_mm"]) / 1000.0
        half = math.pi * D * D * L / 8.0
        vol[a] = vol.get(a, 0.0) + half
        vol[b] = vol.get(b, 0.0) + half
        ef.append(a); et.append(b); ek.append(Kmap[m["main"].strip()])
    N = len(nodes)
    V = np.array([vol.get(i, 0.0) for i in range(N)])
    C = V / PATM  # standard m3 per bar abs

    # boundary valves (open ones become mains to a fixed-pressure node)
    bv = []  # (node, p_nb_abs, K)
    for _, v in open_valves.iterrows():
        name = v["valve"].strip()
        node = nid(v["node"])
        pnb = float(v["neighbour_pressure_barg"]) + PATM
        k = None
        row = res.get("valve", {}).get(name)
        if row is not None:
            try:
                pn = float(row[0]) + PATM
                pb = float(row[1]) + PATM
                q = float(row[2])
                if abs(q) > 1e-9:
                    kk = (pb * pb - pn * pn) / (q * abs(q) ** 0.82)
                    if kk > 0:
                        k = kk
            except Exception:
                k = None
        if k is None:
            k = float(np.median(ek))
        bv.append((node, pnb, k))
    N = len(nodes)

    ef = np.array(ef, dtype=int); et = np.array(et, dtype=int); ek = np.array(ek)
    if bv:
        bvn = np.array([b[0] for b in bv], dtype=int)
        bvp = np.array([b[1] for b in bv])
        bvk = np.array([b[2] for b in bv])
    else:
        bvn = np.zeros(0, dtype=int); bvp = np.zeros(0); bvk = np.zeros(0)

    # ---- demand: 24 hourly vectors by step ------------------------------
    dem_hour = np.zeros((24, N))
    gnode = {g["governor"].strip(): nid(g["node"]) for _, g in govs.iterrows()}
    for _, r in dday.iterrows():
        dem_hour[int(r["hour"]) % 24, gnode[r["governor"].strip()]] += float(r["demand_m3h"])
    corr = {}
    for name, row in res.get("meter", {}).items():
        try:
            pct = float(row[0])
            if pct > 0:
                corr[name] = 100.0 / pct
        except Exception:
            pass
    wk = meters[meters["t"].dt.dayofweek < 5]
    hourly = wk.groupby(["meter", wk["t"].dt.hour])["q"].mean()
    for _, c in custs.iterrows():
        mt = c["meter"].strip()
        node = nid(c["node"])
        f = corr.get(mt, 1.0)
        for h in range(24):
            try:
                dem_hour[h, node] += f * float(hourly.loc[(mt, h)])
            except KeyError:
                pass
    N = len(nodes)
    if dem_hour.shape[1] < N:
        dem_hour = np.hstack([dem_hour, np.zeros((24, N - dem_hour.shape[1]))])
        C = np.concatenate([C, np.zeros(N - len(C))])

    pr_node = np.array([nid(r["node"]) for _, r in prs.iterrows()], dtype=int)
    pr_set = np.array([float(r["set_point_barg"]) + PATM for _, r in prs.iterrows()])
    pr_cap = np.array([float(r["capacity_m3h"]) for _, r in prs.iterrows()])
    N = len(nodes)

    dt = 0.1
    M = len(ef)
    rows_inc = np.concatenate([ef, et])
    cols_inc = np.concatenate([np.arange(M), np.arange(M)])
    vals_inc = np.concatenate([-np.ones(M), np.ones(M)])
    # A: node x main, +1 arriving at to, -1 leaving from
    A = sp.csr_matrix((vals_inc, (rows_inc, cols_inc)), shape=(N, M))
    DELTA_EPS = 1e-6

    def flow(d, k):
        ad = np.abs(d)
        q = np.sign(d) * (ad / k) ** (1.0 / EXP)
        # derivative dq/dd
        ade = np.maximum(ad, DELTA_EPS)
        dq = (ade / k) ** (1.0 / EXP) / (EXP * ade)
        return q, dq

    def solve_step(p_prev, p_guess, dem, mode, cdt):
        """Implicit step. mode per PRS: 0 = hold set point, 1 = capacity, 2 = zero."""
        p = p_guess.copy()
        for _outer in range(20):
            fixed = np.zeros(N, dtype=bool)
            inj = np.zeros(N)
            for i in range(len(pr_node)):
                if mode[i] == 0:
                    fixed[pr_node[i]] = True
                    p[pr_node[i]] = pr_set[i]
                elif mode[i] == 1:
                    inj[pr_node[i]] += pr_cap[i]
            free = ~fixed
            for _it in range(60):
                d = p[ef] ** 2 - p[et] ** 2
                q, dqd = flow(d, ek)
                F = A @ q + inj - dem - cdt * (p - p_prev)
                # Jacobian
                gf = dqd * 2 * p[ef]
                gt = -dqd * 2 * p[et]
                # dF_n/dp_j : A[n,m]*dq_m/dp_j
                rr = np.concatenate([et, et, ef, ef])
                cc = np.concatenate([ef, et, ef, et])
                vv = np.concatenate([gf, gt, -gf, -gt])
                diag = -cdt.copy()
                if len(bvn):
                    db = bvp ** 2 - p[bvn] ** 2
                    qb, dqb = flow(db, bvk)
                    np.add.at(F, bvn, qb)
                    np.add.at(diag, bvn, -dqb * 2 * p[bvn])
                J = sp.csr_matrix((np.concatenate([vv, diag]),
                                   (np.concatenate([rr, np.arange(N)]),
                                    np.concatenate([cc, np.arange(N)]))), shape=(N, N))
                idx = np.where(free)[0]
                Jf = J[idx][:, idx].tocsc()
                dp = spla.spsolve(Jf, -F[idx])
                step = 1.0
                mx = np.max(np.abs(dp)) if len(dp) else 0.0
                if mx > 0.5:
                    step = 0.5 / mx
                p[idx] += step * dp
                p = np.maximum(p, 0.05)
                if mx * step < 1e-7:
                    break
            # check PRS consistency
            d = p[ef] ** 2 - p[et] ** 2
            q, _ = flow(d, ek)
            F = A @ q - dem - cdt * (p - p_prev)
            if len(bvn):
                qb, _ = flow(bvp ** 2 - p[bvn] ** 2, bvk)
                np.add.at(F, bvn, qb)
            changed = False
            for i in range(len(pr_node)):
                n = pr_node[i]
                need = -F[n]
                if mode[i] == 0:
                    if need > pr_cap[i] + 1e-9:
                        mode[i] = 1; changed = True
                    elif need < -1e-9:
                        mode[i] = 2; changed = True
                elif mode[i] == 1:
                    if p[n] > pr_set[i] + 1e-12:
                        mode[i] = 0; changed = True
                else:
                    if p[n] < pr_set[i] - 1e-12:
                        mode[i] = 0; changed = True
            if not changed:
                break
        return p

    cdt = C / dt
    hours = [(6 + k // 10) % 24 for k in range(240)]
    p = np.full(N, float(np.max(pr_set)) if len(pr_set) else 7.0)
    # steady start at mean demand
    mode = [0] * len(pr_node)
    p = solve_step(p, p, dem_hour.mean(axis=0), mode, np.zeros(N))
    p0 = p.copy()
    minp = None
    for day in range(200):
        start = p.copy()
        traj_min = np.full(N, np.inf)
        for k in range(240):
            p = solve_step(p, p, dem_hour[hours[k]], mode, cdt)
            traj_min = np.minimum(traj_min, p)
        diff = np.max(np.abs(p - start))
        minp = traj_min
        if os.environ.get("DD_DEBUG"):
            print("day", day, diff, file=sys.stderr)
        if diff < 2e-5 or time.process_time() > 7.0:
            break

    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["governor", "min_pressure_barg"])
        for _, g in govs.iterrows():
            n = gnode[g["governor"].strip()]
            w.writerow([g["governor"].strip(), "%.4f" % (minp[n] - PATM)])


if __name__ == "__main__":
    main()
