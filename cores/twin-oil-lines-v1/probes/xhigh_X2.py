#!/usr/bin/env python3
"""Heated fuel oil lines: hourly results to terminal standard TS-2 for one site package.

    python3 lines.py PACKAGE_DIR OUT_CSV

Writes OUT_CSV with the header record,dp_kPa,t_out_C and one row for every row of the
package's records.csv.  While it runs it may place the package's one survey order with the
`heatsurvey` command (site package format, "The survey crew").
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date

import numpy as np

T0 = 273.15
LN10 = np.log(10.0)
NSTEP = 16                       # integration steps along a pipe (x = L s^3, RK4)
ERR_FLOW, ERR_TOIL, ERR_TAMB = 0.002, 0.02, 0.1   # survey reading limits, TS-2 5.4
DRIFT_RATIO = 0.6                # spread / reading-error bound above which a covering is changing
C3 = 3.66 ** 3 + 0.7 ** 3


# ----------------------------------------------------------------------------------------
# input
# ----------------------------------------------------------------------------------------
def read_csv(path):
    with open(path, newline='') as f:
        rows = [r for r in csv.reader(f) if r and any(c.strip() for c in r)]
    if not rows:
        return []
    hdr = [h.strip().lstrip('﻿') for h in rows[0]]
    return [dict(zip(hdr, [c.strip() for c in r])) for r in rows[1:]]


def fnum(s):
    return float(str(s).strip())


def pdate(s):
    s = str(s).strip()
    try:
        y, m, d = s[:10].split('-')
        return date(int(y), int(m), int(d)).toordinal()
    except Exception:
        return None


def norm_pipe(s):
    return re.sub(r'\s+', '', str(s)).upper()


# ----------------------------------------------------------------------------------------
# TS-2 model of one pipe
# ----------------------------------------------------------------------------------------
def oil_AB(v50, v100):
    """ASTM D341 constants through the two tabulated points (TS-2 2.2)."""
    T1, T2 = 50 + T0, 100 + T0
    y1 = np.log10(np.log10(v50 + 0.7))
    y2 = np.log10(np.log10(v100 + 0.7))
    B = (y1 - y2) / (np.log10(T2) - np.log10(T1))
    A = y1 + B * np.log10(T1)
    return A, B


def visc(A, B, Tc):
    """kinematic viscosity [cSt] and dln(v)/dT at Tc [C]"""
    T = Tc + T0
    w = 10.0 ** (A - B * np.log10(T))
    vp = 10.0 ** w
    v = vp - 0.7
    return v, -(vp / v) * w * B * LN10 / T


def integrate(m, P, U, Ta, Tin, n=NSTEP):
    """Steady march of TS-2 3.1-3.4 along a pipe, vectorised over elements.
    m [kg/s]; P = (D, L, A, B, rho, cp, k) arrays; U = Uo; Ta, Tin [C].
    Uses y = ln(Tb - Ta) (non-stiff at any flow) and x = L s^3 (smooth at the inlet).
    Returns (Tout [C], dp [Pa])."""
    D, L, A, B, rho, cp, k = P
    u = 4 * m / (np.pi * D * D * rho)
    Gzc = 4 * m * cp / (np.pi * k)              # Gz = Gzc / x
    c1 = np.pi * D / (m * cp)
    kD = k / D
    cP = 32 * u / (D * D) * rho * 1e-6          # dp/dx = cP * sqrt(vb vw), v in cSt
    y = np.log(np.maximum(Tin - Ta, 1e-12))
    Pacc = np.zeros_like(m)
    hs = 1.0 / n
    L3 = 3 * L

    def film(s):
        a = 1.077 * np.cbrt(Gzc / (L * s ** 3)) - 0.7
        return np.cbrt(C3 + a * a * a) * kD

    def stage(s, y, h0, eps):
        th = np.exp(y)
        Tb = Ta + th
        vb, _ = visc(A, B, Tb)
        dxds = L3 * (s * s)
        if h0 is None:                          # x = 0: Tw = Tb
            return -c1 * U * dxds, cP * vb * dxds, None
        if eps is None:
            eps = h0 / (h0 + U)
        Tw = Ta + th * eps
        for _ in range(2):                      # Newton on the wall temperature, 3.2/3.3
            vw, dl = visc(A, B, Tw)
            h = h0 * (vb / vw) ** 0.14
            g = h * (Tb - Tw) - U * (Tw - Ta)
            dg = -h * (0.14 * dl * (Tb - Tw) + 1.0) - U
            Tw = np.minimum(np.maximum(Tw - g / dg, Ta), Tb)
        vw, _ = visc(A, B, Tw)
        h = h0 * (vb / vw) ** 0.14
        lam = c1 * h * U / (h + U)
        return -lam * dxds, cP * np.sqrt(vb * vw) * dxds, (Tw - Ta) / np.maximum(th, 1e-300)

    eps = None
    h_prev = None
    for i in range(n):
        s0 = i * hs
        sm = s0 + 0.5 * hs
        s1 = s0 + hs
        hm = film(sm)
        h1 = film(s1)
        k1, p1, e1 = stage(s0, y, h_prev, eps)
        k2, p2, e2 = stage(sm, y + 0.5 * hs * k1, hm, e1)
        k3, p3, e3 = stage(sm, y + 0.5 * hs * k2, hm, e2)
        k4, p4, e4 = stage(s1, y + hs * k3, h1, e3)
        y = y + hs / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        Pacc = Pacc + hs / 6 * (p1 + 2 * p2 + 2 * p3 + p4)
        eps = e4
        h_prev = h1
    return Ta + np.exp(y), Pacc


def integrate_chunked(m, P, U, Ta, Tin, chunk=40000):
    N = len(m)
    if N <= chunk:
        return integrate(m, P, U, Ta, Tin)
    To = np.empty(N)
    dp = np.empty(N)
    for a in range(0, N, chunk):
        b = min(N, a + chunk)
        t, p = integrate(m[a:b], tuple(x[a:b] for x in P), U[a:b], Ta[a:b], Tin[a:b])
        To[a:b] = t
        dp[a:b] = p
    return To, dp


def invert_uo(m, P, Ta, Tin, Tout):
    """Uo for which 3.1-3.3 give the outlet temperature read (TS-2 5.2), vectorised."""
    N = len(m)
    if N == 0:
        return np.zeros(0)
    a = np.full(N, np.log(1e-3))
    b = np.full(N, np.log(1e3))
    fa = integrate(m, P, np.exp(a), Ta, Tin)[0] - Tout
    fb = integrate(m, P, np.exp(b), Ta, Tin)[0] - Tout
    # outlet above what no loss gives, or below the surroundings: clamp to the bracket
    lo_out = fa <= 0          # even Uo=1e-3 gives Tout <= read: Uo tiny
    hi_out = fb >= 0
    c = np.where(lo_out, a, b)
    active = ~(lo_out | hi_out)
    side = np.zeros(N)
    for _ in range(80):
        idx = np.nonzero(active)[0]
        if idx.size == 0:
            break
        ai, bi, fai, fbi = a[idx], b[idx], fa[idx], fb[idx]
        ci = (ai * fbi - bi * fai) / (fbi - fai)
        Pi = tuple(x[idx] for x in P)
        fc = integrate(m[idx], Pi, np.exp(ci), Ta[idx], Tin[idx])[0] - Tout[idx]
        c[idx] = ci
        done = (np.abs(fc) < 1e-9) | (np.abs(bi - ai) < 1e-12)
        same = np.sign(fc) == np.sign(fai)
        sd = side[idx]
        na = np.where(same, ci, ai)
        nfa = np.where(same, fc, fai)
        nb = np.where(same, bi, ci)
        nfb = np.where(same, fbi, fc)
        nfb = np.where(same & (sd == 1), nfb * 0.5, nfb)
        nfa = np.where(~same & (sd == -1), nfa * 0.5, nfa)
        a[idx], fa[idx], b[idx], fb[idx] = na, nfa, nb, nfb
        side[idx] = np.where(same, 1, -1)
        active[idx[done]] = False
    return np.exp(c)


def uo_error_bound(m, P, Ta, Tin, U):
    """Worst-case error of a surveyed Uo from the reading limits of TS-2 5.4 (relative)."""
    T, _ = integrate(m, P, U, Ta, Tin)
    dU = integrate(m, P, U * 1.001, Ta, Tin)[0] - T
    dm = integrate(m * 1.001, P, U, Ta, Tin)[0] - T
    di = integrate(m, P, U, Ta, Tin + 0.01)[0] - T
    da = integrate(m, P, U, Ta + 0.01, Tin)[0] - T
    dTdlnU = dU / np.log(1.001)
    dTdlnm = dm / np.log(1.001)
    dTdTi = di / 0.01
    dTdTa = da / 0.01
    num = np.abs(dTdlnm) * ERR_FLOW + np.abs(dTdTi) * ERR_TOIL + ERR_TOIL + np.abs(dTdTa) * ERR_TAMB
    return num / np.maximum(np.abs(dTdlnU), 1e-12)


# ----------------------------------------------------------------------------------------
# work log
# ----------------------------------------------------------------------------------------
COVER_RE = re.compile(r'(covering|lagging|lagged|insulat|cladding|jacket|sheath|wrapping|mattress|'
                      r'blanket)', re.I)
CHANGE_RE = re.compile(
    r'(renew|repair|replac|patch|made\s*good|make\s*good|refit|re-fit|rebuil|restor|reinstat|'
    r're-?instat|relag|re-lag|reinsul|re-insul|reclad|re-clad|recover|re-cover|new\b|fitted|'
    r'install|remov|strip|redone|re-?done|mend|fix|rewrap|re-wrap|rework|re-work|overhaul|'
    r'refurb|upgrad|improv|reapplied|re-applied|applied|added|extended|sealed|resealed)', re.I)
NOCHANGE_RE = re.compile(r'(inspect|check|survey|examin|photograph|measur|tagg|label|record|'
                         r'test|look|monitor|assess|note|report|logged)', re.I)


def job_kind(job):
    """'change' when the job renewed or repaired the covering (TS-2 5.3), 'maybe' when it did
    something to the covering that is not plainly either, else None."""
    j = job.lower()
    if not COVER_RE.search(j):
        if re.search(r'\b(relag|re-lag|reinsul|re-insul|reclad|re-clad)', j):
            return 'change'
        return None
    if CHANGE_RE.search(j):
        if re.search(r'renew', j):
            return 'change:renew'
        if re.search(r'repair|patch|made\s*good|make\s*good|mend|fix', j):
            return 'change:repair'
        return 'change'
    if NOCHANGE_RE.search(j):
        return None
    return 'maybe'


# ----------------------------------------------------------------------------------------
# main calculation
# ----------------------------------------------------------------------------------------
class Package:
    def __init__(self, d):
        self.dir = d
        try:
            with open(os.path.join(d, 'site.json')) as f:
                self.site = json.load(f)
        except Exception:
            self.site = {}
        self.oils = {}
        for r in read_csv(os.path.join(d, 'oils.csv')):
            A, B = oil_AB(fnum(r['nu50_cSt']), fnum(r['nu100_cSt']))
            self.oils[r['oil']] = (A, B, fnum(r['density_kg_m3']), fnum(r['cp_J_kgK']), fnum(r['k_W_mK']))
        self.lines = {}
        self.pipes = {}            # pipe -> line
        for r in read_csv(os.path.join(d, 'lines.csv')):
            line = r['line']
            npipe = int(round(fnum(r['pipes'])))
            A, B, rho, cp, k = self.oils[r['oil']]
            props = (fnum(r['bore_mm']) / 1000.0, fnum(r['length_m']), A, B, rho, cp, k)
            names = [line + '-' + c for c in 'AB'[:npipe]]
            self.lines[line] = dict(n=npipe, props=props, pipes=names)
            for p in names:
                self.pipes[p] = line
        self.pipe_key = {norm_pipe(p): p for p in self.pipes}
        try:
            self.surveys = read_csv(os.path.join(d, 'surveys.csv'))
        except Exception:
            self.surveys = []
        try:
            self.work = read_csv(os.path.join(d, 'work_log.csv'))
        except Exception:
            self.work = []
        self.recs = read_csv(os.path.join(d, 'records.csv'))

    def props_for(self, pipes):
        pr = [self.lines[self.pipes[p]]['props'] for p in pipes]
        return tuple(np.array([q[i] for q in pr], float) for i in range(7))

    def resolve_pipe(self, name):
        key = norm_pipe(name)
        if key in self.pipe_key:
            return [self.pipe_key[key]]
        for line in self.lines:                # a job entered against the line
            if norm_pipe(line) == key:
                return list(self.lines[line]['pipes'])
        return []


def survey_rows_uo(pk, rows):
    """rows: list of dicts with pipe, flow_t_h, t_in_C, t_out_C, t_amb_C. Returns Uo, bound."""
    pipes = [r['pipe'] for r in rows]
    if not rows:
        return np.zeros(0), np.zeros(0)
    P = pk.props_for(pipes)
    m = np.array([fnum(r['flow_t_h']) for r in rows]) / 3.6
    Ta = np.array([fnum(r['t_amb_C']) for r in rows])
    Ti = np.array([fnum(r['t_in_C']) for r in rows])
    To = np.array([fnum(r['t_out_C']) for r in rows])
    U = invert_uo(m, P, Ta, Ti, To)
    e = uo_error_bound(m, P, Ta, Ti, U)
    return U, e


def wmean(us, es):
    w = 1.0 / np.maximum(np.asarray(es), 1e-6) ** 2
    return float(np.sum(w * np.asarray(us)) / np.sum(w))


def consistent(us, es):
    us = np.asarray(us)
    es = np.asarray(es) * us
    for i in range(len(us)):
        for j in range(i + 1, len(us)):
            if abs(us[i] - us[j]) > DRIFT_RATIO * (es[i] + es[j]):
                return False
    return True


def place_order(pk_dir, pipes):
    exe = shutil.which('heatsurvey')
    if exe is None or not pipes:
        return None
    try:
        res = subprocess.run([exe, pk_dir] + list(pipes), capture_output=True, text=True, timeout=20)
    except Exception:
        return None
    out = res.stdout or ''
    if os.environ.get('LINES_DEBUG'):
        sys.stderr.write('heatsurvey rc=%s\nstdout:\n%s\nstderr:\n%s\n' % (res.returncode, out, res.stderr))
    rows = []
    hdr = None
    for raw in out.splitlines():
        line = raw.strip()
        if not line:
            continue
        cells = [c.strip() for c in line.split(',')]
        if hdr is None:
            if 'pipe' in cells and 't_out_C' in cells:
                hdr = cells
            continue
        if len(cells) != len(hdr):
            continue
        r = dict(zip(hdr, cells))
        try:
            for kk in ('flow_t_h', 't_in_C', 't_out_C', 't_amb_C'):
                fnum(r[kk])
        except Exception:
            continue
        rows.append(r)
    if not rows:
        return None
    return rows


def sensitivity(pk, pipe, U, rel):
    """largest change in outlet temperature [K] over the line's records for a relative change
    `rel` in the pipe's Uo, treating the pipe as carrying its share of the line flow."""
    line = pk.pipes[pipe]
    L = pk.lines[line]
    recs = [r for r in pk.recs if r['line'] == line]
    if not recs:
        return 0.0, 0
    share = 1.0 / L['n']
    m = np.array([fnum(r['flow_t_h']) for r in recs]) / 3.6 * share
    Ta = np.array([fnum(r['t_amb_C']) for r in recs])
    Ti = np.array([fnum(r['t_in_C']) for r in recs])
    P = tuple(np.full(len(recs), x) for x in L['props'])
    T1, P1 = integrate(m, P, np.full(len(recs), U), Ta, Ti)
    T2, P2 = integrate(m, P, np.full(len(recs), U * (1 + rel)), Ta, Ti)
    dT = np.abs(T2 - T1) * share
    ddp = np.abs(P2 / P1 - 1)
    # in units of the tolerance (0.5 K, 1.5 %)
    score = np.maximum(dT / 0.5, ddp / 0.015)
    return float(score.max()), len(recs)


def split_roots(P, M, UA, UB, Ta, Tin):
    """All divisions of the line flow M between the two pipes of a pair that give both the same
    pressure drop (TS-2 4), for each element; returned as lists of fractions in pipe A."""
    n = len(M)
    Z = np.linspace(-12, 12, 121)
    K = len(Z)
    fa, fb = phis(Z)
    rep = lambda a: np.repeat(a, K)
    Pr = tuple(rep(x) for x in P)
    _, pa = integrate_chunked((M[:, None] * fa[None, :]).ravel(), Pr, rep(UA), rep(Ta), rep(Tin))
    _, pb = integrate_chunked((M[:, None] * fb[None, :]).ravel(), Pr, rep(UB), rep(Ta), rep(Tin))
    F = (pa - pb).reshape(n, K)
    out = []
    for i in range(n):
        f = F[i]
        ks = np.nonzero(np.sign(f[:-1]) != np.sign(f[1:]))[0]
        rs = []
        for k in ks:
            z = Z[k] + (Z[k + 1] - Z[k]) * f[k] / (f[k] - f[k + 1])
            rs.append(1.0 / (1.0 + np.exp(-z)))
        out.append(rs)
    return out


def pair_split_check(pk, S, U):
    """For each pair: how far the division of flow read at the surveys on file stands from the
    division TS-2 gives with the coefficients those surveys measured.  Returns line -> worst
    difference in the fraction of the flow, or None where no campaign surveyed both pipes."""
    by = {}
    for i, r in enumerate(S):
        by.setdefault((r['_d'], r['pipe']), i)
    rows = []
    for line, L in pk.lines.items():
        if L['n'] != 2:
            continue
        a, b = L['pipes']
        for (d, p), i in by.items():
            if p != a or (d, b) not in by:
                continue
            j = by[(d, b)]
            try:
                ma, mb = fnum(S[i]['flow_t_h']), fnum(S[j]['flow_t_h'])
                M = 0.5 * (fnum(S[i]['line_flow_t_h']) + fnum(S[j]['line_flow_t_h']))
                Ta = 0.5 * (fnum(S[i]['t_amb_C']) + fnum(S[j]['t_amb_C']))
                Ti = 0.5 * (fnum(S[i]['t_in_C']) + fnum(S[j]['t_in_C']))
            except Exception:
                continue
            if ma + mb <= 0:
                continue
            rows.append((line, M / 3.6, U[i], U[j], Ta, Ti, ma / (ma + mb)))
    res = {line: None for line, L in pk.lines.items() if L['n'] == 2}
    if not rows:
        return res
    P = pk.props_for([r[0] + '-A' for r in rows])
    roots = split_roots(P, np.array([r[1] for r in rows]), np.array([r[2] for r in rows]),
                        np.array([r[3] for r in rows]), np.array([r[4] for r in rows]),
                        np.array([r[5] for r in rows]))
    for r, rs in zip(rows, roots):
        d = min([abs(x - r[6]) for x in rs]) if rs else 1.0
        res[r[0]] = d if res[r[0]] is None else max(res[r[0]], d)
    return res


SPLIT_OK = 0.008      # a pair whose surveys divide as TS-2 does, to within this fraction


def infer_from_sibling(pk, line, row, Uq, eq):
    """Coefficient of the other pipe of a pair from a survey of one: the flow read in the
    surveyed pipe and in the line give the other pipe's flow, and the two pipes have the same
    pressure drop.  Returns (Uo, relative uncertainty) or None."""
    try:
        Ml = fnum(row['line_flow_t_h']) / 3.6
        mq = fnum(row['flow_t_h']) / 3.6
        Ta = fnum(row['t_amb_C'])
        Ti = fnum(row['t_in_C'])
    except Exception:
        return None
    props = pk.lines[line]['props']
    cases = [(1, 1, 1)]
    for sM, sq in ((1 + ERR_FLOW, 1 - ERR_FLOW), (1 - ERR_FLOW, 1 + ERR_FLOW)):
        cases.append((sM, sq, 1))
    cases.append((1, 1, 1 + eq))
    cases.append((1, 1, 1 - eq))
    lg = np.linspace(np.log(0.05), np.log(500.0), 240)
    G = len(lg)
    nc = len(cases)
    mp = np.concatenate([np.full(G, Ml * sM - mq * sq) for sM, sq, _ in cases])
    if np.any(mp <= 0):
        return None
    mqs = np.array([mq * sq for _, sq, _ in cases])
    Uqs = np.array([Uq * su for _, _, su in cases])
    allm = np.concatenate([mp, mqs])
    allU = np.concatenate([np.tile(np.exp(lg), nc), Uqs])
    N = len(allm)
    P = tuple(np.full(N, x) for x in props)
    _, dp = integrate(allm, P, allU, np.full(N, Ta), np.full(N, Ti))
    dpp = dp[:nc * G].reshape(nc, G)
    dpq = dp[nc * G:]
    vals = []
    for c in range(nc):
        f = dpp[c] - dpq[c]
        ks = np.nonzero(np.sign(f[:-1]) != np.sign(f[1:]))[0]
        if ks.size != 1:
            return None
        k = ks[0]
        vals.append(np.exp(lg[k] + (lg[k + 1] - lg[k]) * f[k] / (f[k] - f[k + 1])))
    U0 = vals[0]
    unc = (abs(vals[1] - vals[2]) / 2 + abs(vals[3] - vals[4]) / 2) / U0
    return float(U0), float(unc)


def combine(a, ua, b, ub):
    wa = 1.0 / max(ua, 1e-4) ** 2
    wb = 1.0 / max(ub, 1e-4) ** 2
    return (a * wa + b * wb) / (wa + wb), 1.0 / np.sqrt(wa + wb)


def determine_uo(pk):
    S = []
    for r in pk.surveys:
        p = pk.resolve_pipe(r.get('pipe', ''))
        if len(p) != 1:
            continue
        rr = dict(r)
        rr['pipe'] = p[0]
        rr['_d'] = pdate(r.get('date', ''))
        if rr['_d'] is None:
            rr['_d'] = 0
        S.append(rr)
    U, E = survey_rows_uo(pk, S)
    hist = {p: [] for p in pk.pipes}
    for i, r in enumerate(S):
        if np.isfinite(U[i]) and U[i] > 0:
            hist[r['pipe']].append((r['_d'], U[i], E[i]))
    for p in hist:
        hist[p].sort(key=lambda t: t[0])

    jobs = {p: [] for p in pk.pipes}
    for w in pk.work:
        kind = job_kind(w.get('job', ''))
        if kind is None:
            continue
        d = pdate(w.get('date', ''))
        for p in pk.resolve_pipe(w.get('pipe', '')):
            # a job of unknown date is taken as later than every survey
            jobs[p].append((d if d is not None else 10 ** 9, kind))
    all_dates = [t[0] for p in hist for t in hist[p]] + [d for p in jobs for d, _ in jobs[p] if d < 10 ** 9]
    t_now = (max(all_dates) if all_dates else 0) + 3

    # covering-change ratios seen in this package (for a pipe that cannot be surveyed)
    ratios = {'renew': [], 'repair': [], '': []}

    info = {}
    for p in pk.pipes:
        h = hist[p]
        ch = [d for d, k in jobs[p] if k.startswith('change')]
        mb = [d for d, k in jobs[p] if k == 'maybe']
        last_change = max(ch) if ch else None
        valid = [t for t in h if last_change is None or t[0] > last_change]
        before = [t for t in h if last_change is not None and t[0] < last_change]
        same = [t for t in h if last_change is not None and t[0] == last_change]
        if same:
            # a survey on the day of the work: after it if it no longer agrees with the
            # surveys before the work, otherwise taken as the covering before the work
            if before and not consistent([t[1] for t in before[-1:] + same[:1]],
                                         [t[2] for t in before[-1:] + same[:1]]):
                valid = same + valid
            else:
                before = before + same
        st = dict(valid=valid, before=before, cls=3, est=None, unc=0.0, kind='')
        for d, k in jobs[p]:
            if k.startswith('change'):
                b4 = [t for t in h if t[0] < d]
                af = [t for t in h if t[0] > d and not any(d < dd < t[0] for dd in ch)]
                if b4 and af:
                    kk = k.split(':')[1] if ':' in k else ''
                    ratios[kk].append(af[0][1] / b4[-1][1])
                if d == last_change:
                    st['kind'] = k.split(':')[1] if ':' in k else ''
        if not valid:
            st['cls'] = 0
        else:
            us = [t[1] for t in valid]
            es = [t[2] for t in valid]
            if len(valid) >= 2 and not consistent(us, es):
                # the covering has changed without a job on file
                st['cls'] = 1
                suf = 1
                while suf < len(valid) and consistent(us[-(suf + 1):], es[-(suf + 1):]):
                    suf += 1
                uu = np.array(us)
                ds = np.array([t[0] for t in valid], float)
                monotone = np.all(np.diff(uu) > 0) or np.all(np.diff(uu) < 0)
                if suf >= 2:
                    st['est'] = wmean(us[-suf:], es[-suf:])
                    st['unc'] = 0.05
                elif len(valid) >= 3 and monotone and not consistent(us[:-1], es[:-1]) and ds.max() > ds.min():
                    c = np.polyfit(ds - ds.mean(), uu, 1)
                    st['est'] = float(max(c[1] + c[0] * (t_now - ds.mean()), uu[-1] * 0.2))
                    st['unc'] = abs(st['est'] - uu[-1]) / uu[-1] + 0.05
                else:
                    st['est'] = float(uu[-1])
                    st['unc'] = 0.08
            else:
                st['est'] = wmean(us, es)
                st['unc'] = max(float(np.min(es)) / np.sqrt(len(us)),
                                (max(us) - min(us)) / st['est'])
                last_valid = valid[-1][0]
                if any(d > last_valid for d in mb):
                    st['cls'] = 2
                    st['unc'] = max(st['unc'], 0.1)
        info[p] = st

    def ratio_for(kind):
        r = ratios.get(kind) or ratios['renew'] + ratios['repair'] + ratios['']
        if r:
            return float(np.median(r))
        return {'renew': 0.5, 'repair': 0.65}.get(kind, 0.55)

    for p, st in info.items():
        if st['cls'] == 0:
            if st['before']:
                st['est'] = st['before'][-1][1] * ratio_for(st['kind'])
            else:
                others = [s['est'] for s in info.values() if s['est'] is not None]
                st['est'] = float(np.median(others)) if others else 6.0
            st['unc'] = 0.15

    try:
        split_dev = pair_split_check(pk, S, U)
    except Exception:
        split_dev = {}
    pair_ok = {l: (d is not None and d <= SPLIT_OK) for l, d in split_dev.items()}

    # ---- the survey order -------------------------------------------------------------
    try:
        allowance = int(float(pk.site.get('survey_allowance', 0)))
    except Exception:
        allowance = 0
    with_recs = set(r['line'] for r in pk.recs)
    needs, extras = [], []
    for p, st in info.items():
        if pk.pipes[p] not in with_recs:
            continue
        try:
            sc, _ = sensitivity(pk, p, st['est'], max(st['unc'], 0.005))
        except Exception:
            sc = 0.0
        (needs if st['cls'] < 3 else extras).append((st['cls'], -sc, p))
    needs.sort()
    extras.sort()
    needs = [p for _, _, p in needs]
    extras = [p for _, _, p in extras]

    def sibling(p):
        L = pk.lines[pk.pipes[p]]
        if L['n'] != 2:
            return None
        return [q for q in L['pipes'] if q != p][0]

    order = []
    covered = set()
    for p in needs:                       # every pipe that needs a survey, one way or another
        if len(order) >= allowance:
            break
        if p in covered:
            continue
        order.append(p)
        covered.add(p)
        q = sibling(p)
        if q is not None and pair_ok.get(pk.pipes[p]):
            covered.add(q)
    for p in needs + extras:              # then direct surveys, most useful first
        if len(order) >= allowance:
            break
        if p not in order:
            order.append(p)

    fresh = {}
    fresh_rows = {}
    if order:
        rows = place_order(pk.dir, order)
        if rows is not None:
            good = []
            for r in rows:
                pp = pk.resolve_pipe(r.get('pipe', ''))
                if len(pp) == 1:
                    r = dict(r)
                    r['pipe'] = pp[0]
                    good.append(r)
            Uf, Ef = survey_rows_uo(pk, good)
            for i, r in enumerate(good):
                if np.isfinite(Uf[i]) and Uf[i] > 0:
                    fresh.setdefault(r['pipe'], []).append((t_now, Uf[i], Ef[i]))
                    fresh_rows.setdefault(r['pipe'], []).append((r, Uf[i], Ef[i]))

    Uo = {}
    for p, st in info.items():
        if p in fresh:
            f = fresh[p]
            if st['cls'] in (0, 1):
                Uo[p] = wmean([t[1] for t in f], [t[2] for t in f])
            else:
                allv = st['valid'] + f
                us = [t[1] for t in allv]
                es = [t[2] for t in allv]
                if consistent(us, es):
                    Uo[p] = wmean(us, es)
                else:
                    Uo[p] = wmean([t[1] for t in f], [t[2] for t in f])
            st['src'] = 'survey'
        else:
            Uo[p] = st['est']
            st['src'] = 'file' if st['cls'] in (2, 3) else 'estimate'

    # a pipe left unsurveyed whose pair partner was surveyed now
    for p, st in info.items():
        if p in fresh or st['cls'] == 3:
            continue
        q = sibling(p)
        if q is None or q not in fresh_rows or not pair_ok.get(pk.pipes[p]):
            continue
        r, uq, eq = fresh_rows[q][0]
        try:
            inf = infer_from_sibling(pk, pk.pipes[p], r, Uo[q], eq)
        except Exception:
            inf = None
        if inf is None:
            continue
        ui, ei = inf
        if st['cls'] == 2:
            # keep the surveys on file unless the partner's survey shows the covering changed
            if abs(ui - st['est']) > 2 * (ei + 0.01) * st['est']:
                Uo[p] = ui
                st['src'] = 'partner'
        else:
            Uo[p] = ui if ei < 0.05 else combine(ui, ei, st['est'], st['unc'])[0]
            st['src'] = 'partner'
        st['inferred'] = (ui, ei)
    return Uo, order, info


def solve_singles(pk, idx, Uo, out_dp, out_T):
    if not idx:
        return
    recs = [pk.recs[i] for i in idx]
    lines = [r['line'] for r in recs]
    P = pk.props_for([l + '-A' for l in lines])
    m = np.array([fnum(r['flow_t_h']) for r in recs]) / 3.6
    Ta = np.array([fnum(r['t_amb_C']) for r in recs])
    Ti = np.array([fnum(r['t_in_C']) for r in recs])
    U = np.array([Uo[l + '-A'] for l in lines])
    T, dp = integrate_chunked(m, P, U, Ta, Ti)
    out_dp[idx] = dp / 1000.0
    out_T[idx] = T


def phis(z):
    """split fractions of pipe A and B for logit z, without cancellation"""
    return 1.0 / (1.0 + np.exp(-z)), 1.0 / (1.0 + np.exp(z))


ZGRID = np.concatenate([[-40.0, -30.0, -22.0, -17.0, -14.0], np.linspace(-12, 12, 121), [14.0, 17.0, 22.0, 30.0, 40.0]])


def solve_pairs(pk, runs, Uo, out_dp, out_T):
    """runs: list of record-index lists, one per pair line, in time order.
    The flow divides so that both pipes have the same pressure drop (TS-2 4).  Where the
    division has more than one solution the line holds the one it reaches from its state at
    the previous reading: the flow moves from the pipe with the higher drop to the other
    until the drops are equal."""
    if not runs:
        return
    allidx = [i for run in runs for i in run]
    R = len(allidx)
    pos = {i: j for j, i in enumerate(allidx)}
    recs = [pk.recs[i] for i in allidx]
    lines = [r['line'] for r in recs]
    P = pk.props_for([l + '-A' for l in lines])
    M = np.array([fnum(r['flow_t_h']) for r in recs]) / 3.6
    Ta = np.array([fnum(r['t_amb_C']) for r in recs])
    Ti = np.array([fnum(r['t_in_C']) for r in recs])
    UA = np.array([Uo[l + '-A'] for l in lines])
    UB = np.array([Uo[l + '-B'] for l in lines])

    # residual F = dpA - dpB on a logit grid of the split, every record at once
    K = len(ZGRID)
    fa, fb = phis(ZGRID)
    rep = lambda a: np.repeat(a, K)
    Pr = tuple(rep(x) for x in P)
    mA = (M[:, None] * fa[None, :]).ravel()
    mB = (M[:, None] * fb[None, :]).ravel()
    _, PA = integrate_chunked(mA, Pr, rep(UA), rep(Ta), rep(Ti))
    _, PB = integrate_chunked(mB, Pr, rep(UB), rep(Ta), rep(Ti))
    Fg = (PA - PB).reshape(R, K)
    del Pr, mA, mB, PA, PB

    def evalF(sel, z):
        a, b = phis(z)
        Ps = tuple(x[sel] for x in P)
        n = len(sel)
        T, dp = integrate(np.concatenate([M[sel] * a, M[sel] * b]),
                          tuple(np.concatenate([x, x]) for x in Ps),
                          np.concatenate([UA[sel], UB[sel]]),
                          np.concatenate([Ta[sel], Ta[sel]]),
                          np.concatenate([Ti[sel], Ti[sel]]))
        return dp[:n] - dp[n:], dp[:n], dp[n:], T[:n], T[n:]

    zprev = np.zeros(len(runs))
    maxlen = max(len(r) for r in runs)
    for j in range(maxlen):
        act = [q for q in range(len(runs)) if j < len(runs[q])]
        sel = np.array([pos[runs[q][j]] for q in act])
        zp = zprev[act]
        F0, pa0, pb0, ta0, tb0 = evalF(sel, zp)
        n = len(sel)
        lo = np.empty(n); hi = np.empty(n); flo = np.empty(n); fhi = np.empty(n)
        exact = np.zeros(n, bool)
        for t in range(n):
            r = sel[t]
            f0 = F0[t]
            if f0 == 0:
                exact[t] = True
                lo[t] = hi[t] = zp[t]; flo[t] = fhi[t] = 0
                continue
            Fr = Fg[r]
            if f0 < 0:      # flow moves into pipe A: z rises to the first point where F >= 0
                ks = np.nonzero((ZGRID > zp[t]) & (Fr >= 0))[0]
                if ks.size:
                    k = ks[0]
                    prev = np.nonzero((ZGRID > zp[t]) & (ZGRID < ZGRID[k]))[0]
                    if prev.size:
                        lo[t], flo[t] = ZGRID[prev[-1]], Fr[prev[-1]]
                    else:
                        lo[t], flo[t] = zp[t], f0
                    hi[t], fhi[t] = ZGRID[k], Fr[k]
                else:
                    lo[t], flo[t] = max(zp[t], ZGRID[-1]), (f0 if zp[t] >= ZGRID[-1] else Fr[-1])
                    hi[t], fhi[t] = 60.0, np.nan
            else:           # flow moves into pipe B: z falls to the first point where F <= 0
                ks = np.nonzero((ZGRID < zp[t]) & (Fr <= 0))[0]
                if ks.size:
                    k = ks[-1]
                    prev = np.nonzero((ZGRID < zp[t]) & (ZGRID > ZGRID[k]))[0]
                    if prev.size:
                        hi[t], fhi[t] = ZGRID[prev[0]], Fr[prev[0]]
                    else:
                        hi[t], fhi[t] = zp[t], f0
                    lo[t], flo[t] = ZGRID[k], Fr[k]
                else:
                    hi[t], fhi[t] = min(zp[t], ZGRID[0]), (f0 if zp[t] <= ZGRID[0] else Fr[0])
                    lo[t], flo[t] = -60.0, np.nan
        # beyond the grid: evaluate the far end
        far = np.isnan(flo) | np.isnan(fhi)
        if far.any():
            ii = np.nonzero(far)[0]
            zz = np.where(np.isnan(flo[ii]), lo[ii], hi[ii])
            Fz = evalF(sel[ii], zz)[0]
            flo[ii] = np.where(np.isnan(flo[ii]), Fz, flo[ii])
            fhi[ii] = np.where(np.isnan(fhi[ii]), Fz, fhi[ii])
        # exact zero at a bracket end
        zres = np.where(exact, zp, 0.0)
        for t in range(n):
            if not exact[t]:
                if flo[t] == 0:
                    exact[t] = True; zres[t] = lo[t]
                elif fhi[t] == 0:
                    exact[t] = True; zres[t] = hi[t]
        # Illinois refinement inside the brackets
        active = ~exact
        side = np.zeros(n)
        zc = zres.copy()
        for _ in range(60):
            ia = np.nonzero(active)[0]
            if ia.size == 0:
                break
            a, b, fa_, fb_ = lo[ia], hi[ia], flo[ia], fhi[ia]
            c = (a * fb_ - b * fa_) / (fb_ - fa_)
            c = np.where(np.isfinite(c) & (c > np.minimum(a, b)) & (c < np.maximum(a, b)), c, 0.5 * (a + b))
            Fc, pa, pb, _, _ = evalF(sel[ia], c)
            zc[ia] = c
            rel = np.abs(Fc) / (pa + pb)
            done = (rel < 1e-11) | (np.abs(b - a) < 1e-11)
            same = np.sign(Fc) == np.sign(fa_)
            sd = side[ia]
            na = np.where(same, c, a); nfa = np.where(same, Fc, fa_)
            nb = np.where(same, b, c); nfb = np.where(same, fb_, Fc)
            nfb = np.where(same & (sd == 1), 0.5 * nfb, nfb)
            nfa = np.where(~same & (sd == -1), 0.5 * nfa, nfa)
            lo[ia], flo[ia], hi[ia], fhi[ia] = na, nfa, nb, nfb
            side[ia] = np.where(same, 1, -1)
            active[ia[done]] = False
        F1, pa, pb, ta, tb = evalF(sel, zc)
        a, b = phis(zc)
        for t, q in enumerate(act):
            gi = allidx[sel[t]]
            out_dp[gi] = 0.5 * (pa[t] + pb[t]) / 1000.0
            out_T[gi] = a[t] * ta[t] + b[t] * tb[t]
        zprev[act] = zc


def fallback(pk, idx, Uo, out_dp, out_T):
    """Last resort for a record the solution above left without a result: a pair taken at the
    division that equalises the drops of the two pipes as if their resistances were fixed."""
    recs = [pk.recs[i] for i in idx]
    lines = [r['line'] for r in recs]
    P = pk.props_for([l + '-A' for l in lines])
    M = np.array([fnum(r['flow_t_h']) for r in recs]) / 3.6
    Ta = np.array([fnum(r['t_amb_C']) for r in recs])
    Ti = np.array([fnum(r['t_in_C']) for r in recs])
    UA = np.array([Uo[l + '-A'] for l in lines])
    UB = np.array([Uo.get(l + '-B', Uo[l + '-A']) for l in lines])
    two = np.array([pk.lines[l]['n'] == 2 for l in lines])
    ph = np.where(two, 0.5, 1.0)
    for _ in range(30):
        TA, PA = integrate(M * ph, P, UA, Ta, Ti)
        TB, PB = integrate(M * (1 - ph), P, UB, Ta, Ti)
        new = np.where(two, (PB / (1 - ph)) / (PA / ph + PB / (1 - ph)), 1.0)
        new = np.where(np.isfinite(new), np.clip(new, 1e-4, 1 - 1e-4), 0.5)
        ph = np.where(two, 0.5 * (ph + new), 1.0)
    TA, PA = integrate(M * ph, P, UA, Ta, Ti)
    TB, PB = integrate(M * np.maximum(1 - ph, 1e-12), P, UB, Ta, Ti)
    dp = np.where(two, 0.5 * (PA + PB), PA) / 1000.0
    T = np.where(two, ph * TA + (1 - ph) * TB, TA)
    for k, i in enumerate(idx):
        out_dp[i] = dp[k] if np.isfinite(dp[k]) else 0.0
        out_T[i] = T[k] if np.isfinite(T[k]) else Ti[k]


def main(argv):
    if len(argv) < 3:
        sys.stderr.write('usage: lines.py PACKAGE_DIR OUT_CSV\n')
        return 2
    pkg_dir, out_csv = argv[1], argv[2]
    np.seterr(all='ignore')
    pk = Package(pkg_dir)
    Uo, order, info = determine_uo(pk)
    if os.environ.get('LINES_DEBUG'):
        sys.stderr.write('survey order: %s\n' % ' '.join(order))
        for p in sorted(info):
            st = info[p]
            sys.stderr.write('%s cls=%d est=%.4f Uo=%.4f src=%s%s\n' % (
                p, st['cls'], st['est'], Uo[p], st.get('src'),
                ' inferred=%.4f+-%.4f' % st['inferred'] if 'inferred' in st else ''))

    N = len(pk.recs)
    out_dp = np.full(N, np.nan)
    out_T = np.full(N, np.nan)
    singles = []
    runs = {}
    for i, r in enumerate(pk.recs):
        L = pk.lines[r['line']]
        if L['n'] == 1:
            singles.append(i)
        else:
            runs.setdefault(r['line'], []).append(i)
    for line in runs:
        runs[line].sort(key=lambda i: (fnum(pk.recs[i].get('hour', 0) or 0), i))
    solve_singles(pk, singles, Uo, out_dp, out_T)
    try:
        solve_pairs(pk, list(runs.values()), Uo, out_dp, out_T)
    except Exception as e:                       # never leave a record without a result
        sys.stderr.write('pair solution failed: %r\n' % (e,))
    bad = [i for i in range(N) if not (np.isfinite(out_dp[i]) and np.isfinite(out_T[i]))]
    if bad:
        fallback(pk, bad, Uo, out_dp, out_T)

    with open(out_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['record', 'dp_kPa', 't_out_C'])
        for i, r in enumerate(pk.recs):
            w.writerow([r['record'], '%.4f' % out_dp[i], '%.3f' % out_T[i]])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
