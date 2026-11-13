#!/usr/bin/env python3
"""Airflow at every survey point of a ventilation district package, to VS-4.

    python3 airflow.py PACKAGE_DIR OUT_CSV

Method
------
Network.  Branch flows are q = C l, l being the flows of a spanning-tree loop basis, so the
node balances hold identically.  The branch law p_from - p_to = R q|q| - P_fan(q) is the
gradient of the co-content
    F(l) = sum_i R_i |q_i|^3 / 3  -  sum_fans integral_0^q P_fan,
so the steady flows are the stationary points of F.  Air that follows a change "within
seconds" runs down F (L dq/dt = loop pressure imbalance is a gradient flow of F), so the
flows that are held are the local minima of F.  The fans' catalogue curves have a stall dip,
so there can be several minima, and which one the district is in depends on its history.

History.  Every log change (a regulator wound, a door swung) is followed quasi-statically:
the item's resistance is moved gradually from the old to the new setting and the local
minimum is tracked.  Where it ceases to exist (a fan stalls, or a stalled fan recovers)
the flow drops into the neighbouring minimum, as the air does.

Resistances (VS-4 section 3).  Airways from their pressure-quantity surveys: the latest,
averaged with earlier surveys of the same airway since its last work that agree with it.
Stoppings from the register, unless the campaign surveys show that one does not hold to the
resistance it was built to: within a campaign the regulators and doors stand still, so the
surveyed airways give the pressure across a stopping and, from the node balances, the air
leaking through it.  Regulators from their tables, doors closed or open, fan ducts from the
register.  An airway re-supported or enlarged since its latest survey is surveyed afresh in
the one survey order.  If there are more of them than the crew will take, the order is chosen
to tell the most about the results, and the airways not surveyed are estimated from the
airflows the crew reads in the district as it stands now.

Knife-edge events.  A setting change can bring a fan to within a hair of stalling (or of
recovering), closer than the resistances are known.  The record is therefore also run with
the estimated resistances scaled by small factors.  The crew reads the district as it
stands now, which tells which of these histories the district went through; failing that,
the nominal history is kept.
"""
import csv
import json
import math
import os
import subprocess
import sys
from bisect import bisect_right
from datetime import datetime
from itertools import product

import numpy as np
from scipy.linalg import cho_factor, cho_solve, LinAlgError

DEBUG = bool(os.environ.get('AIRFLOW_DEBUG'))


def dbg(*a):
    if DEBUG:
        sys.stderr.write(' '.join(str(x) for x in a) + '\n')


# --------------------------------------------------------------------------- input


def read_csv(path):
    with open(path, newline='') as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        out.append({(k or '').strip(): (v if isinstance(v, str) else '').strip() for k, v in r.items()})
    return out


def parse_time(s):
    s = s.strip()
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return datetime.strptime(s[:10], '%Y-%m-%d')


def parse_date(s):
    return parse_time(s).date()


def fnum(s, default=None):
    try:
        v = float(s)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def is_changing_work(w):
    w = w.upper().replace(' ', '').replace('-', '')
    return 'RESUPPORT' in w or 'ENLARG' in w


def door_value(s):
    s = s.strip().lower()
    if s.startswith('open'):
        return 1.0
    if s.startswith('clos') or s.startswith('shut'):
        return 0.0
    v = fnum(s)
    return 0.0 if v is None else min(max(v, 0.0), 1.0)


class Package:
    def __init__(self, d):
        self.dir = d
        try:
            self.meta = json.load(open(os.path.join(d, 'district.json')))
        except Exception:
            self.meta = {}
        try:
            self.allowance = int(self.meta.get('survey_allowance', 0))
        except (TypeError, ValueError):
            self.allowance = 0

        def rd(n, required=True):
            try:
                return read_csv(os.path.join(d, n))
            except FileNotFoundError:
                if required:
                    raise
                return []
        self.branches = rd('branches.csv')
        self.surveys = rd('surveys.csv', False)
        self.work = rd('work_log.csv', False)
        self.regulators = rd('regulators.csv', False)
        self.doors = rd('doors.csv', False)
        self.fans = rd('fans.csv', False)
        self.curves = rd('fan_curves.csv', False)
        self.log = rd('log.csv', False)
        self.points = rd('points.csv')


# ---------------------------------------------------------------------------- fans


class FanCurve:
    """Catalogue characteristic: straight lines between the tabulated points (VS-4 s.4),
    continued along the end segments outside the table."""

    def __init__(self, x, y):
        o = sorted(range(len(x)), key=lambda i: x[i])
        x = [float(x[i]) for i in o]
        y = [float(y[i]) for i in o]
        self.x, self.y = x, y
        n = len(x)
        self.s = [(y[k + 1] - y[k]) / (x[k + 1] - x[k]) if x[k + 1] > x[k] else 0.0
                  for k in range(n - 1)]
        cum = [0.0]
        for k in range(n - 1):
            cum.append(cum[-1] + 0.5 * (y[k] + y[k + 1]) * (x[k + 1] - x[k]))
        self.cum = cum
        self.qfree = x[-1]
        self.nseg = n - 1
        # vertices where the curve turns (stall dip, peak): they bound the stable ranges
        self.turns = [x[k + 1] for k in range(n - 2) if (self.s[k] < 0) != (self.s[k + 1] < 0)]

    def eval(self, q):
        k = bisect_right(self.x, q) - 1
        if k < 0:
            k = 0
        elif k > self.nseg - 1:
            k = self.nseg - 1
        xk = self.x[k]
        p = self.y[k] + self.s[k] * (q - xk)
        return p, self.s[k], self.cum[k] + 0.5 * (self.y[k] + p) * (q - xk)

    def branch(self, q):
        return bisect_right(self.turns, q)


def fan_curve_for(pkg, model, blade):
    by = {}
    for c in pkg.curves:
        if c.get('model', '') != model:
            continue
        b = fnum(c.get('blade_setting'))
        x, y = fnum(c.get('flow_m3_s')), fnum(c.get('pressure_Pa'))
        if x is None or y is None:
            continue
        by.setdefault(b, []).append((x, y))
    bv = fnum(blade)
    if bv in by:
        pts = by[bv]
    else:
        keys = sorted(k for k in by if k is not None)
        lo = max([k for k in keys if k <= bv], default=keys[0])
        hi = min([k for k in keys if k >= bv], default=keys[-1])
        a, b = by[lo], by[hi]
        if lo == hi or len(a) != len(b):
            pts = a if abs(bv - lo) <= abs(hi - bv) else b
        else:
            t = (bv - lo) / (hi - lo)
            pts = [(pa[0] * (1 - t) + pb[0] * t, pa[1] * (1 - t) + pb[1] * t) for pa, pb in zip(a, b)]
    return FanCurve([p[0] for p in pts], [p[1] for p in pts])


PRIOR_RATIO = 0.6       # resistance after re-supporting / enlarging, relative to before
PRIOR_SIGMA = 0.35      # spread of log resistance about that
READ_SD = 0.0017        # sd of a survey reading (within 0.3 per cent)


def q_sigma(qv):
    """Uncertainty of a predicted airflow against the crew's reading of it."""
    return 0.004 * abs(qv) + 0.005


# ------------------------------------------------------------------------- network


class Network:
    def __init__(self, pkg):
        self.pkg = pkg
        br = pkg.branches
        self.names = [b['branch'] for b in br]
        self.idx = {n: i for i, n in enumerate(self.names)}
        self.kind = [b.get('kind', '').strip().lower() for b in br]
        self.item = [b.get('item', '') for b in br]
        nodes = {}
        for b in br:
            for k in ('from_node', 'to_node'):
                if b[k] not in nodes:
                    nodes[b[k]] = len(nodes)
        if 'ATM' not in nodes:
            nodes['ATM'] = len(nodes)
        self.nodes = nodes
        self.fr = [nodes[b['from_node']] for b in br]
        self.to = [nodes[b['to_node']] for b in br]
        self.nb = len(br)
        self.incident = [[] for _ in nodes]
        for i in range(self.nb):
            self.incident[self.fr[i]].append(i)
            if self.to[i] != self.fr[i]:
                self.incident[self.to[i]].append(i)
        self._build_loops()

        self.reg_tab = {}
        for r in pkg.regulators:
            s, v = fnum(r.get('setting')), fnum(r.get('resistance_Ns2_m8'))
            if s is not None and v is not None:
                self.reg_tab.setdefault(r['regulator'], []).append((s, v))
        for k in self.reg_tab:
            self.reg_tab[k].sort()
        self.door_tab = {}
        for d in pkg.doors:
            c, o = fnum(d.get('resistance_closed_Ns2_m8')), fnum(d.get('resistance_open_Ns2_m8'))
            if c is not None and o is not None:
                self.door_tab[d['door']] = [c, o]
        self.item_br = {}
        for i in range(self.nb):
            if self.kind[i] in ('regulator', 'door') and self.item[i]:
                self.item_br.setdefault(self.item[i], []).append(i)

        self.fan_br, self.fan_curve = [], []
        by_branch = {f['branch']: f for f in pkg.fans}
        by_name = {f['fan']: f for f in pkg.fans}
        for i in range(self.nb):
            if self.kind[i] != 'fan':
                continue
            f = by_branch.get(self.names[i]) or by_name.get(self.item[i])
            if f is None:
                continue
            self.fan_br.append(i)
            self.fan_curve.append(fan_curve_for(pkg, f['model'], f['blade_setting']))
        self.nf = len(self.fan_br)

        self.R0 = np.zeros(self.nb)
        for i, b in enumerate(br):
            if self.kind[i] in ('stopping', 'fan'):
                v = fnum(b.get('resistance_Ns2_m8'))
                self.R0[i] = v if v is not None else 0.0
        self.uncertain = np.zeros(self.nb, dtype=bool)   # resistances estimated from surveys
        self._airway_resistances()
        self._campaign_evidence()

    # ---- loops of a spanning tree rooted at the surface
    def _build_loops(self):
        nn = len(self.nodes)
        adj = [[] for _ in range(nn)]
        for i in range(self.nb):
            if self.fr[i] != self.to[i]:
                adj[self.fr[i]].append((i, self.to[i]))
                adj[self.to[i]].append((i, self.fr[i]))
        root = self.nodes['ATM']
        parent, pbr, depth = [-1] * nn, [-1] * nn, [0] * nn
        seen = [False] * nn
        tree = set()
        for start in [root] + list(range(nn)):
            if seen[start]:
                continue
            seen[start] = True
            queue, qi = [start], 0
            while qi < len(queue):
                u = queue[qi]
                qi += 1
                for (i, v) in adj[u]:
                    if not seen[v]:
                        seen[v] = True
                        parent[v], pbr[v], depth[v] = u, i, depth[u] + 1
                        tree.add(i)
                        queue.append(v)
        chords = [i for i in range(self.nb) if i not in tree and self.fr[i] != self.to[i]]
        C = np.zeros((self.nb, max(len(chords), 1)))
        for j, c in enumerate(chords):
            C[c, j] = 1.0
            a, b = self.to[c], self.fr[c]
            pa, pb = [], []
            while depth[a] > depth[b]:
                pa.append(a)
                a = parent[a]
            while depth[b] > depth[a]:
                pb.append(b)
                b = parent[b]
            while a != b:
                pa.append(a)
                a = parent[a]
                pb.append(b)
                b = parent[b]
            for x in pa:
                i = pbr[x]
                C[i, j] += 1.0 if self.fr[i] == x else -1.0
            for x in pb:
                i = pbr[x]
                C[i, j] += 1.0 if self.to[i] == x else -1.0
        self.C = C
        self.CT = np.ascontiguousarray(C.T)
        self.nl = C.shape[1]

    # ---- surveys on file
    def _survey_rows(self):
        rows = []
        for k, s in enumerate(self.pkg.surveys):
            dp, q = fnum(s.get('dp_Pa')), fnum(s.get('q_m3_s'))
            if dp is None or q is None or q == 0.0 or s.get('branch') not in self.idx:
                continue
            try:
                d = parse_date(s['date'])
            except Exception:
                continue
            rows.append((d, k, self.idx[s['branch']], dp, q))
        rows.sort()
        return rows

    def _airway_resistances(self):
        surv = {}
        for (d, k, i, dp, q) in self._survey_rows():
            surv.setdefault(i, []).append((d, k, dp / (q * abs(q))))
        work = {}
        for w in self.pkg.work:
            if not is_changing_work(w.get('work', '')):
                continue
            try:
                work.setdefault(w.get('branch', ''), []).append(parse_date(w['date']))
            except Exception:
                pass
        self.need, self.R_old = [], {}
        airway_R = []
        for i in range(self.nb):
            if self.kind[i] != 'airway':
                continue
            self.uncertain[i] = True
            ss = sorted(surv.get(i, []))
            wd = max(work.get(self.names[i], []), default=None)
            if not ss:
                self.need.append(i)
                self.R_old[i] = None
                continue
            d, _, R = ss[-1]
            # the latest survey gives the resistance; earlier surveys since the last work that
            # agree with it are readings of the same airway, and their mean is the better figure
            same = [x[2] for x in ss if (wd is None or x[0] > wd) and x[2] > 0 and R > 0
                    and abs(math.log(x[2] / R)) < 0.03]
            self.R0[i] = math.exp(sum(math.log(v) for v in same) / len(same)) if same else R
            airway_R.append(self.R0[i])
            if wd is None or wd < d:
                continue
            if wd == d:
                # work and survey on the same day: was the airway surveyed before or after it?
                prev = [x for x in ss if x[0] < d]
                if prev and R / prev[-1][2] < 0.85:
                    continue
            self.need.append(i)
            self.R_old[i] = R
        med = float(np.median(airway_R)) if airway_R else 0.01
        for i in self.need:
            if self.R_old[i] is None:
                self.R0[i] = med
                self.R_old[i] = med / PRIOR_RATIO

    # ---- what the survey campaigns say about the branches they did not survey
    def _campaigns(self):
        rows = self._survey_rows()
        groups, last = [], None
        for r in rows:
            if last is None or (r[0] - last).days > 10:
                groups.append({})
            groups[-1][r[2]] = (r[3], r[4])
            last = r[0]
        return groups

    def _campaign_estimates(self, S):
        """For one campaign S {branch: (dp, q)}: pressure difference and airflow of every other
        branch they determine, with the sd of the airflow."""
        nn = len(self.nodes)
        par = list(range(nn))

        def find(x):
            while par[x] != x:
                par[x] = par[par[x]]
                x = par[x]
            return x
        for i in S:
            par[find(self.fr[i])] = find(self.to[i])
        rows, rhs = [], []
        for i, (dp, q) in S.items():
            w = 1.0 / (READ_SD * abs(dp) + 1e-3)
            rows.append((self.fr[i], self.to[i], w))
            rhs.append(dp * w)
        anchors = {}
        for x in range(nn):
            anchors.setdefault(find(x), x)
        atm = self.nodes['ATM']
        anchors[find(atm)] = atm
        M = np.zeros((len(rows) + len(anchors), nn))
        y = np.zeros(len(rows) + len(anchors))
        for k, (a, b, w) in enumerate(rows):
            M[k, a] += w
            M[k, b] -= w
            y[k] = rhs[k]
        for k, x in enumerate(anchors.values()):
            M[len(rows) + k, x] = 1.0
        p = np.linalg.lstsq(M, y, rcond=None)[0]
        flow = {i: (q, (READ_SD * q) ** 2) for i, (dp, q) in S.items()}
        changed = True
        while changed:
            changed = False
            new = {}
            for node in range(nn):
                unk = [i for i in self.incident[node] if i not in flow]
                if len(unk) != 1:
                    continue
                j = unk[0]
                bal, var = 0.0, 0.0
                for i in self.incident[node]:
                    if i == j:
                        continue
                    qi, vi = flow[i]
                    bal += qi if self.to[i] == node else -qi
                    var += vi
                qj = bal if self.fr[j] == node else -bal
                new.setdefault(j, []).append((qj, var))
            for j, ests in new.items():
                w = [1.0 / max(v, 1e-12) for _, v in ests]
                qj = sum(e[0] * wi for e, wi in zip(ests, w)) / sum(w)
                flow[j] = (qj, 1.0 / sum(w))
                changed = True
        out = {}
        for j, (qj, var) in flow.items():
            if j in S or find(self.fr[j]) != find(self.to[j]):
                continue
            out[j] = (float(p[self.fr[j]] - p[self.to[j]]), qj, math.sqrt(var) + 1e-3)
        return out

    def _campaign_evidence(self):
        groups = self._campaigns()
        if not groups:
            return
        ests = {}
        for S in groups:
            for j, e in self._campaign_estimates(S).items():
                ests.setdefault(j, []).append(e)
        self.campaign_notes = []
        for j, el in ests.items():
            if self.kind[j] == 'stopping':
                ref = [self.R0[j]]
            elif self.kind[j] == 'door' and self.item[j] in self.door_tab:
                ref = self.door_tab[self.item[j]]
            else:
                continue

            def z(e, R):
                dp, q, sd = e
                qe = math.copysign(math.sqrt(abs(dp) / R), dp) if R > 0 else 0.0
                return (q - qe) / sd, qe
            dp, q, sd = el[-1]
            if abs(dp) < 1.0 or abs(q) < 3 * sd or (q > 0) != (dp > 0):
                continue
            zs = [z(el[-1], R) for R in ref]
            if min(abs(t[0]) for t in zs) < 6.0:
                continue                      # holds to its register resistance (or a table one)
            if self.kind[j] == 'door':
                c, o = ref
                k_now = abs(q) / math.sqrt(abs(dp))
                if not (1 / math.sqrt(c) < k_now < 1 / math.sqrt(o)):
                    continue
            # the latest campaign, with the earlier ones that agree with it
            k_l = q / math.sqrt(abs(dp))
            ks, ws = [], []
            for (dpc, qc, sdc) in reversed(el):
                if abs(dpc) < 1.0:
                    break
                kc, skc = qc / math.sqrt(abs(dpc)), sdc / math.sqrt(abs(dpc))
                if abs(kc - k_l) > 4 * skc + 0.02 * abs(k_l):
                    break
                ks.append(kc)
                ws.append(1.0 / skc ** 2)
            k = sum(a * w for a, w in zip(ks, ws)) / sum(ws)
            Rn = 1.0 / (k * k)
            if self.kind[j] == 'stopping':
                self.campaign_notes.append((self.names[j], self.R0[j], Rn))
                self.R0[j] = Rn
                self.uncertain[j] = True
            else:
                self.campaign_notes.append((self.names[j], self.door_tab[self.item[j]][0], Rn))
                self.door_tab[self.item[j]][0] = Rn
        dbg('campaign evidence:', self.campaign_notes)

    # ---- settings -> resistances
    def reg_res(self, item, s):
        tab = self.reg_tab.get(item)
        if not tab:
            return 0.0
        if s <= tab[0][0]:
            return tab[0][1]
        if s >= tab[-1][0]:
            return tab[-1][1]
        for k in range(len(tab) - 1):
            a, ra = tab[k]
            b, rb = tab[k + 1]
            if a <= s <= b:
                if b == a:
                    return rb
                t = (s - a) / (b - a)
                if ra > 0 and rb > 0:
                    return math.exp(math.log(ra) * (1 - t) + math.log(rb) * t)
                return ra * (1 - t) + rb * t
        return tab[-1][1]

    def door_res(self, item, u):
        c, o = self.door_tab.get(item, (0.0, 0.0))
        if u <= 0.0:
            return c
        if u >= 1.0:
            return o
        if c > 0 and o > 0:
            return math.exp(math.log(c) * (1 - u) + math.log(o) * u)
        return c * (1 - u) + o * u

    def item_res(self, item, v):
        if item in self.door_tab:
            return self.door_res(item, v)
        return self.reg_res(item, v)

    def resistances(self, Rbase, settings):
        R = Rbase.copy()
        for item, brs in self.item_br.items():
            if item in settings:
                r = self.item_res(item, settings[item])
                for i in brs:
                    R[i] = r
        return R

    def regime(self, q):
        return tuple(fc.branch(float(q[i])) for i, fc in zip(self.fan_br, self.fan_curve))

    # ---- co-content, its gradient and curvature
    def evaluate(self, l, R):
        q = self.C @ l
        aq = np.abs(q)
        dp = R * q * aq
        r = 2.0 * R * np.maximum(aq, 1e-6)
        F = float(np.dot(R, aq * aq * aq)) / 3.0
        for i, fc in zip(self.fan_br, self.fan_curve):
            qi = float(q[i])
            p, s, integ = fc.eval(qi)
            dp[i] -= p
            r[i] = 2.0 * R[i] * abs(qi) - s
            F -= integ
        return F, self.CT @ dp, r, q

    def hessian(self, r):
        return (self.CT * r) @ self.C

    def minimize(self, l, R, maxit=200, qtol=1e-7, maxstep=8.0, leash=None):
        """Local minimum of the co-content from l (a descent: it never climbs to a saddle).
        With leash (q0, limits), give up as soon as a fan's flow strays beyond its limit
        from q0: the minimum sought is then not the one nearby."""
        F, g, r, q = self.evaluate(l, R)
        n = self.nl
        for it in range(maxit):
            H = self.hessian(r)
            pd = True
            try:
                d = -cho_solve(cho_factor(H, check_finite=False), g, check_finite=False)
            except LinAlgError:
                pd = False
                d = None
                lam = 1e-6 * float(np.max(np.abs(np.diag(H)))) + 1e-9
                for _ in range(40):
                    try:
                        d = -cho_solve(cho_factor(H + lam * np.eye(n), check_finite=False), g,
                                       check_finite=False)
                        break
                    except LinAlgError:
                        lam *= 10.0
                if d is None or np.max(np.abs(self.C @ d)) < 1e-6:
                    # at (or next to) a saddle: step along the direction of negative curvature
                    w, V = np.linalg.eigh(H)
                    v = V[:, 0]
                    d = v / max(float(np.max(np.abs(self.C @ v))), 1e-12)
                    if self.evaluate(l + d, R)[0] > self.evaluate(l - d, R)[0]:
                        d = -d
            dq = self.C @ d
            mq = float(np.max(np.abs(dq))) if dq.size else 0.0
            if pd and mq < qtol:
                l = l + d
                F, g, r, q = self.evaluate(l, R)
                return l, q, r, True
            if mq > maxstep:
                d = d * (maxstep / mq)
            gd = float(g @ d)
            t = 1.0
            slack = 1e-13 * (abs(F) + 1.0)
            while True:
                ln = l + t * d
                Fn, gn, rn, qn = self.evaluate(ln, R)
                if Fn <= F + 1e-4 * t * min(gd, 0.0) + slack or t < 1e-10:
                    break
                t *= 0.5
            l, F, g, r, q = ln, Fn, gn, rn, qn
            if leash is not None:
                q0, lim = leash
                if any(abs(float(q[i] - q0[i])) > lm for i, lm in zip(self.fan_br, lim)):
                    return l, q, r, False
        return l, q, r, False

    def follow(self, l, q, Rfun):
        """Track the local minimum from u=0 to u=1 along the resistance path Rfun(u).  Where
        it ceases to exist the flow drops into the minimum below."""
        u, h, hmin = 0.0, 1.0, 1.0 / 2048
        jmax = [max(0.015 * fc.qfree, 0.5) for fc in self.fan_curve]
        while u < 1.0:
            un = min(1.0, u + h)
            R = Rfun(un)
            if h > hmin:
                ln, qn, rn, ok = self.minimize(l, R, leash=(q, [2 * j for j in jmax]))
            else:
                ln, qn, rn, ok = self.minimize(l, R, maxit=1000)
            jump = max([abs(float(qn[i] - q[i])) / jm for i, jm in zip(self.fan_br, jmax)],
                       default=0.0)
            if (ok and jump <= 1.0) or h <= hmin:
                l, q = ln, qn
                u = un
                if jump < 0.3:
                    h = min(1.0, 2.0 * h)
            else:
                h *= 0.5
        return l, q


# ------------------------------------------------------------------------ timeline


class Timeline:
    def __init__(self, net, pkg):
        self.net = net
        rows = []
        for k, e in enumerate(pkg.log):
            try:
                rows.append((parse_time(e['time']), k, e['item'], e['setting']))
            except Exception:
                continue
        rows.sort()
        self.t0 = rows[0][0] if rows else None
        init, changes = {}, []
        for (t, k, item, s) in rows:
            if t == self.t0:
                init[item] = self.value(item, s)
            else:
                changes.append((t, item, self.value(item, s)))
        for item in net.item_br:
            if item not in init:
                later = [c[2] for c in changes if c[1] == item]
                if item in net.door_tab:
                    init[item] = 0.0
                elif later:
                    init[item] = later[0]
                else:
                    tab = net.reg_tab.get(item)
                    init[item] = tab[-1][0] if tab else 10.0
        self.init, self.changes = init, changes
        pts = []
        for k, p in enumerate(pkg.points):
            try:
                t = parse_time(p['time'])
            except Exception:
                t = self.t0 or datetime.min
            pts.append((t, k, p['point'], p['branch']))
        pts.sort()
        self.points = pts
        self.final = dict(init)
        for (_, item, v) in changes:
            self.final[item] = v

    def value(self, item, s):
        if item in self.net.door_tab:
            return door_value(s)
        v = fnum(s)
        return door_value(s) if v is None else v


def start_guess(net, targets):
    return np.linalg.lstsq(net.C[net.fan_br], np.asarray(targets, dtype=float), rcond=None)[0]


def initial_states(net, R):
    """The distinct local minima at the opening settings, the one with most air first."""
    found = []
    combos = list(product([0.8, 0.3], repeat=net.nf)) if 0 < net.nf <= 4 else [None]
    for combo in combos:
        if combo is None:
            l0 = start_guess(net, [0.8 * fc.qfree for fc in net.fan_curve]) if net.nf else np.zeros(net.nl)
        else:
            l0 = start_guess(net, [c * fc.qfree for c, fc in zip(combo, net.fan_curve)])
        l, q, r, ok = net.minimize(l0, R, maxit=1000)
        fq = np.array([q[i] for i in net.fan_br])
        if any(np.max(np.abs(fq - f[2])) < 0.5 for f in found if len(fq)):
            continue
        found.append((l, q, fq))
        if not net.nf:
            break
    found.sort(key=lambda f: -float(np.sum(f[2])))
    return found


def simulate(net, tl, Rbase, l_init):
    """Run the record from the opening state l_init.  Returns the state at every point time
    and the final state (after the last log entry)."""
    settings = dict(tl.init)
    R = net.resistances(Rbase, settings)
    l, q, r, ok = net.minimize(l_init, R, maxit=1000)
    states = {}
    pi, pts = 0, tl.points
    for ci in range(len(tl.changes) + 1):
        tlim = tl.changes[ci][0] if ci < len(tl.changes) else None
        while pi < len(pts) and (tlim is None or pts[pi][0] < tlim):
            if pts[pi][0] not in states:
                states[pts[pi][0]] = (l, q, R)
            pi += 1
        if tlim is None:
            break
        _, item, new = tl.changes[ci]
        old = settings.get(item, new)
        if item not in net.item_br or old == new:
            settings[item] = new
            continue
        brs = net.item_br[item]

        def Rfun(u, R=R, item=item, old=old, new=new, brs=brs):
            Rn = R.copy()
            v = net.item_res(item, old + (new - old) * u)
            for i in brs:
                Rn[i] = v
            return Rn
        l, q = net.follow(l, q, Rfun)
        settings[item] = new
        R = net.resistances(Rbase, settings)
    return states, (l, q, R)


# ------------------------------------------------------------------ scenarios


SCALES = [1.0, 0.995, 1.005, 0.99, 1.01, 0.98, 1.02]
SCALE_SD = 0.005


class Scenario:
    pass


def scaled(net, Rbase, s):
    R = Rbase.copy()
    R[net.uncertain] *= s
    return R


def to_nominal(net, l, R_s, s, regime):
    """The same steady state in the unscaled network, if it holds there."""
    if s == 1.0:
        return None
    R = R_s.copy()
    R[net.uncertain] /= s
    ln, qn, rn, ok = net.minimize(l, R, maxit=300)
    if ok and net.regime(qn) == regime:
        return ln, qn
    return None


def run_scenarios(net, tl, Rbase, starts, scales=SCALES, obs=None):
    """The record run from each opening state, with the estimated resistances scaled by each
    factor.  With readings obs, a scenario whose prior alone exceeds the best score found is
    not run."""
    seen = {}
    best = [float('inf')]
    jobs = []
    for k, st in enumerate(starts):
        for s in (scales if k == 0 else [1.0]):
            jobs.append((((s - 1.0) / SCALE_SD) ** 2 + (9.0 if k else 0.0), k, s, st))
    jobs.sort(key=lambda j: j[0])
    for prior, k, s, st in jobs:
        if obs and prior >= best[0]:
            continue
        Rs = scaled(net, Rbase, s)
        R0 = net.resistances(Rs, tl.init)
        l0, q0, r0, ok = net.minimize(st[0], R0, maxit=1000)
        states, end = simulate(net, tl, Rs, l0)
        sc = Scenario()
        sc.start, sc.scale = k, s
        sc.prior = ((s - 1.0) / SCALE_SD) ** 2 + (9.0 if k else 0.0)
        sc.states, sc.end = states, end
        sc.history = tuple(net.regime(states[t][1]) for t in sorted(states)) + (net.regime(end[1]),)
        nom = to_nominal(net, end[0], end[2], s, net.regime(end[1]))
        sc.end_q = nom[1] if nom else end[1]
        sc.end_l = nom[0] if nom else end[0]
        if obs:
            best[0] = min(best[0], chi2(net, sc, obs) + sc.prior)
        key = sc.history
        if key in seen and seen[key].prior <= sc.prior:
            continue
        seen[key] = sc
    out = sorted(seen.values(), key=lambda c: c.prior)
    for sc in out:
        dbg('scenario start %d scale %.3f prior %.1f end fans %s' % (
            sc.start, sc.scale, sc.prior, [round(float(sc.end[1][i]), 1) for i in net.fan_br]))
    return out


def chi2(net, sc, obs):
    c = 0.0
    for b, (dp, qm) in obs.items():
        c += ((qm - sc.end_q[net.idx[b]]) / q_sigma(qm)) ** 2
    return c


def scenario_results(net, tl, sc):
    """Flows at every point, in the unscaled network wherever the scenario's state holds there."""
    res = {}
    cache = {}
    for (t, _, name, b) in tl.points:
        if t not in cache:
            l, q, R = sc.states[t]
            nom = to_nominal(net, l, R, sc.scale, net.regime(q))
            cache[t] = nom[1] if nom else q
        j = net.idx.get(b)
        res[name] = float(cache[t][j]) if j is not None else 0.0
    return res


# ------------------------------------------------------------- survey order


def sens(net, l, R, cols):
    """dq/dlog R_j for the branches j in cols, at the minimum l."""
    F, g, r, q = net.evaluate(l, R)
    H = net.hessian(r)
    B = net.CT[:, cols] * (R[cols] * q[cols] * np.abs(q[cols]))
    try:
        X = np.linalg.solve(H, B)
    except np.linalg.LinAlgError:
        X = np.linalg.lstsq(H, B, rcond=None)[0]
    return -(net.C @ X), q


def design(net, tl, sc, need, allowance):
    """More re-worked airways than the crew will take: choose the order that leaves the least
    uncertainty in the results (linearised, greedy)."""
    m = len(need)
    pos = {}
    for (t, _, name, b) in tl.points:
        if b in net.idx:
            pos.setdefault(t, []).append(net.idx[b])
    rows = []
    for t, (l, q, R) in sc.states.items():
        S, qq = sens(net, l, R, need)
        for j in pos.get(t, []):
            rows.append(S[j] / max(0.015 * abs(qq[j]), 0.03))
    A = np.array(rows) if rows else np.zeros((1, m))
    Se, qe = sens(net, sc.end[0], sc.end[2], need)
    Sig = np.eye(m) * PRIOR_SIGMA ** 2
    airways = [i for i in range(net.nb) if net.kind[i] == 'airway']

    def update(Sig, h, s2):
        hs = Sig @ h
        return Sig - np.outer(hs, hs) / (h @ hs + s2)
    chosen = []
    for _ in range(allowance):
        best = None
        for c in airways:
            if c in chosen:
                continue
            S2 = Sig
            if c in need:
                e = np.zeros(m)
                e[need.index(c)] = 1.0
                S2 = update(S2, e, (2.5 * READ_SD) ** 2)
            S2 = update(S2, Se[c], q_sigma(qe[c]) ** 2)
            score = float(np.trace(A @ S2 @ A.T))
            if best is None or score < best[0]:
                best = (score, c, S2)
        if best is None:
            break
        chosen.append(best[1])
        Sig = best[2]
    return chosen


def discriminating(net, scens, exclude, need_obs):
    """An airway whose reading now tells apart the plausible histories that end differently,
    if the airways ordered anyway do not."""
    plaus = [sc for sc in scens if sc.prior <= 9.0]
    if len(plaus) < 2:
        return None
    groups = {}
    for sc in plaus:
        groups.setdefault(net.regime(sc.end[1]), sc)
    if len(groups) < 2:
        return None
    reps = list(groups.values())

    def power(i):
        best = None
        for a in range(len(reps)):
            for b in range(a + 1, len(reps)):
                d = abs(reps[a].end_q[i] - reps[b].end_q[i]) / q_sigma(reps[a].end_q[i])
                best = d if best is None else min(best, d)
        return best
    if need_obs and max(power(i) for i in need_obs) > 10.0:
        return None
    cand = [i for i in range(net.nb) if net.kind[i] == 'airway' and i not in exclude]
    if not cand:
        return None
    c = max(cand, key=power)
    return c if power(c) > 3.0 else None


def place_order(pkg_dir, names):
    if not names:
        return {}
    try:
        p = subprocess.run(['pqsurvey', pkg_dir] + names, capture_output=True, text=True,
                           timeout=20)
    except Exception as e:
        sys.stderr.write('pqsurvey failed: %s\n' % e)
        return {}
    if p.returncode != 0 or DEBUG:
        sys.stderr.write('pqsurvey %s -> rc %s\n%s\n%s\n' % (' '.join(names), p.returncode,
                                                         p.stdout.strip(), p.stderr.strip()))
    out = {}
    for line in p.stdout.splitlines():
        parts = [x.strip() for x in line.split(',')]
        if len(parts) < 3:
            continue
        dp, q = fnum(parts[1]), fnum(parts[2])
        if dp is None or q is None:
            continue
        out[parts[0]] = (dp, q)
    return out


def infer(net, tl, Rbase, unknown, obs, l_end, scale=1.0):
    """MAP estimate of the resistances of the re-worked airways the crew did not reach, from
    the airflows the crew read in the district as it stands now (the final state l_end, in the
    network scaled by scale).  Returns the resistances, the misfit of the readings and the
    prior penalty of the estimate, and the largest move from the prior in sd."""
    theta0 = np.array([math.log(net.R_old[i] * PRIOR_RATIO) for i in unknown])
    theta = theta0.copy()
    oi = [net.idx[b] for b in obs]
    qm = np.array([obs[b][1] for b in obs])
    sg = np.array([q_sigma(v) for v in qm])
    Rf = net.resistances(scaled(net, Rbase, scale), tl.final)
    l = l_end
    misfit = None
    for it in range(12):
        Rc = Rf.copy()
        for k, i in enumerate(unknown):
            Rc[i] = math.exp(theta[k]) * scale
        l, q, r, ok = net.minimize(l, Rc, maxit=500)
        S, q = sens(net, l, Rc, unknown)
        misfit = float(np.sum(((qm - q[oi]) / sg) ** 2))
        res = np.concatenate([(qm - q[oi]) / sg, (theta0 - theta) / PRIOR_SIGMA])
        J = np.vstack([S[oi] / sg[:, None], np.eye(len(unknown)) / PRIOR_SIGMA])
        step = np.clip(np.linalg.lstsq(J, res, rcond=None)[0], -0.7, 0.7)
        if it == 11 or np.max(np.abs(step)) < 1e-4:
            break
        theta = theta + step
    Rb = Rbase.copy()
    for k, i in enumerate(unknown):
        Rb[i] = math.exp(theta[k])
    dev = np.abs(theta - theta0) / PRIOR_SIGMA
    pen = float(np.sum(dev ** 2))
    dbg('inferred (scale %.3f) misfit %.1f penalty %.1f' % (scale, misfit, pen),
        [(net.names[i], round(net.R_old[i], 5), round(float(Rb[i]), 5)) for i in unknown])
    return Rb, misfit, pen, float(np.max(dev)) if len(dev) else 0.0


# ------------------------------------------------------------------------ main


def main():
    if len(sys.argv) < 3:
        sys.stderr.write('usage: airflow.py PACKAGE_DIR OUT_CSV\n')
        sys.exit(2)
    pkg_dir, out_csv = sys.argv[1], sys.argv[2]
    pkg = Package(pkg_dir)
    net = Network(pkg)
    tl = Timeline(net, pkg)
    need = list(net.need)
    Rbase = net.R0.copy()
    for i in need:                       # until the crew reports
        Rbase[i] = net.R_old[i] * PRIOR_RATIO
    starts = initial_states(net, net.resistances(Rbase, tl.init))
    dbg('need', [net.names[i] for i in need], 'allowance', pkg.allowance,
        'opening states', [[round(float(x), 1) for x in s[2]] for s in starts])

    # ---- the survey order
    allowance = max(pkg.allowance, 0)
    order = []
    if allowance > 0:
        if len(need) <= allowance:
            order = list(need)
            if not order:
                # nothing to resurvey: one reading of the district as it stands now still
                # tells which history it went through
                scens = run_scenarios(net, tl, Rbase, starts)
                c = discriminating(net, scens, set(), [])
                if c is None:
                    c = int(np.argmax([abs(scens[0].end_q[i]) if net.kind[i] == 'airway' else -1
                                       for i in range(net.nb)]))
                order = [c]
        else:
            sc0 = run_scenarios(net, tl, Rbase, starts[:1], scales=[1.0])[0]
            order = design(net, tl, sc0, need, allowance)
    obs = place_order(pkg_dir, [net.names[i] for i in order]) if order else {}

    flow_obs = {}
    for b, (dp, q) in obs.items():
        i = net.idx.get(b)
        if i is None or net.kind[i] != 'airway' or q == 0.0:
            continue
        flow_obs[b] = (dp, q)
        if i in need and dp / (q * abs(q)) > 0:
            Rbase[i] = dp / (q * abs(q))
    unknown = [i for i in need if net.names[i] not in flow_obs]
    if flow_obs:
        starts = initial_states(net, net.resistances(Rbase, tl.init))

    # ---- the record, and which history the district went through
    limit = max(25.0, 6.0 * len(flow_obs))
    best = run_scenarios(net, tl, Rbase, starts[:1], scales=[1.0])[0]
    if not flow_obs:
        pass
    elif not unknown:
        if chi2(net, best, flow_obs) > limit:
            # the readings do not fit the nominal history: a knife-edge event went the other way
            scens = run_scenarios(net, tl, Rbase, starts, obs=flow_obs)
            for sc in scens:
                dbg('  start %d scale %.3f prior %.1f chi2 %.1f' % (
                    sc.start, sc.scale, sc.prior, chi2(net, sc, flow_obs)))
            best = min(scens, key=lambda c: chi2(net, c, flow_obs) + c.prior)
    else:
        Rb, misfit, pen, dev = infer(net, tl, Rbase, unknown, flow_obs, best.end_l)
        choice = (best, Rb, misfit, dev)
        if misfit > limit or dev > 2.0:
            scored = []
            for sc in run_scenarios(net, tl, Rbase, starts):
                Rc, m, p, d = infer(net, tl, Rbase, unknown, flow_obs, sc.end[0], sc.scale)
                scored.append((m + p + sc.prior, sc, Rc, m, d))
                dbg('  start %d scale %.3f prior %.1f misfit %.1f penalty %.1f' % (
                    sc.start, sc.scale, sc.prior, m, p))
            choice = min(scored, key=lambda x: x[0])[1:]
        sc, Rb, misfit, dev = choice
        if misfit <= limit and dev <= 3.0:
            Rbase = Rb
        # otherwise the readings fit no history: something else is amiss, so they are not let
        # pull the unsurveyed airways about, which stay at the typical post-work resistance
        best = run_scenarios(net, tl, Rbase, [starts[sc.start]], scales=[sc.scale])[0]
        best.start = sc.start
    dbg('chosen start %d scale %.3f chi2 %.1f' % (best.start, best.scale, chi2(net, best, flow_obs)))
    res = scenario_results(net, tl, best)

    with open(out_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['point', 'flow_m3_s'])
        for p in pkg.points:
            w.writerow([p['point'], '%.4f' % res.get(p['point'], 0.0)])


if __name__ == '__main__':
    main()
