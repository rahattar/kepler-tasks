#!/usr/bin/env python3
"""TS-2 heated oil transfer lines: pressure drop and outlet temperature for each record.

Usage: python3 lines.py PACKAGE_DIR OUT_CSV
"""
import sys, os, re, json, subprocess, io
import numpy as np
import pandas as pd

# accuracies of a survey reading, TS-2 5.4
ACC_FLOW, ACC_T, ACC_TA = 0.002, 0.02, 0.1


# ---------------------------------------------------------------- oil and pipe (TS-2 2, 3)
def oil_AB(nu50, nu100):
    T1, T2 = 323.15, 373.15
    y1 = np.log10(np.log10(np.asarray(nu50, float) + 0.7))
    y2 = np.log10(np.log10(np.asarray(nu100, float) + 0.7))
    B = (y1 - y2) / (np.log10(T2) - np.log10(T1))
    A = y1 + B * np.log10(T1)
    return A, B


def nu_of(T, A, B):
    """kinematic viscosity, m2/s, T in C"""
    return (10.0 ** (10.0 ** (A - B * np.log10(T + 273.15))) - 0.7) * 1e-6


def pipe(m, Tin, Ta, D, L, Uo, rho, cp, k, A, B, N=10):
    """Vectorized integration of TS-2 3.1-3.5. m kg/s, D, L m. Returns (Tout C, dp Pa)."""
    arrs = np.broadcast_arrays(*[np.asarray(a, float) for a in (m, Tin, Ta, D, L, Uo, rho, cp, k, A, B)])
    m, Tin, Ta, D, L, Uo, rho, cp, k, A, B = arrs
    u = 4 * m / (np.pi * D ** 2 * rho)
    kD = k / D
    xmin = 1e-9 * L

    def F(s, Tb):
        x = L * s * s
        j = 2 * L * s
        Tb = np.maximum(Tb, Ta)
        nub = nu_of(Tb, A, B)
        Re = u * D / nub
        Pr = nub * rho * cp / k
        Gz = Re * Pr * D / np.maximum(x, xmin)
        c = 1.077 * np.cbrt(Gz) - 0.7
        Nu0 = np.cbrt(3.66 ** 3 + 0.7 ** 3 + c ** 3)
        h0 = Nu0 * kD
        Tw = (h0 * Tb + Uo * Ta) / (h0 + Uo)
        for _ in range(4):
            h = h0 * (nub / nu_of(Tw, A, B)) ** 0.14
            Tw = (h * Tb + Uo * Ta) / (h + Uo)
        nuw = nu_of(Tw, A, B)
        q = np.pi * D * Uo * (Tw - Ta)
        f = 64 / Re * np.sqrt(nuw / nub)
        return -q / (m * cp) * j, f * rho * u * u / (2 * D) * j

    T = Tin.copy()
    P = np.zeros_like(T)
    hs = 1.0 / N
    for i in range(N):
        s0 = i * hs
        a1, b1 = F(s0, T)
        a2, b2 = F(s0 + hs / 2, T + hs / 2 * a1)
        a3, b3 = F(s0 + hs / 2, T + hs / 2 * a2)
        a4, b4 = F(s0 + hs, T + hs * a3)
        T = T + hs / 6 * (a1 + 2 * a2 + 2 * a3 + a4)
        P = P + hs / 6 * (b1 + 2 * b2 + 2 * b3 + b4)
    return np.maximum(T, Ta), P


def fit_U(m, Tin, Tout, Ta, D, L, props, it=44):
    """Uo for which section 3 gives the outlet temperature read (TS-2 5.2); vectorized bisection."""
    shape = np.shape(m)
    lo = np.full(shape, np.log(0.02))
    hi = np.full(shape, np.log(500.0))
    for _ in range(it):
        mid = 0.5 * (lo + hi)
        T, _ = pipe(m, Tin, Ta, D, L, np.exp(mid), *props)
        too_cold = T < Tout  # too much heat lost -> Uo smaller
        hi = np.where(too_cold, mid, hi)
        lo = np.where(too_cold, lo, mid)
    return np.exp(0.5 * (lo + hi))


# ---------------------------------------------------------------- survey analysis
def analyse_surveys(sv, pinfo, fixedU=None):
    """sv: survey rows (pipe, line_flow_t_h, flow_t_h, t_in_C, t_out_C, t_amb_C, grp).
    Rows of one pair in one group (grp) are fitted jointly: Uo of each pipe surveyed and the
    bore in service (5.5).  fixedU: dict pipe -> (U, D) for the partner of a pair not in the group.
    Returns sv with columns U, D."""
    sv = sv.reset_index(drop=True).copy()
    fixedU = fixedU or {}
    n = len(sv)
    pi = pinfo.loc[sv['pipe']]
    props = tuple(pi[c].values for c in ('rho', 'cp', 'k', 'A', 'B'))
    L = pi['L'].values
    Dlaid = pi['Dlaid'].values
    m = sv['flow_t_h'].values / 3.6
    D = Dlaid.copy()

    # build pair groups
    pairs = []      # (idxA, idxB or None, partner pipe name, line_flow)
    single_partner = []
    for (g, line), sub in sv.groupby(['grp', 'line']):
        if pinfo.loc[sub['pipe'].iloc[0], 'pipes'] != 2:
            continue
        ia = sub.index[sub['pipe'].str.endswith('-A')]
        ib = sub.index[sub['pipe'].str.endswith('-B')]
        ia = int(ia[0]) if len(ia) else None
        ib = int(ib[0]) if len(ib) else None
        pairs.append((ia, ib, line))

    # extra evaluations for partners not surveyed in the group
    ex_rows = []
    for ip, (ia, ib, line) in enumerate(pairs):
        if ia is None or ib is None:
            idx = ia if ia is not None else ib
            other = line + ('-B' if ia is not None else '-A')
            if other not in fixedU:
                continue
            U_o, D_o = fixedU[other]
            r = sv.loc[idx]
            ex_rows.append(dict(ip=ip, pipe=other, m=max(r['line_flow_t_h'] - r['flow_t_h'], 1e-4) / 3.6,
                                Tin=r['t_in_C'], Ta=r['t_amb_C'], U=U_o, D0=D_o,
                                first=(ia is None)))
    ex = pd.DataFrame(ex_rows)
    if len(ex):
        epi = pinfo.loc[ex['pipe']]
        eprops = tuple(epi[c].values for c in ('rho', 'cp', 'k', 'A', 'B'))
        eL = epi['L'].values
        eDlaid = epi['Dlaid'].values
    s = np.zeros(len(pairs))   # bore parameter per pair
    U = None
    for it in range(8):
        # bores from s
        for ip, (ia, ib, line) in enumerate(pairs):
            if ia is not None:
                D[ia] = Dlaid[ia] * np.exp(min(s[ip], 0.0))
            if ib is not None:
                D[ib] = Dlaid[ib] * np.exp(min(-s[ip], 0.0))
        U = fit_U(m, sv['t_in_C'].values, sv['t_out_C'].values, sv['t_amb_C'].values, D, L, props,
                  it=44 if it == 0 else 30)
        if not pairs:
            break
        _, dp = pipe(m, sv['t_in_C'].values, sv['t_amb_C'].values, D, L, U, *props)
        exdp = {}
        if len(ex):
            eD = np.empty(len(ex))
            for j, r in ex.iterrows():
                ip = int(r['ip'])
                # partner is A if surveyed pipe is B
                if r['first']:
                    eD[j] = eDlaid[j] * np.exp(min(s[ip], 0.0))
                else:
                    eD[j] = eDlaid[j] * np.exp(min(-s[ip], 0.0))
            _, edp = pipe(ex['m'].values, ex['Tin'].values, ex['Ta'].values, eD, eL, ex['U'].values, *eprops)
            for j, r in ex.iterrows():
                exdp[int(r['ip'])] = edp[j]
        for ip, (ia, ib, line) in enumerate(pairs):
            if ia is not None and ib is not None:
                dpa, dpb = dp[ia], dp[ib]
            elif ip in exdp:
                if ia is not None:
                    dpa, dpb = dp[ia], exdp[ip]
                else:
                    dpa, dpb = exdp[ip], dp[ib]
            else:
                continue
            s[ip] += 0.25 * np.log(dpa / dpb)
    for ip, (ia, ib, line) in enumerate(pairs):
        if ia is not None:
            D[ia] = Dlaid[ia] * np.exp(min(s[ip], 0.0))
        if ib is not None:
            D[ib] = Dlaid[ib] * np.exp(min(-s[ip], 0.0))
    sv['U'] = U
    sv['D'] = D
    # for a group surveying one pipe of a pair, the partner's bore in service
    sv['partner_D'] = np.nan
    for ip, (ia, ib, line) in enumerate(pairs):
        if (ia is None) != (ib is None) and ip in [int(v) for v in ex['ip']] if len(ex) else False:
            idx = ia if ia is not None else ib
            j = int(np.where(ex['ip'].values == ip)[0][0])
            if ia is None:
                sv.loc[idx, 'partner_D'] = eDlaid[j] * np.exp(min(s[ip], 0.0))
            else:
                sv.loc[idx, 'partner_D'] = eDlaid[j] * np.exp(min(-s[ip], 0.0))
    return sv


def U_tolerance(sv, pinfo):
    """bound on the error in Uo from the accuracies of the readings (5.4)"""
    pi = pinfo.loc[sv['pipe']]
    props = tuple(pi[c].values for c in ('rho', 'cp', 'k', 'A', 'B'))
    L = pi['L'].values
    D = sv['D'].values
    base = dict(m=sv['flow_t_h'].values / 3.6, Tin=sv['t_in_C'].values, Tout=sv['t_out_C'].values,
                Ta=sv['t_amb_C'].values)
    tol = np.zeros(len(sv))
    for key, d in (('m', ACC_FLOW * base['m']), ('Tin', ACC_T), ('Tout', ACC_T), ('Ta', ACC_TA)):
        b = dict(base)
        b[key] = b[key] + d
        Up = fit_U(b['m'], b['Tin'], b['Tout'], b['Ta'], D, L, props, it=30)
        tol += np.abs(Up - sv['U'].values)
    return tol


COVER_RE = re.compile(r'cover|lag|insul|clad|jacket|wrap|sheath|tape', re.I)


# ---------------------------------------------------------------- main
def main():
    np.seterr(all='ignore')
    pkg, out = sys.argv[1], sys.argv[2]
    oils = pd.read_csv(os.path.join(pkg, 'oils.csv')).set_index('oil')
    lines = pd.read_csv(os.path.join(pkg, 'lines.csv'))
    lines['line'] = lines['line'].astype(str).str.strip()
    lines = lines.set_index('line')
    sv = pd.read_csv(os.path.join(pkg, 'surveys.csv'))
    wl = pd.read_csv(os.path.join(pkg, 'work_log.csv'))
    rec = pd.read_csv(os.path.join(pkg, 'records.csv'))
    try:
        site = json.load(open(os.path.join(pkg, 'site.json')))
    except Exception:
        site = {}
    allowance = int(site.get('survey_allowance', 0) or 0)

    for df in (sv, wl):
        df['pipe'] = df['pipe'].astype(str).str.strip()
    sv['line'] = sv['pipe'].str.rsplit('-', n=1).str[0]
    rec['line'] = rec['line'].astype(str).str.strip()

    # pipe information
    rows = []
    for line, r in lines.iterrows():
        o = oils.loc[str(r['oil']).strip()]
        A, B = oil_AB(o['nu50_cSt'], o['nu100_cSt'])
        for suf in (['A', 'B'] if int(r['pipes']) == 2 else ['A']):
            rows.append(dict(pipe=f'{line}-{suf}', line=line, pipes=int(r['pipes']),
                             Dlaid=r['bore_mm'] / 1000.0, L=float(r['length_m']),
                             rho=o['density_kg_m3'], cp=o['cp_J_kgK'], k=o['k_W_mK'], A=A, B=B))
    pinfo = pd.DataFrame(rows).set_index('pipe')
    all_pipes = list(pinfo.index)

    # campaigns
    sv['date'] = pd.to_datetime(sv['date'])
    wl['date'] = pd.to_datetime(wl['date'])
    sv = sv[sv['pipe'].isin(pinfo.index)].copy()
    sv['grp'] = sv['date'].astype(str)
    sv = analyse_surveys(sv, pinfo)
    sv['tol'] = U_tolerance(sv, pinfo)

    cover = wl[wl['job'].astype(str).str.contains(COVER_RE)]
    last_cover = cover.groupby('pipe')['date'].max()

    # per pipe state from the surveys on file
    state = {}   # pipe -> dict(U, D, need, score)
    for p in all_pipes:
        s = sv[sv['pipe'] == p].sort_values('date')
        lc = last_cover.get(p, pd.NaT)
        st = dict(U=np.nan, D=pinfo.loc[p, 'Dlaid'], need=0, score=0.0)
        if len(s) == 0:
            st.update(need=3, score=1e9)
            state[p] = st
            continue
        valid = s if pd.isna(lc) else s[s['date'] > lc]
        st['D'] = pinfo.loc[p, 'Dlaid']   # set below for a pair with deposit
        if len(valid) == 0:
            # covering worked on after its last survey (5.3)
            st['U'] = s['U'].iloc[-1]
            st.update(need=3, score=1e6)
        else:
            Us, tols = valid['U'].values, valid['tol'].values
            changing = False
            if len(Us) >= 2:
                changing = bool(np.any(np.abs(np.diff(Us)) > (tols[1:] + tols[:-1]) * 1.0 + 1e-9))
            if changing:
                # 5.6: covering changing; extrapolate as a fallback
                st['U'] = Us[-1]
                st.update(need=2, score=1e3 * abs(Us[-1] - Us[0]) / Us[-1])
            else:
                st['U'] = Us[-1]
        state[p] = st

    # fouling of pairs (5.5): bore in service at each campaign
    for line, r in lines.iterrows():
        if int(r['pipes']) != 2:
            continue
        for suf in 'AB':
            p = f'{line}-{suf}'
            s = sv[sv['pipe'] == p].sort_values('date')
            if len(s) == 0:
                continue
            dl = pinfo.loc[p, 'Dlaid']
            red = 1 - s['D'].values / dl
            # deposit significant and/or growing: the bore now is not known
            if red[-1] > 0.004 or (len(red) > 1 and red[-1] - red[0] > 0.003):
                sc = 10 * (red[-1] - red[0]) + red[-1]
                if state[p]['need'] < 1:
                    state[p]['need'] = 1
                state[p]['score'] = max(state[p]['score'], 1 + 1e2 * sc)
                state[p]['foul'] = True
                state[p]['D'] = s['D'].values[-1]

    # ------------------------------------------------ order for the crew
    cands = [p for p in all_pipes if state[p]['need'] > 0]
    cands.sort(key=lambda p: (-state[p]['need'], -state[p]['score']))
    order = cands[:allowance] if allowance > 0 else []
    new = None
    if order:
        try:
            res = subprocess.run(['heatsurvey', pkg] + order, capture_output=True, text=True, timeout=25)
            if res.returncode == 0 and res.stdout.strip():
                new = pd.read_csv(io.StringIO(res.stdout))
                new.columns = [c.strip() for c in new.columns]
                new['pipe'] = new['pipe'].astype(str).str.strip()
                new = new[new['pipe'].isin(pinfo.index)]
                if len(new) == 0:
                    new = None
            else:
                sys.stderr.write('heatsurvey: ' + res.stderr + res.stdout + '\n')
        except Exception as e:
            sys.stderr.write(f'heatsurvey failed: {e}\n')
    if new is not None:
        new['line'] = new['pipe'].str.rsplit('-', n=1).str[0]
        new['grp'] = 'new'
        # partners not surveyed now keep their own coefficient and bore
        fixed = {p: (state[p]['U'], state[p]['D']) for p in all_pipes}
        nsv = analyse_surveys(new, pinfo, fixedU=fixed)
        for _, r in nsv.iterrows():
            p = r['pipe']
            state[p]['U'] = r['U']
            sig = lambda q, d: d if (1 - d / pinfo.loc[q, 'Dlaid'] > 0.004 or state[q].get('foul')) else pinfo.loc[q, 'Dlaid']
            state[p]['D'] = sig(p, r['D'])
            if not np.isnan(r['partner_D']):
                line = r['line']
                other = line + ('-B' if p.endswith('-A') else '-A')
                state[other]['D'] = sig(other, r['partner_D'])
        # if both pipes of a pair were surveyed, the joint fit already set both bores

    # ------------------------------------------------ records
    for p in all_pipes:
        if not np.isfinite(state[p]['U']):
            state[p]['U'] = 5.0
    rec = rec.reset_index().rename(columns={'index': 'row'})
    rec = rec.sort_values(['line', 'hour', 'row'])
    rec['j'] = rec.groupby('line').cumcount()
    res_dp = np.full(len(rec), np.nan)
    res_T = np.full(len(rec), np.nan)
    rows_idx = rec['row'].values

    def pp(p, key):
        return pinfo.loc[p, key]

    # singles: all at once
    sing = rec[rec['line'].map(lambda l: int(lines.loc[l, 'pipes']) == 1)]
    if len(sing):
        ps = [l + '-A' for l in sing['line']]
        pi = pinfo.loc[ps]
        U = np.array([state[p]['U'] for p in ps])
        D = np.array([state[p]['D'] for p in ps])
        T, dp = pipe(sing['flow_t_h'].values / 3.6, sing['t_in_C'].values, sing['t_amb_C'].values,
                     D, pi['L'].values, U, pi['rho'].values, pi['cp'].values, pi['k'].values,
                     pi['A'].values, pi['B'].values)
        res_dp[sing['row'].values] = dp / 1e3
        res_T[sing['row'].values] = T

    pairs = rec[rec['line'].map(lambda l: int(lines.loc[l, 'pipes']) == 2)]
    if len(pairs):
        plines = sorted(pairs['line'].unique())
        nl = len(plines)
        li = {l: i for i, l in enumerate(plines)}
        def arr(suf, key):
            return np.array([pinfo.loc[l + suf, key] for l in plines], float)
        PA = dict(D=np.array([state[l + '-A']['D'] for l in plines]), U=np.array([state[l + '-A']['U'] for l in plines]),
                  L=arr('-A', 'L'))
        PB = dict(D=np.array([state[l + '-B']['D'] for l in plines]), U=np.array([state[l + '-B']['U'] for l in plines]),
                  L=arr('-B', 'L'))
        props = [arr('-A', c) for c in ('rho', 'cp', 'k', 'A', 'B')]
        phi_prev = np.full(nl, np.nan)
        G = 61
        grid = np.linspace(0.0025, 0.9975, G)
        maxj = pairs['j'].max()

        def g_eval(sel, phi, M, Tin, Ta):
            """dpA - dpB and Tmix for lines sel (indices) at division phi (fraction in A)"""
            mA = phi * M
            mB = (1 - phi) * M
            pr = [c[sel] for c in props]
            TA, dA = pipe(mA, Tin, Ta, PA['D'][sel], PA['L'][sel], PA['U'][sel], *pr)
            TB, dB = pipe(mB, Tin, Ta, PB['D'][sel], PB['L'][sel], PB['U'][sel], *pr)
            return dA - dB, dA, dB, (mA * TA + mB * TB) / M

        for j in range(maxj + 1):
            cur = pairs[pairs['j'] == j]
            sel = np.array([li[l] for l in cur['line']])
            n = len(sel)
            M = cur['flow_t_h'].values / 3.6
            Tin = cur['t_in_C'].values
            Ta = cur['t_amb_C'].values
            # scan over the whole grid of divisions
            selg = np.repeat(sel, G)
            phig = np.tile(grid, n)
            gg, _, _, _ = g_eval(selg, phig, np.repeat(M, G), np.repeat(Tin, G), np.repeat(Ta, G))
            gg = gg.reshape(n, G)
            lo = np.empty(n)
            hi = np.empty(n)
            pp_all = phi_prev[sel]
            has = ~np.isnan(pp_all)
            gp_all = np.zeros(n)
            if has.any():
                gp_all[has] = g_eval(sel[has], pp_all[has], M[has], Tin[has], Ta[has])[0]
            for i in range(n):
                g = gg[i]
                sc = np.where(np.sign(g[:-1]) != np.sign(g[1:]))[0]  # root in [grid[c], grid[c+1]]
                pprev = phi_prev[sel[i]]
                if len(sc) == 0:
                    c = 0 if abs(g[0]) < abs(g[-1]) else G - 2
                    lo[i], hi[i] = grid[c], grid[c + 1]
                    continue
                if np.isnan(pprev):
                    # opening record: one division only; if several, nearest even split
                    c = sc[np.argmin(np.abs(grid[sc] - 0.5))]
                else:
                    # start at previous division; oil shifts away from the pipe with higher dp
                    gp = gp_all[i]
                    if gp > 0:   # A higher -> phi decreases
                        msk = grid < pprev
                        pts = np.concatenate([[pprev], grid[msk][::-1]])
                        vals = np.concatenate([[gp], g[msk][::-1]])
                    else:
                        msk = grid > pprev
                        pts = np.concatenate([[pprev], grid[msk]])
                        vals = np.concatenate([[gp], g[msk]])
                    ch = np.where(np.sign(vals[1:]) != np.sign(vals[0]))[0] if gp != 0 else np.array([], int)
                    if gp == 0:
                        lo[i] = hi[i] = pprev
                    elif len(ch):
                        kk = ch[0]
                        lo[i], hi[i] = pts[kk], pts[kk + 1]
                    else:
                        lo[i] = hi[i] = pts[-1]
                    continue
                lo[i], hi[i] = grid[c], grid[c + 1]
            # bracketed refinement (Illinois)
            glo, _, _, _ = g_eval(sel, lo, M, Tin, Ta)
            ghi, _, _, _ = g_eval(sel, hi, M, Tin, Ta)
            bad = np.sign(glo) == np.sign(ghi)
            gscale = np.abs(gg).max(axis=1) + 1e-30
            for it in range(30):
                den = ghi - glo
                x = np.where(bad | (den == 0), 0.5 * (lo + hi), (lo * ghi - hi * glo) / np.where(den == 0, 1, den))
                x = np.clip(x, np.minimum(lo, hi), np.maximum(lo, hi))
                if it % 3 == 2:
                    x = 0.5 * (lo + hi)
                gx, _, _, _ = g_eval(sel, x, M, Tin, Ta)
                left = np.sign(gx) == np.sign(glo)
                lo = np.where(left & ~bad, x, lo)
                glo = np.where(left & ~bad, gx, glo)
                hi = np.where(~left & ~bad, x, hi)
                ghi = np.where(~left & ~bad, gx, ghi)
                if np.all((np.abs(hi - lo) < 1e-6) | (np.minimum(np.abs(glo), np.abs(ghi)) < 1e-6 * np.abs(gscale))):
                    break
            phi = np.where(bad | (np.abs(glo) < np.abs(ghi)), lo, hi)
            phi = np.where(bad, np.where(np.abs(glo) < np.abs(ghi), lo, hi), phi)
            _, dA, dB, Tm = g_eval(sel, phi, M, Tin, Ta)
            phi_prev[sel] = phi
            res_dp[cur['row'].values] = 0.5 * (dA + dB) / 1e3
            res_T[cur['row'].values] = Tm

    outdf = pd.read_csv(os.path.join(pkg, 'records.csv'))[['record']].copy()
    outdf['dp_kPa'] = np.round(np.nan_to_num(res_dp, nan=0.0), 3)
    outdf['t_out_C'] = np.round(np.nan_to_num(res_T, nan=0.0), 4)
    outdf.to_csv(out, index=False)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(0)
