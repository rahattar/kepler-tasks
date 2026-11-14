#!/usr/bin/env python3
"""TS-2 heated oil transfer lines: pressure drop and outlet temperature for every record of a site.

Usage: python3 lines.py PACKAGE_DIR OUT_CSV
"""
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')

import numpy as np  # noqa: E402

LN10 = math.log(10.0)
NU_C3 = 3.66 ** 3 + 0.7 ** 3
N_FINAL = 32      # RK4 steps (in t, x = L t^3) for reported results and survey inversion
N_ROOT = 20       # RK4 steps for locating the division of a pair
ZMAX = 16.0       # division searched over s = 1/(1+exp(-z)), |z| <= ZMAX
NZ = 161          # grid points in z
# reading tolerances of a survey (TS-2 5.4)
TOL_FLOW = 0.002
TOL_TOIL = 0.02
TOL_TAMB = 0.1
DRIFT_LIMIT = 1.2  # consistency statistic beyond which a covering is taken to be changing


def log(*a):
    print(*a, file=sys.stderr)


# ---------------------------------------------------------------------------------------------
# oil and pipe model (TS-2 sections 2 and 3)
# ---------------------------------------------------------------------------------------------

def visc_params(nu50, nu100):
    T1, T2 = 323.15, 373.15
    y1 = math.log10(math.log10(nu50 + 0.7))
    y2 = math.log10(math.log10(nu100 + 0.7))
    B = (y1 - y2) / (math.log10(T2) - math.log10(T1))
    A = y1 + B * math.log10(T1)
    return A, B


def lnmu(T, Aln, B, lnrho):
    """ln(dynamic viscosity / Pa s) and its derivative in T (C)."""
    TK = T + 273.15
    Z = np.exp(Aln - B * np.log(TK))
    E = np.exp(Z * LN10)          # nu + 0.7, cSt
    nu = E - 0.7
    lm = lnrho + np.log(nu) - 6 * LN10
    dlm = -(E / nu) * LN10 * B * Z / TK
    return lm, dlm


def solve_pipes(D, L, Uo, m, Tin, Ta, rho, cp, k, A, B, N=N_FINAL):
    """Integrate TS-2 3.1-3.5 along a pipe for arrays of cases.

    Integration variable t with x = L t^3 (smooth at the thermal entry); state ln(Tb - Ta) and p.
    Returns pressure drop (Pa) and outlet bulk temperature (C)."""
    D, L, Uo, m, Tin, Ta, rho, cp, k, A, B = np.broadcast_arrays(
        *[np.asarray(v, dtype=float) for v in (D, L, Uo, m, Tin, Ta, rho, cp, k, A, B)])
    Aln = A * LN10
    lnrho = np.log(rho)
    # Gz = 4 m cp / (pi k x); 1.077 Gz^(1/3) = c / t
    c = 1.077 * (4 * m * cp / (math.pi * k * L)) ** (1.0 / 3.0)
    a_heat = 3 * L * math.pi * D * Uo / (m * cp)
    u = 4 * m / (math.pi * D ** 2 * rho)
    a_dp = 3 * L * 32 * u / D ** 2
    r0 = D / k * Uo
    y = np.log(Tin - Ta)
    P = np.zeros_like(y)
    psi = np.ones_like(y)

    def f(t, y, psi):
        if t == 0.0:
            return np.zeros_like(y), np.zeros_like(y), psi
        th = np.exp(y)
        lmb, _ = lnmu(Ta + th, Aln, B, lnrho)
        g = c - 0.7 * t
        br = (g * g * g + NU_C3 * t ** 3) ** (1.0 / 3.0)
        s0 = r0 * t / br                     # Uo / h without the viscosity correction
        for _ in range(2):                   # Newton for psi = (Tw - Ta) / (Tb - Ta)
            lmw, dlmw = lnmu(Ta + th * psi, Aln, B, lnrho)
            s = s0 * np.exp(-0.14 * (lmb - lmw))
            F = psi * (1 + s) - 1
            dF = (1 + s) + psi * s * 0.14 * dlmw * th
            psi = np.clip(psi - F / dF, 1e-6, 1.0)
        lmw, _ = lnmu(Ta + th * psi, Aln, B, lnrho)
        s = s0 * np.exp(-0.14 * (lmb - lmw))
        dy = -a_heat * (t * t) / (1 + s)
        dP = a_dp * (t * t) * np.exp(0.5 * (lmb + lmw))
        return dy, dP, psi

    h = 1.0 / N
    for i in range(N):
        t = i * h
        k1y, k1p, psi = f(t, y, psi)
        k2y, k2p, psi = f(t + h / 2, y + h / 2 * k1y, psi)
        k3y, k3p, psi = f(t + h / 2, y + h / 2 * k2y, psi)
        k4y, k4p, psi = f(t + h, y + h * k3y, psi)
        y = y + h / 6 * (k1y + 2 * k2y + 2 * k3y + k4y)
        P = P + h / 6 * (k1p + 2 * k2p + 2 * k3p + k4p)
    return P, Ta + np.exp(y)


def invert_uo(geo, m, Tin, Tout, Ta, N=N_FINAL):
    """Uo for which the model gives Tout (TS-2 5.2). geo: dict D,L,rho,cp,k,A,B arrays. Vectorised."""
    n = len(m)
    lo = np.full(n, math.log(1e-3))
    hi = np.full(n, math.log(1e3))

    def F(lu):
        return solve_pipes(geo['D'], geo['L'], np.exp(lu), m, Tin, Ta, geo['rho'], geo['cp'], geo['k'],
                           geo['A'], geo['B'], N=N)[1] - Tout

    flo, fhi = F(lo), F(hi)
    ok = (flo > 0) & (fhi < 0) & np.isfinite(flo) & np.isfinite(fhi)
    side = np.zeros(n)
    for it in range(80):
        with np.errstate(divide='ignore', invalid='ignore'):
            zc = (lo * fhi - hi * flo) / (fhi - flo)
        bad = ~np.isfinite(zc) | (zc <= lo) | (zc >= hi) | (it % 6 == 5)
        zc = np.where(bad, 0.5 * (lo + hi), zc)
        fc = F(zc)
        left = (fc > 0)
        lo2 = np.where(left, zc, lo)
        hi2 = np.where(left, hi, zc)
        flo2 = np.where(left, fc, flo)
        fhi2 = np.where(left, fhi, fc)
        fhi2 = np.where(left & (side == 1), fhi2 / 2, fhi2)
        flo2 = np.where(~left & (side == -1), flo2 / 2, flo2)
        side = np.where(left, 1, -1)
        lo, hi, flo, fhi = lo2, hi2, flo2, fhi2
        if np.all((hi - lo) < 1e-11):
            break
    U = np.exp(0.5 * (lo + hi))
    return np.where(ok, U, np.nan)


# ---------------------------------------------------------------------------------------------
# package reading
# ---------------------------------------------------------------------------------------------

def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as fh:
        rd = csv.reader(fh)
        rows = [r for r in rd if r and any(c.strip() for c in r)]
    if not rows:
        return []
    head = [h.strip() for h in rows[0]]
    return [{h: (r[i].strip() if i < len(r) else '') for i, h in enumerate(head)} for r in rows[1:]]


def fnum(v, default=float('nan')):
    try:
        return float(v)
    except Exception:
        return default


def norm_pipe(name):
    s = str(name).strip().upper().replace('_', '-').replace(' ', '-')
    s = re.sub(r'-+', '-', s)
    return s


def norm_date(d):
    d = str(d).strip()
    m = re.match(r'^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', d)
    if m:
        return '%04d-%02d-%02d' % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r'^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})', d)
    if m:
        return '%04d-%02d-%02d' % (int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return d


COVER_RE = re.compile(r'(cover|lagg|\blag\b|\blags\b|insulat|clad|wrap|jacket|sheath)', re.I)
INSPECT_RE = re.compile(r'(inspect|check|survey|examin|photograph|measur|looked|test|no (work|action|defect)|noted|logged|reported)', re.I)
WORK_RE = re.compile(r'(renew|repair|replac|patch|new\b|refit|re-?fit|restor|mend|redo|redone|re-?made|made good|reinstat|fix|re-?lag|re-?insulat|re-?clad|re-?cover|re-?wrap|install|fitted|rebuilt|rebuild|reapplied|re-?applied|removed|stripped)', re.I)


def classify_job(job):
    """'cover' if the job (as the fitters entered it) renewed or repaired a pipe's covering, else ''."""
    j = str(job)
    if not COVER_RE.search(j):
        return ''
    if WORK_RE.search(j):
        return 'cover'
    if INSPECT_RE.search(j):
        return ''
    return 'cover'


# ---------------------------------------------------------------------------------------------
# main calculation
# ---------------------------------------------------------------------------------------------

class Site:
    def __init__(self, pkg):
        self.pkg = pkg
        try:
            with open(os.path.join(pkg, 'site.json'), encoding='utf-8-sig') as fh:
                self.meta = json.load(fh)
        except Exception:
            self.meta = {}
        self.oils = {}
        for r in read_csv(os.path.join(pkg, 'oils.csv')):
            A, B = visc_params(fnum(r['nu50_cSt']), fnum(r['nu100_cSt']))
            self.oils[r['oil'].strip()] = dict(rho=fnum(r['density_kg_m3']), cp=fnum(r['cp_J_kgK']),
                                               k=fnum(r['k_W_mK']), A=A, B=B)
        self.lines = {}
        self.pipe_line = {}
        for r in read_csv(os.path.join(pkg, 'lines.csv')):
            name = norm_pipe(r['line'])
            npipes = int(round(fnum(r.get('pipes', 1), 1)))
            oil = r['oil'].strip()
            if oil not in self.oils:
                # tolerate case / spacing differences
                cand = [o for o in self.oils if o.upper().replace(' ', '') == oil.upper().replace(' ', '')]
                oil = cand[0] if cand else next(iter(self.oils))
            pipes = [name + '-A'] + ([name + '-B'] if npipes >= 2 else [])
            self.lines[name] = dict(n=npipes, D=fnum(r['bore_mm']) / 1000.0, L=fnum(r['length_m']), oil=oil,
                                    pipes=pipes, raw=r['line'].strip())
            for p in pipes:
                self.pipe_line[p] = name
        self.surveys = []
        for r in read_csv(os.path.join(pkg, 'surveys.csv')):
            p = self.resolve_pipe(r.get('pipe', ''))
            if not p:
                continue
            self.surveys.append(dict(date=norm_date(r.get('date', '')), pipe=p, line_flow=fnum(r.get('line_flow_t_h')),
                                     flow=fnum(r.get('flow_t_h')), t_in=fnum(r.get('t_in_C')),
                                     t_out=fnum(r.get('t_out_C')), t_amb=fnum(r.get('t_amb_C')), crew=False))
        self.jobs = []
        try:
            for r in read_csv(os.path.join(pkg, 'work_log.csv')):
                ps = self.resolve_pipes_job(r.get('pipe', ''))
                kind = classify_job(r.get('job', ''))
                for p in ps:
                    self.jobs.append(dict(date=norm_date(r.get('date', '')), pipe=p, job=r.get('job', ''), kind=kind))
        except FileNotFoundError:
            pass
        self.records = read_csv(os.path.join(pkg, 'records.csv'))

    def resolve_pipe(self, name):
        p = norm_pipe(name)
        if p in self.pipe_line:
            return p
        m = re.match(r'^(.*?)-?([AB])$', p)
        if m and (m.group(1) + '-' + m.group(2)) in self.pipe_line:
            return m.group(1) + '-' + m.group(2)
        if p in self.lines and self.lines[p]['n'] == 1:
            return p + '-A'
        return None

    def resolve_pipes_job(self, name):
        p = self.resolve_pipe(name)
        if p:
            return [p]
        q = norm_pipe(name)
        if q in self.lines:
            return list(self.lines[q]['pipes'])
        # names like "FL-214-A/B" or "FL-214 A+B"
        m = re.match(r'^(.*?)-?([AB])[/+&,]-?([AB])$', q)
        if m and m.group(1) in self.lines:
            return [p for p in self.lines[m.group(1)]['pipes'] if p[-1] in (m.group(2), m.group(3))]
        return []

    def geo_for_pipes(self, pipes):
        g = {k: [] for k in ('D', 'L', 'rho', 'cp', 'k', 'A', 'B')}
        for p in pipes:
            ln = self.lines[self.pipe_line[p]]
            o = self.oils[ln['oil']]
            g['D'].append(ln['D']); g['L'].append(ln['L'])
            for kk in ('rho', 'cp', 'k', 'A', 'B'):
                g[kk].append(o[kk])
        return {k: np.asarray(v, float) for k, v in g.items()}


def survey_uo(site, svs):
    """Uo and its reading uncertainty (in ln Uo, tolerances combined in quadrature) for surveys."""
    if not svs:
        return np.zeros(0), np.zeros(0)
    pipes = [s['pipe'] for s in svs]
    geo = site.geo_for_pipes(pipes)
    m = np.array([s['flow'] for s in svs]) / 3.6
    Ti = np.array([s['t_in'] for s in svs])
    To = np.array([s['t_out'] for s in svs])
    Ta = np.array([s['t_amb'] for s in svs])
    n = len(svs)
    valid = np.isfinite(m) & (m > 0) & np.isfinite(Ti) & np.isfinite(To) & np.isfinite(Ta) & (Ti > To) & (To > Ta)
    m_ = np.where(valid, m, 1.0); Ti_ = np.where(valid, Ti, 80.0); To_ = np.where(valid, To, 70.0)
    Ta_ = np.where(valid, Ta, 10.0)
    # base and the four reading perturbations in one batch
    rep = lambda a: np.concatenate([a] * 5)
    geo5 = {k: rep(v) for k, v in geo.items()}
    m5 = np.concatenate([m_, m_ * (1 + TOL_FLOW), m_, m_, m_])
    Ti5 = np.concatenate([Ti_, Ti_, Ti_ + TOL_TOIL, Ti_, Ti_])
    To5 = np.concatenate([To_, To_, To_, To_ + TOL_TOIL, To_])
    Ta5 = np.concatenate([Ta_, Ta_, Ta_, Ta_, Ta_ + TOL_TAMB])
    U5 = invert_uo(geo5, m5, Ti5, To5, Ta5)
    U = U5[:n]
    sig2 = np.zeros(n)
    for j in range(1, 5):
        sig2 += np.log(U5[j * n:(j + 1) * n] / U) ** 2
    sig = np.sqrt(sig2)
    U = np.where(valid, U, np.nan)
    sig = np.where(np.isfinite(sig) & (sig > 0), sig, 0.01)
    return U, sig


def day_number(d):
    try:
        import datetime
        return datetime.date.fromisoformat(d).toordinal()
    except Exception:
        return None


def job_class(text):
    t = str(text).lower()
    if 'renew' in t or 'replac' in t or 'new ' in t or t.endswith('new') or 're-lag' in t or 'relag' in t:
        return 'renewed'
    if 'repair' in t or 'patch' in t or 'mend' in t or 'made good' in t:
        return 'repaired'
    return 'other'


DEFAULT_RATIO = {'renewed': 0.5, 'repaired': 0.63, 'other': 0.6}


def assess_pipes(site, U, sig):
    """Per pipe: the surveys that stand for its covering as it is now, and whether it needs the crew.

    kind 'cover': covering renewed or repaired after its last survey (TS-2 5.3);
    kind 'drift': surveys of the same covering disagree beyond their reading accuracy (TS-2 5.4);
    kind 'ok'."""
    info = {}
    by_pipe = {}
    for i, s in enumerate(site.surveys):
        if np.isfinite(U[i]):
            by_pipe.setdefault(s['pipe'], []).append(i)
    cover_jobs = {}
    for j in site.jobs:
        if j['kind'] == 'cover':
            cover_jobs.setdefault(j['pipe'], []).append(j)

    def consistent(i, k):
        return abs(math.log(U[i]) - math.log(U[k])) / math.hypot(sig[i], sig[k]) <= DRIFT_LIMIT

    # Uo after / before covering work, from this site's own surveys (used only when the crew cannot help)
    ratios = {}
    for p in site.pipe_line:
        idx = sorted(by_pipe.get(p, []), key=lambda i: site.surveys[i]['date'])
        for j in cover_jobs.get(p, []):
            before = [i for i in idx if site.surveys[i]['date'] < j['date']]
            after = [i for i in idx if site.surveys[i]['date'] > j['date']]
            later_jobs = [k for k in cover_jobs.get(p, []) if k['date'] > j['date']]
            if before and after and (not later_jobs or site.surveys[after[0]]['date'] < min(k['date'] for k in later_jobs)):
                ratios.setdefault(job_class(j['job']), []).append(U[after[0]] / U[before[-1]])
    ratio = dict(DEFAULT_RATIO)
    for k, v in ratios.items():
        ratio[k] = float(np.median(v))

    for p in site.pipe_line:
        idx = sorted(by_pipe.get(p, []), key=lambda i: site.surveys[i]['date'])
        jobs = sorted(cover_jobs.get(p, []), key=lambda j: j['date'])
        inf = dict(valid=[], kind='ok', need=0.0, reason='', fallback=None, slope=0.0)
        info[p] = inf
        valid = idx
        if jobs:
            lj = jobs[-1]
            lc = lj['date']
            valid = [i for i in idx if site.surveys[i]['date'] > lc]
            same = [i for i in idx if site.surveys[i]['date'] == lc]
            before = [i for i in idx if site.surveys[i]['date'] < lc]
            if same and before:
                # survey on the day of the work: before the work if it agrees with the earlier surveys
                for i in same:
                    if not consistent(i, before[-1]):
                        valid = [i] + valid
        if not valid:
            inf['kind'] = 'cover'
            inf['need'] = 1000.0
            inf['reason'] = 'covering worked on after its last survey' if idx else 'no survey on file'
            if idx:
                jc = job_class(jobs[-1]['job']) if jobs else 'other'
                inf['fallback'] = (idx[-1], ratio.get(jc, 0.6))
            continue
        u = np.log(U[valid]); sg = sig[valid]
        stat = 0.0
        for a in range(len(valid)):
            for b in range(a + 1, len(valid)):
                stat = max(stat, abs(u[b] - u[a]) / math.hypot(sg[a], sg[b]))
        if stat > DRIFT_LIMIT:
            keep = [valid[-1]]
            for i in reversed(valid[:-1]):
                if all(consistent(i, k) for k in keep):
                    keep.insert(0, i)
                else:
                    break
            inf['valid'] = keep
            inf['kind'] = 'drift'
            # rate of change of ln Uo per day, from the surveys of this covering
            days = [day_number(site.surveys[i]['date']) for i in valid]
            if all(d is not None for d in days) and len(set(days)) >= 2:
                dd = np.array(days, float)
                w = 1.0 / sg ** 2
                dm = (w * dd).sum() / w.sum()
                um = (w * u).sum() / w.sum()
                inf['slope'] = float((w * (dd - dm) * (u - um)).sum() / (w * (dd - dm) ** 2).sum())
                inf['last_day'] = days[-1]
            inf['need'] = 100.0 + min(abs(inf['slope']) * 1e4, 800.0) + stat * 1e-3
            inf['reason'] = 'covering changing between surveys (stat %.1f, %.2f %%/month)' % (stat, inf['slope'] * 3000)
        else:
            inf['valid'] = valid
            se = 1.0 / math.sqrt(sum(1.0 / s_ ** 2 for s_ in sg))
            # rank for any spare place in the order: surveys that come nearest to disagreeing first,
            # then the Uo resting on the fewest / least certain surveys
            inf['need'] = (1.0 if stat > 0.7 else 0.0) + min(se, 0.5)
            inf['stat'] = stat
    return info


def call_crew(pkg, pipes):
    exe = shutil.which('heatsurvey')
    if exe is None:
        for cand in ('/tmp/ftl_BX1/app/heatsurvey',):
            if os.path.exists(cand) and os.access(cand, os.X_OK):
                exe = cand
                break
    if exe is None:
        log('heatsurvey not found')
        return [], False
    try:
        pr = subprocess.run([exe, pkg] + list(pipes), capture_output=True, text=True, timeout=15)
    except Exception as e:
        log('heatsurvey failed:', e)
        return [], False
    if pr.returncode != 0:
        log('heatsurvey refused (%d): %s %s' % (pr.returncode, pr.stdout.strip()[:500], pr.stderr.strip()[:500]))
    out = []
    lines_ = [l for l in pr.stdout.splitlines() if l.strip()]
    head = None
    for l in lines_:
        cells = [c.strip() for c in l.split(',')]
        if head is None:
            if 'pipe' in [c.lower() for c in cells]:
                head = [c.lower() for c in cells]
            continue
        if len(cells) != len(head):
            continue
        out.append(dict(zip(head, cells)))
    log('heatsurvey returned %d rows' % len(out))
    return out, len(out) > 0


def sig_fn(z):
    return 1.0 / (1.0 + np.exp(-z))


class PairSolver:
    def __init__(self, mt, argsA, argsB):
        self.mt = mt
        self.A = argsA
        self.B = argsB

    def G(self, z, idx, N=N_ROOT):
        a = {k: v[idx] for k, v in self.A.items()}
        b = {k: v[idx] for k, v in self.B.items()}
        mt = self.mt[idx]
        PA, TA = solve_pipes(m=mt * sig_fn(z), N=N, **a)
        PB, TB = solve_pipes(m=mt * sig_fn(-z), N=N, **b)
        return np.log(PA) - np.log(PB), PA, TA, PB, TB

    def grid(self, idx_all, z):
        n = len(idx_all)
        out = np.empty((n, len(z)))
        s = sig_fn(z)[None, :]
        chunk = max(1, 40000 // len(z))
        for c0 in range(0, n, chunk):
            idx = idx_all[c0:c0 + chunk]
            a = {k: v[idx][:, None] for k, v in self.A.items()}
            b = {k: v[idx][:, None] for k, v in self.B.items()}
            mt = self.mt[idx][:, None]
            PA, _ = solve_pipes(m=mt * s, N=N_ROOT, **a)
            PB, _ = solve_pipes(m=mt * s, N=N_ROOT, **b)
            out[c0:c0 + len(idx)] = np.log(PA) - np.log(PB[:, ::-1])
        return out

    def refine(self, ii, lo, hi, flo=None, fhi=None, iters=60, tol=1e-11):
        if len(ii) == 0:
            return np.zeros(0), np.zeros(0, bool)
        if flo is None:
            flo = self.G(lo, ii)[0]
        if fhi is None:
            fhi = self.G(hi, ii)[0]
        good = np.sign(flo) != np.sign(fhi)
        side = np.zeros(len(ii))
        for it in range(iters):
            with np.errstate(divide='ignore', invalid='ignore'):
                zc = (lo * fhi - hi * flo) / (fhi - flo)
            bad = ~np.isfinite(zc) | (zc <= np.minimum(lo, hi)) | (zc >= np.maximum(lo, hi)) | (it % 8 == 7)
            zc = np.where(bad, 0.5 * (lo + hi), zc)
            fc = self.G(zc, ii)[0]
            left = np.sign(fc) == np.sign(flo)
            lo2 = np.where(left, zc, lo); flo2 = np.where(left, fc, flo)
            hi2 = np.where(left, hi, zc); fhi2 = np.where(left, fhi, fc)
            fhi2 = np.where(left & (side == 1), fhi2 / 2, fhi2)
            flo2 = np.where(~left & (side == -1), flo2 / 2, flo2)
            side = np.where(left, 1, -1)
            lo, hi, flo, fhi = lo2, hi2, flo2, fhi2
            if np.all(np.abs(hi - lo) < tol):
                break
        root = 0.5 * (lo + hi)
        return root, good

    def all_roots(self, idx_all):
        """Every division (as z) satisfying TS-2 4.1 for each case in idx_all."""
        z = np.linspace(-ZMAX, ZMAX, NZ)
        G = self.grid(idx_all, z)
        # G runs from -inf (all oil in B) to +inf (all oil in A); keep that sign where a value is unusable
        G = np.where(np.isfinite(G), G, np.where(z[None, :] < 0, -1e3, 1e3))
        sg = np.sign(G)
        ri, rj = np.nonzero(sg[:, :-1] * sg[:, 1:] < 0)
        lo = list(z[rj]); hi = list(z[rj + 1]); ii = list(ri)
        flo = list(G[ri, rj]); fhi = list(G[ri, rj + 1])
        # a division beyond the grid (one pipe all but stopped)
        for k in np.nonzero(G[:, 0] > 0)[0]:
            ii.append(k); lo.append(-60.0); hi.append(z[0]); flo.append(-1e3); fhi.append(G[k, 0])
        for k in np.nonzero(G[:, -1] < 0)[0]:
            ii.append(k); lo.append(z[-1]); hi.append(60.0); flo.append(G[k, -1]); fhi.append(1e3)
        # exact zeros on the grid
        zi, zj = np.nonzero(sg == 0)
        exact = [(a, z[b]) for a, b in zip(zi, zj)]
        # roots in pairs hidden between grid points: local extremum of G close to zero
        Gm, G0, Gp = G[:, :-2], G[:, 1:-1], G[:, 2:]
        ext = ((G0 - Gm) * (Gp - G0) < 0) & (np.sign(Gm) == np.sign(G0)) & (np.sign(Gp) == np.sign(G0))
        a_ = (Gp - Gm) / 2
        b_ = (Gp + Gm - 2 * G0) / 2
        with np.errstate(divide='ignore', invalid='ignore'):
            Gext = G0 - a_ * a_ / (4 * b_)
        cand = ext & ((np.sign(Gext) != np.sign(G0)) | (np.abs(Gext) < 3 * np.abs(b_) + 1e-9))
        ci, cj = np.nonzero(cand)
        if len(ci):
            nf = 41
            f = np.linspace(0, 1, nf)
            zz = z[cj][:, None] + (z[cj + 2] - z[cj])[:, None] * f[None, :]
            idx = idx_all[ci]
            a = {k: v[idx][:, None] for k, v in self.A.items()}
            b = {k: v[idx][:, None] for k, v in self.B.items()}
            mt = self.mt[idx][:, None]
            PA, _ = solve_pipes(m=mt * sig_fn(zz), N=N_ROOT, **a)
            PB, _ = solve_pipes(m=mt * sig_fn(-zz), N=N_ROOT, **b)
            Gf = np.log(PA) - np.log(PB)
            sgf = np.sign(Gf)
            fi, fj = np.nonzero(sgf[:, :-1] * sgf[:, 1:] < 0)
            for a1, b1 in zip(fi, fj):
                ii.append(ci[a1]); lo.append(zz[a1, b1]); hi.append(zz[a1, b1 + 1])
                flo.append(Gf[a1, b1]); fhi.append(Gf[a1, b1 + 1])
        ii = np.asarray(ii, int)
        roots = [[] for _ in range(len(idx_all))]
        if len(ii):
            r, good = self.refine(idx_all[ii], np.asarray(lo, float), np.asarray(hi, float),
                                  np.asarray(flo, float), np.asarray(fhi, float))
            for k, zr, g in zip(ii, r, good):
                if g:
                    roots[k].append(zr)
        for a, zr in exact:
            roots[a].append(zr)
        return [np.unique(np.round(np.asarray(rr, float), 12)) for rr in roots]


def pick_first(roots):
    """TS-2 4.3: one division only at the opening record. Guard against a spurious pair near a fold."""
    r = roots
    if len(r) == 1:
        return r[0]
    if len(r) == 0:
        return 0.0
    if len(r) == 3:
        return r[2] if (r[1] - r[0]) < (r[2] - r[1]) else r[0]
    st = r[0::2]
    return st[np.argmin(np.abs(st))]


def choose_order(site, info, allowance):
    """Pipes to name in the one order for the crew, and pipes whose Uo is to follow from a partner's survey."""
    ranked = sorted(site.pipe_line, key=lambda p: -info[p]['need'])
    needed = [p for p in ranked if info[p]['need'] >= 100.0]
    infer = {}
    if len(needed) > allowance:
        # a pair with both pipes in need: one survey gives the division of the line's flow at the survey rating,
        # from which the partner's Uo follows (TS-2 4.1)
        for ln, L_ in site.lines.items():
            if L_['n'] >= 2 and len(needed) > allowance:
                a, b = L_['pipes'][0], L_['pipes'][1]
                if a in needed and b in needed:
                    drop = b if info[b]['need'] <= info[a]['need'] else a
                    keep = a if drop == b else b
                    needed.remove(drop)
                    infer[drop] = keep
        if len(needed) > allowance:
            log('survey allowance %d short of the %d pipes in need' % (allowance, len(needed)))
            needed = needed[:allowance]
    order = list(needed)
    spare = allowance - len(order)
    if spare > 0:
        rest = [p for p in ranked if p not in order and p not in infer]
        order += rest[:spare]
    return order, infer


def crew_surveys(site, order):
    if not order:
        return [], False
    log('ordering survey of', ' '.join(order))
    names = []
    for p in order:
        ln = site.lines[site.pipe_line[p]]
        names.append(ln['raw'] + p[len(site.pipe_line[p]):])
    rows, ok = call_crew(site.pkg, names)
    crew = []
    for r in rows:
        p = site.resolve_pipe(r.get('pipe', ''))
        if not p:
            continue
        g = lambda key: fnum(r.get(key.lower(), r.get(key)))
        crew.append(dict(date='9999-99-99', pipe=p, line_flow=g('line_flow_t_h'), flow=g('flow_t_h'),
                         t_in=g('t_in_C'), t_out=g('t_out_C'), t_amb=g('t_amb_C'), crew=True))
    return crew, ok


def infer_partner(site, row, Ukeep, partner):
    """Uo of a pair's other pipe from a crew survey of one pipe: the line's flow divides so that both pipes
    have the same pressure drop (TS-2 4.1)."""
    try:
        mk = row['flow'] / 3.6
        mp = (row['line_flow'] - row['flow']) / 3.6
        if not (mp > 0.02 * row['line_flow'] / 3.6) or not np.isfinite(Ukeep):
            return None
        geo = site.geo_for_pipes([partner])
        args = dict(D=geo['D'], L=geo['L'], m=np.array([mk]), Tin=np.array([row['t_in']]), Ta=np.array([row['t_amb']]),
                    rho=geo['rho'], cp=geo['cp'], k=geo['k'], A=geo['A'], B=geo['B'])
        dpk = solve_pipes(Uo=np.array([Ukeep]), **args)[0][0]
        args['m'] = np.array([mp])
        lo, hi = math.log(1e-2), math.log(1e3)
        f = lambda lu: math.log(solve_pipes(Uo=np.array([math.exp(lu)]), **args)[0][0] / dpk)
        flo, fhi = f(lo), f(hi)
        if not (flo < 0 < fhi):
            return None
        for _ in range(42):
            mid = 0.5 * (lo + hi)
            fm = f(mid)
            if fm < 0:
                lo = mid
            else:
                hi = mid
        return math.exp(0.5 * (lo + hi))
    except Exception:
        return None


def final_uo(site, info, U, sig, crew, Uc, sigc, infer):
    Uo = {}
    crew_by = {}
    for i, c in enumerate(crew):
        if np.isfinite(Uc[i]):
            crew_by.setdefault(c['pipe'], []).append(i)
    all_days = [day_number(s_['date']) for s_ in site.surveys] + [day_number(j['date']) for j in site.jobs]
    all_days = [d for d in all_days if d is not None]
    now = (max(all_days) + 2) if all_days else None
    for p in site.pipe_line:
        inf = info[p]
        old = [(math.log(U[i]), sig[i]) for i in inf['valid']]
        vals = []
        if p in crew_by:
            new = [(math.log(Uc[i]), sigc[i]) for i in crew_by[p]]
            if inf['need'] >= 100.0 or not old:
                vals = new
            else:
                # a covering taken as unchanged: the new survey joins the old unless it shows a change
                stat = max(abs(a - b) / math.hypot(sa, sb) for a, sa in new for b, sb in old)
                vals = new if stat > DRIFT_LIMIT else new + old
                if stat > DRIFT_LIMIT:
                    log('crew survey of %s shows its covering changed (stat %.1f)' % (p, stat))
        elif p in infer and infer[p] in crew_by:
            i = crew_by[infer[p]][0]
            v = infer_partner(site, crew[i], Uc[i], p)
            if v is not None:
                Uo[p] = v
                log('Uo of %s from the division in the survey of %s: %.3f' % (p, infer[p], v))
                continue
        if not vals and old:
            if inf['kind'] == 'drift':
                lu, _ = old[-1]
                if now is not None and inf.get('last_day') is not None:
                    lu += float(np.clip(inf['slope'] * (now - inf['last_day']), -0.5, 0.5))
                vals = [(lu, 1.0)]
                log('no current survey for %s (changing covering): using %.3f' % (p, math.exp(lu)))
            else:
                vals = old
        if vals:
            w = np.array([1.0 / s_ ** 2 for _, s_ in vals])
            v = np.array([x for x, _ in vals])
            Uo[p] = float(math.exp((w * v).sum() / w.sum()))
        else:
            fb = inf.get('fallback')
            if fb:
                Uo[p] = float(U[fb[0]]) * fb[1]
                log('no current survey for %s: using %.3f' % (p, Uo[p]))
            else:
                Uo[p] = float(np.nanmedian(U)) if np.any(np.isfinite(U)) else 6.0
                log('no survey at all for %s: using %.3f' % (p, Uo[p]))
    return Uo


def run(pkg, out_csv):
    site = Site(pkg)
    allowance = site.meta.get('survey_allowance', None)
    allowance = int(fnum(allowance, 0)) if allowance is not None else None
    U, sig = survey_uo(site, site.surveys)
    info = assess_pipes(site, U, sig)
    if allowance is None:
        allowance = sum(1 for p in site.pipe_line if info[p]['need'] >= 100.0)
    order, infer = choose_order(site, info, allowance)
    for p in order:
        if info[p]['reason']:
            log('  %s: %s' % (p, info[p]['reason']))
    crew, ok = crew_surveys(site, order)
    if not ok:
        needed = [p for p in order if info[p]['need'] >= 100.0]
        if needed and len(needed) < len(order):
            # a refused order does not count: try once more with the pipes in need alone
            crew, ok = crew_surveys(site, needed)
    Uc, sigc = survey_uo(site, crew)
    Uo = final_uo(site, info, U, sig, crew, Uc, sigc, infer)
    return site.records, *compute(site, Uo)


def compute(site, Uo):
    # --- records
    recs = site.records
    nrec = len(recs)
    res_dp = np.full(nrec, np.nan)
    res_T = np.full(nrec, np.nan)
    line_of = []
    for r in recs:
        q = norm_pipe(r.get('line', ''))
        if q not in site.lines:
            q2 = site.resolve_pipe(q)
            q = site.pipe_line.get(q2, q) if q2 else q
        line_of.append(q)
    flow = np.array([fnum(r.get('flow_t_h')) for r in recs]) / 3.6
    Tin = np.array([fnum(r.get('t_in_C')) for r in recs])
    Ta = np.array([fnum(r.get('t_amb_C')) for r in recs])
    hour = np.array([fnum(r.get('hour'), i) for i, r in enumerate(recs)])

    def args_for(idx, which):
        g = {k: [] for k in ('D', 'L', 'rho', 'cp', 'k', 'A', 'B', 'Uo', 'Tin', 'Ta')}
        for i in idx:
            ln = site.lines[line_of[i]]
            o = site.oils[ln['oil']]
            g['D'].append(ln['D']); g['L'].append(ln['L'])
            for kk in ('rho', 'cp', 'k', 'A', 'B'):
                g[kk].append(o[kk])
            g['Uo'].append(Uo[ln['pipes'][which]])
            g['Tin'].append(Tin[i]); g['Ta'].append(Ta[i])
        return {k: np.asarray(v, float) for k, v in g.items()}

    single = [i for i in range(nrec) if line_of[i] in site.lines and site.lines[line_of[i]]['n'] == 1]
    pair = [i for i in range(nrec) if line_of[i] in site.lines and site.lines[line_of[i]]['n'] >= 2]

    if single:
        try:
            a = args_for(single, 0)
            P, T = solve_pipes(m=flow[single], N=N_FINAL, **a)
            res_dp[single] = P / 1000.0
            res_T[single] = T
        except Exception:
            import traceback
            traceback.print_exc()
    if pair:
        try:
            pair_results(site, Uo, pair, line_of, flow, hour, args_for, res_dp, res_T)
        except Exception:
            import traceback
            traceback.print_exc()
    return res_dp, res_T


def pair_results(site, Uo, pair, line_of, flow, hour, args_for, res_dp, res_T):
    if True:
        pidx = np.asarray(pair, int)
        aA = args_for(pair, 0)
        aB = args_for(pair, 1)
        mt = flow[pidx]
        ps = PairSolver(mt, aA, aB)
        loc = np.arange(len(pidx))
        roots = ps.all_roots(loc)
        # continuation along each line's run of records (TS-2 4.2)
        by_line = {}
        for k, i in enumerate(pair):
            by_line.setdefault(line_of[i], []).append(k)
        seqs = []
        for ln, ks in by_line.items():
            ks.sort(key=lambda k: (hour[pidx[k]], k))
            seqs.append(ks)
        zsel = np.zeros(len(pidx))
        maxlen = max(len(s) for s in seqs)
        for step in range(maxlen):
            if step == 0:
                for sq in seqs:
                    zsel[sq[0]] = pick_first(roots[sq[0]])
                continue
            later = [sq[step] for sq in seqs if step < len(sq)]
            if later:
                prevk = np.array([sq[step - 1] for sq in seqs if step < len(sq)])
                later = np.array(later)
                zp = zsel[prevk]
                Gp = ps.G(zp, later)[0]
                for k, z0, g0 in zip(later, zp, Gp):
                    r = roots[k]
                    if g0 > 0:     # pipe A has the higher pressure drop: oil shifts to B, z decreases
                        c = r[r <= z0]
                        if len(c):
                            zsel[k] = c[-1]
                            continue
                    elif g0 < 0:
                        c = r[r >= z0]
                        if len(c):
                            zsel[k] = c[0]
                            continue
                    else:
                        zsel[k] = z0
                        continue
                    # no root found in that direction: search for it directly
                    zsel[k] = local_search(ps, k, z0, g0)
        G, PA, TA, PB, TB = ps.G(zsel, loc, N=N_FINAL)
        s = sig_fn(zsel)
        res_dp[pidx] = 0.5 * (PA + PB) / 1000.0
        res_T[pidx] = s * TA + (1 - s) * TB


def local_search(ps, k, z0, g0):
    step = -0.05 if g0 > 0 else 0.05
    za, ga = z0, g0
    for _ in range(int(2 * ZMAX / 0.05) + 2):
        zb = za + step
        if abs(zb) > ZMAX + 1:
            break
        gb = ps.G(np.array([zb]), np.array([k]))[0][0]
        if np.sign(gb) != np.sign(ga):
            lo, hi = (za, zb) if za < zb else (zb, za)
            r, good = ps.refine(np.array([k]), np.array([lo]), np.array([hi]))
            return float(r[0])
        za, ga = zb, gb
    return z0


def write_out(out_csv, recs, dp, T):
    with open(out_csv, 'w', newline='') as fh:
        fh.write('record,dp_kPa,t_out_C\n')
        for r, a, b in zip(recs, dp, T):
            a = a if np.isfinite(a) else 0.0
            b = b if np.isfinite(b) else 0.0
            fh.write('%s,%.4f,%.4f\n' % (r.get('record', ''), a, b))


def main():
    if len(sys.argv) < 3:
        print('usage: python3 lines.py PACKAGE_DIR OUT_CSV', file=sys.stderr)
        return 0
    pkg, out_csv = sys.argv[1], sys.argv[2]
    try:
        recs, dp, T = run(pkg, out_csv)
        write_out(out_csv, recs, dp, T)
    except Exception:
        import traceback
        traceback.print_exc()
        try:
            recs = read_csv(os.path.join(pkg, 'records.csv'))
            write_out(out_csv, recs, np.zeros(len(recs)), np.zeros(len(recs)))
        except Exception:
            traceback.print_exc()
    return 0


if __name__ == '__main__':
    np.seterr(all='ignore')
    sys.exit(main())
