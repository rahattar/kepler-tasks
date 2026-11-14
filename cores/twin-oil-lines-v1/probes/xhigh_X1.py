#!/usr/bin/env python3
"""TS-2 heated oil lines: pressure drop and outlet temperature for every hourly record of a site package.

    python3 lines.py PACKAGE_DIR OUT_CSV

Method (TS-2 and the site package format):
  * oil viscosity from ASTM D341 through the two tabulated points (TS-2 2.2);
  * each pipe integrated along its length (TS-2 3.1-3.5): heat balance with the local inside film
    (developing-flow Nusselt number with the viscosity correction at the local wall temperature), the wall
    temperature solved from the inside/outside heat balance, and the laminar pressure gradient corrected to
    the wall viscosity;
  * the outside coefficient Uo of every pipe from its heat-loss surveys (TS-2 5.2), using only surveys made
    after the last work on its covering (TS-2 5.3); pipes whose covering was worked on after their last
    survey, or whose surveys disagree beyond what the survey accuracy (TS-2 5.4) allows, are surveyed afresh
    with the package's single survey order;
  * a pair divides its flow so that both pipes have the same pressure drop (TS-2 4).  Where more than one
    division satisfies that, the line keeps the division it had at the previous hourly record: the split
    relaxes from the previous record's split to the nearest stable division in the direction the pressure
    difference drives it.  The first record of a line starts from an even split.
"""
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys

import numpy as np

T0 = 273.15
LN10 = math.log(10.0)

# ----------------------------------------------------------------------------------------------- physics

N_STEPS = 40                       # integration steps along a pipe (x = L s^2 grid)
N_WALL = 3                         # wall temperature iterations per evaluation
XS = np.linspace(0.0, 1.0, N_STEPS + 1) ** 2


def d341(nu50, nu100):
    t1, t2 = math.log10(50.0 + T0), math.log10(100.0 + T0)
    y1, y2 = math.log10(math.log10(nu50 + 0.7)), math.log10(math.log10(nu100 + 0.7))
    B = (y1 - y2) / (t2 - t1)
    A = y1 + B * t1
    return A, B


def visc(T, rho6, A, B):
    """dynamic viscosity (Pa s); rho6 = density * 1e-6"""
    return rho6 * (np.exp(LN10 * np.exp(LN10 * (A - B * np.log10(T + T0)))) - 0.7)


def integrate(P):
    """Integrate one pipe for every element of the parameter dict P (arrays of one shape).

    keys: D, L, m (kg/s), Tin, Ta, Uo, rho, cp, k, A, B.  Returns (dp in Pa, outlet temperature in C)."""
    D, L, m, Tin, Ta, Uo = P['D'], P['L'], np.maximum(P['m'], 1e-12), P['Tin'], P['Ta'], P['Uo']
    rho, cp, k, A, B = P['rho'], P['cp'], P['k'], P['A'], P['B']
    rho6 = rho * 1e-6
    u = 4.0 * m / (np.pi * D * D * rho)
    gz_num = 4.0 * m * cp / (np.pi * k * L)       # Gz = Re Pr D / x = gz_num / (x/L)
    kD = k / D
    lam_c = np.pi * D / (m * cp)                   # lambda = pi D Ueff / (m cp)
    cdp = 32.0 * u / (D * D)
    c3 = 3.66 ** 3 + 0.7 ** 3

    def state(xn, Tb, Tw):
        mub = visc(Tb, rho6, A, B)
        Gz = gz_num / xn
        base = np.cbrt(c3 + (1.077 * np.cbrt(Gz) - 0.7) ** 3) * kD
        for _ in range(N_WALL):
            muw = visc(Tw, rho6, A, B)
            h = base * (mub / muw) ** 0.14
            Tw = (h * Tb + Uo * Ta) / (h + Uo)
        muw = visc(Tw, rho6, A, B)
        h = base * (mub / muw) ** 0.14
        Tw = (h * Tb + Uo * Ta) / (h + Uo)
        return h * Uo / (h + Uo), np.sqrt(mub * muw), Tw

    Tb = Tin.astype(float).copy()
    Tw = Tb.copy()
    lam0 = lam_c * Uo                              # at the inlet the film coefficient is unbounded
    f0 = cdp * visc(Tb, rho6, A, B)
    dp = np.zeros_like(Tb)
    for i in range(N_STEPS):
        dx = (XS[i + 1] - XS[i]) * L
        dT = Tb - Ta
        Tp = Ta + dT * np.exp(-lam0 * dx)
        Ue1, _, Tw1 = state(XS[i + 1], Tp, Tw)
        Tn = Ta + dT * np.exp(-0.5 * (lam0 + lam_c * Ue1) * dx)
        Ue1, mu1, Tw = state(XS[i + 1], Tn, Tw1)
        lam1 = lam_c * Ue1
        f1 = cdp * mu1
        lr = np.log(f1 / f0)
        small = np.abs(lr) < 1e-7
        dp = dp + np.where(small, 0.5 * (f0 + f1), (f1 - f0) / np.where(small, 1.0, lr)) * dx
        Tb, lam0, f0 = Tn, lam1, f1
    return dp, Tb


def integrate_chunked(P, chunk=60000):
    n = P['m'].size
    if n <= chunk:
        return integrate(P)
    dp = np.empty(n)
    T = np.empty(n)
    for s in range(0, n, chunk):
        sub = {key: v[s:s + chunk] for key, v in P.items()}
        dp[s:s + chunk], T[s:s + chunk] = integrate(sub)
    return dp, T


def invert_uo(P, Tout, iters=44):
    """Uo for which the pipe gives the outlet temperature Tout (TS-2 5.2); vectorised bisection on log Uo."""
    lo = np.full(Tout.shape, math.log(1e-4))
    hi = np.full(Tout.shape, math.log(1e3))
    Q = dict(P)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        Q['Uo'] = np.exp(mid)
        _, T = integrate(Q)
        too_much = T < Tout
        hi = np.where(too_much, mid, hi)
        lo = np.where(too_much, lo, mid)
    return np.exp(0.5 * (lo + hi))


# ----------------------------------------------------------------------------------------------- package

def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    return [{(k or '').strip(): (v or '').strip() for k, v in r.items()} for r in rows]


def fnum(s):
    return float(str(s).strip())


class Package:
    def __init__(self, d):
        self.dir = d
        try:
            with open(os.path.join(d, 'site.json')) as f:
                self.site = json.load(f)
        except Exception:
            self.site = {}
        self.oils = {r['oil']: r for r in read_csv(os.path.join(d, 'oils.csv'))}
        self.lines = {}
        for r in read_csv(os.path.join(d, 'lines.csv')):
            oil = self.oils[r['oil']]
            A, B = d341(fnum(oil['nu50_cSt']), fnum(oil['nu100_cSt']))
            self.lines[r['line']] = dict(
                line=r['line'], pipes=int(float(r['pipes'])), D=fnum(r['bore_mm']) / 1000.0,
                L=fnum(r['length_m']), rho=fnum(oil['density_kg_m3']), cp=fnum(oil['cp_J_kgK']),
                k=fnum(oil['k_W_mK']), A=A, B=B)
        self.pipes = []
        self.pipe_line = {}
        for ln, L in self.lines.items():
            for s in 'AB'[:L['pipes']]:
                p = ln + '-' + s
                self.pipes.append(p)
                self.pipe_line[p] = ln
        self.surveys = read_csv(os.path.join(d, 'surveys.csv'))
        wl = os.path.join(d, 'work_log.csv')
        self.work = read_csv(wl) if os.path.exists(wl) else []
        self.records = read_csv(os.path.join(d, 'records.csv'))
        try:
            self.allowance = int(self.site.get('survey_allowance', 0))
        except Exception:
            self.allowance = 0

    def norm_pipe(self, s):
        """Map a pipe or line reference as written in a file to the pipes it names."""
        t = re.sub(r'\s+', '', str(s).upper()).replace('_', '-')
        if t in self.pipe_line:
            return [t]
        if t in self.lines:
            return [p for p in self.pipes if self.pipe_line[p] == t]
        mm = re.match(r'^([A-Z]+)-?(\d+)-?([AB/&+,]*)$', t)
        if mm:
            ln = '%s-%s' % (mm.group(1), mm.group(2))
            if ln in self.lines:
                suf = re.sub(r'[^AB]', '', mm.group(3))
                if not suf:
                    return [p for p in self.pipes if self.pipe_line[p] == ln]
                return [ln + '-' + c for c in suf if ln + '-' + c in self.pipe_line]
        return [p for p in self.pipes if p in t]

    def params(self, pipe_or_line):
        L = self.lines[self.pipe_line.get(pipe_or_line, pipe_or_line)]
        return {k: L[k] for k in ('D', 'L', 'rho', 'cp', 'k', 'A', 'B')}


def stack(dicts, extra):
    """Arrays of pipe parameters for many elements: dicts = list of param dicts, extra = dict of lists."""
    out = {k: np.array([d[k] for d in dicts], float) for k in ('D', 'L', 'rho', 'cp', 'k', 'A', 'B')}
    for k, v in extra.items():
        out[k] = np.asarray(v, float)
    return out


# ----------------------------------------------------------------------------------------------- surveys

COVER_RE = re.compile(r'cover|lag|insul|clad|jacket|wrap|sheath|sheet|weatherproof|mineral\s*wool|rock\s*wool|'
                      r'foam', re.I)
OTHER_COVER_RE = re.compile(r'(valve|drain|manhole|pit|inspection|box|meter|gauge|pump)\s+cover|cover\s*(plate|bolt|gasket)',
                            re.I)
NOCHANGE_RE = re.compile(r'inspect|check|survey|measur|photograph|record|note|examin|look', re.I)
WORK_RE = re.compile(r'renew|repair|replac|patch|refit|re-?fit|reinstat|restor|install|fit|made\s*good|'
                     r'remov|strip|new|rebuil|re-?lag|re-?cover|re-?insul|mend|fix|seal|wrap|clad|lag', re.I)

READ_ERR = (('flow', 0.002), ('t_in', 0.02), ('t_amb', 0.1), ('t_out', 0.02))   # TS-2 5.4


def job_kind(text):
    """'cover' for work that changes a covering, 'maybe' for a mention of the covering that may not."""
    t = text or ''
    if not COVER_RE.search(t):
        return None
    if OTHER_COVER_RE.search(t) and not COVER_RE.search(OTHER_COVER_RE.sub('', t)):
        return 'maybe'                       # a cover of some other item, not plainly the pipe's covering
    if NOCHANGE_RE.search(t) and not WORK_RE.search(COVER_RE.sub('', t)):
        return 'maybe'
    return 'cover'


def survey_uo(pkg, rows):
    """Uo and its error bound (from the reading accuracy) for survey rows (dicts with pipe and readings)."""
    if not rows:
        return np.zeros(0), np.zeros(0)
    base = [pkg.params(r['pipe']) for r in rows]
    vals = {
        'flow': np.array([fnum(r['flow_t_h']) for r in rows]),
        't_in': np.array([fnum(r['t_in_C']) for r in rows]),
        't_out': np.array([fnum(r['t_out_C']) for r in rows]),
        't_amb': np.array([fnum(r['t_amb_C']) for r in rows]),
    }
    n = len(rows)
    sets = [dict(vals)]
    for key, err in READ_ERR:
        v = dict(vals)
        v[key] = vals[key] * (1 + err) if key == 'flow' else vals[key] + err
        sets.append(v)
    allp = stack(base * len(sets), {
        'm': np.concatenate([s['flow'] for s in sets]) / 3.6,
        'Tin': np.concatenate([s['t_in'] for s in sets]),
        'Ta': np.concatenate([s['t_amb'] for s in sets]),
    })
    tout = np.concatenate([s['t_out'] for s in sets])
    # Tout must lie strictly between the surroundings and the inlet
    tout = np.minimum(tout, allp['Tin'] - 1e-6)
    tout = np.maximum(tout, allp['Ta'] + 1e-6)
    U = invert_uo(allp, tout)
    U0 = U[:n]
    bound = np.zeros(n)
    for j in range(1, len(sets)):
        bound += np.abs(U[j * n:(j + 1) * n] - U0)
    return U0, np.maximum(bound, 1e-9)


def wmean(us, bs):
    w = 1.0 / np.asarray(bs) ** 2
    return float(np.sum(w * np.asarray(us)) / np.sum(w))


def consistency(us, bs):
    r = 0.0
    for i in range(len(us)):
        for j in range(i + 1, len(us)):
            r = max(r, abs(us[i] - us[j]) / (bs[i] + bs[j]))
    return r


DRIFT_RATIO = 0.5


def log(*a):
    print(*a, file=sys.stderr)


def plan_uo(pkg):
    """Uo of every pipe from the surveys on file, and the pipes worth surveying afresh (in priority order)."""
    U, bd = survey_uo(pkg, pkg.surveys)
    hist = {p: [] for p in pkg.pipes}
    for r, u, b in zip(pkg.surveys, U, bd):
        for p in pkg.norm_pipe(r['pipe']):
            hist[p].append((r['date'], float(u), float(b)))
    for p in hist:
        hist[p].sort()
    cover = {p: [] for p in pkg.pipes}
    maybe = {p: [] for p in pkg.pipes}
    for w in pkg.work:
        kind = job_kind(w.get('job', ''))
        if kind is None:
            continue
        for p in pkg.norm_pipe(w.get('pipe', '')):
            (cover if kind == 'cover' else maybe)[p].append((w.get('date', ''), w.get('job', '')))

    info = {}
    cands = []
    for p in pkg.pipes:
        h = hist[p]
        lw = max([d for d, _ in cover[p]], default='')
        lm = max([d for d, _ in maybe[p]], default='')
        valid = [x for x in h if x[0] > lw]
        sameday = [x for x in h if x[0] == lw]
        before = [x for x in h if x[0] < lw]
        st = dict(hist=h, last_work=lw, jobs=cover[p], valid=valid)
        if not h:
            st.update(kind='nosurvey', U=None)
            cands.append((0, 0.0, p))
        elif not valid:
            # covering worked on after the last survey: the surveys on file are of another covering
            if sameday and before and consistency([sameday[-1][1], before[-1][1]],
                                                  [sameday[-1][2], before[-1][2]]) > DRIFT_RATIO:
                st.update(kind='sameday', U=sameday[-1][1], B=sameday[-1][2])   # survey followed the work
                cands.append((1, 0.0, p))
            else:
                st.update(kind='stale', U=None, old=h[-1][1], oldB=h[-1][2])
                cands.append((0, 0.0, p))
        else:
            us = [x[1] for x in valid]
            bs = [x[2] for x in valid]
            r = consistency(us, bs) if len(us) > 1 else 0.0
            st.update(ratio=r, B=min(bs) / math.sqrt(len(bs)))
            if r > DRIFT_RATIO:
                # the covering is changing: the latest survey is the best of those on file
                st.update(kind='drift', U=us[-1], B=bs[-1])
                cands.append((2, -r, p))
            else:
                st.update(kind='ok', U=wmean(us, bs))
                if lm and lm > valid[-1][0]:
                    cands.append((2.2, 0.0, p))
                else:
                    cands.append((3 if len(us) > 1 else 2.5, -r, p))
        info[p] = st
    return info, cands


def fallback_uo(st):
    """Best estimate of Uo when the pipe cannot be surveyed afresh."""
    if st['kind'] == 'stale':
        txt = ' '.join(j for _, j in st['jobs']).lower()
        if re.search(r'renew|replac|new|re-?lag|re-?insul', txt):
            f = 0.5
        elif re.search(r'repair|patch|made\s*good|mend', txt):
            f = 0.65
        else:
            f = 0.6
        return st['old'] * f
    if st['kind'] == 'drift':
        v = st['valid']
        us = [x[1] for x in v]
        bs = [x[2] for x in v]
        # a step: the latest surveys agree with each other -> use them
        tail = [v[-1]]
        for x in reversed(v[:-1]):
            if consistency([x[1], tail[0][1]], [x[2], tail[0][2]]) <= DRIFT_RATIO:
                tail.insert(0, x)
            else:
                break
        steps = [us[i + 1] - us[i] for i in range(len(us) - 1)]
        trend = len(us) >= 2 and len(tail) == 1 and (all(d > 0 for d in steps) or all(d < 0 for d in steps))
        if not trend:
            return wmean([x[1] for x in tail], [x[2] for x in tail])
        import datetime as _dt

        def day(s_):
            try:
                return _dt.date.fromisoformat(s_).toordinal()
            except Exception:
                return None
        ds = [day(x[0]) for x in v[-2:]]
        if None in ds or ds[1] <= ds[0]:
            return us[-1]
        jd = [day(d) for d, _ in st['jobs']] + [ds[1]]
        t_now = max(d for d in jd if d is not None) + 14
        rate = math.log(us[-1] / us[-2]) / (ds[1] - ds[0])
        return float(us[-1] * math.exp(rate * (t_now - ds[1])))
    return st['U']


def site_default_uo(info):
    us = [st['U'] for st in info.values() if st.get('kind') == 'ok' and st.get('U')]
    return float(np.median(us)) if us else 5.0


def impact(pkg, p, st, recs_by_line):
    """Rough effect on the results of not knowing a stale pipe's covering (for ranking survey priority)."""
    ln = pkg.pipe_line[p]
    rr = recs_by_line.get(ln, [])
    if not rr or st.get('old') is None:
        return 1.0
    L = pkg.lines[ln]
    base = pkg.params(ln)
    m = np.array([fnum(r['flow_t_h']) for r in rr]) / 3.6 / L['pipes']
    Tin = np.array([fnum(r['t_in_C']) for r in rr])
    Ta = np.array([fnum(r['t_amb_C']) for r in rr])
    n = len(rr)
    P = stack([base] * (2 * n), {'m': np.concatenate([m, m]), 'Tin': np.concatenate([Tin, Tin]),
                                  'Ta': np.concatenate([Ta, Ta]),
                                  'Uo': np.concatenate([np.full(n, st['old']), np.full(n, 0.5 * st['old'])])})
    dp, T = integrate(P)
    e = np.maximum(np.abs(dp[n:] / dp[:n] - 1) / 0.015, np.abs(T[n:] - T[:n]) / 0.5)
    w = 3.0 if L['pipes'] == 2 else 1.0           # a pair's split can amplify it
    return float(np.max(e)) * w


def find_heatsurvey():
    exe = shutil.which('heatsurvey')
    if exe:
        return exe
    for c in ('/tmp/ol1_X1/app/heatsurvey',):
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def order_surveys(pkg_dir, pipes):
    cache = os.environ.get('LINES_FRESH')           # testing aid only: replay a reply saved earlier
    if cache and os.path.exists(cache):
        with open(cache) as f:
            text = f.read()
        log('survey reply replayed from', cache)
    else:
        exe = find_heatsurvey()
        if not exe or not pipes:
            return None, 'no command' if not exe else 'nothing to order'
        try:
            cp = subprocess.run([exe, pkg_dir] + list(pipes), capture_output=True, text=True, timeout=30)
        except Exception as e:
            return None, 'failed: %s' % e
        if cp.returncode != 0:
            return None, 'refused (%d): %s %s' % (cp.returncode, cp.stdout.strip()[:300], cp.stderr.strip()[:300])
        text = cp.stdout
        if cache:
            with open(cache, 'w') as f:
                f.write(text)
    rows = []
    hdr = None
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().split(',')]
        if hdr is None:
            if 'pipe' in cells and 't_out_C' in cells:
                hdr = cells
            continue
        if len(cells) != len(hdr):
            continue
        r = dict(zip(hdr, cells))
        try:
            for k in ('flow_t_h', 't_in_C', 't_out_C', 't_amb_C'):
                fnum(r[k])
        except Exception:
            continue
        rows.append(r)
    if not rows:
        return None, 'no rows in reply: %s' % text.strip()[:300]
    return rows, 'ok'


def decide_uo(pkg):
    info, cands = plan_uo(pkg)
    recs_by_line = {}
    for r in pkg.records:
        recs_by_line.setdefault(r['line'], []).append(r)
    # rank: stale/unsurveyed first (by their effect on the results), then the rest by priority
    keyed = []
    for pri, sub, p in cands:
        if pri == 0:
            try:
                sub = -impact(pkg, p, info[p], recs_by_line)
            except Exception:
                sub = 0.0
        keyed.append((pri, sub, p))
    keyed.sort()
    allowance = max(0, pkg.allowance)
    chosen = [p for _, _, p in keyed[:allowance]]
    needed = [p for pri, _, p in keyed if pri < 3]
    log('survey plan: allowance %d, needed %s, ordering %s' % (allowance, needed, chosen))
    fresh = {}
    tries = []                                     # a refused order does not count: retry smaller ones
    for lst in (chosen, needed[:allowance], [p for pri, _, p in keyed if pri < 1][:allowance]):
        if lst and lst not in tries:
            tries.append(lst)
    rows = None
    for lst in tries:
        rows, msg = order_surveys(pkg.dir, lst)
        log('survey order %s: %s' % (lst, msg))
        if rows or not msg.startswith('refused'):
            break
    for r in rows or []:
        for p in pkg.norm_pipe(r.get('pipe', '')):
            r2 = dict(r)
            r2['pipe'] = p
            fresh[p] = r2
    Uo = {}
    if fresh:
        ps = list(fresh)
        U, B = survey_uo(pkg, [fresh[p] for p in ps])
        fu = {p: (float(u), float(b)) for p, u, b in zip(ps, U, B)}
    else:
        fu = {}
    for p in pkg.pipes:
        st = info[p]
        if p in fu:
            u, b = fu[p]
            if st['kind'] == 'ok':
                us = [x[1] for x in st['valid']] + [u]
                bs = [x[2] for x in st['valid']] + [b]
                if consistency([wmean(us[:-1], bs[:-1]), u], [st['B'], b]) <= DRIFT_RATIO:
                    Uo[p] = wmean(us, bs)
                else:
                    Uo[p] = u
            else:
                Uo[p] = u
            log('  %s %s: on file %s -> fresh %.4f -> use %.4f' % (
                p, st['kind'], ','.join('%.3f' % x[1] for x in st['hist']), u, Uo[p]))
        else:
            Uo[p] = fallback_uo(st)
            if Uo[p] is None or not (Uo[p] > 0):
                Uo[p] = site_default_uo(info)
            if st['kind'] not in ('ok',):
                log('  %s %s: no fresh survey, estimate %.4f' % (p, st['kind'], Uo[p]))
    return Uo


# ----------------------------------------------------------------------------------------------- records

PHI_T = np.linspace(-11.0, 11.0, 176)
PHI = 1.0 / (1.0 + np.exp(-PHI_T))


def pair_eval(base, m, Tin, Ta, UA, UB, phi):
    """g = dp_A - dp_B and both pipes' results for pair elements at splits phi (all 1-D, same length)."""
    n = phi.size
    P = {k: np.concatenate([v, v]) for k, v in base.items()}
    P['m'] = np.concatenate([phi * m, (1.0 - phi) * m])
    P['Tin'] = np.concatenate([Tin, Tin])
    P['Ta'] = np.concatenate([Ta, Ta])
    P['Uo'] = np.concatenate([UA, UB])
    dp, T = integrate_chunked(P)
    return dp[:n] - dp[n:], dp[:n], dp[n:], T[:n], T[n:]


def solve_pairs(pkg, idx, Uo):
    """idx: list of record indices of pair lines.  Returns dp (Pa) and mixed outlet temperature."""
    recs = pkg.records
    nr = len(idx)
    lines = [recs[i]['line'] for i in idx]
    base = stack([pkg.params(l) for l in lines], {})
    m = np.array([fnum(recs[i]['flow_t_h']) for i in idx]) / 3.6
    Tin = np.array([fnum(recs[i]['t_in_C']) for i in idx])
    Ta = np.array([fnum(recs[i]['t_amb_C']) for i in idx])
    UA = np.array([Uo[l + '-A'] for l in lines])
    UB = np.array([Uo[l + '-B'] for l in lines])
    G = PHI.size

    # 1. g on the split grid for every record
    rep = lambda a: np.repeat(a, G)
    gb = {k: rep(v) for k, v in base.items()}
    ggrid = pair_eval(gb, rep(m), rep(Tin), rep(Ta), rep(UA), rep(UB), np.tile(PHI, nr))[0].reshape(nr, G)

    # order of records along each line
    order = {}
    for j, i in enumerate(idx):
        r = recs[i]
        try:
            h = float(r.get('hour', ''))
        except ValueError:
            h = float(j)
        order.setdefault(r['line'], []).append((h, j))
    seqs = [[j for _, j in sorted(v)] for v in order.values()]

    def pick(j, phi_prev, g_prev):
        """The root the split relaxes to from phi_prev, using the grid values of g.

        Returns key (identifies the root's grid interval), bracket lo, hi, and g at lo, hi (None = beyond grid)."""
        g = ggrid[j]
        if g_prev == 0.0:
            return ('at',), phi_prev, phi_prev, 0.0, 0.0
        k = int(np.searchsorted(PHI, phi_prev, side='right'))   # PHI[k-1] <= phi_prev < PHI[k]
        if g_prev > 0:          # dp_A > dp_B: flow moves out of pipe A, the split falls
            hi, ghi = phi_prev, g_prev
            for q in range(k - 1, -1, -1):
                if g[q] <= 0:
                    return ('dn', q), PHI[q], hi, g[q], ghi
                hi, ghi = PHI[q], g[q]
            return ('dn', -1), 0.0, hi, None, ghi
        lo, glo = phi_prev, g_prev
        for q in range(k, G):
            if g[q] >= 0:
                return ('up', q), lo, PHI[q], glo, g[q]
            lo, glo = PHI[q], g[q]
        return ('up', G), lo, 1.0, glo, None

    def interp_g(j, phi):
        t = math.log(phi / (1.0 - phi)) if 0 < phi < 1 else (-50.0 if phi <= 0 else 50.0)
        return float(np.interp(t, PHI_T, ggrid[j]))

    def lin_root(lo, hi, glo, ghi):
        if glo is None:
            return 0.5 * hi
        if ghi is None:
            return 0.5 * (1.0 + lo)
        if ghi == glo:
            return 0.5 * (lo + hi)
        return lo + (hi - lo) * (-glo) / (ghi - glo)

    exact_gprev = {}           # j -> (phi_prev used, exact g there)
    phi_star = np.full(nr, np.nan)
    keys = [None] * nr
    brackets = [None] * nr
    out_dp = np.zeros(nr)
    out_T = np.zeros(nr)
    for it in range(8):
        changed = []
        for seq in seqs:
            phi_prev = 0.5
            for j in seq:
                ex = exact_gprev.get(j)
                if ex is not None and ex[0] == phi_prev:
                    gp = ex[1]
                else:
                    gp = interp_g(j, phi_prev)
                key, lo, hi, glo, ghi = pick(j, phi_prev, gp)
                if keys[j] != key:
                    keys[j] = key
                    brackets[j] = (lo, hi)
                    changed.append(j)
                    phi_star[j] = lin_root(lo, hi, glo, ghi)
                phi_prev = phi_star[j]
        if not changed:
            break
        log('pair pass %d: %d roots to refine' % (it, len(changed)))
        # refine the chosen roots (Illinois method inside the bracket)
        ch = np.array(changed)
        lo = np.array([brackets[j][0] for j in ch], float)
        hi = np.array([brackets[j][1] for j in ch], float)
        same = hi <= lo
        lo = np.where(lo <= 0, np.minimum(PHI[0], hi) * 1e-3, lo)
        hi = np.where(hi >= 1, 1 - (1 - lo) * 1e-3, hi)
        sub = {k_: v[ch] for k_, v in base.items()}
        args = (sub, m[ch], Tin[ch], Ta[ch], UA[ch], UB[ch])
        r_lo = pair_eval(*args, lo)
        r_hi = pair_eval(*args, hi)
        glo, ghi = r_lo[0], r_hi[0]
        best = [np.where(np.abs(glo) <= np.abs(ghi), lo, hi)]
        pick_lo = np.abs(glo) <= np.abs(ghi)
        best_r = [np.where(pick_lo, a, b) for a, b in zip(r_lo, r_hi)]
        bx = best[0]
        bad = (np.sign(glo) == np.sign(ghi)) & ~same
        if np.any(bad) and it > 0:
            log('note: %d pair roots re-bracketed in pass %d' % (int(bad.sum()), it))
        side = np.zeros(ch.size)
        for _ in range(60):
            scale = np.maximum(np.abs(best_r[1]) + np.abs(best_r[2]), 1e-30)
            done = same | (np.abs(best_r[0]) <= 1e-10 * scale) | ((hi - lo) <= 1e-13)
            if np.all(done):
                break
            denom = ghi - glo
            x = lo - glo * (hi - lo) / np.where(denom == 0, 1.0, denom)
            x = np.where((denom == 0) | ~(x > lo) | ~(x < hi) | bad, 0.5 * (lo + hi), x)
            x = np.where(done, bx, x)
            r_x = pair_eval(*args, x)
            gx = r_x[0]
            better = (np.abs(gx) < np.abs(best_r[0])) & ~done
            bx = np.where(better, x, bx)
            best_r = [np.where(better, a, b) for a, b in zip(r_x, best_r)]
            left = (np.sign(gx) == np.sign(glo)) & ~done
            right = ~left & ~done
            lo_n = np.where(left, x, lo)
            hi_n = np.where(right, x, hi)
            glo_n = np.where(left, gx, np.where(right & (side == -1), 0.5 * glo, glo))
            ghi_n = np.where(right, gx, np.where(left & (side == 1), 0.5 * ghi, ghi))
            side = np.where(left, 1, np.where(right, -1, side))
            lo, hi, glo, ghi = lo_n, hi_n, glo_n, ghi_n
        g, dA, dB, TA, TB = best_r
        phi_star[ch] = bx
        out_dp[ch] = 0.5 * (dA + dB)
        out_T[ch] = bx * TA + (1 - bx) * TB
        # exact g at each record's starting split (the previous record's split)
        js, ps = [], []
        for seq in seqs:
            prev = 0.5
            for j in seq:
                ex = exact_gprev.get(j)
                if ex is None or ex[0] != prev:
                    js.append(j)
                    ps.append(prev)
                prev = phi_star[j]
        if js:
            ja = np.array(js)
            pa = np.array(ps)
            sub = {k_: v[ja] for k_, v in base.items()}
            ge = pair_eval(sub, m[ja], Tin[ja], Ta[ja], UA[ja], UB[ja], pa)[0]
            for j, p_, g_ in zip(js, ps, ge):
                exact_gprev[j] = (p_, float(g_))
    return out_dp, out_T, phi_star


def solve(pkg, Uo):
    recs = pkg.records
    n = len(recs)
    dp = np.zeros(n)
    T = np.zeros(n)
    singles = [i for i, r in enumerate(recs) if pkg.lines[r['line']]['pipes'] == 1]
    pairs = [i for i, r in enumerate(recs) if pkg.lines[r['line']]['pipes'] == 2]
    if singles:
        P = stack([pkg.params(recs[i]['line']) for i in singles], {
            'm': [fnum(recs[i]['flow_t_h']) / 3.6 for i in singles],
            'Tin': [fnum(recs[i]['t_in_C']) for i in singles],
            'Ta': [fnum(recs[i]['t_amb_C']) for i in singles],
            'Uo': [Uo[recs[i]['line'] + '-A'] for i in singles]})
        d, t = integrate_chunked(P)
        dp[singles] = d
        T[singles] = t
    if pairs:
        try:
            d, t, _ = solve_pairs(pkg, pairs, Uo)
            if not (np.all(np.isfinite(d)) and np.all(np.isfinite(t))):
                raise ValueError('non-finite pair result')
        except Exception as e:
            log('pair solver failed (%s); using the even-split branch' % e)
            d, t = solve_pairs_simple(pkg, pairs, Uo)
        dp[pairs] = d
        T[pairs] = t
    return dp, T


def solve_pairs_simple(pkg, idx, Uo):
    """Fallback: one root by bisection on the split (no branch tracking)."""
    recs = pkg.records
    lines = [recs[i]['line'] for i in idx]
    base = stack([pkg.params(l) for l in lines], {})
    m = np.array([fnum(recs[i]['flow_t_h']) for i in idx]) / 3.6
    Tin = np.array([fnum(recs[i]['t_in_C']) for i in idx])
    Ta = np.array([fnum(recs[i]['t_amb_C']) for i in idx])
    UA = np.array([Uo[l + '-A'] for l in lines])
    UB = np.array([Uo[l + '-B'] for l in lines])
    lo = np.full(len(idx), 1e-6)
    hi = np.full(len(idx), 1 - 1e-6)
    for _ in range(45):
        x = 0.5 * (lo + hi)
        g = pair_eval(base, m, Tin, Ta, UA, UB, x)[0]
        hi = np.where(g > 0, x, hi)
        lo = np.where(g > 0, lo, x)
    x = 0.5 * (lo + hi)
    g, dA, dB, TA, TB = pair_eval(base, m, Tin, Ta, UA, UB, x)
    return 0.5 * (dA + dB), x * TA + (1 - x) * TB


def main():
    if len(sys.argv) != 3:
        print('usage: python3 lines.py PACKAGE_DIR OUT_CSV', file=sys.stderr)
        sys.exit(2)
    pkg_dir, out_csv = sys.argv[1], sys.argv[2]
    np.seterr(all='ignore')
    pkg = Package(pkg_dir)
    try:
        Uo = decide_uo(pkg)
    except Exception as e:                      # never leave the package without results
        log('Uo from the surveys on file only (%s)' % e)
        info, _ = plan_uo(pkg)
        Uo = {p: (fallback_uo(st) or site_default_uo(info)) for p, st in info.items()}
    dp, T = solve(pkg, Uo)
    with open(out_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['record', 'dp_kPa', 't_out_C'])
        for r, d, t in zip(pkg.records, dp, T):
            w.writerow([r['record'], '%.6f' % (d / 1000.0), '%.4f' % t])


if __name__ == '__main__':
    main()
