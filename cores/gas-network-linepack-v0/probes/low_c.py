#!/usr/bin/env python3
"""Design-day governor inlet pressures to GD-3 for one network package.

Usage: python3 designday.py PACKAGE_DIR OUT_CSV
"""
import io
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.linalg as spla

PA = 1.01325
EXP = 1.82          # Q|Q|^0.82
INV = 1.0 / EXP
NSTEP, DT = 240, 0.1
NEW_K_WORK = {"RENEWED", "RELINED", "LAID"}


def read(pkg, name):
    return pd.read_csv(os.path.join(pkg, name), dtype=str, keep_default_na=False)


def k_of(pf_abs, pt_abs, q):
    q = float(q)
    if q == 0.0:
        return None
    k = (pf_abs ** 2 - pt_abs ** 2) / (q * abs(q) ** 0.82)
    return k if k > 0 else None


def parse_survey_output(text):
    blocks = {}
    cur = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        head = line.split(",")[0]
        if head in ("main", "valve", "meter"):
            cur = head
            blocks[cur] = [line]
        elif cur is not None:
            blocks[cur].append(line)
    out = {}
    for k, lines in blocks.items():
        out[k] = pd.read_csv(io.StringIO("\n".join(lines)), dtype=str)
    return out


def main():
    pkg, out_csv = sys.argv[1], sys.argv[2]
    with open(os.path.join(pkg, "network.json")) as f:
        net = json.load(f)
    allowance = int(net.get("survey_allowance", 0))

    mains = read(pkg, "mains.csv")
    surveys = read(pkg, "surveys.csv")
    work = read(pkg, "work_log.csv")
    prs = read(pkg, "prs.csv")
    govs = read(pkg, "governors.csv")
    dd = read(pkg, "design_day.csv")
    cust = read(pkg, "customers.csv")
    meters = read(pkg, "customer_meters.csv")
    bvs = read(pkg, "boundary_valves.csv")

    # ---- K of each main from its latest valid survey after any K-changing work
    last_new = {}
    for _, r in work.iterrows():
        if r["work"].strip().upper() in NEW_K_WORK:
            m = r["main"].strip()
            last_new[m] = max(last_new.get(m, ""), r["date"].strip())
    K = {}
    surveys = surveys.sort_values("date", kind="stable")
    for _, r in surveys.iterrows():
        m = r["main"].strip()
        if r["date"].strip() <= last_new.get(m, ""):
            continue   # surveyed before the work that made the present main
        try:
            pf = float(r["p_from_barg"]) + PA
            k = k_of(pf, pf - float(r["dp_bar"]), r["q_m3h"])
        except ValueError:
            k = None
        if k is not None:
            K[m] = k
    need_mains = [m.strip() for m in mains["main"] if m.strip() not in K]
    open_bv = bvs[bvs["state"].str.strip().str.lower() == "open"]
    need_valves = [v.strip() for v in open_bv["valve"]]
    # open valves first (without a K the valve could not be modelled at all), then
    # the mains whose K no survey on file measured, then meters, largest flow first
    items = need_valves + need_mains
    mflow = meters.assign(q=pd.to_numeric(meters["q_m3h"], errors="coerce")).groupby(
        meters["meter"].str.strip())["q"].mean()
    meter_ids = sorted([m.strip() for m in cust["meter"]],
                       key=lambda m: -float(mflow.get(m, 0.0)))
    items += meter_ids
    items = items[:max(allowance, 0)]
    reg_pct = {}
    VK = {}
    if items:
        try:
            res = subprocess.run(["gdsurvey", pkg] + items, capture_output=True,
                                 text=True, timeout=60)
            blocks = parse_survey_output(res.stdout)
        except Exception as e:  # field team unavailable
            sys.stderr.write("gdsurvey failed: %s\n" % e)
            blocks = {}
        if "main" in blocks:
            for _, r in blocks["main"].iterrows():
                pf = float(r["p_from_barg"]) + PA
                k = k_of(pf, pf - float(r["dp_bar"]), r["q_m3h"])
                if k is not None:
                    K[r["main"].strip()] = k
        if "valve" in blocks:
            for _, r in blocks["valve"].iterrows():
                # flow from neighbour into the node: treat as main neighbour -> node
                k = k_of(float(r["p_neighbour_barg"]) + PA,
                         float(r["p_node_barg"]) + PA, r["q_m3h"])
                if k is not None:
                    VK[r["valve"].strip()] = k
        if "meter" in blocks:
            for _, r in blocks["meter"].iterrows():
                reg_pct[r["meter"].strip()] = float(r["registers_pct"])
    missing = [m.strip() for m in mains["main"] if m.strip() not in K]
    if missing:
        # no survey possible within the allowance: estimate K from like mains,
        # K ~ L / D^4.82 (same material where possible)
        sys.stderr.write("warning: no K for %s; estimated from like mains\n" % missing)
        reg = mains.assign(main=mains["main"].str.strip()).set_index("main")
        L = reg["length_m"].astype(float)
        Dm = reg["diameter_mm"].astype(float)
        mat = reg["material"].str.strip()
        known = [m for m in K if m in reg.index]
        coef = pd.Series({m: K[m] * Dm[m] ** 4.82 / L[m] for m in known})
        for m in missing:
            same = [x for x in known if mat[x] == mat[m]]
            c = coef[same].median() if same else coef.median()
            K[m] = c * L[m] / Dm[m] ** 4.82

    # ---- nodes
    nodes = sorted(set(mains["from_node"].str.strip()) | set(mains["to_node"].str.strip()))
    idx = {n: i for i, n in enumerate(nodes)}
    N = len(nodes)
    fr = np.array([idx[x.strip()] for x in mains["from_node"]])
    to = np.array([idx[x.strip()] for x in mains["to_node"]])
    Kv = np.array([K[m.strip()] for m in mains["main"]])
    D = mains["diameter_mm"].astype(float).values / 1000.0
    Lm = mains["length_m"].astype(float).values
    vol = np.pi * D ** 2 * Lm / 8.0
    V = np.zeros(N)
    np.add.at(V, fr, vol)
    np.add.at(V, to, vol)
    C = V / PA / DT   # std m3/h per bar of pressure change over a step

    # boundary valves that pass gas: fixed-pressure ends
    bv_node, bv_p, bv_k = [], [], []
    for _, r in open_bv.iterrows():
        v = r["valve"].strip()
        if v in VK:
            bv_node.append(idx[r["node"].strip()])
            bv_p.append(float(r["neighbour_pressure_barg"]) + PA)
            bv_k.append(VK[v])
    bv_node = np.array(bv_node, dtype=int)
    bv_p = np.array(bv_p)
    bv_k = np.array(bv_k)

    prs_node = np.array([idx[x.strip()] for x in prs["node"]], dtype=int)
    prs_set = prs["set_point_barg"].astype(float).values + PA
    prs_cap = prs["capacity_m3h"].astype(float).values

    # ---- demand per clock hour
    dem = np.zeros((24, N))
    gnode = {r["governor"].strip(): idx[r["node"].strip()] for _, r in govs.iterrows()}
    for _, r in dd.iterrows():
        dem[int(r["hour"]), gnode[r["governor"].strip()]] += float(r["demand_m3h"])
    meters["t"] = pd.to_datetime(meters["time"].str.strip())
    meters["q"] = meters["q_m3h"].astype(float)
    meters["meter"] = meters["meter"].str.strip()
    wk = meters[meters["t"].dt.dayofweek < 5]
    for _, r in cust.iterrows():
        mt = r["meter"].strip()
        g = wk[wk["meter"] == mt]
        prof = g.groupby(g["t"].dt.hour)["q"].mean()
        fac = 100.0 / reg_pct[mt] if mt in reg_pct else 1.0
        n = idx[r["node"].strip()]
        for h, q in prof.items():
            dem[int(h), n] += q * fac

    # ---- network equations
    rows = np.concatenate([fr, to, fr, to])
    cols = np.concatenate([fr, to, to, fr])

    def flows(p):
        x = p[fr] ** 2 - p[to] ** 2
        ax = np.abs(x)
        xe = np.maximum(ax, 1e-8)
        q = np.sign(x) * (xe / Kv) ** INV
        dq = INV * (xe / Kv) ** INV / xe   # dQ/dx
        small = ax < 1e-8
        q[small] = x[small] * (1e-8 / Kv[small]) ** INV / 1e-8
        return q, dq

    nP = len(prs_node)
    M = N + nP
    G = 1e4   # scaling of the PRS complementarity equations, m3/h per bar
    prow = np.arange(N, M)
    # sparsity pattern of the augmented Jacobian (nodes then PRS deliveries)
    pr = np.concatenate([rows, np.arange(N), prs_node, prow, prow])
    pc = np.concatenate([cols, np.arange(N), prow, prs_node, prow])
    Jpat = sp.csr_matrix((np.arange(1, len(pr) + 1, dtype=float), (pr, pc)), shape=(M, M))
    Jpat.sum_duplicates()
    Jpat.sort_indices()

    def pos(r, c):
        out = np.empty(len(r), dtype=int)
        for i, (a_, b_) in enumerate(zip(r, c)):
            s0, s1 = Jpat.indptr[a_], Jpat.indptr[a_ + 1]
            out[i] = s0 + np.searchsorted(Jpat.indices[s0:s1], b_)
        return out
    pos_m = pos(rows, cols)
    pos_d = pos(np.arange(N), np.arange(N))
    pos_ns = pos(prs_node, prow)     # dF_node/ds = 1
    pos_sp = pos(prow, prs_node)     # dPhi/dp
    pos_ss = pos(prow, prow)         # dPhi/ds

    def step(pprev, d, p0, s0):
        """Implicit step: end-of-step pressures and PRS deliveries."""
        p = p0.copy()
        s = s0.copy()
        for _it in range(100):
            q, dq = flows(p)
            F = -d - C * (p - pprev)
            np.add.at(F, to, q)
            np.add.at(F, fr, -q)
            np.add.at(F, prs_node, s)
            Jd = -C.copy()
            if len(bv_node):
                y = bv_p ** 2 - p[bv_node] ** 2
                ay = np.maximum(np.abs(y), 1e-8)
                qb = np.sign(y) * (ay / bv_k) ** INV
                np.add.at(F, bv_node, qb)
                np.add.at(Jd, bv_node, -INV * (ay / bv_k) ** INV / ay * 2 * p[bv_node])
            u = s + G * (prs_set - p[prs_node])
            act = (u > 0) & (u < prs_cap)
            phi = s - np.clip(u, 0.0, prs_cap)
            if np.max(np.abs(F)) < 1e-3 and np.max(np.abs(phi)) < 1e-6:
                break
            a = dq * 2 * p[fr]
            b = dq * 2 * p[to]
            data = np.zeros(len(Jpat.data))
            np.add.at(data, pos_m, np.concatenate([-a, -b, b, a]))
            np.add.at(data, pos_d, Jd)
            data[pos_ns] += 1.0
            data[pos_sp] += np.where(act, G, 0.0)
            data[pos_ss] += np.where(act, 0.0, 1.0)
            J = sp.csr_matrix((data, Jpat.indices, Jpat.indptr), shape=(M, M))
            dx = spla.spsolve(J.tocsc(), -np.concatenate([F, phi]))
            dp = dx[:N]
            lim = np.max(np.abs(dp))
            if lim > 0.5:
                dx *= 0.5 / lim
            p = np.maximum(p + dx[:N], 0.05)
            s = s + dx[N:]
        return p, s

    hours = [(6 + int(k * DT)) % 24 for k in range(NSTEP)]
    # initial state: a steady state at mean demand ~ start from set point
    p = np.full(N, prs_set.min())
    sv = np.zeros(len(prs_node))
    start = p.copy()
    traj = None
    for day in range(200):
        start = p.copy()
        traj = np.empty((NSTEP, N))
        for k in range(NSTEP):
            p, sv = step(p, dem[hours[k]], p, sv)
            traj[k] = p
        if np.max(np.abs(p - start)) < 1e-5:
            break

    gmin = traj.min(axis=0)
    out = pd.DataFrame({"governor": govs["governor"].str.strip(),
                        "min_pressure_barg": [round(gmin[gnode[g.strip()]] - PA, 4)
                                              for g in govs["governor"]]})
    out.to_csv(out_csv, index=False)


if __name__ == "__main__":
    main()
