#!/usr/bin/env python3
"""Supply temperatures and delivered heat of a hot-water heat network to HN-3.

Usage: python3 heatnet.py PACKAGE_DIR OUT_CSV
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import splu

RHO = 975.0
CP = 4.19
DT = 120.0
DTH = DT / 3600.0


def schedule_index(times, nsteps):
    """For each step k=1..nsteps, index of the schedule row valid at t_(k-1)."""
    tk = np.arange(nsteps) * DTH  # t_(k-1)
    return np.searchsorted(np.asarray(times, float), tk + 1e-9, side="right") - 1


class Hydraulics:
    def __init__(self, nn, plant, pu, pv, R, sn, K):
        self.nn, self.plant = nn, plant
        self.pu, self.pv, self.R = pu, pv, R
        self.sn, self.K = sn, K
        self.np_ = len(pu)
        self.ns = len(sn)
        keep = np.ones(nn, bool)
        keep[plant] = False
        self.keep = keep
        self.map = -np.ones(nn, int)
        self.map[keep] = np.arange(keep.sum())
        self.h = np.zeros(nn)
        self.iters = 0
        self.lu = None
        self.m = None
        self.ms = None
        # sparse pattern: rows/cols of Laplacian
        rows = np.concatenate([pu, pv, pu, pv, sn])
        cols = np.concatenate([pu, pv, pv, pu, sn])
        sel = keep[rows] & keep[cols]
        self.sel = sel
        nk = int(keep.sum())
        self.nk = nk
        r0, c0 = self.map[rows[sel]], self.map[cols[sel]]
        # fill-reducing ordering, computed once
        data0 = np.ones(len(r0))
        A0 = sp.csc_matrix((data0, (r0, c0)), shape=(nk, nk)) + sp.identity(nk, format="csc")
        perm = splu(A0, permc_spec="MMD_AT_PLUS_A").perm_c if nk else np.zeros(0, int)
        inv = np.empty(nk, int)
        inv[perm] = np.arange(nk)
        rp, cp = inv[r0], inv[c0]
        key = cp.astype(np.int64) * nk + rp
        ukey, self.einv = np.unique(key, return_inverse=True)
        ucol, urow = ukey // nk, ukey % nk
        self.indices = urow.astype(np.int32)
        self.indptr = np.searchsorted(ucol, np.arange(nk + 1)).astype(np.int32)
        self.nnz = len(ukey)
        self.perm = perm  # permuted index i corresponds to original reduced index perm[i]

    def solve(self, DP, mwant):
        pu, pv, R, sn, K = self.pu, self.pv, self.R, self.sn, self.K
        nn = self.nn
        h = self.h
        if self.m is None:
            self.m = np.full(self.np_, 1e-3)
            self.ms = mwant.copy()
            # initial: tree-ish guess via small flows; GGA will fix
        m = self.m
        ms = self.ms
        keep, mp = self.keep, self.map
        nk = keep.sum()
        self.iters = getattr(self, 'iters', 0)
        for it in range(200):
            self.iters += 1
            dp = DP - 2.0 * h[sn]
            mmax = K * np.sqrt(np.maximum(dp, 0.0))
            bind = mmax < mwant
            msb = np.maximum(np.where(bind, np.maximum(mmax, ms), ms), 1e-7)
            am = np.maximum(np.abs(m), 1e-7)
            a = 1.0 / (2.0 * R * am)
            b = m / 2.0
            asub = np.where(bind, K * K / msb, 0.0)
            bsub = np.where(bind, msb / 2.0, mwant)
            rhs = np.zeros(nn)
            np.add.at(rhs, pv, -b)
            np.add.at(rhs, pu, b)
            np.add.at(rhs, sn, bsub + asub * DP / 2.0)
            data = np.concatenate([a, a, -a, -a, asub])
            vals = np.bincount(self.einv, weights=data[self.sel], minlength=self.nnz)
            A = sp.csc_matrix((vals, self.indices, self.indptr), shape=(nk, nk))
            hn = np.zeros(nn)
            if nk:
                lu = splu(A, permc_spec="NATURAL", diag_pivot_thresh=0.0,
                          options=dict(SymmetricMode=True))
                rk = rhs[keep]
                xk = np.empty(nk)
                xk[self.perm] = lu.solve(rk[self.perm])
                hn[keep] = xk
            m_new = a * (hn[pv] - hn[pu]) + b
            ms_new = np.where(bind, asub * (DP / 2.0 - hn[sn]) + bsub, mwant)
            dh = np.max(np.abs(hn - h)) if nn else 0.0
            h = hn
            m = m_new
            ms = ms_new
            # true residual check
            d = h[pv] - h[pu]
            mt = np.sign(d) * np.sqrt(np.abs(d) / R)
            dpt = DP - 2.0 * h[sn]
            mst = np.minimum(mwant, K * np.sqrt(np.maximum(dpt, 0.0)))
            mst[dpt <= 0] = 0.0
            res = np.zeros(nn)
            np.add.at(res, pv, mt)
            np.add.at(res, pu, -mt)
            np.add.at(res, sn, -mst)
            res[self.plant] = 0.0
            if np.max(np.abs(res)) < 1e-8 * max(1.0, mst.sum()):
                break
        self.h, self.m, self.ms = h, m, ms
        # report flows consistent with pressures
        return mt, mst

    def _resid(self, h, DP, mwant):
        pu, pv, R, sn, K = self.pu, self.pv, self.R, self.sn, self.K
        d = h[pv] - h[pu]
        mt = np.sign(d) * np.sqrt(np.abs(d) / R)
        dpt = DP - 2.0 * h[sn]
        mst = np.minimum(mwant, K * np.sqrt(np.maximum(dpt, 0.0)))
        res = (np.bincount(pv, mt, self.nn) - np.bincount(pu, mt, self.nn)
               - np.bincount(sn, mst, self.nn))
        res[self.plant] = 0.0
        return res, mt, mst, d, dpt

    def _factor(self, h, DP, mwant, d, dpt):
        R, K = self.R, self.K
        ad = np.maximum(np.abs(d), 1e-12)
        a = 1.0 / (2.0 * np.sqrt(R * ad))
        a = np.minimum(a, 1e6)
        mmax = K * np.sqrt(np.maximum(dpt, 0.0))
        bind = (mmax < mwant) & (dpt > 0)
        asub = np.where(bind, K / np.sqrt(np.maximum(dpt, 1e-12)), 0.0)
        asub = np.minimum(asub, 1e6)
        data = np.concatenate([a, a, -a, -a, asub])
        vals = np.bincount(self.einv, weights=data[self.sel], minlength=self.nnz)
        A = sp.csc_matrix((vals, self.indices, self.indptr), shape=(self.nk, self.nk))
        self.lu = splu(A, permc_spec="NATURAL", diag_pivot_thresh=0.0,
                       options=dict(SymmetricMode=True))

    def _apply(self, r):
        rk = r[self.keep]
        xk = np.empty(self.nk)
        xk[self.perm] = self.lu.solve(rk[self.perm])
        out = np.zeros(self.nn)
        out[self.keep] = xk
        return out

    def step(self, DP, mwant):
        if self.nk == 0:
            return self._resid(self.h, DP, mwant)[1:3]
        if getattr(self, "lu", None) is None:
            mt, mst = self.solve(DP, mwant)
            res, mt, mst, d, dpt = self._resid(self.h, DP, mwant)
            self._factor(self.h, DP, mwant, d, dpt)
            return mt, mst
        h = self.h
        res, mt, mst, d, dpt = self._resid(h, DP, mwant)
        tol = 1e-11 * max(1.0, mst.sum())
        prev = np.inf
        for it in range(100):
            rn = np.max(np.abs(res))
            if rn < tol:
                break
            if rn > 0.2 * prev:
                self._factor(h, DP, mwant, d, dpt)
            prev = rn
            # J = d(res)/dh = A (weighted Laplacian), Newton: dh = -A^-1 res
            h = h - self._apply(res)
            res, mt, mst, d, dpt = self._resid(h, DP, mwant)
            self.iters += 1
        else:
            # fall back to robust GGA
            self.h = h
            mt, mst = self.solve(DP, mwant)
            res, mt, mst, d, dpt = self._resid(self.h, DP, mwant)
            self._factor(self.h, DP, mwant, d, dpt)
            return mt, mst
        self.h = h
        return mt, mst


class Plugs:
    """Plug-flow pipes, vectorised. Labels: v end at lo, u end at lo+V."""

    def __init__(self, V, T0, tau, Tg, W=64):
        n = len(V)
        self.n, self.V, self.tau, self.Tg = n, V, tau, Tg
        self.W = W
        self.X = np.zeros((n, W))
        self.G = np.zeros((n, W))
        c = W // 2
        self.hd = np.full(n, c - 1)
        self.tl = np.full(n, c)
        r = np.arange(n)
        self.r = r
        self.X[r, c - 1] = 0.0
        self.X[r, c] = V
        self.G[r, c] = (T0 - Tg) * V

    def _compact(self):
        n = self.tl - self.hd + 1
        W = self.W
        while n.max() + 8 > W // 2:
            W *= 2
        start = (W - n) // 2
        X = np.zeros((self.n, W))
        G = np.zeros((self.n, W))
        L = n.max()
        j = np.arange(L)
        valid = j[None, :] < n[:, None]
        src = np.minimum(self.hd[:, None] + j[None, :], self.W - 1)
        dst = start[:, None] + j[None, :]
        rr = np.broadcast_to(self.r[:, None], src.shape)
        X[rr[valid], dst[valid]] = self.X[rr[valid], src[valid]]
        G[rr[valid], dst[valid]] = self.G[rr[valid], src[valid]]
        self.X, self.G, self.W = X, G, W
        self.hd = start
        self.tl = start + n - 1

    def outflow(self, dv, tk):
        """dv signed volume (positive u->v). Returns outflow temperature at the outlet end."""
        X, G = self.X, self.G
        out = np.full(self.n, np.nan)
        # forward
        f = np.nonzero(dv > 0)[0]
        if len(f):
            lo_new = X[f, self.hd[f]] + dv[f]
            g0 = G[f, self.hd[f]]
            idx = f
            ln = lo_new
            while len(idx):
                c = X[idx, self.hd[idx] + 1] <= ln
                if not c.any():
                    break
                self.hd[idx[c]] += 1
                idx, ln = idx[c], ln[c]
            h = self.hd[f]
            x0, x1 = X[f, h], X[f, h + 1]
            g1, g2 = G[f, h], G[f, h + 1]
            gn = g1 + (g2 - g1) * (lo_new - x0) / (x1 - x0)
            X[f, h] = lo_new
            G[f, h] = gn
            out[f] = self.Tg + (gn - g0) / dv[f] * np.exp(-tk / self.tau[f])
        b = np.nonzero(dv < 0)[0]
        if len(b):
            d = -dv[b]
            top_new = X[b, self.tl[b]] - d
            g0 = G[b, self.tl[b]]
            idx, tn = b, top_new
            while len(idx):
                c = X[idx, self.tl[idx] - 1] >= tn
                if not c.any():
                    break
                self.tl[idx[c]] -= 1
                idx, tn = idx[c], tn[c]
            t = self.tl[b]
            x0, x1 = X[b, t - 1], X[b, t]
            g1, g2 = G[b, t - 1], G[b, t]
            gn = g1 + (g2 - g1) * (top_new - x0) / (x1 - x0)
            X[b, t] = top_new
            G[b, t] = gn
            out[b] = self.Tg + (g0 - gn) / d * np.exp(-tk / self.tau[b])
        self._f, self._b = f, b
        return out

    def inflow(self, dv, Tin_u, Tin_v, tk):
        """Water entering: forward pipes at u end with Tin_u, backward at v end with Tin_v."""
        if self.tl.max() + 2 >= self.W or self.hd.min() <= 1:
            self._compact()
        X, G = self.X, self.G
        f, b = self._f, self._b
        if len(f):
            A = (Tin_u[f] - self.Tg) * np.exp(tk / self.tau[f])
            t = self.tl[f]
            X[f, t + 1] = X[f, t] + dv[f]
            G[f, t + 1] = G[f, t] + A * dv[f]
            self.tl[f] = t + 1
        if len(b):
            d = -dv[b]
            A = (Tin_v[b] - self.Tg) * np.exp(tk / self.tau[b])
            h = self.hd[b]
            X[b, h - 1] = X[b, h] - d
            G[b, h - 1] = G[b, h] - A * d
            self.hd[b] = h - 1


def main(pkg, out_csv):
    with open(os.path.join(pkg, "network.json")) as fh:
        net = json.load(fh)
    Tg = float(net["ground_C"])
    hours = float(net["hours"])
    nodes = pd.read_csv(os.path.join(pkg, "nodes.csv"), dtype=str)["node"].str.strip().tolist()
    nid = {n: i for i, n in enumerate(nodes)}
    pipes = pd.read_csv(os.path.join(pkg, "pipes.csv"), dtype={"pipe": str, "from_node": str, "to_node": str})
    for c in ("pipe", "from_node", "to_node"):
        pipes[c] = pipes[c].str.strip()
    for n in list(pipes.from_node) + list(pipes.to_node):
        if n not in nid:
            nid[n] = len(nodes)
            nodes.append(n)
    plant_name = str(net["plant_node"]).strip()
    if plant_name not in nid:
        nid[plant_name] = len(nodes)
        nodes.append(plant_name)
    nn = len(nodes)
    plant = nid[plant_name]
    pu = pipes.from_node.map(nid).to_numpy()
    pv = pipes.to_node.map(nid).to_numpy()
    R = pipes.resistance_Pa_s2_kg2.to_numpy(float)
    V = pipes.volume_m3.to_numpy(float)
    tau = pipes.loss_time_h.to_numpy(float)
    pid = {p: i for i, p in enumerate(pipes["pipe"])}

    subs = pd.read_csv(os.path.join(pkg, "substations.csv"), dtype={"substation": str, "node": str})
    subs["substation"] = subs.substation.str.strip()
    subs["node"] = subs.node.str.strip()
    sid = {s: i for i, s in enumerate(subs.substation)}
    sn = subs.node.map(nid).to_numpy()
    Tr = subs.return_C.to_numpy(float)
    K = subs.valve_capacity.to_numpy(float)
    ns = len(subs)

    nsteps = int(round(hours / DTH))

    dem = pd.read_csv(os.path.join(pkg, "demand.csv"), dtype={"substation": str})
    dem["substation"] = dem.substation.str.strip()
    Qs = np.zeros((nsteps, ns))
    for s, g in dem.groupby("substation"):
        g = g.sort_values("time_h", kind="stable")
        ix = schedule_index(g.time_h.to_numpy(float), nsteps)
        Qs[:, sid[s]] = g.heat_kW.to_numpy(float)[np.maximum(ix, 0)]
    plantdf = pd.read_csv(os.path.join(pkg, "plant.csv")).sort_values("time_h", kind="stable")
    ix = np.maximum(schedule_index(plantdf.time_h.to_numpy(float), nsteps), 0)
    Tsup = plantdf.supply_C.to_numpy(float)[ix]
    DPs = plantdf.dp_Pa.to_numpy(float)[ix]

    ini = pd.read_csv(os.path.join(pkg, "initial.csv"), dtype={"kind": str, "name": str, "network": str})
    for c in ("kind", "name", "network"):
        ini[c] = ini[c].str.strip()
    T0s = np.full(len(pipes), Tg)
    T0r = np.full(len(pipes), Tg)
    Ts = np.full(nn, Tg)
    Trn = np.full(nn, Tg)
    for kind, name, netw, T in ini[["kind", "name", "network", "temp_C"]].itertuples(index=False):
        if kind == "pipe" and name in pid:
            (T0s if netw == "supply" else T0r)[pid[name]] = T
        elif kind == "node" and name in nid:
            (Ts if netw == "supply" else Trn)[nid[name]] = T

    pts = pd.read_csv(os.path.join(pkg, "points.csv"), dtype={"point": str, "item": str, "quantity": str})
    pts["item"] = pts["item"].str.strip()
    pts["quantity"] = pts["quantity"].str.strip()
    pstep = np.rint(pts.time_h.to_numpy(float) / DTH).astype(int)
    want_steps = set(pstep.tolist())

    hyd = Hydraulics(nn, plant, pu, pv, R, sn, K)
    sup = Plugs(V, T0s, tau, Tg)
    ret = Plugs(V, T0r, tau, Tg)

    rec_Ts = {0: Ts.copy()}
    rec_Tret = {0: Trn[plant]}
    E = np.zeros((nsteps + 1, ns))  # cumulative energy kJ
    Ecur = np.zeros(ns)
    is_plant_node = np.zeros(nn, bool)
    is_plant_node[plant] = True

    for k in range(1, nsteps + 1):
        tk = k * DTH
        Q = Qs[k - 1]
        DP = DPs[k - 1]
        mwant = Q / (CP * (Ts[sn] - Tr))
        mp, ms = hyd.step(DP, mwant)
        dv = mp * DT / RHO
        # supply
        To = sup.outflow(dv, tk)
        mass = np.zeros(nn)
        heat = np.zeros(nn)
        am = np.abs(mp) * DT
        dst = np.where(mp > 0, pv, pu)
        act = mp != 0
        np.add.at(mass, dst[act], am[act])
        np.add.at(heat, dst[act], am[act] * To[act])
        # plant feed = what the network takes from the plant node
        src = np.where(mp > 0, pu, pv)
        take = am[act & (src == plant)].sum() + ms[sn == plant].sum() * DT
        if take > 0:
            mass[plant] += take
            heat[plant] += take * Tsup[k - 1]
        nz = mass > 0
        Ts = Ts.copy()
        Ts[nz] = heat[nz] / mass[nz]
        Ecur = Ecur + ms * DT * CP * (Ts[sn] - Tr)
        E[k] = Ecur
        sup.inflow(dv, Ts[pu], Ts[pv], tk)
        # return: flow reversed; return pipe flows v->u for mp>0
        dvr = -dv
        Tor = ret.outflow(dvr, tk)
        mass = np.zeros(nn)
        heat = np.zeros(nn)
        dstr = np.where(mp > 0, pu, pv)
        np.add.at(mass, dstr[act], am[act])
        np.add.at(heat, dstr[act], am[act] * Tor[act])
        sm = ms * DT
        np.add.at(mass, sn, sm)
        np.add.at(heat, sn, sm * Tr)
        nz = mass > 0
        Trn = Trn.copy()
        Trn[nz] = heat[nz] / mass[nz]
        ret.inflow(dvr, Trn[pu], Trn[pv], tk)
        if k in want_steps:
            rec_Ts[k] = Ts
            rec_Tret[k] = Trn[plant]

    vals = []
    for (point, item, q), k in zip(pts[["point", "item", "quantity"]].itertuples(index=False), pstep):
        k = int(k)
        if q == "return_C":
            v = rec_Tret[k]
        elif q == "supply_C":
            v = rec_Ts[k][sn[sid[item]]]
        else:
            k0 = max(k - int(round(1.0 / DTH)), 0)
            v = (E[k, sid[item]] - E[k0, sid[item]]) / 3600.0
        vals.append("%s,%.9f" % (point, v))
    with open(out_csv, "w") as fh:
        fh.write("point,value\n")
        fh.write("\n".join(vals))
        fh.write("\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
