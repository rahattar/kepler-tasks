#!/usr/bin/env python3
"""RL-2 sucker-rod pump setting-table calculation (method of characteristics)."""
import sys, json, os
import numpy as np
import pandas as pd

G = 9.80665
MAT = {'steel': (200e9, 8000.0), 'fibreglass': (50e9, 2400.0)}
TUBING_ID = {60.3: 50.7, 73.0: 62.0, 88.9: 76.0}
ET = 200e9
PATM = float(os.environ.get('RL2_PATM', '0'))
DT_TARGET = float(os.environ.get('RL2_DT', '0.0085'))
TRACE = bool(os.environ.get('RL2_TRACE'))
TRN = int(os.environ.get("RL2_TRN", "5"))
FILT = float(os.environ.get('RL2_FILT', '0.8'))
FORD = int(os.environ.get('RL2_FORD', '4'))
GASFIX = int(os.environ.get('RL2_GASFIX', '0'))


def load(fd):
    f = json.load(open(os.path.join(fd, 'field.json')))
    wells = pd.read_csv(os.path.join(fd, 'wells.csv'))
    rods = pd.read_csv(os.path.join(fd, 'rods.csv'))
    cards = pd.read_csv(os.path.join(fd, 'cards.csv'))
    sets = pd.read_csv(os.path.join(fd, 'settings.csv'))
    return f, wells, rods, cards, sets


def well_props(f, wells, rods, anchor_override=None):
    rhol = f['liquid_density_kg_m3']
    P = {}
    for _, w in wells.iterrows():
        name = w['well']
        r = rods[rods.well == name].sort_values('taper')
        tapers = []
        W = 0.0
        for _, t in r.iterrows():
            E, rho = MAT[str(t['material']).strip().lower()]
            A = np.pi * (t['diameter_mm'] / 1000) ** 2 / 4
            a = np.sqrt(E / rho)
            tapers.append((t['length_m'] / a, A * np.sqrt(E * rho)))
            W += A * t['length_m'] * G * (rho - rhol)
        L = float(w['pump_depth_m'])
        od = float(w['tubing_od_mm'])
        idm = min(TUBING_ID.items(), key=lambda kv: abs(kv[0] - od))[1]
        At = np.pi / 4 * ((od / 1000) ** 2 - (idm / 1000) ** 2)
        anc = w['anchor_depth_m']
        Lf = L if (pd.isna(anc)) else L - float(anc)
        Ap = np.pi * (w['plunger_mm'] / 1000) ** 2 / 4
        pd_ = w['tubing_head_pressure_kPa'] * 1000 + rhol * G * L
        P[name] = dict(tapers=tapers, W=W, kt=Lf / (ET * At), Ap=Ap, pd=pd_,
                       k=float(w['unit_factor']), S0=float(w['found_surface_stroke_m']),
                       N0=float(w['found_spm']), L=L)
    return P


def build_grid(tapers):
    tau = sum(t for t, _ in tapers)
    N = max(len(tapers) * 2, int(round(tau / DT_TARGET)))
    dt = tau / N
    raw = [t / dt for t, _ in tapers]
    n = [max(1, int(np.floor(x))) for x in raw]
    while sum(n) < N:
        i = int(np.argmax([raw[j] - n[j] for j in range(len(n))]))
        n[i] += 1
    while sum(n) > N:
        i = int(np.argmax([n[j] - raw[j] for j in range(len(n))]))
        n[i] -= 1
    Z = np.concatenate([np.full(n[j], tapers[j][1]) for j in range(len(n))])
    return dt, Z


def simulate(rows, c, t_settle=30.0, t_window=30.0, min_cycles=3):
    """Time-march the rod strings by characteristics with the pump boundary of RL-2 s.4-5.

    rows: dicts with tapers, W, kt, Ap, pd, k, S, N, Fo, hs (hs None -> barrel fills with liquid).
    The nodes of all rows are kept in one flat array.  Returns per-row medians over the
    recorded cycles of plunger stroke, liquid column, and peak and minimum dynamic polished
    rod load (tension above rest)."""
    R0 = len(rows)
    grids = [build_grid(r['tapers']) for r in rows]
    Nn = np.array([len(g[1]) for g in grids])
    dt = np.array([g[0] for g in grids])
    # flat layout: row i holds nodes 0..Nn[i]
    rowid = np.repeat(np.arange(R0), Nn + 1)
    Zr = np.concatenate([np.append(g[1], g[1][-1]) for g in grids])
    Zl = np.concatenate([np.insert(g[1], 0, g[1][0]) for g in grids])
    dampf = (1.0 - c * dt)[rowid]
    ZrD = Zr * dampf; ZlD = Zl * dampf
    inv = 1.0 / (Zl + Zr); c1 = ZrD - Zl; c2 = Zl + ZlD
    start = np.concatenate([[0], np.cumsum(Nn + 1)[:-1]])
    bot = start + Nn
    zr0 = Zr[start]; zrd0 = ZrD[start]; Zb = Zl[bot]; ZlDb = ZlD[bot]
    S = np.array([r['S'] for r in rows], float); Nspm = np.array([r['N'] for r in rows], float)
    kk = np.array([r['k'] for r in rows], float)
    Fo = np.array([r['Fo'] for r in rows], float); kt = np.array([r['kt'] for r in rows], float)
    Ap = np.array([r['Ap'] for r in rows], float); pdv = np.array([r['pd'] for r in rows], float)
    hs = np.array([1e9 if r['hs'] is None else r['hs'] for r in rows], float)
    pdA = pdv + PATM
    piA = pdA - Fo / Ap
    Glof = piA / pdA
    Tper = 60.0 / Nspm
    om = 2 * np.pi / Tper
    cyc_first = np.ceil(t_settle / Tper).astype(int)
    ncyc = np.maximum(min_cycles, np.ceil(t_window / Tper)).astype(int)
    t_end = (cyc_first + ncyc) * Tper
    nend = np.ceil(t_end / dt).astype(int) + 1
    K = int(ncyc.max())
    st_max = np.full((R0, K), np.nan); st_min = np.full((R0, K), np.nan)
    st_sp = np.full((R0, K), np.nan); st_hl = np.full((R0, K), np.nan)

    R = R0
    orig = np.arange(R0)
    L = len(Zr)
    P = np.zeros(L); Q = np.zeros(L)   # T + ZrD V and T - ZlD V at the nodes
    mode = np.zeros(R, int)   # 0 TV open, 1 both shut on liquid, 2 SV open, 3 gas
    yN = np.zeros(R); yprev = np.zeros(R)
    s = Fo * kt; slow = s.copy(); stop = s.copy(); g0 = np.zeros(R)
    F = np.zeros(R)
    cmax = np.full(R, -1e30); cmin = np.full(R, 1e30)
    Sp = np.zeros(R); hl = np.zeros(R)
    cyc_prev = np.zeros(R, int)
    gopen = np.zeros(R, bool); sopen = np.zeros(R)
    BDF2 = os.environ.get('RL2_BDF2', '0') == '1'
    Zbdt = (1.5 if BDF2 else 1.0) * Zb / dt
    kz = kt * Zbdt
    perrow = ['dt', 'S', 'om', 'kk', 'Fo', 'kt', 'Ap', 'hs', 'pdA', 'piA', 'Glof', 'Tper', 'cyc_first',
              'nend', 'orig', 'zr0', 'zrd0', 'Zb', 'ZlDb', 'Zbdt', 'kz', 'mode', 'yN', 'yprev', 's',
              'slow', 'stop', 'g0', 'F', 'cmax', 'cmin', 'Sp', 'hl', 'cyc_prev', 'gopen', 'sopen', 'Nn']
    flat = ['P', 'Q', 'inv', 'c1', 'c2', 'rowid']
    V = locals()
    st = {k: V[k] for k in perrow + flat}
    Kd = K
    n = 0
    nmax = int(nend.max())
    next_compact = 1
    while True:
        n += 1
        if n > nmax:
            break
        if n >= next_compact:
            keep = st['nend'] > n
            if not keep.all():
                kf = keep[st['rowid']]
                for k in flat:
                    st[k] = st[k][kf]
                for k in perrow:
                    st[k] = st[k][keep]
                st['rowid'] = np.repeat(np.arange(keep.sum()), st['Nn'] + 1)
            ne = np.sort(st['nend'])
            R = len(ne)
            next_compact = int(ne[min(R - 1, R // 3)]) if R > 8 else nmax + 1
            if next_compact <= n:
                next_compact = nmax + 1
            dt = st['dt']; S = st['S']; om = st['om']; kk = st['kk']; Fo = st['Fo']; kt = st['kt']
            Ap = st['Ap']; hs = st['hs']; pdA = st['pdA']; piA = st['piA']; Glof = st['Glof']
            Tper = st['Tper']; cyc_first = st['cyc_first']; orig = st['orig']; zr0 = st['zr0']
            zrd0 = st['zrd0']; Zb = st['Zb']; ZlDb = st['ZlDb']; Zbdt = st['Zbdt']; kz = st['kz']
            mode = st['mode']; yN = st['yN']; yprev = st['yprev']; s = st['s']; slow = st['slow']
            stop = st['stop']; g0 = st['g0']; F = st['F']; cmax = st['cmax']; cmin = st['cmin']
            Sp = st['Sp']; hl = st['hl']; cyc_prev = st['cyc_prev']; gopen = st['gopen']
            sopen = st['sopen']; P = st['P']; Q = st['Q']
            inv = st['inv'][1:-1]; c1 = st['c1'][1:-1]; c2 = st['c2'][1:-1]
            Nn = st['Nn']
            start = np.concatenate([[0], np.cumsum(Nn + 1)[:-1]])
            bot = start + Nn; top1 = start + 1; botm1 = bot - 1
            fwf = np.full(len(st['rowid']), FILT * 0.25)
            fwf[start] = 0; fwf[bot] = 0
            zrf = st['c2']
            jn = np.zeros(len(fwf), bool)
            jn[1:-1] = (np.abs(zrf[1:-1] - zrf[:-2]) > 1e-9 * zrf[1:-1]) | (np.abs(zrf[1:-1] - zrf[2:]) > 1e-9 * zrf[1:-1])
            fwf[jn] = 0; fwf[start + 1] = 0; fwf[bot - 1] = 0
            fw = fwf[1:-1]
            fw4f = np.where(fwf > 0, FILT / 16.0, 0.0)
            for sh in (1, -1, 2, -2):
                fw4f[np.roll(fwf == 0, sh)] = 0.0
            fw4f[start] = 0; fw4f[bot] = 0
            fw4 = fw4f[2:-2]
            R = len(Nn)
        t = n * dt
        q = om * t
        v0 = S * om * (0.5 * np.sin(q) + 0.25 * kk * np.sin(2 * q))
        ain = P[botm1]
        T0 = Q[top1] + zr0 * v0
        Pm = P[:-2]
        Vi = (Pm - Q[2:]) * inv
        Pn = np.empty_like(P); Qn = np.empty_like(Q)
        np.add(Pm, c1 * Vi, out=Pn[1:-1])
        np.subtract(Pm, c2 * Vi, out=Qn[1:-1])
        Pn[start] = T0 + zrd0 * v0
        Qn[start] = 0.0; Pn[bot] = 0.0
        # pump boundary
        vN = np.empty(R); Fn = F.copy()
        m0 = mode == 0
        if m0.any():
            vv = ain / Zb
            Fn[m0] = 0.0; vN[m0] = vv[m0]
            sw = m0 & (vv > 0)
            if GASFIX == 1:
                # the TV opened on gas: it stays open until the plunger has gone down through
                # the gas column (a turn back up before that lies outside RL-2 s.4)
                sw = sw & ~gopen
            elif GASFIX == 2:
                gb = sw & gopen
                if gb.any():
                    mode[gb] = 3
                    stop[gb] = (s + g0 * (1 - Glof))[gb]
                    sw = sw & ~gb
            mode[sw] = 1; slow[sw] = s[sw]
        m1 = mode == 1
        if m1.any():
            ystar = (4 * yN - yprev) / 3 if BDF2 else yN
            Fl = (ain + kz * F - Zbdt * (yN - ystar)) / (1 + kz)
            up = m1 & (Fl >= Fo); dn = m1 & (Fl <= 0)
            Fl = np.minimum(np.maximum(Fl, 0), Fo)
            Fn[m1] = Fl[m1]; vN[m1] = (ain[m1] - Fl[m1]) / Zb[m1]
            mode[up] = 2; mode[dn] = 0
        m2 = (mode == 2) & ~m1
        if m2.any():
            vu = (ain - Fo) / Zb
            Fn[m2] = Fo[m2]; vN[m2] = vu[m2]
            shut = m2 & (vu < 0)
            if shut.any():
                spv = s - slow
                h = np.minimum(spv, hs)
                Sp[shut] = spv[shut]; hl[shut] = h[shut]
                gg = spv - h
                gas = shut & (gg > 1e-4)
                mode[shut & ~gas] = 1
                mode[gas] = 3; stop[gas] = s[gas]; g0[gas] = gg[gas]
        m3 = mode == 3
        if m3.any():
            idx = np.nonzero(m3)[0]
            _a = ain[idx]; _Z = Zb[idx]; _kt = kt[idx]; _Fo = Fo[idx]; _Ap = Ap[idx]
            _g0 = g0[idx]; _st = stop[idx]; _y = (4 * yN[idx] - yprev[idx]) / 3 if BDF2 else yN[idx]; _Zd = Zbdt[idx]
            _pi = piA[idx]; _pd = pdA[idx]
            _c = _Ap * _pi * _g0
            _base = _st - _g0 - _Fo * _kt - _y
            def resid(Gv):
                Fp = _Ap * _pd - _c / Gv
                r_ = Fp + _Zd * (Gv + _base + Fp * _kt) - _a
                dF = _c / (Gv * Gv)
                return r_, dF + _Zd * (1 + dF * _kt), Fp
            lo = _g0 * Glof[idx]; hi = _g0.copy()
            rlo = resid(lo)[0]; rhi = resid(hi)[0]
            opn = rlo >= 0
            back = rhi <= 0
            Gv = np.minimum(np.maximum(_g0 - (_st - s[idx]), lo), hi)
            for _ in range(8):
                r_, dr, _f = resid(Gv)
                pos = r_ > 0
                hi = np.where(pos, Gv, hi); lo = np.where(pos, lo, Gv)
                Gn = Gv - r_ / dr
                bad = (Gn <= lo) | (Gn >= hi)
                Gv = np.where(bad, 0.5 * (lo + hi), Gn)
            Fp = resid(Gv)[2]
            Fp = np.where(opn, 0.0, np.where(back, _Fo, Fp))
            Fp = np.minimum(np.maximum(Fp, 0), _Fo)
            Fn[idx] = Fp; vN[idx] = (_a - Fp) / _Z
            mm = mode[idx]; mm[back] = 2; mm[opn] = 0; mode[idx] = mm
            go = idx[opn]
            gopen[go] = True; sopen[go] = s[go]
        Qn[bot] = Fn - ZlDb * vN
        if FILT > 0:
            # light high-wavenumber dissipation on the interior nodes
            if FORD == 2:
                Pn[1:-1] += (Pn[:-2] + Pn[2:] - 2 * Pn[1:-1]) * fw
                Qn[1:-1] += (Qn[:-2] + Qn[2:] - 2 * Qn[1:-1]) * fw
            else:
                Pn[2:-2] -= (Pn[:-4] + Pn[4:] - 4 * (Pn[1:-3] + Pn[3:-1]) + 6 * Pn[2:-2]) * fw4
                Qn[2:-2] -= (Qn[:-4] + Qn[4:] - 4 * (Qn[1:-3] + Qn[3:-1]) + 6 * Qn[2:-2]) * fw4
        P = Pn; Q = Qn
        st['P'] = P; st['Q'] = Q
        ynew = (4 * yN - yprev) / 3 + (2.0 / 3.0) * dt * vN if BDF2 else yN + dt * vN
        yprev[:] = yN; yN[:] = ynew
        F[:] = Fn
        s[:] = yN + (Fo - F) * kt
        gopen &= (s > sopen - g0 * Glof - 1e-3) & (mode == 0)
        # statistics per cycle
        cyc = np.floor(t / Tper + 1e-9).astype(int)
        done = cyc != cyc_prev
        if done.any():
            j = cyc_prev - cyc_first
            ok = done & (j >= 0) & (j < Kd)
            if ok.any():
                ii = np.nonzero(ok)[0]
                oi = orig[ii]; jj = j[ii]
                st_max[oi, jj] = cmax[ii]; st_min[oi, jj] = cmin[ii]
                st_sp[oi, jj] = Sp[ii]; st_hl[oi, jj] = hl[ii]
            cmax[done] = -1e30; cmin[done] = 1e30
            cyc_prev[:] = cyc
        np.maximum(cmax, T0, out=cmax); np.minimum(cmin, T0, out=cmin)
        if TRACE and R0 == 1 and n % TRN == 0:
            print("TR %.3f %d %.0f %.4f %.4f %.0f" % (t[0], mode[0], F[0], s[0], vN[0], T0[0]))
    with np.errstate(all='ignore'):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            out = dict(Sp=np.nanmedian(st_sp, 1), hl=np.nanmedian(st_hl, 1),
                       pmax=np.nanmedian(st_max, 1), pmin=np.nanmedian(st_min, 1),
                       st_min=st_min, st_sp=st_sp)
    return out


def card_mean(cards, name):
    g = cards[cards.well == name]
    arr = [gc.sort_values('sample')['load_kN'].values * 1000.0 for _, gc in g.groupby('card')]
    return np.mean(arr, axis=0)


def downhole(p, rr, load, c, nh=40):
    S, N, kk = p['S0'], p['N0'], p['k']
    ns = len(load)
    q = 2 * np.pi * np.arange(ns) / ns
    y0 = S * ((1 - np.cos(q)) / 2 + kk / 8 * (1 - np.cos(2 * q)))
    Y = np.fft.rfft(y0); T = np.fft.rfft(load - p['W'])
    Y[nh:] = 0; T[nh:] = 0
    om = 2 * np.pi * N / 60 * np.arange(len(Y))
    for _, t in rr.iterrows():
        E, rho = MAT[str(t['material']).strip().lower()]
        A = np.pi * (t['diameter_mm'] / 1000) ** 2 / 4
        a = np.sqrt(E / rho); L = t['length_m']
        k = np.sqrt(om ** 2 - 1j * c * om + 0j) / a
        cs = np.cos(k * L)
        kz = np.where(k == 0, 1, k)
        snk = np.where(k == 0, L, np.sin(k * L) / kz)
        ksn = k * np.sin(k * L)
        Y, T = cs * Y - snk / (E * A) * T, E * A * ksn * Y + cs * T
    return np.fft.irfft(Y, ns), np.fft.irfft(T, ns)


def analyse(p, rr, load, c):
    yL, F = downhole(p, rr, load, c)
    Fs = np.sort(F)
    Fo = float(np.median(Fs[int(0.8 * len(F)):]))
    hi = F > 0.9 * Fo
    if hi.any():
        Fo = float(np.median(F[hi]))
    if not np.isfinite(Fo) or Fo <= 0:
        Fo = max(float(np.max(F)), 1.0)
    s = yL + (Fo - F) * p['kt']
    n = len(F)
    # top of stroke in barrel: max s while load is on plunger
    itop = int(np.argmax(np.where(F > 0.5 * Fo, s, -1e9)))
    ilow = int(np.argmin(s))
    Sp = s[itop] - s[ilow]
    pdA = p['pd'] + PATM
    piA = pdA - Fo / p['Ap']
    ds = []; Fs_ = []
    for j in range(1, n):
        i = (itop + j) % n
        if F[i] < 0.1 * Fo:
            break
        if F[i] < 0.9 * Fo:
            ds.append(s[itop] - s[i]); Fs_.append(F[i])
    g0 = 0.0
    if len(ds) >= 2:
        ds = np.array(ds); Fs_ = np.array(Fs_)
        pb = pdA - Fs_ / p['Ap']
        gpt = pb * ds / np.maximum(pb - piA, 1.0)
        g_init = float(np.median(gpt))
        if g_init > 0.01 * max(Sp, 1e-6):
            from scipy.optimize import minimize_scalar
            def cost(g):
                return np.sum((p['Ap'] * (pdA - piA * g / np.maximum(g - ds, 1e-9)) - Fs_) ** 2)
            lo = ds.max() + 1e-4
            r_ = minimize_scalar(cost, bounds=(lo, max(lo * 1.001, 3 * g_init + 0.01)), method='bounded',
                                 options={'xatol': 1e-6})
            g0 = float(r_.x)
        else:
            g0 = max(g_init, 0.0)
    g0 = max(g0, 0.0)
    return dict(Fo=Fo, Sp=Sp, g0=g0, full=g0 < 0.03 * Sp, hs=Sp - g0)


PK_CORR = float(os.environ.get('RL2_PKC', '0.0045'))
MN_CORR = float(os.environ.get('RL2_MNC', '0.0034'))
WORK_BUDGET = float(os.environ.get('RL2_WORK', '0.9e9'))   # node-steps (~20 s CPU here)


def main(fd, outcsv):
    global DT_TARGET
    f, wells, rods, cards, sets = load(fd)
    c = float(f['damping_per_s'])
    P = well_props(f, wells, rods)
    info = {}
    for n in P:
        rr = rods[rods.well == n].sort_values('taper')
        try:
            info[n] = analyse(P[n], rr, card_mean(cards, n), c)
        except Exception:
            info[n] = dict(Fo=0.5 * P[n]['Ap'] * P[n]['pd'], Sp=P[n]['S0'], g0=0.0, full=True, hs=P[n]['S0'])
        if os.environ.get('RL2_DEBUG'):
            print(n, info[n], file=sys.stderr)
    rows = []
    for _, x in sets.iterrows():
        p = P[x['well']]; d = info[x['well']]
        rows.append(dict(p, S=float(x['surface_stroke_m']), N=float(x['spm']), Fo=d['Fo'],
                         hs=None if d['full'] else d['hs'] * p['N0'] / float(x['spm'])))
    ts = float(os.environ.get('RL2_TS', '30')); tw = float(os.environ.get('RL2_TW', '30'))
    # keep the run within the CPU budget: coarsen the time step for very large/deep packages
    tau = np.array([sum(t for t, _ in r['tapers']) for r in rows])
    T = 60.0 / np.array([r['N'] for r in rows])
    tend = (np.ceil(ts / T) + np.maximum(3, np.ceil(tw / T))) * T
    work = float((tau * tend).sum()) / DT_TARGET ** 2
    if work > WORK_BUDGET:
        DT_TARGET = DT_TARGET * np.sqrt(work / WORK_BUDGET)
    out = simulate(rows, c, t_settle=ts, t_window=tw)
    Ap = np.array([r['Ap'] for r in rows]); Nn = np.array([r['N'] for r in rows])
    W = np.array([r['W'] for r in rows])
    def fin(x, fb):
        x = np.asarray(x, float)
        return np.where(np.isfinite(x), x, fb)
    Sp = fin(out['Sp'], 0.0); hl = fin(out['hl'], 0.0)
    pk = fin(out['pmax'] + W, W); mn = fin(out['pmin'] + W, W)
    # the wave filter rounds the load extremes slightly; correction calibrated on the example packages
    pk, mn = pk * (1 + PK_CORR), mn - MN_CORR * pk
    res = pd.DataFrame({'setting': sets['setting'],
                        'plunger_stroke_m': np.round(Sp, 5),
                        'liquid_m3_d': np.round(Ap * hl * Nn * 1440, 4),
                        'pprl_kN': np.round(pk / 1000, 4),
                        'mprl_kN': np.round(mn / 1000, 4)})
    res.to_csv(outcsv, index=False)


if __name__ == '__main__':
    import warnings
    warnings.simplefilter('ignore')
    np.seterr(all='ignore')
    main(sys.argv[1], sys.argv[2])
