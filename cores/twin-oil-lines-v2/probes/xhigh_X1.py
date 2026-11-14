#!/usr/bin/env python3
"""TS-2 calculation of the heated oil lines of one site package.

    python3 lines.py PACKAGE_DIR OUT_CSV

For every hourly record: the pressure drop between the line's manifolds (kPa) and
the temperature of the oil leaving the outlet manifold (C), to TS-2.

Outline
  1. Uo of every survey on file is found by inverting TS-2 3.1-3.3 (TS-2 5.2).
  2. A survey counts for a pipe only if no work on the pipe's covering came after it
     (TS-2 5.3).  The valid surveys of a pipe are tested against each other with the
     reading tolerances of TS-2 5.4; a covering whose Uo has moved between surveys is
     not standing as it was surveyed.
  3. One order is placed with the survey crew (site_package.md): first the pipes with
     no valid survey, then the pipes whose surveys disagree most.
  4. Single pipes are integrated directly.  For a pair the split of the line flow is
     the one that gives both pipes the same pressure drop (TS-2 4).  There can be up
     to five such splits; the line keeps the one it is on: from the split of the
     previous hour the flow moves in the direction the pressure imbalance drives it
     to the nearest balanced split (the stable split whose basin holds the previous
     state).
"""
import csv
import json
import math
import os
import re
import subprocess
import sys

import numpy as np

LN10 = math.log(10.0)
C3 = 3.66 ** 3 + 0.7 ** 3
NS = 24            # RK4 steps along a pipe (x = L s^3); ~1e-5 relative accuracy
NEWTON = 2         # Newton iterations for the wall temperature at each stage
TOL_FLOW = 0.002   # TS-2 5.4 reading tolerances
TOL_TOIL = 0.02
TOL_TAMB = 0.1


def log(*a):
    print(*a, file=sys.stderr)


# --------------------------------------------------------------------------- oil
class Oil:
    def __init__(self, row):
        self.rho = float(row['density_kg_m3'])
        self.cp = float(row['cp_J_kgK'])
        self.k = float(row['k_W_mK'])
        n50 = float(row['nu50_cSt'])
        n100 = float(row['nu100_cSt'])
        z1 = math.log10(math.log10(n50 + 0.7))
        z2 = math.log10(math.log10(n100 + 0.7))
        t1, t2 = math.log10(323.15), math.log10(373.15)
        self.B = (z1 - z2) / (t2 - t1)
        self.A = z1 + self.B * t1


def visc(A, B, TC):
    """kinematic viscosity (m2/s) and beta = -d ln(nu)/dT (1/K), ASTM D341."""
    T = TC + 273.15
    tz = np.exp(LN10 * (A - B * np.log10(T)))
    w = np.exp(LN10 * tz)
    v = w - 0.7
    beta = (w / v) * (LN10 * B) * tz / T
    return v * 1e-6, beta


# --------------------------------------------------------------------------- one pipe
def run_pipe(m, Tin, Ta, Uo, D, L, A, B, rho, cp, k, nsteps=NS):
    """TS-2 section 3 for arrays of pipes.  Returns (outlet temperature C, dp Pa).

    State: theta = ln(Tb - Ta) (not stiff even when the oil cools to ambient within
    a few millimetres) and the pressure.  Independent variable s with x = L s^3,
    which makes the Graetz entrance behaviour (1/h ~ x^(1/3)) smooth.
    """
    shp = np.broadcast(m, Tin, Ta, Uo, D, L, A, B, rho, cp, k).shape
    f = lambda a: np.broadcast_to(np.asarray(a, dtype=float), shp)
    m, Tin, Ta, Uo, D, L, A, B, rho, cp, k = map(f, (m, Tin, Ta, Uo, D, L, A, B, rho, cp, k))
    cth = np.pi * D * Uo / (m * cp)                       # d theta/dx = -cth (1-y)
    cdp = 32.0 * (4.0 * m / (np.pi * D * D * rho)) * rho / (D * D)   # dp/dx = cdp sqrt(nub nuw)
    cgz = np.cbrt(4.0 * m * cp / (np.pi * k))             # Gz^(1/3) = cgz x^(-1/3)
    h0c = k / D
    th0 = np.log(np.maximum(Tin - Ta, 1e-9))
    zero = np.zeros(shp)

    def deriv(s, th, y):
        if s <= 0.0:
            return zero, zero, y
        x = L * s ** 3
        dxds = 3.0 * L * s * s
        dT = np.exp(th)
        Tb = Ta + dT
        vb, _ = visc(A, B, Tb)
        g3 = 1.077 * cgz / np.cbrt(x) - 0.7
        h0 = np.cbrt(C3 + g3 * g3 * g3) * h0c
        vw = None
        for _ in range(NEWTON):
            vw, bw = visc(A, B, Tb - y * dT)
            ph = (vb / vw) ** 0.14
            hp = h0 * ph
            F = y * (hp + Uo) - Uo
            dF = hp * (1.0 - 0.14 * y * bw * dT) + Uo
            y = np.clip(y - F / dF, 0.0, 1.0)
        vw, _ = visc(A, B, Tb - y * dT)
        return -cth * (1.0 - y) * dxds, cdp * np.sqrt(vb * vw) * dxds, y

    s = np.linspace(0.0, 1.0, nsteps + 1)
    xg = L * (0.5 * s[1]) ** 3
    g3 = 1.077 * cgz / np.cbrt(xg) - 0.7
    y = Uo / (np.cbrt(C3 + g3 ** 3) * h0c + Uo)
    th = th0
    P = zero
    for i in range(nsteps):
        s0 = s[i]
        hs = s[i + 1] - s0
        a1, p1, _ = deriv(s0, th, y)
        a2, p2, y = deriv(s0 + 0.5 * hs, th + 0.5 * hs * a1, y)
        a3, p3, y = deriv(s0 + 0.5 * hs, th + 0.5 * hs * a2, y)
        a4, p4, y = deriv(s0 + hs, th + hs * a3, y)
        th = th + hs / 6.0 * (a1 + 2.0 * a2 + 2.0 * a3 + a4)
        P = P + hs / 6.0 * (p1 + 2.0 * p2 + 2.0 * p3 + p4)
    return Ta + np.exp(th), P


def illinois(fun, a, b, fa, fb, iters=60, xtol=1e-11):
    """Vectorised Illinois (modified regula falsi) on brackets with fa*fb <= 0.
    Returns the root estimates."""
    a = np.array(a, float); b = np.array(b, float)
    fa = np.array(fa, float); fb = np.array(fb, float)
    done = (fa == 0) | (fb == 0)
    x = np.where(fb == 0, b, np.where(fa == 0, a, 0.5 * (a + b)))
    for _ in range(iters):
        den = fb - fa
        c = np.where(den != 0, b - fb * (b - a) / np.where(den != 0, den, 1.0), 0.5 * (a + b))
        lo = np.minimum(a, b); hi = np.maximum(a, b)
        c = np.where((c > lo) & (c < hi), c, 0.5 * (a + b))
        act = ~done
        if not act.any():
            break
        fc = fun(c)
        fc = np.where(np.isfinite(fc), fc, 0.0)
        x = np.where(act, c, x)
        conv = act & ((np.abs(c - b) < xtol) | (fc == 0) | (np.abs(b - a) < xtol))
        swap = fc * fb < 0
        # swap: the old b becomes a; otherwise a is kept and its value halved
        na = np.where(swap, b, a); nfa = np.where(swap, fb, fa * 0.5)
        a = np.where(act, na, a); fa = np.where(act, nfa, fa)
        b = np.where(act, c, b); fb = np.where(act, fc, fb)
        done = done | conv
    return x


# --------------------------------------------------------------------------- package
def read_csv(path):
    with open(path, newline='') as f:
        return [{k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items() if k is not None}
                for r in csv.DictReader(f)]


def pipe_line(p):
    return p.rsplit('-', 1)[0]


COVER_RE = re.compile(r'\b(re-?)?(cover|lag|insulat|clad|jacket|wrap|sheath|mattress)')
NOCHANGE_RE = re.compile(r'\b(inspect|check|survey|measur|photograph|examin|look|test)')
CHANGE_RE = re.compile(r'(renew|repair|replac|patch|refit|reinstat|restor|mend|new|fix|remov|strip|damag|wet|redone|re-?do)')


def covering_work(job):
    """Does a work-log entry change the covering of a pipe? (TS-2 5.3)"""
    j = job.lower()
    if not COVER_RE.search(j):
        return False
    if NOCHANGE_RE.search(j) and not CHANGE_RE.search(j):
        return False
    return True


def covering_kind(job):
    j = job.lower()
    if any(w in j for w in ('renew', 'replac', 'new', 're-lag', 'relag', 'recover', 're-cover')):
        return 'renewed'
    return 'repaired'


def clean_surveys(rows, known):
    out = []
    for r in rows:
        try:
            r['pipe'] = r['pipe'].strip().upper()
            if r['pipe'] in known and float(r['flow_t_h']) > 0 and float(r['t_in_C']) > float(r['t_amb_C']) \
                    and float(r['t_in_C']) > float(r['t_out_C']) > float(r['t_amb_C']):
                out.append(r)
        except (KeyError, ValueError, TypeError):
            pass
    return out


class Package:
    def __init__(self, d):
        self.dir = d
        self.site = json.load(open(os.path.join(d, 'site.json')))
        self.oils = {r['oil']: Oil(r) for r in read_csv(os.path.join(d, 'oils.csv'))}
        self.lines = {}
        for r in read_csv(os.path.join(d, 'lines.csv')):
            r['line'] = r['line'].strip().upper()
            self.lines[r['line']] = dict(pipes=int(float(r['pipes'])), D=float(r['bore_mm']) / 1000.0,
                                         L=float(r['length_m']), oil=self.oils[r['oil']])
        self.pipes = []
        for ln, l in self.lines.items():
            for suf in ('A', 'B')[:l['pipes']]:
                self.pipes.append(ln + '-' + suf)
        self.surveys = clean_surveys(read_csv(os.path.join(d, 'surveys.csv')), set(self.pipes))
        wl = os.path.join(d, 'work_log.csv')
        self.work = read_csv(wl) if os.path.exists(wl) else []
        self.records = read_csv(os.path.join(d, 'records.csv'))
        for r in self.records:
            r['line'] = r['line'].strip().upper()

    def pipe_params(self, pipes):
        ls = [self.lines[pipe_line(p)] for p in pipes]
        D = np.array([l['D'] for l in ls]); L = np.array([l['L'] for l in ls])
        op = [np.array([getattr(l['oil'], a) for l in ls]) for a in ('A', 'B', 'rho', 'cp', 'k')]
        return D, L, op


# --------------------------------------------------------------------------- surveys
def invert_surveys(pkg, rows):
    """Uo for each survey row (TS-2 5.2) and its worst-case error from TS-2 5.4."""
    n = len(rows)
    if n == 0:
        return np.zeros(0), np.zeros(0)
    pipes = [r['pipe'] for r in rows]
    D, L, op = pkg.pipe_params(pipes)
    m = np.array([float(r['flow_t_h']) for r in rows]) / 3.6
    Ti = np.array([float(r['t_in_C']) for r in rows])
    To = np.array([float(r['t_out_C']) for r in rows])
    Ta = np.array([float(r['t_amb_C']) for r in rows])

    def resid(lu, mm=m, ti=Ti, ta=Ta):
        return run_pipe(mm, ti, ta, np.exp(lu), D, L, *op)[0] - To

    lo = np.full(n, math.log(0.02)); hi = np.full(n, math.log(2000.0))
    flo = resid(lo); fhi = resid(hi)
    lu = illinois(resid, lo, hi, flo, fhi, iters=60, xtol=1e-10)
    U = np.exp(lu)
    # sensitivities of the outlet temperature, for the error bound of Uo
    eps = 1e-3
    T0 = run_pipe(m, Ti, Ta, U, D, L, *op)[0]
    dU = (run_pipe(m, Ti, Ta, U * (1 + eps), D, L, *op)[0] - T0) / (U * eps)
    dTi = (run_pipe(m, Ti + 0.05, Ta, U, D, L, *op)[0] - T0) / 0.05
    dTa = (run_pipe(m, Ti, Ta + 0.05, U, D, L, *op)[0] - T0) / 0.05
    dm = (run_pipe(m * (1 + eps), Ti, Ta, U, D, L, *op)[0] - T0) / eps
    num = TOL_TOIL + np.abs(dTi) * TOL_TOIL + np.abs(dTa) * TOL_TAMB + np.abs(dm) * TOL_FLOW
    bound = num / np.maximum(np.abs(dU), 1e-12)
    bad = ~np.isfinite(U) | (U <= 0.021) | (U >= 1999.0)
    bound = np.where(bad, np.inf, bound)
    return U, bound


def plan(pkg):
    """Uo estimates from the surveys on file and the pipes to order."""
    U, bnd = invert_surveys(pkg, pkg.surveys)
    pkg.U, pkg.B = U, bnd
    cov = {}
    known = set(pkg.pipes)
    for w in pkg.work:
        name = (w.get('pipe') or '').strip().upper()
        if not covering_work(w.get('job') or ''):
            continue
        # an entry against a line rather than one of its pipes covers all its pipes
        targets = [name] if name in known else [q for q in pkg.pipes if pipe_line(q) == name]
        for q in targets:
            cov.setdefault(q, []).append((w.get('date', ''), w.get('job', '')))
    by = {}
    for i, s in enumerate(pkg.surveys):
        by.setdefault(s['pipe'], []).append(i)
    info = {}
    for p in pkg.pipes:
        idx = sorted(by.get(p, []), key=lambda i: pkg.surveys[i]['date'])
        last_cov = max([d for d, _ in cov.get(p, [])], default='')
        # a survey on the same day as covering work cannot be placed before or after
        # it with certainty: it is not taken as a survey of the covering as it stands
        valid = [i for i in idx if pkg.surveys[i]['date'] > last_cov and np.isfinite(bnd[i])]
        rec = dict(valid=valid, all=idx, cov=cov.get(p, []), score=0.0)
        if valid:
            u = U[valid]; b = bnd[valid]
            w = 1.0 / b ** 2
            rec['uo'] = float(np.sum(w * u) / np.sum(w))
            sc = 0.0
            for a in range(len(valid)):
                for c in range(a + 1, len(valid)):
                    sc = max(sc, abs(u[a] - u[c]) / (b[a] + b[c]))
            rec['score'] = sc
            rec['last'] = float(u[-1])
        info[p] = rec
    return info, U, bnd


def order_surveys(pkg, info):
    allow = int(pkg.site.get('survey_allowance', 0))
    mandatory = [p for p in pkg.pipes if not info[p]['valid']]
    if len(mandatory) > allow:
        # not all can be had: survey first the pipes whose results hang most on Uo
        imp = impact(pkg, info, mandatory)
        mandatory.sort(key=lambda p: imp[p], reverse=True)
    rest = [p for p in pkg.pipes if info[p]['valid']]
    rest.sort(key=lambda p: -info[p]['score'])
    drift = [p for p in rest if info[p]['score'] > 1.0]
    others = [p for p in rest if info[p]['score'] <= 1.0 and len(info[p]['valid']) >= 2]
    lone = [p for p in rest if len(info[p]['valid']) == 1]
    order = (mandatory + drift + others + lone)[:max(allow, 0)]
    return order, mandatory, drift


def fallback_uo(pkg, rec):
    """Uo of a covering that has been worked on and could not be surveyed again."""
    old = [pkg.U[i] for i in rec['all'] if np.isfinite(pkg.B[i])]
    if not old:
        return 5.0
    kind = covering_kind(sorted(rec['cov'])[-1][1]) if rec['cov'] else 'repaired'
    return float(old[-1]) * (0.5 if kind == 'renewed' else 0.65)


def impact(pkg, info, pipes):
    """How far the results of a pipe's line move when its Uo is uncertain by a
    factor 1.3 either way (pipe taken with an even share of the line flow)."""
    recs = {}
    for r in pkg.records:
        recs.setdefault(r['line'], []).append(r)
    score = {}
    for p in pipes:
        ln = pipe_line(p); rr = recs.get(ln, [])
        if not rr:
            score[p] = (0, 0.0)
            continue
        l = pkg.lines[ln]
        D, L, op = pkg.pipe_params([p] * len(rr))
        M = np.array([float(r['flow_t_h']) for r in rr]) / 3.6 / l['pipes']
        ti = np.array([float(r['t_in_C']) for r in rr]); ta = np.array([float(r['t_amb_C']) for r in rr])
        u = fallback_uo(pkg, info[p])
        T1, p1 = run_pipe(M, ti, ta, u / 1.3, D, L, *op)
        T2, p2 = run_pipe(M, ti, ta, u * 1.3, D, L, *op)
        w = 1.0 / l['pipes']
        e = np.maximum(w * np.abs(T1 - T2) / 2 / 0.5, np.abs(np.log(p1 / p2)) / 2 / 0.015)
        score[p] = (int(np.sum(e > 1)), float(np.sum(e)))
    return score


def call_crew(pkg_dir, pipes):
    if not pipes:
        return []
    try:
        cp = subprocess.run(['heatsurvey', pkg_dir] + list(pipes), capture_output=True, text=True, timeout=30)
    except Exception as e:  # noqa
        log('heatsurvey failed:', e)
        return []
    if cp.returncode != 0:
        log('heatsurvey refused:', (cp.stdout + cp.stderr).strip())
        return []
    rows = []
    lines = [l for l in cp.stdout.splitlines() if l.strip()]
    try:
        hdr_i = next(i for i, l in enumerate(lines) if l.replace(' ', '').startswith('pipe,'))
    except StopIteration:
        log('heatsurvey: no table in reply')
        return []
    for r in csv.DictReader(lines[hdr_i:]):
        r = {k.strip(): v.strip() for k, v in r.items() if k is not None and v is not None}
        try:
            for key in ('flow_t_h', 't_in_C', 't_out_C', 't_amb_C'):
                float(r[key])
        except (KeyError, ValueError):
            continue
        rows.append(r)
    return rows


def settle_uo(pkg, info, new_rows):
    Un, bn = invert_surveys(pkg, new_rows)
    newu = {}
    for r, u, b in zip(new_rows, Un, bn):
        if np.isfinite(u) and np.isfinite(b):
            newu[r['pipe']] = (float(u), float(b))
    uo = {}
    for p in pkg.pipes:
        rec = info[p]
        if p in newu:
            u, b = newu[p]
            if rec['valid'] and rec['score'] <= 1.0:
                # covering steady: the new survey joins the valid ones if it agrees
                v = rec['valid']
                us = list(pkg.U[v]); bs = list(pkg.B[v])
                agree = all(abs(u - a) <= (b + c) for a, c in zip(us, bs))
                if agree:
                    us.append(u); bs.append(b)
                    w = 1.0 / np.array(bs) ** 2
                    uo[p] = float(np.sum(w * np.array(us)) / np.sum(w))
                    continue
            uo[p] = u
            continue
        if rec['valid']:
            if rec['score'] > 1.0:
                uo[p] = extrapolate(pkg, rec)
            else:
                uo[p] = rec['uo']
            continue
        # no valid survey and none could be had: estimate from the covering work
        uo[p] = fallback_uo(pkg, rec)
        log('no survey for', p, '- estimated Uo', uo[p])
    return uo


def extrapolate(pkg, rec):
    """A covering that is moving and could not be surveyed: carry its trend on."""
    from datetime import date
    v = rec['valid']
    ds = []
    for i in v:
        y, mo, d = map(int, pkg.surveys[i]['date'].split('-'))
        ds.append(date(y, mo, d).toordinal())
    us = pkg.U[v]
    if len(v) < 2:
        return float(us[-1])
    t = np.array(ds, float)
    a, b = np.polyfit(t, us, 1)
    last_job = []
    for w in pkg.work:
        try:
            y, mo, d = map(int, w['date'].split('-'))
            last_job.append(date(y, mo, d).toordinal())
        except Exception:  # noqa
            pass
    tn = max([t[-1]] + last_job) + 14
    return float(max(a * tn + b, 0.05))


# --------------------------------------------------------------------------- records
def single_lines(pkg, uo, recs, out):
    if not recs:
        return
    pipes = [r['line'] + '-A' for r in recs]
    D, L, op = pkg.pipe_params(pipes)
    M = np.array([float(r['flow_t_h']) for r in recs]) / 3.6
    ti = np.array([float(r['t_in_C']) for r in recs])
    ta = np.array([float(r['t_amb_C']) for r in recs])
    U = np.array([uo[p] for p in pipes])
    To, dp = run_pipe(M, ti, ta, U, D, L, *op)
    for r, a, b in zip(recs, dp, To):
        out[r['record']] = (a / 1000.0, b)


ZGRID = np.unique(np.concatenate([np.arange(-16.0, -8.0, 0.5), np.arange(-8.0, 8.0001, 0.16),
                                  np.arange(8.5, 16.01, 0.5)]))


def sig(z):
    return 1.0 / (1.0 + np.exp(-z))


class PairSet:
    """Balance function g(z) = ln dpA(phi M) - ln dpB((1-phi) M), phi = 1/(1+e^-z),
    for a set of pair records (vectorised)."""

    def __init__(self, pkg, uo, recs):
        self.recs = recs
        la = [r['line'] + '-A' for r in recs]
        lb = [r['line'] + '-B' for r in recs]
        self.D, self.L, self.op = pkg.pipe_params(la)
        self.M = np.array([float(r['flow_t_h']) for r in recs]) / 3.6
        self.ti = np.array([float(r['t_in_C']) for r in recs])
        self.ta = np.array([float(r['t_amb_C']) for r in recs])
        self.uA = np.array([uo[p] for p in la])
        self.uB = np.array([uo[p] for p in lb])

    def evaluate(self, z, idx, full=False):
        """g at points z (any shape); idx (same shape) gives the record of each point."""
        z = np.asarray(z, float)
        g = lambda a: a[idx]
        M, ti, ta = g(self.M), g(self.ti), g(self.ta)
        D, L = g(self.D), g(self.L)
        op = [g(a) for a in self.op]
        phA = sig(z); phB = sig(-z)
        ToA, pA = run_pipe(M * phA, ti, ta, g(self.uA), D, L, *op)
        ToB, pB = run_pipe(M * phB, ti, ta, g(self.uB), D, L, *op)
        gg = np.log(pA) - np.log(pB)
        if full:
            return gg, ToA, ToB, pA, pB
        return gg


def pair_lines(pkg, uo, recs, out):
    if not recs:
        return
    ps = PairSet(pkg, uo, recs)
    n = len(recs)
    Z = ZGRID
    # balance function on the grid, in chunks
    G = np.empty((n, len(Z)))
    ch = max(1, 60000 // len(Z))
    for a in range(0, n, ch):
        b = min(n, a + ch)
        idx = np.repeat(np.arange(a, b), len(Z)).reshape(b - a, len(Z))
        G[a:b] = ps.evaluate(np.broadcast_to(Z, (b - a, len(Z))), idx=idx)
    bad = ~np.isfinite(G)
    if bad.any():
        G[bad] = np.where(np.broadcast_to(Z, G.shape)[bad] < 0, -1e3, 1e3)
    # brackets: sign changes, plus dips of g towards zero that the grid steps over
    br_rec, br_lo, br_hi = [], [], []
    sgn = np.sign(G)
    ii, jj = np.nonzero(sgn[:, :-1] * sgn[:, 1:] <= 0)
    br_rec += list(ii); br_lo += list(Z[jj]); br_hi += list(Z[jj + 1])
    # dips: interior local minima of |g| without a sign change
    A = np.abs(G)
    dip = (A[:, 1:-1] < A[:, :-2]) & (A[:, 1:-1] < A[:, 2:]) & (sgn[:, :-2] == sgn[:, 1:-1]) & (sgn[:, 1:-1] == sgn[:, 2:])
    di, dj = np.nonzero(dip)
    if len(di):
        dj = dj + 1
        # parabola through the three points; check whether its extremum reaches zero
        z0, z1, z2 = Z[dj - 1], Z[dj], Z[dj + 1]
        g0, g1, g2 = G[di, dj - 1], G[di, dj], G[di, dj + 1]
        # parabola p(z) = g0 + d01 (z-z0) + c2 (z-z0)(z-z1) and its vertex
        d01 = (g1 - g0) / (z1 - z0); d12 = (g2 - g1) / (z2 - z1)
        c2 = (d12 - d01) / (z2 - z0)
        zc = 0.5 * (z0 + z1) - d01 / np.where(c2 != 0, 2 * c2, 1e-30)
        zc = np.clip(zc, z0, z2)
        gv = g0 + d01 * (zc - z0) + c2 * (zc - z0) * (zc - z1)
        susp = (np.abs(gv) < 0.5 * np.abs(g1) + 0.02) | (np.sign(gv) != np.sign(g1))
        di, dj = di[susp], dj[susp]
        if len(di):
            K = 17
            zz = Z[dj - 1][:, None] + (Z[dj + 1] - Z[dj - 1])[:, None] * np.linspace(0, 1, K)[None, :]
            idx = np.repeat(di, K).reshape(len(di), K)
            gz = ps.evaluate(zz, idx=idx)
            s2 = np.sign(gz)
            a2, b2 = np.nonzero(s2[:, :-1] * s2[:, 1:] <= 0)
            br_rec += list(di[a2]); br_lo += list(zz[a2, b2]); br_hi += list(zz[a2, b2 + 1])
    br_rec = np.array(br_rec, dtype=int); br_lo = np.array(br_lo); br_hi = np.array(br_hi)
    # refine every bracket
    flo = ps.evaluate(br_lo, idx=br_rec); fhi = ps.evaluate(br_hi, idx=br_rec)
    zr = illinois(lambda z: ps.evaluate(z, idx=br_rec), br_lo, br_hi, flo, fhi, iters=50, xtol=1e-9)
    stab = fhi > flo     # g increasing through the root: a stable split
    roots = [[] for _ in range(n)]
    for r, z, st in zip(br_rec, zr, stab):
        roots[r].append((float(z), bool(st)))
    for r in range(n):
        lst = sorted(set((round(z, 9), s) for z, s in roots[r]))
        # merge duplicates from overlapping brackets
        clean = []
        for z, s in lst:
            if clean and abs(z - clean[-1][0]) < 1e-6:
                continue
            clean.append((z, s))
        roots[r] = clean
    # follow each line through its hours
    byline = {}
    for i, r in enumerate(recs):
        byline.setdefault(r['line'], []).append(i)
    chosen = np.zeros(n)
    for ln, ids in byline.items():
        ids.sort(key=lambda i: float(recs[i]['hour']))
        zprev = None
        for i in ids:
            rl = roots[i]
            if not rl:
                # no bracket found (should not happen): take the grid minimum of |g|
                j = int(np.argmin(np.abs(G[i])))
                z = float(Z[j])
            elif zprev is None:
                st = [z for z, s in rl if s]
                if len(st) == 1:
                    z = st[0]
                else:
                    z = follow(rl, 0.0, G[i], Z)
                    log('line %s: %d balanced splits at its first record; taken from an even start' % (ln, len(st)))
            else:
                z = follow(rl, zprev, G[i], Z)
            chosen[i] = z
            zprev = z
    gg, ToA, ToB, pA, pB = ps.evaluate(chosen, idx=np.arange(n), full=True)
    phA = sig(chosen)
    for i, r in enumerate(recs):
        dp = math.sqrt(pA[i] * pB[i])
        To = phA[i] * ToA[i] + (1.0 - phA[i]) * ToB[i]
        out[r['record']] = (dp / 1000.0, To)


def follow(rl, zprev, Grow, Z):
    """The balanced split reached from zprev: move against the imbalance g to the
    nearest root (it is a stable one)."""
    for z, s in rl:
        if s and abs(z - zprev) < 1e-7:
            return z
    zs = [z for z, _ in rl]
    below = sum(1 for z in zs if z < zprev)
    # g(-inf) < 0 and every root flips the sign
    consistent = all(s == (k % 2 == 0) for k, (_, s) in enumerate(rl))
    if consistent:
        gpos = (below % 2 == 1)
    else:
        gpos = float(np.interp(zprev, Z, Grow)) > 0
    if gpos:
        cand = [z for z in zs if z < zprev]
        if cand:
            return max(cand)
    else:
        cand = [z for z in zs if z > zprev]
        if cand:
            return min(cand)
    st = [z for z, s in rl if s] or zs
    return min(st, key=lambda z: abs(z - zprev))


# --------------------------------------------------------------------------- main
def main():
    if len(sys.argv) != 3:
        print('usage: python3 lines.py PACKAGE_DIR OUT_CSV', file=sys.stderr)
        sys.exit(2)
    pdir, outp = sys.argv[1], sys.argv[2]
    np.seterr(all='ignore')
    pkg = Package(pdir)
    info, _, _ = plan(pkg)
    order, mandatory, drift = order_surveys(pkg, info)
    log('no valid survey:', mandatory)
    log('covering moving:', drift)
    log('order:', order)
    new_rows = call_crew(pdir, order)
    new_rows = clean_surveys(new_rows, set(order))
    uo = settle_uo(pkg, info, new_rows)
    out = {}
    singles = [r for r in pkg.records if pkg.lines[r['line']]['pipes'] == 1]
    pairs = [r for r in pkg.records if pkg.lines[r['line']]['pipes'] == 2]
    single_lines(pkg, uo, singles, out)
    pair_lines(pkg, uo, pairs, out)
    with open(outp, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['record', 'dp_kPa', 't_out_C'])
        for r in pkg.records:
            dp, To = out[r['record']]
            w.writerow([r['record'], '%.4f' % dp, '%.4f' % To])


if __name__ == '__main__':
    main()
