"""ref_heat.py PACKAGE_DIR OUT_CSV: HN-3, written to run fast.

- Schedules are turned into one table of values a step before the run.
- Pipes are deques held in a ring buffer, one row a pipe, so a step moves every pipe at once; a step's outflow
  takes as many parcels from each pipe's end as its volume needs, whole parcels in one pass and the last in part.
  A parcel keeps vol and w = vol (T0 - Tg) exp(t0 / tau), so its temperature at t is Tg + w / vol exp(-t / tau).
- Hydraulics: Newton on the supply pressures from the last step's state, with the factorisation of the Jacobian
  kept from step to step and made again only when the iteration slows.
"""
import csv, json, math, os, sys
import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

RHO, CP, DT = 975.0, 4.19, 120.0
DELTA = 1e-6


def rows(folder, name):
    with open(os.path.join(folder, name), newline="") as f:
        return list(csv.DictReader(f))


def table(names, entries, key, value, times):
    """value of each name at each of `times` (last row at or before)."""
    out = np.zeros((len(times), len(names)))
    per = {}
    for r in entries:
        per.setdefault(r[key], []).append((float(r["time_h"]) * 3600.0, value(r)))
    for i, n in enumerate(names):
        e = sorted(per[n], key=lambda x: x[0])
        ts = np.array([x[0] for x in e]); vs = np.array([x[1] for x in e])
        idx = np.searchsorted(ts, times + 1e-9, side="right") - 1
        out[:, i] = vs[np.maximum(idx, 0)]
    return out


class Tapes:
    """Every pipe's content, parcels from the from_node end (left) to the to_node end (right)."""

    def __init__(self, V, tau, tg, temp0, cap=64):
        self.P = len(V); self.cap = cap; self.tau = tau; self.tg = tg
        self.vol = np.zeros((self.P, cap)); self.w = np.zeros((self.P, cap))
        self.lo = np.zeros(self.P, int); self.n = np.ones(self.P, int)        # first slot, number of parcels
        self.vol[:, 0] = V; self.w[:, 0] = V * (temp0 - tg)                   # entered at t = 0
        self.rows = np.arange(self.P)

    def grow(self):
        cap = self.cap * 2
        for name in ("vol", "w"):
            a = getattr(self, name); b = np.zeros((self.P, cap))
            idx = (self.lo[:, None] + np.arange(self.cap)[None, :]) % self.cap
            b[:, :self.cap] = a[self.rows[:, None], idx]
            setattr(self, name, b)
        self.lo[:] = 0; self.cap = cap

    def take(self, amount, right, t):
        """Remove `amount` of water from the right end where `right`, else the left; return its heat (m3 deg C)."""
        heat = np.zeros(self.P); left = amount.copy()
        decay = np.exp(-t / self.tau)
        active = np.nonzero(left > 0)[0]
        while active.size:
            r = right[active]
            slot = np.where(r, (self.lo[active] + self.n[active] - 1) % self.cap, self.lo[active])
            v = self.vol[active, slot]; w = self.w[active, slot]
            whole = v <= left[active] * (1 + 1e-12)
            use = np.where(whole, v, left[active])
            frac = np.where(v > 0, use / np.where(v > 0, v, 1.0), 0.0)
            heat[active] += use * self.tg + frac * w * decay[active]
            left[active] -= use
            # whole parcels go; a partial one is left smaller
            gone = active[whole]
            if gone.size:
                rg = right[gone]
                self.n[gone] -= 1
                self.lo[gone] = np.where(rg, self.lo[gone], (self.lo[gone] + 1) % self.cap)
            part = active[~whole]
            if part.size:
                sl = slot[~whole]; fr = frac[~whole]
                self.vol[part, sl] -= use[~whole]; self.w[part, sl] *= (1 - fr)
            active = active[(left[active] > 1e-12 * np.maximum(amount[active], 1e-30)) & (self.n[active] > 0)]
        return heat

    def put(self, amount, right, temp, t):
        """Add a parcel of `amount` at temperature `temp`, entered at t, at the right end where `right`."""
        idx = np.nonzero(amount > 0)[0]
        if not idx.size: return
        if (self.n[idx] >= self.cap).any(): self.grow()
        r = right[idx]
        slot = np.where(r, (self.lo[idx] + self.n[idx]) % self.cap, (self.lo[idx] - 1) % self.cap)
        self.vol[idx, slot] = amount[idx]
        self.w[idx, slot] = amount[idx] * (temp[idx] - self.tg) * np.exp(t / self.tau[idx])
        self.lo[idx] = np.where(r, self.lo[idx], slot)
        self.n[idx] += 1


def main(folder, out_csv):
    head = json.load(open(os.path.join(folder, "network.json")))
    tg = float(head["ground_C"]); hours = int(head["hours"])
    nodes = [r["node"] for r in rows(folder, "nodes.csv")]; ix = {n: i for i, n in enumerate(nodes)}; N = len(nodes)
    plant = ix[head["plant_node"]]
    pr = rows(folder, "pipes.csv"); P = len(pr)
    u = np.array([ix[r["from_node"]] for r in pr]); v = np.array([ix[r["to_node"]] for r in pr])
    R = np.array([float(r["resistance_Pa_s2_kg2"]) for r in pr]); V = np.array([float(r["volume_m3"]) for r in pr])
    tau = np.array([float(r["loss_time_h"]) for r in pr]) * 3600.0
    subs = rows(folder, "substations.csv"); S = len(subs)
    snode = np.array([ix[r["node"]] for r in subs]); Tr = np.array([float(r["return_C"]) for r in subs])
    K = np.array([float(r["valve_capacity"]) for r in subs])
    steps = hours * 30
    starts = np.arange(steps) * DT
    Qtab = table([r["substation"] for r in subs], rows(folder, "demand.csv"), "substation", lambda r: float(r["heat_kW"]), starts)
    pl = rows(folder, "plant.csv")
    for r in pl: r["k"] = "plant"
    Tpl = table(["plant"], pl, "k", lambda r: float(r["supply_C"]), starts)[:, 0]
    DPP = table(["plant"], pl, "k", lambda r: float(r["dp_Pa"]), starts)[:, 0]
    pn = {r["pipe"]: i for i, r in enumerate(pr)}
    t0s = np.zeros(P); t0r = np.zeros(P); Ts = np.zeros(N); Trn = np.zeros(N)
    for r in rows(folder, "initial.csv"):
        if r["kind"] == "pipe":
            (t0s if r["network"] == "supply" else t0r)[pn[r["name"]]] = float(r["temp_C"])
        else:
            (Ts if r["network"] == "supply" else Trn)[ix[r["name"]]] = float(r["temp_C"])
    sup = Tapes(V, tau, tg, t0s); ret = Tapes(V, tau, tg, t0r)
    points = rows(folder, "points.csv")
    at = {}
    sname = {r["substation"]: i for i, r in enumerate(subs)}
    for r in points: at.setdefault(int(round(float(r["time_h"]) * 30)), []).append(r)
    free = np.array([i for i in range(N) if i != plant]); pos = -np.ones(N, int); pos[free] = np.arange(N - 1)
    # Jacobian pattern, once
    Jr = np.concatenate([v, v, u, u, snode]); Jc = np.concatenate([v, u, u, v, snode])
    keep = (pos[Jr] >= 0) & (pos[Jc] >= 0)
    Jr_, Jc_ = pos[Jr[keep]], pos[Jc[keep]]
    out_plant = (u == plant).astype(float) - (v == plant).astype(float)
    h = np.zeros(N); lu = None
    heat_acc = np.zeros(S); results = {}
    def residual(h, mwant, dpp):
        dh = h[v] - h[u]; a = np.abs(dh); m = dh / np.sqrt(R * (a + DELTA))
        dpn = dpp - 2.0 * h[snode]; mmax = K * np.sqrt(np.maximum(dpn, 0.0)); sat = mmax < mwant
        ms = np.where(sat, mmax, mwant)
        res = np.bincount(v, m, N) - np.bincount(u, m, N) - np.bincount(snode, ms, N)
        return res, m, ms, dh, a, dpn, sat
    for k in range(1, steps + 1):
        t1 = k * DT; dpp = DPP[k - 1]
        mwant = Qtab[k - 1] / (CP * (Ts[snode] - Tr))
        res, m, ms, dh, a, dpn, sat = residual(h, mwant, dpp)
        scale = max(1.0, ms.sum())
        it = 0; prev = np.inf
        while np.abs(res[free]).max() >= 1e-10 * scale:
            it += 1
            norm = np.abs(res[free]).max()
            if lu is None or norm > 0.5 * prev or it > 6:
                g = (a + 2 * DELTA) / (2 * np.sqrt(R) * (a + DELTA) ** 1.5)
                gs = np.where(sat & (dpn > 0), K / np.sqrt(np.maximum(dpn, 1e-30)), 0.0)
                Jv = np.concatenate([g, -g, g, -g, gs])[keep]
                lu = splu(sp.csc_matrix((Jv, (Jr_, Jc_)), shape=(N - 1, N - 1)))
            prev = norm
            step = lu.solve(-res[free])
            lam = 1.0
            while True:
                hn = h.copy(); hn[free] += lam * step
                r2 = residual(hn, mwant, dpp)
                if np.abs(r2[0][free]).sum() < np.abs(res[free]).sum() or lam < 1e-4: break
                lam *= 0.5
            h = hn; res, m, ms, dh, a, dpn, sat = r2
            if it > 200: raise SystemExit("hydraulics did not converge")
        vol = np.abs(m) * DT / RHO
        fwd = m > 0
        # supply: forward flow leaves at the right end, enters at the left
        heat = sup.take(vol, fwd, t1)
        avol = np.bincount(np.where(fwd, v, u), vol, N); aheat = np.bincount(np.where(fwd, v, u), heat, N)
        net = float(np.dot(out_plant, m))
        if net > 0: avol[plant] += net * DT / RHO; aheat[plant] += net * DT / RHO * Tpl[k - 1]
        Ts = np.where(avol > 0, aheat / np.where(avol > 0, avol, 1.0), Ts)
        sup.put(vol, ~fwd, np.where(fwd, Ts[u], Ts[v]), t1)
        heat_acc += ms * CP * (Ts[snode] - Tr)
        # return: flows reversed
        heat = ret.take(vol, ~fwd, t1)
        sv = ms * DT / RHO
        avol = np.bincount(np.where(fwd, u, v), vol, N) + np.bincount(snode, sv, N)
        aheat = np.bincount(np.where(fwd, u, v), heat, N) + np.bincount(snode, sv * Tr, N)
        Trn = np.where(avol > 0, aheat / np.where(avol > 0, avol, 1.0), Trn)
        ret.put(vol, fwd, np.where(fwd, Trn[v], Trn[u]), t1)
        if k % 30 == 0:
            for r in at.get(k, []):
                q = r["quantity"]
                if q == "supply_C": results[r["point"]] = Ts[snode[sname[r["item"]]]]
                elif q == "heat_kW": results[r["point"]] = heat_acc[sname[r["item"]]] / 30.0
                else: results[r["point"]] = Trn[plant]
            heat_acc[:] = 0.0
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["point", "value"])
        for r in points: w.writerow([r["point"], "%.6f" % results[r["point"]]])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
