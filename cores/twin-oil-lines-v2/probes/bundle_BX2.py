#!/usr/bin/env python3
"""TS-2 heated oil transfer lines: pressure drop and outlet temperature for every hourly record of a site.

    python3 lines.py PACKAGE_DIR OUT_CSV

Outline
  * oil viscosity by ASTM D341 through the two tabulated points (TS-2 2.2);
  * one pipe (TS-2 3): heat balance and pressure gradient integrated along the pipe with the wall temperature solved
    locally from 3.2/3.3, in the variable s with x = L s^3 (removes the entrance singularity of Gz^(1/3)) and with
    ln(Tb - Ta) as the thermal state (no stiffness when a starved pipe cools to ambient within a few metres);
  * Uo of each pipe from the heat-loss surveys (TS-2 5.2), using only surveys of the covering as it now stands (5.3);
    surveys that disagree beyond their reading accuracy (5.4) mark a covering that has changed without a log entry;
  * pairs whose surveyed division of flow cannot give equal pressure drops with the bores as laid show a pipe whose
    bore has changed in service (5.1); its bore is found from the pressure balance of the survey;
  * pipes whose present state the surveys on file do not give are surveyed by the crew (one order, <= allowance);
  * pairs (TS-2 4): the division is followed record by record from the division of the previous record, oil moving
    from the pipe with the higher pressure drop until the two drops are equal (4.2); the run opens at the only
    division (4.3).
"""
import sys
import os
import json
import math
import csv
import shutil
import subprocess

import numpy as np

LN10 = math.log(10.0)
TK = 273.15
SIG_T = 0.02 / math.sqrt(3.0)      # TS-2 5.4 reading accuracy, as standard deviations of a uniform error
SIG_TA = 0.1 / math.sqrt(3.0)
SIG_M = 0.002 / math.sqrt(3.0)
DRIFT_RATIO = 3.0                  # spread of Uo between surveys, in combined standard deviations, that marks a change
IMBAL_TOL = 0.015                  # |ln(dpA/dpB)| at a survey beyond which the pair's bores are not as laid
BORE_DRIFT = 0.006                 # relative spread of a fitted bore between campaigns that marks a bore still changing
F_RENEWED = 0.5                    # fall-back only: Uo of renewed / repaired covering relative to the old one
F_REPAIRED = 0.65
F_REMOVED = 1.5


# ----------------------------------------------------------------------------------------------------------------
# oil and single pipe
# ----------------------------------------------------------------------------------------------------------------

def oil_AB(nu50, nu100):
    T1, T2 = 50.0 + TK, 100.0 + TK
    y1 = math.log10(math.log10(nu50 + 0.7))
    y2 = math.log10(math.log10(nu100 + 0.7))
    B = (y1 - y2) / (math.log10(T2) - math.log10(T1))
    A = y1 + B * math.log10(T1)
    return A, B


class Cases:
    """A batch of single-pipe calculations; every attribute is a 1-D float array of the same length."""
    __slots__ = ('a1', 'B', 'rho', 'cp', 'k', 'D', 'L', 'm', 'U', 'Tin', 'Ta')

    def __init__(self, **kw):
        arrs = np.broadcast_arrays(*[np.asarray(kw[n], dtype=float) for n in self.__slots__])
        for n, a in zip(self.__slots__, arrs):
            setattr(self, n, np.ascontiguousarray(a).ravel())


def integrate(c, N=32, newton=2):
    """Outlet temperature (C) and pressure drop (Pa) for a batch of pipes (TS-2 3.1-3.5)."""
    a1, B, U, Ta = c.a1, c.B, c.U, c.Ta
    gzc = 4.0 * c.m * c.cp / (math.pi * c.k)                 # Gz * x
    c1 = 1.077 * np.cbrt(gzc / c.L)                          # 1.077 Gz^(1/3) * s  (x = L s^3)
    kD = c.k / c.D
    u = 4.0 * c.m / (math.pi * c.D ** 2 * c.rho)
    cdp = 32e-6 * u * c.rho / c.D ** 2 * 3.0 * c.L           # dp/ds = cdp sqrt(nu_b nu_w)[cSt] s^2
    cq = math.pi * c.D * U / (c.m * c.cp) * 3.0 * c.L        # dln(theta)/ds = -cq w s^2
    th0 = c.Tin - Ta
    sg = np.where(th0 >= 0.0, 1.0, -1.0)
    y = np.log(np.maximum(np.abs(th0), 1e-9))
    p = np.zeros_like(y)
    w = np.ones_like(y)
    NU0 = 3.66 ** 3 + 0.7 ** 3
    cB = LN10 * B

    def rhs(s, y, w):
        if s <= 0.0:
            return 0.0, 0.0, w
        g3 = c1 / s - 0.7
        H0 = np.cbrt(NU0 + g3 * g3 * g3) * kD
        th = sg * np.exp(y)
        Tb = Ta + th
        lnTb = np.log(Tb + TK)
        nub = np.exp(LN10 * np.exp(a1 - B * lnTb)) - 0.7
        lnnub = np.log(nub)
        for _ in range(newton):
            TwK = Ta + w * th + TK
            ww = np.exp(a1 - B * np.log(TwK))
            v07 = np.exp(LN10 * ww)
            nuw = v07 - 0.7
            r = np.exp(0.14 * (lnnub - np.log(nuw)))
            dlnr = 0.14 * v07 * cB * ww / TwK / nuw * th      # d ln r / d w
            omw = 1.0 - w
            F = H0 * r * omw - U * w
            Fp = H0 * r * (dlnr * omw - 1.0) - U
            w = np.minimum(np.maximum(w - F / Fp, 0.0), 1.0)
        TwK = Ta + w * th + TK
        nuw = np.exp(LN10 * np.exp(a1 - B * np.log(TwK))) - 0.7
        s2 = s * s
        return -cq * w * s2, cdp * np.sqrt(nub * nuw) * s2, w

    h = 1.0 / N
    for i in range(N):
        s = i * h
        k1y, k1p, w1 = rhs(s, y, w)
        k2y, k2p, w2 = rhs(s + 0.5 * h, y + 0.5 * h * k1y, w1)
        k3y, k3p, w3 = rhs(s + 0.5 * h, y + 0.5 * h * k2y, w2)
        k4y, k4p, w = rhs(s + h, y + h * k3y, w3)
        y = y + h / 6.0 * (k1y + 2.0 * k2y + 2.0 * k3y + k4y)
        p = p + h / 6.0 * (k1p + 2.0 * k2p + 2.0 * k3p + k4p)
    return Ta + sg * np.exp(y), p


def safe(x, default):
    try:
        x = float(x)
        return x if math.isfinite(x) else default
    except Exception:
        return default


# ----------------------------------------------------------------------------------------------------------------
# package
# ----------------------------------------------------------------------------------------------------------------

def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for r in rows:
        out.append({(k or '').strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()})
    return out


def norm_pipe(s):
    s = (s or '').strip().upper().replace('_', '-').replace(' ', '-')
    while '--' in s:
        s = s.replace('--', '-')
    return s


class Oil:
    def __init__(self, r):
        self.rho = float(r['density_kg_m3'])
        self.cp = float(r['cp_J_kgK'])
        self.k = float(r['k_W_mK'])
        A, B = oil_AB(float(r['nu50_cSt']), float(r['nu100_cSt']))
        self.a1 = LN10 * A
        self.B = B


class Pipe:
    def __init__(self, name, line, oil, D, L):
        self.name, self.line, self.oil, self.D0, self.L = name, line, oil, D, L
        self.D = D
        self.U = None
        self.surveys = []           # dicts: date, line_flow, m (kg/s), Tin, Tout, Ta, U, sig, D
        self.cover_jobs = []        # (date, kind)
        self.valid = []             # surveys of the covering as it stands
        self.need = 0.0             # crew priority (0: none)
        self.need_kind = ''
        self.crew = None
        self.bore_changed = False

    def cases(self, m, Tin, Ta, U=None, D=None):
        o = self.oil
        return Cases(a1=o.a1, B=o.B, rho=o.rho, cp=o.cp, k=o.k, D=self.D if D is None else D, L=self.L, m=m,
                     U=self.U if U is None else U, Tin=Tin, Ta=Ta)


def concat_cases(lst):
    kw = {}
    for n in Cases.__slots__:
        kw[n] = np.concatenate([getattr(c, n) for c in lst])
    return Cases(**kw)


def fit_U(cs, Tout, N=40, newton=3, iters=40):
    """Uo for which TS-2 3.1-3.3 give the outlet temperature read (TS-2 5.2), vectorised over cases."""
    n = cs.m.size
    th_in = cs.Tin - cs.Ta
    th_out = Tout - cs.Ta
    ok = (th_in != 0) & (th_out / np.where(th_in == 0, 1, th_in) > 1e-6) & (th_out / np.where(th_in == 0, 1, th_in) < 1)
    ratio = np.where(ok, th_out / np.where(th_in == 0, 1, th_in), 0.5)
    target = np.log(ratio)
    Us = cs.m * cs.cp * (-target) / (math.pi * cs.D * cs.L)        # no film resistance
    z = np.log(np.maximum(Us * 1.2, 1e-4))
    zlo = np.log(np.maximum(Us, 1e-6)) - 1e-9                      # U is at least the no-film value
    zhi = np.full(n, np.inf)

    def resid(zz):
        cs.U = np.exp(zz)
        T, _ = integrate(cs, N=N, newton=newton)
        r = (T - cs.Ta) / np.where(th_in == 0, 1, th_in)
        return np.log(np.maximum(r, 1e-300)) - target                 # decreasing in U

    f = resid(z)
    zp, fp = z + 0.0, f + 0.0
    z2 = z + np.where(f > 0, 0.2, -0.2)
    for it in range(iters):
        f2 = resid(z2)
        zlo = np.where(f2 > 0, np.maximum(zlo, z2), zlo)
        zhi = np.where(f2 <= 0, np.minimum(zhi, z2), zhi)
        den = f2 - fp
        step = np.where(np.abs(den) > 1e-300, -f2 * (z2 - zp) / np.where(den == 0, 1, den), 0.0)
        step = np.clip(step, -1.0, 1.0)
        zn = z2 + step
        bad = (zn <= zlo) | (zn >= zhi)
        mid = np.where(np.isfinite(zhi), 0.5 * (zlo + zhi), zlo + 1.0)
        zn = np.where(bad, mid, zn)
        zp, fp = z2, f2
        if np.all(np.abs(zn - z2) < 1e-11):
            z2 = zn
            break
        z2 = zn
    cs.U = np.exp(z2)
    U = np.where(ok, cs.U, np.nan)
    return U


class Site:
    def __init__(self, pkg):
        self.pkg = pkg
        try:
            with open(os.path.join(pkg, 'site.json'), encoding='utf-8-sig') as fh:
                self.meta = json.load(fh)
        except Exception:
            self.meta = {}
        self.allowance = int(safe(self.meta.get('survey_allowance', 0), 0))
        self.oils = {}
        for r in read_csv(os.path.join(pkg, 'oils.csv')):
            try:
                self.oils[(r.get('oil') or '').strip().upper()] = Oil(r)
            except Exception as e:
                sys.stderr.write(f'oil skipped: {r!r} {e!r}\n')
        self.lines = {}
        self.pipes = {}
        for r in read_csv(os.path.join(pkg, 'lines.csv')):
            try:
                name = norm_pipe(r['line'])
                npipes = int(round(safe(r.get('pipes', 1), 1)))
                oil = self.oils.get((r.get('oil') or '').strip().upper())
                if oil is None:
                    oil = next(iter(self.oils.values()))
                    sys.stderr.write(f'line {name}: oil {r.get("oil")!r} not tabulated\n')
                D = float(r['bore_mm']) / 1000.0
                L = float(r['length_m'])
            except Exception as e:
                sys.stderr.write(f'line skipped: {r!r} {e!r}\n')
                continue
            ps = []
            for suf in ('A', 'B')[:max(1, min(2, npipes))]:
                p = Pipe(f'{name}-{suf}', name, oil, D, L)
                self.pipes[p.name] = p
                ps.append(p)
            self.lines[name] = ps
        self.records = read_csv(os.path.join(pkg, 'records.csv'))
        try:
            self.surveys = read_csv(os.path.join(pkg, 'surveys.csv'))
        except Exception:
            self.surveys = []
        try:
            self.work = read_csv(os.path.join(pkg, 'work_log.csv'))
        except Exception:
            self.work = []


# ----------------------------------------------------------------------------------------------------------------
# covering work
# ----------------------------------------------------------------------------------------------------------------

COVER_WORDS = ('covering', 'lagg', 'insulat', 'cladd')
NO_WORK_WORDS = ('inspect', 'check', 'survey', 'examin', 'no work', 'no action', 'noted', 'looked', 'measured',
                 'photograph', 'tested', 'deferred', 'postponed', 'cancel')


def covering_kind(job):
    j = (job or '').lower()
    if not any(wd in j for wd in COVER_WORDS):
        return None
    if any(wd in j for wd in NO_WORK_WORDS) and not any(wd in j for wd in ('renew', 'repair', 'replac', 'new ')):
        return None
    if ('remov' in j or 'strip' in j or 'taken off' in j) and not ('renew' in j or 'replac' in j or 'new' in j):
        return 'removed'
    if 'renew' in j or 'replac' in j or 'new' in j or 're-lag' in j or 'relag' in j:
        return 'renewed'
    return 'repaired'


# ----------------------------------------------------------------------------------------------------------------
# surveys -> state of each pipe
# ----------------------------------------------------------------------------------------------------------------

def survey_sigma(pipe_list, svs):
    """Standard deviation of the fitted Uo of each survey from the reading accuracy (TS-2 5.4)."""
    pert = []
    for p, s in zip(pipe_list, svs):
        D = s.get('D') or p.D
        for dm, dti, dta, du in ((0, 0, 0, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)):
            pert.append(p.cases(s['m'] * (1 + 1e-3 * dm), s['Tin'] + 0.01 * dti, s['Ta'] + 0.05 * dta,
                                U=s['U'] * (1 + 1e-3 * du), D=D))
    T, _ = integrate(concat_cases(pert), N=40, newton=3)
    T = T.reshape(-1, 5)
    dTdm = (T[:, 1] - T[:, 0]) / 1e-3         # per relative m
    dTdTi = (T[:, 2] - T[:, 0]) / 0.01
    dTdTa = (T[:, 3] - T[:, 0]) / 0.05
    dTdU = (T[:, 4] - T[:, 0]) / 1e-3         # per relative U
    var = SIG_T ** 2 + (dTdTi * SIG_T) ** 2 + (dTdTa * SIG_TA) ** 2 + (dTdm * SIG_M) ** 2
    rel = np.sqrt(var) / np.maximum(np.abs(dTdU), 1e-12)
    return rel


def dp_at(p, m, Tin, Ta, U, D):
    _, dp = integrate(p.cases(m, Tin, Ta, U=U, D=D), N=40, newton=3)
    return dp


def solve_bore(pn, po, rows):
    """Joint bore and Uo of pipe pn from surveys: heat fit to its outlet temperature and equal pressure drop with the
    other pipe po.  rows: list of dict(mn, mo, Tin, Tout, Ta, Uo_other, Do_other).  Returns arrays D, U."""
    n = len(rows)
    mn = np.array([r['mn'] for r in rows])
    mo = np.array([r['mo'] for r in rows])
    Tin = np.array([r['Tin'] for r in rows])
    Tout = np.array([r['Tout'] for r in rows])
    Ta = np.array([r['Ta'] for r in rows])
    Uo = np.array([r['Uo_other'] for r in rows])
    Do = np.array([r['Do_other'] for r in rows])
    dpo = dp_at(po, mo, Tin, Ta, Uo, Do)

    def F(lnD):
        D = np.exp(lnD)
        U = fit_U(pn.cases(mn, Tin, Ta, U=1.0, D=D), Tout)
        dpn = dp_at(pn, mn, Tin, Ta, U, D)
        return np.log(dpn / dpo), U

    z0 = np.full(n, math.log(pn.D0))
    f0, U0 = F(z0)
    z1 = z0 + f0 / 4.0                      # laminar: dp ~ D^-4
    U1 = U0
    for _ in range(12):
        f1, U1 = F(z1)
        den = f1 - f0
        zn = z1 - f1 * (z1 - z0) / np.where(np.abs(den) > 1e-14, den, 1e-14)
        zn = np.clip(zn, z1 - 0.3, z1 + 0.3)
        z0, f0 = z1, f1
        if np.all(np.abs(zn - z1) < 1e-10):
            z1 = zn
            f1, U1 = F(z1)
            break
        z1 = zn
    return np.exp(z1), U1


def wmean(vals, rels):
    vals = np.asarray(vals, float)
    sig = np.asarray(rels, float) * vals
    w = 1.0 / np.maximum(sig, 1e-9) ** 2
    return float(np.sum(w * vals) / np.sum(w)), float(1.0 / math.sqrt(np.sum(w)))


def max_spread_ratio(vals, rels):
    vals = np.asarray(vals, float)
    sig = np.asarray(rels, float) * vals
    best = 0.0
    for i in range(len(vals)):
        for j in range(i + 1, len(vals)):
            best = max(best, abs(vals[i] - vals[j]) / max(math.hypot(sig[i], sig[j]), 1e-12))
    return best


def analyse_surveys(site):
    # attach surveys
    for r in site.surveys:
        p = site.pipes.get(norm_pipe(r.get('pipe')))
        if p is None:
            continue
        s = dict(date=r.get('date', ''), line_flow=safe(r.get('line_flow_t_h'), float('nan')) / 3.6,
                 m=safe(r.get('flow_t_h'), float('nan')) / 3.6, Tin=safe(r.get('t_in_C'), float('nan')),
                 Tout=safe(r.get('t_out_C'), float('nan')), Ta=safe(r.get('t_amb_C'), float('nan')))
        if all(math.isfinite(s[k]) for k in ('m', 'Tin', 'Tout', 'Ta')) and s['m'] > 0:
            p.surveys.append(s)
    for p in site.pipes.values():
        p.surveys.sort(key=lambda s: s['date'])
    # covering work
    for r in site.work:
        kind = covering_kind(r.get('job'))
        if kind is None:
            continue
        nm = norm_pipe(r.get('pipe'))
        targets = [site.pipes[nm]] if nm in site.pipes else site.lines.get(nm, [])
        for p in targets:
            p.cover_jobs.append((r.get('date', ''), kind))
    # fit Uo of every survey with the bore as laid
    allp, alls = [], []
    for p in site.pipes.values():
        for s in p.surveys:
            allp.append(p)
            alls.append(s)
    if alls:
        cs = concat_cases([p.cases(s['m'], s['Tin'], s['Ta'], U=1.0, D=p.D0) for p, s in zip(allp, alls)])
        U = fit_U(cs, np.array([s['Tout'] for s in alls]))
        for s, u in zip(alls, U):
            s['U'] = float(u)
            s['D'] = None
        good = [(p, s) for p, s in zip(allp, alls) if math.isfinite(s['U'])]
        if good:
            rel = survey_sigma([g[0] for g in good], [dict(g[1], D=g[0].D0) for g in good])
            for (p, s), rl in zip(good, rel):
                s['sig'] = float(rl)
        for s in alls:
            if not math.isfinite(s['U']):
                s['sig'] = float('nan')
    # pairs: are the bores as laid?  pressure balance at each campaign (one batch for all pairs)
    pairs = []
    cl = []
    for name, ps in site.lines.items():
        if len(ps) != 2:
            continue
        pa, pb = ps
        sa = {s['date']: s for s in pa.surveys if math.isfinite(s['U'])}
        sb = {s['date']: s for s in pb.surveys if math.isfinite(s['U'])}
        dates = sorted(set(sa) & set(sb))
        if not dates:
            continue
        rows_a = [sa[d] for d in dates]
        rows_b = [sb[d] for d in dates]
        cl.append(pa.cases(np.array([s['m'] for s in rows_a]), np.array([s['Tin'] for s in rows_a]),
                           np.array([s['Ta'] for s in rows_a]), U=np.array([s['U'] for s in rows_a]), D=pa.D0))
        cl.append(pb.cases(np.array([s['m'] for s in rows_b]), np.array([s['Tin'] for s in rows_b]),
                           np.array([s['Ta'] for s in rows_b]), U=np.array([s['U'] for s in rows_b]), D=pb.D0))
        pairs.append((pa, pb, sa, sb, dates))
    dps = integrate(concat_cases(cl), N=40, newton=3)[1] if cl else np.zeros(0)
    pos = 0
    for (pa, pb, sa, sb, dates) in pairs:
        n = len(dates)
        dpa = dps[pos:pos + n]
        dpb = dps[pos + n:pos + 2 * n]
        pos += 2 * n
        imb = np.log(dpa / dpb)
        if not np.any(np.abs(imb) > IMBAL_TOL):
            continue
        k = int(np.argmax(np.abs(imb)))
        pn, po = (pa, pb) if imb[k] < 0 else (pb, pa)      # the pipe whose drop the bore as laid makes too low
        sn = sa if pn is pa else sb
        so = sb if pn is pa else sa
        rows = [dict(mn=sn[d]['m'], mo=so[d]['m'], Tin=sn[d]['Tin'], Tout=sn[d]['Tout'], Ta=sn[d]['Ta'],
                     Uo_other=so[d]['U'], Do_other=po.D0) for d in dates]
        D, U = solve_bore(pn, po, rows)
        for d, dd, uu in zip(dates, D, U):
            sn[d]['D'] = float(dd)
            sn[d]['U'] = float(uu)
        rel = survey_sigma([pn] * len(dates), [sn[d] for d in dates])
        for d, rl in zip(dates, rel):
            sn[d]['sig'] = float(rl)
        pn.bore_changed = True
        pn.partner = po
        pn.bore_hist = [(d, sn[d]['D']) for d in dates]
    # state of each pipe from the surveys on file
    for p in site.pipes.values():
        last_job = max([j[0] for j in p.cover_jobs], default='')
        svs = [s for s in p.surveys if math.isfinite(s.get('U', float('nan')))]
        valid = []
        for i, s in enumerate(svs):
            if last_job and s['date'] < last_job:
                continue
            if last_job and s['date'] == last_job:
                # same day as the work: before it if it agrees with the survey before
                prev = [t for t in svs if t['date'] < s['date']]
                if not prev or max_spread_ratio([prev[-1]['U'], s['U']], [prev[-1]['sig'], s['sig']]) < DRIFT_RATIO:
                    continue
            valid.append(s)
        p.valid = valid
        p.stale = svs[-1] if svs else None
        p.last_kind = max(p.cover_jobs)[1] if p.cover_jobs else ''
        if not valid:
            p.need, p.need_kind = 1000.0 + {'removed': 20.0, 'renewed': 10.0}.get(p.last_kind, 0.0), 'covering'
        else:
            ratio = max_spread_ratio([s['U'] for s in valid], [s['sig'] for s in valid])
            p.u_ratio = ratio
            if ratio > DRIFT_RATIO:
                p.need, p.need_kind = 100.0 + min(ratio, 99.0), 'Uo drift'
        if p.bore_changed:
            Ds = np.array([d for _, d in p.bore_hist])
            spread = (Ds.max() - Ds.min()) / Ds.mean() if Ds.size else 0.0
            p.bore_spread = spread
            if Ds.size < 2 or spread > BORE_DRIFT:
                p.need = max(p.need, 500.0 + min(spread * 100.0, 99.0))
                p.need_kind = 'bore drift' if p.need < 1000 else p.need_kind
    # the order: the pipes whose state is not known, most needed first, no more than the allowance
    cand = sorted([p for p in site.pipes.values() if p.need > 0], key=lambda p: -p.need)
    order = cand[:max(0, site.allowance)]
    if len(order) < site.allowance:
        # spare places: pipes whose surveys agree least well among those not yet ordered
        rest = sorted([p for p in site.pipes.values() if p.need == 0 and getattr(p, 'u_ratio', 0.0) > 2.0],
                      key=lambda p: -p.u_ratio)
        order += rest[:site.allowance - len(order)]
    return order


def call_crew(site, order):
    if not order:
        return {}
    exe = shutil.which('heatsurvey')
    if exe is None:
        here = os.path.join(os.path.dirname(os.path.abspath(site.pkg)), '..', '..', 'heatsurvey')
        for cand in (here, '/tmp/ftl_BX2/app/heatsurvey'):
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                exe = cand
                break
    if exe is None:
        return {}
    try:
        res = subprocess.run([exe, site.pkg] + [p.name for p in order], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=20, universal_newlines=True)
    except Exception:
        return {}
    if res.returncode != 0:
        return {}
    lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
    hdr = None
    out = {}
    for ln in lines:
        cells = [c.strip() for c in ln.split(',')]
        if hdr is None:
            if 'pipe' in [c.lower() for c in cells]:
                hdr = [c.lower() for c in cells]
            continue
        if len(cells) != len(hdr):
            continue
        d = dict(zip(hdr, cells))
        nm = norm_pipe(d.get('pipe'))
        try:
            s = dict(date='crew', line_flow=float(d['line_flow_t_h']) / 3.6, m=float(d['flow_t_h']) / 3.6,
                     Tin=float(d['t_in_c']), Tout=float(d['t_out_c']), Ta=float(d['t_amb_c']))
        except Exception:
            continue
        if nm in site.pipes and s['m'] > 0:
            out[nm] = s
    return out


def day_number(d):
    try:
        import datetime
        return datetime.date.fromisoformat(str(d).strip()[:10]).toordinal()
    except Exception:
        return None


def extrapolate(hist, t_now):
    """Linear trend of the last two (date, value) points carried to t_now; the last value if that is not possible."""
    pts = [(day_number(d), v) for d, v in hist if day_number(d) is not None and math.isfinite(v)]
    if not pts:
        return hist[-1][1]
    pts.sort()
    last = pts[-1][1]
    if len(pts) < 2 or t_now is None or pts[-1][0] <= pts[-2][0]:
        return last
    slope = (pts[-1][1] - pts[-2][1]) / (pts[-1][0] - pts[-2][0])
    v = last + slope * max(0, t_now - pts[-1][0])
    return float(min(max(v, 0.67 * last), 1.5 * last))


def settle_state(site, crew):
    """Present Uo (and bore) of every pipe."""
    # 1. pipes whose state the surveys on file give (a pipe still changing is carried forward in time only as a
    #    fall-back for when the crew cannot survey it: records come after the last job on the log)
    t_now = None
    dates = [r.get('date', '') for r in site.work] + [s['date'] for p in site.pipes.values() for s in p.surveys]
    dates = [d for d in dates if day_number(d) is not None]
    if dates:
        t_now = max(day_number(d) for d in dates) + 7
    for p in site.pipes.values():
        if p.valid:
            p.U, _ = wmean([s['U'] for s in p.valid], [s['sig'] for s in p.valid])
            if p.need_kind == 'Uo drift':
                p.U = extrapolate([(s['date'], s['U']) for s in p.valid], t_now)
        elif p.stale is not None:
            f = {'renewed': F_RENEWED, 'removed': F_REMOVED}.get(p.last_kind, F_REPAIRED)
            p.U = p.stale['U'] * f
        else:
            p.U = None
        if p.bore_changed:
            Ds = [d for _, d in p.bore_hist]
            if p.need_kind == 'bore drift' or getattr(p, 'bore_spread', 0.0) > BORE_DRIFT:
                p.D = min(extrapolate(p.bore_hist, t_now), Ds[-1])
            else:
                p.D = float(np.mean(Ds))
    # 2. crew surveys: plain pipes first, then pipes whose bore has changed (need their partner's state)
    plain = [nm for nm in crew if not site.pipes[nm].bore_changed]
    if plain:
        ps = [site.pipes[nm] for nm in plain]
        ss = [crew[nm] for nm in plain]
        cs = concat_cases([p.cases(s['m'], s['Tin'], s['Ta'], U=1.0, D=p.D) for p, s in zip(ps, ss)])
        U = fit_U(cs, np.array([s['Tout'] for s in ss]))
        ok = [(p, s, float(u)) for p, s, u in zip(ps, ss, U) if math.isfinite(u)]
        for p, s, u in ok:
            s['U'] = u
        rels = survey_sigma([o[0] for o in ok], [dict(o[1], D=o[0].D) for o in ok]) if ok else []
        for (p, s, u), rel in zip(ok, rels):
            s['sig'] = float(rel)
            p.crew = s
            if p.need > 0 or not p.valid:
                p.U = u
                s['replaces'] = True
            else:
                # a spare place: the crew's survey joins the surveys on file unless it shows a change
                Uh, sh = wmean([t['U'] for t in p.valid], [t['sig'] for t in p.valid])
                ratio = abs(s['U'] - Uh) / max(math.hypot(sh, s['sig'] * s['U']), 1e-12)
                if ratio > DRIFT_RATIO:
                    p.U = u
                    s['replaces'] = True
                else:
                    p.U = wmean([t['U'] for t in p.valid] + [s['U']], [t['sig'] for t in p.valid] + [s['sig']])[0]
    for nm in crew:
        p = site.pipes[nm]
        if not p.bore_changed:
            continue
        s = crew[nm]
        po = p.partner
        if po.name in crew and 'U' in crew[po.name]:
            mo = crew[po.name]['m']
        else:
            mo = s['line_flow'] - s['m']
        if po.U is None or not (mo > 0):
            continue
        D, U = solve_bore(p, po, [dict(mn=s['m'], mo=mo, Tin=s['Tin'], Tout=s['Tout'], Ta=s['Ta'],
                                       Uo_other=po.U, Do_other=po.D)])
        if math.isfinite(D[0]) and math.isfinite(U[0]):
            p.D, p.U = float(D[0]), float(U[0])
            p.crew = s
    # 3. pairs: the surveyed division of the oil must give equal pressure drops (TS-2 4.1); with the bores as laid
    #    this is a second reading of the two Uo, often a sharper one than the heat balance of a single survey
    try:
        joint_pairs(site)
    except Exception as e:
        sys.stderr.write(f'joint estimate skipped: {e!r}\n')
    # anything still unknown: the site's median
    known = [p.U for p in site.pipes.values() if p.U is not None and math.isfinite(p.U)]
    med = float(np.median(known)) if known else 5.0
    for p in site.pipes.values():
        if p.U is None or not math.isfinite(p.U):
            p.U = med


def present_surveys(p):
    """Surveys of pipe p that read its present state, keyed by campaign ('crew' for the crew's)."""
    if p.crew is not None and 'U' in p.crew and (p.need > 0 or not p.valid or p.crew.get('replaces')):
        return {'crew': p.crew}
    if p.need > 0 or not p.valid:
        return {}
    d = {s['date']: s for s in p.valid}
    if p.crew is not None and 'U' in p.crew:
        d['crew'] = p.crew
    return d


def joint_pairs(site):
    """Weighted least squares for ln Uo of both pipes of each pair (bores as laid): the Uo fitted to each present
    survey, and at every survey of both pipes in their present state the equality of the two pressure drops."""
    groups = []
    for name, ps in site.lines.items():
        if len(ps) != 2 or any(p.bore_changed for p in ps):
            continue
        pa, pb = ps
        sa, sb = present_surveys(pa), present_surveys(pb)
        if not sa or not sb or pa.U is None or pb.U is None:
            continue
        if any('sig' not in s or not math.isfinite(s.get('sig', float('nan'))) for s in list(sa.values()) + list(sb.values())):
            continue
        bal = []
        for key in sorted(set(sa) & set(sb)):
            bal.append((sa[key]['m'], sb[key]['m'], sa[key]['Tin'], sa[key]['Ta'], SIG_M, SIG_M))
        for s_one, other, a_is in ((sa.get('crew'), sb, True), (sb.get('crew'), sa, False)):
            if s_one is None or 'crew' in other or not math.isfinite(s_one['line_flow']):
                continue
            m1, m2 = s_one['m'], s_one['line_flow'] - s_one['m']
            if not (m2 > 0.05 * s_one['line_flow']):
                continue
            s2 = SIG_M * math.hypot(s_one['line_flow'], m1) / m2
            if a_is:
                bal.append((m1, m2, s_one['Tin'], s_one['Ta'], SIG_M, s2))
            else:
                bal.append((m2, m1, s_one['Tin'], s_one['Ta'], s2, SIG_M))
        if not bal:
            continue
        ha = [(math.log(s['U']), s['sig']) for s in sa.values()]
        hb = [(math.log(s['U']), s['sig']) for s in sb.values()]
        groups.append([pa, pb, ha, hb, bal, np.array([math.log(pa.U), math.log(pb.U)])])
    if not groups:
        return
    d = 1e-3
    for it in range(3):
        cl = []
        for (pa, pb, ha, hb, bal, x) in groups:
            UA, UB = math.exp(x[0]), math.exp(x[1])
            for (ma, mb, ti, ta, sa_, sb_) in bal:
                cl.append(pa.cases(np.array([ma, ma, ma * (1 + d)]), ti, ta, U=np.array([UA, UA * math.exp(d), UA]), D=pa.D))
                cl.append(pb.cases(np.array([mb, mb, mb * (1 + d)]), ti, ta, U=np.array([UB, UB * math.exp(d), UB]), D=pb.D))
        _, dp = integrate(concat_cases(cl), N=40, newton=3)
        ldp = np.log(dp).reshape(-1, 3)
        pos = 0
        for gr in groups:
            pa, pb, ha, hb, bal, x = gr
            rows, rhs, w = [], [], []
            for v, s in ha:
                rows.append([1.0, 0.0]); rhs.append(v - x[0]); w.append(1.0 / max(s, 1e-6) ** 2)
            for v, s in hb:
                rows.append([0.0, 1.0]); rhs.append(v - x[1]); w.append(1.0 / max(s, 1e-6) ** 2)
            for (ma, mb, ti, ta, sa_, sb_) in bal:
                A_, B_ = ldp[pos], ldp[pos + 1]
                pos += 2
                i0 = A_[0] - B_[0]
                ga = (A_[1] - A_[0]) / d
                gb = -(B_[1] - B_[0]) / d
                sig = math.hypot((A_[2] - A_[0]) / d * sa_, (B_[2] - B_[0]) / d * sb_) + 1e-5
                rows.append([ga, gb]); rhs.append(-i0); w.append(1.0 / sig ** 2)
            A = np.array(rows); W = np.array(w); r = np.array(rhs)
            try:
                dx = np.linalg.solve(A.T @ (W[:, None] * A), A.T @ (W * r))
            except np.linalg.LinAlgError:
                continue
            gr[5] = x + np.clip(dx, -0.2, 0.2)
    for (pa, pb, ha, hb, bal, x) in groups:
        if np.all(np.isfinite(x)):
            pa.U, pb.U = math.exp(x[0]), math.exp(x[1])


# ----------------------------------------------------------------------------------------------------------------
# records
# ----------------------------------------------------------------------------------------------------------------

def logistic(u):
    return 1.0 / (1.0 + np.exp(-u))


class PairSet:
    """Parameters of a set of (pair line, record) items; g(u) is evaluated for one or more divisions per item."""

    def __init__(self, items):
        # items: list of (pa, pb, M, Tin, Ta)
        def arr(fn):
            return np.array([fn(it) for it in items], float)
        self.n = len(items)
        self.A = {n_: arr(lambda it, n_=n_: getattr(it[0].oil, n_)) for n_ in ('a1', 'B', 'rho', 'cp', 'k')}
        self.L = arr(lambda it: it[0].L)
        self.DA = arr(lambda it: it[0].D)
        self.DB = arr(lambda it: it[1].D)
        self.UA = arr(lambda it: it[0].U)
        self.UB = arr(lambda it: it[1].U)
        self.M = arr(lambda it: it[2])
        self.Tin = arr(lambda it: it[3])
        self.Ta = arr(lambda it: it[4])

    def evaluate(self, sel, u, N, newton, full=False):
        """sel: item index per evaluation; u: division per evaluation.  Returns g (and the pipe results)."""
        sel = np.asarray(sel, int)
        u = np.asarray(u, float)
        f = logistic(u)
        M = self.M[sel]
        kw = {n_: np.concatenate([v[sel], v[sel]]) for n_, v in self.A.items()}
        c = Cases(D=np.concatenate([self.DA[sel], self.DB[sel]]), L=np.concatenate([self.L[sel], self.L[sel]]),
                  m=np.concatenate([f * M, (1.0 - f) * M]), U=np.concatenate([self.UA[sel], self.UB[sel]]),
                  Tin=np.concatenate([self.Tin[sel], self.Tin[sel]]), Ta=np.concatenate([self.Ta[sel], self.Ta[sel]]),
                  **kw)
        T, dp = integrate(c, N=N, newton=newton)
        n = sel.size
        a, b = dp[:n], dp[n:]
        g = (a - b) / (a + b)
        if full:
            return g, a, b, T[:n], T[n:]
        return g


UEND = 40.0          # virtual ends of the division: fraction 0 (g = -1) and fraction 1 (g = +1)


def exact_search(ps, i, u_from, direction, N, newton, umin=-14.0, umax=14.0, npts=400):
    """First crossing met when moving from u_from in direction (-1: towards fraction 0), on a fine exact grid."""
    if direction < 0:
        uu = np.linspace(u_from, umin, npts)
    else:
        uu = np.linspace(u_from, umax, npts)
    g = ps.evaluate(np.full(npts, i), uu, N, newton)
    for j in range(1, npts):
        if direction < 0 and g[j] <= 0 < g[j - 1]:
            return (uu[j], uu[j - 1], g[j], g[j - 1])
        if direction > 0 and g[j] >= 0 > g[j - 1]:
            return (uu[j - 1], uu[j], g[j - 1], g[j])
    if direction < 0:
        return (-UEND, uu[-1], -1.0, g[-1])
    return (uu[-1], UEND, g[-1], 1.0)


def refine(ps, items, brackets, N, newton, dirs, iters=60):
    """Root of g in each bracket (u_lo, u_hi, g_lo, g_hi), g_lo <= 0 <= g_hi, by the Illinois method.  Ends taken
    from the scan are confirmed with the exact g first; where they are not, an exact search finds the crossing."""
    items = np.asarray(items, int)
    n = items.size
    lo = np.array([b[0] for b in brackets], float)
    hi = np.array([b[1] for b in brackets], float)
    glo = np.array([b[2] for b in brackets], float)
    ghi = np.array([b[3] for b in brackets], float)
    # confirm the ends (virtual ends have known signs)
    vl = np.abs(lo) < UEND - 1
    vh = np.abs(hi) < UEND - 1
    sel = np.concatenate([items[vl], items[vh]])
    if sel.size:
        g = ps.evaluate(sel, np.concatenate([lo[vl], hi[vh]]), N, newton)
        glo[vl] = g[:vl.sum()]
        ghi[vh] = g[vl.sum():]
    for j in range(n):
        if glo[j] <= 0 <= ghi[j]:
            continue
        # moving down (dir < 0) the search started at hi; moving up it started at lo
        if dirs[j] < 0:
            lo[j], hi[j], glo[j], ghi[j] = exact_search(ps, items[j], hi[j], -1, N, newton)
        else:
            lo[j], hi[j], glo[j], ghi[j] = exact_search(ps, items[j], lo[j], +1, N, newton)
    # the virtual ends are replaced by far finite points (g there has the sign of the end)
    lo = np.where(lo < -UEND + 1, -16.0, lo)
    hi = np.where(hi > UEND - 1, 16.0, hi)
    side = np.zeros(n)
    x = 0.5 * (lo + hi)
    done = (hi - lo) < 1e-12
    for it in range(iters):
        den = ghi - glo
        xn = (lo * ghi - hi * glo) / np.where(den == 0, 1.0, den)
        xn = np.where((xn <= lo) | (xn >= hi) | ~np.isfinite(xn), 0.5 * (lo + hi), xn)
        x = np.where(done, x, xn)
        act = np.where(~done)[0]
        if act.size == 0:
            break
        gx = np.zeros(n)
        gx[act] = ps.evaluate(items[act], x[act], N, newton)
        upd = ~done
        pos = upd & (gx > 0)
        neg = upd & (gx <= 0)
        glo = np.where(pos & (side == 1), glo * 0.5, glo)
        ghi = np.where(neg & (side == -1), ghi * 0.5, ghi)
        hi = np.where(pos, x, hi)
        ghi = np.where(pos, gx, ghi)
        lo = np.where(neg, x, lo)
        glo = np.where(neg, gx, glo)
        side = np.where(pos, 1, np.where(neg, -1, side))
        done = done | (upd & ((np.abs(gx) < 1e-13) | ((hi - lo) < 1e-11)))
    return x


def solve_pairs(site, pair_lines, out):
    """pair_lines: list of (pa, pb, idx, M, Tin, Ta) with records in hour order.  Fills out[idx] = (dp, Tout)."""
    if not pair_lines:
        return
    UG = np.linspace(-9.0, 9.0, 145)        # scan of the division, in logit of the fraction to pipe A
    NSCAN, NWSCAN = 12, 1
    NTR, NWTR = 20, 2
    PROBE = np.array([5e-4, 1.5e-3, 5e-3, 1.5e-2, 4e-2])
    items = []
    start = []
    for (pa, pb, idx, M, Tin, Ta) in pair_lines:
        start.append(len(items))
        for j in range(len(idx)):
            items.append((pa, pb, M[j], Tin[j], Ta[j]))
    ps = PairSet(items)
    nit = len(items)
    # scan of every record
    sel = np.repeat(np.arange(nit), UG.size)
    G = ps.evaluate(sel, np.tile(UG, nit), NSCAN, NWSCAN).reshape(nit, UG.size)
    nl = len(pair_lines)
    U = np.zeros(nit)
    # record 0 of each line: the only division (TS-2 4.3)
    br = []
    it0 = [start[li] for li in range(nl)]
    for i in it0:
        uu = np.concatenate([[-UEND], UG, [UEND]])
        gg = np.concatenate([[-1.0], G[i], [1.0]])
        st = np.where((gg[:-1] <= 0) & (gg[1:] > 0))[0]
        un = np.where((gg[:-1] > 0) & (gg[1:] <= 0))[0]
        j = st[0]
        if len(st) > 1:       # should not happen at a run's opening; keep the stable division furthest from others
            best = -1.0
            for c in st:
                dist = np.min(np.abs(uu[un] - uu[c])) if un.size else 1e9
                if dist > best:
                    best, j = dist, c
        br.append((uu[j], uu[j + 1], gg[j], gg[j + 1]))
    U[it0] = refine(ps, it0, br, NTR, NWTR, dirs=[1] * nl)
    # following records (TS-2 4.2)
    Kmax = max(len(pl[2]) for pl in pair_lines)
    offs = np.concatenate([[0.0], -PROBE, PROBE])
    npb = PROBE.size
    for k in range(1, Kmax):
        act = [li for li in range(nl) if k < len(pair_lines[li][2])]
        if not act:
            break
        cur = np.array([start[li] + k for li in act])
        u0 = U[cur - 1]
        gp = ps.evaluate(np.repeat(cur, offs.size), (u0[:, None] + offs[None, :]).ravel(), NTR, NWTR)
        gp = gp.reshape(len(act), offs.size)
        brs, dirs, todo = [], [], []
        for a, i in enumerate(cur):
            g0 = gp[a, 0]
            if g0 == 0.0:
                U[i] = u0[a]
                continue
            gs = G[i]
            if g0 > 0:        # pipe A has the higher drop: oil moves from A to B, the fraction to A falls
                pts_u = list(u0[a] - PROBE) + list(UG[UG < u0[a] - PROBE[-1]][::-1]) + [-UEND]
                pts_g = list(gp[a, 1:1 + npb]) + list(gs[UG < u0[a] - PROBE[-1]][::-1]) + [-1.0]
                pu, pg = u0[a], g0
                for uu_, gg_ in zip(pts_u, pts_g):
                    if gg_ <= 0:
                        brs.append((uu_, pu, gg_, pg))
                        break
                    pu, pg = uu_, gg_
                dirs.append(-1)
            else:
                pts_u = list(u0[a] + PROBE) + list(UG[UG > u0[a] + PROBE[-1]]) + [UEND]
                pts_g = list(gp[a, 1 + npb:]) + list(gs[UG > u0[a] + PROBE[-1]]) + [1.0]
                pu, pg = u0[a], g0
                for uu_, gg_ in zip(pts_u, pts_g):
                    if gg_ >= 0:
                        brs.append((pu, uu_, pg, gg_))
                        break
                    pu, pg = uu_, gg_
                dirs.append(1)
            todo.append(i)
        if todo:
            U[todo] = refine(ps, todo, brs, NTR, NWTR, dirs)
    # results at the divisions found
    g, a, b, TA, TB = ps.evaluate(np.arange(nit), U, 48, 3, full=True)
    f = logistic(U)
    dp = 0.5 * (a + b)
    To = f * TA + (1.0 - f) * TB
    for li, (pa, pb, idx, M, Tin, Ta) in enumerate(pair_lines):
        for j, ri in enumerate(idx):
            out[ri] = (dp[start[li] + j], To[start[li] + j])
    site.pair_divisions = {pl[0].line: f[start[li]:start[li] + len(pl[2])] for li, pl in enumerate(pair_lines)}


def compute(site):
    recs = site.records
    nrec = len(recs)
    out = [None] * nrec
    by_line = {}
    for i, r in enumerate(recs):
        by_line.setdefault(norm_pipe(r.get('line')), []).append(i)
    singles = []
    pair_lines = []
    for ln, idx in by_line.items():
        ps = site.lines.get(ln)
        if ps is None:
            continue
        idx.sort(key=lambda i: (safe(recs[i].get('hour'), 0.0), i))
        M = np.array([safe(recs[i].get('flow_t_h'), 0.0) for i in idx]) / 3.6
        Tin = np.array([safe(recs[i].get('t_in_C'), 80.0) for i in idx])
        Ta = np.array([safe(recs[i].get('t_amb_C'), 10.0) for i in idx])
        M = np.maximum(M, 1e-6)
        if len(ps) == 1:
            singles.append((ps[0], idx, M, Tin, Ta))
        else:
            pair_lines.append((ps[0], ps[1], idx, M, Tin, Ta))
    if singles:
        cs = concat_cases([p.cases(M, Tin, Ta) for (p, idx, M, Tin, Ta) in singles])
        T, dp = integrate(cs, N=48, newton=3)
        pos = 0
        for (p, idx, M, Tin, Ta) in singles:
            for j, ri in enumerate(idx):
                out[ri] = (dp[pos + j], T[pos + j])
            pos += len(idx)
    try:
        solve_pairs(site, pair_lines, out)
    except Exception as e:     # never leave a pair without an answer: equal division
        sys.stderr.write(f'pair solution failed: {e!r}\n')
        for (pa, pb, idx, M, Tin, Ta) in pair_lines:
            for j, ri in enumerate(idx):
                if out[ri] is None:
                    T1, d1 = integrate(pa.cases(M[j] / 2, Tin[j], Ta[j]), N=32)
                    T2, d2 = integrate(pb.cases(M[j] / 2, Tin[j], Ta[j]), N=32)
                    out[ri] = (0.5 * (d1[0] + d2[0]), 0.5 * (T1[0] + T2[0]))
    return out


def main():
    if len(sys.argv) < 3:
        sys.stderr.write('usage: python3 lines.py PACKAGE_DIR OUT_CSV\n')
        return 0
    pkg, out_csv = sys.argv[1], sys.argv[2]
    site = None
    results = None
    try:
        site = Site(pkg)
        order = []
        try:
            order = analyse_surveys(site)
        except Exception as e:
            sys.stderr.write(f'survey analysis failed: {e!r}\n')
        crew = {}
        try:
            crew = call_crew(site, order)
        except Exception as e:
            sys.stderr.write(f'crew order failed: {e!r}\n')
        try:
            settle_state(site, crew)
        except Exception as e:
            sys.stderr.write(f'state failed: {e!r}\n')
            for p in site.pipes.values():
                if p.U is None or not math.isfinite(p.U):
                    p.U = p.valid[-1]['U'] if p.valid else 5.0
        if os.environ.get('LINES_DEBUG'):
            for p in site.pipes.values():
                sys.stderr.write(f'{p.name} U={p.U:.4f} D={p.D*1000:.3f} need={p.need:.1f} {p.need_kind} '
                                 f'crew={"y" if p.crew else "n"}\n')
            sys.stderr.write('order: ' + ' '.join(p.name for p in order) + '\n')
        results = compute(site)
    except Exception as e:
        sys.stderr.write(f'calculation failed: {e!r}\n')
    # write
    try:
        recs = site.records if site is not None else read_csv(os.path.join(pkg, 'records.csv'))
    except Exception:
        recs = []
    with open(out_csv, 'w', newline='') as fh:
        fh.write('record,dp_kPa,t_out_C\n')
        for i, r in enumerate(recs):
            dp, T = (None, None)
            if results is not None and results[i] is not None:
                dp, T = results[i]
            dp = safe(dp, 0.0) / 1000.0
            T = safe(T, safe(r.get('t_in_C'), 0.0))
            fh.write(f'{r.get("record", "")},{dp:.5f},{T:.4f}\n')
    return 0


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        sys.stderr.write(f'error: {e!r}\n')
    sys.exit(0)
