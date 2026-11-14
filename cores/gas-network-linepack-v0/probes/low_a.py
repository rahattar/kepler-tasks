#!/usr/bin/env python3
"""GD-3 design-day minimum governor pressures for one network package.

Usage: python3 designday.py PACKAGE_DIR OUT_CSV
"""
import csv
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.linalg as spla

PATM = 1.01325
EXP = 1.82
DT = 0.1
NSTEP = 240


def kval(pf_abs, pt_abs, q):
    den = q * abs(q) ** 0.82
    if den == 0:
        return None
    k = (pf_abs ** 2 - pt_abs ** 2) / den
    return k if k > 0 else None


def parse_survey_output(text):
    """Return dict kind -> list of row dicts."""
    out = {}
    header = None
    kind = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        cells = [c.strip() for c in line.split(",")]
        if cells[0] in ("main", "valve", "meter") and len(cells) > 1 and not \
                _isnum(cells[1]):
            header = cells
            kind = cells[0]
            out.setdefault(kind, [])
            continue
        if header is None or len(cells) != len(header):
            continue
        out[kind].append(dict(zip(header, cells)))
    return out


def _isnum(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def main():
    pkg, out_csv = sys.argv[1], sys.argv[2]
    rd = lambda f: pd.read_csv(os.path.join(pkg, f), dtype=str, skipinitialspace=True)
    with open(os.path.join(pkg, "network.json")) as fh:
        meta = json.load(fh)
    allowance = int(meta.get("survey_allowance", 0))

    mains = rd("mains.csv")
    surveys = rd("surveys.csv")
    work = rd("work_log.csv")
    prs = rd("prs.csv")
    govs = rd("governors.csv")
    dd = rd("design_day.csv")
    custs = rd("customers.csv")
    meters = rd("customer_meters.csv")
    valves = rd("boundary_valves.csv")
    for df in (mains, surveys, work, prs, govs, dd, custs, meters, valves):
        for c in df.columns:
            df[c] = df[c].str.strip()

    mains["length_m"] = mains["length_m"].astype(float)
    mains["diameter_mm"] = mains["diameter_mm"].astype(float)
    main_names = list(mains["main"])

    # ---- latest survey K per main, and whether later work invalidates it
    surveys = surveys.copy()
    surveys["p_from_barg"] = surveys["p_from_barg"].astype(float)
    surveys["dp_bar"] = surveys["dp_bar"].astype(float)
    surveys["q_m3h"] = surveys["q_m3h"].astype(float)
    surveys = surveys.sort_values("date", kind="stable")
    latest = {}
    for r in surveys.itertuples(index=False):
        pf = r.p_from_barg + PATM
        k = kval(pf, pf - r.dp_bar, r.q_m3h)
        if k is not None:
            latest[r.main] = (r.date, k)
    changing = work[work["work"].str.upper().isin(["RENEWED", "RELINED", "LAID"])]
    last_change = changing.groupby("main")["date"].max().to_dict()

    K = {}
    need_mains = []
    for m in main_names:
        s = latest.get(m)
        ch = last_change.get(m)
        if s is None or (ch is not None and ch >= s[0]):
            need_mains.append(m)
        else:
            K[m] = s[1]

    open_valves = valves[valves["state"].str.lower() == "open"]
    need_valves = list(open_valves["valve"])

    # ---- customer demand profile (by clock hour), weekday mean
    meters = meters.copy()
    meters["q_m3h"] = meters["q_m3h"].astype(float)
    ts = pd.to_datetime(meters["time"], format="%Y-%m-%d %H:%M")
    meters["hour"] = ts.dt.hour
    wk = meters[ts.dt.dayofweek < 5]
    prof = wk.groupby(["meter", "hour"])["q_m3h"].mean()
    meter_size = wk.groupby("meter")["q_m3h"].mean().to_dict()

    # ---- order with the field team
    order = list(need_valves)
    # mains most loaded first if we cannot afford them all
    room = max(allowance - len(order), 0)
    if len(need_mains) > room:
        # rank by a rough conductance (larger main carries more flow)
        dmap = mains.set_index("main")
        need_mains_sorted = sorted(
            need_mains,
            key=lambda m: -(dmap.at[m, "diameter_mm"] ** 2.6 / dmap.at[m, "length_m"] ** 0.55))
        order += need_mains_sorted[:room]
    else:
        order += need_mains
    room = max(allowance - len(order), 0)
    cmeters = sorted(custs["meter"].tolist(), key=lambda m: -meter_size.get(m, 0.0))
    order += cmeters[:room]
    order = order[:allowance] if allowance >= 0 else []

    res = {}
    if order:
        try:
            p = subprocess.run(["gdsurvey", pkg] + order, capture_output=True,
                               text=True, timeout=6)
            res = parse_survey_output(p.stdout)
        except Exception:
            res = {}

    for r in res.get("main", []):
        try:
            pf = float(r["p_from_barg"]) + PATM
            k = kval(pf, pf - float(r["dp_bar"]), float(r["q_m3h"]))
        except (KeyError, ValueError):
            k = None
        if k is not None:
            K[r["main"]] = k
    valveK = {}
    for r in res.get("valve", []):
        try:
            pn = float(r["p_node_barg"]) + PATM
            pb = float(r["p_neighbour_barg"]) + PATM
            k = kval(pb, pn, float(r["q_m3h"]))
        except (KeyError, ValueError):
            k = None
        if k is not None:
            valveK[r["valve"]] = k
    meter_pct = {}
    for r in res.get("meter", []):
        try:
            meter_pct[r["meter"]] = float(r["registers_pct"])
        except (KeyError, ValueError):
            pass

    # ---- fallback K for mains still unknown: K ~ c * L / D^4.82 per material
    missing = [m for m in main_names if m not in K]
    if missing:
        mi = mains.set_index("main")
        coef = {}
        allc = []
        for m, k in K.items():
            row = mi.loc[m]
            c = k * row["diameter_mm"] ** 4.82 / row["length_m"]
            coef.setdefault(row["material"], []).append(c)
            allc.append(c)
        gmed = float(np.median(allc)) if allc else 1.0
        for m in missing:
            row = mi.loc[m]
            cs = coef.get(row["material"])
            c = float(np.median(cs)) if cs else gmed
            K[m] = c * row["length_m"] / row["diameter_mm"] ** 4.82

    # ---- build network
    nodes = sorted(set(mains["from_node"]) | set(mains["to_node"]))
    idx = {n: i for i, n in enumerate(nodes)}
    N = len(nodes)
    fi = np.array([idx[n] for n in mains["from_node"]])
    ti = np.array([idx[n] for n in mains["to_node"]])
    Kv = np.array([K[m] for m in main_names])
    vol = np.pi * (mains["diameter_mm"].values / 1000.0) ** 2 * mains["length_m"].values / 8.0
    V = np.zeros(N)
    np.add.at(V, fi, vol)
    np.add.at(V, ti, vol)
    C = V / PATM  # m3(st) per bar

    # boundary valves (open with K) as mains to fixed pressure
    bv_node, bv_p, bv_K = [], [], []
    for r in open_valves.itertuples(index=False):
        if r.valve in valveK and r.node in idx:
            bv_node.append(idx[r.node])
            bv_p.append(float(r.neighbour_pressure_barg) + PATM)
            bv_K.append(valveK[r.valve])
    bv_node = np.array(bv_node, dtype=int)
    bv_p = np.array(bv_p)
    bv_K = np.array(bv_K)

    prs_node = np.array([idx[n] for n in prs["node"]], dtype=int)
    prs_set = prs["set_point_barg"].astype(float).values + PATM
    prs_cap = prs["capacity_m3h"].astype(float).values

    # demand per step (240 x N)
    hours = [(6 + k // 10) % 24 for k in range(NSTEP)]
    dem_h = np.zeros((24, N))
    dd = dd.copy()
    dd["hour"] = dd["hour"].astype(int)
    dd["demand_m3h"] = dd["demand_m3h"].astype(float)
    gnode = dict(zip(govs["governor"], govs["node"]))
    for r in dd.itertuples(index=False):
        if r.governor in gnode:
            dem_h[r.hour % 24, idx[gnode[r.governor]]] += r.demand_m3h
    for r in custs.itertuples(index=False):
        fac = 100.0 / meter_pct[r.meter] if r.meter in meter_pct and meter_pct[r.meter] > 0 else 1.0
        for h in range(24):
            try:
                q = prof.loc[(r.meter, h)]
            except KeyError:
                q = 0.0
            dem_h[h, idx[r.node]] += q * fac

    # flow function with linearised core for tiny dp^2
    eps = 1e-6

    def flows(pa, pb, k):
        d = pa * pa - pb * pb
        x = d / k
        ax = np.abs(x)
        big = ax > eps
        q = np.empty_like(x)
        dq = np.empty_like(x)
        q[big] = np.sign(x[big]) * ax[big] ** (1 / EXP)
        dq[big] = (1 / EXP) * ax[big] ** (1 / EXP - 1)
        s = eps ** (1 / EXP - 1)
        q[~big] = x[~big] * s
        dq[~big] = s
        dq = dq / k  # dQ/d(d)
        return q, dq * 2 * pa, -dq * 2 * pb

    nP = len(prs_node)
    ar = np.arange(N)
    pattern_rows = np.concatenate([ar, fi, fi, ti, ti, bv_node])
    pattern_cols = np.concatenate([ar, fi, ti, fi, ti, bv_node])

    def residual(p, pold, dem, s):
        q, dqa, dqb = flows(p[fi], p[ti], Kv)
        F = C * (p - pold) / DT + dem
        np.add.at(F, fi, q)
        np.subtract.at(F, ti, q)
        vals = [C / DT, dqa, dqb, -dqa, -dqb]
        if len(bv_node):
            qb, _, dnode = flows(bv_p, p[bv_node], bv_K)
            np.subtract.at(F, bv_node, qb)
            vals.append(-dnode)
        else:
            vals.append(np.zeros(0))
        np.subtract.at(F, prs_node, s)
        return F, np.concatenate(vals)

    mode = np.zeros(nP, int)  # 0: holds set point, 1: delivers nothing, 2: delivers capacity

    def solve_step(pold, dem, pguess):
        p = pguess.copy()
        for outer in range(4 * nP + 4):
            fixedp = mode == 0
            s = np.where(mode == 2, prs_cap, 0.0)
            p[prs_node[fixedp]] = prs_set[fixedp]
            free = np.ones(N, bool)
            free[prs_node[fixedp]] = False
            fidx = np.nonzero(free)[0]
            for it in range(50):
                F, vals = residual(p, pold, dem, s)
                J = sp.csr_matrix((vals, (pattern_rows, pattern_cols)), shape=(N, N))
                Jf = J[fidx][:, fidx].tocsc()
                dx = spla.spsolve(Jf, -F[fidx])
                m = np.max(np.abs(dx))
                if m > 0.3:
                    dx *= 0.3 / m
                p[fidx] += dx
                if m < 1e-8:
                    break
            F, _ = residual(p, pold, dem, s)
            # needed delivery at fixed-pressure PRS: s + F
            need = s + F[prs_node]
            changed = False
            for j in range(nP):
                if mode[j] == 0:
                    if need[j] < -1e-6:
                        mode[j] = 1; changed = True
                    elif need[j] > prs_cap[j] + 1e-6:
                        mode[j] = 2; changed = True
                elif mode[j] == 1:
                    if p[prs_node[j]] < prs_set[j] - 1e-9:
                        mode[j] = 0; changed = True
                else:
                    if p[prs_node[j]] > prs_set[j] + 1e-9:
                        mode[j] = 0; changed = True
            if not changed:
                break
        return p

    # initial state: start all nodes at the highest set point and run days to periodicity
    p = np.full(N, prs_set.max() if nP else 5.0)
    dem_steps = [dem_h[h] for h in hours]
    prev_end = None
    mins = None
    for day in range(40):
        start = p.copy()
        mins = np.full(N, np.inf)
        for k in range(NSTEP):
            p = solve_step(p, dem_steps[k], p)
            mins = np.minimum(mins, p)
        if np.max(np.abs(p - start)) < 2e-5:
            break

    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["governor", "min_pressure_barg"])
        for g, n in zip(govs["governor"], govs["node"]):
            w.writerow([g, "%.4f" % (mins[idx[n]] - PATM)])


if __name__ == "__main__":
    main()
