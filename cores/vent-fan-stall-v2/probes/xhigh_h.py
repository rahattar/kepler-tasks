#!/usr/bin/env python3
"""Airflow at every survey point of a district package, to VS-4.

    python3 airflow.py PACKAGE_DIR OUT_CSV

Outline
  1. Resistances (VS-4 s.3): airways from their latest survey; airways re-supported
     or enlarged since that survey, and stoppings whose leakage in the survey
     campaigns does not match the register, are surveyed again with the one
     `pqsurvey` order the package allows (district_package.md).
  2. Network (VS-4 s.2): apart from the main fans, which stand in parallel at the
     fan house (VS-4 s.1), every branch obeys dp = R q|q|.  The rest of the
     district is therefore one square-law two-terminal network: for total flow Q
     its branch flows are Q times the unit-flow solution and its pressure drop is
     Rs Q^2.  The unit-flow solution is found by minimising the network content.
  3. Fans (VS-4 s.4, s.5): the catalogue characteristics have a stall dip, so the
     fans can have several steady operating points.  Settings change slowly and
     the air follows, so the operating point is followed quasi-statically from the
     opening of the record; where the operating point it is on ceases to exist
     (or becomes unstable) the fans move, by their own dynamics, to another
     stable operating point.
"""
import bisect
import csv
import json
import os
import subprocess
import sys

import numpy as np

SURVEY_REL = 0.003          # a survey reads dp and q each within 0.3 per cent
WORK_CHANGES = ('RESUPPORTED', 'ENLARGED')
WORK_RATIO = 0.61           # resistance after such work / before, as seen in the records


# ----------------------------------------------------------------------------- input
def read_csv(path):
    with open(path, newline='') as f:
        return [{k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
                for r in csv.DictReader(f)]


def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


class Package:
    def __init__(self, d):
        self.dir = d
        self.district = json.load(open(os.path.join(d, 'district.json')))
        self.allowance = int(self.district.get('survey_allowance', 0) or 0)
        self.branches = read_csv(os.path.join(d, 'branches.csv'))
        self.surveys = read_csv(os.path.join(d, 'surveys.csv'))
        self.work = read_csv(os.path.join(d, 'work_log.csv'))
        self.regs = read_csv(os.path.join(d, 'regulators.csv'))
        self.doors = read_csv(os.path.join(d, 'doors.csv'))
        self.fans = read_csv(os.path.join(d, 'fans.csv'))
        self.curves = read_csv(os.path.join(d, 'fan_curves.csv'))
        self.log = read_csv(os.path.join(d, 'log.csv'))
        self.points = read_csv(os.path.join(d, 'points.csv'))


# ----------------------------------------------------------------------------- network
class Network:
    def __init__(self, pk):
        br = pk.branches
        self.names = [b['branch'] for b in br]
        self.bidx = {n: i for i, n in enumerate(self.names)}
        self.kind = [b['kind'].lower() for b in br]
        self.item = [b.get('item', '') or '' for b in br]
        self.reg_R = [fnum(b.get('resistance_Ns2_m8')) for b in br]
        self.frm = [b['from_node'] for b in br]
        self.to = [b['to_node'] for b in br]
        nodes = sorted(set(self.frm) | set(self.to))
        self.nodes = nodes
        self.nidx = {n: i for i, n in enumerate(nodes)}
        self.fan_br = [i for i, k in enumerate(self.kind) if k == 'fan']
        self.pas = np.array([i for i, k in enumerate(self.kind) if k != 'fan'])
        if not self.fan_br:
            raise SystemExit('no fan in the district')
        fx = {self.frm[i] for i in self.fan_br}
        fy = {self.to[i] for i in self.fan_br}
        if len(fx) != 1 or len(fy) != 1:
            raise SystemExit('fans do not stand in parallel at one fan house')
        self.X = self.nidx[fx.pop()]       # fan house (fan inlet side)
        self.Y = self.nidx[fy.pop()]       # fan outlet side (surface)
        nn = len(nodes)
        # incidence of the passive branches, rows for every node but Y
        rows = [n for n in range(nn) if n != self.Y]
        self.rows = rows
        rpos = {n: k for k, n in enumerate(rows)}
        A = np.zeros((len(rows), len(self.pas)))
        for j, b in enumerate(self.pas):
            f, t = self.nidx[self.frm[b]], self.nidx[self.to[b]]
            if f in rpos:
                A[rpos[f], j] += 1.0
            if t in rpos:
                A[rpos[t], j] -= 1.0
        self.A = A
        b = np.zeros(len(rows))
        b[rpos[self.X]] = -1.0             # unit flow arrives at the fan house
        self.b = b
        # tables
        self.regt = {}
        for r in pk.regs:
            self.regt[(r['regulator'], int(round(float(r['setting']))))] = float(r['resistance_Ns2_m8'])
        self.doort = {r['door']: (float(r['resistance_closed_Ns2_m8']), float(r['resistance_open_Ns2_m8']))
                      for r in pk.doors}
        # fan curves
        fans = {f['branch']: f for f in pk.fans}
        self.curves = []
        for i in self.fan_br:
            f = fans.get(self.names[i])
            if f is None:   # fan given by item name
                f = next(ff for ff in pk.fans if ff['fan'] == self.item[i])
            pts = [(float(c['flow_m3_s']), float(c['pressure_Pa'])) for c in pk.curves
                   if c['model'] == f['model'] and float(c['blade_setting']) == float(f['blade_setting'])]
            pts.sort()
            x = np.array([p[0] for p in pts])
            p = np.array([p[1] for p in pts])
            rd = self.reg_R[i] or 0.0
            self.curves.append((x, p, rd))
        self._q0 = None

    def resistances(self, base, settings):
        R = np.array(base, dtype=float)
        for i, k in enumerate(self.kind):
            if k == 'regulator':
                s = settings[self.item[i]]
                R[i] = self.reg_value(self.item[i], s)
            elif k == 'door':
                s = str(settings[self.item[i]]).lower()
                R[i] = self.doort[self.item[i]][0 if s.startswith('c') else 1]
        return R

    def reg_value(self, reg, s):
        v = float(s)
        if abs(v - round(v)) < 1e-9 and (reg, int(round(v))) in self.regt:
            return self.regt[(reg, int(round(v)))]
        # between tabulated settings: geometric interpolation
        ks = sorted(k for (r, k) in self.regt if r == reg)
        lo = max([k for k in ks if k <= v], default=ks[0])
        hi = min([k for k in ks if k >= v], default=ks[-1])
        if lo == hi:
            return self.regt[(reg, lo)]
        a, b = self.regt[(reg, lo)], self.regt[(reg, hi)]
        w = (v - lo) / (hi - lo)
        return float(np.exp(np.log(a) * (1 - w) + np.log(b) * w))

    def passive(self, R, q0=None):
        """Unit flow through the passive network from the surface side to the fan
        house.  Returns (Rs, q) with q the flow in every branch (fans 0)."""
        A, b = self.A, self.b
        Rp = R[self.pas]
        if q0 is None:
            q0 = self._q0
        if q0 is not None and len(q0) == len(self.names):
            q0 = q0[self.pas]
        if q0 is None:
            q = np.linalg.lstsq(A, b, rcond=None)[0]
        else:
            q = q0 + np.linalg.lstsq(A, b - A @ q0, rcond=None)[0]
        scale = 1.0
        f = lambda v: float(np.sum(Rp * np.abs(v) ** 3)) / 3.0
        fq = f(q)
        for _ in range(100):
            g = Rp * q * np.abs(q)
            h = 2.0 * Rp * np.maximum(np.abs(q), 1e-7 * scale)
            hi = 1.0 / h
            S = (A * hi) @ A.T
            r = b - A @ q
            rhs = -(A @ (hi * g)) - r
            try:
                lam = np.linalg.solve(S, rhs)
            except np.linalg.LinAlgError:
                lam = np.linalg.lstsq(S, rhs, rcond=None)[0]
            dq = -hi * (g + A.T @ lam)
            t = 1.0
            slope = float(g @ dq)
            while t > 1e-10:
                qn = q + t * dq
                fn = f(qn)
                if fn <= fq + 1e-4 * t * slope + 1e-15 * abs(fq):
                    break
                t *= 0.5
            q, fq = qn, fn
            if np.max(np.abs(t * dq)) < 1e-11:
                break
        self._q0 = q.copy()
        Rs = float(np.sum(Rp * np.abs(q) ** 3))
        full = np.zeros(len(self.names))
        full[self.pas] = q
        return Rs, full


# ----------------------------------------------------------------------------- fans
class Fans:
    """Main fans in parallel.  Fan i delivers h = F_i(q_i) = P_i(q_i) - Rd_i q_i|q_i|;
    the rest of the district needs h = Rs Q|Q|, Q = sum q_i.  The flow follows
    M dq/dt = G(q), G_i = F_i(q_i) - Rs Q|Q|, a gradient system whose stable steady
    states are the local maxima of V = sum int F_i - Rs |Q|^3 / 3; it is stable
    exactly where the Jacobian H = diag(F_i') - 2 Rs |Q| is negative definite,
    whatever the inertances M."""

    def __init__(self, curves):
        self.c = curves
        self.n = len(curves)
        self.qmax = np.array([c[0][-1] for c in curves])
        self.seg = []
        for x, p, rd in curves:
            xs = [float(v) for v in x]
            ps = [float(v) for v in p]
            sl = [(ps[j + 1] - ps[j]) / (xs[j + 1] - xs[j]) for j in range(len(xs) - 1)]
            self.seg.append((xs, ps, sl, float(rd)))
        L = np.full(self.n, 10.0)
        self.M = np.diag(L) + 100.0
        self.Minv = np.linalg.inv(self.M)

    def _fd(self, q):
        F = np.empty(self.n)
        D = np.empty(self.n)
        for k in range(self.n):
            xs, ps, sl, rd = self.seg[k]
            qi = float(q[k])
            j = bisect.bisect_right(xs, qi) - 1
            if j < 0:
                j = 0
            elif j > len(sl) - 1:
                j = len(sl) - 1
            if qi <= xs[0]:
                P = ps[0]
            elif qi >= xs[-1]:
                P = ps[-1]
            else:
                P = ps[j] + sl[j] * (qi - xs[j])
            F[k] = P - rd * qi * abs(qi)
            D[k] = sl[j] - 2.0 * rd * abs(qi)
        return F, D

    def F(self, q):
        return self._fd(q)[0]

    def G(self, q, Rs):
        Q = float(q.sum())
        return self._fd(q)[0] - Rs * Q * abs(Q)

    def GH(self, q, Rs):
        F, D = self._fd(q)
        Q = float(q.sum())
        return F - Rs * Q * abs(Q), np.diag(D) - 2.0 * Rs * abs(Q)

    def H(self, q, Rs):
        return self.GH(q, Rs)[1]

    def stable(self, q, Rs):
        # negative definite Jacobian, on both sides of a kink of the characteristic
        for qq in (q, q - 1e-7):
            if np.max(np.linalg.eigvalsh(self.H(qq, Rs))) >= 0:
                return False
        return True

    def newton(self, q, Rs, maxit=30):
        q = q.copy()
        for _ in range(maxit):
            g, H = self.GH(q, Rs)
            if np.max(np.abs(g)) < 1e-8 * max(1.0, float(np.max(np.abs(g + Rs * q.sum() ** 2)))):
                return q, True
            try:
                dq = -np.linalg.solve(H, g)
            except np.linalg.LinAlgError:
                return q, False
            if not np.all(np.isfinite(dq)):
                return q, False
            q = q + dq
        g = self.G(q, Rs)
        return q, bool(np.max(np.abs(g)) < 1e-5)

    def settle(self, q, Rs, maxsteps=200000):
        """Let the fan flows evolve at fixed Rs until they come to rest
        (explicit RK4 on M dq/dt = G, steps limited by stiffness and size)."""
        q = q.copy()
        Minv = self.Minv
        dt = 0.01
        dmax = 0.5
        for it in range(maxsteps):
            g, H = self.GH(q, Rs)
            if np.max(np.abs(g)) < 5.0:
                q2, ok = self.newton(q, Rs)
                if ok and np.max(np.abs(q2 - q)) < 1.0 and self.stable(q2, Rs):
                    return q2
            rho = float(np.max(np.abs(np.linalg.eigvals(Minv @ H))))
            dt = min(dt * 1.5, 0.5 / max(rho, 1e-12))
            while True:
                k1 = Minv @ g
                k2 = Minv @ self.G(q + 0.5 * dt * k1, Rs)
                k3 = Minv @ self.G(q + 0.5 * dt * k2, Rs)
                k4 = Minv @ self.G(q + dt * k3, Rs)
                dq = dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
                if float(np.max(np.abs(dq))) > dmax and dt > 1e-9:
                    dt *= 0.5
                    continue
                break
            q = q + dq
        raise RuntimeError('fan flow did not settle')

    def follow(self, q, Rs0, Rs1):
        """Quasi-static change of the district's resistance from Rs0 to Rs1: the fans
        stay on their operating branch while it exists and is stable."""
        if Rs1 == Rs0:
            return q
        L0, L1 = np.log(Rs0), np.log(Rs1)
        direction = 1.0 if L1 > L0 else -1.0
        L = L0
        h = 0.02
        while (L1 - L) * direction > 1e-12:
            Ln = L + direction * min(h, abs(L1 - L))
            Rs, Rn = np.exp(L), np.exp(Ln)
            # predictor: tangent of the branch, dG/dRs = -Q|Q|
            g, H = self.GH(q, Rs)
            Q = float(q.sum())
            try:
                dqdR = np.linalg.solve(H, np.full(self.n, Q * abs(Q)))
            except np.linalg.LinAlgError:
                dqdR = np.zeros(self.n)
            qp = q + dqdR * (Rn - Rs)
            q2, ok = self.newton(qp, Rn)
            okc = ok and np.max(np.abs(q2 - qp)) < 0.2 + 0.25 * float(np.max(np.abs(qp - q))) \
                and np.max(np.abs(q2 - q)) < 0.05 * float(np.max(self.qmax)) and self.stable(q2, Rn)
            if okc:
                q, L = q2, Ln
                h = min(h * 1.5, 0.1)
            elif h > 2e-5:
                h *= 0.25
            else:
                # the branch ends here: the fans move to another operating point
                # while the district's resistance carries on changing
                L = L + direction * min(0.01, abs(L1 - L))
                qs = q.copy()
                qs[-1] -= 1e-6 * self.qmax[-1]      # (breaks the tie between identical fans)
                q = self.settle(qs, np.exp(L))
                h = 0.02
        return q

    def equilibria(self, Rs):
        """Stable operating points at Rs, found by letting the fans settle from a
        spread of starting flows; largest total flow first."""
        import itertools
        found = []
        fr = [0.15, 0.4, 0.6, 0.8, 0.97] if self.n <= 3 else [0.3, 0.97]
        for combo in itertools.product(fr, repeat=self.n):
            try:
                e = self.settle(np.array(combo) * self.qmax, Rs)
            except RuntimeError:
                continue
            if not any(np.max(np.abs(e - f)) < 0.5 for f in found):
                found.append(e)
        found.sort(key=lambda v: -v.sum())
        return found

    def start(self, Rs):
        """Operating point as the record opens: the fans brought up to their
        normal (largest-flow) operating point."""
        return self.settle(0.97 * self.qmax, Rs)


# ----------------------------------------------------------------------------- resistances
def survey_R(dp, q):
    return dp / (q * abs(q))


def campaigns(surveys):
    """Group survey dates into campaigns (consecutive days)."""
    import datetime as dt
    ds = sorted({s['date'] for s in surveys})
    if not ds:
        return []
    groups, cur = [], [ds[0]]
    for a, b in zip(ds, ds[1:]):
        da = dt.date.fromisoformat(a)
        db = dt.date.fromisoformat(b)
        if (db - da).days <= 3:
            cur.append(b)
        else:
            groups.append(cur)
            cur = [b]
    groups.append(cur)
    return groups


def stopping_check(pk, net):
    """Leakage of each stopping in each survey campaign, from the airway readings:
    flow by balance at the nodes, pressure difference along surveyed airways.
    Returns {branch: dict(z=..., R_est=..., n=...)} for stoppings that can be checked."""
    nodes, nidx = net.nodes, net.nidx
    out = {}
    per = {}
    for g in campaigns(pk.surveys):
        gs = set(g)
        last = {}
        for s in sorted((s for s in pk.surveys if s['date'] in gs), key=lambda s: s['date']):
            last[s['branch']] = s
        air = [i for i, n in enumerate(net.names) if n in last and net.kind[i] == 'airway']
        if not air:
            continue
        other = [i for i in range(len(net.names)) if i not in set(air)]
        nn = len(nodes)
        # node balance: sum over branches of outflow = 0, unknown flows in `other`
        Mo = np.zeros((nn, len(other)))
        for j, i in enumerate(other):
            Mo[nidx[net.frm[i]], j] += 1
            Mo[nidx[net.to[i]], j] -= 1
        B = np.zeros((nn, len(air)))
        qa = np.zeros(len(air))
        A = np.zeros((len(air), nn))
        dpa = np.zeros(len(air))
        for k, i in enumerate(air):
            s = last[net.names[i]]
            B[nidx[net.frm[i]], k] += 1
            B[nidx[net.to[i]], k] -= 1
            qa[k] = float(s['q_m3_s'])
            dpa[k] = float(s['dp_Pa'])
            A[k, nidx[net.frm[i]]] = 1
            A[k, nidx[net.to[i]]] = -1
        keep = [n for n in range(nn) if nodes[n] != nodes[net.Y]]
        M = Mo[keep]
        Mp = np.linalg.pinv(M)
        qo = -Mp @ (B[keep] @ qa)
        # identifiable flows
        U, S, Vt = np.linalg.svd(M)
        rank = int(np.sum(S > 1e-9 * max(1.0, S.max())))
        null = Vt[rank:]
        ident = np.all(np.abs(null) < 1e-8, axis=0) if len(null) else np.ones(len(other), bool)
        sens = -Mp @ B[keep]                     # d qo / d qa
        sq = np.sqrt((sens ** 2) @ ((SURVEY_REL / np.sqrt(3) * qa) ** 2))
        # pressures from airway readings, per connected component
        p = np.linalg.lstsq(A, dpa, rcond=None)[0]
        parent = list(range(nn))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for i in air:
            ra, rb = find(nidx[net.frm[i]]), find(nidx[net.to[i]])
            parent[ra] = rb
        for j, i in enumerate(other):
            if net.kind[i] != 'stopping' or not ident[j]:
                continue
            f, t = nidx[net.frm[i]], nidx[net.to[i]]
            if find(f) != find(t):
                continue
            dp = p[f] - p[t]
            Rr = net.reg_R[i]
            if abs(dp) < 1e-9:
                continue
            # (a stopping with no resistance in the register is always estimated)
            qpred = np.sign(dp) * np.sqrt(abs(dp) / Rr) if Rr and Rr > 0 else 0.0
            sig = max(float(sq[j]), 1e-3)
            per.setdefault(net.names[i], []).append(dict(date=g[-1], dp=dp, q=float(qo[j]), qpred=qpred, sig=sig))
    for b, lst in per.items():
        lst.sort(key=lambda d: d['date'])
        z = [(d['q'] - d['qpred']) / d['sig'] for d in lst]
        latest = lst[-1]
        zl = z[-1]
        zc = sum(z) / np.sqrt(len(z))
        # leak coefficient k = q / sqrt|dp| (R = 1/k^2); combine campaigns consistent with the latest
        ks = [d['q'] / np.sqrt(abs(d['dp'])) * np.sign(d['dp']) for d in lst]
        ksig = [d['sig'] / np.sqrt(abs(d['dp'])) for d in lst]
        sel = [k for k, s in zip(ks, ksig) if abs(k - ks[-1]) < 3 * np.hypot(s, ksig[-1])]
        w = [1 / s ** 2 for k, s in zip(ks, ksig) if abs(k - ks[-1]) < 3 * np.hypot(s, ksig[-1])]
        kest = sum(k * ww for k, ww in zip(sel, w)) / sum(w)
        Rest = 1.0 / kest ** 2 if kest > 0 else None
        out[b] = dict(z_latest=zl, z_comb=zc, R_est=Rest, n=len(lst), excess=latest['q'] - latest['qpred'],
                      leak=latest['q'])
    return out


def plan(pk, net):
    """Resistances from the records and the survey order to place."""
    lat = {}
    for s in sorted(pk.surveys, key=lambda s: s['date']):
        q = fnum(s['q_m3_s'])
        dp = fnum(s['dp_Pa'])
        if q is None or dp is None or q == 0:
            continue
        lat[s['branch']] = (s['date'], survey_R(dp, q))
    work = {}
    for w in pk.work:
        if w['work'].strip().upper() in WORK_CHANGES:
            work[w['branch']] = max(work.get(w['branch'], ''), w['date'])
    base = [0.0] * len(net.names)
    must, sameday = [], []      # airways needing a survey
    unknown_air = {}
    for i, n in enumerate(net.names):
        k = net.kind[i]
        if k == 'airway':
            if n in lat:
                d, R = lat[n]
                base[i] = R
                wd = work.get(n)
                if wd is not None and wd > d:
                    must.append(n)
                    unknown_air[n] = R
                elif wd is not None and wd == d:
                    sameday.append(n)
            else:
                must.append(n)
                unknown_air[n] = None
        elif k in ('stopping', 'fan'):
            base[i] = net.reg_R[i] or 0.0
    # airways never surveyed: placeholder from the other airways (replaced by the survey)
    known = [base[i] for i, n in enumerate(net.names) if net.kind[i] == 'airway' and n in lat]
    med = float(np.median(known)) if known else 0.01
    for n, R in unknown_air.items():
        i = net.bidx[n]
        base[i] = med if R is None else R
    # stoppings whose campaign leakage contradicts the register
    st = stopping_check(pk, net)
    bad = []
    for b, d in st.items():
        if (abs(d['z_latest']) > 4.5 or abs(d['z_comb']) > 5.0) and d['R_est']:
            bad.append((abs(d['excess']), b))
            base[net.bidx[b]] = d['R_est']
    bad.sort(reverse=True)
    # stoppings with no resistance in the register and none from the campaigns
    regd = [net.reg_R[i] for i, k in enumerate(net.kind) if k == 'stopping' and net.reg_R[i]]
    for i, k in enumerate(net.kind):
        if k == 'stopping' and not base[i] > 0:
            base[i] = float(np.median(regd)) if regd else 2500.0
            bad.append((0.0, net.names[i]))
    for i, k in enumerate(net.kind):
        if k == 'airway' and not base[i] > 0:
            base[i] = med
    return base, must, sameday, [b for _, b in bad], unknown_air


def impact(net, base, settings, names):
    """Largest relative change of any branch flow when a branch's resistance halves."""
    R = net.resistances(base, settings)
    Rs0, q0 = net.passive(R)
    out = {}
    for n in names:
        R2 = R.copy()
        R2[net.bidx[n]] *= 0.5
        Rs1, q1 = net.passive(R2, q0)
        m = np.max(np.abs(q1 - q0) / np.maximum(np.abs(q0), 1e-3)) + abs(np.log(Rs1 / Rs0))
        out[n] = float(m)
    net._q0 = q0
    return out


def order_survey(pkdir, names):
    if not names:
        return {}
    try:
        r = subprocess.run(['pqsurvey', pkdir] + list(names), capture_output=True, text=True, timeout=60)
    except Exception as e:
        sys.stderr.write('survey order failed: %s\n' % e)
        return {}
    if r.returncode != 0:
        sys.stderr.write('survey order refused: %s %s\n' % (r.stdout.strip(), r.stderr.strip()))
        return {}
    out = {}
    for row in csv.DictReader(r.stdout.strip().splitlines()):
        try:
            out[row['branch'].strip()] = (float(row['dp_Pa']), float(row['q_m3_s']))
        except (KeyError, ValueError, AttributeError):
            pass
    return out



def infer(net, fans, base, settings, last_state, surveyed, prior, meas_sd=0.004):
    """Resistances of airways the crew could not take, fitted to the crew's flow
    readings of the district as it stands now (linearised Bayesian update)."""
    names = list(prior)
    obs = [(n, float(np.log(abs(q)))) for n, (dp, q) in surveyed.items()
           if n in net.bidx and abs(q) > 0.05]
    if not obs:
        return None
    mu = np.array([prior[n][0] for n in names])
    sd = np.array([prior[n][1] for n in names])
    q_last = last_state[3]

    def predict(theta):
        b = list(base)
        for n, t in zip(names, theta):
            b[net.bidx[n]] = float(np.exp(t))
        Rs, qu = net.passive(net.resistances(b, settings))
        qf, ok = fans.newton(q_last, Rs)
        if not ok:
            qf = fans.settle(q_last, Rs)
        v = qf.sum() * qu
        for k, i in enumerate(net.fan_br):
            v[i] = qf[k]
        return np.array([np.log(max(abs(v[net.bidx[n]]), 1e-9)) for n, _ in obs])
    y = np.array([o[1] for o in obs])
    theta = mu.copy()
    for _ in range(4):
        p0 = predict(theta)
        J = np.zeros((len(obs), len(names)))
        for j in range(len(names)):
            t2 = theta.copy()
            t2[j] += 0.02
            J[:, j] = (predict(t2) - p0) / 0.02
        A = J.T @ J / meas_sd ** 2 + np.diag(1.0 / sd ** 2)
        g = J.T @ (y - p0) / meas_sd ** 2 - (theta - mu) / sd ** 2
        step = np.linalg.solve(A, g)
        theta = np.clip(theta + step, mu - 3 * sd, mu + 3 * sd)
        if np.max(np.abs(step)) < 1e-3:
            break
    b = list(base)
    for n, t in zip(names, theta):
        b[net.bidx[n]] = float(np.exp(t))
    log('fitted: %s' % {n: round(float(np.exp(t)), 6) for n, t in zip(names, theta)})
    return b

# ----------------------------------------------------------------------------- record
def log_events(pk, net):
    rows = sorted(pk.log, key=lambda r: r['time'])
    first = rows[0]['time']
    init = {r['item']: r['setting'] for r in rows if r['time'] == first}
    ev = [(r['time'], r['item'], r['setting']) for r in rows if r['time'] != first]
    for i, k in enumerate(net.kind):
        it = net.item[i]
        if k not in ('regulator', 'door') or it in init:
            continue
        later = [s for t, x, s in ev if x == it]
        if k == 'door':
            init[it] = ('closed' if later[0].lower().startswith('o') else 'open') if later else 'closed'
        else:
            init[it] = later[0] if later else '10'
        log('no opening setting for %s, taken as %s' % (it, init[it]))
    return first, init, ev


def simulate(net, fans, base, first, init, ev, q_init=None, Rs_scale=1.0):
    cache = {}

    def solve(settings):
        key = tuple(sorted(settings.items()))
        if key not in cache:
            cache[key] = net.passive(net.resistances(base, settings))
        return cache[key]
    settings = dict(init)
    Rs, qu = solve(settings)
    if q_init is None:
        q = fans.start(Rs * Rs_scale)
    else:
        q = q_init
    states = [(first, Rs, qu, q.copy())]
    for t, it, s in ev:
        settings = dict(settings)
        settings[it] = s
        Rs1, qu1 = solve(settings)
        q = fans.follow(q, Rs * Rs_scale, Rs1 * Rs_scale)
        Rs, qu = Rs1, qu1
        states.append((t, Rs, qu, q.copy()))
    return states, settings


def final_flows(net, state):
    t, Rs, qu, q = state
    v = q.sum() * qu
    for k, i in enumerate(net.fan_br):
        v[i] = q[k]
    return v


def mismatch(net, state, surveyed):
    v = final_flows(net, state)
    worst = 0.0
    for n, (dp, qm) in surveyed.items():
        if n not in net.bidx:
            continue
        qc = v[net.bidx[n]]
        worst = max(worst, abs(qc - qm) / max(abs(qm), 1.0))
    return worst


# ----------------------------------------------------------------------------- main
def log(msg):
    sys.stderr.write('airflow: %s\n' % msg)


def main():
    if len(sys.argv) != 3:
        sys.stderr.write('usage: airflow.py PACKAGE_DIR OUT_CSV\n')
        sys.exit(2)
    pkdir, out_csv = sys.argv[1], sys.argv[2]
    pk = Package(pkdir)
    net = Network(pk)
    fans = Fans(net.curves)
    first, init, ev = log_events(pk, net)
    final_settings = dict(init)
    for t, it, s in ev:
        final_settings[it] = s

    base, must, sameday, bad_stop, unknown_air = plan(pk, net)

    # ---- the survey order
    allowance = pk.allowance
    want = []
    if must:
        imp = impact(net, base, final_settings, must)
        want += sorted(must, key=lambda n: -imp[n])
    if sameday:
        imp = impact(net, base, final_settings, sameday)
        want += sorted(sameday, key=lambda n: -imp[n])
    want += bad_stop
    seen = set()
    want = [n for n in want if not (n in seen or seen.add(n))][:max(allowance, 0)]
    spare = allowance - len(want)
    if spare > 0:
        want += [net.names[i] for i in net.fan_br][:spare]
    log('needs survey: airways %s, same-day %s, stoppings %s' % (must, sameday, bad_stop))
    log('order: %s' % want)
    surveyed = order_survey(pkdir, want)
    log('survey: %s' % surveyed)
    for n, (dp, q) in surveyed.items():
        i = net.bidx.get(n)
        if i is None or q == 0:
            continue
        if net.kind[i] in ('airway', 'stopping') and dp * q > 0:
            base[i] = survey_R(dp, q)
    # airways worked on that the crew could not take: the usual effect of the work,
    # then refined from the crew's readings of the district as it stands now
    prior = {}
    for n in must:
        if n in surveyed:
            continue
        i = net.bidx[n]
        if unknown_air.get(n) is not None:
            prior[n] = (np.log(unknown_air[n] * WORK_RATIO), 0.25)
        else:
            prior[n] = (np.log(base[i]), 1.0)
    for n in sameday:
        if n not in surveyed:
            prior[n] = (np.log(base[net.bidx[n]] * np.sqrt(WORK_RATIO)), 0.25)
    for n, (mu, sd) in prior.items():
        base[net.bidx[n]] = float(np.exp(mu))

    # ---- the record
    states, _ = simulate(net, fans, base, first, init, ev)
    if prior and surveyed:
        base2 = infer(net, fans, base, final_settings, states[-1], surveyed, prior)
        if base2 is not None:
            base = base2
            states, _ = simulate(net, fans, base, first, init, ev)

    # ---- check the final state against the crew's readings: the fan operating
    # point at the end of the record must agree with them
    if surveyed:
        m0 = mismatch(net, states[-1], surveyed)
        log('final state against the survey: worst rel. difference %.4f' % m0)
        if m0 > 0.03:
            best = (m0, states)
            Rs0 = states[0][1]
            eqs = fans.equilibria(Rs0)
            for q0 in eqs[1:]:
                st, _ = simulate(net, fans, base, first, init, ev, q_init=q0)
                m = mismatch(net, st[-1], surveyed)
                if m < best[0] - 0.005:
                    best = (m, st)
            if best[0] > 0.03:
                for s in (0.005, -0.005, 0.01, -0.01, 0.02, -0.02, 0.03, -0.03, 0.05, -0.05):
                    st, _ = simulate(net, fans, base, first, init, ev, Rs_scale=1.0 + s)
                    # same operating branches, at the district's own resistance
                    fixed = []
                    for (t, Rs, qu, q) in st:
                        q2, ok = fans.newton(q, Rs)
                        if ok and fans.stable(q2, Rs):
                            q = q2
                        fixed.append((t, Rs, qu, q))
                    m = mismatch(net, fixed[-1], surveyed)
                    if m < best[0] - 0.01:
                        best = (m, fixed)
                    if best[0] < 0.03:
                        break
            states = best[1]

    # ---- results
    times = [s[0] for s in states]
    flows = {}
    with open(out_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['point', 'flow_m3_s'])
        for p in pk.points:
            k = max(bisect.bisect_right(times, p['time']) - 1, 0)
            key = id(states[k])
            if key not in flows:
                flows[key] = final_flows(net, states[k])
            v = flows[key][net.bidx[p['branch']]]
            w.writerow([p['point'], '%.4f' % v])


if __name__ == '__main__':
    main()
