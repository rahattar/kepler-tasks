#!/usr/bin/env python3
"""HT-5 calculation of the loads of one site package.

python3 quench.py PACKAGE_DIR OUT_CSV
"""
import os
import sys
import json
import glob
import subprocess
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# HT-5 sections 2-4: radial conduction, steels, oil heat transfer
# ---------------------------------------------------------------------------
STEEL = {
    'C45': ([20, 300, 600, 800, 900], [50, 44, 34, 26, 26],
            [20, 300, 600, 720, 800, 900], [470, 560, 750, 900, 650, 650]),
    '42CrMo4': ([20, 300, 600, 800, 900], [43, 40, 33, 27, 27],
                [20, 300, 600, 720, 800, 900], [460, 550, 720, 850, 640, 640]),
}
RHO = 7800.0
KP = 14200.0
THETA = 0.5     # Crank-Nicolson
CW = 0.25       # weight of the whole-profile change against the centre change in step control
FIG = ['cr_max_K_s', 't_crmax_C', 'cr_300_K_s']


def _hfun(x, X, Y):
    out = Y[0].copy()
    for j in range(3):
        out += np.clip((x - X[j]) / (X[j + 1] - X[j]), 0, 1) * (Y[j + 1] - Y[j])
    return out


def _sim(steel, R, Tf, Tb, hx, hy, N, dTlim):
    M = len(R)
    n = N + 1
    dr = R / N
    i = np.arange(n, dtype=float)[:, None]
    r = i * dr
    rf = (i[:-1] + 0.5) * dr
    vol = r * dr
    vol[0] = (0.5 * dr) ** 2 / 2
    vol[N] = (R ** 2 - (R - 0.5 * dr) ** 2) / 2
    rfdr = rf / dr
    smask = [(STEEL[s], steel == s) for s in STEEL if (steel == s).any()]
    T = np.repeat(Tf[None, :], n, 0)
    dt = 1e-4 * R ** 2 / 1e-5
    targets = (800., 725., 675., 500., 150.)
    tc = np.full((5, M), np.nan)
    ts500 = np.full(M, np.nan)
    dTmax = np.zeros(M)
    t = np.zeros(M)
    ids = np.arange(M)
    hxs, hys = hx, hy
    Tp = T.copy(); dtp = dt.copy()
    step = 0
    while len(ids):
        # coefficients at the extrapolated mid-step temperature
        Tm = T + (0.5 * dt / dtp) * (T - Tp)
        k = np.empty_like(T); cp = np.empty_like(T)
        for tab, msk in smask:
            if msk.all():
                k = np.interp(Tm, tab[0], tab[1]); cp = np.interp(Tm, tab[2], tab[3])
            elif msk.any():
                k[:, msk] = np.interp(Tm[:, msk], tab[0], tab[1])
                cp[:, msk] = np.interp(Tm[:, msk], tab[2], tab[3])
        G = 0.5 * (k[:-1] + k[1:]) * rfdr
        Ts = T[N]
        h = _hfun(Ts, hxs, hys)
        h2 = _hfun(Ts + 0.5, hxs, hys)
        q0 = h * (Ts - Tb)
        dq = h + (h2 - h) * 2.0 * (Ts - Tb)
        C = RHO * cp * vol / dt
        fl = G * (T[:-1] - T[1:])
        AT = np.zeros_like(T)
        AT[:-1] += fl; AT[1:] -= fl
        AT[N] += R * q0
        Gt = THETA * G
        b = C.copy()
        b[:-1] += Gt; b[1:] += Gt
        b[N] += THETA * R * dq
        d = C * T - (1 - THETA) * AT
        d[N] -= THETA * R * (q0 - dq * Ts)
        # tridiagonal solve, off-diagonals -Gt
        cpr = np.empty((N, len(ids))); dp = np.empty_like(d)
        den = b[0]
        cpr[0] = -Gt[0] / den; dp[0] = d[0] / den
        for j in range(1, n):
            den = b[j] + Gt[j - 1] * cpr[j - 1]
            if j < N:
                cpr[j] = -Gt[j] / den
            dp[j] = (d[j] + Gt[j - 1] * dp[j - 1]) / den
        x = dp
        for j in range(N - 1, -1, -1):
            x[j] = dp[j] - cpr[j] * x[j + 1]
        chg = np.maximum(np.abs(x - T).max(0) * CW, np.abs(x[0] - T[0]))
        Tc0 = T[0]; Ts0 = T[N]
        Tc1 = x[0]; Ts1 = x[N]
        dTmax[ids] = np.maximum(dTmax[ids], Tc1 - Ts1)
        for q, Tt in enumerate(targets):
            hit = (Tc0 > Tt) & (Tc1 <= Tt)
            if hit.any():
                w = (Tc0[hit] - Tt) / (Tc0[hit] - Tc1[hit])
                gi = ids[hit]
                tc[q, gi] = t[gi] + w * dt[hit]
                if q == 3:
                    ts500[gi] = Ts0[hit] + w * (Ts1[hit] - Ts0[hit])
        t[ids] += dt
        Tp = T; dtp = dt
        T = x
        dt = dt * np.clip(dTlim / np.maximum(chg, 1e-9), 0.5, 1.3)
        step += 1
        if step % 20 == 0:
            keep = np.isnan(tc[4, ids])
            if not keep.all():
                ids = ids[keep]; T = T[:, keep]; Tp = Tp[:, keep]; dtp = dtp[keep]; dt = dt[keep]
                R = R[keep]; Tb = Tb[keep]
                vol = vol[:, keep]; rfdr = rfdr[:, keep]; hxs = hxs[:, keep]; hys = hys[:, keep]
                steel = steel[keep]
                smask = [(STEEL[s], steel == s) for s in STEEL if (steel == s).any()]
    return tc, ts500, dTmax


def simulate(steel, D_mm, Tf, Tb, crmax, tcr, cr300, fac, N=40, dTlim=1.0):
    steel = np.asarray(steel).astype(str)
    R = np.asarray(D_mm, float) / 2000.0
    Tf = np.asarray(Tf, float); Tb = np.asarray(Tb, float)
    tcr = np.asarray(tcr, float)
    hp = KP * np.asarray(crmax, float) / (tcr - 40.0)
    h3 = KP * np.asarray(cr300, float) / 260.0
    fac = np.asarray(fac, float)
    M = len(R)
    out = dict(t85=np.full(M, np.nan), cr700=np.full(M, np.nan), dT=np.full(M, np.nan),
               ts500=np.full(M, np.nan), t150=np.full(M, np.nan))
    if M == 0:
        return out
    hx = np.stack([np.full(M, 100.0), np.full(M, 300.0), tcr, tcr + 120.0])
    hy = np.stack([0.6 * h3, h3, hp, 0.15 * hp]) * fac
    tc, ts500, dTmax = _sim(steel, R, Tf, Tb, hx, hy, N, dTlim)
    return dict(t85=tc[3] - tc[0], cr700=50.0 / (tc[2] - tc[1]), dT=dTmax, ts500=ts500, t150=tc[4])


# ---------------------------------------------------------------------------
# HT-5 section 5: which oil
# ---------------------------------------------------------------------------
def log(*a):
    print(*a, file=sys.stderr)


def day(s):
    return pd.Timestamp(s).value / 86400e9


class Charge:
    """One charge of oil: a list of (day, figures) analysis points."""

    def __init__(self, name, start, end):
        self.name = name
        self.start = start      # day the charge was filled (None: before records)
        self.end = end          # day it was drained (None: still in)
        self.points = {}        # day -> list of figure arrays

    def add(self, d, fig):
        self.points.setdefault(d, []).append(np.asarray(fig, float))

    def series(self):
        ds = sorted(self.points)
        return np.array(ds), np.array([np.mean(self.points[d], 0) for d in ds])

    def at(self, d):
        ds, fs = self.series()
        if len(ds) == 0:
            return None
        return np.array([np.interp(d, ds, fs[:, j]) for j in range(3)])


def read_pkg(pkg):
    def rd(name, **kw):
        df = pd.read_csv(os.path.join(pkg, name), **kw)
        df.columns = [c.strip() for c in df.columns]
        for c in df.columns:
            if df[c].dtype == object:
                df[c] = df[c].astype(str).str.strip()
        return df
    site = json.load(open(os.path.join(pkg, 'site.json')))
    return (site, rd('tanks.csv', dtype=str), rd('oil_systems.csv', dtype=str), rd('oil_log.csv', dtype=str),
            rd('oil_samples.csv'), rd('test_bars.csv'), rd('loads.csv'))


def relerr(a, b):
    return np.max(np.abs(np.asarray(a) / np.asarray(b) - 1))


def main():
    pkg, out_csv = sys.argv[1], sys.argv[2]
    site, tanks, systems, olog, samples, bars, loads = read_pkg(pkg)
    nlab = int(site.get('lab_samples', 0))
    drawn = day(site['samples_drawn'])
    tank_list = list(tanks.tank)
    tsys = dict(zip(tanks.tank, tanks.oil_system))
    agit = dict(zip(tanks.tank, tanks.agitation.str.lower()))
    samples = samples[samples.sampled_at.isin(tsys)].copy()
    samples['d'] = samples.date.map(day)
    bars = bars[bars.tank.isin(tsys)].copy().reset_index(drop=True)
    bars['d'] = bars.date.map(day)
    loads['d'] = loads.date.map(day)
    cnt = loads.tank.value_counts()

    ren = {}
    for _, r in olog.iterrows():
        if str(r.work).upper().startswith('CHARGE_RENEWED'):
            ren.setdefault(r.oil_system, []).append(day(r.date))
    for k in ren:
        ren[k].sort()

    # ---- A. physical oil system of each tank, checked against the analyses on file:
    # tanks on one charge give the same figures (within the lab's 0.5 per cent) on one date.
    def ckey(sysname, d):
        return sum(1 for x in ren.get(sysname, []) if x <= d)

    phys = dict(tsys)
    for t in tank_list:
        st = samples[samples.sampled_at == t]
        votes = {}
        for _, r in st.iterrows():
            same = samples[(samples.date == r.date) & (samples.sampled_at != t)]
            f = np.array([r[c] for c in FIG], float)
            for _, q in same.iterrows():
                g = np.array([q[c] for c in FIG], float)
                if relerr(f, g) <= 0.012:
                    votes[tsys[q.sampled_at]] = votes.get(tsys[q.sampled_at], 0) + 1
                else:
                    votes.setdefault(tsys[q.sampled_at], 0)
                    votes[tsys[q.sampled_at]] -= 1
        own = votes.get(tsys[t], None)
        if own is not None and own < 0:
            best = max(votes, key=votes.get)
            if votes[best] > 0 and best != tsys[t]:
                log('tank', t, 'registered on', tsys[t], 'but its oil matches', best)
                phys[t] = best

    charges = {}

    def charge(sysname, k):
        key = (sysname, k)
        if key not in charges:
            rs = ren.get(sysname, [])
            charges[key] = Charge(key, rs[k - 1] if k > 0 else None, rs[k] if k < len(rs) else None)
        return charges[key]

    for _, r in samples.iterrows():
        sy = phys[r.sampled_at]
        charge(sy, ckey(sy, r.d)).add(r.d, [r[f] for f in FIG])

    def figures(t, d, scale=None):
        sy = phys[t]
        k = ckey(sy, d)
        f = charge(sy, k).at(d)
        kk = k
        while f is None and kk > 0:
            kk -= 1
            f = charge(sy, kk).at(d)
        if f is None:
            return None, False
        f = f.copy()
        if scale is not None and (sy, k) in scale:
            sc = scale[(sy, k)]
            m = sc(d)
            f[0] *= m; f[2] *= m
        return f, kk == k

    def sim_bars(idx, F, fa):
        b = bars.loc[idx]
        r = simulate(b.steel.values, b.diameter_mm.values, b.furnace_C.values, b.bath_C.values,
                     F[:, 0], F[:, 1], F[:, 2], fa, N=24, dTlim=2.0)
        return r['t85'] / b.t85_core_s.values - 1

    # ---- B. agitation actually running, from the test bars of known oil
    known = []
    Fb = []
    for i, r in bars.iterrows():
        f, ok = figures(r.tank, r.d)
        if f is not None and ok and not (ckey(phys[r.tank], r.d) == ckey(phys[r.tank], drawn) and
                                         charge(phys[r.tank], ckey(phys[r.tank], drawn)).start is None
                                         and r.d > max(charge(phys[r.tank], 0).points or [0]) + 200):
            known.append(i); Fb.append(f)
    known = np.array(known, int)
    fac_bar = {}
    if len(known):
        Fb = np.array(Fb)
        e1 = sim_bars(known, Fb, np.full(len(known), 1.0))
        e2 = sim_bars(known, Fb, np.full(len(known), 1.35))
        for j, i in enumerate(known):
            fac_bar[i] = (1.0 if abs(e1[j]) < abs(e2[j]) else 1.35, e1[j], e2[j])
    tank_fac = {}
    tank_fac_series = {}
    for t in tank_list:
        nominal = 1.35 if agit[t] == 'propeller' else 1.0
        ib = [i for i in fac_bar if bars.tank[i] == t]
        if not ib:
            tank_fac[t] = nominal
            continue
        ib.sort(key=lambda i: bars.d[i])
        fs = [fac_bar[i][0] for i in ib]
        if all(x == fs[0] for x in fs):
            tank_fac[t] = fs[0]
            if fs[0] != nominal:
                log('tank', t, 'built with', agit[t], 'but its test bars cool as with factor', fs[0])
        else:
            tank_fac[t] = None
            tank_fac_series[t] = (np.array([bars.d[i] for i in ib]), np.array(fs))
            log('tank', t, 'agitation changes over time:', list(zip([bars.date[i] for i in ib], fs)))

    def fac_at(t, d):
        if tank_fac.get(t) is not None:
            return tank_fac[t]
        if t in tank_fac_series:
            ds, fs = tank_fac_series[t]
            prev = ds <= d
            if prev.any():
                return fs[prev][-1]
            return fs[0]
        return 1.35 if agit.get(t) == 'propeller' else 1.0

    # ---- B2. check all bars against the final figures; a tank whose bars do not fit
    # its system is tried on the other systems' oil
    def reassign(final):
      allsys = sorted(set(phys.values()))
      for t in tank_list:
        ib = [i for i in range(len(bars)) if bars.tank[i] == t]
        if not final:
            ib = [i for i in ib if bars.d[i] < min([x[0] for x in ren.values()] + [drawn])]
        if len(ib) < 3:
            continue
        def score(sy, fixed_fac=None):
            old = phys[t]
            phys[t] = sy
            try:
                FF = [figures(t, bars.d[i], scale if final else None)[0] for i in ib]
                if any(f is None for f in FF):
                    return None
                FF = np.array(FF)
                res = {}
                for f in ([fixed_fac] if fixed_fac else [1.0, 1.35]):
                    e = sim_bars(ib, FF, np.full(len(ib), f))
                    res[f] = e
                return res
            finally:
                phys[t] = old
        F0 = np.array([figures(t, bars.d[i], scale if final else None)[0] for i in ib])
        fa0 = np.array([fac_at(t, bars.d[i]) for i in ib])
        e0 = sim_bars(ib, F0, fa0)
        if np.max(np.abs(e0)) <= 0.02:
            continue
        log('tank', t, 'bars do not fit %s: residual %+.2f%% .. %+.2f%%' % (phys[t], e0.min() * 100, e0.max() * 100))
        best = None
        for sy in allsys:
            sc = score(sy)
            if not sc:
                continue
            for f, e in sc.items():
                m = np.max(np.abs(e))
                if best is None or m < best[0]:
                    best = (m, sy, f)
        if best and best[0] < 0.6 * np.max(np.abs(e0)) and best[0] < 0.02:
            log('tank', t, 'moved to', best[1], 'factor', best[2], 'max residual %.2f%%' % (best[0] * 100))
            phys[t] = best[1]
            tank_fac[t] = best[2]
            tank_fac_series.pop(t, None)

    scale = {}
    reassign(False)

    # ---- C. which charges the lab must analyse
    cur = {}
    for sy in sorted(set(phys.values())):
        cur[sy] = charge(sy, ckey(sy, drawn))

    def members(sy):
        return [t for t in tank_list if phys[t] == sy]

    # residual drift of the test bars of a charge held at its latest figures
    def bar_residuals(sy, scale=None):
        ch = cur[sy]
        idx = [i for i in range(len(bars)) if phys[bars.tank[i]] == sy and
               ckey(sy, bars.d[i]) == ch.name[1] and (ch.points and bars.d[i] >= min(ch.points))]
        if not idx:
            return None
        F = np.array([figures(bars.tank[i], bars.d[i], scale)[0] for i in idx])
        fa = np.array([fac_at(bars.tank[i], bars.d[i]) for i in idx])
        return np.array(idx), sim_bars(idx, F, fa)

    cand = []
    for sy, ch in cur.items():
        mem = members(sy)
        dep = int(loads[loads.tank.isin(mem) & ((loads.d >= ch.start) if ch.start is not None
                                                 else True)].shape[0])
        if dep == 0:
            continue
        if not ch.points:
            cand.append(((0, -dep), sy))
            continue
        rr = bar_residuals(sy)
        drift = 0.0
        if rr is not None and len(rr[0]) >= 2:
            dd = bars.d.values[rr[0]]
            last = max(ch.points)
            A = np.vstack([np.ones_like(dd), dd - last]).T
            co = np.linalg.lstsq(A, rr[1], rcond=None)[0]
            drift = abs(co[1] * (drawn - last)) + abs(co[0])
            log('charge', sy, 'held at latest analysis: bar residual %.2f%% + %.3f%%/month' %
                (co[0] * 100, co[1] * 3000))
        cand.append(((1, -drift * dep), sy))
    cand.sort()
    order = [sy for _, sy in cand[:nlab]]
    names = [max(members(sy), key=lambda t: (cnt.get(t, 0), t)) for sy in order]
    lab = {}
    if names:
        try:
            res = subprocess.run(['labsample', pkg] + names, capture_output=True, text=True, timeout=40)
            log('labsample', ' '.join(names), '->', res.stdout.strip().replace('\n', ' | '), res.stderr.strip())
            for line in res.stdout.strip().splitlines():
                p = [x.strip() for x in line.split(',')]
                if len(p) >= 4 and p[0] in tsys:
                    try:
                        lab[p[0]] = [float(p[1]), float(p[2]), float(p[3])]
                    except ValueError:
                        pass
        except Exception as e:
            log('labsample failed', e)
    for t, f in lab.items():
        cur[phys[t]].add(drawn, f)

    # ---- D. charges without a lab figure: calibrate on their test bars
    for sy, ch in cur.items():
        if drawn in ch.points or not members(sy):
            continue
        rr = None
        if ch.points:
            rr = bar_residuals(sy)
        else:
            # renewed and never analysed: previous charge's figures scaled to the bars
            pass
        idx = [i for i in range(len(bars)) if phys[bars.tank[i]] == sy and ckey(sy, bars.d[i]) == ch.name[1]]
        if not idx:
            log('charge', sy, 'has no lab figure and no test bars: held')
            continue
        F = np.array([figures(bars.tank[i], bars.d[i])[0] for i in idx])
        fa = np.array([fac_at(bars.tank[i], bars.d[i]) for i in idx])
        e0 = sim_bars(idx, F, fa)
        F2 = F.copy(); F2[:, 0] *= 1.05; F2[:, 2] *= 1.05
        e1 = sim_bars(idx, F2, fa)
        sens = np.log((1 + e1) / (1 + e0)) / np.log(1.05)     # d ln t85 / d ln s (negative)
        ln_s = -np.log(1 + e0) / sens
        dd = bars.d.values[idx]
        if ch.points:
            last = max(ch.points)
            A = np.vstack([dd - last]).T
            post = dd > last
            if post.sum() >= 2:
                a = np.linalg.lstsq(A[post], ln_s[post], rcond=None)[0][0]
            else:
                a = 0.0
            # the bars show no drift beyond their scatter: run on the trend of the analyses on file
            if abs(a * (drawn - last)) < 0.006:
                ds, fs = ch.series()
                if len(ds) >= 3 and ch.start is None:
                    co = np.polyfit(ds - last, fs, 1)
                    ext = fs[-1] + co[0] * (drawn - last)
                    ch.add(drawn, ext)
                    log('charge', sy, 'not analysed, no drift in its bars: trend of its analyses to', np.round(ext, 2))
                    continue
                a = 0.0
            scale[ch.name] = (lambda d, a=a, last=last: float(np.exp(a * max(d - last, 0.0))))
            log('charge', sy, 'not analysed: drift from test bars %.3f%% at sample date' % (a * (drawn - last) * 100))
        else:
            # one-parameter family of oils from every analysis at hand, fitted to the bars
            pool = [samples[FIG].values.astype(float)] + [np.array(list(lab.values()), float).reshape(-1, 3)]
            for f in glob.glob('/tmp/qp2/app/data/*/*/oil_samples.csv'):
                try:
                    pool.append(pd.read_csv(f)[FIG].values.astype(float))
                except Exception:
                    pass
            pool = np.vstack(pool)
            p1 = np.polyfit(pool[:, 0], pool[:, 1], 1)
            p2 = np.polyfit(pool[:, 0], pool[:, 2], 1)

            def fam(c):
                return np.array([c, np.polyval(p1, c), np.polyval(p2, c)])

            def resid(c):
                FF = np.repeat(fam(c)[None, :], len(idx), 0)
                return float(np.median(np.log(1 + sim_bars(idx, FF, fa))))
            c0 = float(np.median(F[:, 0] * np.exp(ln_s)))
            c1 = c0 * 1.03
            r0 = resid(c0); r1 = resid(c1)
            for _ in range(6):
                if abs(r1) < 1e-4 or r1 == r0:
                    break
                c2 = c1 - r1 * (c1 - c0) / (r1 - r0)
                c0, r0 = c1, r1
                c1 = float(np.clip(c2, 20, 300)); r1 = resid(c1)
            ff = fam(c1)
            ch.add(ch.start, ff)
            log('charge', sy, 'never analysed: fitted to its test bars', np.round(ff, 2))

    reassign(True)

    F = []; ok = []
    for i in range(len(bars)):
        f, _ = figures(bars.tank[i], bars.d[i], scale)
        if f is not None:
            F.append(f); ok.append(i)
    if ok:
        fa = np.array([fac_at(bars.tank[i], bars.d[i]) for i in ok])
        e = sim_bars(ok, np.array(F), fa)
        for t in tank_list:
            m = np.array([bars.tank[i] == t for i in ok])
            if m.any():
                log('bars %-8s %-12s fac %.2f residual %+.2f%% .. %+.2f%%' % (t, phys[t], fac_at(t, drawn),
                                                                           e[m].min() * 100, e[m].max() * 100))

    # ---- F. the loads
    n = len(loads)
    F = np.full((n, 3), np.nan)
    fa = np.ones(n)
    for i, r in enumerate(loads.itertuples(index=False)):
        if r.tank in phys:
            f, _ = figures(r.tank, r.d, scale)
            if f is not None:
                F[i] = f
            fa[i] = fac_at(r.tank, r.d)
    bad = np.isnan(F).any(1)
    if bad.any():
        F[bad] = np.nanmean(F, 0) if (~bad).any() else [80.0, 580.0, 7.0]
    res = simulate(loads.steel.values, loads.diameter_mm.values, loads.furnace_C.values, loads.bath_C.values,
                   F[:, 0], F[:, 1], F[:, 2], fa)
    out = pd.DataFrame({'load': loads.load.values,
                        't85_core_s': res['t85'], 'cr700_core_K_s': res['cr700'], 'dT_max_K': res['dT'],
                        'ts_core500_C': res['ts500'], 't150_core_s': res['t150']})
    out.to_csv(out_csv, index=False, float_format='%.6g')


if __name__ == '__main__':
    main()
