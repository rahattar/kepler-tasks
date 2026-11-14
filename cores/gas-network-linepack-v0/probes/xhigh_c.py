#!/usr/bin/env python3
"""Design-day governor inlet pressures to GD-3 for one network package.

    python3 designday.py PACKAGE_DIR OUT_CSV

Reads the ten files of the package, places the package's one order with the
field team (gdsurvey) for the items the records cannot settle, then runs the
GD-3 design day (240 implicit steps of 0.1 h, repeated until the day is
periodic) and writes the lowest pressure at every district governor.
"""
import os

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')

import sys
import csv
import json
import time
import math
import datetime
import subprocess

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

PATM = 1.01325          # bar
NEXP = 1.82             # p1^2 - p2^2 = K Q |Q|^0.82
DT = 0.1                # h
NSTEP = 240
K_CHANGING = ('RENEWED', 'RELINED', 'LAID')
METER_OK_PCT = 1.1      # a proved meter within this of 100 % is within its accuracy
PMIN_ABS = 0.05         # bar: floor on absolute pressure inside the Newton iterations
CPU_BUDGET = 7.0        # s of CPU after which the solver hurries (limit is 10 s per run)

# evidence thresholds for the survey campaigns on file
Z_FLAG = 3.0            # standard deviations of the readings (taken as 1 % each)
VALVE_MIN_Q = 20.0      # m3/h through a closed valve before it counts as passing
METER_MIN_REL = 0.015   # relative disagreement before a meter counts as faulty


def log(*a):
    print(*a, file=sys.stderr)


# --------------------------------------------------------------------------- input

def read_csv(path):
    if not os.path.exists(path):
        return [], []
    with open(path, newline='', encoding='utf-8-sig') as f:
        r = csv.reader(f)
        try:
            hdr = [h.strip().lower() for h in next(r)]
        except StopIteration:
            return [], []
        rows = []
        for row in r:
            row = [c.strip() for c in row]
            if any(row):
                rows.append(row + [''] * (len(hdr) - len(row)))
    return hdr, rows


def table(pkg, name):
    hdr, rows = read_csv(os.path.join(pkg, name))
    col = {h: i for i, h in enumerate(hdr)}
    return col, rows


def fnum(s, default=float('nan')):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def k_of(pf_abs, pt_abs, q):
    """Resistance from end pressures (absolute) and flow; nan if undetermined."""
    if not (math.isfinite(pf_abs) and math.isfinite(pt_abs) and math.isfinite(q)) or q == 0.0:
        return float('nan')
    k = (pf_abs * pf_abs - pt_abs * pt_abs) / (q * abs(q) ** (NEXP - 1.0))
    return k if (math.isfinite(k) and k > 0.0) else float('nan')


class Package:
    def __init__(self, pkg):
        self.pkg = pkg
        try:
            with open(os.path.join(pkg, 'network.json'), encoding='utf-8-sig') as f:
                meta = json.load(f)
        except Exception:
            meta = {}
        self.name = meta.get('network', '')
        try:
            self.allowance = int(meta.get('survey_allowance', 0))
        except (TypeError, ValueError):
            self.allowance = 0

        # mains and nodes
        c, rows = table(pkg, 'mains.csv')
        self.mains = []
        self.node_index = {}
        self.nodes = []
        for r in rows:
            m = r[c['main']]
            a, b = r[c['from_node']], r[c['to_node']]
            for n in (a, b):
                if n not in self.node_index:
                    self.node_index[n] = len(self.nodes)
                    self.nodes.append(n)
            self.mains.append(dict(name=m, f=a, t=b, L=fnum(r[c['length_m']]),
                                   D=fnum(r[c['diameter_mm']]) / 1000.0,
                                   mat=r[c['material']].strip() if 'material' in c else ''))
        self.main_index = {m['name']: j for j, m in enumerate(self.mains)}

        # surveys: per main, list of (date, p_from_barg, dp_bar, q)
        c, rows = table(pkg, 'surveys.csv')
        self.surveys = {}
        self.campaigns = {}
        for r in rows:
            rec = (r[c['date']], fnum(r[c['p_from_barg']]), fnum(r[c['dp_bar']]), fnum(r[c['q_m3h']]))
            self.surveys.setdefault(r[c['main']], []).append(rec)
            self.campaigns.setdefault(rec[0], {})[r[c['main']]] = rec[1:]
        for v in self.surveys.values():
            v.sort()

        # work log
        c, rows = table(pkg, 'work_log.csv')
        self.lastwork = {}
        for r in rows:
            if r[c['work']].strip().upper() in K_CHANGING:
                m, d = r[c['main']], r[c['date']]
                if m not in self.lastwork or d > self.lastwork[m]:
                    self.lastwork[m] = d

        c, rows = table(pkg, 'prs.csv')
        self.prs = [dict(name=r[c['prs']], node=r[c['node']], set=fnum(r[c['set_point_barg']]),
                         cap=fnum(r[c['capacity_m3h']])) for r in rows]
        self.prs = [p for p in self.prs if p['node'] in self.node_index]

        c, rows = table(pkg, 'boundary_valves.csv')
        self.valves = [dict(name=r[c['valve']], node=r[c['node']],
                            p_nb=fnum(r[c['neighbour_pressure_barg']]),
                            state=r[c['state']].strip().lower()) for r in rows]
        self.valves = [v for v in self.valves if v['node'] in self.node_index]

        c, rows = table(pkg, 'governors.csv')
        self.governors = [(r[c['governor']], r[c['node']]) for r in rows]
        c, rows = table(pkg, 'design_day.csv')
        self.gov_demand = {}
        for r in rows:
            g = r[c['governor']]
            h = fnum(r[c['hour']])
            if not math.isfinite(h):
                continue
            h = int(h) % 24
            self.gov_demand.setdefault(g, np.zeros(24))[h] += fnum(r[c['demand_m3h']], 0.0)

        c, rows = table(pkg, 'customers.csv')
        self.customers = [dict(name=r[c['customer']], node=r[c['node']], meter=r[c['meter']]) for r in rows]
        self.customers = [cu for cu in self.customers if cu['node'] in self.node_index]
        meters = {cu['meter'] for cu in self.customers}
        c, rows = table(pkg, 'customer_meters.csv')
        self.meter_sum = {m: np.zeros(24) for m in meters}
        self.meter_cnt = {m: np.zeros(24) for m in meters}
        self.meter_at = {m: {} for m in meters}
        wd = {}
        it, im, iq = c.get('time'), c.get('meter'), c.get('q_m3h')
        for r in rows:
            m = r[im]
            if m not in meters:
                continue
            ts = r[it]
            q = fnum(r[iq])
            if not math.isfinite(q):
                continue
            ds = ts[:10]
            w = wd.get(ds)
            if w is None:
                try:
                    w = datetime.date(int(ds[0:4]), int(ds[5:7]), int(ds[8:10])).weekday() < 5
                except ValueError:
                    w = False
                wd[ds] = w
            hh = ts[11:13]
            self.meter_at[m][ts[:16]] = q
            if w and hh.isdigit():
                h = int(hh) % 24
                self.meter_sum[m][h] += q
                self.meter_cnt[m][h] += 1


# --------------------------------------------------------------------------- records analysis

class Analysis:
    """What the records settle, what they do not, and the evidence of the survey campaigns."""

    def __init__(self, P):
        self.P = P
        nm = len(P.mains)
        self.K = np.full(nm, np.nan)
        self.K_basis = [''] * nm
        self.need_mains = []        # (priority, name)
        self.ambiguous = []         # (priority, name, fallbackK)
        for j, m in enumerate(P.mains):
            name = m['name']
            ss = P.surveys.get(name, [])
            w = P.lastwork.get(name)
            after = [s for s in ss if w is None or s[0] > w]
            same = [s for s in ss if w is not None and s[0] == w]
            k = float('nan')
            if after and after[-1][3] == 0.0 and abs(after[-1][2]) > 1e-3:
                k = float('inf')               # a pressure difference and no flow: passes nothing
            else:
                for s in reversed(after):      # latest survey that gives a K
                    pf = s[1] + PATM
                    k = k_of(pf, pf - s[2], s[3])
                    if math.isfinite(k):
                        break
            if math.isfinite(k) or k == float('inf'):
                self.K[j] = k
                self.K_basis[j] = 'survey'
                continue
            dpw = max([abs(s[2]) for s in ss if math.isfinite(s[2])] or [0.05])
            if same:
                s = same[-1]
                pf = s[1] + PATM
                self.ambiguous.append((dpw, name, k_of(pf, pf - s[2], s[3])))
            self.need_mains.append((dpw, name))
        self._fit_class_constants()
        self._campaign_evidence()

    # K ~ c L / D^4.848 by material class, for mains with no usable survey
    @staticmethod
    def mat_class(mat):
        m = mat.upper()
        return 'PE' if m.startswith('PE') else m

    def _fit_class_constants(self):
        P = self.P
        vals = {}
        allv = []
        for j, m in enumerate(P.mains):
            if self.K_basis[j] == 'survey' and math.isfinite(self.K[j]) and m['L'] > 0 and m['D'] > 0:
                cval = self.K[j] * m['D'] ** 4.848 / m['L']
                vals.setdefault(self.mat_class(m['mat']), []).append(cval)
                allv.append(cval)
        self.cclass = {k: float(np.median(v)) for k, v in vals.items()}
        self.call = float(np.median(allv)) if allv else 1.1e-13
        if 'PE' not in self.cclass:
            self.cclass['PE'] = 8.65e-14

    def estimate_K(self, j):
        m = self.P.mains[j]
        c = self.cclass.get(self.mat_class(m['mat']), self.call)
        L = m['L'] if m['L'] > 0 else 800.0
        D = m['D'] if m['D'] > 0 else 0.15
        return c * L / D ** 4.848

    def _campaign_evidence(self):
        """Flow balance at valve and customer nodes in every survey campaign on file."""
        P = self.P
        self.valve_ev = {}   # valve -> dict(z, q, p_node, date) from the latest campaign with readings
        self.meter_ev = {}   # meter -> dict(z, ratio, rel)
        camp_nodes = {}
        for date in sorted(P.campaigns):
            rec = P.campaigns[date]
            bal = {}
            var = {}
            pres = {}
            for mname, (pfb, dp, q) in rec.items():
                j = P.main_index.get(mname)
                if j is None or not (math.isfinite(q) and math.isfinite(pfb) and math.isfinite(dp)):
                    continue
                a, b = P.mains[j]['f'], P.mains[j]['t']
                bal[a] = bal.get(a, 0.0) - q
                bal[b] = bal.get(b, 0.0) + q
                var[a] = var.get(a, 0.0) + (0.01 * q) ** 2
                var[b] = var.get(b, 0.0) + (0.01 * q) ** 2
                pres.setdefault(a, []).append(pfb)
                pres.setdefault(b, []).append(pfb - dp)
            camp_nodes[date] = (bal, var, pres)
        dates = sorted(camp_nodes)
        for v in P.valves:
            n = v['node']
            per = []
            for date in dates:
                bal, var, pres = camp_nodes[date]
                if n in bal:
                    qin = -bal[n]                     # into the network through the valve
                    per.append((date, qin, qin / (math.sqrt(var[n]) + 1.0), float(np.mean(pres[n]))))
            if not per:
                self.valve_ev[v['name']] = None
                continue
            date, qin, zl, pnode = per[-1]
            zc = abs(sum(x[2] for x in per)) / math.sqrt(len(per))
            self.valve_ev[v['name']] = dict(date=date, q=qin, z=max(abs(zl), zc), z_latest=abs(zl),
                                            p_node=pnode, latest=(date == dates[-1]))
        for cu in P.customers:
            m = cu['meter']
            nums, dens, zs = [], [], []
            for date in dates:
                qm = P.meter_at.get(m, {}).get(date + ' 13:00')
                bal, var, pres = camp_nodes[date]
                n = cu['node']
                if qm is None or n not in bal:
                    continue
                qout = bal[n]                         # taken out of the mains at the node
                if qout <= 0:
                    continue
                sd = math.sqrt(var[n] + (0.01 * qm) ** 2) + 1.0
                nums.append(qm)
                dens.append(qout)
                zs.append((qm - qout) / sd)
            if nums:
                ratio = sum(nums) / sum(dens)
                z = abs(sum(zs)) / math.sqrt(len(zs))
                self.meter_ev[m] = dict(ratio=ratio, rel=abs(ratio - 1.0), z=z, n=len(nums))
            else:
                self.meter_ev[m] = None

    def valve_passing(self, v):
        ev = self.valve_ev.get(v['name'])
        return ev is not None and ev['z'] > Z_FLAG and abs(ev['q']) > VALVE_MIN_Q

    def meter_faulty(self, m):
        ev = self.meter_ev.get(m)
        return ev is not None and ev['z'] > Z_FLAG and ev['rel'] > METER_MIN_REL

    # ------------------------------------------------------------------ the order
    def candidates(self):
        """Every item the field team could usefully be asked for, most needed first."""
        P = self.P
        items = []   # (tier, score, name)
        for dpw, name in self.need_mains:
            amb = any(a[1] == name for a in self.ambiguous)
            items.append((2 if not amb else 4, dpw, name))
        for v in P.valves:
            ev = self.valve_ev.get(v['name'])
            passing = self.valve_passing(v)
            if v['state'] != 'closed':
                # open: its K can only come from a survey across it, unless the campaigns
                # show it passing nothing against a clear pressure difference
                shut = (ev is not None and ev['z'] < 2.0 and math.isfinite(v['p_nb'])
                        and abs(v['p_nb'] - ev['p_node']) > 0.05)
                items.append((1 if passing else (3 if shut else 0), ev['z'] if ev else 0.0, v['name']))
            elif passing:
                items.append((1, ev['z'] + (100.0 if ev['latest'] else 0.0), v['name']))
            else:
                items.append((6 if ev else 5, ev['z'] if ev else 0.0, v['name']))
        for cu in P.customers:
            m = cu['meter']
            ev = self.meter_ev.get(m)
            flow = float(np.sum(P.meter_sum[m] / np.maximum(P.meter_cnt[m], 1)))
            if self.meter_faulty(m):
                items.append((1, ev['z'], m))
            elif ev is None:
                items.append((5, 1.0 + flow * 1e-9, m))
            else:
                items.append((6, ev['z'] + flow * 1e-9, m))
        items.sort(key=lambda x: (x[0], -x[1]))
        return items


# --------------------------------------------------------------------------- field team

def place_order(pkg, items, allowance):
    order = []
    seen = set()
    for it in items:
        if it[2] not in seen:
            seen.add(it[2])
            order.append(it[2])
    order = order[:max(0, allowance)]
    res = {'main': {}, 'valve': {}, 'meter': {}}
    if not order:
        return order, res, 'nothing to order'
    try:
        cp = subprocess.run(['gdsurvey', pkg] + order, capture_output=True, text=True, timeout=60)
    except Exception as e:  # not on PATH, timed out, ...
        return order, res, 'gdsurvey failed: %r' % (e,)
    if cp.returncode != 0:
        return order, res, 'gdsurvey refused: %s %s' % (cp.stdout.strip(), cp.stderr.strip())
    kind = None
    for line in cp.stdout.splitlines():
        parts = [x.strip() for x in line.strip().split(',')]
        if not parts or not parts[0]:
            continue
        head = parts[0].lower()
        if head in ('main', 'valve', 'meter') and len(parts) > 1 and not _isnum(parts[1]):
            kind = head
            continue
        if kind is None:
            continue
        vals = [fnum(x) for x in parts[1:]]
        if kind == 'meter':
            if vals and math.isfinite(vals[0]):
                res['meter'][parts[0]] = vals[0]
        elif len(vals) >= 3:
            res[kind][parts[0]] = tuple(vals[:3])
    return order, res, 'ok'


def _isnum(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------------- the network model

class Model:
    def __init__(self, P, A, field):
        N = len(P.nodes)
        self.N = N
        idx = P.node_index
        fi = np.array([idx[m['f']] for m in P.mains], dtype=np.int64)
        ti = np.array([idx[m['t']] for m in P.mains], dtype=np.int64)
        K = A.K.copy()
        self.notes = []
        # mains the records do not settle
        amb = {a[1]: a[2] for a in A.ambiguous}
        for _, name in A.need_mains:
            j = P.main_index[name]
            k = float('nan')
            if name in field['main']:
                pfb, dp, q = field['main'][name]
                k = k_of(pfb + PATM, pfb + PATM - dp, q)
                if not math.isfinite(k) and q == 0.0 and abs(dp) > 1e-3:
                    k = float('inf')   # a pressure difference and no flow: the main passes nothing
            if not (math.isfinite(k) or k == float('inf')):
                est = A.estimate_K(j)
                ka = amb.get(name, float('nan'))
                k = ka if (math.isfinite(ka) and 0.85 < ka / est < 1.15) else est
                self.notes.append('K of %s estimated (%.3g)' % (name, k))
            K[j] = k
        bad = ~np.isfinite(K) & ~np.isinf(K)
        for j in np.nonzero(bad)[0]:
            K[j] = A.estimate_K(j)
        keep = ~np.isinf(K)
        fi, ti, K = fi[keep], ti[keep], K[keep]
        self.fi, self.ti = fi, ti
        self.Kn = K ** (1.0 / NEXP)
        # linepack: half of every main's geometric volume at each end (all mains of the register)
        V = np.zeros(N)
        for m in P.mains:
            vol = math.pi * m['D'] ** 2 * m['L'] / 8.0
            if math.isfinite(vol) and vol > 0:
                V[idx[m['f']]] += vol
                V[idx[m['t']]] += vol
        self.C = V / PATM / DT
        # boundary valves that pass gas
        vn, vp, vk = [], [], []
        for v in P.valves:
            k = float('nan')
            surveyed = v['name'] in field['valve']
            if surveyed:
                pn, pnb, q = field['valve'][v['name']]
                if abs(q) > 1e-6:
                    k = k_of(pnb + PATM, pn + PATM, q)
                    if not math.isfinite(k):
                        self.notes.append('valve %s survey gives no K' % v['name'])
                        surveyed = False
            if not surveyed:
                ev = A.valve_ev.get(v['name'])
                if A.valve_passing(v):
                    k = k_of(v['p_nb'] + PATM, ev['p_node'] + PATM, ev['q'])
                    self.notes.append('valve %s K from campaign %s (%.3g)' % (v['name'], ev['date'], k))
                elif v['state'] != 'closed':
                    self.notes.append('open valve %s has no survey: taken as passing nothing' % v['name'])
            if math.isfinite(k) and k > 0 and math.isfinite(v['p_nb']):
                vn.append(idx[v['node']])
                vp.append(v['p_nb'] + PATM)
                vk.append(k)
        self.v_node = np.array(vn, dtype=np.int64)
        self.v_p = np.array(vp)
        self.v_Kn = np.array(vk) ** (1.0 / NEXP)
        # PRS
        self.prs_node = np.array([idx[p['node']] for p in P.prs], dtype=np.int64)
        self.prs_set = np.array([p['set'] + PATM for p in P.prs])
        self.prs_cap = np.array([max(p['cap'], 0.0) for p in P.prs])
        # demand by clock hour
        dem = np.zeros((24, N))
        for g, n in P.governors:
            if g in P.gov_demand and n in idx:
                dem[:, idx[n]] += P.gov_demand[g]
        for cu in P.customers:
            m = cu['meter']
            prof = P.meter_sum[m] / np.maximum(P.meter_cnt[m], 1)
            f = 1.0
            if m in field['meter']:
                pct = field['meter'][m]
                if pct > 0 and abs(pct - 100.0) > METER_OK_PCT:
                    f = pct / 100.0
                    self.notes.append('meter %s proved at %.1f%%' % (m, pct))
            else:
                ev = A.meter_ev.get(m)
                if A.meter_faulty(m):
                    f = ev['ratio']
                    self.notes.append('meter %s not proved: campaign ratio %.3f used' % (m, f))
            dem[:, idx[cu['node']]] += prof / f
        self.dem = dem

        # sparse Jacobian pattern (CSC)
        rows = np.concatenate([fi, fi, ti, ti, np.arange(N)])
        cols = np.concatenate([fi, ti, fi, ti, np.arange(N)])
        key = cols * N + rows
        uk, inv = np.unique(key, return_inverse=True)
        self.inv = inv
        self.nnz = len(uk)
        self.indices = (uk % N).astype(np.int32)
        self.indptr = np.searchsorted(uk // N, np.arange(N + 1)).astype(np.int32)
        self.rows = rows
        self.cscale = 1e5
        self.eps = 1e-10
        self.hurry = False
        self.failures = 0
        self.deadline = float('inf')

    # PRS modes: 0 holds the set point, 1 delivers its capacity, 2 delivers nothing
    def residual(self, p, pold, dem, modes, secant=None):
        """Node balances (m3/h) with the PRS rows in the given modes, and their Jacobian.

        modes None: the PRS rows are the semismooth form mid(s, s - cap, c (p - set)) = 0.
        secant: mains whose linearisation uses the secant conductance (flow reversals)."""
        N = self.N
        fi, ti = self.fi, self.ti
        pf = p[fi]
        pt = p[ti]
        d = pf * pf - pt * pt
        ad = np.abs(d)
        ade = ad + self.eps
        base = self.Kn * ade ** (1.0 - 1.0 / NEXP)
        q = d / base
        g = (ad / NEXP + self.eps) / (base * ade)
        if secant is not None:
            g = np.where(secant, 1.0 / base, g)
        F = np.bincount(ti, q, N) - np.bincount(fi, q, N) - dem - self.C * (p - pold)
        diag = -self.C.copy()
        if len(self.v_node):
            pv = p[self.v_node]
            dv = self.v_p * self.v_p - pv * pv
            adv = np.abs(dv)
            advd = adv + self.eps
            bv = self.v_Kn * advd ** (1.0 - 1.0 / NEXP)
            qv = dv / bv
            gv = (adv / NEXP + self.eps) / (bv * advd)
            np.add.at(F, self.v_node, qv)
            np.add.at(diag, self.v_node, -2.0 * gv * pv)
        R = F
        rowscale = None
        pn = self.prs_node
        if len(pn):
            R = F.copy()
            rowscale = np.ones(N)
            diagadd = np.zeros(N)
            hp = self.cscale * (p[pn] - self.prs_set)
            if modes is None:
                a = -F[pn]
                b = a - self.prs_cap
                hold = (hp <= a) & (hp >= b)
                R[pn] = np.maximum(b, np.minimum(a, hp))     # mid(a, b, hp), b <= a
                rowscale[pn] = np.where(hold, 0.0, -1.0)
            else:
                hold = modes == 0
                R[pn] = np.where(hold, hp, F[pn] + np.where(modes == 1, self.prs_cap, 0.0))
                rowscale[pn] = np.where(hold, 0.0, 1.0)
            diagadd[pn] = np.where(hold, self.cscale, 0.0)
        gf = 2.0 * g * pf
        gt = 2.0 * g * pt
        vals = np.concatenate([-gf, gt, gf, -gt, diag])
        if rowscale is not None:
            vals *= rowscale[self.rows]
            vals[-N:] += diagadd
        data = np.bincount(self.inv, vals, self.nnz)
        J = sp.csc_matrix((data, self.indices, self.indptr), shape=(N, N))
        return R, J, d > 0, F

    def _solve(self, J, b):
        try:
            return splu(J, permc_spec='MMD_AT_PLUS_A', diag_pivot_thresh=0.0,
                        options={'SymmetricMode': True}).solve(b)
        except RuntimeError:
            pass
        try:
            return splu(J).solve(b)
        except RuntimeError:
            return splu(J + sp.identity(self.N, format='csc') * 1e-3).solve(b)

    def newton(self, pold, dem, p, modes, tol=1e-7, maxit=40):
        if self.hurry:
            maxit = min(maxit, 8)
        R, J, sg, F = self.residual(p, pold, dem, modes)
        nr = np.max(np.abs(R))
        for it in range(maxit):
            dp = self._solve(J, -R)
            if not np.all(np.isfinite(dp)):
                return p, F, False
            if np.max(np.abs(dp)) < tol:
                p = p + dp
                R, J, sg, F = self.residual(p, pold, dem, modes)
                return p, F, True
            lam = 1.0
            while True:
                pn = np.maximum(p + lam * dp, PMIN_ABS)
                Rn, Jn, sgn, Fn = self.residual(pn, pold, dem, modes)
                nrn = np.max(np.abs(Rn))
                if nrn < nr or lam < 1e-3:
                    break
                lam *= 0.5
            flip = sgn != sg
            if flip.any():
                # a main whose flow reversed: its next linearisation uses the secant
                # conductance, which stops the overshoot of Q ~ dp^0.55 about zero
                Rn, Jn, sgn, Fn = self.residual(pn, pold, dem, modes, flip)
            p, R, J, nr, sg, F = pn, Rn, Jn, nrn, sgn, Fn
        return p, F, False

    def step(self, pold, dem, guess):
        """One implicit step: PRS modes by an active-set loop around Newton."""
        modes = self.modes.copy()
        p = guess
        ok = False
        tried = set()
        for outer in range(12):
            p, F, ok = self.newton(pold, dem, p, modes)
            if len(modes) == 0:
                break
            pn = self.prs_node
            s = -F[pn]                       # delivery the node needs
            pp = p[pn]
            new = modes.copy()
            new[(modes == 0) & (s > self.prs_cap * (1 + 1e-12) + 1e-9)] = 1
            new[(modes == 0) & (s < -1e-9)] = 2
            new[(modes == 1) & (pp > self.prs_set + 1e-12)] = 0
            new[(modes == 2) & (pp < self.prs_set - 1e-12)] = 0
            if np.array_equal(new, modes):
                break
            key = tuple(new)
            if key in tried:                 # cycling between mode sets
                ok = False
                break
            tried.add(tuple(modes))
            modes = new
        if not ok and not self.hurry:
            # fall back to the semismooth form of the PRS law
            p2, F2, ok2 = self.newton(pold, dem, p, None, maxit=80)
            if ok2:
                p = p2
                pn = self.prs_node
                s = -F2[pn]
                modes = np.where(s >= self.prs_cap, 1, np.where(s <= 0, 2, 0)).astype(int)
            else:
                self.failures += 1
        elif not ok:
            self.failures += 1
        self.modes = modes
        return p

    def day(self, p0):
        p = p0.copy()
        prev = None
        pmin = np.full(self.N, np.inf)
        for k in range(NSTEP):
            if not self.hurry and time.process_time() > self.deadline:
                self.hurry = True
                log('running short of time: Newton iterations limited')
            h = (6 + k // 10) % 24
            guess = p if prev is None else p + (p - prev)
            pn = self.step(p, self.dem[h], guess)
            prev, p = p, pn
            np.minimum(pmin, p, out=pmin)
        return p, pmin

    def periodic(self, cpu_budget=8.0, tol=1e-7, maxdays=60):
        """Repeat the design day from its own end state until the end state is its start."""
        t0 = time.process_time()
        self.deadline = t0 + cpu_budget
        self.hurry = False
        self.failures = 0
        self.modes = np.zeros(len(self.prs_node), dtype=int)
        top = float(np.max(self.prs_set)) if len(self.prs_set) else 7.0
        p = np.full(self.N, top)
        pmin = None
        err = float('inf')
        d = 0
        for d in range(maxdays):
            pe, pm = self.day(p)
            err = float(np.max(np.abs(pe - p)))
            dmin = float(np.max(np.abs(pm - pmin))) if pmin is not None else np.inf
            p, pmin = pe, pm
            if err < tol or (d >= 1 and dmin < 1e-6) or self.hurry:
                break
            used = time.process_time() - t0
            if used / (d + 1) * (d + 2) > cpu_budget:
                log('stopping after day %d for time (err %.2e)' % (d + 1, err))
                break
        return pmin, d + 1, err


# --------------------------------------------------------------------------- main

def main():
    if len(sys.argv) != 3:
        print('usage: python3 designday.py PACKAGE_DIR OUT_CSV', file=sys.stderr)
        sys.exit(2)
    pkg, out = sys.argv[1], sys.argv[2]
    t0 = time.process_time()
    P = Package(pkg)
    A = Analysis(P)
    items = A.candidates()
    order, field, status = place_order(pkg, items, P.allowance)
    log('order (%d of %d): %s -> %s' % (len(order), P.allowance, ' '.join(order), status))
    M = Model(P, A, field)
    for n in M.notes:
        log(n)
    pmin, days, err = M.periodic(cpu_budget=max(1.5, CPU_BUDGET - (time.process_time() - t0)))
    log('periodic after %d days (end-of-day change %.1e bar), %d unconverged steps, cpu %.2f s'
        % (days, err, M.failures, time.process_time() - t0))
    with open(out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['governor', 'min_pressure_barg'])
        for g, n in P.governors:
            if n in P.node_index:
                w.writerow([g, '%.4f' % (pmin[P.node_index[n]] - PATM)])
            else:
                w.writerow([g, ''])


if __name__ == '__main__':
    main()
