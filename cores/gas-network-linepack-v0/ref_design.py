#!/usr/bin/env python3
"""designday.py PACKAGE_DIR OUT_CSV: the GD-3 design-day pressures of one network (the reference).

Reads the package, orders the field team (the mains worked on since their latest survey, and any boundary
valve or customer meter whose campaign node balances do not close), and runs the periodic design day.
"""
import csv
import datetime as dtm
import json
import os
import subprocess
import sys

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl

P_ATM = 1.01325
EXP = 1.82
STEPS, DT = 240, 0.1
GAS_DAY = [6 + k if 6 + k < 24 else k - 18 for k in range(24)]
CHANGES = ("RENEWED", "RELINED", "LAID")


def rows(pkg, name):
    with open(os.path.join(pkg, name), newline="") as f:
        return list(csv.DictReader(f))


def k_of(p_from_g, dp, q):
    pa = p_from_g + P_ATM
    pb = pa - dp
    return (pa * pa - pb * pb) / (q * abs(q) ** (EXP - 1))


def q_of(dp2, K):
    return np.sign(dp2) * (np.abs(dp2) / K) ** (1 / EXP)


def dq_of(dp2, K):
    return (1 / EXP) * (np.abs(dp2) / K + 1e-12) ** (1 / EXP - 1) / K


class Package:
    def __init__(self, pkg):
        self.pkg = pkg
        self.info = json.load(open(os.path.join(pkg, "network.json")))
        self.mains = rows(pkg, "mains.csv")
        self.surveys = rows(pkg, "surveys.csv")
        self.works = rows(pkg, "work_log.csv")
        self.prs = rows(pkg, "prs.csv")
        self.govs = rows(pkg, "governors.csv")
        self.design = rows(pkg, "design_day.csv")
        self.custs = rows(pkg, "customers.csv")
        self.valves = rows(pkg, "boundary_valves.csv")
        self.meter_rows = rows(pkg, "customer_meters.csv")
        nodes = set()
        for m in self.mains:
            nodes.add(m["from_node"])
            nodes.add(m["to_node"])
        self.nodes = sorted(nodes)
        self.ix = {n: i for i, n in enumerate(self.nodes)}
        self.latest = {}
        self.by_date = {}
        for r in self.surveys:
            rec = (r["date"], float(r["p_from_barg"]), float(r["dp_bar"]), float(r["q_m3h"]))
            if r["main"] not in self.latest or rec[0] > self.latest[r["main"]][0]:
                self.latest[r["main"]] = rec
            self.by_date.setdefault(r["date"], {})[r["main"]] = rec
        self.meter = {}
        for r in self.meter_rows:
            self.meter.setdefault(r["meter"], {})[r["time"]] = float(r["q_m3h"])

    def changed(self):
        """Mains renewed, relined or laid after their latest survey on file (or never surveyed)."""
        out = []
        for m in self.mains:
            name = m["main"]
            last = self.latest.get(name, ("0000-00-00",))[0]
            if any(w["main"] == name and w["work"] in CHANGES and w["date"] > last for w in self.works) \
                    or name not in self.latest:
                out.append(name)
        return out

    def balances(self):
        """Per campaign, the misclosure at every node whose flows are all on file (m3/h, into the node > 0),
        with the bound the readings' stated accuracy puts on it."""
        demand_nodes = {g["node"] for g in self.govs} | {p["node"] for p in self.prs}
        cust_at = {c["node"]: c["meter"] for c in self.custs}
        ends = {m["main"]: (m["from_node"], m["to_node"]) for m in self.mains}
        out = {}
        for date, recs in sorted(self.by_date.items()):
            net, mag = {}, {}
            for name, (_d, _p, _dp, q) in recs.items():
                a, b = ends[name]
                net[a] = net.get(a, 0.0) - q
                net[b] = net.get(b, 0.0) + q
                mag[a] = mag.get(a, 0.0) + abs(q)
                mag[b] = mag.get(b, 0.0) + abs(q)
            for node in net:
                if node in demand_nodes:
                    continue
                miss, bound = net[node], 0.01 * mag[node]
                if node in cust_at:
                    t = date + " 13:00"
                    if t not in self.meter.get(cust_at[node], {}):
                        continue
                    took = self.meter[cust_at[node]][t]
                    miss -= took
                    bound += 0.01 * took
                out.setdefault(node, []).append((date, miss, bound))
        return out


def suspects(pk):
    """Boundary valves and customer meters whose node does not balance in the latest campaigns."""
    bal = pk.balances()
    vnode = {v["node"]: v["valve"] for v in pk.valves}
    cnode = {c["node"]: c["meter"] for c in pk.custs}
    found = []
    for node, seq in bal.items():
        seq = sorted(seq)[-2:]
        if all(abs(m) > 3 * b for _d, m, b in seq):
            if node in vnode:
                found.append((max(abs(m) for _d, m, _b in seq), vnode[node]))
            elif node in cnode:
                found.append((max(abs(m) for _d, m, _b in seq), cnode[node]))
    return [name for _m, name in sorted(found, reverse=True)]


def order(pk, items):
    if not items:
        return {}
    try:
        p = subprocess.run(["gdsurvey", pk.pkg] + items, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return {}
    if p.returncode != 0:
        return {}
    got, head = {}, None
    for line in p.stdout.strip().splitlines():
        cells = line.strip().split(",")
        if cells[0] in ("main", "valve", "meter"):
            head = cells[0]
            continue
        got[cells[0]] = (head, [float(x) for x in cells[1:]])
    return got


class Model:
    def __init__(self, pk, read):
        ix = pk.ix
        n = self.n = len(pk.nodes)
        a, b, K, V = [], [], [], []
        for m in pk.mains:
            name = m["main"]
            if name in read and read[name][0] == "main":
                pf, dp, q = read[name][1]
            else:
                _d, pf, dp, q = pk.latest[name]
            a.append(ix[m["from_node"]])
            b.append(ix[m["to_node"]])
            K.append(k_of(pf, dp, q))
            D = float(m["diameter_mm"]) / 1000
            V.append(np.pi / 4 * D * D * float(m["length_m"]))
        self.a, self.b, self.K = np.array(a), np.array(b), np.array(K)
        C = np.zeros(n)
        np.add.at(C, self.a, np.array(V) / 2)
        np.add.at(C, self.b, np.array(V) / 2)
        self.C = C / P_ATM
        self.pi = np.array([ix[p["node"]] for p in pk.prs])
        self.pset = np.array([float(p["set_point_barg"]) + P_ATM for p in pk.prs])
        self.pcap = np.array([float(p["capacity_m3h"]) for p in pk.prs])
        vi, vp, vK = [], [], []
        for v in pk.valves:
            r = read.get(v["valve"])
            if r and r[0] == "valve" and abs(r[1][2]) > 1.0:
                p_node, p_nb, q = r[1]
                pn, pb = p_node + P_ATM, p_nb + P_ATM
                vi.append(ix[v["node"]])
                vp.append(float(v["neighbour_pressure_barg"]) + P_ATM)
                vK.append(abs(pb * pb - pn * pn) / abs(q) ** EXP)
        self.vi, self.vp, self.vK = np.array(vi, int), np.array(vp), np.array(vK)
        self.rows = np.concatenate([self.b, self.b, self.a, self.a, np.arange(n)])
        self.cols = np.concatenate([self.a, self.b, self.a, self.b, np.arange(n)])

    def balance(self, p):
        a, b = self.a, self.b
        dp2 = p[a] ** 2 - p[b] ** 2
        Q = q_of(dp2, self.K)
        g = dq_of(dp2, self.K)
        inflow = np.zeros(self.n)
        np.add.at(inflow, b, Q)
        np.add.at(inflow, a, -Q)
        diag = np.zeros(self.n)
        if len(self.vi):
            dv = self.vp ** 2 - p[self.vi] ** 2
            np.add.at(inflow, self.vi, q_of(dv, self.vK))
            np.add.at(diag, self.vi, -dq_of(dv, self.vK) * 2 * p[self.vi])
        ga, gb = 2 * g * p[a], 2 * g * p[b]
        return inflow, np.concatenate([ga, -gb, -ga, gb, diag])

    def step(self, p0, demand, dt, mode):
        n = self.n
        p = p0.copy()
        for _sweep in range(20):
            fixed = self.pi[mode == 0]
            p[fixed] = self.pset[mode == 0]
            src = np.zeros(n)
            np.add.at(src, self.pi[mode == 1], self.pcap[mode == 1])
            free = np.ones(n, bool)
            free[fixed] = False
            fidx = np.flatnonzero(free)
            for _it in range(60):
                inflow, data = self.balance(p)
                r = inflow + src - demand
                if dt:
                    r -= self.C * (p - p0) / dt
                    data[-n:] -= self.C / dt
                J = sp.csc_matrix((data, (self.rows, self.cols)), shape=(n, n))[fidx][:, fidx]
                d = spl.spsolve(J.tocsc(), -r[fidx])
                big = np.max(np.abs(d))
                if big > 0.5:
                    d *= 0.5 / big
                p[fidx] += d
                if big < 1e-9:
                    break
            inflow, _ = self.balance(p)
            r = inflow + src - demand
            if dt:
                r -= self.C * (p - p0) / dt
            need = -r[self.pi]
            new = mode.copy()
            for k in range(len(self.pi)):
                if mode[k] == 0 and need[k] > self.pcap[k]:
                    new[k] = 1
                elif mode[k] == 0 and need[k] < 0:
                    new[k] = 2
                elif mode[k] == 1 and p[self.pi[k]] > self.pset[k]:
                    new[k] = 0
                elif mode[k] == 2 and p[self.pi[k]] < self.pset[k]:
                    new[k] = 0
            if np.array_equal(new, mode):
                return p, mode
            mode = new
        raise RuntimeError("PRS modes did not settle")

    def day(self, dem):
        mode = np.zeros(len(self.pi), int)
        p = np.full(self.n, self.pset.max() - 0.3)
        p, _ = self.step(p, dem.mean(axis=0), None, mode)
        for _day in range(60):
            start = p.copy()
            P = np.zeros((STEPS, self.n))
            for k in range(STEPS):
                p, mode = self.step(p, dem[k // 10], DT, mode)
                P[k] = p
            if np.max(np.abs(p - start)) < 1e-7:
                return P
        raise RuntimeError("no periodic day")


def demand(pk, read):
    n = len(pk.nodes)
    dem = np.zeros((24, n))
    gnode = {g["governor"]: pk.ix[g["node"]] for g in pk.govs}
    for r in pk.design:
        dem[GAS_DAY.index(int(r["hour"])), gnode[r["governor"]]] += float(r["demand_m3h"])
    for c in pk.custs:
        ratio = 1.0
        rr = read.get(c["meter"])
        if rr and rr[0] == "meter" and abs(rr[1][0] - 100.0) > 1.0:
            ratio = rr[1][0] / 100.0
        sums, cnt = np.zeros(24), np.zeros(24)
        for t, q in pk.meter.get(c["meter"], {}).items():
            day = dtm.date.fromisoformat(t[:10])
            if day.weekday() < 5:
                h = int(t[11:13])
                sums[h] += q / ratio
                cnt[h] += 1
        for k, h in enumerate(GAS_DAY):
            dem[k, pk.ix[c["node"]]] += sums[h] / cnt[h]
    return dem


def solve(pk, read):
    model = Model(pk, read)
    P = model.day(demand(pk, read))
    out = []
    for g in pk.govs:
        out.append((g["governor"], float(P[:, pk.ix[g["node"]]].min() - P_ATM)))
    return out


def main(argv):
    pk = Package(argv[1])
    items = pk.changed()
    spare = int(pk.info["survey_allowance"]) - len(items)
    if spare > 0:
        items += suspects(pk)[:spare]
    read = order(pk, items)
    res = solve(pk, read)
    with open(argv[2], "w") as f:
        f.write("governor,min_pressure_barg\n")
        for g, v in res:
            f.write("%s,%.4f\n" % (g, v))


if __name__ == "__main__":
    main(sys.argv)
