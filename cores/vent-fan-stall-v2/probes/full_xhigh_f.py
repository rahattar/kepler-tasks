#!/usr/bin/env python3
"""Airflow at every survey point of a ventilation district package, to VS-4.

    python3 airflow.py PACKAGE_DIR OUT_CSV

Method
------
* Resistances (VS-4 s.3): airways from their surveys made since the last
  re-support/enlargement (repeat readings of an unchanged airway are averaged);
  airways with no such survey are surveyed by the crew.  Stoppings use the
  register unless the survey campaigns show one leaking far more than its
  register resistance allows; such stoppings are surveyed by the crew (or,
  failing that, given the resistance the campaign shows).  Doors and
  regulators come from their tables at the setting in the log.
* Every passive branch obeys dp = R q|q|, so the district seen from the fan
  house is exactly H = Req Q^2.  Req is found for every state of the log by a
  Newton solution of the network carrying unit flow; the flow in any branch is
  Q times its unit-flow share.
* The fans stand in parallel: H = P_i(q_i) - r_i q_i^2 for each fan.  The
  fan characteristics have a stall dip, so a district can have more than one
  steady state.  Settings change slowly (s.5), so the fans follow their
  operating branch quasi-statically as Req moves monotonically from one log
  state to the next; when a branch ends (a fold) the fan at its peak (or
  trough) drops (or recovers) onto its neighbouring stable branch.
"""
import csv
import json
import math
import os
import subprocess
import sys
import itertools

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu
from scipy.sparse.csgraph import connected_components


# ----------------------------------------------------------------------------
# reading

def read_csv(d, name):
    path = os.path.join(d, name)
    if not os.path.exists(path):
        return []
    with open(path, newline='') as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        out.append({(k or '').strip(): (v or '').strip() for k, v in r.items()})
    return out


def fnum(x, default=float('nan')):
    try:
        return float(x)
    except Exception:
        return default


# ----------------------------------------------------------------------------
# passive network: unit flow from node T to node F

class Passive:
    def __init__(self, nn, fi, ti, T, F):
        nb = len(fi)
        # restrict to the connected component holding T and F (self-loops carry nothing)
        G = sp.csr_matrix((np.ones(nb), (fi, ti)), shape=(nn, nn))
        nc, lab = connected_components(G, directed=False)
        comp = lab[T]
        act = np.where((lab[fi] == comp) & (fi != ti))[0]
        self.act = act
        nodes = np.where(lab == comp)[0]
        nodes = nodes[nodes != F]
        loc = -np.ones(nn, dtype=int)
        loc[nodes] = np.arange(len(nodes))
        rows = np.r_[loc[fi[act]], loc[ti[act]]]
        cols = np.r_[np.arange(len(act)), np.arange(len(act))]
        vals = np.r_[np.ones(len(act)), -np.ones(len(act))]
        m = rows >= 0
        self.A = sp.csr_matrix((vals[m], (rows[m], cols[m])), shape=(len(nodes), len(act)))
        self.AT = self.A.T.tocsr()
        self.s = np.zeros(len(nodes))
        self.s[loc[T]] = 1.0
        self.Tloc = loc[T]
        self.n = len(nodes)
        # pattern of L = A diag(w) A^T, and where each branch weight goes in it
        u = loc[fi[act]]
        v = loc[ti[act]]
        k = np.arange(len(act))
        er = np.r_[u, v, u, v]
        ec = np.r_[u, v, v, u]
        eb = np.r_[k, k, k, k]
        es = np.r_[np.ones(2 * len(act)), -np.ones(2 * len(act))]
        m = (er >= 0) & (ec >= 0)
        er, ec, eb, es = er[m], ec[m], eb[m], es[m]
        n = len(nodes)
        keys = ec.astype(np.int64) * n + er
        uk, inv = np.unique(keys, return_inverse=True)
        self.Lrows = (uk % n).astype(np.int32)
        cols = (uk // n).astype(np.int64)
        self.Lptr = np.r_[0, np.cumsum(np.bincount(cols, minlength=n))].astype(np.int32)
        self.Linv = inv
        self.Lb = eb
        self.Ls = es
        self.Lnnz = len(uk)
        self.Rprev = None

    def laplacian(self, w):
        data = np.bincount(self.Linv, weights=self.Ls * w[self.Lb], minlength=self.Lnnz)
        return sp.csc_matrix((data, self.Lrows, self.Lptr), shape=(self.n, self.n))

    def solve(self, Rall, q0=None, tol=1e-11, maxit=80):
        """Rall: resistances of all passive branches; returns (Req, q_all)"""
        R = np.maximum(Rall[self.act], 1e-12)
        A = self.A
        if q0 is None:
            G = 1.0 / R
            p = splu(self.laplacian(G)).solve(self.s)
            q = G * (self.AT @ p)
        else:
            q = q0[self.act].copy()
            if self.Rprev is not None:
                # a branch whose resistance changed: start it at its old pressure drop
                ch = np.where(self.Rprev != R)[0]
                if len(ch):
                    q[ch] *= np.sqrt(self.Rprev[ch] / R[ch])
        self.Rprev = R.copy()
        p = None
        for it in range(maxit):
            aq = np.maximum(np.abs(q), 1e-7)
            D = 2.0 * R * aq
            f = R * q * np.abs(q)
            Dinv = 1.0 / D
            L = self.laplacian(Dinv)
            rhs = self.s - A @ q + A @ (Dinv * f)
            try:
                p = splu(L).solve(rhs)
            except Exception:
                L = L + sp.identity(self.n, format='csc') * 1e-12 * L.diagonal().max()
                p = splu(L).solve(rhs)
            qn = q + Dinv * (self.AT @ p - f)
            dq = np.max(np.abs(qn - q))
            q = qn
            if dq < tol:
                break
        Req = float(p[self.Tloc])
        qall = np.zeros(len(Rall))
        qall[self.act] = q
        # direct estimate of Req from dissipation (sum R|q|^3 = Req * 1^3)
        Req2 = float(np.sum(R * np.abs(q) ** 3))
        if np.isfinite(Req2) and Req2 > 0:
            Req = Req2
        return Req, qall


# ----------------------------------------------------------------------------
# fans

class Fan:
    def __init__(self, qs, ps, r):
        order = np.argsort(qs, kind='stable')
        qs = np.asarray(qs, float)[order]
        ps = np.asarray(ps, float)[order]
        self.qs, self.ps, self.r = qs, ps, float(r)
        pts = [qs[0]]
        for k in range(len(qs) - 1):
            a, b = qs[k], qs[k + 1]
            if b <= a:
                continue
            s = (ps[k + 1] - ps[k]) / (b - a)
            if self.r > 0:
                qe = s / (2 * self.r)
                if a + 1e-9 < qe < b - 1e-9:
                    pts.append(qe)
            pts.append(b)
        pts = np.array(pts)
        gv = self.g(pts)
        pieces = []
        start = 0
        sgn = 0
        for k in range(len(pts) - 1):
            d = np.sign(gv[k + 1] - gv[k])
            if d == 0:
                continue
            if sgn == 0:
                sgn = d
            elif d != sgn:
                pieces.append((start, k, sgn))
                start = k
                sgn = d
        pieces.append((start, len(pts) - 1, sgn))
        self.dec = []
        for (i0, i1, s) in pieces:
            if s < 0 and i1 > i0:
                self.dec.append((pts[i0:i1 + 1].copy(), gv[i0:i1 + 1].copy()))
        if not self.dec:
            raise ValueError('fan characteristic has no falling part')

    def P(self, q):
        return np.interp(q, self.qs, self.ps)

    def g(self, q):
        q = np.asarray(q, float)
        return self.P(q) - self.r * q * q

    def ghi(self, j):
        return self.dec[j][1][0]

    def glo(self, j):
        return self.dec[j][1][-1]

    def inv(self, j, H):
        bq, bg = self.dec[j]
        k = int(np.searchsorted(-bg, -H)) - 1
        k = min(max(k, 0), len(bq) - 2)
        q0 = bq[k]
        q1 = bq[k + 1]
        qm = 0.5 * (q0 + q1)
        jj = int(np.searchsorted(self.qs, qm)) - 1
        jj = min(max(jj, 0), len(self.qs) - 2)
        s = (self.ps[jj + 1] - self.ps[jj]) / (self.qs[jj + 1] - self.qs[jj])
        c0 = self.ps[jj] - s * self.qs[jj] - H
        r = self.r
        if r <= 0:
            q = -c0 / s if s != 0 else qm
        else:
            disc = max(s * s + 4 * r * c0, 0.0)
            q = (s + math.sqrt(disc)) / (2 * r)
        return min(max(q, q0), q1)


class FanSet:
    def __init__(self, fans):
        self.fans = fans
        self.rng = {}
        for c in itertools.product(*[range(len(f.dec)) for f in fans]):
            hi = min(f.ghi(j) for f, j in zip(fans, c))
            lo = max(f.glo(j) for f, j in zip(fans, c))
            lo = max(lo, 0.0)
            if lo >= hi:
                continue
            Qlo = self.Q(c, lo)
            Qhi = self.Q(c, hi)
            Rlo = lo / Qlo ** 2 if Qlo > 0 else float('inf')
            Rhi = hi / Qhi ** 2 if Qhi > 0 else float('inf')
            self.rng[c] = (lo, hi, Rlo, Rhi)

    def Q(self, c, H):
        return sum(f.inv(j, H) for f, j in zip(self.fans, c))

    def solve(self, c, R):
        lo, hi, Rlo, Rhi = self.rng[c]
        a, b = lo, hi
        for _ in range(200):
            m = 0.5 * (a + b)
            Qm = self.Q(c, m)
            if Qm > 0 and m / Qm ** 2 < R:
                a = m
            else:
                b = m
            if b - a < 1e-12 * max(1.0, hi):
                break
        H = 0.5 * (a + b)
        return H, np.array([f.inv(j, H) for f, j in zip(self.fans, c)])

    def stable(self, R):
        return [c for c, v in self.rng.items() if v[2] <= R <= v[3]]

    def nearest_stable(self, c, R):
        st = self.stable(R)
        if not st:
            # outside every branch (should not happen within VS-4 scope):
            # take the branch whose range is closest in log R
            best = None
            for cc, v in self.rng.items():
                dlt = 0.0
                if R < v[2]:
                    dlt = math.log(v[2] / max(R, 1e-300))
                elif R > v[3]:
                    dlt = math.log(R / v[3])
                key = (dlt, sum(abs(x - y) for x, y in zip(cc, c)))
                if best is None or key < best[0]:
                    best = (key, cc)
            return best[1]
        return min(st, key=lambda cc: (sum(abs(x - y) for x, y in zip(cc, c)), -sum(cc)))

    def move(self, c, R0, R1):
        """quasi-static change of the system resistance from R0 to R1"""
        if c not in self.rng:
            return self.nearest_stable(c, R1)
        for _ in range(4 * len(self.fans) + 4):
            lo, hi, Rlo, Rhi = self.rng[c]
            if Rlo <= R1 <= Rhi:
                return c
            c = list(c)
            if R1 > Rhi:
                Rnow = Rhi
                j = int(np.argmin([f.ghi(k) for f, k in zip(self.fans, c)]))
                c[j] -= 1
            else:
                Rnow = Rlo
                j = int(np.argmax([f.glo(k) for f, k in zip(self.fans, c)]))
                c[j] += 1
            c = tuple(c)
            if c not in self.rng:
                return self.nearest_stable(c, R1)
            v = self.rng[c]
            if not (v[2] * (1 - 1e-9) <= Rnow <= v[3] * (1 + 1e-9)):
                c = self.nearest_stable(c, Rnow)
        return self.nearest_stable(c, R1)


# ----------------------------------------------------------------------------

def main():
    pkg = sys.argv[1]
    out = sys.argv[2]
    pts = read_csv(pkg, 'points.csv')
    try:
        res = compute(pkg)
    except Exception as e:  # last resort: never leave without a result file
        sys.stderr.write('airflow: calculation failed: %r\n' % (e,))
        res = {}
    with open(out, 'w', newline='') as f:
        f.write('point,flow_m3_s\n')
        for p in pts:
            v = res.get(p['point'], 0.0)
            if not np.isfinite(v):
                v = 0.0
            f.write('%s,%.6f\n' % (p['point'], v))


def compute(pkg):
    dj = {}
    try:
        with open(os.path.join(pkg, 'district.json')) as f:
            dj = json.load(f)
    except Exception:
        pass
    allowance = int(fnum(dj.get('survey_allowance', 0), 0))
    br = read_csv(pkg, 'branches.csv')
    surveys = read_csv(pkg, 'surveys.csv')
    works = read_csv(pkg, 'work_log.csv')
    regs = read_csv(pkg, 'regulators.csv')
    doors = read_csv(pkg, 'doors.csv')
    fans_t = read_csv(pkg, 'fans.csv')
    curves = read_csv(pkg, 'fan_curves.csv')
    log = read_csv(pkg, 'log.csv')
    pts = read_csv(pkg, 'points.csv')

    names = [r['branch'] for r in br]
    nb = len(names)
    bidx = {n: i for i, n in enumerate(names)}
    kind = [r['kind'].lower() for r in br]
    item = [r.get('item', '') for r in br]
    nodes = sorted(set(r['from_node'] for r in br) | set(r['to_node'] for r in br))
    nidx = {n: i for i, n in enumerate(nodes)}
    nn = len(nodes)
    fi = np.array([nidx[r['from_node']] for r in br], dtype=int)
    ti = np.array([nidx[r['to_node']] for r in br], dtype=int)
    regR_reg = np.array([fnum(r.get('resistance_Ns2_m8', '')) for r in br])
    isair = np.array([k == 'airway' for k in kind])

    # ---------------- airway resistances -----------------
    changing = {}
    for w in works:
        if w.get('work', '').upper() == 'INSPECTED':
            continue
        b = w.get('branch', '')
        changing[b] = max(changing.get(b, ''), w.get('date', ''))
    sv_by = {}
    for s in surveys:
        dp = fnum(s.get('dp_Pa')); q = fnum(s.get('q_m3_s'))
        if not (np.isfinite(dp) and np.isfinite(q)) or q == 0:
            continue
        R = dp / (q * abs(q))
        if not (np.isfinite(R) and R > 0):
            continue
        sv_by.setdefault(s['branch'], []).append((s.get('date', ''), R, dp, q))
    for v in sv_by.values():
        v.sort(key=lambda x: x[0])

    Rbase = np.full(nb, np.nan)
    need = []          # airways needing a survey (no survey since work)
    weak = []          # airways whose survey on the day of the work may precede it
    stale = {}         # fall-back resistance for those
    for i in range(nb):
        if not isair[i]:
            continue
        n = names[i]
        lst = sv_by.get(n, [])
        W = changing.get(n, '')
        valid = [x for x in lst if x[0] > W] if W else list(lst)
        same = [x for x in lst if W and x[0] == W]
        before = [x for x in lst if W and x[0] < W]
        if not valid and same:
            Rs = same[-1][1]
            if before and abs(math.log(Rs / before[-1][1])) > 0.1:
                valid = same            # the survey shows the changed airway
            else:
                weak.append(n)
                stale[n] = Rs
                continue
        if not valid:
            need.append(n)
            if lst:
                stale[n] = lst[-1][1]
            continue
        RL = valid[-1][1]
        agree = [x[1] for x in valid if abs(math.log(x[1] / RL)) < 0.02]
        Rbase[i] = math.exp(sum(math.log(x) for x in agree) / len(agree))
    for i in range(nb):
        if kind[i] == 'stopping':
            Rbase[i] = regR_reg[i]
        elif kind[i] == 'fan':
            Rbase[i] = regR_reg[i] if np.isfinite(regR_reg[i]) else 0.0

    # ---------------- campaign check of stoppings and doors -----------------
    door_tab = {r['door']: (fnum(r['resistance_closed_Ns2_m8']), fnum(r['resistance_open_Ns2_m8'])) for r in doors}
    try:
        camp = campaign_check(surveys, names, kind, item, fi, ti, nn, Rbase, isair, door_tab)
    except Exception as e:
        dbg('campaign check failed', repr(e))
        camp = {}
    ZFLAG = 1.3
    flagged = [(n, v[1], v[2]) for n, v in camp.items() if v[0] > ZFLAG and kind[bidx[n]] == 'stopping']
    flagged_doors = [(n, v[1], v[2]) for n, v in camp.items() if v[0] > ZFLAG and kind[bidx[n]] == 'door']
    # stoppings leaking clearly less than built to: worth a survey, but the
    # campaign cannot give their resistance well
    tight = sorted([(v[1], n) for n, v in camp.items() if v[0] < -ZFLAG and kind[bidx[n]] == 'stopping'])
    near = sorted([(abs(v[0]), n) for n, v in camp.items() if 0.9 < abs(v[0]) <= ZFLAG and kind[bidx[n]] == 'stopping'], reverse=True)
    last_setting = {}
    for r in sorted(log, key=lambda r: r.get('time', '')):
        if r.get('item'):
            last_setting[r['item']] = (r.get('time', ''), r.get('setting', ''))

    # ---------------- fans -----------------
    fanb = [i for i in range(nb) if kind[i] == 'fan']
    fan_by_branch = {r.get('branch', ''): r for r in fans_t}
    fan_by_name = {r.get('fan', ''): r for r in fans_t}

    # ---------------- crew order -----------------
    order = []
    def add(n):
        if n in bidx and n not in order and len(order) < allowance:
            order.append(n)
    # airways with no survey since work: most important (largest flows first)
    def lastq(n):
        l = sv_by.get(n, [])
        return -abs(l[-1][3]) if l else 0.0
    for n in sorted(need, key=lastq):
        add(n)
    for n in sorted(weak, key=lastq):
        add(n)
    for n, excess, Rest in sorted(flagged, key=lambda x: -x[1]):
        add(n)
    for n, excess, Rest in sorted(flagged_doors, key=lambda x: -x[1]):
        if last_setting.get(item[bidx[n]], ('', ''))[1].lower().startswith('c'):
            add(n)
    for x, n in tight:
        add(n)
    for i in fanb:
        add(names[i])
    for z, n in near:
        add(n)
    crew = {}
    if order:
        crew = call_crew(pkg, order)
    dbg('need', need, 'weak', weak, 'flagged', flagged, 'doors', flagged_doors, 'tight', tight[:5], 'near', near[:5])
    dbg('order', order)
    dbg('crew', crew)
    for n, (dp, q) in crew.items():
        i = bidx.get(n)
        if i is None or q == 0:
            continue
        R = dp / (q * abs(q))
        if not (np.isfinite(R) and R > 0):
            continue
        if kind[i] in ('airway', 'stopping'):
            Rbase[i] = R
    for n, excess, Rest in flagged:
        i = bidx[n]
        if n not in crew and np.isfinite(Rest) and Rest > 0:
            Rbase[i] = Rest
    door_closed = {}
    for n, excess, Rest in flagged_doors:
        i = bidx[n]
        if n in crew:
            dp, q = crew[n]
            R = dp / (q * abs(q)) if q != 0 else float('nan')
            if np.isfinite(R) and R > 0:
                door_closed[item[i]] = R
                continue
        if np.isfinite(Rest) and Rest > 0:
            door_closed[item[i]] = Rest
    # an airway the crew could not survey: its last survey, scaled by the change
    # that work of the same kind made to airways surveyed before and after it
    ratios = {}
    for w in works:
        wk = w.get('work', '').upper()
        if wk == 'INSPECTED':
            continue
        lst = sv_by.get(w.get('branch', ''), [])
        bef = [x for x in lst if x[0] < w.get('date', '')]
        aft = [x for x in lst if x[0] > w.get('date', '')]
        if bef and aft:
            ratios.setdefault(wk, []).append(math.log(aft[0][1] / bef[-1][1]))
    allr = [x for v in ratios.values() for x in v]
    for n in need + weak:
        i = bidx[n]
        if not np.isfinite(Rbase[i]) and n in stale:
            wk = ''
            for w in works:
                if w.get('branch') == n and w.get('date', '') == changing.get(n):
                    wk = w.get('work', '').upper()
            known = ('RESUPPORTED', 'ENLARGED')
            lr = ratios.get(wk)
            if not lr and wk in known:
                lr = [x for k2 in known for x in ratios.get(k2, [])]
            if lr:
                fac = math.exp(sum(lr) / len(lr))
            else:
                fac = 0.17 if wk in known else 1.0
            Rbase[i] = stale[n] * fac
    # anything still unknown: median airway resistance
    good = Rbase[isair & np.isfinite(Rbase)]
    med = float(np.median(good)) if len(good) else 1.0
    for i in range(nb):
        if kind[i] != 'fan' and not (np.isfinite(Rbase[i]) and Rbase[i] > 0):
            if kind[i] in ('airway', 'stopping'):
                Rbase[i] = med

    # ---------------- settings -----------------
    reg_tab = {}
    for r in regs:
        reg_tab.setdefault(r['regulator'], []).append((fnum(r['setting']), fnum(r['resistance_Ns2_m8'])))
    for k in reg_tab:
        reg_tab[k].sort()
    for it, R in door_closed.items():
        if it in door_tab:
            door_tab[it] = (R, door_tab[it][1])

    def setting_R(it, v):
        v = (v or '').strip()
        if it in door_tab:
            c, o = door_tab[it]
            vl = v.lower()
            if vl.startswith('o'):
                return o
            if vl.startswith('c'):
                return c
            x = fnum(v)
            return o if (np.isfinite(x) and x > 0) else c
        if it in reg_tab:
            tab = reg_tab[it]
            x = fnum(v)
            if not np.isfinite(x):
                vl = v.lower()
                x = tab[-1][0] if vl.startswith('o') else tab[0][0]
            ss = np.array([a for a, _ in tab]); rr = np.array([b for _, b in tab])
            return float(np.exp(np.interp(x, ss, np.log(rr))))
        return float('nan')

    item_branches = {}
    for i in range(nb):
        if kind[i] in ('door', 'regulator') and item[i]:
            item_branches.setdefault(item[i], []).append(i)

    # ---------------- network -----------------
    pas = np.array([i for i in range(nb) if kind[i] != 'fan'], dtype=int)
    ppos = -np.ones(nb, dtype=int)
    ppos[pas] = np.arange(len(pas))
    F = fi[fanb[0]]
    T = ti[fanb[0]]
    net = Passive(nn, fi[pas], ti[pas], T, F)

    fans = []
    for i in fanb:
        fr = fan_by_branch.get(names[i]) or fan_by_name.get(item[i])
        model = fr.get('model', '')
        blade = fnum(fr.get('blade_setting', ''))
        cand = [c for c in curves if c.get('model', '') == model]
        blades = sorted(set(fnum(c.get('blade_setting', '')) for c in cand))
        if blade not in blades and blades:
            blade = min(blades, key=lambda x: abs(x - blade))
        cc = [c for c in cand if fnum(c.get('blade_setting', '')) == blade]
        qs = [fnum(c['flow_m3_s']) for c in cc]
        ps = [fnum(c['pressure_Pa']) for c in cc]
        fans.append(Fan(qs, ps, Rbase[i] if np.isfinite(Rbase[i]) else 0.0))
    FS = FanSet(fans)

    # ---------------- run through the log -----------------
    log_rows = [(r['time'], r['item'], r['setting']) for r in log if r.get('item')]
    log_rows.sort(key=lambda x: x[0])   # stable: file order within a time
    Rcur = Rbase[pas].copy()
    t0 = log_rows[0][0] if log_rows else ''

    def apply(it, v, Rv):
        val = setting_R(it, v)
        if not np.isfinite(val):
            return
        for i in item_branches.get(it, []):
            Rv[ppos[i]] = val

    li = 0
    while li < len(log_rows) and log_rows[li][0] == t0:
        apply(log_rows[li][1], log_rows[li][2], Rcur)
        li += 1
    # doors/regulators never in the log: closed / fully shut? use table default
    for i in pas:
        if not (np.isfinite(Rcur[ppos[i]]) and Rcur[ppos[i]] > 0):
            it = item[i]
            if it in door_tab:
                Rcur[ppos[i]] = door_tab[it][0]
            elif it in reg_tab:
                Rcur[ppos[i]] = reg_tab[it][-1][1]
            else:
                Rcur[ppos[i]] = med

    Req, q = net.solve(Rcur)
    seq = [Req]                       # Req after each state change
    ptimes = sorted(set(p['time'] for p in pts))
    snap = {}                         # point time -> (index into seq, unit flows)
    pj = 0
    while pj < len(ptimes) and ptimes[pj] <= t0:
        snap[ptimes[pj]] = (len(seq) - 1, q.copy()); pj += 1
    while li < len(log_rows):
        t = log_rows[li][0]
        while pj < len(ptimes) and ptimes[pj] < t:
            snap[ptimes[pj]] = (len(seq) - 1, q.copy()); pj += 1
        Rn = Rcur.copy()
        apply(log_rows[li][1], log_rows[li][2], Rn)
        li += 1
        if np.array_equal(Rn, Rcur):
            seq.append(Req)
            continue
        Rcur = Rn
        Req, q = net.solve(Rcur, q, tol=1e-10)
        seq.append(Req)
    while pj < len(ptimes):
        snap[ptimes[pj]] = (len(seq) - 1, q.copy()); pj += 1
    qfinal = q

    # ---------------- fan states -----------------
    init = FS.stable(seq[0])
    if not init:
        init = [FS.nearest_stable(tuple(len(f.dec) - 1 for f in fans), seq[0])]
    trajs = []
    for c0 in init:
        tr = [c0]
        c = c0
        for k in range(1, len(seq)):
            c = FS.move(c, seq[k - 1], seq[k])
            tr.append(c)
        trajs.append(tr)
    # distinct trajectories?
    uniq = []
    for tr in trajs:
        if tr not in uniq:
            uniq.append(tr)
    if len(uniq) == 1:
        traj = uniq[0]
    else:
        traj = None
        uniq.sort(key=lambda tr: -sum(tr[0]))   # normal running first
        if crew:
            best = None
            for tr in uniq:
                c = tr[-1]
                H, qf = FS.solve(c, seq[-1])
                Qt = qf.sum()
                err = 0.0
                for n, (dp, qm) in crew.items():
                    i = bidx.get(n)
                    if i is None:
                        continue
                    if kind[i] == 'fan':
                        qp = qf[fanb.index(i)]
                    else:
                        qp = Qt * qfinal[ppos[i]]
                    err += ((qp - qm) / max(abs(qm), 1.0)) ** 2
                if best is None or err < 0.5 * best[0]:
                    best = (err, tr)
            traj = best[1]
        if traj is None:
            # no evidence: the fans running on their normal (highest-flow) branches
            traj = max(uniq, key=lambda tr: sum(tr[0]))

    dbg('initial Req %.6g stable %s, %d distinct trajectories' % (seq[0], init, len(uniq)))
    dbg('fan ranges', FS.rng)
    jumps = [(k, traj[k - 1], traj[k], seq[k - 1], seq[k]) for k in range(1, len(seq)) if traj[k] != traj[k - 1]]
    dbg('jumps', len(jumps), jumps[:6])
    # margins: closest approach of Req to the end of the current branch
    marg = []
    for k in range(len(seq)):
        v = FS.rng[traj[k]]
        marg.append(min(abs(math.log(seq[k] / v[2])) if v[2] > 0 else 9, abs(math.log(v[3] / seq[k]))))
    dbg('min log-margin to a fold %.4f' % min(marg))

    # ---------------- results -----------------
    res = {}
    cache = {}
    for p in pts:
        t = p['time']
        if t not in snap:
            continue
        k, qu = snap[t]
        key = (t,)
        if key not in cache:
            c = traj[k]
            H, qf = FS.solve(c, seq[k])
            cache[key] = (qf.sum(), qf)
        Qt, qf = cache[key]
        i = bidx.get(p['branch'])
        if i is None:
            continue
        if kind[i] == 'fan':
            res[p['point']] = float(qf[fanb.index(i)])
        else:
            res[p['point']] = float(Qt * qu[ppos[i]])
    return res


def dbg(*a):
    if os.environ.get('AIRFLOW_DEBUG'):
        sys.stderr.write(' '.join(str(x) for x in a) + '\n')


def call_crew(pkg, order):
    out = {}
    try:
        r = subprocess.run(['pqsurvey', pkg] + list(order), capture_output=True, text=True, timeout=20)
    except Exception as e:
        sys.stderr.write('airflow: survey order failed: %r\n' % (e,))
        return out
    if r.returncode != 0:
        sys.stderr.write('airflow: survey crew: %s\n' % (r.stdout + r.stderr).strip())
    for line in r.stdout.splitlines():
        parts = [x.strip() for x in line.split(',')]
        if len(parts) < 3 or parts[0] == 'branch':
            continue
        dp = fnum(parts[1]); q = fnum(parts[2])
        if np.isfinite(dp) and np.isfinite(q):
            out[parts[0]] = (dp, q)
    return out


def campaign_check(surveys, names, kind, item, fi, ti, nn, Rbase, isair, door_tab):
    """Leakage of stoppings and closed doors in the survey campaigns.

    A campaign surveys every airway while the regulators and doors stand still,
    each panel on a day of its own, so at a node where every other branch is an
    airway surveyed that day the flow through a stopping follows from the
    balance of flows, and the pressure across it from the pressure drops along
    the airways surveyed that day.  The latest day that shows a stopping counts.  Readings are within 0.3 %,
    which bounds the error of the balance.  Returns {name: (z, excess, R_est)}
    with z the excess leakage over that bound."""
    nb = len(names)
    # one day of a campaign is one steady state (the settings stand still and a
    # panel is surveyed on a day of its own): check each survey day by itself
    groups = [[d] for d in sorted(set(s.get('date', '') for s in surveys if s.get('date')))]
    bidx = {n: i for i, n in enumerate(names)}
    inc = [[] for _ in range(nn)]
    for i in range(nb):
        if fi[i] != ti[i]:
            inc[fi[i]].append((i, 1.0))
            inc[ti[i]].append((i, -1.0))
    result = {}
    byday = {}
    for s in surveys:
        byday.setdefault(s.get('date', ''), []).append(s)
    for g in groups:
        gs = set(g)
        q = np.full(nb, np.nan); dp = np.full(nb, np.nan); day = [''] * nb
        for s in byday.get(g[0], []):
            if s.get('branch') in bidx:
                i = bidx[s['branch']]
                if isair[i] and s['date'] >= day[i]:
                    q[i] = fnum(s.get('q_m3_s')); dp[i] = fnum(s.get('dp_Pa')); day[i] = s['date']
        meas = np.isfinite(q) & np.isfinite(dp) & isair
        if meas.sum() < 3:
            continue
        mi = np.where(meas)[0]
        G = sp.csr_matrix((np.ones(len(mi)), (fi[mi], ti[mi])), shape=(nn, nn))
        nc, lab = connected_components(G, directed=False)
        refs = set(); seen = set()
        for n in range(nn):
            if lab[n] not in seen:
                seen.add(lab[n]); refs.add(n)
        cols = np.array([n for n in range(nn) if n not in refs], dtype=int)
        cpos = -np.ones(nn, dtype=int); cpos[cols] = np.arange(len(cols))
        rows = []; cc = []; vv = []
        for k, i in enumerate(mi):
            if cpos[fi[i]] >= 0:
                rows.append(k); cc.append(cpos[fi[i]]); vv.append(1.0)
            if cpos[ti[i]] >= 0:
                rows.append(k); cc.append(cpos[ti[i]]); vv.append(-1.0)
        M = sp.csr_matrix((vv, (rows, cc)), shape=(len(mi), len(cols)))
        try:
            from scipy.sparse.linalg import lsqr
            sol = lsqr(M, dp[mi], atol=1e-14, btol=1e-14, iter_lim=50000)[0]
        except Exception:
            continue
        pot = np.zeros(nn); pot[cols] = sol
        for i in range(nb):
            if kind[i] not in ('stopping', 'door') or lab[fi[i]] != lab[ti[i]]:
                continue
            est = []; bnd = []
            for n, sg0 in ((fi[i], 1.0), (ti[i], -1.0)):
                others = [(j, sg) for j, sg in inc[n] if j != i]
                if others and all(meas[j] for j, _ in others):
                    tot = sum(sg * q[j] for j, sg in others)
                    est.append(-tot / sg0)
                    bnd.append(0.003 * sum(abs(q[j]) for j, _ in others))
            if not est:
                continue
            x = sum(est) / len(est); B = sum(bnd) / len(bnd) + 0.01
            dP = pot[fi[i]] - pot[ti[i]]
            Rest = abs(dP) / (x * x) if x != 0 else float('nan')
            if kind[i] == 'stopping':
                Rr = Rbase[i]
            else:
                c, o = door_tab.get(item[i], (float('nan'), float('nan')))
                if not (np.isfinite(c) and np.isfinite(o)):
                    continue
                po = math.sqrt(abs(dP) / o) if o > 0 else float('inf')
                if abs(x) > 0.5 * po:
                    continue        # the door stood open
                Rr = c
            if not (np.isfinite(Rr) and Rr > 0):
                result[names[i]] = (1e9, 1e9, Rest)
                continue
            pred = math.sqrt(abs(dP) / Rr)
            excess = abs(x) - pred
            result[names[i]] = (excess / B, excess, Rest)   # days in order: latest kept
    return result


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write('airflow: %r\n' % (e,))
    sys.exit(0)
