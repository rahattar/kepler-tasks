#!/usr/bin/env python3
"""Airflow at every survey point of a ventilation district package, to VS-4.

    python3 airflow.py PACKAGE_DIR OUT_CSV

Writes OUT_CSV with the header `point,flow_m3_s`: the airflow in each survey
point's branch at its time, in m3/s, signed in the branch's direction.

Method
------
Resistances (VS-4 s.3)
    Airways: the latest pressure-quantity survey, R = dp / (q|q|), provided it was
    made after the airway's last re-support or enlargement.  Airways without such a
    survey on file are surveyed now, in the package's one `pqsurvey` order (crew
    readings of the district as it stands after the last log entry).  A spare slot
    in the order is used for an airway that carries the whole fan flow, as a check
    on the fans' present state.  Stoppings: the register.  Regulators: the table at
    the setting of the log.  Doors: closed (leaking) or open.  Fan branches: the
    ducting resistance in series with the fan.

Steady flow (VS-4 s.2)
    The steady flows are the stationary points of the network's flow potential
        Phi(q) = sum_b [ R_b |q_b|^3 / 3  -  int_0^q_b P_fan,b ]
    over flows that balance at every node.  The fans stand in parallel between the
    fan house and the surface, and everything else is a pure square law, so for a
    total fan flow Q the rest of the network absorbs exactly Req * Q|Q|; Req and
    the flow distribution per unit Q come from one network solve per log state, and
    every non-fan branch flow is Q times its unit flow.

Fan state (VS-4 s.4, s.5)
    The catalogue characteristics (straight lines between tabulated points) have a
    stall dip, so fans in parallel can have several stable operating states (local
    minima of Phi) for the same settings, e.g. both fans unstalled, or one stalled.
    Regulators and doors move slowly and the air follows within seconds, so the
    fans stay in their stable state while a regulator is wound or a door swung,
    moving with it continuously; when that state ceases to exist they fall, along
    the descent of Phi, into the stable state that takes over.  The fan state is
    therefore carried through the whole log, change by change, from the state as
    the record opens.  Req is monotone in every branch resistance, so a change of
    one item moves Req monotonically from its old to its new value, and the fan
    state is followed along that path.
"""
import bisect
import csv
import json
import math
import os
import re
import subprocess
import sys
from collections import defaultdict, deque

import numpy as np

MAJOR_WORK = ('RESUPPORTED', 'ENLARGED')
NO_CHANGE_WORK = ('INSPECTED',)


def warn(msg):
    sys.stderr.write(msg.rstrip() + '\n')


# ----------------------------------------------------------------------------- input
def read_csv(path):
    with open(path, newline='') as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        out.append({(k or '').strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()})
    return out


def fnum(x):
    return float(str(x).strip())


def setting_key(x):
    s = str(x).strip().lower()
    try:
        return ('n', round(float(s), 6))
    except ValueError:
        return ('s', s)


class Package:
    def __init__(self, d):
        self.dir = d
        with open(os.path.join(d, 'district.json')) as f:
            self.meta = json.load(f)
        self.branches = read_csv(os.path.join(d, 'branches.csv'))
        self.surveys = read_csv(os.path.join(d, 'surveys.csv'))
        self.work = read_csv(os.path.join(d, 'work_log.csv'))
        self.regulators = read_csv(os.path.join(d, 'regulators.csv'))
        self.doors = read_csv(os.path.join(d, 'doors.csv'))
        self.fans = read_csv(os.path.join(d, 'fans.csv'))
        self.fan_curves = read_csv(os.path.join(d, 'fan_curves.csv'))
        self.log = read_csv(os.path.join(d, 'log.csv'))
        self.points = read_csv(os.path.join(d, 'points.csv'))


# ------------------------------------------------------------------------ network
class Network:
    def __init__(self, pkg):
        self.pkg = pkg
        br = pkg.branches
        self.names = [b['branch'] for b in br]
        self.bidx = {n: i for i, n in enumerate(self.names)}
        self.kind = [b['kind'].strip().lower() for b in br]
        self.item = [b.get('item', '') or '' for b in br]
        nodes, nset = [], {}
        for b in br:
            for n in (b['from_node'], b['to_node']):
                if n not in nset:
                    nset[n] = len(nodes)
                    nodes.append(n)
        self.nodes, self.nidx = nodes, nset
        self.nb = len(br)
        self.fr = np.array([nset[b['from_node']] for b in br])
        self.to = np.array([nset[b['to_node']] for b in br])
        self.reg_R = {}
        for r in pkg.regulators:
            self.reg_R[(r['regulator'], setting_key(r['setting']))] = fnum(r['resistance_Ns2_m8'])
        self.door_R = {}
        for r in pkg.doors:
            self.door_R[r['door']] = (fnum(r['resistance_closed_Ns2_m8']), fnum(r['resistance_open_Ns2_m8']))
        self.fan_idx = [i for i in range(self.nb) if self.kind[i] == 'fan']
        self.atm = nset['ATM']

    def regulator_R(self, reg, setting):
        key = (reg, setting_key(setting))
        if key in self.reg_R:
            return self.reg_R[key]
        # a setting between tabulated ones: log-linear between its neighbours
        v = fnum(setting)
        tab = sorted((k[1][1], r) for k, r in self.reg_R.items() if k[0] == reg and k[1][0] == 'n')
        xs = [t[0] for t in tab]
        j = min(max(bisect.bisect_left(xs, v), 1), len(xs) - 1)
        (x0, r0), (x1, r1) = tab[j - 1], tab[j]
        a = (v - x0) / (x1 - x0)
        warn('note: %s setting %s is not in its table; interpolating' % (reg, setting))
        return math.exp((1 - a) * math.log(r0) + a * math.log(r1))

    def loop_basis(self, use):
        """Loop matrix C (branches x loops) of the sub-network `use`, from a spanning
        tree rooted at ATM; also the tree and a path-to-root function."""
        fr, to = self.fr, self.to
        adj = defaultdict(list)
        for i in use:
            adj[fr[i]].append((i, to[i]))
            adj[to[i]].append((i, fr[i]))
        par = {self.atm: None}
        dq = deque([self.atm])
        tree = set()
        while dq:
            u = dq.popleft()
            for (e, v) in adj[u]:
                if v not in par:
                    par[v] = (e, u)
                    tree.add(e)
                    dq.append(v)

        def path(n):
            res = []
            while par[n] is not None:
                e, u = par[n]
                res.append((e, 1.0 if fr[e] == n else -1.0))
                n = u
            return res

        chords = [e for e in use if e not in tree]
        C = np.zeros((self.nb, len(chords)))
        for j, e in enumerate(chords):
            C[e, j] += 1.0
            for (ee, s) in path(to[e]):
                C[ee, j] += s
            for (ee, s) in path(fr[e]):
                C[ee, j] -= s
        return C, par, path


# ----------------------------------------------------------------- resistances
def airway_resistances(pkg, net):
    """Airway resistances from the latest survey made since any re-support or
    enlargement (VS-4 s.3), and the airways that need a fresh survey, as
    (priority, -importance, name): 1 = no valid survey on file, 2 = surveyed on the
    day of the work (order unknown), 3 = work of an unknown kind since the survey."""
    last_major, last_other = {}, {}
    for w in pkg.work:
        kind = w.get('work', '').strip().upper()
        b = w.get('branch', '')
        d = w.get('date', '')
        if kind in MAJOR_WORK:
            if d > last_major.get(b, ''):
                last_major[b] = d
        elif kind not in NO_CHANGE_WORK:
            if d > last_other.get(b, ''):
                last_other[b] = d
    surveys = defaultdict(list)
    for k, s in enumerate(pkg.surveys):
        try:
            surveys[s['branch']].append((s['date'], k, fnum(s['dp_Pa']), fnum(s['q_m3_s'])))
        except (ValueError, KeyError):
            continue
    R, need = {}, []
    for i, n in enumerate(net.names):
        if net.kind[i] != 'airway':
            continue
        lst = sorted(s for s in surveys.get(n, []) if s[2] != 0 and s[3] != 0)
        wd = last_major.get(n)
        valid = [s for s in lst if wd is None or s[0] > wd]
        if valid:
            _, _, dp, q = valid[-1]
            R[n] = dp / (q * abs(q))
            od = last_other.get(n)
            if od is not None and od >= valid[-1][0]:
                need.append((3, -abs(dp), n))
        else:
            # no survey since the work; one made on the day of the work may or may not
            # follow it: use it meanwhile, but survey afresh
            same_day = [s for s in lst if s[0] == wd]
            pool = same_day or lst
            if pool:
                _, _, dp, q = pool[-1]
                R[n] = dp / (q * abs(q))
                imp = abs(dp)
            else:
                R[n] = None
                imp = float('inf')
            need.append((1 if not same_day else 2, -imp, n))
    need.sort()
    return R, need


def resistance_vector(net, Rair, state):
    R = np.zeros(net.nb)
    for i in range(net.nb):
        k = net.kind[i]
        b = net.pkg.branches[i]
        if k == 'airway':
            R[i] = Rair[net.names[i]]
        elif k == 'stopping':
            R[i] = fnum(b['resistance_Ns2_m8'])
        elif k == 'regulator':
            R[i] = net.regulator_R(net.item[i], state[net.item[i]])
        elif k == 'door':
            it = net.item[i]
            c, o = net.door_R[it]
            R[i] = o if str(state[it]).strip().lower() == 'open' else c
        elif k == 'fan':
            v = b.get('resistance_Ns2_m8', '')
            R[i] = fnum(v) if v not in ('', None) else 0.0
        else:
            raise ValueError('unknown branch kind %r' % k)
    return R


def log_states(pkg, net):
    """[(time, {item: setting})]: the settings as the record opens, then after each
    change (VS-4 s.5)."""
    log = [r for _, r in sorted(enumerate(pkg.log), key=lambda kv: (kv[1]['time'], kv[0]))]
    t0 = log[0]['time']
    state = {}
    for r in log:
        if r['time'] == t0:
            state[r['item']] = r['setting']
    # an item missing from the opening rows: take its first entry in the log
    for i in range(net.nb):
        it = net.item[i]
        if net.kind[i] in ('regulator', 'door') and it not in state:
            first = [r for r in log if r['item'] == it]
            if first:
                state[it] = first[0]['setting']
            else:
                state[it] = 'closed' if net.kind[i] == 'door' else '10'
            warn('note: %s has no setting as the record opens; taking %s' % (it, state[it]))
    states = [(t0, dict(state))]
    for r in log:
        if r['time'] == t0:
            continue
        state[r['item']] = r['setting']
        states.append((r['time'], dict(state)))
    return states


# ---------------------------------------------------------------------- fans
class FanCurve:
    """Catalogue characteristic, straight lines between tabulated points (VS-4 s.4),
    with the ducting resistance Rd of the fan branch in series."""

    def __init__(self, flows, pressures, Rd):
        pts = sorted(zip([float(v) for v in flows], [float(v) for v in pressures]))
        pts = [p for k, p in enumerate(pts) if k == 0 or p[0] > pts[k - 1][0]]
        self.x = [p[0] for p in pts]
        self.y = [p[1] for p in pts]
        self.Rd = float(Rd)
        x, y = self.x, self.y
        self.s = [(y[k + 1] - y[k]) / (x[k + 1] - x[k]) for k in range(len(x) - 1)]
        cum = [0.0]
        for k in range(len(x) - 1):
            cum.append(cum[-1] + 0.5 * (y[k] + y[k + 1]) * (x[k + 1] - x[k]))
        self.cum = cum
        self.g0 = self._Gx(0.0)
        self.qmax = x[-1]

    def _seg(self, q):
        k = bisect.bisect_right(self.x, q) - 1
        return 0 if k < 0 else min(k, len(self.s) - 1)

    def P(self, q):
        # straight-line extension outside the table (never reached within scope)
        k = self._seg(q)
        return self.y[k] + self.s[k] * (q - self.x[k])

    def dP(self, q):
        return self.s[self._seg(q)]

    def _Gx(self, q):
        k = self._seg(q)
        d = q - self.x[k]
        return self.cum[k] + self.y[k] * d + 0.5 * self.s[k] * d * d

    def G(self, q):
        """integral_0^q P."""
        return self._Gx(q) - self.g0

    def H(self, q):
        """Fan pressure less the ducting loss: what the fan branch delivers."""
        return self.P(q) - self.Rd * q * abs(q)

    def dH(self, q):
        return self.dP(q) - 2.0 * self.Rd * abs(q)


def fan_curves(pkg, net):
    curves = []
    for i in net.fan_idx:
        it = net.item[i]
        fan = [f for f in pkg.fans if f.get('fan') == it] or [f for f in pkg.fans if f.get('branch') == net.names[i]]
        if not fan:
            raise ValueError('no fan for branch %s' % net.names[i])
        fan = fan[0]
        model, bs = fan['model'], setting_key(fan['blade_setting'])
        rows = [r for r in pkg.fan_curves if r['model'] == model and setting_key(r['blade_setting']) == bs]
        if len(rows) < 2:
            raise ValueError('no catalogue characteristic for %s at blade setting %s' % (model, fan['blade_setting']))
        v = pkg.branches[i].get('resistance_Ns2_m8', '')
        Rd = fnum(v) if v not in ('', None) else 0.0
        curves.append(FanCurve([fnum(r['flow_m3_s']) for r in rows], [fnum(r['pressure_Pa']) for r in rows], Rd))
    return curves


class FanSystem:
    """n fans in parallel between the fan house and the surface, working against the
    rest of the network of equivalent resistance Req:
        Phi(q) = Req |Q|^3/3 + sum_i [Rd_i |q_i|^3/3 - int_0^q_i P_i],   Q = sum q_i."""

    def __init__(self, curves):
        self.c = curves
        self.n = len(curves)

    def grad(self, q, Req):
        Q = q.sum()
        return np.array([Req * Q * abs(Q) - c.H(qi) for c, qi in zip(self.c, q)])

    def hess(self, q, Req):
        Q = q.sum()
        Hm = np.full((self.n, self.n), 2.0 * Req * abs(Q))
        for i, (c, qi) in enumerate(zip(self.c, q)):
            Hm[i, i] -= c.dH(qi)
        return Hm

    def phi(self, q, Req):
        Q = q.sum()
        v = Req * abs(Q) ** 3 / 3.0
        for c, qi in zip(self.c, q):
            v += c.Rd * abs(qi) ** 3 / 3.0 - c.G(qi)
        return v

    def is_min(self, q, Req):
        """Strict local minimum (stable state); checked on both sides of any kink of
        the piecewise-linear characteristics."""
        for d in (-1e-6, 1e-6):
            if np.linalg.eigvalsh(self.hess(q + d, Req)).min() <= 0:
                return False
        return True

    def newton(self, q, Req, maxit=100, rmax=2.0):
        """Safeguarded Newton descent to a local minimum of Phi near q.  Steps are
        bounded and never increase Phi.  Returns (q, converged)."""
        q = np.asarray(q, float).copy()
        g = self.grad(q, Req)
        f = self.phi(q, Req)
        for _ in range(maxit):
            if np.max(np.abs(g)) < 1e-8:
                return q, True
            Hm = self.hess(q, Req)
            w, V = np.linalg.eigh(Hm)
            pd = w.min() > 0
            if pd:
                step = -np.linalg.solve(Hm, g)
            else:
                wm = np.maximum(np.abs(w), 1e-3 * np.abs(w).max() + 1e-12)
                step = -V @ ((V.T @ g) / wm)
            m = np.max(np.abs(step))
            if m > rmax:
                step *= rmax / m
                m = rmax
            if pd and m < 1e-3:
                # close in: plain Newton (Phi differences are lost in rounding here)
                qn = q + step
                gn = self.grad(qn, Req)
                if np.max(np.abs(gn)) < np.max(np.abs(g)):
                    q, g = qn, gn
                    f = self.phi(q, Req)
                    if m < 1e-11:
                        return q, True
                    continue
            t = 1.0
            slope = float(g @ step)
            while True:
                qn = q + t * step
                fn = self.phi(qn, Req)
                if fn <= f + 1e-4 * t * slope:
                    break
                t *= 0.5
                if t < 1e-10:
                    return q, bool(np.max(np.abs(g)) < 1e-6)
            q, f = qn, fn
            g = self.grad(q, Req)
            if t * m < 1e-11:
                return q, bool(np.max(np.abs(g)) < 1e-6)
        return q, bool(np.max(np.abs(g)) < 1e-6)

    def descend(self, q, Req):
        """Follow the descent of Phi (dq/dt = -grad Phi) from q until the fans settle
        in a stable state."""
        from scipy.integrate import solve_ivp
        q = np.asarray(q, float).copy()
        fun = lambda t, y: -self.grad(y, Req)
        jac = lambda t, y: -self.hess(y, Req)
        for _attempt in range(8):
            T = 1.0
            for _ in range(40):
                sol = solve_ivp(fun, (0.0, T), q, method='BDF', jac=jac, rtol=1e-9, atol=1e-9)
                q = sol.y[:, -1]
                if np.max(np.abs(self.grad(q, Req))) < 1e-6:
                    break
                T *= 2.0
            qn, ok = self.newton(q, Req, rmax=0.1)
            if ok and self.is_min(qn, Req) and np.max(np.abs(qn - q)) < 0.5:
                return qn
            # resting on a saddle or on a kink of a characteristic: leave it downhill
            best = None
            f0 = self.phi(q, Req)
            for d in (-1e-6, 1e-6):
                w, V = np.linalg.eigh(self.hess(q + d, Req))
                for j in range(len(w)):
                    for sgn in (-1.0, 1.0):
                        qt = q + sgn * 1e-3 * V[:, j]
                        ft = self.phi(qt, Req)
                        if ft < f0 and (best is None or ft < best[0]):
                            best = (ft, qt)
            if best is None:
                break
            q = best[1]
        raise RuntimeError('fan state did not settle (q=%s, Req=%r)' % (q, Req))

    def track(self, q, Req0, Req1):
        """Carry a stable state along a monotone change of Req from Req0 to Req1."""
        if Req0 == Req1:
            return q
        l0, l1 = math.log(Req0), math.log(Req1)
        H0 = 0.01
        h = H0 if l1 > l0 else -H0
        lam = l0
        q = q.copy()
        hmin = 1e-7
        while (l1 - lam) * math.copysign(1.0, h) > 0:
            step = h if abs(h) < abs(l1 - lam) else (l1 - lam)
            Req = math.exp(lam + step)
            qn, ok = self.newton(q, Req)
            if ok and self.is_min(qn, Req) and np.max(np.abs(qn - q)) < 2.0:
                q = qn
                lam += step
                h = math.copysign(min(abs(h) * 1.5, H0), h)
                continue
            if abs(step) > hmin:
                h = step / 4.0
                continue
            # the stable state has ceased to exist: fall into the one that takes over
            # (evaluated just past the end of the old state, so the fall is not lost
            # in rounding)
            over = math.copysign(min(1e-4, abs(l1 - lam)), h)
            q = self.descend(q, math.exp(lam + over))
            lam += over
            h = math.copysign(H0, h)
        return q

    def all_minima(self, Req, qmax):
        """All stable states at a given Req (for the state as the record opens)."""
        from scipy.optimize import minimize
        found = []
        k = 7 if self.n <= 2 else (5 if self.n == 3 else 3)
        grids = [np.linspace(0.02 * qm, 0.98 * qm, k) for qm in qmax]
        mesh = np.array(np.meshgrid(*grids, indexing='ij')).reshape(self.n, -1).T
        bounds = [(0.0, qm) for qm in qmax]
        for q0 in mesh:
            r = minimize(lambda y: self.phi(y, Req), q0, jac=lambda y: self.grad(y, Req),
                         method='L-BFGS-B', bounds=bounds, options={'gtol': 1e-9, 'ftol': 1e-14})
            q, ok = self.newton(r.x, Req)
            if not ok or not self.is_min(q, Req):
                continue
            if not any(np.max(np.abs(q - f)) < 1e-3 for f in found):
                found.append(q)
        return found


# ------------------------------------------------------------------ passive solve
class Passive:
    """The network without its fans, carrying a unit flow from the surface through
    the mine to the fan house: Req and the flow per unit of total fan flow."""

    def __init__(self, net):
        self.net = net
        fanset = set(net.fan_idx)
        if not fanset:
            raise ValueError('no fans')
        fh = set(int(net.fr[i]) for i in net.fan_idx)
        ends = set(int(net.to[i]) for i in net.fan_idx)
        if len(fh) != 1 or ends != {net.atm}:
            raise ValueError('fans are not in parallel between one fan house and ATM')
        use = [i for i in range(net.nb) if i not in fanset]
        C, par, path = net.loop_basis(use)
        if len(par) != len(net.nodes):
            raise ValueError('network without the fans is disconnected')
        self.C = C
        self.fh = fh.pop()
        q0 = np.zeros(net.nb)
        for (e, s) in path(self.fh):
            q0[e] -= s
        self.q0 = q0
        self.f = np.zeros(C.shape[1])

    def solve(self, R):
        """Minimise sum R|q|^3/3 over unit flows (convex): Newton with line search,
        warm-started from the previous solve."""
        C, q0 = self.C, self.q0
        f = self.f.copy()

        def phi(ff):
            qq = q0 + C @ ff
            return float(np.sum(R * np.abs(qq) ** 3)) / 3.0

        p_old = phi(f)
        for _ in range(200):
            q = q0 + C @ f
            aq = np.abs(q)
            g = C.T @ (R * q * aq)
            d = 2.0 * R * aq
            d = np.maximum(d, 1e-12 * (d.max() + 1e-30))
            J = C.T @ (d[:, None] * C)
            step = np.linalg.solve(J, -g)
            t = 1.0
            slope = float(g @ step)
            while True:
                p_new = phi(f + t * step)
                if p_new <= p_old + 1e-4 * t * slope or t < 1e-12:
                    break
                t *= 0.5
            f = f + t * step
            p_old = p_new
            if np.max(np.abs(t * step)) < 1e-12:
                break
        self.f = f
        q = q0 + C @ f
        return float(np.sum(R * np.abs(q) ** 3)), q


# --------------------------------------------------------- fallback: transient
def transient_history(net, Rair, states, curves):
    """Fallback for a fan arrangement outside the reduction above: the full network
    in loop flows, with inertia, every change ramped over a minute and then left to
    settle.  Returns the branch flows of every log state."""
    from scipy.integrate import solve_ivp
    C, par, path = net.loop_basis(list(range(net.nb)))
    fanpos = {b: j for j, b in enumerate(net.fan_idx)}
    L = np.full(net.nb, 0.05)
    M = C.T @ (L[:, None] * C)
    Minv = np.linalg.inv(M)

    def hd(q, R):
        h = R * q * np.abs(q)
        d = 2.0 * R * np.abs(q)
        for b, j in fanpos.items():
            c = curves[j]
            h[b] -= c.P(q[b])
            d[b] -= c.dP(q[b])
        return h, d

    def run(Rfun, f, T):
        fun = lambda t, y: -Minv @ (C.T @ hd(C @ y, Rfun(t))[0])
        jac = lambda t, y: -Minv @ (C.T @ (hd(C @ y, Rfun(t))[1][:, None] * C))
        return solve_ivp(fun, (0.0, T), f, method='BDF', jac=jac, rtol=1e-8, atol=1e-8).y[:, -1]

    # fan branch resistance (ducting) is already in R; the curve carries P only
    R0 = resistance_vector(net, Rair, states[0][1])
    f = run(lambda t: R0, np.zeros(C.shape[1]), 3000.0)
    out = [C @ f]
    for k in range(1, len(states)):
        Ra = resistance_vector(net, Rair, states[k - 1][1])
        Rb = resistance_vector(net, Rair, states[k][1])
        la, lb = np.log(np.maximum(Ra, 1e-300)), np.log(np.maximum(Rb, 1e-300))

        def Rfun(t, la=la, lb=lb):
            a = min(max(t / 60.0, 0.0), 1.0)
            return np.exp((1.0 - a) * la + a * lb)
        f = run(Rfun, f, 60.0)
        f = run(lambda t, Rb=Rb: Rb, f, 3000.0)
        out.append(C @ f)
    return out


# ------------------------------------------------------------------------- main
def order_surveys(pkg_dir, order, retry=True):
    """Place the package's one survey order; returns {branch: (dp, q)}.  An order
    larger than the crew takes is refused without being taken, so it is cut down
    once (the list is in order of importance)."""
    measured = {}
    if not order:
        return measured
    try:
        res = subprocess.run(['pqsurvey', pkg_dir] + order, capture_output=True, text=True, timeout=20)
    except Exception as e:
        warn('pqsurvey could not be run: %s' % e)
        return measured
    if res.returncode != 0:
        msg = (res.stderr or res.stdout).strip()
        warn('pqsurvey (%s) answered %d: %s' % (' '.join(order), res.returncode, msg))
        m = re.search(r'at most (\d+)', msg)
        if retry and m and 0 < int(m.group(1)) < len(order):
            return order_surveys(pkg_dir, order[:int(m.group(1))], retry=False)
    for line in res.stdout.splitlines():
        parts = [p.strip() for p in line.strip().split(',')]
        if len(parts) < 3 or parts[0] == 'branch':
            continue
        try:
            measured[parts[0]] = (float(parts[1]), float(parts[2]))
        except ValueError:
            continue
    return measured


def main():
    if len(sys.argv) != 3:
        sys.exit('usage: python3 airflow.py PACKAGE_DIR OUT_CSV')
    pkg_dir, out_csv = sys.argv[1], sys.argv[2]
    pkg = Package(pkg_dir)
    net = Network(pkg)
    try:
        allowance = int(pkg.meta.get('survey_allowance', 0))
    except (TypeError, ValueError):
        allowance = 0
    debug = bool(os.environ.get('AIRFLOW_DEBUG'))

    Rair, need = airway_resistances(pkg, net)
    order = [n for _, _, n in need][:max(allowance, 0)]
    if len([1 for p, _, _ in need if p == 1]) > allowance:
        warn('note: %d airways need a survey, the allowance is %d' % (len([1 for p, _, _ in need if p == 1]), allowance))
    states = log_states(pkg, net)
    curves = fan_curves(pkg, net)

    try:
        passive = Passive(net)
    except ValueError as e:
        warn('note: %s; using the transient calculation' % e)
        passive = None

    # a spare slot: an airway in series with the fans, as a check on their present state
    check_branch = None
    if passive is not None and len(order) < allowance:
        Rtmp = {k: (v if v is not None else 0.01) for k, v in Rair.items()}
        _, qu = passive.solve(resistance_vector(net, Rtmp, states[-1][1]))
        passive.f[:] = 0.0
        best = None
        for i in range(net.nb):
            if net.kind[i] == 'airway' and net.names[i] not in order:
                if best is None or abs(qu[i]) > best[0] + 1e-9:
                    best = (abs(qu[i]), i)
        if best is not None and best[0] > 0.999:
            check_branch = net.names[best[1]]
            order.append(check_branch)

    measured = order_surveys(pkg_dir, order)
    for b, (dp, q) in measured.items():
        if b in Rair and q != 0 and dp != 0:
            Rair[b] = dp / (q * abs(q))
    for b in order:
        if b not in measured and b != check_branch:
            warn('note: no fresh survey of %s; using the survey on file' % b)
    missing = [k for k, v in Rair.items() if v is None]
    if missing:
        raise RuntimeError('no resistance for airways %s' % missing)

    times = [s[0] for s in states]
    flows = None  # per state: function branch index -> flow
    if passive is not None:
        try:
            seg_Req, seg_qu = [], []
            for (t, st) in states:
                Req, qu = passive.solve(resistance_vector(net, Rair, st))
                seg_Req.append(Req)
                seg_qu.append(qu)
            fs = FanSystem(curves)

            def run_history(q):
                qs = [q]
                for k in range(1, len(states)):
                    q = fs.track(q, seg_Req[k - 1], seg_Req[k])
                    qs.append(q)
                return qs

            starts = fs.all_minima(seg_Req[0], [c.qmax for c in curves])
            if not starts:
                raise RuntimeError('no stable fan state as the record opens')
            starts.sort(key=lambda q: -q.sum())
            if len(starts) == 1:
                hist = run_history(starts[0])
            else:
                warn('note: %d stable fan states as the record opens' % len(starts))
                hists = [run_history(q) for q in starts]
                chosen = 0
                if check_branch in measured:
                    ib = net.bidx[check_branch]
                    qm = measured[check_branch][1]
                    errs = [abs(h[-1].sum() * seg_qu[-1][ib] - qm) for h in hists]
                    chosen = int(np.argmin(errs))
                hist = hists[chosen]
            if check_branch in measured:
                ib = net.bidx[check_branch]
                pred = hist[-1].sum() * seg_qu[-1][ib]
                qm = measured[check_branch][1]
                if abs(pred - qm) > 0.01 * abs(qm):
                    warn('warning: %s now carries %.3f m3/s by the crew, %.3f by calculation' % (check_branch, qm, pred))
            if debug:
                warn('order: %s  (needed: %s)' % (order, need))
                for k, (t, st) in enumerate(states):
                    warn('%3d %s Req=%.6f fans=%s Q=%.3f' % (k, t, seg_Req[k], np.round(hist[k], 3), hist[k].sum()))
            fanpos = {b: j for j, b in enumerate(net.fan_idx)}

            def flow(k, ib):
                if ib in fanpos:
                    return hist[k][fanpos[ib]]
                return hist[k].sum() * seg_qu[k][ib]
            flows = flow
        except Exception as e:
            warn('note: fan-state calculation failed (%s); using the transient calculation' % e)
            flows = None
    if flows is None:
        qs = transient_history(net, Rair, states, curves)
        flows = lambda k, ib: qs[k][ib]

    with open(out_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['point', 'flow_m3_s'])
        for p in pkg.points:
            k = max(bisect.bisect_right(times, p['time']) - 1, 0)
            w.writerow([p['point'], '%.4f' % flows(k, net.bidx[p['branch']])])


if __name__ == '__main__':
    main()
