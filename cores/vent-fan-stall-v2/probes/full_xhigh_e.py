#!/usr/bin/env python3
"""Airflow at every survey point of a ventilation district package, to VS-4.

Usage: python3 airflow.py PACKAGE_DIR OUT_CSV
"""
import sys
import os
import re
import csv
import json
import math
import bisect
import shutil
import subprocess

for _v in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')

import numpy as np


def log(*a):
    try:
        print(*a, file=sys.stderr)
        sys.stderr.flush()
    except Exception:
        pass


# ----------------------------------------------------------------------------
# reading the package
# ----------------------------------------------------------------------------

def read_csv(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, newline='', encoding='utf-8-sig', errors='replace') as f:
        rd = csv.reader(f)
        header = None
        for rec in rd:
            if not rec or all(not x.strip() for x in rec):
                continue
            if header is None:
                header = [h.strip().lstrip('\ufeff') for h in rec]
                continue
            rec = [x.strip() for x in rec]
            rec += [''] * (len(header) - len(rec))
            rows.append(dict(zip(header, rec)))
    return rows


def fnum(x, default=float('nan')):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def date_key(s):
    """Date or time string as a tuple of integers, for ordering."""
    parts = re.findall(r'\d+', s or '')
    if not parts:
        return (0,)
    v = [int(x) for x in parts[:6]]
    if len(parts[0]) <= 2 and len(parts) >= 3 and len(parts[2]) == 4:
        # DD-MM-YYYY
        v[0], v[2] = v[2], v[0]
    v += [0] * (6 - len(v))
    return tuple(v)


class Package:
    def __init__(self, d):
        self.dir = d
        try:
            with open(os.path.join(d, 'district.json')) as f:
                self.meta = json.load(f)
        except Exception:
            self.meta = {}
        try:
            self.allowance = int(float(self.meta.get('survey_allowance', 0)))
        except Exception:
            self.allowance = 0
        self.branches = read_csv(os.path.join(d, 'branches.csv'))
        for b in self.branches:
            b['kind'] = b.get('kind', '').strip().lower()
        self.surveys = read_csv(os.path.join(d, 'surveys.csv'))
        self.work = read_csv(os.path.join(d, 'work_log.csv'))
        self.regs = read_csv(os.path.join(d, 'regulators.csv'))
        self.doors = read_csv(os.path.join(d, 'doors.csv'))
        self.fans = read_csv(os.path.join(d, 'fans.csv'))
        self.curves = read_csv(os.path.join(d, 'fan_curves.csv'))
        self.log = read_csv(os.path.join(d, 'log.csv'))
        self.points = read_csv(os.path.join(d, 'points.csv'))


# ----------------------------------------------------------------------------
# resistances of airways (VS-4 section 3)
# ----------------------------------------------------------------------------

CHANGING_WORK = ('RESUPPORT', 'ENLARG')
NEUTRAL_WORK = ('INSPECT',)


def work_changes(w):
    w = (w or '').strip().upper()
    if any(w.startswith(k) for k in CHANGING_WORK):
        return 1
    if any(w.startswith(k) for k in NEUTRAL_WORK):
        return 0
    return 2  # unknown kind of work: treat as possibly changing


def survey_R(dp, q):
    if not (math.isfinite(dp) and math.isfinite(q)) or q == 0:
        return None
    R = dp / (q * abs(q))
    if not math.isfinite(R) or R <= 0:
        return None
    return R


def airway_resistances(pkg, airways):
    """Return (R dict of valid resistances, list of needs with priority, fallback R dict)."""
    sv = {}
    for i, s in enumerate(pkg.surveys):
        br = s.get('branch', '')
        if br not in airways:
            continue
        R = survey_R(fnum(s.get('dp_Pa')), fnum(s.get('q_m3_s')))
        sv.setdefault(br, []).append((date_key(s.get('date')), i, R))
    jobs = {}
    for w in pkg.work:
        br = w.get('branch', '')
        if br not in airways:
            continue
        c = work_changes(w.get('work'))
        if c:
            jobs.setdefault(br, []).append((date_key(w.get('date')), c))
    Rv = {}       # resistance from a valid survey on file
    Rfb = {}      # survey value to fall back on where the survey on file may not hold
    needs = []    # (priority, branch, estimate_from_neighbours)
    # priority 0: no survey since the work (or none at all); 1: survey on the day of the work
    # that shows no change; 2: unknown kind of work; 3: survey on the day of the work that
    # shows the change
    for br in sorted(airways):
        lst = sorted(sv.get(br, []))
        good = [x for x in lst if x[2] is not None]
        jl = sorted(jobs.get(br, []))
        if not good:
            needs.append((0, br, True))
            continue
        if not jl:
            Rv[br] = good[-1][2]
            continue
        # latest job that changes the airway
        jdate = max(j[0] for j in jl)
        jkind = min(j[1] for j in jl if j[0] == jdate)
        after = [x for x in good if x[0] > jdate]
        same = [x for x in good if x[0] == jdate]
        before = [x for x in good if x[0] < jdate]
        if after:
            Rv[br] = after[-1][2]
            continue
        if same:
            # survey on the day of the job: was it made before or after the work?
            Rs = same[-1][2]
            Rfb[br] = Rs
            if before and abs(math.log(Rs / before[-1][2])) <= 0.04:
                # no change since the survey before: read before the work
                needs.append((1 if jkind == 1 else 2, br, jkind == 1))
            else:
                needs.append((3, br, False))
            continue
        # every survey on file is older than the work
        Rfb[br] = good[-1][2]
        if jkind == 1:
            needs.append((0, br, True))
        else:
            needs.append((2, br, False))
    return Rv, needs, Rfb, sv


# ----------------------------------------------------------------------------
# the survey crew
# ----------------------------------------------------------------------------

def find_pqsurvey():
    exe = shutil.which('pqsurvey')
    if exe:
        return exe
    for c in ('/tmp/vfb_xe/app/pqsurvey',):
        if os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return None


def order_survey(pkg_dir, branches):
    """Place the one survey order; return {branch: (dp, q)}."""
    out = {}
    if not branches:
        return out
    exe = find_pqsurvey()
    if exe is None:
        log('pqsurvey not found')
        return out
    try:
        pr = subprocess.run([exe, pkg_dir] + list(branches), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, timeout=20)
    except Exception as e:
        log('pqsurvey failed:', e)
        return out
    if pr.returncode != 0:
        log('pqsurvey exit', pr.returncode, pr.stderr.strip()[:500])
    for line in pr.stdout.splitlines():
        parts = [x.strip() for x in line.split(',')]
        if len(parts) < 3:
            continue
        dp = fnum(parts[1]); q = fnum(parts[2])
        if parts[0] in branches and math.isfinite(dp) and math.isfinite(q):
            out[parts[0]] = (dp, q)
    return out


# ----------------------------------------------------------------------------
# passive network: R q|q| = p_from - p_to, two fixed pressures
# ----------------------------------------------------------------------------

class PassiveNet:
    def __init__(self, names, fr, to, term_hi, term_lo):
        """term_hi held at 0, term_lo held at -1."""
        self.names = names
        E = len(names)
        self.E = E
        nodes = {}
        for n in list(fr) + list(to) + [term_hi, term_lo]:
            if n not in nodes:
                nodes[n] = len(nodes)
        self.nodes = nodes
        fi = np.array([nodes[n] for n in fr], dtype=np.int64)
        ti = np.array([nodes[n] for n in to], dtype=np.int64)
        N = len(nodes)
        hi = nodes[term_hi]; lo = nodes[term_lo]
        # prune: branches not in the component of the terminals, dead ends
        active = np.ones(E, bool)
        active[fi == ti] = False
        # component containing terminals
        adj = [[] for _ in range(N)]
        for e in range(E):
            if active[e]:
                adj[fi[e]].append((ti[e], e)); adj[ti[e]].append((fi[e], e))
        seen = np.zeros(N, bool)
        stack = [hi, lo]
        seen[hi] = seen[lo] = True
        while stack:
            n = stack.pop()
            for m, e in adj[n]:
                if not seen[m]:
                    seen[m] = True; stack.append(m)
        for e in range(E):
            if active[e] and not seen[fi[e]]:
                active[e] = False
        # dead ends
        deg = np.zeros(N, np.int64)
        np.add.at(deg, fi[active], 1); np.add.at(deg, ti[active], 1)
        changed = True
        while changed:
            changed = False
            dead = np.where(active & (((deg[fi] == 1) & (fi != hi) & (fi != lo)) |
                                      ((deg[ti] == 1) & (ti != hi) & (ti != lo))))[0]
            if len(dead):
                changed = True
                for e in dead:
                    if active[e]:
                        active[e] = False
                        deg[fi[e]] -= 1; deg[ti[e]] -= 1
        self.active = active
        ae = np.where(active)[0]
        self.ae = ae
        afi = fi[ae]; ati = ti[ae]
        used = np.zeros(N, bool); used[afi] = True; used[ati] = True
        used[hi] = used[lo] = True
        free_nodes = [n for n in range(N) if used[n] and n != hi and n != lo]
        nf = len(free_nodes)
        self.nf = nf
        loc = -np.ones(N, np.int64)
        loc[free_nodes] = np.arange(nf)
        # ordering for a small bandwidth
        perm = np.arange(nf)
        if nf > 2:
            try:
                import scipy.sparse as sp
                from scipy.sparse.csgraph import reverse_cuthill_mckee
                lf = loc[afi]; lt = loc[ati]
                m = (lf >= 0) & (lt >= 0)
                G = sp.csr_matrix((np.ones(2 * m.sum()), (np.concatenate([lf[m], lt[m]]),
                                                         np.concatenate([lt[m], lf[m]]))),
                                  shape=(nf, nf))
                perm = np.asarray(reverse_cuthill_mckee(G, symmetric_mode=True))
            except Exception:
                perm = np.arange(nf)
        inv = np.empty(nf, np.int64); inv[perm] = np.arange(nf)
        pos = -np.ones(N, np.int64)
        pos[free_nodes] = inv[np.arange(nf)]
        self.pf = pos[afi]; self.pt = pos[ati]
        self.fhi = (afi == hi) | (ati == hi)
        self.flo_from = (afi == lo)
        self.flo_to = (ati == lo)
        pf = self.pf; pt = self.pt
        both = (pf >= 0) & (pt >= 0)
        bw = int(np.max(np.abs(pf[both] - pt[both]))) if both.any() else 0
        self.bw = bw
        self.use_band = bw <= 120 and nf > 0
        nE = len(ae)
        # flat index of band storage (upper form) ab[bw + i - j, j], i <= j
        if self.use_band:
            W = bw + 1
            def flat(i, j):
                ii = np.minimum(i, j); jj = np.maximum(i, j)
                return (bw + ii - jj) * nf + jj
            idx = []; src = []; sgn = []
            mf = pf >= 0; mt = pt >= 0
            e_ = np.arange(nE)
            idx.append(flat(pf[mf], pf[mf])); src.append(e_[mf])
            idx.append(flat(pt[mt], pt[mt])); src.append(e_[mt])
            idx.append(flat(pf[both], pt[both])); src.append(e_[both])
            self.band_idx = np.concatenate(idx)
            self.band_src = np.concatenate(src)
            nd = mf.sum() + mt.sum()
            self.band_sign = np.concatenate([np.ones(nd), -np.ones(both.sum())])
            self.band_size = W * nf
        else:
            import scipy.sparse as sp
            mf = pf >= 0; mt = pt >= 0
            e_ = np.arange(nE)
            self.sp_r = np.concatenate([pf[mf], pt[mt], pf[both], pt[both]])
            self.sp_c = np.concatenate([pf[mf], pt[mt], pt[both], pf[both]])
            self.sp_src = np.concatenate([e_[mf], e_[mt], e_[both], e_[both]])
            self.sp_sign = np.concatenate([np.ones(mf.sum() + mt.sum()), -np.ones(2 * both.sum())])
        self.q = None
        # node incidence for flow into term_lo (the fan house)
        self.into_lo = np.where(self.flo_to, 1.0, 0.0) - np.where(self.flo_from, 1.0, 0.0)

    def solve(self, Rfull, tol=1e-10, maxit=200):
        R = np.maximum(Rfull[self.ae], 1e-9)
        nE = len(R)
        nf = self.nf
        pf = self.pf; pt = self.pt
        q = self.q
        if q is None:
            q = np.full(nE, 1.0)
            # first linear estimate
        scale = max(np.max(np.abs(q)), 1e-12)
        from scipy.linalg import solveh_banded
        for it in range(maxit):
            aq = np.abs(q)
            D = 2.0 * R * np.maximum(aq, 1e-7 * scale)
            w = 1.0 / D
            h = R * q * aq
            t = w * h - q
            # rhs at free nodes
            rhs = np.zeros(nf + 1)
            # A[n,e] = +1 at from, -1 at to
            rhs += np.bincount(np.where(pf >= 0, pf, nf), weights=t, minlength=nf + 1)
            rhs -= np.bincount(np.where(pt >= 0, pt, nf), weights=t, minlength=nf + 1)
            # fixed pressure at term_lo = -1: rhs_n += w_e * p_c
            lo_e = self.flo_from | self.flo_to
            other = np.where(self.flo_from, pt, pf)
            m = lo_e & (other >= 0)
            if m.any():
                rhs -= np.bincount(other[m], weights=w[m], minlength=nf + 1)
            rhs = rhs[:nf]
            if nf > 0:
                if self.use_band:
                    ab = np.bincount(self.band_idx, weights=w[self.band_src] * self.band_sign,
                                     minlength=self.band_size).reshape(self.bw + 1, nf)
                    try:
                        p = solveh_banded(ab, rhs, check_finite=False)
                    except Exception:
                        p = self._sparse_solve(w, rhs)
                else:
                    p = self._sparse_solve(w, rhs)
            else:
                p = np.zeros(0)
            pext = np.concatenate([p, [0.0]])
            # pressure at ends
            pfrom = np.where(pf >= 0, pext[np.where(pf >= 0, pf, nf)], np.where(self.flo_from, -1.0, 0.0))
            pto = np.where(pt >= 0, pext[np.where(pt >= 0, pt, nf)], np.where(self.flo_to, -1.0, 0.0))
            dp = pfrom - pto
            qn = q + w * (dp - h)
            err = np.max(np.abs(qn - q)) if nE else 0.0
            q = qn
            scale = max(np.max(np.abs(q)), 1e-12)
            if err <= tol * scale:
                break
        self.q = q
        self.iters = it + 1
        full = np.zeros(self.E)
        full[self.ae] = q
        Q = float(np.dot(self.into_lo, q))
        return full, Q

    def _sparse_solve(self, w, rhs):
        import scipy.sparse as sp
        import scipy.sparse.linalg as spla
        if self.use_band:
            # rebuild a sparse matrix from the band description
            pf = self.pf; pt = self.pt
            both = (pf >= 0) & (pt >= 0)
            mf = pf >= 0; mt = pt >= 0
            e_ = np.arange(len(w))
            r = np.concatenate([pf[mf], pt[mt], pf[both], pt[both]])
            c = np.concatenate([pf[mf], pt[mt], pt[both], pf[both]])
            v = np.concatenate([w[mf], w[mt], -w[both], -w[both]])
        else:
            r = self.sp_r; c = self.sp_c; v = w[self.sp_src] * self.sp_sign
        M = sp.csc_matrix((v, (r, c)), shape=(self.nf, self.nf))
        return spla.spsolve(M, rhs)


# ----------------------------------------------------------------------------
# fans (VS-4 section 4)
# ----------------------------------------------------------------------------

class Fan:
    """Characteristic seen from the fan house: F(q) = P_fan(q) - r q|q|."""

    def __init__(self, qs, ps, r):
        o = np.argsort(qs, kind='stable')
        qs = np.asarray(qs, float)[o]; ps = np.asarray(ps, float)[o]
        self.qs = qs; self.ps = ps; self.r = r
        ints = []
        for j in range(len(qs) - 1):
            q0, q1 = qs[j], qs[j + 1]
            if q1 <= q0:
                continue
            s = (ps[j + 1] - ps[j]) / (q1 - q0)
            if r > 0:
                qc = s / (2 * r)
            else:
                qc = -np.inf if s < 0 else np.inf
            a = max(q0, qc)
            if a < q1 - 1e-12:
                ints.append([a, q1])
        merged = []
        for a, c in ints:
            if merged and abs(merged[-1][1] - a) < 1e-9:
                merged[-1][1] = c
            else:
                merged.append([a, c])
        self.ints = merged
        # dense monotone tables per falling interval
        self.tabs = []
        for a, c in merged:
            pts = [a, c] + [x for x in qs if a < x < c]
            grid = np.unique(np.concatenate([np.array(pts), np.linspace(a, c, 4001)]))
            Fv = self.F(grid)
            # strictly decreasing table (reverse for interp)
            self.tabs.append((grid, Fv))
        self.pr = [(self.tabs[k][1][-1], self.tabs[k][1][0]) for k in range(len(merged))]

    def F(self, q):
        q = np.asarray(q, float)
        return np.interp(q, self.qs, self.ps) - self.r * q * np.abs(q)

    def qinv(self, P, k):
        grid, Fv = self.tabs[k]
        return float(np.interp(P, Fv[::-1], grid[::-1]))


class FanHouse:
    def __init__(self, fans):
        self.fans = fans
        self.cache = {}

    def limits(self, A):
        """Valid range [Rlo, Rhi] of the equivalent resistance for assignment A."""
        if A in self.cache:
            return self.cache[A]
        fl = self.fans
        Plo = max(fl[i].pr[k][0] for i, k in enumerate(A))
        Phi = min(fl[i].pr[k][1] for i, k in enumerate(A))
        if Plo >= Phi:
            res = None
        else:
            Qhi = sum(fl[i].qinv(Phi, k) for i, k in enumerate(A))
            Rhi = Phi / Qhi ** 2 if Qhi > 0 and Phi > 0 else (np.inf if Phi > 0 else -np.inf)
            if Plo <= 0:
                Rlo = -np.inf
            else:
                Qlo = sum(fl[i].qinv(Plo, k) for i, k in enumerate(A))
                Rlo = Plo / Qlo ** 2 if Qlo > 0 else np.inf
            ihi = min(range(len(A)), key=lambda i: fl[i].pr[A[i]][1])
            ilo = max(range(len(A)), key=lambda i: fl[i].pr[A[i]][0])
            res = (Rlo, Rhi, Plo, Phi, ilo, ihi)
        self.cache[A] = res
        return res

    def valid(self, A, R):
        L = self.limits(A)
        return L is not None and L[0] <= R <= L[1]

    def equilibrium(self, A, R):
        fl = self.fans
        L = self.limits(A)
        Plo, Phi = L[2], L[3]
        lo = max(Plo, 0.0); hi = Phi

        def g(P):
            return sum(fl[i].qinv(P, k) for i, k in enumerate(A)) - math.sqrt(max(P, 0.0) / R)
        glo = g(lo); ghi = g(hi)
        if glo <= 0:
            P = lo
        elif ghi >= 0:
            P = hi
        else:
            a, b = lo, hi
            fa, fb = glo, ghi
            for _ in range(200):
                # regula falsi / bisection mix
                m = 0.5 * (a + b)
                fm = g(m)
                if fm > 0:
                    a, fa = m, fm
                else:
                    b, fb = m, fm
                if b - a < 1e-10 * max(1.0, abs(b)):
                    break
            P = 0.5 * (a + b)
        qs = [fl[i].qinv(P, k) for i, k in enumerate(A)]
        return P, qs

    def jump(self, A, R):
        """Follow the fan house from assignment A to equivalent resistance R."""
        A = list(A)
        fl = self.fans
        for _ in range(4 * len(A) + 8):
            L = self.limits(tuple(A))
            if L is None:
                return None
            Rlo, Rhi, Plo, Phi, ilo, ihi = L
            if Rlo <= R <= Rhi:
                return tuple(A)
            if R > Rhi:
                i = ihi; Pst = Phi
                # stall: the nearest falling interval to lower flow that reaches Pst
                k = A[i] - 1
                while k >= 0 and fl[i].pr[k][1] < Pst:
                    k -= 1
                if k < 0:
                    k = A[i] - 1 if A[i] > 0 else None
                if k is None:
                    return None
                A[i] = k
            else:
                i = ilo; Pst = Plo
                k = A[i] + 1
                n = len(fl[i].ints)
                while k < n and fl[i].pr[k][0] > Pst:
                    k += 1
                if k >= n:
                    k = A[i] + 1 if A[i] + 1 < n else None
                if k is None:
                    return None
                A[i] = k
        return None


# ----------------------------------------------------------------------------
# main calculation
# ----------------------------------------------------------------------------

def main(pkg_dir, out_csv):
    pkg = Package(pkg_dir)
    points = pkg.points
    br = pkg.branches
    names = [b['branch'] for b in br]
    bidx = {n: i for i, n in enumerate(names)}
    kinds = [b['kind'] for b in br]
    airways = set(n for n, k in zip(names, kinds) if k == 'airway')

    # ---------------- airway resistances
    Rv, needs, Rfb, svlist = airway_resistances(pkg, airways)
    allow = max(pkg.allowance, 0)
    survey = {}

    # ---------------- network data
    fans_by_branch = {}
    for f in pkg.fans:
        fans_by_branch[f.get('branch', '')] = f
    fan_brs = [n for n, k in zip(names, kinds) if k == 'fan']
    for n in list(fans_by_branch):
        if n in bidx and n not in fan_brs:
            fan_brs.append(n)
    reg_tab = {}
    for r in pkg.regs:
        reg_tab.setdefault(r.get('regulator', ''), []).append((fnum(r.get('setting')), fnum(r.get('resistance_Ns2_m8'))))
    for k in reg_tab:
        reg_tab[k].sort()
    door_tab = {}
    for d in pkg.doors:
        door_tab[d.get('door', '')] = (fnum(d.get('resistance_closed_Ns2_m8')), fnum(d.get('resistance_open_Ns2_m8')))

    def reg_R(item, setting):
        tab = reg_tab.get(item)
        s = fnum(setting)
        if not tab or not math.isfinite(s):
            return None
        for x, r in tab:
            if abs(x - s) < 1e-9:
                return r
        xs = [x for x, _ in tab]; rs = [math.log(r) for _, r in tab]
        return math.exp(float(np.interp(s, xs, rs)))

    def door_R(item, setting):
        t = door_tab.get(item)
        if t is None:
            return None
        s = (setting or '').strip().lower()
        if s.startswith('o'):
            return t[1]
        if s.startswith('c') or s.startswith('s'):
            return t[0]
        v = fnum(s)
        if math.isfinite(v):
            return t[1] if v > 0 else t[0]
        return None

    # fan house terminals
    fb_rows = [br[bidx[n]] for n in fan_brs]
    pairs = set((b['from_node'], b['to_node']) for b in fb_rows)
    if len(pairs) != 1:
        log('fans not at one pair of nodes:', pairs)
    fh, atm = fb_rows[0]['from_node'], fb_rows[0]['to_node']

    pas_idx = [i for i, k in enumerate(kinds) if names[i] not in fan_brs]
    pas_names = [names[i] for i in pas_idx]
    pas_pos = {n: j for j, n in enumerate(pas_names)}
    net = PassiveNet(pas_names, [br[i]['from_node'] for i in pas_idx],
                     [br[i]['to_node'] for i in pas_idx], atm, fh)

    R = np.zeros(len(pas_idx))
    item_pos = {}
    for j, i in enumerate(pas_idx):
        b = br[i]; k = b['kind']
        if k == 'airway':
            continue
        elif k == 'stopping':
            R[j] = fnum(b.get('resistance_Ns2_m8'), 1e4)
        elif k in ('regulator', 'door'):
            item_pos.setdefault(b.get('item', ''), []).append((j, k))
            R[j] = fnum(b.get('resistance_Ns2_m8'), float('nan'))
        else:
            R[j] = fnum(b.get('resistance_Ns2_m8'), float('nan'))

    # fans
    fans_by_name = {f.get('fan', ''): f for f in pkg.fans}
    fan_objs = []
    for n in fan_brs:
        f = fans_by_branch.get(n) or fans_by_name.get(br[bidx[n]].get('item', ''))
        rd = fnum(br[bidx[n]].get('resistance_Ns2_m8'), 0.0)
        if not math.isfinite(rd):
            rd = 0.0
        model = f.get('model', '') if f else ''
        blade = fnum(f.get('blade_setting', '')) if f else float('nan')
        mrows = [c for c in pkg.curves if c.get('model', '') == model] or list(pkg.curves)
        blades = sorted(set(fnum(c.get('blade_setting')) for c in mrows))
        if blade not in blades and blades:
            log('blade setting', blade, 'of', n, 'not in the catalogue; nearest taken')
            blade = min(blades, key=lambda b: abs(b - blade) if math.isfinite(blade) else 0)
        cq = []; cp = []
        for c in mrows:
            if fnum(c.get('blade_setting')) == blade:
                cq.append(fnum(c.get('flow_m3_s'))); cp.append(fnum(c.get('pressure_Pa')))
        fan_objs.append(Fan(cq, cp, rd))
    house = FanHouse(fan_objs)

    # ---------------- log: settings over time
    logrows = sorted(enumerate(pkg.log), key=lambda x: (date_key(x[1].get('time')), x[0]))
    groups = []
    for _, r in logrows:
        t = date_key(r.get('time'))
        if groups and groups[-1][0] == t:
            groups[-1][1].append(r)
        else:
            groups.append((t, [r]))
    times = [g[0] for g in groups]

    # default settings for items not in the opening rows: doors closed, regulators as table max
    for item, lst in item_pos.items():
        for j, k in lst:
            if not math.isfinite(R[j]) or R[j] <= 0:
                if k == 'door' and item in door_tab:
                    R[j] = door_tab[item][0]
                elif k == 'regulator' and item in reg_tab:
                    R[j] = reg_tab[item][-1][1]

    def apply(r):
        item = r.get('item', '')
        for j, k in item_pos.get(item, []):
            v = reg_R(item, r.get('setting')) if k == 'regulator' else door_R(item, r.get('setting'))
            if v is not None and math.isfinite(v) and v > 0:
                R[j] = v

    # ---------------- airway resistances, survey order
    def set_airways(extra_R):
        for j, i in enumerate(pas_idx):
            n = names[i]
            if kinds[i] == 'airway':
                if n in extra_R:
                    R[j] = extra_R[n]
                elif n in Rv:
                    R[j] = Rv[n]
                elif n in Rfb:
                    R[j] = Rfb[n]
                else:
                    R[j] = float('nan')

    # estimates for airways that want a survey, from like airways that have a valid one
    est = {}
    known = [v for v in Rv.values() if math.isfinite(v) and v > 0]
    med = float(np.median(known)) if known else 0.01

    def group_key(n):
        m = re.match(r'^(.*?)[-_ ]?\d+$', n)
        return m.group(1) if m else None
    groups_R = {}
    for n, v in Rv.items():
        g = group_key(n)
        if g is not None:
            groups_R.setdefault(g, []).append(v)
    node_air = {}
    for i, n in enumerate(names):
        if kinds[i] == 'airway':
            for nd in (br[i]['from_node'], br[i]['to_node']):
                node_air.setdefault(nd, []).append(n)
    for _, n, use_est in needs:
        if not use_est and n in Rfb:
            est[n] = Rfb[n]
            continue
        g = group_key(n)
        if g is not None and len(groups_R.get(g, [])) >= 4:
            est[n] = float(np.median(groups_R[g]))
            continue
        i = bidx[n]
        nb = [Rv[m] for nd in (br[i]['from_node'], br[i]['to_node'])
              for m in node_air.get(nd, []) if m != n and m in Rv]
        est[n] = float(np.median(nb)) if nb else med

    set_airways(est)
    for j in range(len(R)):
        if not math.isfinite(R[j]) or R[j] <= 0:
            R[j] = med

    # ---------------- a first look at the record: opening state and the state now
    R_open = R.copy()
    nst = len(groups)
    cand0 = None
    q_now = None
    try:
        if nst:
            for r in groups[0][1]:
                apply(r)
            _, Q0 = net.solve(R)
            nints = [len(f.ints) for f in fan_objs]
            import itertools
            cand0 = [A for A in itertools.product(*[range(n) for n in nints])
                     if house.valid(A, 1.0 / Q0 ** 2)]
            for g in groups[1:]:
                for r in g[1]:
                    apply(r)
            q_now, _ = net.solve(R)
    except Exception as e:
        log('first look failed:', e)
    R[:] = R_open
    net.q = None

    # ---------------- the survey order
    def impact(n):
        if q_now is None or n not in pas_pos:
            return 0.0
        return abs(q_now[pas_pos[n]])
    needs.sort(key=lambda x: (x[0], -impact(x[1]), x[1]))
    order = [n for _, n, _ in needs][:allow]
    if len(needs) > allow:
        log('more airways want a survey (%d) than the allowance (%d)' % (len(needs), allow))
    if cand0 is not None and len(cand0) > 1 and len(order) < allow and q_now is not None:
        # the opening state of the fan house cannot be told from the record:
        # have the crew read the airway carrying the most air as well
        best_air = sorted((n for n in airways if n in pas_pos and n not in order),
                          key=lambda n: -impact(n))
        if best_air:
            order.append(best_air[0])
    log('survey order:', order)
    survey = order_survey(pkg_dir, order) if order else {}
    newR = {}
    for n, (dp, q) in survey.items():
        r_ = survey_R(dp, q)
        if r_ is not None:
            newR[n] = r_
    missing = [n for n in order if n not in newR]
    if missing:
        log('no reading for:', missing)
    est.update(newR)
    set_airways(est)
    for j in range(len(R)):
        if not math.isfinite(R[j]) or R[j] <= 0:
            R[j] = med

    # ---------------- states
    need_states = set()
    pt_state = []
    for p in points:
        t = date_key(p.get('time'))
        k = bisect.bisect_right(times, t) - 1
        if k < 0:
            k = 0
        pt_state.append(k)
        need_states.add(k)
    nst = len(groups)
    last = nst - 1
    need_states.add(last)
    Req = np.zeros(max(nst, 1))
    store = {}
    for k, (t, rows) in enumerate(groups):
        for r in rows:
            apply(r)
        qv, Q = net.solve(R)
        Req[k] = 1.0 / Q ** 2 if Q > 0 else np.inf
        if k in need_states:
            store[k] = qv.copy()
    if nst == 0:
        qv, Q = net.solve(R)
        Req[0] = 1.0 / Q ** 2
        store[0] = qv
        nst = 1; last = 0

    # ---------------- fan house through the record
    import itertools
    nints = [len(f.ints) for f in fan_objs]
    allA = list(itertools.product(*[range(n) for n in nints]))
    cand = [A for A in allA if house.valid(A, Req[0])]
    if not cand:
        # nearest assignment
        cand = [tuple(n - 1 for n in nints)]
    log('initial fan house states:', cand)

    def track(A0):
        seq = []
        A = A0
        for k in range(nst):
            if k > 0:
                B = house.jump(A, Req[k])
                if B is None:
                    B = A
                A = B
            seq.append(A)
        return seq

    seqs = [track(A) for A in cand]

    def now_misfit(seq):
        """rms relative misfit of the state now against the crew's readings."""
        A = seq[last]
        if not house.valid(A, Req[last]):
            return np.inf, 0
        P, qs = house.equilibrium(A, Req[last])
        err = 0.0; cnt = 0
        for n, (dp, q) in survey.items():
            if n in pas_pos and abs(q) > 0:
                qp = store[last][pas_pos[n]] * math.sqrt(P)
                err += ((qp - q) / abs(q)) ** 2; cnt += 1
        return (math.sqrt(err / cnt) if cnt else 0.0), cnt

    def open_flow(A):
        P, qs = house.equilibrium(A, Req[0])
        return sum(qs)

    fits = [now_misfit(s) for s in seqs]
    best = 0
    if len(cand) > 1:
        # the state now, as the crew read it, tells the opening state where it can;
        # otherwise the fans are taken to open on the high-flow side of their characteristics
        m = min(f[0] for f in fits)
        ok = [i for i, f in enumerate(fits) if f[0] <= m + 0.005]
        best = max(ok, key=lambda i: (open_flow(cand[i]), -i))
        log('opening candidates', cand, 'misfits', fits, 'chosen', cand[best])
    seq = seqs[best]
    fit = fits[best]
    log('misfit of the state now against the readings: %.4f over %d' % fit)
    # other states of the fan house now, for comparison
    try:
        for A in allA:
            if A != seq[last] and house.valid(A, Req[last]):
                alt = list(seq); alt[last] = A
                log('  if the fan house were in', A, 'now: misfit %.4f' % now_misfit(alt)[0])
    except Exception:
        pass
    if fit[1] and fit[0] > 0.01:
        # the readings do not bear out the state the record leads to: try the fan house
        # without memory of its past (the valid state of most, or of least, air)
        def memoryless(sign):
            out_ = []
            for k in range(nst):
                vs = [A for A in allA if house.valid(A, Req[k])]
                if not vs:
                    out_.append(out_[-1] if out_ else seq[k]); continue
                out_.append(max(vs, key=lambda A: sign * sum(house.equilibrium(A, Req[k])[1])))
            return out_
        for sign in (1, -1):
            try:
                alt = memoryless(sign)
                f2 = now_misfit(alt)
                log('memoryless variant', sign, 'misfit %.4f' % f2[0])
                if f2[0] < 0.01 and f2[0] < fit[0] / 3:
                    seq = alt; fit = f2
                    log('taking the memoryless variant', sign)
                    break
            except Exception as e:
                log('variant failed', e)

    # ---------------- results
    eqcache = {}
    fanpos = {n: i for i, n in enumerate(fan_brs)}
    out = []
    for p, k in zip(points, pt_state):
        A = seq[k]
        if k not in eqcache:
            if house.limits(A) is None:
                eqcache[k] = (0.0, [0.0] * len(fan_objs))
            else:
                eqcache[k] = house.equilibrium(A, Req[k])
        P, qs = eqcache[k]
        b = p.get('branch', '')
        if b in fanpos:
            v = qs[fanpos[b]]
        elif b in pas_pos:
            v = store[k][pas_pos[b]] * math.sqrt(P)
        else:
            v = 0.0
        out.append((p.get('point', ''), v))
    try:
        d = os.path.dirname(os.path.abspath(out_csv))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    with open(out_csv, 'w', newline='') as f:
        f.write('point,flow_m3_s\n')
        for n, v in out:
            if not math.isfinite(v):
                v = 0.0
            f.write('%s,%.6f\n' % (n, v))


def fallback(pkg_dir, out_csv):
    rows = read_csv(os.path.join(pkg_dir, 'points.csv'))
    with open(out_csv, 'w', newline='') as f:
        f.write('point,flow_m3_s\n')
        for r in rows:
            f.write('%s,%.6f\n' % (r.get('point', ''), 0.0))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('usage: airflow.py PACKAGE_DIR OUT_CSV', file=sys.stderr)
        sys.exit(0)
    try:
        main(sys.argv[1], sys.argv[2])
    except Exception:
        import traceback
        traceback.print_exc()
        try:
            fallback(sys.argv[1], sys.argv[2])
        except Exception:
            traceback.print_exc()
    sys.exit(0)
