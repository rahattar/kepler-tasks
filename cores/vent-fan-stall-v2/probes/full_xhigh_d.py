#!/usr/bin/env python3
"""Airflow at the survey points of a ventilation district package, to VS-4.

    python3 airflow.py PACKAGE_DIR OUT_CSV

Resistances (VS-4 section 3)
  airways     the surveys made since the airway was last re-supported or
              enlarged (the mean of those that agree within the reading
              errors); where there is none, the survey crew's reading now
  stoppings   the register, unless the campaigns show the stopping leaking
              far more than it was built to: the flow through it follows from
              the balance of the surveyed airways at its ends, the pressure
              across it from their pressure drops; then the campaigns' value,
              or the crew's reading where the order has room
  regulators, doors, fan ducting: the tables and the register

The network (VS-4 section 2)
  Without the fans the district is a passive square-law network between the
  surface and the fan house: it acts as one equivalent resistance Re
  (dp = Re Q^2) and every branch flow is proportional to the total flow Q.
  The main fans in parallel then satisfy
      P_i(q_i) - Rd_i q_i^2 = Re (sum q)^2           for every fan i,
  with P_i the catalogue table of the fan, straight between its points.

The fans through the record (VS-4 sections 4 and 5)
  The characteristics have a stall dip, so one Re can have several steady
  states; the stable ones are the minima of the district's content.  The
  settings change slowly, so the state follows its stable branch through every
  change of the log (Re moves monotonically between its values before and
  after a change); where the branch ends the air settles, under the inertia
  of the district and of the fans, in another stable state.

The survey order
  airways that need a survey, then stoppings found leaking, then the fans: a
  reading of the fans tells the state the record ends in, and where it
  contradicts the state followed, the change that put the district in another
  steady state is looked for.
"""
import bisect
import csv
import itertools
import json
import math
import os
import subprocess
import sys

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.sparse.csgraph import reverse_cuthill_mckee, connected_components

WORK_KINDS = ('RESUPPORTED', 'ENLARGED')


# ----------------------------------------------------------------------------
# reading the package
# ----------------------------------------------------------------------------
def read_csv(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, newline='', encoding='utf-8-sig') as f:
        rd = csv.reader(f)
        header = None
        for r in rd:
            if not r or all(not c.strip() for c in r):
                continue
            if header is None:
                header = [c.strip() for c in r]
                continue
            r = [c.strip() for c in r]
            if len(r) < len(header):
                r = r + [''] * (len(header) - len(r))
            rows.append(dict(zip(header, r)))
    return rows


def fnum(s, default=None):
    try:
        v = float(s)
        if math.isnan(v) or math.isinf(v):
            return default
        return v
    except Exception:
        return default


def norm_time(s):
    s = (s or '').strip().replace('T', ' ')
    parts = s.split(' ')
    if len(parts) >= 2:
        d, t = parts[0], parts[1]
        hm = t.split(':')
        if len(hm) >= 2:
            t = '%02d:%02d' % (int(hm[0]), int(hm[1]))
        return d + ' ' + t
    return s


def norm_date(s):
    s = (s or '').strip()
    return s[:10]


class Package:
    def __init__(self, d):
        self.dir = d
        try:
            with open(os.path.join(d, 'district.json')) as f:
                self.district = json.load(f)
        except Exception:
            self.district = {}
        self.branches = read_csv(os.path.join(d, 'branches.csv'))
        self.surveys = read_csv(os.path.join(d, 'surveys.csv'))
        self.work = read_csv(os.path.join(d, 'work_log.csv'))
        self.regs = read_csv(os.path.join(d, 'regulators.csv'))
        self.doors = read_csv(os.path.join(d, 'doors.csv'))
        self.fans = read_csv(os.path.join(d, 'fans.csv'))
        self.curves = read_csv(os.path.join(d, 'fan_curves.csv'))
        self.log = read_csv(os.path.join(d, 'log.csv'))
        self.points = read_csv(os.path.join(d, 'points.csv'))


# ----------------------------------------------------------------------------
# airway resistances (VS-4 section 3)
# ----------------------------------------------------------------------------
def survey_R(dp, q):
    if dp is None or q is None or q == 0.0:
        return None
    R = abs(dp) / (q * q)
    if not (R > 0) or math.isinf(R):
        return None
    return R


def airway_status(pkg, airways):
    """For every airway: dict(samples, need, fallback, weight).

    samples: resistances from the surveys that describe the airway as it is now
    (made since its last re-support or enlargement); need: no such survey."""
    surv = {}
    for i, r in enumerate(pkg.surveys):
        b = r.get('branch', '')
        if b not in airways:
            continue
        q = fnum(r.get('q_m3_s'))
        R = survey_R(fnum(r.get('dp_Pa')), q)
        if R is None:
            continue
        surv.setdefault(b, []).append((norm_date(r.get('date', '')), i, R, abs(q)))
    jobs = {}
    for r in pkg.work:
        b = r.get('branch', '')
        w = (r.get('work', '') or '').strip().upper()
        if b in airways and w in WORK_KINDS:
            jobs.setdefault(b, []).append((norm_date(r.get('date', '')), w))
    for b in surv:
        surv[b].sort()

    # resistance change brought by a job, learned from the package's own record
    ratios = {}
    for b, js in jobs.items():
        S = surv.get(b, [])
        for (jd, w) in js:
            before = [s for s in S if s[0] < jd]
            after = [s for s in S if s[0] > jd]
            if before and after:
                ratios.setdefault(w, []).append(after[0][2] / before[-1][2])
    allr = [x for v in ratios.values() for x in v]
    med_all = float(np.median(allr)) if allr else 0.2
    med = {w: float(np.median(v)) for w, v in ratios.items()}

    out = {}
    for b in airways:
        S = surv.get(b, [])
        js = sorted(jobs.get(b, []))
        last_job = js[-1] if js else None
        if not S:
            out[b] = dict(samples=[], need=True, fallback=None, weight=0.0)
            continue
        d, _, R, q = S[-1]
        if last_job is None or last_job[0] < d:
            valid = [s for s in S if last_job is None or s[0] > last_job[0]]
        else:
            valid = []
            if last_job[0] == d:
                # job on the day of the latest survey: that survey describes the
                # airway as it is now only if it shows the change the work made
                prev = [s for s in S if s[0] < d]
                if prev and abs(R / prev[-1][2] - 1.0) > 0.05:
                    valid = [s for s in S if s[0] == d]
        if valid:
            out[b] = dict(samples=consistent([s[2] for s in valid]), need=False, fallback=None, weight=q)
        else:
            out[b] = dict(samples=[], need=True, fallback=R * med.get(last_job[1], med_all), weight=q)
    return out


def consistent(Rs):
    """the latest surveys that agree with one another within what the reading
    errors allow (an airway that has changed keeps only its latest state)"""
    sel = [Rs[-1]]
    for R in reversed(Rs[:-1]):
        lo, hi = min(sel + [R]), max(sel + [R])
        if hi / lo - 1.0 > 0.025:
            break
        sel.append(R)
    return sel


def mean_R(samples):
    return float(math.exp(sum(math.log(r) for r in samples) / len(samples)))


def campaigns(pkg):
    """the surveys on file grouped into campaigns: runs of days less than a
    week apart; within one the regulators and doors stood as they were"""
    rows = []
    for r in pkg.surveys:
        dp, q = fnum(r.get('dp_Pa')), fnum(r.get('q_m3_s'))
        d = norm_date(r.get('date', ''))
        if dp is None or q is None or not d:
            continue
        rows.append((d, (r.get('branch', '') or '').strip(), dp, q))
    rows.sort(key=lambda x: x[0])
    out = []
    last = None
    for d, b, dp, q in rows:
        try:
            day = (int(d[:4]) * 372 + int(d[5:7]) * 31 + int(d[8:10]))
        except Exception:
            day = None
        if not out or last is None or day is None or day - last > 7:
            out.append({})
        out[-1][b] = (dp, q)
        last = day
    return out


def stopping_check(pkg, names, kind, fnode, tnode):
    """Stoppings are not surveyed, but in a campaign the flow through one
    follows from the balance of the surveyed airways at its ends and the
    pressure across it from their pressure drops.  Returns, for the stoppings
    whose leakage contradicts the resistance they were built to, the resistance
    the campaigns show: {branch index: (R, leak)}."""
    nb = len(names)
    inc = {}
    for k in range(nb):
        inc.setdefault(fnode[k], []).append((k, 1.0))
        inc.setdefault(tnode[k], []).append((k, -1.0))
    bidx = {n: k for k, n in enumerate(names)}
    stops = [k for k in range(nb) if kind[k] == 'stopping']
    est = {k: [] for k in stops}
    for c, camp in enumerate(campaigns(pkg)):
        meas = {}
        for b, (dp, q) in camp.items():
            k = bidx.get(b)
            if k is not None and kind[k] == 'airway':
                meas[k] = (dp, q)
        # pressures from the surveyed airways, node by node
        pot, comp = {}, {}
        adj = {}
        for k, (dp, q) in meas.items():
            adj.setdefault(fnode[k], []).append((tnode[k], -dp, dp * dp))
            adj.setdefault(tnode[k], []).append((fnode[k], dp, dp * dp))
        var = {}
        cid = 0
        for n0 in adj:
            if n0 in pot:
                continue
            cid += 1
            pot[n0], comp[n0], var[n0] = 0.0, cid, 0.0
            stack = [n0]
            while stack:
                n = stack.pop()
                for m, d, d2 in adj[n]:
                    if m not in pot:
                        pot[m] = pot[n] + d
                        var[m] = var[n] + d2
                        comp[m] = cid
                        stack.append(m)
        for k in stops:
            a, b = fnode[k], tnode[k]
            if a not in pot or b not in pot or comp[a] != comp[b]:
                continue
            dp = pot[a] - pot[b]
            qs, vs = [], []
            for n, sk in ((a, 1.0), (b, -1.0)):
                others = [(j, sg) for (j, sg) in inc[n] if j != k]
                if others and all(j in meas for j, _ in others):
                    qs.append(-sum(sg * meas[j][1] for j, sg in others) / sk)
                    vs.append(sum((0.003 * meas[j][1]) ** 2 / 3.0 for j, _ in others))
            if not qs:
                continue
            qk = sum(qs) / len(qs)
            vq = sum(vs) / len(vs) ** 2
            est[k].append((c, dp, qk, vq))
    found = {}
    for k in stops:
        if not est[k]:
            continue
        Rreg = fnum(pkg.branches[k].get('resistance_Ns2_m8'), None)
        if not Rreg or Rreg <= 0:
            continue
        c, dp, qk, vq = est[k][-1]
        qp = math.copysign(math.sqrt(abs(dp) / Rreg), dp)
        dev = abs(qk - qp)
        sig = math.sqrt(vq + (0.02 * qp) ** 2)
        if dev <= max(6.0 * sig, 0.15) or qk * dp <= 0:
            continue
        Rs = [abs(e[1]) / (e[2] * e[2]) for e in est[k] if e[2] * e[1] > 0]
        Rl = abs(dp) / (qk * qk)
        if abs(math.log(Rl / Rreg)) < math.log(1.3):
            continue
        sel = [r for r in Rs if abs(math.log(r / Rl)) < 0.15]
        found[k] = (mean_R(sel or [Rl]), abs(qk))
    return found


def order_surveys(pkgdir, branches):
    """One survey order with the crew.  Returns {branch: (dp, q)}."""
    res = {}
    if not branches:
        return res
    try:
        p = subprocess.run(['pqsurvey', pkgdir] + list(branches), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True, timeout=20)
        txt = p.stdout
    except Exception:
        return res
    for line in txt.splitlines():
        parts = [c.strip() for c in line.split(',')]
        if len(parts) < 3:
            continue
        dp, q = fnum(parts[1]), fnum(parts[2])
        if dp is None or q is None:
            continue
        res[parts[0]] = (dp, q)
    return res


# ----------------------------------------------------------------------------
# passive network: unit flow from the surface to the fan house
# ----------------------------------------------------------------------------
class Passive:
    def __init__(self, fnodes, tnodes, src, snk):
        nodes = sorted(set(fnodes) | set(tnodes) | {src, snk})
        idx = {n: i for i, n in enumerate(nodes)}
        nb = len(fnodes)
        fi = np.array([idx[n] for n in fnodes], dtype=np.int64)
        ti = np.array([idx[n] for n in tnodes], dtype=np.int64)
        nn = len(nodes)
        # keep only the component joining the terminals
        G = sp.coo_matrix((np.ones(nb), (fi, ti)), shape=(nn, nn))
        ncomp, lab = connected_components(G, directed=False)
        live_node = lab == lab[idx[src]]
        self.connected = bool(live_node[idx[snk]])
        live_br = live_node[fi] & live_node[ti] & (fi != ti)
        self.live_br = live_br
        lb = np.nonzero(live_br)[0]
        # renumber nodes of live component, ground = src
        ln = np.nonzero(live_node)[0]
        newid = -np.ones(nn, dtype=np.int64)
        newid[ln] = np.arange(len(ln))
        self.nb = nb
        self.lb = lb
        f2 = newid[fi[lb]]
        t2 = newid[ti[lb]]
        n2 = len(ln)
        self.n2 = n2
        self.src = newid[idx[src]]
        self.snk = newid[idx[snk]]
        self.f2, self.t2 = f2, t2
        m = len(lb)
        A = sp.csr_matrix((np.r_[np.ones(m), -np.ones(m)], (np.r_[f2, t2], np.r_[np.arange(m), np.arange(m)])),
                          shape=(n2, m))
        self.A = A
        b = np.zeros(n2)
        b[self.src] = 1.0
        b[self.snk] = -1.0
        self.b = b
        keep = np.array([i for i in range(n2) if i != self.src], dtype=np.int64)
        # fill-reducing order of the reduced Laplacian
        Ar = A[keep, :].tocsr()
        Lp = (Ar @ Ar.T).tocsr()
        perm = reverse_cuthill_mckee(Lp, symmetric_mode=True)
        keep = keep[perm]
        self.keep = keep
        Ar = A[keep, :].tocsr()
        self.Ar = Ar
        # map branch weights -> CSC data of L = Ar W Ar^T
        nk = len(keep)
        pos = -np.ones(n2, dtype=np.int64)
        pos[keep] = np.arange(nk)
        pf, pt = pos[f2], pos[t2]
        rows, cols, br = [], [], []
        for k in range(m):
            a, c = pf[k], pt[k]
            if a >= 0:
                rows.append(a); cols.append(a); br.append(k)
            if c >= 0:
                rows.append(c); cols.append(c); br.append(k)
        sgn = [1.0] * len(rows)
        for k in range(m):
            a, c = pf[k], pt[k]
            if a >= 0 and c >= 0:
                rows += [a, c]; cols += [c, a]; br += [k, k]; sgn += [-1.0, -1.0]
        rows = np.array(rows); cols = np.array(cols); br = np.array(br); sgn = np.array(sgn)
        # build pattern
        key = rows * nk + cols
        ukey, inv = np.unique(key, return_inverse=True)
        ur, uc = ukey // nk, ukey % nk
        # CSC ordering of unique entries
        order = np.lexsort((ur, uc))
        rank = np.empty_like(order)
        rank[order] = np.arange(len(order))
        self.Lrow = ur[order]
        self.Lcol = uc[order]
        indptr = np.zeros(nk + 1, dtype=np.int64)
        np.add.at(indptr, self.Lcol + 1, 1)
        self.indptr = np.cumsum(indptr)
        self.indices = self.Lrow.astype(np.int32)
        self.M = sp.csr_matrix((sgn, (rank[inv], br)), shape=(len(ukey), m))
        self.nk = nk
        self.pf, self.pt = pf, pt
        self._L = sp.csc_matrix((np.ones(len(self.indices)), self.indices, self.indptr), shape=(nk, nk))

    def lap(self, w):
        L = self._L
        L.data[:] = self.M @ w
        return L

    def pot(self, lam):
        p = np.zeros(self.n2)
        p[self.keep] = lam
        return p

    def solve(self, Rall, q0=None, tol=1e-8, maxit=100):
        """Unit flow src -> snk.  Returns flows of live branches and Re."""
        R = Rall[self.lb]
        f2, t2 = self.f2, self.t2
        keep = self.keep
        if q0 is None:
            w = 1.0 / R
            lam = spla.splu(self.lap(w), permc_spec='NATURAL').solve(self.b[keep])
            p = self.pot(lam)
            q = w * (p[f2] - p[t2])
        else:
            q = q0.copy()
        A = self.A
        b = self.b
        for it in range(maxit):
            aq = np.abs(q)
            scale = aq.max()
            g = R * q * aq
            D = 2.0 * R * np.maximum(aq, 1e-9 * scale)
            w = 1.0 / D
            r = b - A @ q
            rhs = (r + A @ (w * g))[keep]
            lam = spla.splu(self.lap(w), permc_spec='NATURAL').solve(rhs)
            p = self.pot(lam)
            dq = w * (p[f2] - p[t2] - g)
            mdq = np.max(np.abs(dq))
            if mdq < tol * scale:
                q = q + dq
                break
            alpha = 1.0
            if np.max(np.abs(r)) < 1e-12:
                F0 = np.sum(R * aq ** 3)
                slope = 3.0 * np.dot(g, dq)
                while alpha > 1e-6:
                    qn = q + alpha * dq
                    if np.sum(R * np.abs(qn) ** 3) <= F0 + 1e-4 * alpha * slope + 1e-13 * F0:
                        break
                    alpha *= 0.5
            q = q + alpha * dq
        self.iters = it + 1
        g = R * q * np.abs(q)
        # pressure drop src->snk for the unit flow: sum over branches of dp*q
        Re = float(np.dot(g, q))
        return q, Re


# ----------------------------------------------------------------------------
# fans in parallel at one fan house (VS-4 section 4)
# ----------------------------------------------------------------------------
def _chol_pd(H):
    m = len(H)
    L = [[0.0] * m for _ in range(m)]
    for i in range(m):
        for j in range(i + 1):
            s = H[i][j]
            for k in range(j):
                s -= L[i][k] * L[j][k]
            if i == j:
                if s <= 1e-12 * (abs(H[i][i]) + 1.0):
                    return False
                L[i][i] = math.sqrt(s)
            else:
                L[i][j] = s / L[j][j]
    return True


def _solve(H, g):
    m = len(H)
    A = [list(H[i]) + [g[i]] for i in range(m)]
    for c in range(m):
        p = max(range(c, m), key=lambda r: abs(A[r][c]))
        if abs(A[p][c]) < 1e-300:
            return None
        A[c], A[p] = A[p], A[c]
        for r in range(c + 1, m):
            f = A[r][c] / A[c][c]
            if f:
                for k in range(c, m + 1):
                    A[r][k] -= f * A[c][k]
    x = [0.0] * m
    for r in range(m - 1, -1, -1):
        s = A[r][m]
        for k in range(r + 1, m):
            s -= A[r][k] * x[k]
        x[r] = s / A[r][r]
    return x


class FanSet:
    """Main fans in parallel between the fan house and the surface.

    G(q) = Re |Q|^3 / 3 + sum_i [Rd_i q_i^3 / 3 - int_0^q_i P_i] is the content of
    the district as a function of the fan flows; steady states are its stationary
    points and the stable ones its local minima."""

    def __init__(self, curves, Rd):
        self.m = len(curves)
        self.x = [list(map(float, c[0])) for c in curves]
        self.y = [list(map(float, c[1])) for c in curves]
        self.Rd = [float(r) for r in Rd]
        self.free = [x[-1] for x in self.x]
        self.sl = [[(y[s + 1] - y[s]) / (x[s + 1] - x[s]) for s in range(len(x) - 1)]
                   for x, y in zip(self.x, self.y)]
        self.Im = 30.0   # inertance of the district against that of a fan and its ducting
        self.qstep = max(4.0, 0.02 * max(self.free))

    def E(self, q):
        e, de = [], []
        for i in range(self.m):
            x = self.x[i]
            qi = q[i]
            s = bisect.bisect_right(x, qi) - 1
            if s < 0:
                s = 0
            elif s > len(x) - 2:
                s = len(x) - 2
            sl = self.sl[i][s]
            e.append(self.y[i][s] + sl * (qi - x[s]) - self.Rd[i] * qi * qi)
            de.append(sl - 2.0 * self.Rd[i] * qi)
        return e, de

    def grad(self, q, Re):
        e, de = self.E(q)
        Q = sum(q)
        h = Re * Q * abs(Q)
        return [h - ei for ei in e], de, Q

    def hess(self, Re, de, Q):
        a = 2.0 * Re * abs(Q)
        m = self.m
        return [[a - (de[i] if i == j else 0.0) for j in range(m)] for i in range(m)]

    def stable(self, q, Re):
        _, de = self.E(q)
        return _chol_pd(self.hess(Re, de, sum(q)))

    def newton(self, q, Re, maxit=30):
        q = list(q)
        m = self.m
        prev = None
        for it in range(maxit):
            g, de, Q = self.grad(q, Re)
            gn = max(abs(v) for v in g)
            if gn < 1e-7:
                return q, True
            if prev is not None and it > 6 and gn > 0.5 * prev:
                return q, False
            prev = gn
            dq = _solve(self.hess(Re, de, Q), g)
            if dq is None:
                return q, False
            mx = max(abs(v) for v in dq)
            f = 20.0 / mx if mx > 20.0 else 1.0
            q = [q[i] - f * dq[i] for i in range(m)]
            for i in range(m):
                if q[i] < -1e-6 or q[i] > self.free[i] * 1.05:
                    return q, False
        g, de, Q = self.grad(q, Re)
        return q, max(abs(v) for v in g) < 1e-6

    def settle(self, q, Re, maxsteps=50000):
        """Let the air settle from q: M dq/dt = -grad G, the district's inertance
        common to all fans and each fan's own in its branch."""
        m = self.m
        Im = self.Im
        c = Im / (1.0 + m * Im)
        q = list(q)
        for k in range(maxsteps):
            g, de, Q = self.grad(q, Re)
            sg = sum(g)
            v = [-(gi - c * sg) for gi in g]
            mv = max(abs(t) for t in v)
            H = self.hess(Re, de, Q)
            gersh = max(sum(abs(h) for h in row) for row in H)
            dt0 = min(0.02, 1.0 / gersh) if gersh > 0 else 0.02
            dt = dt0 if mv * dt0 < 0.25 else 0.25 / mv
            q = [min(max(q[i] + dt * v[i], 0.0), self.free[i]) for i in range(m)]
            if k % 10 == 9 and mv * dt0 < 0.25 and _chol_pd(H):
                qn, ok = self.newton(q, Re, maxit=12)
                if ok and max(abs(qn[i] - q[i]) for i in range(m)) < 1.0 and self.stable(qn, Re):
                    return qn
        qn, ok = self.newton(q, Re)
        return qn

    def equilibria(self, Re):
        """all stable steady states, by Newton from a grid of starts"""
        n = max(4, int(round(170 ** (1.0 / self.m))))
        grids = [[f * (0.02 + 0.96 * j / (n - 1)) for j in range(n)] for f in self.free]
        sols = []
        for q0 in itertools.product(*grids):
            q, ok = self.newton(list(q0), Re, maxit=60)
            if ok and all(0.0 <= q[i] <= self.free[i] for i in range(self.m)) and self.stable(q, Re):
                if not any(max(abs(q[i] - s[i]) for i in range(self.m)) < 1e-3 for s in sols):
                    sols.append(q)
        return sols

    def track(self, q, R0, R1, hmax=0.01):
        """Follow the stable state from Re = R0 to Re = R1 along the monotone
        path of the change; where it ceases to exist, let the air settle."""
        if R0 == R1:
            return list(q)
        m = self.m
        L0, L1 = math.log(R0), math.log(R1)
        n = max(1, int(math.ceil(abs(L1 - L0) / hmax)))
        h = (L1 - L0) / n
        cur = L0
        q = list(q)
        while (L1 - cur) * (L1 - L0) > 0:
            step = h if abs(h) <= abs(L1 - cur) else (L1 - cur)
            while True:
                tgt = cur + step
                last = abs(L1 - tgt) <= 1e-14
                Rt = R1 if last else math.exp(tgt)
                qn, ok = self.newton(q, Rt, maxit=15)
                if ok and max(abs(qn[i] - q[i]) for i in range(m)) < self.qstep and self.stable(qn, Rt):
                    q = qn
                    cur = L1 if last else tgt
                    break
                if abs(step) < 1e-7:
                    q = self.settle(q, Rt)
                    cur = L1 if last else tgt
                    break
                step *= 0.5
        return q


def fan_curve(pkg, model, blade):
    pts = []
    for r in pkg.curves:
        if r.get('model', '').strip() != model.strip():
            continue
        bs = r.get('blade_setting', '').strip()
        if fnum(bs) is not None and fnum(blade) is not None:
            if abs(fnum(bs) - fnum(blade)) > 1e-9:
                continue
        elif bs != blade.strip():
            continue
        x, y = fnum(r.get('flow_m3_s')), fnum(r.get('pressure_Pa'))
        if x is None or y is None:
            continue
        pts.append((x, y))
    pts.sort()
    xs, ys = [], []
    for x, y in pts:
        if xs and abs(x - xs[-1]) < 1e-12:
            ys[-1] = y
            continue
        xs.append(x); ys.append(y)
    return xs, ys


# ----------------------------------------------------------------------------
def main():
    pkgdir, outcsv = sys.argv[1], sys.argv[2]
    pts, res = [], {}
    try:
        pkg = Package(pkgdir)
        for r in pkg.points:
            pts.append(((r.get('point', '') or '').strip(), norm_time(r.get('time', '')),
                        (r.get('branch', '') or '').strip()))
        res = calculate(pkg, pkgdir, pts)
    except Exception:
        import traceback
        traceback.print_exc()
    with open(outcsv, 'w', newline='') as f:
        f.write('point,flow_m3_s\n')
        for p, t, b in pts:
            v = res.get(p, 0.0)
            if not (isinstance(v, float) and math.isfinite(v)):
                v = 0.0
            f.write('%s,%.6f\n' % (p, v))


def calculate(pkg, pkgdir, pts):
    br = pkg.branches
    names = [(r.get('branch', '') or '').strip() for r in br]
    kind = [(r.get('kind', '') or '').strip().lower() for r in br]
    fnode = [(r.get('from_node', '') or '').strip() for r in br]
    tnode = [(r.get('to_node', '') or '').strip() for r in br]
    nb = len(br)
    bidx = {n: k for k, n in enumerate(names)}

    # ---- fans (VS-4 sections 3 and 4)
    fan_rows = {}
    for f in pkg.fans:
        fan_rows[(f.get('branch', '') or '').strip()] = f
    fan_br = [k for k in range(nb) if kind[k] == 'fan' or names[k] in fan_rows]
    curves, Rd = [], []
    for k in fan_br:
        f = fan_rows.get(names[k])
        if f is None:
            item = (br[k].get('item', '') or '').strip()
            f = next((x for x in pkg.fans if (x.get('fan', '') or '').strip() == item), {})
        xs, ys = fan_curve(pkg, f.get('model', ''), f.get('blade_setting', ''))
        curves.append((xs, ys))
        Rd.append(fnum(br[k].get('resistance_Ns2_m8'), 0.0) or 0.0)
    fans = FanSet(curves, Rd)
    fh = fnode[fan_br[0]]
    atm = tnode[fan_br[0]]
    fan_set = set(fan_br)

    # ---- passive branches
    pas = [k for k in range(nb) if k not in fan_set]
    pas_pos = {k: i for i, k in enumerate(pas)}
    net = Passive([fnode[k] for k in pas], [tnode[k] for k in pas], atm, fh)
    live_pos = -np.ones(len(pas), dtype=np.int64)
    live_pos[net.lb] = np.arange(len(net.lb))

    # ---- tables
    regtab = {}
    for r in pkg.regs:
        s, v = fnum(r.get('setting')), fnum(r.get('resistance_Ns2_m8'))
        if s is None or v is None or v <= 0:
            continue
        regtab.setdefault((r.get('regulator', '') or '').strip(), {})[s] = v
    doortab = {}
    for r in pkg.doors:
        doortab[(r.get('door', '') or '').strip()] = (fnum(r.get('resistance_closed_Ns2_m8'), 1e3),
                                                      fnum(r.get('resistance_open_Ns2_m8'), 1e-3))
    item_br = {}
    for k in pas:
        it = (br[k].get('item', '') or '').strip()
        if kind[k] in ('regulator', 'door') and it:
            item_br.setdefault(it, []).append(pas_pos[k])

    def reg_R(item, setting):
        tab = regtab.get(item)
        s = fnum(setting)
        if not tab or s is None:
            return None
        if s in tab:
            return tab[s]
        ks = sorted(tab)
        if s <= ks[0]:
            return tab[ks[0]]
        if s >= ks[-1]:
            return tab[ks[-1]]
        for a, c in zip(ks[:-1], ks[1:]):
            if a <= s <= c:
                u = (s - a) / (c - a)
                return math.exp((1 - u) * math.log(tab[a]) + u * math.log(tab[c]))
        return None

    def item_R(item, setting):
        if item in doortab:
            st_ = (setting or '').strip().lower()
            return doortab[item][1] if st_.startswith('open') else doortab[item][0]
        return reg_R(item, setting)

    # ---- log (VS-4 section 5)
    log = []
    for i, r in enumerate(pkg.log):
        log.append((norm_time(r.get('time', '')), i, (r.get('item', '') or '').strip(),
                    (r.get('setting', '') or '').strip()))
    log.sort()
    t0 = log[0][0] if log else ''
    first = [e for e in log if e[0] == t0]
    rest = [e for e in log if e[0] != t0]

    # ---- resistances (VS-4 section 3)
    airways = set(names[k] for k in pas if kind[k] == 'airway')
    st = airway_status(pkg, airways)
    known = [mean_R(v['samples']) for v in st.values() if v['samples']]
    typical = float(np.median(known)) if known else 0.01
    R = np.zeros(len(pas))
    for k in pas:
        i = pas_pos[k]
        n = names[k]
        if kind[k] == 'airway':
            s = st[n]
            R[i] = mean_R(s['samples']) if s['samples'] else (
                s['fallback'] or fnum(br[k].get('resistance_Ns2_m8'), None) or typical)
        elif kind[k] == 'stopping':
            R[i] = fnum(br[k].get('resistance_Ns2_m8'), 1000.0) or 1000.0
        elif kind[k] in ('regulator', 'door'):
            R[i] = 1.0
        else:
            R[i] = fnum(br[k].get('resistance_Ns2_m8'), None) or typical
    for it, ks in item_br.items():          # items the opening rows leave out
        if it in doortab:
            v = doortab[it][0]
        else:
            tab = regtab.get(it, {0: typical})
            v = tab[max(tab)]
        for i in ks:
            R[i] = v
    for _, _, it, s in first:
        v = item_R(it, s)
        if v is not None and it in item_br:
            for i in item_br[it]:
                R[i] = v
    # stoppings whose leakage in the campaigns contradicts the register
    try:
        damaged = stopping_check(pkg, names, kind, fnode, tnode)
    except Exception:
        damaged = {}
    for k, (Rs, _) in damaged.items():
        if k in pas_pos:
            R[pas_pos[k]] = Rs
    R = np.maximum(R, 1e-9)

    ptimes = sorted(set(p[1] for p in pts))
    fan_names = [names[k] for k in fan_br]
    tolf = [0.04 * f for f in fans.free]

    def same(a, b):
        return all(abs(a[i] - b[i]) <= tolf[i] for i in range(fans.m))

    def record(Rv, warm=None):
        """the passive district through the record: Re of every state, the unit
        flows at the point times, and the flows of every state for a warm start"""
        Rv = Rv.copy()
        q, Re = net.solve(Rv, None if warm is None else warm[0])
        res_Re, snap, qs = [Re], {}, [q]
        pi = 0
        for j, (t, _, it, s) in enumerate(rest):
            while pi < len(ptimes) and ptimes[pi] < t:
                snap[ptimes[pi]] = (len(res_Re) - 1, q)
                pi += 1
            v = item_R(it, s)
            if v is not None and it in item_br:
                for i in item_br[it]:
                    Rv[i] = max(v, 1e-9)
                q, Re = net.solve(Rv, q if warm is None else warm[j + 1])
            res_Re.append(Re)
            qs.append(q)
        while pi < len(ptimes):
            snap[ptimes[pi]] = (len(res_Re) - 1, q)
            pi += 1
        return res_Re, snap, qs, Rv

    def start_states(Re0):
        c = fans.equilibria(Re0)
        if not c:
            c = [fans.settle([0.6 * f for f in fans.free], Re0)]
        c.sort(key=lambda x: -sum(x))
        return c

    def run(sRe, q0, lam=1.0, Im=None):
        old = fans.Im
        if Im is not None:
            fans.Im = Im
        out = [fans.track(q0, sRe[0], sRe[0] * lam) if lam != 1.0 else list(q0)]
        for k in range(1, len(sRe)):
            out.append(fans.track(out[-1], sRe[k - 1] * lam, sRe[k] * lam))
        fans.Im = old
        return out

    # ---- the survey order: the district as it stands after the last entry
    allowance = int(fnum(pkg.district.get('survey_allowance', 0), 0) or 0)
    need = sorted([b for b in airways if st[b]['need']], key=lambda b: (-st[b]['weight'], b))
    dmg = [names[k] for k in sorted(damaged, key=lambda k: -damaged[k][1])]
    order = need[:allowance]
    order += dmg[:max(0, allowance - len(order))]
    spare = allowance - len(order)
    pre = None
    if allowance > 0:
        # how the record ends: if a slightly different district would end it
        # in another steady state, a reading of the fans is worth more than
        # one more resistance
        try:
            pre = record(R)
            sRe = pre[0]
            c0 = start_states(sRe[0])[0]
            base = run(sRe, c0)[-1]
            alts = [run(sRe, c0, lam)[-1] for lam in (1.005, 0.995)]
            diff = [a for a in alts if not same(a, base)]
        except Exception:
            diff, base = [], None
        fan_rank = list(range(fans.m))
        if diff:
            fan_rank.sort(key=lambda i: -max(abs(a[i] - base[i]) for a in diff))
            if spare == 0 and order:
                order.pop()
                spare = 1
        obs_fans = [fan_names[i] for i in fan_rank][:spare]
        order += obs_fans
        spare -= len(obs_fans)
    else:
        obs_fans = []
    if spare > 0:
        try:
            R_last = R.copy()
            for _, _, it, s in rest:
                v = item_R(it, s)
                if v is not None and it in item_br:
                    for i in item_br[it]:
                        R_last[i] = v
            ql, Rl = net.solve(R_last)
            sens = R_last[net.lb] * np.abs(ql) ** 3 / Rl
            cand = []
            for j in np.argsort(-sens):
                n = names[pas[net.lb[j]]]
                if kind[pas[net.lb[j]]] == 'airway' and n not in order and sens[j] > 1e-3:
                    cand.append(n)
                if len(cand) >= spare:
                    break
            order += cand
        except Exception:
            pass
    crew = order_surveys(pkgdir, order) if order else {}
    for n, (dp, qq) in crew.items():
        k = bidx.get(n)
        if k is not None and k in damaged and k in pas_pos:
            Rv = survey_R(dp, qq)
            if Rv is not None:
                R[pas_pos[k]] = Rv
            continue
        if n not in airways:
            continue
        Rv = survey_R(dp, qq)
        if Rv is None:
            continue
        s = st[n]
        if s['need'] or not s['samples']:
            s['samples'] = [Rv]
            s['need'] = False
        else:
            s['samples'] = consistent(s['samples'][::-1] + [Rv])
        i = pas_pos[bidx[n]]
        R[i] = mean_R(s['samples'])
    R = np.maximum(R, 1e-9)

    # ---- the record
    states_Re, snap, _, _ = record(R, pre[2] if pre is not None else None)
    cands = start_states(states_Re[0])
    fan_states = run(states_Re, cands[0])

    # ---- the crew's reading of the fans checks the state the record ends in
    obs = [(fan_names.index(n), crew[n][1]) for n in obs_fans if n in crew]

    def agrees(qfin):
        return all(abs(qfin[i] - v) <= tolf[i] for i, v in obs)

    if obs and not agrees(fan_states[-1]):
        found = None
        trials = [(c, 1.0, None) for c in cands[1:]]
        trials += [(cands[0], 1.0, 0.1), (cands[0], 1.0, 1000.0)]
        for d in (0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02, 0.03):
            for sg in (1, -1):
                trials.append((cands[0], math.exp(sg * d), None))
        for c, lam, Im in trials:
            alt = run(states_Re, c, lam, Im)
            if agrees(alt[-1]):
                found = (alt, lam)
                break
        if found is None:
            # look for the change after which the district took another of its
            # steady states
            K = 0
            for k in range(len(fan_states) - 1, 0, -1):
                if not same(fan_states[k], fan_states[k - 1]):
                    K = k
                    break
            seg = list(range(K, len(states_Re)))
            picks = [K, max(seg, key=lambda k: states_Re[k]), min(seg, key=lambda k: states_Re[k])]
            for k0 in picks:
                for qe in fans.equilibria(states_Re[k0]):
                    if same(qe, fan_states[k0]):
                        continue
                    alt = list(fan_states[:k0]) + [qe]
                    for k in range(k0 + 1, len(states_Re)):
                        alt.append(fans.track(alt[-1], states_Re[k - 1], states_Re[k]))
                    if agrees(alt[-1]):
                        found = (alt, 1.0)
                        break
                if found is not None:
                    break
        if found is not None:
            alt, lam = found
            k = len(states_Re) - 1
            while k >= 0 and not same(alt[k], fan_states[k]):
                qa = alt[k]
                if lam != 1.0:
                    qn, ok = fans.newton(qa, states_Re[k])
                    if ok and fans.stable(qn, states_Re[k]) and max(abs(qn[i] - qa[i]) for i in range(fans.m)) < 4.0:
                        qa = qn
                fan_states[k] = qa
                k -= 1

    # ---- results (VS-4 section 6)
    fan_pos = {names[k]: i for i, k in enumerate(fan_br)}
    res = {}
    for p, t, b in pts:
        val = 0.0
        if t in snap:
            sidx, uq = snap[t]
            qfan = fan_states[sidx]
            Q = float(sum(qfan))
            if b in fan_pos:
                val = float(qfan[fan_pos[b]])
            elif b in bidx and bidx[b] in pas_pos:
                lp = live_pos[pas_pos[bidx[b]]]
                if lp >= 0:
                    val = float(uq[lp]) * Q
        res[p] = val
    return res


if __name__ == '__main__':
    main()
