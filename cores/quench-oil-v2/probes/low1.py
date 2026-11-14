import numpy as np

RHO = 7800.0
KT = {'C45': ([20, 300, 600, 800, 900], [50, 44, 34, 26, 26]),
      '42CrMo4': ([20, 300, 600, 800, 900], [43, 40, 33, 27, 27])}
CT = {'C45': ([20, 300, 600, 720, 800, 900], [470, 560, 750, 900, 650, 650]),
      '42CrMo4': ([20, 300, 600, 720, 800, 900], [460, 550, 720, 850, 640, 640])}
PK = 14200.0
PASSES = 2
MIDH = True


def htab(crmax, tcr, cr300, agit):
    hp = PK * crmax / (tcr - 40.0)
    h3 = PK * cr300 / 260.0
    xs = np.stack([np.full_like(hp, 100.0), np.full_like(hp, 300.0), tcr, tcr + 120.0], 1)
    ys = np.stack([0.6 * h3, h3, hp, 0.15 * hp], 1) * agit[:, None]
    return xs, ys


def interp_rows(T, xs, ys):
    # T: (n,), xs,ys: (n,m) increasing xs
    out = np.empty_like(T)
    out[:] = ys[:, 0]
    for j in range(xs.shape[1] - 1):
        x0, x1, y0, y1 = xs[:, j], xs[:, j + 1], ys[:, j], ys[:, j + 1]
        f = np.clip((T - x0) / (x1 - x0), 0, 1)
        m = T > x0
        out = np.where(m, y0 + f * (y1 - y0), out)
    return out


def solve(steel, D_mm, Tf, Tb, crmax, tcr, cr300, agit, N=40, steps_per_tau=None, late=8.0):
    steel = np.asarray(steel)
    n = len(steel)
    out = np.full((n, 5), np.nan)
    for st in set(steel.tolist()):
        m = np.where(steel == st)[0]
        out[m] = _solve(st, *[np.asarray(x, float)[m] for x in (D_mm, Tf, Tb, crmax, tcr, cr300, agit)], N=N, S=steps_per_tau, late=late)
    return out


def _solve(st, D_mm, Tf, Tb, crmax, tcr, cr300, agit, N, S, late):
    n = len(D_mm)
    R = D_mm / 2000.0
    xs, ys = htab(crmax, tcr, cr300, agit)
    kx = np.array(KT[st][0], float); ky = np.array(KT[st][1], float)
    cx = np.array(CT[st][0], float); cy = np.array(CT[st][1], float)
    xi = np.linspace(0, 1, N + 1)
    Hx = np.linspace(-100, 1100, 12001); cc = np.interp(Hx, cx, cy)
    Hy = np.concatenate([[0], np.cumsum(0.5 * (cc[1:] + cc[:-1]) * np.diff(Hx))])
    dr = R / N
    r = xi[None, :] * R[:, None]
    rf = 0.5 * (r[:, 1:] + r[:, :-1])
    vol = np.empty((n, N + 1))
    vol[:, 1:-1] = r[:, 1:-1] * dr[:, None]
    vol[:, 0] = dr * dr / 8.0
    vol[:, -1] = (R - dr / 4) * dr / 2.0
    Gg = rf / dr[:, None]
    T = np.repeat(Tf[:, None], N + 1, 1)
    alpha = 30.0 / (RHO * 600.0)
    dt0 = R ** 2 / alpha / S
    targets = [800.0, 725.0, 675.0, 500.0, 150.0]
    tcross = np.full((n, 5), np.nan)
    ts500 = np.full(n, np.nan)
    dTmax = np.zeros(n)
    t = np.zeros(n)
    a = np.arange(n)  # active global indices
    Ta = T
    sub = lambda arr: arr[a]
    vA, GA, xsA, ysA, RA, TbA, dtA = vol, Gg, xs, ys, R, Tb, dt0
    tA = t
    it = 0
    m = N + 1
    while len(a):
        it += 1
        fac = np.where(Ta[:, 0] < 480.0, late, 1.0)
        dt = dtA * fac
        Tg = Ta
        for p in range(PASSES):
            if p == 0:
                k = np.interp(Ta, kx, ky)
                c = np.interp(Ta, cx, cy)
                Ts = Ta[:, -1]
            else:
                Tm = 0.5 * (Ta + Tg)
                k = np.interp(Tm, kx, ky)
                dTg = Tg - Ta
                small = np.abs(dTg) < 1e-6
                c = np.where(small, np.interp(Tm, cx, cy), (np.interp(Tg, Hx, Hy) - np.interp(Ta, Hx, Hy)) / np.where(small, 1.0, dTg))
                Ts = Tm[:, -1] if MIDH else Ta[:, -1]
            G = 0.5 * (k[:, 1:] + k[:, :-1]) * GA
            C = (RHO / dt)[:, None] * c * vA
            Hs = interp_rows(Ts, xsA, ysA) * RA
            diag = C.copy()
            diag[:, :-1] += G
            diag[:, 1:] += G
            diag[:, -1] += Hs
            rhs = C * Ta
            rhs[:, -1] += Hs * TbA
            cp = np.empty((len(a), m - 1)); dp = np.empty_like(rhs)
            b0 = diag[:, 0]
            cp[:, 0] = -G[:, 0] / b0
            dp[:, 0] = rhs[:, 0] / b0
            for i in range(1, m):
                den = diag[:, i] + G[:, i - 1] * cp[:, i - 1]
                if i < m - 1:
                    cp[:, i] = -G[:, i] / den
                dp[:, i] = (rhs[:, i] + G[:, i - 1] * dp[:, i - 1]) / den
            Tn = np.empty_like(Ta)
            Tn[:, -1] = dp[:, -1]
            for i in range(m - 2, -1, -1):
                Tn[:, i] = dp[:, i] - cp[:, i] * Tn[:, i + 1]
            Tg = Tn
        tc0 = Ta[:, 0]; tc1 = Tn[:, 0]
        for j, Tt in enumerate(targets):
            hit = (tc0 > Tt) & (tc1 <= Tt)
            if hit.any():
                f = (tc0[hit] - Tt) / (tc0[hit] - tc1[hit])
                g = a[hit]
                tcross[g, j] = tA[hit] + f * dt[hit]
                if j == 3:
                    ts500[g] = Ta[hit, -1] + f * (Tn[hit, -1] - Ta[hit, -1])
        dT = Tn[:, 0] - Tn[:, -1]
        np.maximum.at(dTmax, a, dT) if False else None
        dTmax[a] = np.maximum(dTmax[a], dT)
        Ta = Tn
        tA = tA + dt
        if it % 50 == 0 or True:
            done = tc1 <= 150.0
            if done.any():
                keep = ~done
                a = a[keep]; Ta = Ta[keep]; tA = tA[keep]
                vA = vA[keep]; GA = GA[keep]; xsA = xsA[keep]; ysA = ysA[keep]; RA = RA[keep]; TbA = TbA[keep]; dtA = dtA[keep]
    return np.stack([tcross[:, 3] - tcross[:, 0], 50.0 / (tcross[:, 2] - tcross[:, 1]), dTmax, ts500, tcross[:, 4]], 1)


# ---------------------------------------------------------------- package logic
import sys, os, json, subprocess
import pandas as pd
from datetime import date as _date

FIG = ['cr_max_K_s', 't_crmax_C', 'cr_300_K_s']


def log(*a):
    print(*a, file=sys.stderr)


def dnum(s):
    y, m, d = map(int, str(s)[:10].split('-'))
    return _date(y, m, d).toordinal()


def run(F, steel, D, Tf, Tb, ag, N=30, S=200):
    F = np.asarray(F, float)
    a = [np.asarray(steel), np.asarray(D, float), np.asarray(Tf, float), np.asarray(Tb, float), F[:, 0], F[:, 1], F[:, 2], np.asarray(ag, float)]
    r1 = solve(*a, N=N, steps_per_tau=S)
    r2 = solve(*a, N=N, steps_per_tau=2 * S)
    return 2 * r2 - r1


class Charge:
    def __init__(self, system, start, end):
        self.system, self.start, self.end = system, start, end  # [start, end)
        self.an = {}  # date -> list of figure arrays
        self.lab = None  # (date, figs)
        self.drift = None  # (t0, slope) multiplicative h factor fallback
        self.scale_ref = None

    def points(self):
        pts = sorted((d, np.mean(v, 0)) for d, v in self.an.items())
        return pts

    def figs(self, d):
        pts = self.points()
        current = self.end is None
        if current and self.lab is not None:
            pts = [p for p in pts if p[0] < self.lab[0]] + [self.lab]
        if not pts:
            if self.scale_ref is not None:
                base, m = self.scale_ref
                f = base.copy(); f[0] *= m; f[2] *= m
                return f
            return None
        ds = np.array([p[0] for p in pts], float)
        fs = np.array([p[1] for p in pts])
        if d <= ds[0]:
            f = fs[0].copy()
        elif d >= ds[-1]:
            f = fs[-1].copy()
        else:
            f = np.array([np.interp(d, ds, fs[:, j]) for j in range(3)])
        if self.drift is not None and self.lab is None:
            t0, sl = self.drift
            m = 1.0 + sl * (d - t0)
            f[0] *= m; f[2] *= m
        return f


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    site = json.load(open(os.path.join(pkg, 'site.json')))
    nlab = int(site.get('lab_samples', 0))
    dlab = dnum(site['samples_drawn'])
    tanks = pd.read_csv(os.path.join(pkg, 'tanks.csv'), dtype=str)
    systems = pd.read_csv(os.path.join(pkg, 'oil_systems.csv'), dtype=str)
    olog = pd.read_csv(os.path.join(pkg, 'oil_log.csv'), dtype=str)
    samples = pd.read_csv(os.path.join(pkg, 'oil_samples.csv'))
    bars = pd.read_csv(os.path.join(pkg, 'test_bars.csv'))
    loads = pd.read_csv(os.path.join(pkg, 'loads.csv'))
    for df in (samples, bars, loads):
        df['d'] = [dnum(x) for x in df['date']]
    olog['d'] = [dnum(x) for x in olog['date']]
    tanks['tank'] = tanks['tank'].str.strip()
    t_sys = dict(zip(tanks.tank, tanks.oil_system.str.strip()))
    t_ag = {t: (1.35 if str(a).strip().lower() == 'propeller' else 1.0) for t, a in zip(tanks.tank, tanks.agitation)}
    allsys = set(systems.oil_system.str.strip()) | set(t_sys.values())
    charges = {}
    for s in allsys:
        ren = sorted(olog[(olog.oil_system.str.strip() == s) & (olog.work.str.strip().str.upper() == 'CHARGE_RENEWED')].d.tolist())
        bounds = [-10 ** 9] + ren
        charges[s] = [Charge(s, bounds[i], bounds[i + 1] if i + 1 < len(bounds) else None) for i in range(len(bounds))]

    def charge_of(tank, d):
        for c in charges[t_sys[tank]]:
            if d >= c.start and (c.end is None or d < c.end):
                return c
        return charges[t_sys[tank]][-1]

    for _, r in samples.iterrows():
        tk = str(r.sampled_at).strip()
        if tk not in t_sys:
            continue
        charge_of(tk, r.d).an.setdefault(r.d, []).append(np.array([r[f] for f in FIG], float))

    loads['tank'] = loads['tank'].astype(str).str.strip()
    bars['tank'] = bars['tank'].astype(str).str.strip()

    # ---- provisional figures for test bars (known charges only)
    def prev_charge(c):
        lst = charges[c.system]
        i = lst.index(c)
        return lst[i - 1] if i > 0 else None

    # charges needing lab: current charges with loads or bars
    need = {}
    for _, r in loads.iterrows():
        c = charge_of(r.tank, r.d)
        if c.end is None:
            need.setdefault(id(c), [c, set()])[1].add(r.tank)

    # pre-order test-bar evaluation of current charges that have analyses on file (drift estimate)
    rows = []
    for i, r in bars.iterrows():
        c = charge_of(r.tank, r.d)
        f = c.figs(r.d)
        if f is not None:
            rows.append((i, f))
    agdet = {}
    devs = {}
    if rows:
        idx = [i for i, _ in rows]
        F = np.array([f for _, f in rows])
        b = bars.loc[idx]
        rs = run(np.vstack([F, F]), np.concatenate([b.steel.values] * 2), np.concatenate([b.diameter_mm.values] * 2),
                 np.concatenate([b.furnace_C.values] * 2), np.concatenate([b.bath_C.values] * 2),
                 np.r_[np.ones(len(b)), np.full(len(b), 1.35)], N=20, S=150)
        n = len(b)
        meas = b.t85_core_s.values
        e1 = meas / rs[:n, 0] - 1
        e3 = meas / rs[n:, 0] - 1
        for k, i in enumerate(idx):
            ag = 1.0 if abs(e1[k]) < abs(e3[k]) else 1.35
            agdet[i] = ag
            devs[i] = e1[k] if ag == 1.0 else e3[k]
    # score current charges with analyses: projected deviation at lab date
    score = {}
    for key, (c, tks) in need.items():
        if not c.an:
            score[key] = 1e9  # renewed, never analysed: must sample
            continue
        sel = [i for i in devs if charge_of(bars.loc[i, 'tank'], bars.loc[i, 'd']) is c]
        last = max(c.an)
        sel = [i for i in sel if bars.loc[i, 'd'] > last]
        if len(sel) >= 2:
            x = bars.loc[sel, 'd'].values.astype(float) - last
            y = np.array([devs[i] for i in sel])
            sl = np.sum(x * y) / np.sum(x * x)
            score[key] = abs(sl * (dlab - last)) + 1e-3 * len(tks)
        elif sel:
            score[key] = abs(devs[sel[0]]) + 1e-3
        else:
            score[key] = 0.5 + 1e-3 * len(tks)
    order = sorted(need, key=lambda k: -score[k])
    chosen = order[:nlab]
    log('lab scores', [(need[k][0].system, round(score[k], 4)) for k in order])
    # pick tank per charge: the tank of the charge with most loads, preferring tanks that agree with the group
    req = []
    for k in chosen:
        c, tks = need[k]
        cnt = loads[loads.tank.isin(tks)].groupby('tank').size()
        req.append((cnt.idxmax(), c))
    labres = {}
    if req:
        try:
            p = subprocess.run(['labsample', pkg] + [t for t, _ in req], capture_output=True, text=True, timeout=30)
            log('lab:', p.stdout.strip(), p.stderr.strip())
            for line in p.stdout.splitlines():
                parts = [x.strip() for x in line.split(',')]
                if len(parts) >= 4:
                    try:
                        labres[parts[0]] = np.array([float(x) for x in parts[1:4]])
                    except ValueError:
                        pass
        except Exception as ex:
            log('lab failed', ex)
    for t, c in req:
        if t in labres:
            c.lab = (dlab, labres[t])

    # unsampled current charges: fallback from test bars
    for key, (c, tks) in need.items():
        if c.lab is not None:
            continue
        if not c.an:
            pc = prev_charge(c)
            base = None
            if pc is not None and pc.an:
                base = pc.points()[-1][1]
            else:
                allf = [np.mean(v, 0) for ch in sum(charges.values(), []) for v in ch.an.values()]
                base = np.mean(allf, 0) if allf else np.array([80., 580., 7.])
            c.scale_ref = (base, 1.0)
        fit_drift(c, bars, charge_of, t_ag, dlab)

    # ---- agitation from test bars with final figures
    F = np.array([charge_of(r.tank, r.d).figs(r.d) for _, r in bars.iterrows()]) if len(bars) else np.zeros((0, 3))
    tank_ag = {}
    if len(bars):
        n = len(bars)
        rs = run(np.vstack([F, F]), np.concatenate([bars.steel.values] * 2), np.concatenate([bars.diameter_mm.values] * 2),
                 np.concatenate([bars.furnace_C.values] * 2), np.concatenate([bars.bath_C.values] * 2),
                 np.r_[np.ones(n), np.full(n, 1.35)], N=20, S=150)
        meas = bars.t85_core_s.values
        e1 = meas / rs[:n, 0] - 1
        e3 = meas / rs[n:, 0] - 1
        bars['ag'] = np.where(np.abs(e1) < np.abs(e3), 1.0, 1.35)
        bars['dev'] = np.where(bars.ag == 1.0, e1, e3)
        for t, g in bars.groupby('tank'):
            tank_ag[t] = (g.d.values, g.ag.values)
            log(t, t_sys.get(t), 'reg', t_ag.get(t), 'ag', ''.join('P' if a > 1 else '-' for a in g.sort_values('d').ag.values),
                'dev%', np.round(g.sort_values('d').dev.values * 100, 1).tolist())

    def ag_of(t, d):
        if t in tank_ag:
            ds, ags = tank_ag[t]
            return ags[np.argmin(np.abs(ds - d) + 1e-3 * (ds > d))]
        return t_ag.get(t, 1.0)

    LF = np.array([charge_of(r.tank, r.d).figs(r.d) for _, r in loads.iterrows()])
    LA = np.array([ag_of(r.tank, r.d) for _, r in loads.iterrows()])
    res = run(LF, loads.steel.values, loads.diameter_mm.values, loads.furnace_C.values, loads.bath_C.values, LA, N=32, S=200)
    o = pd.DataFrame({'load': loads['load'], 't85_core_s': np.round(res[:, 0], 4), 'cr700_core_K_s': np.round(res[:, 1], 5),
                      'dT_max_K': np.round(res[:, 2], 3), 'ts_core500_C': np.round(res[:, 3], 3), 't150_core_s': np.round(res[:, 4], 3)})
    o.to_csv(out, index=False)


def fit_drift(c, bars, charge_of, t_ag, dlab):
    """Fit a multiplicative factor on h, linear in time, to the test bars of charge c."""
    idx = [i for i, r in bars.iterrows() if charge_of(r.tank, r.d) is c]
    if len(idx) < 2:
        return
    b = bars.loc[idx]
    t0 = max(c.an) if c.an else c.start
    F0 = np.array([c.figs(d) for d in b.d])
    ag = np.array([t_ag.get(t, 1.0) for t in b.tank])
    n = len(b)
    F1 = F0.copy(); F1[:, 0] *= 1.1; F1[:, 2] *= 1.1
    args = lambda x: np.concatenate([x] * 2)
    rs = run(np.vstack([F0, F1]), args(b.steel.values), args(b.diameter_mm.values), args(b.furnace_C.values), args(b.bath_C.values), args(ag), N=20, S=150)
    p = np.log(rs[n:, 0] / rs[:n, 0]) / np.log(1.1)
    lm = np.log(b.t85_core_s.values / rs[:n, 0]) / p  # log multiplier needed
    # agitation possibly wrong: discard bars needing |lm| > 0.2
    ok = np.abs(lm) < 0.2
    if ok.sum() < 2:
        return
    x = b.d.values[ok].astype(float) - t0; y = lm[ok]
    if c.scale_ref is not None:
        base, _ = c.scale_ref
        c.scale_ref = (base, float(np.exp(np.median(y))))
        log('scaled charge', c.system, c.scale_ref[1])
        return
    sl = np.sum(x * y) / np.sum(x * x)
    log('drift', c.system, sl * (dlab - t0))
    if abs(sl * (dlab - t0)) > 0.01:
        c.drift = (t0, sl)


if __name__ == '__main__':
    main()
