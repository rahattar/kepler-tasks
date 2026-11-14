#!/usr/bin/env python3
"""Heated fuel oil lines to terminal standard TS-2, for one site package.

    python3 lines.py PACKAGE_DIR OUT_CSV

Writes OUT_CSV with `record,dp_kPa,t_out_C`, one row per row of records.csv.

Outline
  * Oil: constant rho, cp, k; ASTM D341 viscosity through the two tabulated points (TS-2 2).
  * One pipe: the heat balance 3.1-3.3 and the pressure gradient 3.4 are marched from the
    inlet manifold with RK4 in s = (x/L)^(1/3) (the entry-length term goes as x^(-1/3)) and
    in y = ln(Tb - Ta) (so that strong cooling of a starved pipe is not stiff).  The wall
    temperature is solved at each point by Newton's method.
  * Outside coefficient Uo of each pipe (TS-2 5.2, 5.3): the Uo that reproduces the surveyed
    outlet temperature, from surveys of the covering as it stands, i.e. after the last work
    on the covering.  A pipe with no such survey, or whose surveys drift by more than the
    reading tolerances of TS-2 5.4 allow, gets a fresh survey in the package's single
    survey order (heatsurvey), within the survey allowance.
  * Pairs (TS-2 4): the line flow divides so that both pipes have the same pressure drop.
    That equation can have several roots (flow maldistribution between cooled parallel
    pipes); a pair's records are an unbroken run in time order, so at each record the split
    is the stable root whose basin holds the split of the hour before.
"""
import csv
import json
import math
import os
import shutil
import subprocess
import sys
from collections import defaultdict

import numpy as np

PI = math.pi
LN10 = math.log(10.0)
T0C = 273.15
N_STEPS = 16          # RK4 steps along a pipe (converged to ~1e-5 relative)
NEWTON_WALL = 2       # Newton iterations for the wall temperature per evaluation
DRIFT_RATIO = 1.0     # spread of Uo over campaigns / reading-tolerance bound => covering drifting
SURVEY_TIMEOUT = 25.0

COVER_WORDS = ('cover', 'lag', 'insulat', 'clad', 'wrap')
NOT_WORK_WORDS = ('inspect', 'check', 'examin', 'survey', 'photograph', 'measur', 'noted', 'observ')


# ----------------------------------------------------------------------------------------------
# input
# ----------------------------------------------------------------------------------------------
def read_csv(path):
    with open(path, newline='') as f:
        rows = []
        for r in csv.DictReader(f):
            rows.append({(k or '').strip(): (v or '').strip() for k, v in r.items()})
        return rows


def norm_name(s):
    s = (s or '').strip().upper().replace('_', '-').replace(' ', '-')
    while '--' in s:
        s = s.replace('--', '-')
    return s


def fnum(s):
    return float(str(s).strip().replace(',', '.')) if not isinstance(s, (int, float)) else float(s)


def oil_params(row):
    rho = fnum(row['density_kg_m3'])
    cp = fnum(row['cp_J_kgK'])
    k = fnum(row['k_W_mK'])
    v1 = fnum(row['nu50_cSt'])
    v2 = fnum(row['nu100_cSt'])
    T1, T2 = 50.0 + T0C, 100.0 + T0C
    Y1 = math.log10(math.log10(v1 + 0.7))
    Y2 = math.log10(math.log10(v2 + 0.7))
    B = (Y1 - Y2) / (math.log10(T2) - math.log10(T1))
    A = Y1 + B * math.log10(T1)
    return dict(rho=rho, cp=cp, k=k, A=A, B=B)


# ----------------------------------------------------------------------------------------------
# one pipe (TS-2 3)
# ----------------------------------------------------------------------------------------------
def nu_cSt(T, A, B):
    return 10.0 ** (10.0 ** (A - B * np.log10(T))) - 0.7


def pipe(m, Tin, Ta, Uo, D, L, rho, cp, k, A, B, N=N_STEPS, newton=NEWTON_WALL):
    """Vectorised: returns (outlet bulk temperature K, pressure drop Pa).
    m kg/s, temperatures K, Uo W/m2K on the bore, D and L m."""
    arrs = np.broadcast_arrays(*[np.asarray(a, float) for a in (m, Tin, Ta, Uo, D, L, rho, cp, k, A, B)])
    m, Tin, Ta, Uo, D, L, rho, cp, k, A, B = [np.array(a) for a in arrs]
    shape = m.shape
    m = np.maximum(m, 1e-12)
    u = 4.0 * m / (PI * D * D * rho)
    gzc = 4.0 * m * cp / (PI * k)            # Gz = Re Pr D / x = 4 m cp / (pi k x)
    kD = k / D
    c_dp = 32.0 * u * rho * 1e-6 / (D * D)    # -dp/dx = 32 u sqrt(mu_b mu_w) / D^2, v in cSt
    c_T = PI * D * Uo / (m * cp)
    dT_in = Tin - Ta
    sgn = np.where(dT_in < 0.0, -1.0, 1.0)
    y = np.log(np.maximum(np.abs(dT_in), 1e-9))
    P = np.zeros(shape)
    psi = np.ones(shape)                     # (Tw - Ta) / (Tb - Ta)
    ds = 1.0 / N
    p = 3.0

    def rhs(s, y, psi):
        dT0 = sgn * np.exp(np.maximum(y, -60.0))
        Tb = Ta + dT0
        vb = nu_cSt(Tb, A, B)
        dxds = p * L * s * s
        if s <= 0.0:
            return -c_T * dxds, c_dp * vb * dxds, np.ones(shape)
        x = L * s ** p
        nu0 = np.cbrt(3.66 ** 3 + 0.7 ** 3 + (1.077 * np.cbrt(gzc / x) - 0.7) ** 3)
        h0 = kD * nu0
        for _ in range(newton):
            Tw = Ta + psi * dT0
            Z = 10.0 ** (A - B * np.log10(Tw))
            vp = 10.0 ** Z
            vw = vp - 0.7
            dlv = -(vp * LN10 * B * Z / Tw) / vw          # d ln(v)/dT at the wall
            r = h0 * (vb / vw) ** 0.14
            g = r * (1.0 - psi) - Uo * psi
            dg = r * (-0.14 * dlv * dT0 * (1.0 - psi) - 1.0) - Uo
            psi = np.clip(psi - g / dg, 0.0, 1.0)
        Tw = Ta + psi * dT0
        vw = nu_cSt(Tw, A, B)
        return -c_T * psi * dxds, c_dp * np.sqrt(vb * vw) * dxds, psi

    for i in range(N):
        s0 = i * ds
        k1, q1, psi = rhs(s0, y, psi)
        k2, q2, psi = rhs(s0 + 0.5 * ds, y + 0.5 * ds * k1, psi)
        k3, q3, psi = rhs(s0 + 0.5 * ds, y + 0.5 * ds * k2, psi)
        k4, q4, psi = rhs(s0 + ds, y + ds * k3, psi)
        y = y + ds / 6.0 * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        P = P + ds / 6.0 * (q1 + 2.0 * q2 + 2.0 * q3 + q4)
    return Ta + sgn * np.exp(y), P


def illinois(f, a, b, fa, fb, iters=60, xtol=1e-11):
    """Vectorised bracketed root finding (Illinois).  fa, fb must differ in sign."""
    a = np.array(a, float); b = np.array(b, float)
    fa = np.array(fa, float); fb = np.array(fb, float)
    side = np.zeros(a.shape)
    x = 0.5 * (a + b)
    for _ in range(iters):
        if a.size == 0 or np.all(np.abs(b - a) <= xtol * np.maximum(1.0, np.abs(a))):
            break
        x = (a * fb - b * fa) / (fb - fa)
        bad = ~np.isfinite(x) | (x <= np.minimum(a, b)) | (x >= np.maximum(a, b))
        x = np.where(bad, 0.5 * (a + b), x)
        fx = f(x)
        keep_b = np.sign(fx) == np.sign(fa)        # root between x and b
        a_new = np.where(keep_b, x, a); fa_new = np.where(keep_b, fx, fa)
        b_new = np.where(keep_b, b, x); fb_new = np.where(keep_b, fb, fx)
        fb_new = np.where(keep_b & (side == 1), 0.5 * fb_new, fb_new)
        fa_new = np.where(~keep_b & (side == -1), 0.5 * fa_new, fa_new)
        side = np.where(keep_b, 1, -1)
        a, fa, b, fb = a_new, fa_new, b_new, fb_new
    return np.where(np.abs(fa) < np.abs(fb), a, b) if a.size else a


# ----------------------------------------------------------------------------------------------
# outside coefficient from surveys (TS-2 5.2)
# ----------------------------------------------------------------------------------------------
def fit_uo(m, Tin, Tout, Ta, D, L, rho, cp, k, A, B):
    def f(lnU):
        T, _ = pipe(m, Tin, Ta, np.exp(lnU), D, L, rho, cp, k, A, B, N=24)
        return T - Tout
    n = np.shape(m)
    lo = np.full(n, math.log(1e-4)); hi = np.full(n, math.log(1e4))
    flo = f(lo); fhi = f(hi)
    ok = np.sign(flo) != np.sign(fhi)
    lo2 = np.where(ok, lo, lo); hi2 = np.where(ok, hi, hi)
    fhi2 = np.where(ok, fhi, -flo + 1e-9)        # degenerate rows: give some bracket, flagged below
    r = illinois(f, lo2, hi2, flo, fhi2, iters=100, xtol=1e-12)
    U = np.exp(r)
    U = np.where(ok, U, np.nan)
    return U


# ----------------------------------------------------------------------------------------------
# main calculation
# ----------------------------------------------------------------------------------------------
class Package:
    def __init__(self, pkg):
        self.dir = pkg
        try:
            self.site = json.load(open(os.path.join(pkg, 'site.json')))
        except Exception:
            self.site = {}
        self.oils = {r['oil'].strip(): oil_params(r) for r in read_csv(os.path.join(pkg, 'oils.csv'))}
        self.lines = {}
        for r in read_csv(os.path.join(pkg, 'lines.csv')):
            name = norm_name(r['line'])
            npipes = int(round(fnum(r['pipes'])))
            self.lines[name] = dict(name=name, npipes=npipes, D=fnum(r['bore_mm']) / 1000.0,
                                    L=fnum(r['length_m']), oil=r['oil'].strip())
        self.pipes = {}
        for ln, r in self.lines.items():
            for suf in ('A', 'B')[:max(1, min(2, r['npipes']))]:
                self.pipes[ln + '-' + suf] = ln
        self.surveys = read_csv(os.path.join(pkg, 'surveys.csv')) if os.path.exists(
            os.path.join(pkg, 'surveys.csv')) else []
        self.work = read_csv(os.path.join(pkg, 'work_log.csv')) if os.path.exists(
            os.path.join(pkg, 'work_log.csv')) else []
        self.records = read_csv(os.path.join(pkg, 'records.csv'))

    def oilv(self, line, key):
        return self.oils[self.lines[line]['oil']][key]


def covering_work_dates(pk):
    """Latest date of work on each pipe's covering."""
    last = {}
    for w in pk.work:
        job = (w.get('job') or '').lower()
        if not any(word in job for word in COVER_WORDS):
            continue
        if any(word in job for word in NOT_WORK_WORDS):
            continue
        name = norm_name(w.get('pipe', ''))
        targets = []
        if name in pk.pipes:
            targets = [name]
        elif name in pk.lines:
            targets = [p for p, l in pk.pipes.items() if l == name]
        for p in targets:
            d = (w.get('date') or '').strip()
            if p not in last or d > last[p]:
                last[p] = d
    return last


def survey_arrays(pk, rows):
    lines = [pk.pipes[norm_name(r['pipe'])] for r in rows]
    a = dict(
        m=np.array([fnum(r['flow_t_h']) / 3.6 for r in rows]),
        Tin=np.array([fnum(r['t_in_C']) + T0C for r in rows]),
        Tout=np.array([fnum(r['t_out_C']) + T0C for r in rows]),
        Ta=np.array([fnum(r['t_amb_C']) + T0C for r in rows]),
        D=np.array([pk.lines[l]['D'] for l in lines]),
        L=np.array([pk.lines[l]['L'] for l in lines]),
    )
    for key in ('rho', 'cp', 'k', 'A', 'B'):
        a[key] = np.array([pk.oilv(l, key) for l in lines])
    return a


def fit_rows(pk, rows, with_bounds=False):
    """Uo for each survey row; optionally the bound on Uo from the reading tolerances (TS-2 5.4)."""
    if not rows:
        return np.zeros(0), np.zeros(0)
    a = survey_arrays(pk, rows)
    n = len(rows)
    if not with_bounds:
        U = fit_uo(a['m'], a['Tin'], a['Tout'], a['Ta'], a['D'], a['L'],
                   a['rho'], a['cp'], a['k'], a['A'], a['B'])
        return U, np.zeros(n)
    rep = lambda v: np.tile(v, 5)
    m = rep(a['m']); Tin = rep(a['Tin']); Tout = rep(a['Tout']); Ta = rep(a['Ta'])
    m[n:2 * n] *= 1.002
    Tin[2 * n:3 * n] += 0.02
    Tout[3 * n:4 * n] += 0.02
    Ta[4 * n:5 * n] += 0.1
    U = fit_uo(m, Tin, Tout, Ta, rep(a['D']), rep(a['L']), rep(a['rho']), rep(a['cp']),
               rep(a['k']), rep(a['A']), rep(a['B']))
    U0 = U[:n]
    bound = sum(np.abs(U[j * n:(j + 1) * n] - U0) for j in range(1, 5))
    return U0, bound


def run_survey(pk, pipes):
    """Place the package's one survey order.  Returns {pipe: row}."""
    if not pipes:
        return {}
    exe = shutil.which('heatsurvey')
    if exe is None:
        return {}
    try:
        res = subprocess.run([exe, pk.dir] + list(pipes), capture_output=True, text=True,
                             timeout=SURVEY_TIMEOUT)
    except Exception as e:
        sys.stderr.write('heatsurvey failed: %s\n' % e)
        return {}
    if res.returncode != 0:
        sys.stderr.write('heatsurvey refused (%d): %s %s\n' % (res.returncode, res.stdout.strip(),
                                                               res.stderr.strip()))
    out = {}
    header = None
    for raw in res.stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        cells = [c.strip() for c in line.split(',')]
        if header is None:
            if 'pipe' in cells and 't_out_C' in cells:
                header = cells
            continue
        if len(cells) != len(header):
            continue
        row = dict(zip(header, cells))
        name = norm_name(row.get('pipe', ''))
        if name not in pk.pipes:
            continue
        try:
            for key in ('flow_t_h', 't_in_C', 't_out_C', 't_amb_C'):
                fnum(row[key])
        except Exception:
            continue
        row['pipe'] = name
        out[name] = row
    if not out and res.returncode == 0 and res.stdout.strip():
        sys.stderr.write('heatsurvey output not understood: %s\n' % res.stdout.strip()[:500])
    return out


def infer_partner_uo(pk, row, Ux, other):
    """Uo of pipe `other` from a survey of its partner: the partner's flow is the line flow less
    the surveyed pipe's flow, and both pipes have the same pressure drop (TS-2 4)."""
    try:
        M = fnum(row['line_flow_t_h']) / 3.6
        mx = fnum(row['flow_t_h']) / 3.6
    except Exception:
        return None
    my = M - mx
    if not (my > 0 and np.isfinite(Ux)):
        return None
    ln = pk.pipes[other]
    lp = pk.lines[ln]
    o = pk.oils[lp['oil']]
    Tin = fnum(row['t_in_C']) + T0C
    Ta = fnum(row['t_amb_C']) + T0C
    _, Px = pipe(np.array([mx]), Tin, Ta, Ux, lp['D'], lp['L'], o['rho'], o['cp'], o['k'], o['A'], o['B'])

    def f(lnU):
        _, P = pipe(np.array([my]) * np.ones_like(lnU), Tin, Ta, np.exp(lnU), lp['D'], lp['L'],
                    o['rho'], o['cp'], o['k'], o['A'], o['B'])
        return np.log(P / Px[0])
    lo = np.array([math.log(1e-3)]); hi = np.array([math.log(1e3)])
    flo = f(lo); fhi = f(hi)
    if not (np.sign(flo[0]) != np.sign(fhi[0])):
        return None
    r = illinois(f, lo, hi, flo, fhi, iters=80)
    U = float(np.exp(r[0]))
    return U if np.isfinite(U) else None


def outside_coefficients(pk):
    """Uo of every pipe as its covering stands (TS-2 5.2, 5.3), placing the survey order."""
    work_date = covering_work_dates(pk)
    srows = [r for r in pk.surveys if norm_name(r.get('pipe', '')) in pk.pipes]
    U, bound = fit_rows(pk, srows, with_bounds=True)
    per = defaultdict(list)
    for r, u, b in zip(srows, U, bound):
        if np.isfinite(u):
            per[norm_name(r['pipe'])].append(((r.get('date') or '').strip(), float(u), float(b)))

    est = {}          # pipe -> Uo from the surveys on file
    status = {}       # pipe -> 'ok' | 'none' | 'drift'
    score = {}
    for p in pk.pipes:
        lst = sorted(per.get(p, []))
        wd = work_date.get(p)
        valid = [x for x in lst if wd is None or x[0] > wd]
        if not valid:
            status[p] = 'none'
            est[p] = lst[-1][1] if lst else None       # stale fallback: the covering before the work
            score[p] = 1e9
            continue
        us = np.array([x[1] for x in valid])
        bs = np.array([x[2] for x in valid])
        if len(valid) >= 2:
            ratio = (us.max() - us.min()) / max(float(np.mean(bs)), 1e-12)
        else:
            ratio = 0.0
        if ratio > DRIFT_RATIO:
            status[p] = 'drift'
            est[p] = float(us[-1])                     # most recent state on file
            score[p] = ratio
        else:
            status[p] = 'ok'
            est[p] = float(np.mean(us))
            score[p] = ratio

    # ---- the survey order ----------------------------------------------------------------
    allowance = pk.site.get('survey_allowance', 0)
    try:
        allowance = int(allowance)
    except Exception:
        allowance = 0
    n_rec = defaultdict(int)
    for r in pk.records:
        n_rec[norm_name(r.get('line', ''))] += 1

    def weight(p):
        return n_rec.get(pk.pipes[p], 0)

    need = [p for p in pk.pipes if status[p] != 'ok']
    tier1, tier2, tier3 = [], [], []
    seen_pair = set()
    for p in sorted(need, key=lambda q: (status[q] != 'none', -weight(q), q)):
        ln = pk.pipes[p]
        partner = [q for q in pk.pipes if pk.pipes[q] == ln and q != p]
        if status[p] == 'none':
            if not partner or ln not in seen_pair:
                tier1.append(p)
                seen_pair.add(ln)
            else:
                tier3.append(p)          # partner surveyed: this one can be inferred from the split
        else:
            tier2.append(p)
    tier2.sort(key=lambda q: -score[q] * max(weight(q), 1))
    order = (tier1 + tier2 + tier3)[:max(0, allowance)]

    fresh = run_survey(pk, order) if order else {}
    Ufresh = {}
    if fresh:
        rows = list(fresh.values())
        Uf, _ = fit_rows(pk, rows)
        for r, u in zip(rows, Uf):
            if np.isfinite(u):
                Ufresh[r['pipe']] = float(u)

    Uo = {}
    for p in pk.pipes:
        if p in Ufresh:
            Uo[p] = Ufresh[p]
        else:
            Uo[p] = est[p]
    # pipes still without a survey of their covering as it stands: infer from a partner's survey
    for p in pk.pipes:
        if p in Ufresh or status[p] == 'ok':
            continue
        ln = pk.pipes[p]
        partner = [q for q in pk.pipes if pk.pipes[q] == ln and q != p]
        if partner and partner[0] in Ufresh:
            u = infer_partner_uo(pk, fresh[partner[0]], Ufresh[partner[0]], p)
            if u is not None:
                Uo[p] = u
    for p in pk.pipes:
        if Uo[p] is None or not np.isfinite(Uo[p]):
            Uo[p] = float(np.nanmedian([v for v in Uo.values() if v is not None])) if Uo else 5.0
    info = dict(order=order, fresh=sorted(Ufresh), status=status)
    return Uo, info


# ----------------------------------------------------------------------------------------------
# pairs (TS-2 4)
# ----------------------------------------------------------------------------------------------
ZGRID = np.linspace(-7.0, 7.0, 71)


def phi_of(z):
    return 0.5 * (1.0 + np.tanh(z))


def pair_eval(z, M, Tin, Ta, UA, UB, D, L, o):
    """f = (dpA - dpB)/(dpA + dpB) for the split phi(z) to pipe A; also the outputs."""
    ph = phi_of(z)
    mm = np.concatenate([ph * M, (1.0 - ph) * M])
    cat = lambda v: np.concatenate([v, v])
    T, P = pipe(mm, cat(Tin), cat(Ta), np.concatenate([UA, UB]), cat(D), cat(L),
                cat(o['rho']), cat(o['cp']), cat(o['k']), cat(o['A']), cat(o['B']))
    n = ph.size
    PA, PB = P[:n], P[n:]
    TA, TB = T[:n], T[n:]
    return (PA - PB) / (PA + PB), ph, PA, PB, TA, TB


def pair_roots(M, Tin, Ta, UA, UB, D, L, o):
    """All roots of the split equation for each record.
    Returns list (per record) of sorted lists of (z, stable)."""
    n = M.size
    G = ZGRID.size
    rep = lambda v: np.repeat(v, G)
    zz = np.tile(ZGRID, n)
    oo = {k: rep(v) for k, v in o.items()}
    F = pair_eval(zz, rep(M), rep(Tin), rep(Ta), rep(UA), rep(UB), rep(D), rep(L), oo)[0].reshape(n, G)
    F = np.where(np.isfinite(F), F, 0.0)

    # near-fold check: two close roots can hide inside the grid where |F| has a local minimum
    # without a change of sign; probe such places on two finer sub-grids.
    extra = defaultdict(list)          # record -> list of (z, f) probe points
    h = ZGRID[1] - ZGRID[0]
    s = np.sign(F)
    absF = np.abs(F)
    cand = (s[:, 1:-1] == s[:, :-2]) & (s[:, 1:-1] == s[:, 2:]) & \
           (absF[:, 1:-1] < absF[:, :-2]) & (absF[:, 1:-1] < absF[:, 2:])
    ci, cj = np.nonzero(cand)
    zc = ZGRID[cj + 1] if ci.size else np.zeros(0)
    fc = F[ci, cj + 1] if ci.size else np.zeros(0)
    width = h
    for level in range(2):
        if ci.size == 0:
            break
        offs = np.linspace(-width, width, 9)
        K = offs.size
        zs = (zc[:, None] + offs[None, :]).ravel()
        ii = np.repeat(ci, K)
        fs = pair_eval(zs, M[ii], Tin[ii], Ta[ii], UA[ii], UB[ii], D[ii], L[ii],
                       {k: v[ii] for k, v in o.items()})[0]
        fs = np.where(np.isfinite(fs), fs, fc.repeat(K))
        for i, z_, f_ in zip(ii, zs, fs):
            extra[int(i)].append((float(z_), float(f_)))
        fs = fs.reshape(-1, K)
        flipped = np.any(np.sign(fs) != np.sign(fc)[:, None], axis=1)
        keep = ~flipped
        jmin = np.argmin(np.abs(fs), axis=1)
        zc = (zc[:, None] + offs[None, :])[np.arange(len(zc)), jmin][keep]
        fc = fs[np.arange(len(fs)), jmin][keep]
        ci = ci[keep]
        width = width / 4.0

    # brackets
    bi, ba, bb, fa, fb = [], [], [], [], []
    for i in range(n):
        pts = list(zip(ZGRID.tolist(), F[i].tolist()))
        if i in extra:
            pts += [pz for pz in extra[i] if np.isfinite(pz[1])]
            pts.sort()
        for (z0, f0_), (z1, f1_) in zip(pts[:-1], pts[1:]):
            if f0_ == 0.0:
                f0_ = -1e-300 if f1_ > 0 else 1e-300
            if (f0_ < 0) != (f1_ < 0):
                bi.append(i); ba.append(z0); bb.append(z1); fa.append(f0_); fb.append(f1_)
    bi = np.array(bi, int)
    out = [[] for _ in range(n)]
    if bi.size == 0:
        return out
    ba = np.array(ba); bb = np.array(bb); fa = np.array(fa); fb = np.array(fb)
    sub = {k: v[bi] for k, v in o.items()}
    args = (M[bi], Tin[bi], Ta[bi], UA[bi], UB[bi], D[bi], L[bi], sub)
    zr = illinois(lambda z: pair_eval(z, *args)[0], ba, bb, fa, fb, iters=60, xtol=1e-10)
    stable = fb > fa                       # f rises through the root: a stable split
    for i, z_, st in zip(bi, zr, stable):
        out[int(i)].append((float(z_), bool(st)))
    for lst in out:
        lst.sort()
    return out


def choose_root(roots, zprev):
    """The stable root whose basin holds zprev: no unstable root between them."""
    stables = [z for z, st in roots if st]
    if not stables:
        return min(roots, key=lambda r: abs(r[0] - (zprev if zprev is not None else 0.0)))[0] if roots else 0.0
    if len(stables) == 1 or zprev is None:
        return stables[0] if len(stables) == 1 else None
    unst = [z for z, st in roots if not st]
    best = None
    for zs in stables:
        lo, hi = min(zs, zprev), max(zs, zprev)
        if not any(lo < zu < hi for zu in unst):
            if best is None or abs(zs - zprev) < abs(best - zprev):
                best = zs
    if best is None:
        best = min(stables, key=lambda zs: abs(zs - zprev))
    return best


def first_state(M, Tin, Ta, UA, UB, D, L, o, rating):
    """Split at a line's first record when that record admits more than one stable split:
    the state reached by bringing the line down from a flow with a single split."""
    Mhi = max(rating or 0.0, M)
    for _ in range(12):
        r = pair_roots(np.array([Mhi]), np.array([Tin]), np.array([Ta]), np.array([UA]),
                       np.array([UB]), np.array([D]), np.array([L]),
                       {k: np.array([v]) for k, v in o.items()})[0]
        if len([1 for z, st in r if st]) <= 1:
            break
        Mhi *= 2.0
    flows = np.geomspace(Mhi, M, 12) if Mhi > M else np.array([M])
    zprev = None
    seq = pair_roots(flows, np.full(flows.size, Tin), np.full(flows.size, Ta), np.full(flows.size, UA),
                     np.full(flows.size, UB), np.full(flows.size, D), np.full(flows.size, L),
                     {k: np.full(flows.size, v) for k, v in o.items()})
    for r in seq:
        z = choose_root(r, zprev)
        if z is None:
            z = choose_root(r, 0.0 if zprev is None else zprev)
            if z is None:
                z = [zz for zz, st in r if st][0]
        zprev = z
    return zprev


# ----------------------------------------------------------------------------------------------
def fmt(x, sig=6):
    if not np.isfinite(x):
        return 'nan'
    if x == 0:
        return '0'
    e = int(math.floor(math.log10(abs(x))))
    dec = max(0, sig - 1 - e)
    return ('%.*f' % (dec, x))


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: python3 lines.py PACKAGE_DIR OUT_CSV\n')
        return 2
    pkg_dir, out_csv = os.path.abspath(argv[1]), argv[2]
    np.seterr(all='ignore')
    pk = Package(pkg_dir)
    Uo, info = outside_coefficients(pk)

    # survey rating of each line (flow delivered to the line during the surveys on file)
    rating = defaultdict(list)
    for r in pk.surveys:
        p = norm_name(r.get('pipe', ''))
        if p in pk.pipes:
            try:
                rating[pk.pipes[p]].append(fnum(r['line_flow_t_h']) / 3.6)
            except Exception:
                pass

    res_dp = {}
    res_T = {}
    by_line = defaultdict(list)
    for idx, r in enumerate(pk.records):
        by_line[norm_name(r['line'])].append(idx)

    def hour_key(i):
        try:
            return fnum(pk.records[i].get('hour', i))
        except Exception:
            return float(i)

    singles, pairs = [], []
    for ln, idxs in by_line.items():
        idxs.sort(key=lambda i: (hour_key(i), i))
        (pairs if pk.lines[ln]['npipes'] >= 2 else singles).append(ln)

    def rec_arrays(idxs, ln):
        rr = [pk.records[i] for i in idxs]
        M = np.array([fnum(r['flow_t_h']) / 3.6 for r in rr])
        Tin = np.array([fnum(r['t_in_C']) + T0C for r in rr])
        Ta = np.array([fnum(r['t_amb_C']) + T0C for r in rr])
        return M, Tin, Ta

    # ---- single pipes -----------------------------------------------------------------------
    if singles:
        cols = defaultdict(list)
        order = []
        for ln in singles:
            idxs = by_line[ln]
            M, Tin, Ta = rec_arrays(idxs, ln)
            lp = pk.lines[ln]
            o = pk.oils[lp['oil']]
            n = len(idxs)
            for key, v in (('M', M), ('Tin', Tin), ('Ta', Ta), ('U', np.full(n, Uo[ln + '-A'])),
                           ('D', np.full(n, lp['D'])), ('L', np.full(n, lp['L']))):
                cols[key].append(v)
            for key in ('rho', 'cp', 'k', 'A', 'B'):
                cols[key].append(np.full(n, o[key]))
            order += idxs
        c = {k: np.concatenate(v) for k, v in cols.items()}
        T, P = pipe(c['M'], c['Tin'], c['Ta'], c['U'], c['D'], c['L'], c['rho'], c['cp'], c['k'],
                    c['A'], c['B'])
        for i, t, p in zip(order, T, P):
            res_T[i] = t - T0C
            res_dp[i] = p / 1000.0

    # ---- pairs ------------------------------------------------------------------------------
    if pairs:
        cols = defaultdict(list)
        order = []
        for ln in pairs:
            idxs = by_line[ln]
            M, Tin, Ta = rec_arrays(idxs, ln)
            lp = pk.lines[ln]
            o = pk.oils[lp['oil']]
            n = len(idxs)
            for key, v in (('M', M), ('Tin', Tin), ('Ta', Ta), ('UA', np.full(n, Uo[ln + '-A'])),
                           ('UB', np.full(n, Uo[ln + '-B'])), ('D', np.full(n, lp['D'])),
                           ('L', np.full(n, lp['L']))):
                cols[key].append(v)
            for key in ('rho', 'cp', 'k', 'A', 'B'):
                cols[key].append(np.full(n, o[key]))
            order += idxs
        c = {k: np.concatenate(v) for k, v in cols.items()}
        oc = {k: c[k] for k in ('rho', 'cp', 'k', 'A', 'B')}
        roots = pair_roots(c['M'], c['Tin'], c['Ta'], c['UA'], c['UB'], c['D'], c['L'], oc)
        pos = {i: j for j, i in enumerate(order)}
        zsel = np.zeros(len(order))
        for ln in pairs:
            zprev = None
            for k, i in enumerate(by_line[ln]):
                j = pos[i]
                r = roots[j]
                if not r:
                    z = 0.0
                elif zprev is None:
                    st = [zz for zz, s_ in r if s_]
                    if len(st) == 1:
                        z = st[0]
                    else:
                        z = first_state(c['M'][j], c['Tin'][j], c['Ta'][j], c['UA'][j], c['UB'][j],
                                        c['D'][j], c['L'][j], {kk: v[j] for kk, v in oc.items()},
                                        float(np.median(rating[ln])) if rating.get(ln) else None)
                        if z is None or not np.isfinite(z):
                            z = st[0] if st else r[0][0]
                        # snap to the record's own root
                        z = choose_root(r, z)
                else:
                    z = choose_root(r, zprev)
                zsel[j] = z
                zprev = z
        f, ph, PA, PB, TA, TB = pair_eval(zsel, c['M'], c['Tin'], c['Ta'], c['UA'], c['UB'], c['D'],
                                          c['L'], oc)
        Tmix = ph * TA + (1.0 - ph) * TB
        for j, i in enumerate(order):
            res_T[i] = Tmix[j] - T0C
            res_dp[i] = 0.5 * (PA[j] + PB[j]) / 1000.0

    with open(out_csv, 'w', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['record', 'dp_kPa', 't_out_C'])
        for i, r in enumerate(pk.records):
            w.writerow([r['record'], fmt(res_dp.get(i, float('nan'))), fmt(res_T.get(i, float('nan')), 6)])
    if os.environ.get('LINES_DEBUG'):
        sys.stderr.write(json.dumps(dict(order=info['order'], fresh=info['fresh'],
                                         Uo={k: round(v, 4) for k, v in Uo.items()})) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
