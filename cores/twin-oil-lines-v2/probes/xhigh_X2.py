#!/usr/bin/env python3
"""Heated fuel oil lines to terminal standard TS-2.

    python3 lines.py PACKAGE_DIR OUT_CSV

For every row of the package's records.csv, writes the pressure drop between the line's manifolds (kPa)
and the temperature of the oil leaving its outlet manifold (C).

Outline
  * TS-2 section 3 is integrated along each pipe in s = (x/L)^(1/3), which removes the entrance
    singularity of the Graetz term, with the bulk temperature carried as ln(Tb - Ta) so that the
    integration stays stable however quickly the oil cools.  The wall temperature is solved at each
    point by Newton's method; ln(viscosity) comes from a fine table of ASTM D341.
  * Uo of each pipe (TS-2 5.2) is fitted to its heat-loss surveys.  A survey taken before a renewal or
    repair of the covering does not count (5.3).  A covering whose surveys differ by more than the
    reading tolerances of 5.4 allow has changed while standing.  Pipes with no valid survey, then
    pipes whose covering is changing, are surveyed again by the crew (one order per run, at most
    survey_allowance pipes).  Spare places in the order go to the pipes that look least certain.
  * A pair (section 4) has the same pressure drop in both pipes.  A heated viscous line has an S-shaped
    pressure-drop/flow characteristic, so a pair can have several steady splits of its flow.  All
    splits are found for each record, and the line is followed through its run of records in time
    order: at each reading it settles in the stable split whose basin holds the split it had at the
    previous reading.
"""
import csv
import json
import math
import os
import re
import subprocess
import sys

import numpy as np

C1 = 3.66 ** 3 + 0.7 ** 3
NSTEP = 14          # RK4 steps along a pipe
TW_ITER = 2         # Newton steps on the wall temperature per stage
NOW = '9999-99-99'  # date given to the crew's readings


# ----------------------------------------------------------------------------------------------- input
def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows = []
        for r in csv.DictReader(f):
            rows.append({(k or '').strip(): (v or '').strip() for k, v in r.items()})
        return rows


def fnum(s):
    return float(str(s).strip().replace(',', '.')) if not isinstance(s, (int, float)) else float(s)


def norm_pipe(s):
    return re.sub(r'\s+', '', str(s)).upper()


def norm_date(s):
    s = str(s).strip()
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})', s)
    if m:
        return '%s-%02d-%02d' % (m.group(1), int(m.group(2)), int(m.group(3)))
    return s


class Oil:
    def __init__(self, r):
        self.name = r['oil'].strip()
        self.rho = fnum(r['density_kg_m3'])
        self.cp = fnum(r['cp_J_kgK'])
        self.k = fnum(r['k_W_mK'])
        n1, n2 = fnum(r['nu50_cSt']), fnum(r['nu100_cSt'])
        T1, T2 = 323.15, 373.15
        y1 = math.log10(math.log10(n1 + 0.7))
        y2 = math.log10(math.log10(n2 + 0.7))
        self.B = (y1 - y2) / (math.log10(T2) - math.log10(T1))
        self.A = y1 + self.B * math.log10(T1)


# ----------------------------------------------------------------------------------------- the physics
class ViscTable:
    """ln(dynamic viscosity, Pa s) of each oil on a uniform grid in deg C (linear interpolation)."""

    def __init__(self, oils, Tlo, Thi, dT=0.02):
        self.T0 = Tlo
        self.inv = 1.0 / dT
        self.NT = int(math.ceil((Thi - Tlo) / dT)) + 2
        Tg = Tlo + dT * np.arange(self.NT)
        tabs = []
        for o in oils:
            nu = 10.0 ** (10.0 ** (o.A - o.B * np.log10(Tg + 273.15))) - 0.7
            tabs.append(np.log(nu * 1e-6 * o.rho))
        self.tab = np.concatenate(tabs)
        self.dtab = np.concatenate([np.append(np.diff(t), 0.0) for t in tabs])

    def lnmu(self, T, off):
        u = (T - self.T0) * self.inv
        i = u.astype(np.int64)
        np.clip(i, 0, self.NT - 2, out=i)
        f = u - i
        j = i + off
        return self.tab[j] + f * self.dtab[j]

    def lnmu_d(self, T, off):
        u = (T - self.T0) * self.inv
        i = u.astype(np.int64)
        np.clip(i, 0, self.NT - 2, out=i)
        f = u - i
        j = i + off
        d = self.dtab[j]
        return self.tab[j] + f * d, d * self.inv


def pipe_solve(vt, g, m, Tin, Ta, U):
    """One pipe, TS-2 section 3.  g: dict of per-case arrays off, D, L, rho, cp, k.
    m kg/s, temperatures C, U W/m2K (referred to the bore).  Returns outlet Tb (C) and dp (Pa)."""
    off, D, L, rho, cp, k = g['off'], g['D'], g['L'], g['rho'], g['cp'], g['k']
    gzc = 4.0 * m * cp / (math.pi * k)                 # Gz * x
    a = math.pi * D * U / (m * cp)                       # 1/m
    dpc = 128.0 * m / (math.pi * rho * D ** 4)           # -dp/dx = dpc * sqrt(mu_b mu_w)
    kD = k / D
    dTin = Tin - Ta
    hs = 1.0 / NSTEP
    th = np.zeros_like(m)          # ln((Tb - Ta) / (Tin - Ta))
    p = np.zeros_like(m)
    r = np.ones_like(m)            # (Tw - Ta) / (Tb - Ta) = h / (h + U)

    def h0_at(s):
        gz = gzc / (L * s ** 3)
        c = 1.077 * np.cbrt(gz) - 0.7
        return np.cbrt(C1 + c * c * c) * kD

    def stage(s, th, r, h0):
        dTb = dTin * np.exp(th)
        Tb = Ta + dTb
        lb = vt.lnmu(Tb, off)
        dxds = 3.0 * L * s * s
        if h0 is None:              # x = 0: h is infinite, the wall is at the bulk temperature
            r = np.ones_like(th)
            lw = lb
        else:
            Tw = Ta + r * dTb
            for _ in range(TW_ITER):
                lw, sw = vt.lnmu_d(Tw, off)
                h = h0 * np.exp(0.14 * (lb - lw))
                rr = h / (h + U)
                gres = Tw - Ta - rr * dTb
                gp = 1.0 + dTb * rr * (1.0 - rr) * 0.14 * sw
                Tw = Tw - gres / gp
            lw = vt.lnmu(Tw, off)
            pos = dTb > 0
            r = np.where(pos, (Tw - Ta) / np.where(pos, dTb, 1.0), 1.0)
        return -a * r * dxds, dpc * np.exp(0.5 * (lb + lw)) * dxds, r

    h0n = None
    for i in range(NSTEP):
        s0 = i * hs
        sm = s0 + 0.5 * hs
        s1 = s0 + hs
        h0m = h0_at(sm)
        h01 = h0_at(s1)
        k1, p1, r = stage(s0, th, r, h0n)
        k2, p2, r = stage(sm, th + 0.5 * hs * k1, r, h0m)
        k3, p3, r = stage(sm, th + 0.5 * hs * k2, r, h0m)
        k4, p4, r = stage(s1, th + hs * k3, r, h01)
        th = th + hs / 6.0 * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        p = p + hs / 6.0 * (p1 + 2.0 * p2 + 2.0 * p3 + p4)
        h0n = h01
    return Ta + dTin * np.exp(th), p


def take(g, idx):
    return {kk: v[idx] for kk, v in g.items()}


def calibrate(vt, g, m, Tin, Tout, Ta):
    """Uo for which section 3 gives the outlet temperature read (TS-2 5.2): bisection on log10 Uo."""
    lo = np.full(m.shape, -4.0)
    hi = np.full(m.shape, 4.0)
    for _ in range(56):
        mid = 0.5 * (lo + hi)
        T, _ = pipe_solve(vt, g, m, Tin, Ta, 10.0 ** mid)
        hot = T > Tout
        lo = np.where(hot, mid, lo)
        hi = np.where(hot, hi, mid)
    return 10.0 ** (0.5 * (lo + hi))


def calibrate_with_bounds(vt, g, m, Tin, Tout, Ta):
    """Uo with the bound on its error implied by the reading tolerances of TS-2 5.4, and a sigma."""
    n = len(m)
    if n == 0:
        z = np.zeros(0)
        return z, z, z
    cat = lambda a: np.concatenate([a] * 5)
    G5 = {kk: cat(v) for kk, v in g.items()}
    M = np.concatenate([m, m * 1.002, m, m, m])
    TI = np.concatenate([Tin, Tin, Tin + 0.02, Tin, Tin])
    TO = np.concatenate([Tout, Tout, Tout, Tout + 0.02, Tout])
    TA = np.concatenate([Ta, Ta, Ta, Ta, Ta + 0.1])
    U = calibrate(vt, G5, M, TI, TO, TA)
    U0 = U[:n]
    d = [np.abs(U[n * j:n * (j + 1)] - U0) for j in range(1, 5)]
    bound = d[0] + d[1] + d[2] + d[3]
    sig = np.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2 + d[3] ** 2) / math.sqrt(3.0)
    return U0, np.maximum(bound, 1e-9), np.maximum(sig, 1e-9)


# ------------------------------------------------------------------------------------------------ pairs
def pair_eval(vt, g, phi, m, Tin, Ta, UA, UB):
    n = len(phi)
    G2 = {kk: np.concatenate([v, v]) for kk, v in g.items()}
    T, p = pipe_solve(vt, G2, np.concatenate([phi * m, (1.0 - phi) * m]), np.concatenate([Tin, Tin]),
                      np.concatenate([Ta, Ta]), np.concatenate([UA, UB]))
    return p[:n] - p[n:], T[:n], p[:n], T[n:], p[n:]


def find_splits(vt, g, m, Tin, Ta, UA, UB, G=72):
    """All solutions phi = mA / m of dpA(phi m) = dpB((1-phi) m) for each case.
    Returns a list (per case) of [phi, stable] sorted by phi."""
    N = len(m)
    t = np.linspace(0.0, 1.0, G)
    grid = 0.5 - 0.5 * np.cos(np.pi * t)           # dense towards a starved pipe
    grid[0], grid[-1] = 1e-6, 1.0 - 1e-6
    cells = []                                      # (case, lo, hi, flo, fhi)
    # coarse scan, in chunks to bound memory
    CH = max(1, 120000 // G)
    F = np.empty((N, G))
    for c0 in range(0, N, CH):
        c1 = min(N, c0 + CH)
        I = np.repeat(np.arange(c0, c1), G)
        PH = np.tile(grid, c1 - c0)
        f = pair_eval(vt, take(g, I), PH, m[I], Tin[I], Ta[I], UA[I], UB[I])[0]
        F[c0:c1] = f.reshape(c1 - c0, G)
    # sign changes, and cells where |f| dips towards zero without a sign change (two close roots?)
    fine_req = []
    for i in range(N):
        f = F[i]
        s = np.sign(f)
        for j in np.nonzero(s[:-1] * s[1:] <= 0)[0]:
            if f[j] != f[j + 1]:
                cells.append((i, grid[j], grid[j + 1], f[j], f[j + 1]))
        af = np.abs(f)
        for j in range(1, G - 1):
            if s[j - 1] == s[j] == s[j + 1] and af[j] < af[j - 1] and af[j] < af[j + 1]:
                fine_req.append((i, grid[j - 1], grid[j + 1]))
    # look closely at the dips (two levels)
    for level in range(2):
        if not fine_req:
            break
        K = 24
        I = np.repeat(np.array([q[0] for q in fine_req]), K)
        lo = np.array([q[1] for q in fine_req])
        hi = np.array([q[2] for q in fine_req])
        PH = (lo[:, None] + (hi - lo)[:, None] * np.linspace(0.0, 1.0, K)[None, :]).ravel()
        f = pair_eval(vt, take(g, I), PH, m[I], Tin[I], Ta[I], UA[I], UB[I])[0].reshape(-1, K)
        PH = PH.reshape(-1, K)
        nxt = []
        for q in range(len(fine_req)):
            i = fine_req[q][0]
            ff = f[q]
            s = np.sign(ff)
            ch = np.nonzero(s[:-1] * s[1:] <= 0)[0]
            for j in ch:
                if ff[j] != ff[j + 1]:
                    cells.append((i, PH[q, j], PH[q, j + 1], ff[j], ff[j + 1]))
            if len(ch) == 0 and level == 0:
                af = np.abs(ff)
                if af.min() < 0.25 * (ff.max() - ff.min()):
                    for j in range(1, K - 1):
                        if af[j] < af[j - 1] and af[j] < af[j + 1]:
                            nxt.append((i, PH[q, j - 1], PH[q, j + 1]))
        fine_req = nxt
    # refine every bracket (Illinois)
    if not cells:
        return [[] for _ in range(N)]
    ci = np.array([c[0] for c in cells])
    a = np.array([c[1] for c in cells])
    b = np.array([c[2] for c in cells])
    fa = np.array([c[3] for c in cells])
    fb = np.array([c[4] for c in cells])
    stable = fb > fa
    gi = take(g, ci)
    mi, Ti, Tai, UAi, UBi = m[ci], Tin[ci], Ta[ci], UA[ci], UB[ci]
    side = np.zeros(len(ci))
    for _ in range(40):
        den = fb - fa
        c = np.where(den != 0, b - fb * (b - a) / np.where(den != 0, den, 1.0), 0.5 * (a + b))
        bad = ~((c > np.minimum(a, b)) & (c < np.maximum(a, b)))
        c = np.where(bad, 0.5 * (a + b), c)
        fc = pair_eval(vt, gi, c, mi, Ti, Tai, UAi, UBi)[0]
        left = np.sign(fc) == np.sign(fa)
        # replace a when fc has the sign of fa, else b; Illinois halving of the retained end
        a_new = np.where(left, c, a)
        fa_new = np.where(left, fc, np.where(side == -1, fa * 0.5, fa))
        b_new = np.where(left, b, c)
        fb_new = np.where(left, np.where(side == 1, fb * 0.5, fb), fc)
        side = np.where(left, 1, -1)
        a, fa, b, fb = a_new, fa_new, b_new, fb_new
        if np.all(np.abs(b - a) < 1e-12):
            break
    root = c
    out = [[] for _ in range(N)]
    for q in range(len(ci)):
        out[ci[q]].append([root[q], bool(stable[q])])
    for i in range(N):
        rs = sorted(out[i])
        merged = []
        for r in rs:                        # the same root bracketed twice (coarse and fine scans)
            if merged and abs(r[0] - merged[-1][0]) < 1e-7 and r[1] == merged[-1][1]:
                continue
            merged.append(r)
        out[i] = merged
    return out


def settle(roots, phi_prev):
    """The stable split the line settles in from phi_prev: follow the sign of dpB - dpA."""
    stab = [r[0] for r in roots if r[1]]
    if not stab:
        return None
    if len(stab) == 1 or phi_prev is None:
        return stab[0] if len(stab) == 1 else None
    uns = [r[0] for r in roots if not r[1]]
    best = None
    for s in stab:
        lo = max([u for u in uns if u < s], default=0.0)
        hi = min([u for u in uns if u > s], default=1.0)
        if lo <= phi_prev <= hi:
            return s
        dist = min(abs(phi_prev - lo), abs(phi_prev - hi), abs(phi_prev - s))
        if best is None or dist < best[0]:
            best = (dist, s)
    return best[1]


# --------------------------------------------------------------------------------------- covering work
COVER_RE = re.compile(r'\b(re-?)?(cover|lag|insul|clad|jacket|wrap|sheath|mattress)', re.I)
NOWORK_RE = re.compile(r'(inspect|check|examin|survey|photograph|measur|no work|no action|not done|'
                       r'defer|postpon|cancel|plann|schedul|order|request|quot|report|await)', re.I)


def classify_job(job):
    """2: the covering was renewed or repaired; 1: the job may have disturbed it; 0: not the covering."""
    j = job or ''
    if not COVER_RE.search(j) and not re.search(r'\bun-?cover', j, re.I):
        return 0
    if re.search(r'\bun-?cover', j, re.I) or NOWORK_RE.search(j):
        return 1
    return 2


# ----------------------------------------------------------------------------------------------- main
def main():
    pkg, out_csv = sys.argv[1], sys.argv[2]
    site = {}
    try:
        with open(os.path.join(pkg, 'site.json'), encoding='utf-8-sig') as f:
            site = json.load(f)
    except Exception:
        pass
    oils = {}
    for r in read_csv(os.path.join(pkg, 'oils.csv')):
        o = Oil(r)
        oils[o.name] = o
    lines = {}
    for r in read_csv(os.path.join(pkg, 'lines.csv')):
        lines[r['line'].strip().upper()] = dict(
            pipes=int(round(fnum(r['pipes']))), D=fnum(r['bore_mm']) / 1000.0, L=fnum(r['length_m']),
            oil=r['oil'].strip())
    surveys = read_csv(os.path.join(pkg, 'surveys.csv'))
    try:
        work = read_csv(os.path.join(pkg, 'work_log.csv'))
    except Exception:
        work = []
    records = read_csv(os.path.join(pkg, 'records.csv'))

    oil_names = list(oils)
    for l in lines.values():
        if l['oil'] not in oils:            # tolerate a case/spacing difference in the oil name
            for nm in oil_names:
                if nm.replace(' ', '').upper() == l['oil'].replace(' ', '').upper():
                    l['oil'] = nm
    pipes_of = {}
    for ln, l in lines.items():
        pipes_of[ln] = [ln + '-A'] if l['pipes'] == 1 else [ln + '-A', ln + '-B']
    all_pipes = [p for ln in lines for p in pipes_of[ln]]

    def line_of(pipe):
        p = norm_pipe(pipe)
        if p in lines:
            return p
        mm = re.match(r'^(.*)-([A-Z])$', p)
        return mm.group(1) if mm else p

    # temperature range for the viscosity table
    temps = []
    for r in records:
        temps += [fnum(r['t_in_C']), fnum(r['t_amb_C'])]
    for s in surveys:
        temps += [fnum(s['t_in_C']), fnum(s['t_out_C']), fnum(s['t_amb_C'])]
    Tlo = min(temps) - 15.0
    Thi = max(temps) + 15.0
    vt = ViscTable([oils[n] for n in oil_names], Tlo, Thi)
    off_of = {n: i * vt.NT for i, n in enumerate(oil_names)}

    def geom(line_names):
        Ls = [lines[x] for x in line_names]
        os_ = [oils[x['oil']] for x in Ls]
        return dict(off=np.array([off_of[x['oil']] for x in Ls], dtype=np.int64),
                    D=np.array([x['D'] for x in Ls], float), L=np.array([x['L'] for x in Ls], float),
                    rho=np.array([o.rho for o in os_], float), cp=np.array([o.cp for o in os_], float),
                    k=np.array([o.k for o in os_], float))

    def fit(rows):
        lns = [line_of(s['pipe']) for s in rows]
        g = geom(lns)
        m = np.array([fnum(s['flow_t_h']) / 3.6 for s in rows])
        Tin = np.array([fnum(s['t_in_C']) for s in rows])
        Tout = np.array([fnum(s['t_out_C']) for s in rows])
        Ta = np.array([fnum(s['t_amb_C']) for s in rows])
        return calibrate_with_bounds(vt, g, m, Tin, Tout, Ta)

    # ---- the surveys on file
    surveys = [s for s in surveys if norm_pipe(s.get('pipe', '')) in set(all_pipes)]
    for s in surveys:
        s['pipe'] = norm_pipe(s['pipe'])
        s['date'] = norm_date(s['date'])
    U_s, B_s, S_s = fit(surveys)
    by_pipe = {p: [] for p in all_pipes}
    for s, u, b, sg in zip(surveys, U_s, B_s, S_s):
        by_pipe[s['pipe']].append((s['date'], float(u), float(b), float(sg)))

    # ---- the work log: last renewal/repair of each covering, and doubtful jobs
    last_cover = {}
    doubtful = {}
    for w in work:
        cls = classify_job(w.get('job', ''))
        if cls == 0:
            continue
        p = norm_pipe(w.get('pipe', ''))
        targets = [p] if p in by_pipe else pipes_of.get(p, [])
        d = norm_date(w.get('date', ''))
        for t in targets:
            if cls == 2:
                last_cover[t] = max(last_cover.get(t, ''), d)
            else:
                doubtful[t] = max(doubtful.get(t, ''), d)

    def wmean(v):
        w = np.array([1.0 / x[3] ** 2 for x in v])
        u = np.array([x[1] for x in v])
        return float((w * u).sum() / w.sum())

    def spread(v):
        """largest difference of two readings, over what the reading tolerances allow."""
        r = 0.0
        for i in range(len(v)):
            for j in range(i):
                r = max(r, abs(v[i][1] - v[j][1]) / (v[i][2] + v[j][2]))
        return r

    valid = {}
    must1, must2, rank = [], [], []
    nrec_line = {}
    for r in records:
        ln = r['line'].strip().upper()
        nrec_line[ln] = nrec_line.get(ln, 0) + 1
    for p in all_pipes:
        lst = sorted(by_pipe[p])
        lw = last_cover.get(p, '')
        v = [x for x in lst if x[0] > lw]
        valid[p] = v
        weight = nrec_line.get(line_of(p), 0)
        if not v:
            must1.append((weight, p))
            continue
        sp = spread(v) if len(v) >= 2 else 0.0
        if sp > 1.0:
            must2.append((sp, p))
            continue
        score = sp
        if p in doubtful and doubtful[p] >= v[-1][0]:
            score = max(score, 0.9)
        if len(v) == 1:
            score = max(score, 0.5)
        if lst and lw and lw == lst[-1][0]:
            score = max(score, 0.95)
        rank.append((score, weight, p))
    must1.sort(key=lambda t: -t[0])
    must2.sort(key=lambda t: -t[0])
    rank.sort(key=lambda t: (-t[0], -t[1]))
    order = [p for _, p in must1] + [p for _, p in must2] + [p for _, _, p in rank]
    try:
        allowance = int(site.get('survey_allowance', 0))
    except Exception:
        allowance = 0
    order = order[:max(0, allowance)]

    # ---- the survey crew: one order for this package
    crew = {}
    if order:
        crew_rows = order_survey(pkg, order)
        crew_rows = [c for c in crew_rows if norm_pipe(c.get('pipe', '')) in by_pipe]
        for c in crew_rows:
            c['pipe'] = norm_pipe(c['pipe'])
        if crew_rows:
            try:
                Uc, Bc, Sc = fit(crew_rows)
                for c, u, b, sg in zip(crew_rows, Uc, Bc, Sc):
                    if np.isfinite(u):
                        crew[c['pipe']] = (NOW, float(u), float(b), float(sg))
            except Exception:
                crew = {}

    # ---- Uo of each pipe for the records
    def trending(v):
        if len(v) < 2 or spread(v) <= 0.5:
            return False
        d = np.diff([x[1] for x in v])
        return bool(np.all(d > 0) or np.all(d < 0))

    Uo = {}
    for p in all_pipes:
        v = valid[p]
        c = crew.get(p)
        changing = (not v) or (len(v) >= 2 and spread(v) > 1.0) or trending(v)
        if c is not None:
            # the covering as it stands now; older readings are pooled with it only if they agree
            if changing or spread([c] + v) > 0.5 or trending(v + [c]):
                Uo[p] = c[1]
            else:
                Uo[p] = wmean(v + [c])
        elif v:
            Uo[p] = v[-1][1] if changing else wmean(v)
        else:
            lst = sorted(by_pipe[p])
            Uo[p] = lst[-1][1] if lst else 5.0

    # ---- the records
    N = len(records)
    rec_line = [r['line'].strip().upper() for r in records]
    m = np.array([fnum(r['flow_t_h']) / 3.6 for r in records])
    Tin = np.array([fnum(r['t_in_C']) for r in records])
    Ta = np.array([fnum(r['t_amb_C']) for r in records])
    hour = []
    for q, r in enumerate(records):
        try:
            hour.append(fnum(r.get('hour', q)))
        except Exception:
            hour.append(float(q))
    dp = np.zeros(N)
    To = np.zeros(N)

    single = np.array([i for i in range(N) if lines[rec_line[i]]['pipes'] == 1], dtype=np.int64)
    pair = np.array([i for i in range(N) if lines[rec_line[i]]['pipes'] != 1], dtype=np.int64)
    if len(single):
        g = geom([rec_line[i] for i in single])
        U = np.array([Uo[rec_line[i] + '-A'] for i in single])
        T, p = pipe_solve(vt, g, m[single], Tin[single], Ta[single], U)
        dp[single] = p / 1000.0
        To[single] = T
    if len(pair):
        g = geom([rec_line[i] for i in pair])
        UA = np.array([Uo[rec_line[i] + '-A'] for i in pair])
        UB = np.array([Uo[rec_line[i] + '-B'] for i in pair])
        mp, Tp, Tap = m[pair], Tin[pair], Ta[pair]
        roots = find_splits(vt, g, mp, Tp, Tap, UA, UB)
        # follow each line through its run of records in time order
        runs = {}
        for q, i in enumerate(pair):
            runs.setdefault(rec_line[i], []).append(q)
        phi = np.full(len(pair), 0.5)
        for ln, qs in runs.items():
            qs.sort(key=lambda q: (hour[pair[q]], q))
            prev = None
            for q in qs:
                st = [r[0] for r in roots[q] if r[1]]
                if not st:
                    ph = solve_one(vt, take(g, [q]), mp[q], Tp[q], Tap[q], UA[q], UB[q], prev)
                elif len(st) == 1:
                    ph = st[0]
                else:
                    if prev is None:
                        # no history before the run: take the line as having come down to this
                        # reading from a flow at which its split is unique
                        prev = come_down(vt, take(g, [q]), mp[q], Tp[q], Tap[q], UA[q], UB[q],
                                         max(mp[qq] for qq in qs))
                    ph = settle(roots[q], prev)
                    if ph is None:
                        ph = min(st, key=lambda s: abs(s - 0.5))
                phi[q] = ph
                prev = ph
        f, TA, pA, TB, pB = pair_eval(vt, g, phi, mp, Tp, Tap, UA, UB)
        dp[pair] = 0.5 * (pA + pB) / 1000.0
        To[pair] = phi * TA + (1.0 - phi) * TB

    with open(out_csv, 'w', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['record', 'dp_kPa', 't_out_C'])
        for i, r in enumerate(records):
            wr.writerow([r['record'], '%.4f' % dp[i], '%.4f' % To[i]])


def come_down(vt, g1, m, Tin, Ta, UA, UB, mmax):
    """Split reached when the flow is brought down to m from a flow with a single steady split."""
    one = lambda x: np.array([x], float)
    mhi = max(mmax, m) * 1.5
    phi = None
    for _ in range(10):
        rs = find_splits(vt, g1, one(mhi), one(Tin), one(Ta), one(UA), one(UB))[0]
        st = [r[0] for r in rs if r[1]]
        if len(st) == 1:
            phi = st[0]
            break
        mhi *= 2.0
    if phi is None:
        return 0.5
    K = 24
    ms = mhi * (m / mhi) ** (np.arange(1, K) / K)
    gK = {kk: np.repeat(v, K - 1) for kk, v in g1.items()}
    rr = find_splits(vt, gK, ms, np.full(K - 1, Tin), np.full(K - 1, Ta), np.full(K - 1, UA),
                     np.full(K - 1, UB))
    for rs in rr:
        s = settle(rs, phi)
        if s is not None:
            phi = s
    return phi


def solve_one(vt, g, m, Tin, Ta, UA, UB, prev):
    """Fallback for a pair whose scan found no stable split: bisection on the whole interval."""
    lo, hi = np.array([1e-9]), np.array([1.0 - 1e-9])
    M, TI, TA_, A_, B_ = (np.array([x]) for x in (m, Tin, Ta, UA, UB))
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        f = pair_eval(vt, g, mid, M, TI, TA_, A_, B_)[0]
        lo = np.where(f < 0, mid, lo)
        hi = np.where(f < 0, hi, mid)
    return float(0.5 * (lo + hi)[0])


def order_survey(pkg, pipes):
    """One order to the survey crew.  An order that is refused does not count, so a refused order is
    cut down and placed again; nothing else is retried."""
    target = os.path.abspath(pkg)
    tries = [list(pipes)]
    rows = []
    for attempt in range(4):
        if not tries:
            break
        cur = tries.pop(0)
        if not cur:
            break
        try:
            res = subprocess.run(['heatsurvey', target] + cur, capture_output=True, text=True, timeout=40)
        except Exception:
            return []
        out = res.stdout or ''
        rows = parse_crew(out)
        if res.returncode == 0 and rows:
            return rows
        msg = ((res.stderr or '') + out).lower()
        if res.returncode == 0:
            return rows
        mm = re.search(r'at most\s+(\d+)', msg)
        if mm and int(mm.group(1)) < len(cur):
            tries.append(cur[:int(mm.group(1))])
            continue
        bad = re.findall(r'no pipe\s+([A-Za-z0-9_\-]+)', ((res.stderr or '') + out))
        if bad:
            nb = [p for p in cur if norm_pipe(p) not in {norm_pipe(b) for b in bad}]
            if nb and len(nb) < len(cur):
                tries.append(nb)
                continue
        return []
    return rows


def parse_crew(text):
    lines_ = [ln for ln in text.splitlines() if ln.strip()]
    start = None
    for i, ln in enumerate(lines_):
        if ln.strip().lower().startswith('pipe'):
            start = i
            break
    if start is None:
        return []
    rows = []
    for r in csv.DictReader(lines_[start:]):
        r = {(k or '').strip(): (v or '').strip() for k, v in r.items()}
        try:
            for kk in ('flow_t_h', 't_in_C', 't_out_C', 't_amb_C'):
                fnum(r[kk])
        except Exception:
            continue
        rows.append(r)
    return rows


if __name__ == '__main__':
    main()
