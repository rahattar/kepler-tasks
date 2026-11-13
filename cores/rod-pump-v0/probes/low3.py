#!/usr/bin/env python3
"""Rod-pumped well setting-table calculation to RL-2, Issue 4.

Usage: python3 rodlift.py FIELD_DIR OUT_CSV

Model: the rod string (RL-2 s.2) is linear and solved exactly in the frequency
domain (transfer matrices per taper).  The periodic response of the plunger to
the pump load is expressed as a sampled periodic impulse response, and the
nonlinear pump/tubing boundary (s.4, s.5) is solved by sweeping the cycle in
time until it is periodic.  Fluid load and liquid supply (s.6) are found by
fitting the model to the dynamometer cards at the found setting.
"""
import sys, os, json
import numpy as np
import pandas as pd

G = 9.80665
MAT = {'steel': (200e9, 8000.0), 'fibreglass': (50e9, 2400.0)}
TUB_ID = {60.3: 50.7, 73.0: 62.0, 88.9: 76.0}
E_T = 200e9
M = 256          # samples per cycle in the solver
R = 8            # oversampling for impulse responses


def transfer(tapers, omega, c):
    """Return M11,M12,M21,M22 arrays (len omega) of [y,T](L) = M [y,T](0)."""
    m11 = np.ones_like(omega, dtype=complex); m12 = np.zeros_like(m11)
    m21 = np.zeros_like(m11); m22 = np.ones_like(m11)
    for E, rho, A, l in tapers:
        k2 = (rho / E) * (omega ** 2 - 1j * c * omega)
        k = np.sqrt(k2)
        kl = k * l
        cs = np.cos(kl)
        small = np.abs(kl) < 1e-8
        kk = np.where(small, 1.0, k)
        sk = np.where(small, l, np.sin(kl) / kk)          # sin(kl)/k
        ks = np.where(small, 0.0, k * np.sin(kl))         # k sin(kl)
        a11, a12, a21, a22 = cs, -sk / (E * A), E * A * ks, cs
        m11, m12, m21, m22 = (a11 * m11 + a12 * m21, a11 * m12 + a12 * m22,
                              a21 * m11 + a22 * m21, a21 * m12 + a22 * m22)
    return m11, m12, m21, m22


class Well:
    pass


def load_package(d):
    f = json.load(open(os.path.join(d, 'field.json')))
    wells = pd.read_csv(os.path.join(d, 'wells.csv'))
    rods = pd.read_csv(os.path.join(d, 'rods.csv'))
    out = {}
    rho_l = float(f['liquid_density_kg_m3'])
    for _, r in wells.iterrows():
        w = Well()
        w.name = str(r['well'])
        w.L = float(r['pump_depth_m'])
        w.Ap = np.pi * (float(r['plunger_mm']) / 1000) ** 2 / 4
        od = float(r['tubing_od_mm'])
        idd = min(TUB_ID.items(), key=lambda kv: abs(kv[0] - od))[1]
        w.At = np.pi * ((od / 1000) ** 2 - (idd / 1000) ** 2) / 4
        anc = r['anchor_depth_m']
        if pd.isna(anc) or str(anc).strip() == '':
            Lf = w.L
            w.anchor = None
        else:
            Lf = min(w.L, max(0.0, w.L - float(anc)))
            w.anchor = float(anc)
        w.tau = Lf / (E_T * w.At)
        w.pd = float(r['tubing_head_pressure_kPa']) * 1e3 + rho_l * G * w.L
        w.k = float(r['unit_factor'])
        w.S0 = float(r['found_surface_stroke_m'])
        w.N0 = float(r['found_spm'])
        rr = rods[rods['well'].astype(str) == w.name].sort_values('taper')
        tp = []
        W = 0.0
        for _, t in rr.iterrows():
            E, rho = MAT[str(t['material']).strip().lower()]
            A = np.pi * (float(t['diameter_mm']) / 1000) ** 2 / 4
            l = float(t['length_m'])
            tp.append((E, rho, A, l))
            W += A * l * G * (rho - rho_l)
        # rod string reaches the pump: scale lengths if records disagree
        tot = sum(t[3] for t in tp)
        if tot > 0 and abs(tot - w.L) > 1e-6:
            sc = w.L / tot
            tp = [(E, rho, A, l * sc) for E, rho, A, l in tp]
            W = sum(A * l * G * (rho - rho_l) for E, rho, A, l in tp)
        w.tapers = tp
        w.W = W
        out[w.name] = w
    return f, out


def prep(w, S, N, c):
    """Linear response pieces for one setting, sampled at M points."""
    om0 = 2 * np.pi * N / 60
    nh = R * M // 2 + 1
    n = np.arange(nh)
    om = om0 * n
    m11, m12, m21, m22 = transfer(w.tapers, om, c)
    Gf = m12 / m22                 # y_p per unit F_p
    TF = 1.0 / m22                 # T0 per unit F_p
    Hy = m11 - m12 * m21 / m22     # y_p per unit y0
    Ty = -m21 / m22                # T0 per unit y0
    hat = np.sinc(n / M) * np.exp(1j * np.pi * n / M)   # pulse on (t-dt, t]
    h = np.fft.irfft(R * Gf * hat, R * M)[::R]
    hT = np.fft.irfft(R * TF * hat, R * M)[::R]
    # y0 = S[(1/2+k/8) - 1/2 cos q - k/8 cos 2q]
    q = 2 * np.pi * np.arange(M) / M
    c0 = S * (0.5 + w.k / 8)
    c1 = -S / 2
    c2 = -S * w.k / 8
    y0 = c0 + c1 * np.cos(q) + c2 * np.cos(2 * q)
    a = (c0 * Hy[0].real + (c1 * Hy[1] * np.exp(1j * q)).real
         + (c2 * Hy[2] * np.exp(2j * q)).real)
    aT = (c0 * Ty[0].real + (c1 * Ty[1] * np.exp(1j * q)).real
          + (c2 * Ty[2] * np.exp(2j * q)).real)
    return h, hT, a, aT, y0


def well_dt(w, dt0):
    """A time step near dt0 that keeps every taper's Courant number close to 1."""
    best = (-1.0, dt0)
    for E, rho, A, l in w.tapers:
        a = np.sqrt(E / rho)
        n0 = l / (a * dt0)
        for nc in range(max(1, int(n0 * 0.8)), int(n0 * 1.25) + 2):
            dt = l / (a * nc)
            if dt > dt0 * 1.25 or dt < dt0 * 0.8:
                continue
            cr = []
            for E2, rho2, A2, l2 in w.tapers:
                a2 = np.sqrt(E2 / rho2)
                n2 = max(1, int(np.floor(l2 / (a2 * dt) + 1e-9)))
                cr.append(a2 * dt * n2 / l2)
            sc = min(cr) - 0.02 * abs(np.log(dt / dt0))
            if sc > best[0]:
                best = (sc, dt)
    return best[1]


def build_chain(w, dt):
    """Lumped-mass chain for a well: node masses, cell stiffnesses."""
    ks = []; ms = []
    for E, rho, A, l in w.tapers:
        a = np.sqrt(E / rho)
        nc = max(1, int(np.floor(l / (a * dt) + 1e-9)))
        dx = l / nc
        ks += [E * A / dx] * nc
        ms += [rho * A * dx] * nc
    nn = len(ks) + 1
    mn = np.zeros(nn)
    mn[:-1] += 0.5 * np.array(ms); mn[1:] += 0.5 * np.array(ms)
    return np.array(ks), mn


DT = 0.008
CYC = 5          # (unused)
TMIN = 30.0      # s of settling simulated at least, before the last cycle


def solve(cases, c, dt=None, tmin=None, cyc=None, record=False):
    """Time-domain solution to the steady cycle for each case.
    cases: list of dicts with w,S,N,Fo,hs.  Returns Sp, hl, pprl, mprl (N, N, N, N)."""
    dt0 = dt or DT; tmin = TMIN if tmin is None else tmin; cyc = cyc or CYC
    n = len(cases)
    chains = {}
    for cs in cases:
        w = cs['w']
        if w.name not in chains:
            dtw = dt0
            chains[w.name] = build_chain(w, dtw) + (dtw,)
    dt = np.array([chains[cs['w'].name][2] for cs in cases])
    nmax = max(len(v[1]) for v in chains.values())
    K = np.zeros((n, nmax - 1)); Mn = np.ones((n, nmax)); top = np.zeros(n, dtype=int)
    Fo = np.empty(n); hs = np.empty(n); tau = np.empty(n); Ap = np.empty(n)
    pdv = np.empty(n); Wv = np.empty(n); S = np.empty(n); kf = np.empty(n); om = np.empty(n)
    for i, cs in enumerate(cases):
        w = cs['w']; ks, mn, _ = chains[w.name]
        nn = len(mn); t0 = nmax - nn
        K[i, t0:] = ks; Mn[i, t0:] = mn; top[i] = t0
        Fo[i] = cs['Fo']; hs[i] = cs['hs']; tau[i] = w.tau; Ap[i] = w.Ap
        pdv[i] = w.pd; Wv[i] = w.W; S[i] = cs['S']; kf[i] = w.k; om[i] = 2 * np.pi * cs['N'] / 60
    pi_ = pdv - Fo / Ap
    ApPd = Ap * pdv
    rows = np.arange(n)
    # prescribed region mask: columns <= top are driven
    col = np.arange(nmax)[None, :]
    drv = col <= top[:, None]
    fac = 1.0 / (1 + c * dt / 2)
    cm = (1 - c * dt / 2)
    f2 = (2 * fac)[:, None]; fc = (cm * fac)[:, None]
    dt2m = (dt * dt * fac)[:, None] / Mn
    beta = dt2m[:, -1]
    gco = -(beta + tau)
    ytop_m = Mn[rows, top]

    def y0f(t):
        q = om * t
        return S * ((1 - np.cos(q)) / 2 + kf / 8 * (1 - np.cos(2 * q)))

    def a0f(t):
        q = om * t
        return S * om * om * (np.cos(q) / 2 + kf / 2 * np.cos(2 * q))

    def v0f(t):
        q = om * t
        return S * om * (np.sin(q) / 2 + kf / 4 * np.sin(2 * q))

    period = 2 * np.pi / om
    T_end = np.maximum(tmin, 2 * period) + period
    nsteps = int(np.ceil((T_end / dt).max())) + 1
    y = np.zeros((n, nmax)); yp = np.zeros((n, nmax))
    state = np.ones(n, dtype=int)
    slock = np.zeros(n); smin = np.zeros(n); stop = np.zeros(n)
    z = np.zeros(n); G0 = np.zeros(n)
    sprev = np.zeros(n)
    Fp = np.zeros(n)
    cyc_idx = np.zeros(n, dtype=int)
    cmax = np.full(n, -np.inf); cmin = np.full(n, np.inf)
    rmax = np.zeros(n); rmin = np.zeros(n); Sp = np.zeros(n); Sp_cur = np.zeros(n)
    Sp_prev = np.zeros(n)
    nlast = np.floor(T_end / period + 1e-9).astype(int) - 1
    rec = np.full((n, 200), np.nan) if record else None
    f = np.zeros((n, nmax)); ten = np.zeros((n, nmax - 1)); ynew = np.zeros((n, nmax))
    tmp = np.zeros((n, nmax))
    Sc = S * om * om; Sv = S * om
    for step in range(1, nsteps):
        t = step * dt
        tc = t - dt
        # forces at time t-dt (current y)
        np.subtract(y[:, :-1], y[:, 1:], out=ten)
        ten *= K
        np.negative(ten, out=f[:, :-1])
        f[:, -1] = -Fp
        f[:, 1:] += ten
        np.multiply(y, f2, out=ynew)
        np.multiply(yp, fc, out=tmp); ynew -= tmp
        np.multiply(dt2m, f, out=tmp); ynew += tmp
        # PRL at time t-dt
        q = om * tc
        cq = np.cos(q); sq = np.sin(q)
        c2q = 2 * cq * cq - 1; s2q = 2 * sq * cq
        acc = Sc * (cq / 2 + kf / 2 * c2q); vel = Sv * (sq / 2 + kf / 4 * s2q)
        prl = Wv + ten[rows, top] + ytop_m * (acc + c * vel)
        cmax = np.maximum(cmax, prl); cmin = np.minimum(cmin, prl)
        if record:
            ph = (tc / period - (nlast - 1)) * 200
            kk = np.rint(ph).astype(int)
            ok = (np.abs(ph - kk) <= 0.5 * dt / period * 200 + 1e-12) & (kk >= 0) & (kk < 200) & (tc <= T_end + 1e-9)
            if ok.any():
                rec[ok, kk[ok]] = prl[ok]
        # pump: ynew[:, -1] currently includes -Fp*beta; remove to get P
        P = ynew[:, -1] + beta * Fp
        B = P + Fo * tau
        st = state
        for _ in range(3):
            F = np.zeros(n); s = B.copy()
            newst = st.copy()
            m = st == 0
            if m.any():
                idx = np.where(m)[0]
                r = idx[B[idx] > sprev[idx]]
                newst[r] = 1; slock[r] = sprev[r]; smin[r] = sprev[r]
            m = (st == 1) | (st == 4)
            if m.any():
                idx = np.where(m)[0]
                Fl = (slock[idx] - B[idx]) / gco[idx]
                newst[idx[Fl < 0]] = 0
                newst[idx[Fl >= Fo[idx]]] = 2
                F[idx] = np.clip(Fl, 0, Fo[idx]); s[idx] = slock[idx]
            m = st == 2
            if m.any():
                idx = np.where(m)[0]
                su = B[idx] + gco[idx] * Fo[idx]
                F[idx] = Fo[idx]; s[idx] = su
                r = idx[su < sprev[idx]]
                if r.size:
                    stop[r] = sprev[r]
                    spv = stop[r] - smin[r]
                    Sp_cur[r] = spv
                    hlv = np.minimum(spv, hs[r])
                    g0 = spv - hlv
                    full = g0 <= 1e-9
                    rf = r[full]; rg = r[~full]
                    newst[rf] = 4; slock[rf] = stop[rf]
                    newst[rg] = 3; z[rg] = smin[rg] + hlv[~full]; G0[rg] = g0[~full]
            m = st == 3
            if m.any():
                idx = np.where(m)[0]
                gg = gco[idx]
                bb = B[idx] - z[idx] + gg * ApPd[idx]
                cc = gg * Ap[idx] * pi_[idx] * G0[idx]
                u = (bb + np.sqrt(np.maximum(bb * bb - 4 * cc, 0))) / 2
                Fg = ApPd[idx] - Ap[idx] * pi_[idx] * G0[idx] / np.maximum(u, 1e-12)
                lo = Fg <= 0; hi = Fg >= Fo[idx]
                newst[idx[lo]] = 0
                newst[idx[hi]] = 2
                F[idx] = np.clip(Fg, 0, Fo[idx])
                s[idx] = np.where(lo, B[idx], np.where(hi, B[idx] + gg * Fo[idx], z[idx] + u))
            if np.array_equal(newst, st):
                break
            st = newst
        state = st
        sprev = s
        Fp = F
        ynew[:, -1] = P - beta * F
        # driven nodes
        ynew[rows, top] = y0f(t)
        yp, y, ynew = y, ynew, yp
        # cycle bookkeeping
        ci = np.floor(t / period + 1e-9).astype(int)
        wrap = ci > cyc_idx
        if wrap.any():
            rmax[wrap] = cmax[wrap]; rmin[wrap] = cmin[wrap]
            Sp_prev[wrap] = Sp[wrap]; Sp[wrap] = Sp_cur[wrap]
            cmax[wrap] = -np.inf; cmin[wrap] = np.inf
            cyc_idx = ci
    hl = np.minimum(Sp, hs)
    if record:
        # fill any unsampled points by periodic interpolation
        for i in np.where(np.isnan(rec).any(1))[0]:
            g = ~np.isnan(rec[i]); xs = np.arange(200)
            rec[i] = np.interp(xs, xs[g], rec[i][g], period=200)
        return Sp, hl, rmax, rmin, rec
    return Sp, hl, rmax, rmin


def fit_wells(wells, cards, c):
    names = list(wells)
    meas = {}
    for nm in names:
        cw = cards[cards['well'].astype(str) == nm]
        L = []
        for cid, cc in cw.groupby('card'):
            cc = cc.sort_values('sample')
            L.append(cc['load_kN'].values * 1e3)
        meas[nm] = np.mean(L, axis=0)
    # stage A: downhole card from the surface card (linear rod string)
    Fo = {}; hs = {}
    for nm in names:
        w = wells[nm]
        cw = cards[cards['well'].astype(str) == nm]
        pos = cw.groupby('sample')['position_m'].mean().values
        T0 = meas[nm] - w.W
        nh = 25
        om = 2 * np.pi * w.N0 / 60 * np.arange(nh)
        m11, m12, m21, m22 = transfer(w.tapers, om, c)
        Y = np.fft.rfft(pos)[:nh]; T = np.fft.rfft(T0)[:nh]
        nf = len(pos) // 2 + 1
        yp = np.fft.irfft(np.r_[m11 * Y + m12 * T, np.zeros(nf - nh)], len(pos))
        Fp = np.fft.irfft(np.r_[m21 * Y + m22 * T, np.zeros(nf - nh)], len(pos))
        fo = float(np.percentile(Fp, 90))
        fo = min(max(fo, 0.05 * w.Ap * w.pd), 0.999 * w.Ap * w.pd)
        # free tubing length from the load pick-up at the bottom of the stroke,
        # where the plunger stands still in the barrel and the rods take the load
        # off the tubing: the plunger rises with the tubing by tau * Fo.
        npt = len(Fp)
        i9 = int(np.argmax(Fp > 0.9 * fo))
        j = i9
        while j > i9 - npt + 1 and Fp[j % npt] > 0.1 * fo:
            j -= 1
        idx = np.arange(j, i9 + 1) % npt
        sel = idx[(Fp[idx] > 0.15 * fo) & (Fp[idx] < 0.85 * fo)]
        if len(sel) >= 4:
            tau_e = np.polyfit(Fp[sel], yp[sel], 1)[0]
            Lf_e = tau_e * E_T * w.At
            cand = [w.L] + ([min(w.L, max(0.0, w.L - w.anchor))] if w.anchor is not None else [])
            dist = [abs(Lf_e - x) for x in cand]
            k = int(np.argmin(dist))
            if dist[k] > max(150.0, 0.3 * w.L):
                Lf = min(w.L, max(0.0, Lf_e))
            else:
                Lf = cand[k]
            w.tau = Lf / (E_T * w.At)
            w.Lf_est = Lf_e
        sp = yp + (fo - Fp) * w.tau
        it = int(np.argmax(sp))
        smin = sp.min()
        Spe = sp[it] - smin
        pi_ = w.pd - fo / w.Ap
        pb = w.pd - 0.1 * fo / w.Ap
        seq = np.r_[np.arange(it, len(sp)), np.arange(0, it)]
        j = next((k for k in seq if Fp[k] < 0.1 * fo), it)
        dlt = max(sp[it] - sp[j], 0.0)
        G0 = dlt / max(1 - pi_ / pb, 1e-6)
        Fo[nm] = fo
        hs[nm] = np.inf if G0 < 0.03 * Spe else max(Spe - G0, 0.05 * Spe)
    # stage B: damped Gauss-Newton on (Fo, hs), keeping the best point
    dF = 0.005; dh = 0.01
    best = {nm: (np.inf, Fo[nm], hs[nm]) for nm in names}
    lam = {nm: 1.0 for nm in names}
    step = {nm: (0.0, 0.0) for nm in names}
    for it in range(6):
        cases = []
        for nm in names:
            w = wells[nm]
            h0 = hs[nm]
            hp = (h0 if np.isfinite(h0) else 0.97 * w.S0) - dh * w.S0
            cases += [dict(w=w, S=w.S0, N=w.N0, Fo=Fo[nm], hs=h0),
                      dict(w=w, S=w.S0, N=w.N0, Fo=Fo[nm] * (1 + dF), hs=h0),
                      dict(w=w, S=w.S0, N=w.N0, Fo=Fo[nm], hs=hp)]
        Sp, _, _, _, rec = solve(cases, c, record=True)
        for k, nm in enumerate(names):
            w = wells[nm]
            r0 = rec[3 * k] - meas[nm]
            sse = float(np.dot(r0, r0))
            if sse < best[nm][0]:
                best[nm] = (sse, Fo[nm], hs[nm]); lam[nm] = min(1.0, lam[nm] * 2)
            else:
                lam[nm] *= 0.3
                _, f0, h0 = best[nm]
                d1, d2 = step[nm]
                Fo[nm] = f0 + lam[nm] * d1
                hs[nm] = h0 + lam[nm] * d2 if np.isfinite(h0) and np.isfinite(d2) else h0
                continue
            J1 = (rec[3 * k + 1] - rec[3 * k]) / (Fo[nm] * dF)
            rg = rec[3 * k + 2] - meas[nm]
            if not np.isfinite(hs[nm]):
                hp = 0.97 * w.S0 - dh * w.S0
                if np.dot(rg, rg) < sse and hp < Sp[3 * k]:
                    step[nm] = (0.0, 0.0)
                    hs[nm] = hp
                    continue
                d1 = -np.dot(J1, r0) / np.dot(J1, J1)
                step[nm] = (d1, 0.0)
                Fo[nm] += lam[nm] * d1
                continue
            J2 = -(rec[3 * k + 2] - rec[3 * k]) / (dh * w.S0)
            if np.linalg.norm(J2) * w.S0 < 1e-4 * np.linalg.norm(J1) * Fo[nm]:
                d1 = -np.dot(J1, r0) / np.dot(J1, J1); d2 = 0.0
            else:
                d, *_ = np.linalg.lstsq(np.stack([J1, J2], 1), -r0, rcond=None)
                d1 = float(np.clip(d[0], -0.3 * Fo[nm], 0.3 * Fo[nm]))
                d2 = float(np.clip(d[1], -0.3 * w.S0, 0.3 * w.S0))
            step[nm] = (d1, d2)
            Fo[nm] += lam[nm] * d1
            hs[nm] = max(hs[nm] + lam[nm] * d2, 0.02 * w.S0)
    for nm in names:
        Fo[nm], hs[nm] = best[nm][1], best[nm][2]
    cases = [dict(w=wells[nm], S=wells[nm].S0, N=wells[nm].N0, Fo=Fo[nm], hs=hs[nm]) for nm in names]
    Sp, _, _, _, rec = solve(cases, c, record=True)
    res = {}
    for i, nm in enumerate(names):
        gas = Sp[i] - min(Sp[i], hs[nm])
        full = gas < 0.03 * Sp[i]
        rms = np.sqrt(np.mean((rec[i] - meas[nm]) ** 2))
        res[nm] = (Fo[nm], np.inf if full else hs[nm], full, gas / Sp[i], rms)
    return res


def main():
    d, outp = sys.argv[1], sys.argv[2]
    f, wells = load_package(d)
    c = float(f['damping_per_s'])
    cards = pd.read_csv(os.path.join(d, 'cards.csv'))
    sets = pd.read_csv(os.path.join(d, 'settings.csv'))
    fit = fit_wells(wells, cards, c)
    if os.environ.get('RODLIFT_DEBUG'):
        for nm, v in fit.items():
            print(nm, '%.1f' % v[0], v[1], v[2], '%.3f' % v[3], 'rms %.0f' % v[4], file=sys.stderr)
    cases = []
    for _, r in sets.iterrows():
        w = wells[str(r['well'])]
        Fo, hs = fit[w.name][:2]
        cases.append(dict(w=w, S=float(r['surface_stroke_m']), N=float(r['spm']), Fo=Fo, hs=hs * w.N0 / float(r['spm'])))
    Sp, hl, pp, mp = solve(cases, c)
    Ap = np.array([cs['w'].Ap for cs in cases]); N = np.array([cs['N'] for cs in cases])
    Sp = np.nan_to_num(np.maximum(Sp, 0.0)); hl = np.nan_to_num(np.clip(hl, 0.0, None))
    hl = np.minimum(hl, Sp)
    liq = Ap * hl * N * 1440
    pp = np.nan_to_num(pp); mp = np.nan_to_num(mp)
    out = pd.DataFrame(dict(setting=sets['setting'], plunger_stroke_m=np.round(Sp, 5),
                            liquid_m3_d=np.round(liq, 4), pprl_kN=np.round(pp / 1e3, 4),
                            mprl_kN=np.round(mp / 1e3, 4)))
    out.to_csv(outp, index=False)


if __name__ == '__main__':
    main()
