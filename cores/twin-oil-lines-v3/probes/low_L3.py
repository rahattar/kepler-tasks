#!/usr/bin/env python3
"""TS-2 heated oil transfer lines: pressure drop and outlet temperature for each record of a site package.

Usage: python3 lines.py PACKAGE_DIR OUT_CSV
"""
import os
import subprocess
import sys

import numpy as np
import pandas as pd
from scipy.optimize import brentq

NZ = 16
C3 = 3.66 ** 3 + 0.7 ** 3
LN10 = np.log(10.0)


# ---------------------------------------------------------------- oil (TS-2 section 2)
def oil_consts(row):
    T1, T2 = 323.15, 373.15
    y1 = np.log10(np.log10(row.nu50_cSt + 0.7))
    y2 = np.log10(np.log10(row.nu100_cSt + 0.7))
    B = (y1 - y2) / (np.log10(T2) - np.log10(T1))
    A = y1 + B * np.log10(T1)
    return dict(A=A, B=B, rho=float(row.density_kg_m3), cp=float(row.cp_J_kgK), k=float(row.k_W_mK))


def nu_m2s(A, B, Tc):
    return (10.0 ** (10.0 ** (A - B * np.log10(Tc + 273.15))) - 0.7) * 1e-6


# ---------------------------------------------------------------- one pipe (TS-2 section 3)
def pipe(P, D, Uo, m, Tin, Ta, nz=NZ, tw_iter=2):
    """Vectorised over all arguments. P: dict of oil constants and L (arrays or scalars).
    Returns pressure drop [Pa] and outlet bulk temperature [C]."""
    shape = np.broadcast(D, Uo, m, Tin, Ta, P['A'], P['L']).shape
    bc = lambda v: np.broadcast_to(np.asarray(v, float), shape)
    A, B, rho, cp, k, L = (bc(P[n]) for n in ('A', 'B', 'rho', 'cp', 'k', 'L'))
    D, Uo, m, Tin, Ta = bc(D), bc(Uo), bc(m), bc(Tin), bc(Ta)
    a1 = LN10 * A
    b1 = B / LN10 * LN10      # B, kept for clarity: log10(T) = ln(T)/ln10
    rhoe = rho * 1e-6

    def mu(Tc):   # dynamic viscosity, Pa s (ASTM D341, 2.2)
        return rhoe * (np.exp(LN10 * np.exp(a1 - b1 * np.log(Tc + 273.15))) - 0.7)

    u = 4.0 * m / (np.pi * D * D * rho)
    RePrD = u * D * D * cp * rho / k   # Re Pr D (the viscosity cancels)
    kD = k / D
    piDU = np.pi * D * Uo
    UTa = Uo * Ta
    inv_mcp = 1.0 / (m * cp)
    cdp = 32.0 * u / (D * D)
    cg = 1.077 * np.cbrt(RePrD / L)
    st = [None]

    def rhs(z, Tb):
        zz = max(z, 1e-6)
        dxdz = 3.0 * L * zz * zz
        Tb = np.maximum(Tb, Ta)
        mub = mu(Tb)
        base = np.cbrt(C3 + (cg / zz - 0.7) ** 3) * kD    # Gz^(1/3) = (RePrD / L)^(1/3) / z
        Tw = st[0] if st[0] is not None else Tb
        for _ in range(tw_iter):
            muw = mu(Tw)
            h = base * (mub / muw) ** 0.14
            Tw = (h * Tb + UTa) / (h + Uo)
        st[0] = Tw
        muw = mu(Tw)
        dT = -piDU * (Tw - Ta) * inv_mcp * dxdz
        dP = cdp * np.sqrt(mub * muw) * dxdz
        return dT, dP

    hz = 1.0 / nz
    Tb = Tin.copy()
    Pd = np.zeros(shape)
    z = 0.0
    for _ in range(nz):
        k1, p1 = rhs(z, Tb)
        k2, p2 = rhs(z + hz / 2, Tb + hz / 2 * k1)
        k3, p3 = rhs(z + hz / 2, Tb + hz / 2 * k2)
        k4, p4 = rhs(z + hz, Tb + hz * k3)
        Tb = Tb + hz / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        Pd = Pd + hz / 6 * (p1 + 2 * p2 + 2 * p3 + p4)
        z += hz
    return Pd, np.maximum(Tb, Ta)


# ---------------------------------------------------------------- survey interpretation (TS-2 section 5)
def illinois(f, lo, hi, flo, fhi, iters):
    """Vectorised Illinois regula falsi on brackets [lo, hi] (flo, fhi of opposite sign)."""
    side = np.zeros(lo.shape)
    for _ in range(iters):
        den = fhi - flo
        x = np.where(den != 0, (lo * fhi - hi * flo) / np.where(den != 0, den, 1.0), 0.5 * (lo + hi))
        x = np.where((x > np.minimum(lo, hi)) & (x < np.maximum(lo, hi)), x, 0.5 * (lo + hi))
        fx = f(x)
        left = np.sign(fx) == np.sign(flo)
        # replace lo when same sign as flo
        nlo = np.where(left, x, lo)
        nflo = np.where(left, fx, flo)
        nhi = np.where(left, hi, x)
        nfhi = np.where(left, fhi, fx)
        nfhi = np.where(left & (side == 1), nfhi * 0.5, nfhi)
        nflo = np.where(~left & (side == -1), nflo * 0.5, nflo)
        side = np.where(left, 1, -1)
        lo, hi, flo, fhi = nlo, nhi, nflo, nfhi
    return np.where(np.abs(flo) < np.abs(fhi), lo, hi)


def fit_U_vec(P, D, m, tin, tout, ta):
    """Outside coefficient for which section 3 gives the outlet temperature read (TS-2 5.2), vectorised."""
    D, m, tin, tout, ta = (np.atleast_1d(np.asarray(v, float)) for v in (D, m, tin, tout, ta))
    n = len(m)
    Pc = {kk: np.broadcast_to(np.asarray(v, float), (n,))[:, None] for kk, v in P.items()}
    grid = np.exp(np.linspace(np.log(0.05), np.log(150.0), 28))
    G = grid[None, :].repeat(n, 0)
    r = pipe(Pc, D[:, None], G, m[:, None], tin[:, None], ta[:, None])[1] - tout[:, None]
    # r decreases with U
    lo = np.empty(n); hi = np.empty(n); flo = np.empty(n); fhi = np.empty(n)
    for i in range(n):
        ch = np.where((r[i, :-1] > 0) & (r[i, 1:] <= 0))[0]
        c = ch[0] if len(ch) else (0 if r[i, 0] < 0 else len(grid) - 2)
        lo[i], hi[i], flo[i], fhi[i] = G[i, c], G[i, c + 1], r[i, c], r[i, c + 1]
    Pf = {kk: v[:, 0] for kk, v in Pc.items()}
    f = lambda U: pipe(Pf, D, U, m, tin, ta)[1] - tout
    return illinois(f, lo, hi, flo, fhi, 9)


def fit_U(P, D, m, tin, tout, ta):
    return float(fit_U_vec(P, D, m, tin, tout, ta)[0])


def dp_of(P, D, U, m, tin, ta):
    return float(pipe(P, D, U, m, tin, ta)[0])


def pair_fit(P, Dlaid, Dcur, obs, Ufix, fouled_hint=None, tol=0.01, U0=None):
    """obs[i] = (m, tin, ta, tout or None) for pipes 0 (A) and 1 (B); Ufix[i] = known U if tout is None.
    Dcur: starting bores. Returns bores, U, and the index of the pipe whose bore was fitted (or None)."""
    D = list(Dcur)

    def Us(D):
        return [fit_U(P, D[i], obs[i][0], obs[i][1], obs[i][3], obs[i][2]) if obs[i][3] is not None else Ufix[i]
                for i in (0, 1)]

    def mism(D):
        U = Us(D)
        pa = dp_of(P, D[0], U[0], obs[0][0], obs[0][1], obs[0][2])
        pb = dp_of(P, D[1], U[1], obs[1][0], obs[1][1], obs[1][2])
        return pa / pb - 1.0, U

    if U0 is not None:
        pa = dp_of(P, D[0], U0[0], obs[0][0], obs[0][1], obs[0][2])
        pb = dp_of(P, D[1], U0[1], obs[1][0], obs[1][1], obs[1][2])
        r, U = pa / pb - 1.0, list(U0)
    else:
        r, U = mism(D)
    if abs(r) <= tol and fouled_hint is None:
        return D, U, None
    i = fouled_hint if fouled_hint is not None else (0 if r < 0 else 1)
    sgn = 1.0 if i == 0 else -1.0   # residual increases as bore i shrinks

    def g(d):
        DD = list(D)
        DD[i] = d
        return sgn * mism(DD)[0]

    hi = Dlaid
    lo = 0.4 * Dlaid
    ghi, glo = g(hi), g(lo)
    if ghi * glo > 0:
        if abs(r) <= tol:
            return D, U, None
        d = hi if abs(ghi) < abs(glo) else lo
    else:
        d = brentq(g, lo, hi, xtol=1e-7 * Dlaid)
    D[i] = d
    return D, Us(D), i


# ---------------------------------------------------------------- crew
def order_survey(pkg, pipes):
    if not pipes:
        return {}
    try:
        out = subprocess.run(['heatsurvey', pkg] + list(pipes), capture_output=True, text=True, timeout=30)
    except Exception:
        return {}
    if out.returncode != 0:
        return {}
    rows = {}
    lines = [l.strip() for l in out.stdout.splitlines() if l.strip()]
    for l in lines[1:]:
        p = l.split(',')
        if len(p) < 6:
            continue
        try:
            rows[p[0]] = dict(line_flow_t_h=float(p[1]), flow_t_h=float(p[2]), t_in_C=float(p[3]),
                              t_out_C=float(p[4]), t_amb_C=float(p[5]))
        except ValueError:
            pass
    return rows


# ---------------------------------------------------------------- pair division (TS-2 section 4)
def solve_pairs(Pv, DA, DB, UA, UB, m, Tin, Ta, s0):
    """Vectorised over lines of one hour. s0 = previous fraction in A, or nan for the opening record."""
    n = len(m)
    eps = 1e-3

    def g(s, idx):
        sub = {kk: v[idx][:, None] for kk, v in Pv.items()}
        mm, ti, ta = m[idx][:, None], Tin[idx][:, None], Ta[idx][:, None]
        K = s.shape[1]
        one = np.ones((1, K))
        Dc = np.concatenate([DA[idx][:, None] * one, DB[idx][:, None] * one], axis=1)
        Uc = np.concatenate([UA[idx][:, None] * one, UB[idx][:, None] * one], axis=1)
        pp, tt = pipe(sub, Dc, Uc, np.concatenate([s * mm, (1 - s) * mm], axis=1), ti, ta)
        pa, pb, ta_out, tb_out = pp[:, :K], pp[:, K:], tt[:, :K], tt[:, K:]
        return pa - pb, pa, pb, ta_out, tb_out

    lo = np.full(n, np.nan)
    hi = np.full(n, np.nan)
    glo = np.full(n, np.nan)
    ghi = np.full(n, np.nan)
    first = np.isnan(s0)
    if first.any():
        # opening record: one division only satisfies 4.1 (4.3); dense grid
        idx = np.where(first)[0]
        grid = np.linspace(eps, 1 - eps, 121)[None, :].repeat(len(idx), 0)
        gv = g(grid, idx)[0]
        for j, ii in enumerate(idx):
            ch = np.where(np.sign(gv[j, :-1]) != np.sign(gv[j, 1:]))[0]
            c = ch[0] if len(ch) else min(int(np.argmin(np.abs(gv[j]))), grid.shape[1] - 2)
            lo[ii], hi[ii], glo[ii], ghi[ii] = grid[j, c], grid[j, c + 1], gv[j, c], gv[j, c + 1]
    cont = ~first
    if cont.any():
        # 4.2: from the previous division oil shifts away from the pipe with the higher pressure drop
        idx = np.where(cont)[0]
        sp = s0[idx]
        steps = np.concatenate([[0.0], 2e-4 * 1.25 ** np.arange(40)])
        steps = steps[steps < 1.0]
        ns = len(steps)
        cand = np.concatenate([np.clip(sp[:, None] - steps[None, :], eps, 1 - eps),
                               np.clip(sp[:, None] + steps[None, :], eps, 1 - eps)], axis=1)
        gv = g(cand, idx)[0]
        for j, ii in enumerate(idx):
            if gv[j, 0] > 0:
                cs, gs = cand[j, :ns], gv[j, :ns]
            else:
                cs, gs = cand[j, ns:], gv[j, ns:]
            sg = np.sign(gs)
            ch = np.where(sg[:-1] != sg[1:])[0]
            if len(ch):
                c = ch[0]
                lo[ii], hi[ii], glo[ii], ghi[ii] = cs[c], cs[c + 1], gs[c], gs[c + 1]
            else:
                c = int(np.argmin(np.abs(gs)))
                lo[ii] = hi[ii] = cs[c]
                glo[ii] = ghi[ii] = gs[c]
    idx = np.arange(n)
    # one refinement scan of the bracket, then linear interpolation
    for _ in range(1):
        t = np.linspace(0.0, 1.0, 41)[None, :]
        cs = lo[:, None] + (hi - lo)[:, None] * t
        gs = g(cs, idx)[0]
        for i in range(n):
            if lo[i] == hi[i]:
                continue
            sg = np.sign(gs[i])
            ch = np.where(sg[:-1] != sg[1:])[0]
            c = ch[0] if len(ch) else min(int(np.argmin(np.abs(gs[i]))), 39)
            lo[i], hi[i], glo[i], ghi[i] = cs[i, c], cs[i, c + 1], gs[i, c], gs[i, c + 1]
    den = ghi - glo
    s = np.where((den != 0) & (lo != hi), lo - glo * (hi - lo) / np.where(den != 0, den, 1.0), lo)
    s = np.clip(s, np.minimum(lo, hi), np.maximum(lo, hi))
    _, pa, pb, ta_out, tb_out = g(s[:, None], idx)
    pa, pb, ta_out, tb_out = pa[:, 0], pb[:, 0], ta_out[:, 0], tb_out[:, 0]
    dp = 0.5 * (pa + pb)
    tout = s * ta_out + (1 - s) * tb_out
    return s, dp, tout


# ---------------------------------------------------------------- main
def main():
    pkg, out_csv = sys.argv[1], sys.argv[2]
    import json
    site = json.load(open(os.path.join(pkg, 'site.json')))
    allowance = int(site.get('survey_allowance', 0))
    oils = pd.read_csv(os.path.join(pkg, 'oils.csv')).set_index('oil')
    lines = pd.read_csv(os.path.join(pkg, 'lines.csv'))
    sv = pd.read_csv(os.path.join(pkg, 'surveys.csv'))
    wl = pd.read_csv(os.path.join(pkg, 'work_log.csv'))
    rec = pd.read_csv(os.path.join(pkg, 'records.csv'))

    cover_jobs = wl[wl['job'].astype(str).str.lower().str.contains('cover')]
    last_cover = cover_jobs.groupby('pipe')['date'].max().to_dict()

    # outside coefficients of every survey on file at the bore as laid, in one pass
    lmap = lines.set_index('line')
    sv = sv.copy()
    sv['line'] = sv['pipe'].str[:-2]
    sv = sv[sv['line'].isin(lmap.index)].reset_index(drop=True)
    Pc = {kk: np.array([oil_consts(oils.loc[lmap.loc[l, 'oil']])[kk] for l in sv['line']])
          for kk in ('A', 'B', 'rho', 'cp', 'k')}
    Pc['L'] = lmap.loc[sv['line'], 'length_m'].values.astype(float)
    Dsv = lmap.loc[sv['line'], 'bore_mm'].values / 1000.0
    base = [sv['flow_t_h'].values / 3.6, sv['t_in_C'].values, sv['t_out_C'].values, sv['t_amb_C'].values]
    # survey accuracies (TS-2 5.4): flow 0.2 %, oil temperatures 0.02 K, surroundings 0.1 K
    nsv = len(sv)
    pert = [(0, 1.002, 'mul'), (1, 0.02, 'add'), (2, 0.02, 'add'), (3, 0.1, 'add')]
    cols = [list(base)]
    for j, d, kind in pert:
        c = list(base)
        c[j] = c[j] * d if kind == 'mul' else c[j] + d
        cols.append(c)
    Pk = {kk: np.tile(v, len(cols)) for kk, v in Pc.items()}
    Ub = fit_U_vec(Pk, np.tile(Dsv, len(cols)), *[np.concatenate([c[j] for c in cols]) for j in range(4)])
    Ub = Ub.reshape(len(cols), nsv)
    sv['U0'] = Ub[0]
    sv['dU'] = np.abs(Ub[1:] - Ub[0]).sum(axis=0)

    info = {}   # line -> dict
    needs = []  # (priority, score, pipe)
    for _, L in lines.iterrows():
        ln = L['line']
        P = oil_consts(oils.loc[L['oil']])
        P['L'] = float(L['length_m'])
        Dl = float(L['bore_mm']) / 1000.0
        names = [ln + '-A'] if int(L['pipes']) == 1 else [ln + '-A', ln + '-B']
        S = sv[sv['pipe'].isin(names)]
        dates = sorted(S['date'].unique())
        hist = {p: [] for p in names}   # (date, U, D)
        for dt in dates:
            g = S[S['date'] == dt].set_index('pipe')
            if not all(p in g.index for p in names):
                continue
            if len(names) == 1:
                r = g.loc[names[0]]
                U = r.U0
                hist[names[0]].append((dt, U, Dl, r.dU))
            else:
                obs = [(g.loc[p].flow_t_h / 3.6, g.loc[p].t_in_C, g.loc[p].t_amb_C, g.loc[p].t_out_C) for p in names]
                D, U, _ = pair_fit(P, Dl, [Dl, Dl], obs, [None, None], U0=[g.loc[p].U0 for p in names])
                for i, p in enumerate(names):
                    hist[p].append((dt, U[i], D[i], g.loc[p].dU))
        pip = {}
        for p in names:
            lc = last_cover.get(p)
            h = [e for e in hist[p] if lc is None or e[0] > lc]
            reason, score = None, 0.0
            if not h:
                reason, score = 0, 1.0
                U = hist[p][-1][1] if hist[p] else 5.0
                Dp = hist[p][-1][2] if hist[p] else Dl
            else:
                U, Dp = h[-1][1], h[-1][2]
                Uv = np.array([e[1] for e in h])
                Dv = np.array([e[2] for e in h])
                if len(h) > 1:
                    eU = np.array([e[3] for e in h])
                    su = 0.0
                    for a in range(len(h)):
                        for b in range(a + 1, len(h)):
                            su = max(su, abs(Uv[a] - Uv[b]) / (1.5 * (eU[a] + eU[b]) + 0.005 * U))
                    sd = (Dv.max() - Dv.min()) / Dv.mean()
                    if su > 0.5:
                        reason, score = 1, (Uv.max() - Uv.min()) / Uv.mean()
                    if sd > 0.005 and 4 * sd > score:
                        reason, score = 1, 4 * sd
            pip[p] = dict(U=U, D=Dp, hist=h)
            if reason is not None:
                needs.append((reason, -score, p))
        info[ln] = dict(P=P, Dl=Dl, names=names, pip=pip)

    needs.sort()
    order = [p for _, _, p in needs][:allowance]
    crew = order_survey(pkg, order) if order else {}

    # apply crew surveys
    done_lines = set()
    for p in order:
        if p not in crew:
            continue
        ln = p[:-2]
        if ln in done_lines:
            continue
        done_lines.add(ln)
        I = info[ln]
        P, Dl, names = I['P'], I['Dl'], I['names']
        if len(names) == 1:
            r = crew[p]
            I['pip'][p]['U'] = fit_U(P, I['pip'][p]['D'], r['flow_t_h'] / 3.6, r['t_in_C'], r['t_out_C'],
                                     r['t_amb_C'])
            continue
        obs, Ufix = [], []
        for i, q in enumerate(names):
            if q in crew:
                r = crew[q]
                obs.append((r['flow_t_h'] / 3.6, r['t_in_C'], r['t_amb_C'], r['t_out_C']))
            else:
                o = crew[names[1 - i]]
                obs.append(((o['line_flow_t_h'] - o['flow_t_h']) / 3.6, o['t_in_C'], o['t_amb_C'], None))
            Ufix.append(I['pip'][q]['U'])
        Dcur = [I['pip'][q]['D'] for q in names]
        hint = None
        fouled = [i for i, q in enumerate(names) if I['pip'][q]['D'] < Dl * 0.999]
        if len(fouled) == 1:
            hint = fouled[0]
        D, U, _ = pair_fit(P, Dl, Dcur if hint is not None else [Dl, Dl], obs, Ufix, fouled_hint=hint)
        for i, q in enumerate(names):
            I['pip'][q]['U'] = U[i]
            I['pip'][q]['D'] = D[i]

    # ---------------- records
    rec = rec.reset_index(drop=True)
    dp_out = np.full(len(rec), np.nan)
    t_out = np.full(len(rec), np.nan)
    singles = [ln for ln in info if len(info[ln]['names']) == 1]
    pairs = [ln for ln in info if len(info[ln]['names']) == 2]

    if singles:
        mask = rec['line'].isin(singles).values
        sub = rec[mask]
        keys = ('A', 'B', 'rho', 'cp', 'k', 'L')
        Pv = {kk: np.array([info[l]['P'][kk] for l in sub['line']]) for kk in keys}
        D = np.array([info[l]['pip'][l + '-A']['D'] for l in sub['line']])
        U = np.array([info[l]['pip'][l + '-A']['U'] for l in sub['line']])
        dp, T = pipe(Pv, D, U, sub['flow_t_h'].values / 3.6, sub['t_in_C'].values, sub['t_amb_C'].values)
        dp_out[mask] = dp
        t_out[mask] = T

    if pairs:
        keys = ('A', 'B', 'rho', 'cp', 'k', 'L')
        Pall = {kk: np.array([info[l]['P'][kk] for l in pairs]) for kk in keys}
        DA = np.array([info[l]['pip'][l + '-A']['D'] for l in pairs])
        DB = np.array([info[l]['pip'][l + '-B']['D'] for l in pairs])
        UA = np.array([info[l]['pip'][l + '-A']['U'] for l in pairs])
        UB = np.array([info[l]['pip'][l + '-B']['U'] for l in pairs])
        seqs = []
        for l in pairs:
            r = rec[rec['line'] == l].sort_values('hour', kind='stable')
            seqs.append(r.index.values)
        s_prev = np.full(len(pairs), np.nan)
        maxlen = max((len(q) for q in seqs), default=0)
        for step in range(maxlen):
            act = np.array([j for j in range(len(pairs)) if step < len(seqs[j])])
            ridx = np.array([seqs[j][step] for j in act])
            Pv = {kk: v[act] for kk, v in Pall.items()}
            m = rec.loc[ridx, 'flow_t_h'].values / 3.6
            Tin = rec.loc[ridx, 't_in_C'].values
            Ta = rec.loc[ridx, 't_amb_C'].values
            s, dp, T = solve_pairs(Pv, DA[act], DB[act], UA[act], UB[act], m, Tin, Ta, s_prev[act])
            s_prev[act] = s
            dp_out[ridx] = dp
            t_out[ridx] = T

    dp_out = np.where(np.isfinite(dp_out), dp_out, 0.0)
    t_out = np.where(np.isfinite(t_out), t_out, 0.0)
    with open(out_csv, 'w') as f:
        f.write('record,dp_kPa,t_out_C\n')
        for r, a, b in zip(rec['record'].values, dp_out / 1000.0, t_out):
            f.write('%s,%.4f,%.4f\n' % (r, a, b))


if __name__ == '__main__':
    main()
