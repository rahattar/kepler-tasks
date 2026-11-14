#!/usr/bin/env python3
"""District airflow to VS-4.

Usage: python3 airflow.py PACKAGE_DIR OUT_CSV
"""
import bisect
import csv
import json
import os
import shutil
import subprocess
import sys
from collections import deque

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


def read_csv(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------- fans
class FanPart:
    """One falling part of a fan characteristic, extended monotonically
    (strictly falling) outside its own range so the network problem stays
    well posed; q_lo..q_hi is the part's own range."""

    def __init__(self, qs, ps, q_lo, q_hi):
        qs = list(qs)
        ps = list(ps)
        s_left = (ps[1] - ps[0]) / (qs[1] - qs[0])
        s_right = (ps[-1] - ps[-2]) / (qs[-1] - qs[-2])
        s_left = min(s_left, -1.0)
        s_right = min(s_right, -1.0)
        span = 1e4
        qs = [qs[0] - span] + qs + [qs[-1] + span]
        ps = [ps[0] - s_left * span] + ps + [ps[-1] + s_right * span]
        self.q = np.array(qs, float)
        self.p = np.array(ps, float)
        self.slope = np.diff(self.p) / np.diff(self.q)
        # cumulative integral of p at knots
        self.cum = np.concatenate([[0.0], np.cumsum(0.5 * (self.p[1:] + self.p[:-1]) * np.diff(self.q))])
        self._ql = self.q.tolist()
        self._pl = self.p.tolist()
        self._sl = self.slope.tolist()
        self._cl = self.cum.tolist()
        self._n = len(self._ql)
        self.q_lo = q_lo
        self.q_hi = q_hi

    def eval(self, x):
        """Return P(x), dP/dx, integral of P from the first knot to x."""
        x = float(x)
        i = bisect.bisect_right(self._ql, x) - 1
        if i < 0:
            i = 0
        elif i > self._n - 2:
            i = self._n - 2
        d = x - self._ql[i]
        p0 = self._pl[i]
        s = self._sl[i]
        return p0 + s * d, s, self._cl[i] + p0 * d + 0.5 * s * d * d


def fan_parts(qs, ps):
    qs = np.asarray(qs, float)
    ps = np.asarray(ps, float)
    n = len(qs)
    # dip: lowest local min; peak: highest local max after it
    i_dip = None
    for i in range(1, n - 1):
        if ps[i] <= ps[i - 1] and ps[i] <= ps[i + 1]:
            i_dip = i
            break
    i_peak = i_dip + int(np.argmax(ps[i_dip:]))
    low = FanPart(qs[: i_dip + 1], ps[: i_dip + 1], qs[0], qs[i_dip])
    high = FanPart(qs[i_peak:], ps[i_peak:], qs[i_peak], qs[-1])
    return {"H": high, "L": low}


# ---------------------------------------------------------------- network
class Network:
    def __init__(self, names, frm, to, fan_index):
        self.names = names
        nodes = sorted(set(frm) | set(to))
        idx = {n: i for i, n in enumerate(nodes)}
        self.nb = nb = len(names)
        a = [idx[x] for x in frm]
        b = [idx[x] for x in to]
        adj = [[] for _ in nodes]
        for e in range(nb):
            adj[a[e]].append((b[e], e, 1))
            adj[b[e]].append((a[e], e, -1))
        root = idx.get("ATM", 0)
        parent = [None] * len(nodes)  # (parent node, edge, sign: +1 if edge goes parent->node)
        depth = [-1] * len(nodes)
        depth[root] = 0
        dq = deque([root])
        tree = set()
        while dq:
            u = dq.popleft()
            for v, e, s in adj[u]:
                if depth[v] < 0:
                    depth[v] = depth[u] + 1
                    parent[v] = (u, e, s)
                    tree.add(e)
                    dq.append(v)
        rows, cols, vals = [], [], []
        L = 0
        for e in range(nb):
            if e in tree:
                continue
            # loop: traverse edge e from a to b, then path b -> a in tree
            entries = {e: 1.0}
            u, v = b[e], a[e]
            # walk up from u (towards root) and v until meeting
            pu, pv = [], []
            while depth[u] > depth[v]:
                pn, pe, s = parent[u]; pu.append((pe, -s)); u = pn
            while depth[v] > depth[u]:
                pn, pe, s = parent[v]; pv.append((pe, s)); v = pn
            while u != v:
                pn, pe, s = parent[u]; pu.append((pe, -s)); u = pn
                pn, pe, s = parent[v]; pv.append((pe, s)); v = pn
            for pe, s in pu + pv:
                entries[pe] = entries.get(pe, 0.0) + s
            for k, s in entries.items():
                if s != 0:
                    rows.append(k); cols.append(L); vals.append(s)
            L += 1
        self.L = L
        self.N = sp.csr_matrix((vals, (rows, cols)), shape=(nb, L))
        self.NT = self.N.T.tocsr()
        self.fan_index = fan_index  # list of branch indices of fans
        self.f = np.zeros(L)

    def solve(self, R, parts, f0=None, tol=1e-9, maxit=200):
        """R: branch resistances; parts: list of FanPart for fans (aligned with fan_index)."""
        N, NT = self.N, self.NT
        fi = self.fan_index
        f = (self.f if f0 is None else f0).copy()

        def evaluate(f):
            q = N @ f
            h = R * q * np.abs(q)
            dh = 2.0 * R * np.abs(q)
            phi = np.sum(R * np.abs(q) ** 3) / 3.0
            for k, b in enumerate(fi):
                pt = parts[k]
                pv, sv, iv = pt.eval(q[b])
                h[b] -= pv
                dh[b] -= sv
                phi -= iv
            return q, h, dh, phi

        q, h, dh, phi = evaluate(f)
        scale = 1.0
        for it in range(maxit):
            g = NT @ h
            gn = np.max(np.abs(g))
            if it == 0:
                scale = max(np.max(np.abs(h)), 1.0)
            if gn < tol * scale:
                break
            d = np.maximum(dh, 1e-6 * np.maximum(R, 1e-9) + 1e-12)
            J = (NT @ sp.diags(d) @ N).tocsc()
            step = spla.spsolve(J, -g)
            t = 1.0
            gd = g @ step
            while True:
                fn = f + t * step
                qn, hn, dhn, phin = evaluate(fn)
                if phin <= phi + 1e-4 * t * gd + 1e-13 * abs(phi) or t < 1e-6:
                    break
                t *= 0.5
            f, q, h, dh, phi = fn, qn, hn, dhn, phin
        self.f = f
        return q, f


# ---------------------------------------------------------------- main
def main():
    pkg, out = sys.argv[1], sys.argv[2]
    P = lambda n: os.path.join(pkg, n)
    meta = json.load(open(P("district.json")))
    allowance = int(meta.get("survey_allowance", 0))
    branches = read_csv(P("branches.csv"))
    surveys = read_csv(P("surveys.csv"))
    work = read_csv(P("work_log.csv"))
    regs = read_csv(P("regulators.csv"))
    doors = read_csv(P("doors.csv"))
    fans = read_csv(P("fans.csv"))
    curves = read_csv(P("fan_curves.csv"))
    log = read_csv(P("log.csv"))
    points = read_csv(P("points.csv"))

    names = [r["branch"] for r in branches]
    bidx = {n: i for i, n in enumerate(names)}
    nb = len(names)

    # --- airway resistances from latest survey
    latest = {}
    for r in surveys:
        b = r["branch"]
        if b not in latest or r["date"] >= latest[b]["date"]:
            latest[b] = r
    # airways worked on (re-supported / enlarged) since their latest survey
    need = {}
    for r in work:
        if r["work"].strip().upper() not in ("RESUPPORTED", "ENLARGED"):
            continue
        b = r["branch"]
        s = latest.get(b)
        if s is None or r["date"] >= s["date"]:
            strict = s is None or r["date"] > s["date"]
            need[b] = need.get(b, False) or strict
    order = sorted(need, key=lambda b: (not need[b], b))
    order = [b for b in order if b in bidx]
    if len(order) > allowance:
        order = order[:allowance]
    fresh = {}
    if order:
        try:
            exe = shutil.which("pqsurvey")
            if exe is None:
                here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pqsurvey")
                exe = here if os.path.exists(here) else "/tmp/vfc_lc/app/pqsurvey"
            res = subprocess.run([exe, pkg] + order, capture_output=True, text=True, timeout=25)
            for line in res.stdout.splitlines():
                parts = line.strip().split(",")
                if len(parts) != 3 or parts[0] == "branch":
                    continue
                try:
                    fresh[parts[0]] = (float(parts[1]), float(parts[2]))
                except ValueError:
                    pass
        except Exception:
            pass

    R = np.zeros(nb)
    kinds = [r["kind"] for r in branches]
    items = [r["item"] for r in branches]
    for i, r in enumerate(branches):
        k = r["kind"]
        if k == "airway":
            b = r["branch"]
            if b in fresh and fresh[b][1] != 0:
                dp, q = fresh[b]
            elif b in latest:
                dp, q = float(latest[b]["dp_Pa"]), float(latest[b]["q_m3_s"])
            else:
                dp, q = 0.0, 1.0
            R[i] = dp / (q * abs(q)) if q != 0 else 0.0
        elif k in ("stopping", "fan"):
            R[i] = float(r["resistance_Ns2_m8"] or 0.0)
    R = np.maximum(R, 1e-9)

    reg_tab = {}
    for r in regs:
        reg_tab.setdefault(r["regulator"], {})[int(float(r["setting"]))] = float(r["resistance_Ns2_m8"])
    door_tab = {r["door"]: (float(r["resistance_closed_Ns2_m8"]), float(r["resistance_open_Ns2_m8"])) for r in doors}

    item_branches = {}
    for i in range(nb):
        if kinds[i] in ("regulator", "door") and items[i]:
            item_branches.setdefault(items[i], []).append(i)

    def item_R(item, setting):
        s = setting.strip()
        if item in door_tab:
            c, o = door_tab[item]
            return c if s.lower().startswith("c") else o
        return reg_tab[item][int(float(s))]

    # --- fans
    curve_pts = {}
    for r in curves:
        curve_pts.setdefault((r["model"], r["blade_setting"].strip()), []).append(
            (float(r["flow_m3_s"]), float(r["pressure_Pa"])))
    fan_index, fan_parts_list = [], []
    for r in fans:
        pts = curve_pts[(r["model"], r["blade_setting"].strip())]
        fan_index.append(bidx[r["branch"]])
        fan_parts_list.append(fan_parts([p[0] for p in pts], [p[1] for p in pts]))
    nf = len(fan_index)

    net = Network(names, [r["from_node"] for r in branches], [r["to_node"] for r in branches], fan_index)

    # --- log into states
    times = sorted(set(r["time"] for r in log))
    by_time = {}
    for r in log:
        by_time.setdefault(r["time"], []).append(r)

    def apply(Rv, rows):
        Rv = Rv.copy()
        for r in rows:
            it = r["item"]
            if it not in item_branches:
                continue
            v = item_R(it, r["setting"])
            for i in item_branches[it]:
                Rv[i] = v
        return Rv

    state = ["H"] * nf

    def parts_of(st):
        return [fan_parts_list[k][st[k]] for k in range(nf)]

    def violations(q, st):
        out = []
        for k in range(nf):
            pt = fan_parts_list[k][st[k]]
            x = q[fan_index[k]]
            if st[k] == "H" and x < pt.q_lo:
                out.append(k)
            elif st[k] == "L" and x > pt.q_hi:
                out.append(k)
        return out

    def settle(Rold, Rnew, st):
        """Move settings from Rold to Rnew, tracking fan parts; returns q and state."""
        st = list(st)
        f_start = net.f.copy()
        q, f = net.solve(Rnew, parts_of(st), f0=f_start)
        guard = 0
        t_lo = 0.0
        while violations(q, st) and guard < 4 * nf + 4:
            guard += 1
            lr0, lr1 = np.log(Rold), np.log(Rnew)
            Rt = lambda t: np.exp(lr0 + t * (lr1 - lr0))
            # find first fan to leave its part between t_lo and 1
            a, b = t_lo, 1.0
            fa = f_start
            for _ in range(22):
                m = 0.5 * (a + b)
                qm, fm = net.solve(Rt(m), parts_of(st), f0=fa)
                if violations(qm, st):
                    b = m
                else:
                    a, fa = m, fm
            qb, fb = net.solve(Rt(b), parts_of(st), f0=fa)
            v = violations(qb, st)
            if not v:
                v = violations(q, st)
            # pick the fan most beyond its end at b
            def depth(k):
                pt = fan_parts_list[k][st[k]]
                x = qb[fan_index[k]]
                return (pt.q_lo - x) if st[k] == "H" else (x - pt.q_hi)
            k = max(v, key=depth)
            st[k] = "L" if st[k] == "H" else "H"
            # settle in the new state at t=b, then continue to t=1
            qs_, f_start = net.solve(Rt(b), parts_of(st), f0=fb)
            t_lo = b
            q, f = net.solve(Rnew, parts_of(st), f0=f_start)
        return q, st

    # initial state
    Rcur = apply(R, by_time[times[0]])
    q, _ = net.solve(Rcur, parts_of(state))
    # if initial solution violates "beyond peak", still keep H (VS-4 says all start beyond peak)
    state_times = [times[0]]
    state_q = [q.copy()]
    for t in times[1:]:
        Rnew = apply(Rcur, by_time[t])
        q, state = settle(Rcur, Rnew, state)
        Rcur = Rnew
        state_times.append(t)
        state_q.append(q.copy())

    import bisect
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["point", "flow_m3_s"])
        for r in points:
            j = bisect.bisect_right(state_times, r["time"]) - 1
            j = max(j, 0)
            bi = bidx.get(r["branch"])
            val = float(state_q[j][bi]) if bi is not None else 0.0
            w.writerow([r["point"], "%.6f" % val])


if __name__ == "__main__":
    main()
