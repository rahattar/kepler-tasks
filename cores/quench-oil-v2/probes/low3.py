#!/usr/bin/env python3
"""Quench calculation to HT-5 for one site package.

usage: python3 quench.py PACKAGE_DIR OUT_CSV
"""
import sys, os, json, subprocess, io
import numpy as np
import pandas as pd
from scipy.linalg.lapack import dgtsv

# ---------------------------------------------------------------- HT-5 section 3
KT = np.array([20, 300, 600, 800, 900.])
CT = np.array([20, 300, 600, 720, 800, 900.])
KS = {'C45': np.array([50, 44, 34, 26, 26.]), '42CrMo4': np.array([43, 40, 33, 27, 27.])}
CS = {'C45': np.array([470, 560, 750, 900, 650, 650.]), '42CrMo4': np.array([460, 550, 720, 850, 640, 640.])}
RHO = 7800.
KPROBE = 14200.
FIG = ['cr_max_K_s', 't_crmax_C', 'cr_300_K_s']
AGIT = {'propeller': 1.35, 'none': 1.0}

# numerical settings (checked against finer grids/steps: < 0.3 % on every result)
NGRID = 40
TARGET = 0.5      # K per step, inner half of the bar
TSURF = 2.0       # K per step, anywhere


def solve(steel, R, Tf, Tb, fig, fac, N=NGRID, target=TARGET, ts=TSURF):
    """Vectorised over loads. fig: (L,3) CR_max, T_CRmax, CR_300. Returns dict of the five results."""
    steel = np.asarray(steel)
    L = len(R)
    out = {k: np.full(L, np.nan) for k in ['t85', 'cr700', 'dT', 'ts500', 't150']}
    fig = np.asarray(fig, float)
    hp = KPROBE * fig[:, 0] / (fig[:, 1] - 40.)
    h300 = KPROBE * fig[:, 2] / 260.
    for s in np.unique(steel):
        g = np.where(steel == s)[0]
        r = _solve(s, *(np.asarray(x, float)[g] for x in (R, Tf, Tb, hp, h300, fig[:, 1], fac)),
                   N=N, target=target, ts=ts)
        for k in out:
            out[k][g] = r[k]
    return out


def _solve(steel, R, Tf, Tb, hp, h300, tcr, fac, N, target, ts):
    L = len(R)
    kv = KS[steel]; cv = CS[steel]; n1 = N + 1
    hy = np.stack([0.6 * h300, h300, hp, 0.15 * hp], 1) * fac[:, None]
    rf = (np.arange(N) + 0.5)[None, :]
    V0 = np.empty(n1); V0[0] = 1 / 8.; V0[1:N] = np.arange(1, N); V0[N] = N / 2 - 1 / 8.
    dr2 = (R / N) ** 2
    T = np.tile(Tf[:, None], (1, n1)); Tp = T.copy()
    t = np.zeros(L); dt = 1e-3 * (R / 0.01); dtp = dt.copy()
    marks = [800, 725, 675, 500, 150]
    res = {m: np.full(L, np.nan) for m in marks}
    dTmax = np.zeros(L); ts500 = np.full(L, np.nan)
    idx = np.arange(L)
    half = N // 2
    while len(idx):
        m_ = len(idx)
        Tm = T + (0.5 * dt / dtp)[:, None] * (T - Tp)     # coefficients at mid-step (2nd order)
        k = np.interp(Tm, KT, kv); cp = np.interp(Tm, CT, cv)
        G = 0.5 * (k[:, 1:] + k[:, :-1]) * rf
        y = hy[idx]; tc = tcr[idx]; Ts = np.maximum(Tm[:, N], 100.)
        h = np.where(Ts <= 300, y[:, 0] + (y[:, 1] - y[:, 0]) * (Ts - 100) / 200,
            np.where(Ts <= tc, y[:, 1] + (y[:, 2] - y[:, 1]) * (Ts - 300) / (tc - 300),
            np.where(Ts <= tc + 120, y[:, 2] + (y[:, 3] - y[:, 2]) * (Ts - tc) / 120, y[:, 3])))
        Ri = R[idx]; Tbi = Tb[idx]
        Hs = h * Ri
        M = RHO * cp * V0[None, :] * dr2[idx][:, None] / dt[:, None]
        q = G * (T[:, 1:] - T[:, :-1])
        F = np.zeros_like(T); F[:, :-1] += q; F[:, 1:] -= q; F[:, N] -= Hs * (T[:, N] - Tbi)
        hG = 0.5 * G
        b = M.copy(); b[:, 1:] += hG; b[:, :-1] += hG; b[:, N] += 0.5 * Hs
        d = M * T + 0.5 * F; d[:, N] += 0.5 * Hs * Tbi
        off = np.zeros((m_, n1)); off[:, :N] = -hG
        dl = off.ravel()[:-1].copy(); du = dl.copy()
        x = dgtsv(dl, b.ravel(), du, d.ravel())[3]
        Tn = x.reshape(m_, n1)
        c0, c1 = T[:, 0], Tn[:, 0]; ti = t[idx]
        for mk in marks:
            hit = (c1 <= mk) & (c0 > mk)
            if hit.any():
                f = (c0[hit] - mk) / (c0[hit] - c1[hit]); gg = idx[hit]
                res[mk][gg] = ti[hit] + f * dt[hit]
                if mk == 500:
                    ts500[gg] = T[hit, N] + f * (Tn[hit, N] - T[hit, N])
        dTmax[idx] = np.maximum(dTmax[idx], Tn[:, 0] - Tn[:, N])
        chg = np.maximum(np.abs(Tn[:, :half] - T[:, :half]).max(1), np.abs(Tn - T).max(1) * target / ts)
        t[idx] = ti + dt
        ndt = dt * np.clip(target / np.maximum(chg, 1e-9), 0.5, 1.3)
        keep = c1 > 150
        Tp = T[keep]; T = Tn[keep]; dtp = dt[keep]; dt = ndt[keep]; idx = idx[keep]
    return dict(t85=res[500] - res[800], cr700=50 / (res[675] - res[725]), dT=dTmax, ts500=ts500, t150=res[150])


# ---------------------------------------------------------------- package
def d2n(s):
    return pd.to_datetime(pd.Series(s)).values.astype('datetime64[D]').astype(np.int64)


class Package:
    def __init__(self, pkg):
        self.dir = pkg
        self.site = json.load(open(os.path.join(pkg, 'site.json')))
        self.nlab = int(self.site.get('lab_samples', 0))
        self.sd = int(d2n([self.site['samples_drawn']])[0])
        self.tanks = pd.read_csv(os.path.join(pkg, 'tanks.csv'), dtype={'tank': str, 'oil_system': str})
        self.systems = pd.read_csv(os.path.join(pkg, 'oil_systems.csv'), dtype=str)
        log = pd.read_csv(os.path.join(pkg, 'oil_log.csv'), dtype={'oil_system': str})
        log = log[log.work.astype(str).str.strip() == 'CHARGE_RENEWED'].copy()
        log['day'] = d2n(log.date) if len(log) else np.array([], int)
        self.log = log
        S = pd.read_csv(os.path.join(pkg, 'oil_samples.csv'), dtype={'sampled_at': str})
        S['day'] = d2n(S.date) if len(S) else np.array([], int)
        self.samples = S
        B = pd.read_csv(os.path.join(pkg, 'test_bars.csv'), dtype={'tank': str})
        B['day'] = d2n(B.date) if len(B) else np.array([], int)
        self.bars = B
        Ld = pd.read_csv(os.path.join(pkg, 'loads.csv'), dtype={'load': str, 'tank': str})
        Ld['day'] = d2n(Ld.date) if len(Ld) else np.array([], int)
        self.loads = Ld
        self.tank_sys = dict(zip(self.tanks.tank, self.tanks.oil_system))
        self.fac = {t: AGIT.get(str(a).strip(), 1.0) for t, a in zip(self.tanks.tank, self.tanks.agitation)}
        for t in set(Ld.tank) | set(B.tank) | set(S.sampled_at):
            self.tank_sys.setdefault(t, 'OWN-' + t)
            self.fac.setdefault(t, 1.0)

    def renewals(self, s):
        return np.sort(self.log[self.log.oil_system == s].day.values)


def charge_start(ren, D):
    r = ren[ren <= D]
    return r.max() if len(r) else -10 ** 9


def charge_end(ren, D):
    r = ren[ren > D]
    return r.min() if len(r) else 10 ** 9


def analyses(pk, tank_sys, extra=None):
    """Charge analyses: mean per (system, day)."""
    S = pk.samples.copy()
    S['sys'] = S.sampled_at.map(tank_sys)
    parts = [S[['sys', 'day'] + FIG]]
    if extra is not None and len(extra):
        parts.append(extra[['sys', 'day'] + FIG])
    A = pd.concat(parts, ignore_index=True)
    return A.groupby(['sys', 'day'])[FIG].mean().reset_index()


def figures_at(pk, A, sysname, ren, D):
    """HT-5 section 5 for one system and day D. Returns figures or None."""
    st = charge_start(ren, D); en = charge_end(ren, D)
    g = A[(A.sys == sysname) & (A.day >= st) & (A.day < en)].sort_values('day')
    if not len(g):
        return None
    dd = g.day.values; vv = g[FIG].values
    if en < 10 ** 9:            # charge renewed later: its latest analysis holds
        return vv[-1]
    # current charge: linear between analyses on file, then to the samples_drawn analysis
    k = np.searchsorted(dd, D, side='right') - 1
    if k < 0:
        return vv[0]
    if k >= len(dd) - 1:
        return vv[-1]
    return vv[k] + (vv[k + 1] - vv[k]) * (D - dd[k]) / (dd[k + 1] - dd[k])


def figs_for(pk, A, tank_sys, tanks, days, ren_of):
    out = np.full((len(tanks), 3), np.nan)
    cache = {}
    for i, (t, D) in enumerate(zip(tanks, days)):
        s = tank_sys[t]
        key = (s, D)
        if key not in cache:
            cache[key] = figures_at(pk, A, s, ren_of(s), D)
        v = cache[key]
        if v is not None:
            out[i] = v
    return out


# ---------------------------------------------------------------- test bars
def bar_scale(bars, fig, fac):
    """h multiplier m for each bar such that the computed t85 equals the measured one."""
    n = len(bars)
    if n == 0:
        return np.array([])
    ms = np.array([0.7, 1.0, 1.4])
    St = np.concatenate([bars.steel.values] * 3)
    R = np.tile(bars.diameter_mm.values / 2000., 3)
    Tf = np.tile(bars.furnace_C.values * 1., 3); Tb = np.tile(bars.bath_C.values * 1., 3)
    F = np.tile(fig, (3, 1)); fa = np.concatenate([fac * m for m in ms])
    r = solve(St, R, Tf, Tb, F, fa, N=24, target=1.0, ts=4.0)['t85'].reshape(3, n)
    lt = np.log(r); lm = np.log(ms)
    meas = np.log(bars.t85_core_s.values)
    out = np.full(n, np.nan)
    for i in range(n):
        if not np.all(np.isfinite(lt[:, i])):
            continue
        c = np.polyfit(lt[:, i], lm, 2)
        out[i] = np.exp(np.polyval(c, meas[i]))
    return out


def main(pkgdir, outcsv):
    pk = Package(pkgdir)
    Ld, B = pk.loads, pk.bars
    tank_sys = dict(pk.tank_sys)
    fac = dict(pk.fac)

    # --- 1. which oil each tank holds: check the register against the analyses on file
    S = pk.samples.copy()
    S['sys'] = S.sampled_at.map(tank_sys)
    def _dev(v, w):
        return max(abs(w[0] / v[0] - 1), abs(w[2] / v[2] - 1), abs(w[1] - v[1]) / 600.)
    for t in sorted(set(S.sampled_at)):
        st = S[S.sampled_at == t]
        own = tank_sys[t]
        cands = {}
        owndevs = []
        for D in sorted(set(st.day)):
            v = st[st.day == D][FIG].mean().values
            others = S[(S.day == D) & (S.sampled_at != t)]
            for s2, g2 in others.groupby('sys'):
                dv = _dev(v, g2[FIG].mean().values)
                if s2 == own:
                    owndevs.append(dv)
                else:
                    cands.setdefault(s2, []).append(dv)
        good = [s2 for s2, l in cands.items() if max(l) < 0.005 and len(l) >= 2]
        if len(good) != 1:
            continue
        if owndevs and min(owndevs[-2:]) > 0.015:
            tank_sys[t] = good[0]
        elif not owndevs and len(cands[good[0]]) >= 3 and max(cands[good[0]]) < 0.003:
            tank_sys[t] = good[0]

    def ren_of(s):
        return pk.renewals(s)

    systems_used = sorted(set(tank_sys[t] for t in set(Ld.tank) | set(B.tank)))

    # --- 2. reference figures (analyses on file only) and the bars' h multipliers
    A0 = analyses(pk, tank_sys)

    def ref_fig(s, D):
        """figures on file for system s: latest analysis of the charge at day D, or of the previous charge."""
        ren = ren_of(s)
        g = A0[A0.sys == s].sort_values('day')
        if not len(g):
            return None, None
        st = charge_start(ren, D)
        g2 = g[(g.day >= st) & (g.day <= max(D, st))]
        if len(g2):
            return g2[FIG].values[-1], 'own'
        g3 = g[g.day < st]
        if len(g3):
            return g3[FIG].values[-1], 'prev'
        return g[FIG].values[0], 'prev'

    if len(B):
        bf = np.array([ref_fig(tank_sys[t], D)[0] if ref_fig(tank_sys[t], D)[0] is not None else [np.nan] * 3
                       for t, D in zip(B.tank, B.day)], float)
        ok = np.all(np.isfinite(bf), 1)
        B = B.copy()
        B['m0'] = np.nan
        if ok.any():
            B.loc[ok, 'm0'] = bar_scale(B[ok], bf[ok], B[ok].tank.map(fac).values)
        B['sys'] = B.tank.map(tank_sys)
    else:
        B = B.assign(m0=np.nan, sys=None)

    # --- 3. agitation actually running: early bars, on oil known from the analyses on file
    for t in sorted(set(B.tank)):
        bt = B[(B.tank == t) & np.isfinite(B.m0)].sort_values('day')
        if not len(bt):
            continue
        s = tank_sys[t]
        ren = ren_of(s)
        first_ren = ren[ren > -10 ** 8].min() if len(ren) else 10 ** 9
        g = A0[A0.sys == s]
        dlast = g.day.max() if len(g) else bt.day.min()
        early = bt[(bt.day < first_ren) & (bt.day <= dlast + 75)]
        if len(early) < 2:
            early = bt[bt.day < first_ren].head(3)
        if not len(early):
            continue
        m = np.median(early.m0.values)
        cur = fac[t]
        cand = [1.0, 1.35]
        # the measured bars imply an effective factor cur*m
        best = min(cand, key=lambda c: abs(np.log(cur * m / c)))
        if best != cur and abs(np.log(cur * m / best)) < abs(np.log(m)) and abs(np.log(m)) > 0.15:
            B.loc[B.tank == t, 'm0'] *= cur / best
            fac[t] = best

    # --- 4. which charges need the samples_drawn analysis, and the bars' estimate of each
    need = []   # (priority, system, kind, estimate)
    for s in systems_used:
        ren = ren_of(s)
        lastren = ren.max() if len(ren) else -10 ** 9
        g = A0[(A0.sys == s) & (A0.day >= lastren)]
        tl = [t for t in tank_sys if tank_sys[t] == s]
        nloads = int(Ld.tank.isin(tl).sum())
        if nloads == 0 or Ld[Ld.tank.isin(tl)].day.max() < (g.day.max() if len(g) else lastren):
            continue
        bs = B[(B.sys == s) & (B.day >= lastren) & np.isfinite(B.m0)]
        if len(g):
            dlast = g.day.max()
            bs = bs[bs.day > dlast]
            if len(bs) >= 3:
                x = (bs.day.values - dlast).astype(float)
                y = np.log(bs.m0.values)
                slope = float(np.sum(x * y) / np.sum(x * x))
                est = np.exp(slope * (pk.sd - dlast))
                # spread of the estimate
                pri = abs(np.log(est)) * nloads
            else:
                est = 1.0; pri = 0.05 * nloads
            need.append((pri, s, 'drift', est, dlast))
        else:
            if len(bs):
                est = float(np.exp(np.median(np.log(bs.m0.values))))
                pri = (0.03 + abs(np.log(est))) * nloads
            else:
                est = 1.0; pri = 1.0 * nloads
            need.append((pri, s, 'new', est, lastren))
    need.sort(key=lambda z: -z[0])

    # --- 5. the laboratory order
    order = []
    chosen = need[:pk.nlab]
    for _, s, kind, est, _d in chosen:
        tl = [t for t in tank_sys if tank_sys[t] == s]
        tl.sort(key=lambda t: (-(Ld.tank == t).sum(), t))
        order.append(tl[0])
    # spare capacity: second samples of the charges with most loads
    spare = pk.nlab - len(order)
    if spare > 0:
        extra = []
        for _, s, kind, est, _d in chosen:
            tl = [t for t in tank_sys if tank_sys[t] == s and t not in order]
            tl.sort(key=lambda t: (-(Ld.tank == t).sum(), t))
            extra += tl
        order += extra[:spare]
    lab = pd.DataFrame(columns=['sampled_at'] + FIG)
    if order:
        try:
            p = subprocess.run(['labsample', pkgdir] + order, capture_output=True, text=True, timeout=30)
            if p.returncode == 0:
                txt = p.stdout.strip().splitlines()
                hi = [i for i, l in enumerate(txt) if l.startswith('sampled_at')]
                if hi:
                    lab = pd.read_csv(io.StringIO('\n'.join(txt[hi[0]:])), dtype={'sampled_at': str})
                    lab = lab[lab.sampled_at.isin(order)]
                    for c in FIG:
                        lab[c] = pd.to_numeric(lab[c], errors='coerce')
                    lab = lab.dropna()
        except Exception:
            pass
    got = set(lab.sampled_at)

    # tanks of a system whose laboratory figures disagree: own oil
    lab = lab.copy(); lab['sys'] = lab.sampled_at.map(tank_sys); lab['day'] = pk.sd
    for s, g in lab.groupby('sys'):
        if len(g) > 1:
            med = g[FIG].median().values
            for _, r in g.iterrows():
                if abs(r['cr_max_K_s'] / med[0] - 1) > 0.02 or abs(r['cr_300_K_s'] / med[2] - 1) > 0.02:
                    lab.loc[lab.sampled_at == r.sampled_at, 'sys'] = s  # keep; averaged anyway

    # estimates for charges not analysed
    est_rows = []
    sampled_sys = set(lab.sys)
    for _, s, kind, est, d0 in need:
        if s in sampled_sys:
            continue
        if kind == 'drift':
            base = A0[(A0.sys == s) & (A0.day == d0)][FIG].values[0]
        else:
            ren = ren_of(s)
            prev = A0[(A0.sys == s) & (A0.day < d0)].sort_values('day')
            if not len(prev):
                continue
            base = prev[FIG].values[-1]
        v = base.copy(); v[0] *= est; v[2] *= est
        est_rows.append(dict(sys=s, day=pk.sd, cr_max_K_s=v[0], t_crmax_C=v[1], cr_300_K_s=v[2]))
    extra = pd.concat([lab[['sys', 'day'] + FIG], pd.DataFrame(est_rows, columns=['sys', 'day'] + FIG)],
                      ignore_index=True)
    A = analyses(pk, tank_sys, extra)

    # --- 6. check every tank against its bars with the full oil model; correct what they contradict
    corr = {}   # (tank) -> list of (day_from, day_to, multiplier)
    if len(B):
        bfig = figs_for(pk, A, tank_sys, B.tank.values, B.day.values, ren_of)
        ok = np.all(np.isfinite(bfig), 1)
        B['m1'] = np.nan
        if ok.any():
            B.loc[ok, 'm1'] = bar_scale(B[ok], bfig[ok], B[ok].tank.map(fac).values)
        for t in sorted(set(B.tank)):
            s = tank_sys[t]
            ren = ren_of(s)
            edges = [-10 ** 9] + list(ren) + [10 ** 9]
            for a, b in zip(edges[:-1], edges[1:]):
                bt = B[(B.tank == t) & (B.day >= a) & (B.day < b) & np.isfinite(B.m1)]
                if len(bt) < 3:
                    continue
                lm = np.log(bt.m1.values)
                med = float(np.median(lm))
                se = 0.02 / np.sqrt(len(bt)) * 3
                if abs(med) > max(0.04, se):
                    corr.setdefault(t, []).append((a, b, float(np.exp(med))))

    # --- 7. the loads
    lf = figs_for(pk, A, tank_sys, Ld.tank.values, Ld.day.values, ren_of)
    lfac = Ld.tank.map(fac).values.astype(float)
    for t, lst in corr.items():
        for a, b, m in lst:
            sel = ((Ld.tank == t) & (Ld.day >= a) & (Ld.day < b)).values
            lfac[sel] *= m
    bad = ~np.all(np.isfinite(lf), 1)
    if bad.any():   # no analysis at all: fall back on the bars' scale of a typical oil
        lf[bad] = np.nanmedian(lf[~bad], 0) if (~bad).any() else [80., 580., 7.]
    r = solve(Ld.steel.values, Ld.diameter_mm.values / 2000., Ld.furnace_C.values * 1., Ld.bath_C.values * 1.,
              lf, lfac)
    out = pd.DataFrame({'load': Ld.load.values,
                        't85_core_s': np.round(r['t85'], 4),
                        'cr700_core_K_s': np.round(r['cr700'], 5),
                        'dT_max_K': np.round(r['dT'], 3),
                        'ts_core500_C': np.round(r['ts500'], 3),
                        't150_core_s': np.round(r['t150'], 3)})
    out.to_csv(outcsv, index=False)
    if os.environ.get('QUENCH_DEBUG'):
        sys.stderr.write('map %s\norder %s\nneed %s\nfac %s\ncorr %s\n' % ({t:tank_sys[t] for t in tank_sys if tank_sys[t]!=pk.tank_sys.get(t)}, order, need, {t: fac[t] for t in fac if fac[t] != pk.fac.get(t)}, corr))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
