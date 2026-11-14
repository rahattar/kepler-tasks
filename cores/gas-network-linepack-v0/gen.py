"""gen.py: builds the gas-network core.

core/data/examples/{kestrel,heron}: clean, with expected.csv; core/data/pending/plover: both conditions, no
results, no book; core/hidden/<six>: shifted networks with truth.csv; crew/books/<network>.json for the
examples and the hidden networks. Conditions: a boundary valve booked closed that passes; a customer's meter
registering outside its accuracy. Both show only in the campaigns' node balances.
"""
import csv
import datetime as dtm
import json
import os
import shutil
import sys

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import minimum_spanning_tree, shortest_path, connected_components
from scipy.spatial import Delaunay

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gd import Net, P_ATM, STEPS, q_of  # noqa: E402

KR = 48600.0 * 0.6
SIZES = np.array([100, 125, 150, 180, 200, 250, 300, 355, 400, 450, 500, 600], float)
CAMPAIGNS = ["2024-01-17", "2025-12-10", "2026-02-04"]
REC0 = dtm.date(2025, 11, 3)                 # a Monday; the customers' meter record runs 21 weeks from here
REC_DAYS = 147
DOMESTIC = np.array([0.30, 0.27, 0.26, 0.27, 0.33, 0.52, 0.86, 1.00, 0.90, 0.72, 0.62, 0.58,
                     0.57, 0.55, 0.56, 0.62, 0.74, 0.90, 0.98, 0.95, 0.85, 0.70, 0.52, 0.38])   # by clock hour
COMMERCIAL = np.array([0.25, 0.24, 0.24, 0.25, 0.30, 0.45, 0.70, 0.88, 1.00, 0.98, 0.95, 0.93,
                       0.92, 0.92, 0.93, 0.92, 0.88, 0.75, 0.60, 0.48, 0.40, 0.34, 0.30, 0.27])
GAS_DAY = [6 + k if 6 + k < 24 else k - 18 for k in range(24)]   # clock hours from 06:00

CASES = {
    # name: where, seed, N, W, H, n_prs, setpoints, cap_frac, n_cust, n_valves, works after C3 (relined,
    # renewed, laid), pmin target, valve condition, meter condition
    "kestrel": dict(attempt=0, where="examples", seed=11, N=230, W=13, H=10, sets=[6.0, 6.0], cap=0.92, ncust=2, nval=2,
                    works=(2, 2, 1), target=3.0, valve=None, meter=None),
    "heron": dict(attempt=0, where="examples", seed=12, N=270, W=14, H=11, sets=[6.5, 6.5], cap=0.90, ncust=3, nval=3,
                  works=(3, 2, 1), target=2.8, valve=None, meter=None),
    "plover": dict(attempt=0, where="pending", seed=13, N=250, W=13, H=11, sets=[6.2, 6.2], cap=0.91, ncust=3, nval=3,
                   works=(2, 2, 1), target=2.9, valve=dict(nb=0.6, kq=1300), meter=dict(ratio=0.82)),
    "curlew": dict(attempt=1, where="hidden", seed=21, N=420, W=17, H=13, sets=[6.5, 6.3, 6.0], cap=0.88, ncust=3, nval=3,
                   works=(3, 3, 2), target=2.4, valve=dict(nb=0.5, kq=1500), meter=dict(ratio=0.80)),
    "dunlin": dict(attempt=0, where="hidden", seed=22, N=320, W=15, H=12, sets=[6.0, 6.0], cap=0.85, ncust=4, nval=2,
                   works=(3, 2, 1), target=2.6, valve=None, meter=dict(ratio=0.86), weekend_off=True),
    "merlin": dict(attempt=2, where="hidden", seed=23, N=380, W=16, H=12, sets=[6.4, 6.1], cap=0.89, ncust=2, nval=3,
                   works=(2, 3, 1), target=2.3, valve=dict(nb=-0.35, kq=1200), meter=None),
    "osprey": dict(attempt=0, where="hidden", seed=24, N=350, W=15, H=12, sets=[6.2, 6.2, 6.0], cap=0.90, ncust=3, nval=2,
                   works=(4, 3, 2), target=2.7, valve=None, meter=None),
    "siskin": dict(attempt=0, where="hidden", seed=25, N=460, W=18, H=13, sets=[6.5, 6.5], cap=0.90, ncust=3, nval=3,
                   works=(3, 3, 1), target=2.5, valve=dict(nb=-0.7, kq=1400), meter=dict(ratio=0.84)),
    "teal": dict(attempt=0, where="hidden", seed=26, N=330, W=15, H=12, sets=[6.0, 5.8], cap=0.88, ncust=2, nval=4,
                 works=(2, 2, 2), target=2.6, valve=dict(nb=0.8, kq=1100), meter=None),
}


def d2s(d):
    return d.strftime("%Y-%m-%d")


class Case:
    def __init__(self, name, spec):
        self.name, self.s = name, spec
        self.rng = np.random.default_rng(spec["seed"])

    # ------------------------------------------------------------------ the network as laid
    def layout(self):
        s, rng = self.s, self.rng
        N, W, H = s["N"], s["W"], s["H"]
        h = np.sqrt(W * H / N / 0.866)
        pts = []
        for j, y in enumerate(np.arange(0, H, h * 0.866)):
            for x in np.arange(0, W, h):
                pts.append((x + (j % 2) * h / 2, y))
        pts = np.array(pts) + rng.normal(0, 0.17 * h, (len(pts), 2))
        pts = pts[rng.random(len(pts)) > 0.07]
        n = len(pts)
        tri = Delaunay(pts)
        E = set()
        for t in tri.simplices:
            for i in range(3):
                a, b = sorted((int(t[i]), int(t[(i + 1) % 3])))
                E.add((a, b))
        E = np.array(sorted(E))
        L = np.linalg.norm(pts[E[:, 0]] - pts[E[:, 1]], axis=1)
        keep = L < 1.6 * h
        ncomp, _lab = connected_components(sp.coo_matrix((L[keep], (E[keep, 0], E[keep, 1])), shape=(n, n)),
                                           directed=False)
        if ncomp > 1:                       # the length filter cut the town apart: keep the full spanning tree
            Tf = minimum_spanning_tree(sp.coo_matrix((L, (E[:, 0], E[:, 1])), shape=(n, n)).tocsr()).tocoo()
            full = set(zip(np.minimum(Tf.row, Tf.col).tolist(), np.maximum(Tf.row, Tf.col).tolist()))
            keep = keep | np.array([(int(a), int(b)) in full for a, b in E])
        E, L = E[keep], L[keep]
        G = sp.coo_matrix((L, (E[:, 0], E[:, 1])), shape=(n, n)).tocsr()
        T = minimum_spanning_tree(G).tocoo()
        tree = set(zip(np.minimum(T.row, T.col).tolist(), np.maximum(T.row, T.col).tolist()))
        spare = [k for k, (a, b) in enumerate(E) if (a, b) not in tree]
        rng.shuffle(spare)
        loops = spare[: int(0.10 * len(E))]
        sel = sorted([k for k, e in enumerate(E) if tuple(e) in tree] + loops)
        self.tree = tree
        self.pts, self.n = pts, n
        self.E, self.L = E[sel], L[sel] * 1.15 * 1000.0         # m, routed
        self.spare = [tuple(E[k]) for k in spare[int(0.10 * len(E)):]]   # candidates for mains laid later

    def roles(self):
        s, rng, pts, n = self.s, self.rng, self.pts, self.n
        cx, cy = pts.mean(axis=0)
        ang = np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx)
        rad = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
        nprs = len(s["sets"])
        prs = []
        for k in range(nprs):
            a0 = rng.uniform(-np.pi, np.pi) if k == 0 else ang[prs[0]] + 2 * np.pi * k / nprs
            score = rad / rad.max() - 0.6 * np.abs(np.angle(np.exp(1j * (ang - a0))))
            score[prs] = -9
            prs.append(int(np.argmax(score)))
        deg = np.bincount(self.E.ravel(), minlength=n)
        dprs = np.min([np.hypot(pts[:, 0] - pts[p, 0], pts[:, 1] - pts[p, 1]) for p in prs], axis=0)
        free = [i for i in range(n) if i not in prs]
        # boundary valves: junctions near the edge, far from the PRSs, degree 2 or more
        tdeg = np.zeros(n, int)
        for a, b in self.tree:
            tdeg[a] += 1
            tdeg[b] += 1
        cand = [i for i in free if tdeg[i] >= 2 and rad[i] > 0.7 * rad.max() and dprs[i] > 2.5]
        rng.shuffle(cand)
        valves = []
        for i in cand:
            if all(np.hypot(*(pts[i] - pts[j])) > 2.0 for j in valves):
                valves.append(i)
            if len(valves) == s["nval"]:
                break
        free = [i for i in free if i not in valves]
        cand = [i for i in free if deg[i] >= 3 and dprs[i] > 2.0]
        rng.shuffle(cand)
        cust = []
        for i in cand:
            if all(np.hypot(*(pts[i] - pts[j])) > 2.0 for j in cust):
                cust.append(i)
            if len(cust) == s["ncust"]:
                break
        free = [i for i in free if i not in cust]
        leaves = [i for i in free if deg[i] == 1]                  # a dead end always serves a governor
        free = [i for i in free if deg[i] > 1]
        rng.shuffle(free)
        gov = sorted(leaves + free[: max(0, int(0.48 * (len(free) + len(leaves))) - len(leaves))])
        self.prs, self.valves, self.cust, self.gov = prs, valves, cust, gov
        self.deg = deg

    def demands(self):
        s, rng = self.s, self.rng
        n = self.n
        self.gpeak = np.zeros(n)
        self.gpeak[self.gov] = np.maximum(rng.lognormal(np.log(420), 0.55, len(self.gov)), 150.0)
        self.gshape = {}
        for g in self.gov:
            base = DOMESTIC if rng.random() < 0.75 else COMMERCIAL
            self.gshape[g] = np.clip(base * (1 + rng.normal(0, 0.03, 24)), 0.05, None)
        # customers' true flows, hourly over the record (and on the first campaign's day)
        self.cust_hi = rng.uniform(1600, 3400, len(self.cust))
        self.cust_series = []
        for k, c in enumerate(self.cust):
            hi = self.cust_hi[k]
            lo = hi * rng.uniform(0.45, 0.75)
            cont = rng.random() < 0.3
            wk_end = 0.0 if s.get("weekend_off") and k % 2 == 0 else rng.uniform(0.35, 0.8)
            series = np.zeros(REC_DAYS * 24)
            for d in range(REC_DAYS):
                day = REC0 + dtm.timedelta(days=d)
                f = 1 + rng.normal(0, 0.04)
                for hh in range(24):
                    if cont:
                        v = hi
                    else:
                        v = hi if 6 <= hh < 22 else lo
                    if day.weekday() >= 5:
                        v = hi * wk_end if not cont else hi * 0.9
                    series[d * 24 + hh] = max(0.0, v * f * (1 + rng.normal(0, 0.015)))
            self.cust_series.append(series)
        self.cust_c1 = self.cust_hi * rng.uniform(0.9, 1.05, len(self.cust))

    def size(self):
        """Diameters from the peak flows routed on shortest paths from the nearest PRS."""
        n, E, L = self.n, self.E, self.L
        G = sp.coo_matrix((L, (E[:, 0], E[:, 1])), shape=(n, n)).tocsr()
        dist, pred = shortest_path(G, directed=False, indices=self.prs, return_predecessors=True)
        near = np.argmin(dist, axis=0)
        eidx = {(int(a), int(b)): k for k, (a, b) in enumerate(E)}
        load = self.gpeak.copy()
        load[self.cust] += self.cust_hi
        Qe = np.zeros(len(E))
        for i in range(n):
            k, j = near[i], i
            while j != self.prs[k]:
                pj = pred[k, j]
                Qe[eidx[tuple(sorted((int(j), int(pj))))]] += load[i]
                j = pj
        D = np.zeros(len(E))
        for k in range(len(E)):
            need = (KR * max(Qe[k], 250.0) ** 1.82 / 0.45) ** (1 / 4.82)
            D[k] = SIZES[min(np.searchsorted(SIZES, need), len(SIZES) - 1)]
        self.D = np.maximum(D, 125.0)
        rng = self.rng
        mat = rng.choice(["CI", "ST", "DI"], size=len(E), p=[0.45, 0.35, 0.20])
        c = np.where(mat == "CI", rng.uniform(1.15, 1.6, len(E)),
                     np.where(mat == "ST", rng.uniform(0.95, 1.2, len(E)), rng.uniform(1.0, 1.3, len(E))))
        self.mat, self.c = list(mat), c

    def prune(self):
        """Loops that carry next to nothing at a campaign's demand are left out of the network as laid."""
        for _ in range(4):
            K = self.c * KR * (self.L / 1000) / self.D ** 4.82
            V = np.pi / 4 * (self.D / 1000) ** 2 * self.L
            mains = [(int(a), int(b), K[k], V[k]) for k, (a, b) in enumerate(self.E)]
            net = Net(range(self.n), mains, [(p, st + P_ATM, 1e9) for p, st in zip(self.prs, self.s["sets"])])
            d = np.zeros(self.n)
            for g in self.gov:
                d[g] = self.gpeak[g] * self.gshape[g][13] * 0.8
            d[self.cust] += self.cust_hi
            p, _ = net.steady(d)
            Q = net.flows(p)
            dpa = np.abs(p[self.E[:, 0]] - p[self.E[:, 1]])
            weak = [k for k in range(len(self.E)) if tuple(int(x) for x in self.E[k]) not in self.tree
                    and (abs(Q[k]) < 300 or dpa[k] < 4e-4)]
            if not weak:
                return
            keep = np.array([k not in set(weak) for k in range(len(self.E))])
            self.E, self.L, self.D, self.c = self.E[keep], self.L[keep], self.D[keep], self.c[keep]
            self.mat = [m for m, kp in zip(self.mat, keep) if kp]
            deg = np.bincount(self.E.ravel(), minlength=self.n)
            special = set(self.prs) | set(self.valves) | set(self.cust) | set(self.gov)
            for i in range(self.n):
                if deg[i] == 1 and i not in special:          # a dead end left by the pruning gets a governor
                    self.gov.append(i)
                    self.gpeak[i] = max(self.rng.lognormal(np.log(420), 0.55), 150.0)
                    self.gshape[i] = np.clip(DOMESTIC * (1 + self.rng.normal(0, 0.03, 24)), 0.05, None)
            self.gov.sort()

    # ------------------------------------------------------------------ history
    def history(self):
        """Works on the mains: (date, main index, work, new D, new c, new material). Mains laid after the third
        campaign are appended to the network."""
        s, rng = self.s, self.rng
        m = len(self.E)
        self.K0 = self.c * KR * (self.L / 1000) / self.D ** 4.82
        self.events = []
        busy = set()

        def pick(cands):
            cands = [k for k in cands if k not in busy]
            k = int(rng.choice(cands))
            busy.add(k)
            return k

        big = [k for k in range(m) if self.D[k] >= 180]
        windows = [("2024-03-01", "2025-10-31"), ("2025-12-15", "2026-01-28"), ("2026-03-02", "2026-10-30")]

        def rdate(w):
            a = dtm.date.fromisoformat(w[0])
            b = dtm.date.fromisoformat(w[1])
            return a + dtm.timedelta(days=int(rng.integers(0, (b - a).days + 1)))

        def lined(k):
            dn = round(self.D[k] * rng.uniform(0.82, 0.88))
            return dn, rng.uniform(0.86, 0.92), "PE-lined " + self.mat[k]

        def renewed(k):
            j = int(np.searchsorted(SIZES, self.D[k])) + int(rng.integers(1, 3))
            return float(SIZES[min(j, len(SIZES) - 1)]), rng.uniform(0.86, 0.92), "PE"

        # before the second campaign and between the second and third: surveyed since
        for w, nn in ((windows[0], 3), (windows[1], 1)):
            for _ in range(nn):
                k = pick(big)
                if rng.random() < 0.5:
                    dn, cn, mt = lined(k)
                    self.events.append((rdate(w), k, "RELINED", dn, cn, mt))
                else:
                    dn, cn, mt = renewed(k)
                    self.events.append((rdate(w), k, "RENEWED", dn, cn, mt))
        rel, ren, lay = s["works"]
        self.after = []
        trunk = sorted(big, key=lambda k: -self.D[k])[: max(12, len(big) // 3)]
        for _ in range(rel):
            k = pick(trunk if rng.random() < 0.6 else big)
            dn, cn, mt = lined(k)
            self.events.append((rdate(windows[2]), k, "RELINED", dn, cn, mt))
            self.after.append(k)
        for _ in range(ren):
            k = pick(trunk if rng.random() < 0.7 else big)
            dn, cn, mt = renewed(k)
            self.events.append((rdate(windows[2]), k, "RENEWED", dn, cn, mt))
            self.after.append(k)
        # mains laid after the third campaign: new links between existing nodes
        spare = [e for e in self.spare if e[0] not in self.valves and e[1] not in self.valves]
        rng.shuffle(spare)
        newE, newL = [], []
        for e in spare[:lay]:
            newE.append(e)
            newL.append(np.hypot(*(self.pts[e[0]] - self.pts[e[1]])) * 1.15 * 1000.0)
        for j, e in enumerate(newE):
            k = m + j
            self.events.append((rdate(windows[2]), k, "LAID", float(rng.choice([200, 250, 300])),
                                rng.uniform(0.86, 0.92), "PE"))
            self.after.append(k)
        if newE:
            self.E = np.vstack([self.E, np.array(newE)])
            self.L = np.concatenate([self.L, np.array(newL)])
            self.D = np.concatenate([self.D, np.zeros(len(newE))])
            self.c = np.concatenate([self.c, np.zeros(len(newE))])
            self.mat += [""] * len(newE)
            self.K0 = np.concatenate([self.K0, np.full(len(newE), np.nan)])
        # distractors: inspections and repairs, which change nothing
        for _ in range(int(rng.integers(4, 9))):
            k = int(rng.integers(0, m))
            w = windows[int(rng.integers(0, 3))]
            self.events.append((rdate(w), k, str(rng.choice(["INSPECTED", "REPAIRED"])), None, None, None))
        self.events.sort(key=lambda e: (e[0], e[1]))

    def state_at(self, date):
        """K, D and presence of every main on a date."""
        K = self.K0.copy()
        D = self.D.copy()
        mat = list(self.mat)
        present = ~np.isnan(K)
        for (d, k, work, dn, cn, mt) in self.events:
            if d > date or work in ("INSPECTED", "REPAIRED"):
                continue
            D[k] = dn
            K[k] = cn * KR * (self.L[k] / 1000) / dn ** 4.82
            mat[k] = mt
            present[k] = True
        return K, D, mat, present

    # ------------------------------------------------------------------ states
    def net(self, date, valve_on, scale_caps=None):
        K, D, _mat, present = self.state_at(date)
        V = np.pi / 4 * (D / 1000) ** 2 * self.L
        mains = [(int(self.E[k, 0]), int(self.E[k, 1]), K[k], V[k]) for k in range(len(self.E)) if present[k]]
        caps = self.caps if scale_caps is None else scale_caps
        prs = [(p, st + P_ATM, cp) for p, st, cp in zip(self.prs, self.sets, caps)]
        valves = []
        if valve_on and self.vpass is not None:
            valves = [(self.valves[self.vpass], self.vnb + P_ATM, self.vK)]
        return Net(range(self.n), mains, prs, valves), present

    def demand_hour(self, clock_h, gfac, cust_flow):
        d = np.zeros(self.n)
        for g in self.gov:
            d[g] = self.gpeak[g] * self.gshape[g][clock_h] * gfac
        d[self.cust] += cust_flow
        return d

    def design_demand_true(self):
        """(24, n) from 06:00: governors' design day, customers' weekday hourly means of their true flow."""
        out = np.zeros((24, self.n))
        wk = [d for d in range(REC_DAYS) if (REC0 + dtm.timedelta(days=d)).weekday() < 5]
        for k, h in enumerate(GAS_DAY):
            for g in self.gov:
                out[k, g] = self.design[g][h]
            for j, c in enumerate(self.cust):
                out[k, c] += np.mean([self.cust_series[j][d * 24 + h] for d in wk])
        return out

    def build(self):
        s, rng = self.s, self.rng
        self.layout()
        self.roles()
        self.demands()
        self.size()
        self.sets = list(s["sets"])
        self.vpass, self.vnb, self.vK = None, None, None
        self.prune()
        self.history()
        # design-day demand of the governors, then the scale and the PRS capacities
        self.design = {g: self.gpeak[g] * self.gshape[g] for g in self.gov}
        now = dtm.date(2026, 11, 2)
        lo, hi = 0.3, 4.0
        for _ in range(9):
            mid = (lo + hi) / 2
            pmin = self.trial(mid, now)
            if pmin is None or pmin < s["target"]:
                hi = mid
            else:
                lo = mid
        self.scale = lo
        for g in self.gov:
            self.gpeak[g] *= lo
            self.design[g] = self.gpeak[g] * self.gshape[g]
        self.trial(1.0, now, keep=True)

    def trial(self, scale, date, keep=False):
        save = self.gpeak.copy()
        self.gpeak = self.gpeak * scale
        self.design = {g: self.gpeak[g] * self.gshape[g] for g in self.gov}
        dd = self.design_demand_true()
        tot = dd.sum(axis=1)
        self.caps = [1e9] * len(self.prs)
        net, _ = self.net(date, False)
        try:
            p, deliv = net.steady(dd[np.argmax(tot)])
        except RuntimeError:
            self.gpeak = save
            return None
        share = np.maximum(deliv, 0) / max(deliv.sum(), 1)
        share = np.maximum(share, 0.15)
        share /= share.sum()
        self.caps = list(self.s["cap"] * tot.max() * share * self.rng.uniform(0.97, 1.03, len(share)))
        if sum(self.caps) * 24 < 1.12 * tot.sum():
            self.gpeak = save
            return None
        net, _ = self.net(date, False)
        try:
            P, _D, _days = net.design_day(dd)
        except RuntimeError:
            self.gpeak = save
            return None
        pmin = (P[:, self.gov] - P_ATM).min()
        if not keep:
            self.gpeak = save
        return pmin


# ---------------------------------------------------------------------- conditions, campaigns, the crew
def tn(rng, acc, size=None):
    """A reading error within +-acc (truncated normal, sigma acc/2.5)."""
    return np.clip(rng.normal(0, acc / 2.5, size), -acc, acc)


def conditions(cs):
    s, rng = cs.s, cs.rng
    cs.flip = rng.random(len(cs.E)) < 0.5                      # direction each main is registered in
    cs.cfac = rng.uniform(0.95, 1.05, 3)
    cs.gj = [dict((g, rng.uniform(0.94, 1.06)) for g in cs.gov) for _ in range(4)]
    cs.nb_closed = rng.uniform(4.2, 6.3, len(cs.valves))
    cs.good_ratio = rng.uniform(0.996, 1.004, len(cs.cust))
    cs.mfault, cs.mratio = None, 1.0
    if s["meter"]:
        cs.mfault, cs.mratio = int(rng.integers(0, len(cs.cust))), s["meter"]["ratio"]
    cs.vpass = None
    if s["valve"]:
        date = dtm.date.fromisoformat(CAMPAIGNS[2])
        net, _ = cs.net(date, False)
        p, _ = net.steady(campaign_demand(cs, 2))
        cs.vpass = int(rng.integers(0, len(cs.valves)))
        pnode = p[cs.valves[cs.vpass]] - P_ATM
        cs.vnb = float(round(pnode + s["valve"]["nb"], 2))
        kq = s["valve"]["kq"]
        cs.vK = abs((cs.vnb + P_ATM) ** 2 - (pnode + P_ATM) ** 2) / kq ** 1.82
        cs.vsince = 1 if rng.random() < 0.6 else 0              # passing from the second campaign, or all


def ratio_of(cs, j):
    return cs.mratio if j == cs.mfault else cs.good_ratio[j]


def cust_flow(cs, date, hour=13):
    d = (date - REC0).days
    if 0 <= d < REC_DAYS:
        return np.array([cs.cust_series[j][d * 24 + hour] for j in range(len(cs.cust))])
    return cs.cust_c1.copy()


def campaign_demand(cs, ci):
    gfac = [0.78, 0.82, 0.86, 0.72][ci] * (cs.cfac[ci] if ci < 3 else 1.0)
    d = np.zeros(cs.n)
    for g in cs.gov:
        d[g] = cs.design[g][13] * gfac * cs.gj[ci][g]
    if ci < 3:
        d[cs.cust] += cust_flow(cs, dtm.date.fromisoformat(CAMPAIGNS[ci]))
    else:
        d[cs.cust] += cs.cust_hi
    return d


def state(cs, ci):
    """The steady state of a campaign (ci 0..2) or of the crew's visit (ci 3): pressures and the readings."""
    date = dtm.date.fromisoformat(CAMPAIGNS[ci]) if ci < 3 else dtm.date(2026, 11, 4)
    on = cs.vpass is not None and (ci >= cs.vsince if ci < 3 else True)
    net, present = cs.net(date, on)
    p, deliv = net.steady(campaign_demand(cs, ci))
    Q = net.flows(p)
    idx = np.flatnonzero(present)
    rng = cs.rng
    reads = {}
    for j, k in enumerate(idx):
        a, b = int(cs.E[k, 0]), int(cs.E[k, 1])
        q = Q[j]
        if cs.flip[k]:
            a, b, q = b, a, -q
        pf = p[a] - P_ATM + tn(rng, 0.001)
        dp = (p[a] - p[b]) * (1 + tn(rng, 0.005))
        qr = q * (1 + tn(rng, 0.01))
        reads[int(k)] = (round(pf, 4), float("%.6g" % dp), float("%.6g" % qr))
    vflow = net.valve_flows(p)
    return p, reads, (float(vflow[0]) if len(vflow) else 0.0), deliv


def build_case(name):
    spec = dict(CASES[name], name=name)
    for attempt in range(spec.get("attempt", 0), 6):
        cs = Case(name, dict(spec, seed=spec["seed"] + 100 * attempt))
        cs.build()
        conditions(cs)
        cs.states = [state(cs, ci) for ci in range(4)]
        weak = [(ci, k, q, dp) for ci, st in enumerate(cs.states) for k, (pf, dp, q) in st[1].items()
                if abs(q) < 0.05 or abs(dp) < 1e-10]
        if not weak:
            return cs
        print("  %s attempt %d: %d weak readings, e.g. %s" % (name, attempt, len(weak), weak[:3]), flush=True)
    raise RuntimeError("no network without weak readings")


# ---------------------------------------------------------------------- writing a package
NB_NAMES = ["Ashwell IP", "Bramley IP", "Coldharbour IP", "Dalton IP", "Eastgate IP", "Fernhill IP"]


def write_case(cs, root):
    where = cs.s["where"]
    pkg = os.path.join(root, "core", "data", where, cs.name) if where != "hidden" else \
        os.path.join(root, "core", "hidden", cs.name)
    shutil.rmtree(pkg, ignore_errors=True)
    os.makedirs(pkg)
    rng = np.random.default_rng(cs.s["seed"] + 1000)
    node = lambda i: "N%03d" % (i + 1)                                       # noqa: E731
    main = lambda k: "M%03d" % (k + 1)                                       # noqa: E731
    K, D, mat, present = cs.state_at(dtm.date(2026, 11, 2))
    ends = []
    with open(os.path.join(pkg, "mains.csv"), "w") as f:
        f.write("main,from_node,to_node,length_m,diameter_mm,material\n")
        for k in range(len(cs.E)):
            a, b = int(cs.E[k, 0]), int(cs.E[k, 1])
            if cs.flip[k]:
                a, b = b, a
            ends.append((a, b))
            f.write("%s,%s,%s,%.0f,%.0f,%s\n" % (main(k), node(a), node(b), cs.L[k], D[k], mat[k]))
    with open(os.path.join(pkg, "surveys.csv"), "w") as f:
        f.write("date,main,p_from_barg,dp_bar,q_m3h\n")
        for ci in range(3):
            reads = cs.states[ci][1]
            for k in sorted(reads):
                pf, dp, q = reads[k]
                f.write("%s,%s,%.4f,%.6g,%.6g\n" % (CAMPAIGNS[ci], main(k), pf, dp, q))
    with open(os.path.join(pkg, "work_log.csv"), "w") as f:
        f.write("date,main,work\n")
        for (d, k, work, _dn, _cn, _mt) in cs.events:
            f.write("%s,%s,%s\n" % (d2s(d), main(k), work))
    with open(os.path.join(pkg, "prs.csv"), "w") as f:
        f.write("prs,node,set_point_barg,capacity_m3h\n")
        for j, (p, st, cp) in enumerate(zip(cs.prs, cs.sets, cs.caps)):
            f.write("PRS-%s,%s,%.2f,%.0f\n" % ("ABC"[j], node(p), st, cp))
    gname = {g: "G%02d" % (j + 1) for j, g in enumerate(cs.gov)}
    with open(os.path.join(pkg, "governors.csv"), "w") as f:
        f.write("governor,node\n")
        for g in cs.gov:
            f.write("%s,%s\n" % (gname[g], node(g)))
    with open(os.path.join(pkg, "design_day.csv"), "w") as f:
        f.write("governor,hour,demand_m3h\n")
        for g in cs.gov:
            for h in GAS_DAY:
                f.write("%s,%d,%.1f\n" % (gname[g], h, cs.design[g][h]))
    mnames = ["MT-%04d" % int(x) for x in rng.choice(np.arange(1000, 9999), len(cs.cust), replace=False)]
    cs.mnames = mnames
    with open(os.path.join(pkg, "customers.csv"), "w") as f:
        f.write("customer,node,meter\n")
        for j, c in enumerate(cs.cust):
            f.write("CU-%d,%s,%s\n" % (j + 1, node(c), mnames[j]))
    with open(os.path.join(pkg, "customer_meters.csv"), "w") as f:
        f.write("time,meter,q_m3h\n")
        for d in range(REC_DAYS):
            day = REC0 + dtm.timedelta(days=d)
            for h in range(24):
                for j in range(len(cs.cust)):
                    f.write("%s %02d:00,%s,%.1f\n" % (d2s(day), h, mnames[j],
                                                       cs.cust_series[j][d * 24 + h] * ratio_of(cs, j)))
    vnames = ["BV-%d" % (j + 1) for j in range(len(cs.valves))]
    nb = list(NB_NAMES)
    rng.shuffle(nb)
    nbp = list(cs.nb_closed)
    if cs.vpass is not None:
        nbp[cs.vpass] = cs.vnb
    with open(os.path.join(pkg, "boundary_valves.csv"), "w") as f:
        f.write("valve,node,neighbour,neighbour_pressure_barg,state\n")
        for j, v in enumerate(cs.valves):
            f.write("%s,%s,%s,%.2f,closed\n" % (vnames[j], node(v), nb[j], nbp[j]))
    allowance = len(cs.after) + (cs.vpass is not None) + (cs.mfault is not None)
    with open(os.path.join(pkg, "network.json"), "w") as f:
        json.dump({"network": cs.name, "survey_allowance": int(allowance)}, f, indent=1)
        f.write("\n")
    # the crew's book: every main, valve and meter as the network stands now
    p_now, reads_now, vq_now, _ = cs.states[3]
    book = {"allowance": int(allowance), "mains": {}, "valves": {}, "meters": {}}
    for k, (pf, dp, q) in reads_now.items():
        book["mains"][main(k)] = [pf, dp, q]
    for j, v in enumerate(cs.valves):
        q = vq_now if j == cs.vpass else 0.0
        book["valves"][vnames[j]] = [round(p_now[v] - P_ATM + tn(cs.rng, 0.001), 4), round(nbp[j], 4),
                                     round(q * (1 + tn(cs.rng, 0.01)), 1)]
    for j in range(len(cs.cust)):
        book["meters"][mnames[j]] = round(100 * ratio_of(cs, j) + tn(cs.rng, 0.1), 1)
    cs.book = book
    cs.vnames = vnames
    return pkg


def orders_of(cs):
    """What the field team has to be asked for: the mains worked on since the third campaign, the passing
    valve, the meter outside its accuracy."""
    items = ["M%03d" % (k + 1) for k in cs.after]
    if cs.vpass is not None:
        items.append(cs.vnames[cs.vpass])
    if cs.mfault is not None:
        items.append(cs.mnames[cs.mfault])
    return items


def read_of(book, items):
    out = {}
    for it in items:
        for kind, key in (("main", "mains"), ("valve", "valves"), ("meter", "meters")):
            if it in book[key]:
                v = book[key][it]
                out[it] = (kind, list(v) if isinstance(v, list) else [v])
    return out


def main(argv):
    import ref_design as R
    names = argv[1:] or list(CASES)
    mpath = os.path.join(HERE, "core", "manifest.json")
    os.makedirs(os.path.join(HERE, "crew", "books"), exist_ok=True)
    for name in names:
        cs = build_case(name)
        pkg = write_case(cs, HERE)
        items = orders_of(cs)
        pk = R.Package(pkg)
        res = R.solve(pk, read_of(cs.book, items))
        where = cs.s["where"]
        if where == "examples":
            out = os.path.join(pkg, "expected.csv")
        elif where == "hidden":
            out = os.path.join(pkg, "truth.csv")
        else:
            out = os.path.join(HERE, "core", "pending_truth_%s.csv" % name)
        with open(out, "w") as f:
            f.write("governor,min_pressure_barg\n")
            for g, v in res:
                f.write("%s,%.4f\n" % (g, v))
        if where != "pending":
            with open(os.path.join(HERE, "crew", "books", name + ".json"), "w") as f:
                json.dump(cs.book, f)
        entry = dict(where=where, nodes=cs.n, mains=len(cs.E), governors=len(cs.gov),
                              allowance=cs.book["allowance"], worked_on=["M%03d" % (k + 1) for k in cs.after],
                              passing_valve=(cs.vnames[cs.vpass] if cs.vpass is not None else None),
                              valve_since_campaign=(int(cs.vsince) + 1 if cs.vpass is not None else None),
                              valve_flow_now=(round(cs.states[3][2], 1) if cs.vpass is not None else None),
                              low_meter=(cs.mnames[cs.mfault] if cs.mfault is not None else None),
                              meter_ratio=(cs.mratio if cs.mfault is not None else None),
                              caps=[round(c) for c in cs.caps], sets=cs.sets,
                              pmin=round(min(v for _g, v in res), 3))
        print(name, json.dumps(entry), flush=True)
        import fcntl
        with open(mpath + ".lock", "w") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
            manifest[name] = entry
            with open(mpath, "w") as f:
                json.dump(manifest, f, indent=1)


if __name__ == "__main__":
    main(sys.argv)
