#!/usr/bin/env python3
"""RS-4 bending damage along hoist ropes for one works package.
Usage: python3 ropes.py WORKS_DIR OUT_CSV"""
import sys, os, math
import numpy as np
import pandas as pd

G = 9.80665
COEF = {'8x36': (-1.214, 0.887, 7.432, -2.103), '6x36': (-1.371, 0.934, 7.518, -2.146)}
KTERMS = 10


def rd(path):
    df = pd.read_csv(path, skipinitialspace=True)
    df.columns = [str(c).strip().lower() for c in df.columns]
    for c in df.columns:
        if df[c].dtype == object or str(df[c].dtype).startswith('string'):
            df[c] = df[c].astype(str).str.strip()
    return df


def num(s):
    return pd.to_numeric(s, errors='coerce')


def clean_sheet(st, dia):
    """Return (diameters by station index from the sheet's start, n) or None."""
    ok = np.isfinite(st) & np.isfinite(dia) & (dia > 0)
    st, dia = st[ok], dia[ok]
    if len(st) == 0:
        return None
    smin = st.min()
    frac = smin - math.floor(smin)
    base = smin if abs(frac - 0.5) < 0.25 else smin  # first station = index 0
    idx = np.round(st - base).astype(int)
    if (idx < 0).any():
        idx -= idx.min()
    n = int(idx.max()) + 1
    s = pd.Series(dia).groupby(idx).median()
    ii, dd = s.index.values.astype(int), s.values.astype(float)
    if len(dd) >= 5:
        loc = pd.Series(dd).rolling(7, center=True, min_periods=1).median().values
        med = np.median(dd)
        bad = (np.abs(dd - loc) > 0.04 * loc) | (np.abs(dd - med) > 0.25 * med)
        if bad.sum() < len(dd):
            ii, dd = ii[~bad], dd[~bad]
    return np.interp(np.arange(n), ii, dd), n


def align(prev_u, prev_d, new_d):
    """prev_u: element coords (int, of station index) of previous sheet; prev_d diameters.
    Find orientation sg and shift so that element u = shift + sg*j for new station j."""
    m = len(new_d); M = len(prev_d)
    cands = [(sg, k) for sg in (1, -1) for k in range(0, M - m + 1)]
    # work in previous sheet index space: new j -> prev index k + j (sg=1) or k + m-1-j (sg=-1)
    best = None; scores = []
    for sg, k in cands:
        if sg == 1:
            pd_ = prev_d[k:k + m]
        else:
            pd_ = prev_d[k:k + m][::-1]
        diff = new_d - pd_
        sc = np.mean(np.abs(diff - np.median(diff)))
        scores.append(sc)
    scores = np.array(scores)
    bi = int(np.argmin(scores))
    # prefer identity-like options when not clearly worse
    tol = scores[bi] * 1.05 + 1e-6
    pref = []
    for i, (sg, k) in enumerate(cands):
        if scores[i] <= tol:
            pref.append(((0 if sg == 1 else 1), min(k, M - m - k), k, i))
    pref.sort()
    sg, k = cands[pref[0][3]]
    return sg, k


def crane_damage(cr, shv, mv, sv):
    n = float(cr['falls']); H = float(cr['upper_block_height_m'])
    mb = float(cr['block_mass_t']); e = float(cr['reeving_efficiency'])
    L0 = float(cr['rope_length_m'])
    cons = str(cr['rope_construction']).strip().lower().replace('\u00d7', 'x').replace(' ', '')
    b0, b1, b2, b3 = COEF.get(cons, COEF['6x36'])

    # surveys -> list of (day, diam per current station, elem u per current station)
    sheets = []
    if len(sv):
        for day, g in sv.groupby('day'):
            r = clean_sheet(g['station_m'].values.astype(float), g['diameter_mm'].values.astype(float))
            if r is not None:
                sheets.append((float(day), r[0]))
    sheets.sort(key=lambda t: t[0])
    n0 = max(int(round(L0)), 1)
    if not sheets:
        sheets = [(0.0, np.full(n0, 20.0))]
    periods = []  # (day, d per station, u per station)
    first = sheets[0][1]
    if len(first) != n0 and abs(len(first) - n0) > 0:
        n0 = max(n0, len(first))
    u = np.arange(len(first))
    if len(first) < n0:
        # sheet shorter than declared rope: assume declared drum anchorage
        pass
    periods.append((sheets[0][0], first, u))
    for day, d in sheets[1:]:
        pu, pdd = periods[-1][2], periods[-1][1]
        if len(d) > len(pdd):
            # longer than before: keep it as a new reading of the same layout, truncate
            d = d[:len(pdd)] if len(d) > len(pdd) else d
        sg, k = align(pu, pdd, d)
        m = len(d)
        if sg == 1:
            nu = pu[k:k + m]
        else:
            nu = pu[k:k + m][::-1]
        periods.append((day, d, nu.copy()))
    NU = int(max(p[2].max() for p in periods)) + 1
    NU = max(NU, n0)
    dmg = np.zeros(NU)
    pdays = np.array([p[0] for p in periods])

    if len(mv):
        day = mv['day'].values.astype(float)
        h0 = np.minimum(mv['from_height_m'].values.astype(float), H)
        h1 = np.minimum(mv['to_height_m'].values.astype(float), H)
        load = np.nan_to_num(mv['hook_load_t'].values.astype(float))
        S = np.maximum((load + mb) * 1000.0 * G / (n * e), 1e-6)
        lgS = np.log10(S)
        per = np.clip(np.searchsorted(pdays, day + 1e-9, side='right') - 1, 0, len(pdays) - 1)
        for k in np.unique(per):
            selk = per == k
            d = periods[k][1]; uu = periods[k][2]
            ns = len(d)
            L = float(ns) if k > 0 or len(d) != n0 else L0
            xs = np.arange(ns) + 0.5
            hk0, hk1, lgk = h0[selk], h1[selk], lgS[selk]
            acc = np.zeros(ns)
            for _, sh in shv.iterrows():
                p = float(sh['parts']); a = float(sh['offset_m']); D = float(sh['diameter_mm'])
                w = float(sh['bend_weight'])
                if not np.isfinite(w):
                    w = 1.0
                xa = L - a - p * (H - hk0)
                xb = L - a - p * (H - hk1)
                i0 = np.searchsorted(xs, np.minimum(xa, xb), side='left')
                i1 = np.searchsorted(xs, np.maximum(xa, xb), side='right')
                m = i1 > i0
                if not m.any():
                    continue
                a0, a1, lg = i0[m], i1[m], lgk[m]
                lr = np.log10(D / d)
                Bst = b1 + b3 * lr
                Ast = b0 + b2 * lr - Bst * 2 * np.log10(d)
                B0 = float(np.mean(Bst))
                dB = (Bst - B0) * math.log(10)
                lc = float(np.mean(lg))
                # centre the expansion: S^-B = 10^-(B lc) * 10^-(B0 (lg-lc)) * exp(-dB (lg-lc))
                y = lg - lc
                t = 10.0 ** (-B0 * y)
                tot = np.zeros(ns); coef = np.ones(ns)
                for q in range(KTERMS):
                    c = np.bincount(a0, weights=t, minlength=ns + 1) - np.bincount(a1, weights=t, minlength=ns + 1)
                    tot += coef * np.cumsum(c)[:ns]
                    t = t * y
                    coef = coef * (-dB) / (q + 1)
                acc += w * 10.0 ** (-Ast - Bst * lc) * tot
            np.add.at(dmg, uu, acc)
    last = periods[-1][2]
    return dmg[last]


def main():
    wd, out = sys.argv[1], sys.argv[2]
    cr = rd(os.path.join(wd, 'cranes.csv'))
    sh = rd(os.path.join(wd, 'sheaves.csv'))
    mv = rd(os.path.join(wd, 'movements.csv'))
    sv = rd(os.path.join(wd, 'surveys.csv'))
    for df, cols in ((cr, ['falls', 'upper_block_height_m', 'block_mass_t', 'reeving_efficiency', 'rope_length_m']),
                     (sh, ['parts', 'offset_m', 'diameter_mm', 'bend_weight']),
                     (mv, ['day', 'from_height_m', 'to_height_m', 'hook_load_t']),
                     (sv, ['day', 'station_m', 'diameter_mm'])):
        for c in cols:
            df[c] = num(df[c])
    mv = mv.dropna(subset=['day', 'from_height_m', 'to_height_m'])
    rows = []
    for _, c in cr.iterrows():
        name = c['crane']
        try:
            d = crane_damage(c, sh[sh['crane'] == name], mv[mv['crane'] == name], sv[sv['crane'] == name])
        except Exception:
            d = np.zeros(max(int(round(float(c['rope_length_m']))), 1))
        d = np.nan_to_num(d, nan=0.0, posinf=0.0)
        if len(d):
            d[np.abs(d) < 1e-9 * max(np.abs(d).max(), 1e-300)] = 0.0
            d = np.maximum(d, 0.0)
        for i, v in enumerate(d):
            rows.append('%s-%03d,%.6g' % (name, i + 1, v))
    if os.path.islink(out):
        os.unlink(out)
    with open(out, 'w') as f:
        f.write('row,damage\n' + '\n'.join(rows) + '\n')


if __name__ == '__main__':
    main()
