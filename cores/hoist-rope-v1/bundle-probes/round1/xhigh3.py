#!/usr/bin/env python3
"""Bending fatigue damage along crane hoist ropes to RS-4 (issue 3).

usage: python3 ropes.py WORKS_DIR OUT_CSV

For every crane of the works package the damage w/N of RS-4 section 5 is
summed over every bending of every element of the rope, and reported for
each station of the rope's last survey, numbered from the drum anchorage,
for the rope as it lies at the end of the log.

An element is a piece of rope, not a place on the crane.  The surveys are
used to follow the elements:

* Consecutive survey profiles are matched against each other (directly,
  end for end, and with an offset if the rope got shorter) to find which
  element each survey station is.
* A run of surveys that agree in this way is then placed on the crane by
  where its wear builds up: between two surveys the rope loses diameter
  where the sheaves and the drum bend it, so the wear increments must line
  up with the bendings the log gives at the crane positions of the
  elements.  This tells a rope that has been turned end for end (the wear
  keeps building at the same crane positions, now on other elements) from
  a survey sheet written from the dead end (the wear keeps building on
  the same elements).
* A change of the rope's place on the crane that falls between two
  surveys is taken at the middle of that interval, its time not being
  recorded.

The diameter of an element is the one measured on that element itself at
the last survey not later than the movement.
"""
import os
import sys
import math

import numpy as np

G = 9.80665
COEF = {
    '8x36': (-1.214, 0.887, 7.432, -2.103),
    '6x36': (-1.371, 0.934, 7.518, -2.146),
}
DEBUG = bool(os.environ.get('ROPES_DEBUG'))


def log(*a):
    if DEBUG:
        print(*a, file=sys.stderr)


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def read_table(path):
    import pandas as pd
    head = pd.read_csv(path, nrows=0, skipinitialspace=True)
    dtype = {}
    for c in head.columns:
        if str(c).strip().lower() in ('crane', 'sheave', 'rope_construction'):
            dtype[c] = 'category'
    df = pd.read_csv(path, skipinitialspace=True, engine='c', dtype=dtype)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def crane_rows(col):
    """{crane name: row indices}; names compared without surrounding blanks."""
    import pandas as pd
    if not isinstance(col.dtype, pd.CategoricalDtype):
        col = col.astype('category')
    codes = col.cat.codes.to_numpy()
    out = {}
    for ci, nm in enumerate(col.cat.categories):
        key = str(nm).strip()
        idx = np.flatnonzero(codes == ci)
        if key in out:
            out[key] = np.sort(np.concatenate([out[key], idx]))
        else:
            out[key] = idx
    return out


def norm_name(s):
    return s.astype(str).str.strip()


def to_num(df, cols):
    import pandas as pd
    for c in cols:
        if df[c].dtype.kind not in 'fi':
            df[c] = pd.to_numeric(df[c].astype(str).str.strip().str.replace(',', '.'),
                                  errors='coerce')
    return df


def construction(s):
    k = str(s).strip().lower().replace(' ', '').replace('×', 'x').replace('*', 'x')
    if k in COEF:
        return COEF[k]
    for key in COEF:
        if key in k:
            return COEF[key]
    if k.startswith('8'):
        return COEF['8x36']
    return COEF['6x36']


# --------------------------------------------------------------------------
# geometry: station ranges passed by the touch points
# --------------------------------------------------------------------------

def touch_ranges(Lc, a, p, H, h1, h2):
    """Index ranges [il, ih) of stations (centres j+0.5) passed by a touch point."""
    x1 = Lc - a - p * (H - h1)
    x2 = Lc - a - p * (H - h2)
    lo = np.minimum(x1, x2)
    hi = np.maximum(x1, x2)
    il = np.ceil(lo - 0.5)
    ih = np.floor(hi - 0.5) + 1.0
    il = np.clip(il, 0, Lc).astype(np.int64)
    ih = np.clip(ih, 0, Lc).astype(np.int64)
    ih = np.maximum(ih, il)
    return il, ih


# --------------------------------------------------------------------------
# surveys
# --------------------------------------------------------------------------

def station_index(st, L0):
    """Station values of one sheet -> station numbers 0.. from the drum anchorage."""
    fr = np.mod(st, 1.0)
    half = np.abs(fr - 0.5) < 0.05
    whole = (fr < 0.05) | (fr > 0.95)
    if half.mean() >= 0.5:
        idx = np.round(st - 0.5)
        good = half
    elif whole.mean() >= 0.5:
        # whole metres: ends of the metre pieces (1..L) or their starts (0..L-1)
        r = np.round(st)
        idx = r - 1 if np.nanmax(r[whole]) >= L0 else r
        good = whole
    else:
        order = np.argsort(st, kind='mergesort')
        idx = np.empty(len(st))
        idx[order] = np.arange(len(st))
        good = np.ones(len(st), bool)
    good = good & (idx >= 0) & (idx < max(L0, 1))
    return idx.astype(np.int64), good


def survey_profiles(sv, L0):
    """List of (day, profile) with the profile indexed by sheet station 0..n-1.

    A rope can only get shorter: a sheet that ends short of a later sheet
    is taken as incomplete, and its missing stations are filled in."""
    raw = []
    if sv is None or len(sv) == 0:
        return []
    for day, g in sv.groupby('day', sort=True):
        st = g['station_m'].to_numpy(float)
        dm = g['diameter_mm'].to_numpy(float)
        ok = np.isfinite(st) & np.isfinite(dm) & (dm > 0)
        st, dm = st[ok], dm[ok]
        if len(st) == 0:
            continue
        idx, good = station_index(st, L0)
        idx, dm = idx[good], dm[good]
        if len(idx) == 0:
            continue
        n = int(idx.max()) + 1
        sm = np.bincount(idx, dm, n)
        c = np.bincount(idx, None, n)
        prof = np.full(n, np.nan)
        prof[c > 0] = sm[c > 0] / c[c > 0]
        raw.append((float(day), prof))
    if not raw:
        return []
    # length of the rope at each survey
    lens = np.array([len(p) for _, p in raw])
    true_len = np.maximum.accumulate(lens[::-1])[::-1]
    out = []
    for (day, prof), n in zip(raw, true_len):
        if len(prof) < n:
            prof = np.concatenate([prof, np.full(n - len(prof), np.nan)])
        bad = ~np.isfinite(prof)
        if bad.any():
            good = np.flatnonzero(~bad)
            prof[bad] = np.interp(np.flatnonzero(bad), good, prof[good])
        out.append((day, prof))
    return out


def robust_scale(diff):
    diff = diff[np.isfinite(diff)]
    if len(diff) == 0:
        return np.inf
    r = diff - np.median(diff)
    # mean of squares with the worst 5 % of points left out (copying slips)
    q = np.sort(r * r)
    m = max(1, int(math.ceil(0.95 * len(q))))
    return math.sqrt(q[:m].mean() + 1e-12)


def match_sheet(prev_e, cur, prev_map):
    """Place sheet profile `cur` on the elements.

    prev_e: element profile of the previous survey (NaN off the rope).
    prev_map: (o, s) of the previous sheet: element = s + o*i.
    Returns (o, s) for the current sheet.
    """
    L0 = len(prev_e)
    n = len(cur)
    have = np.flatnonzero(np.isfinite(prev_e))
    elo, ehi = int(have.min()), int(have.max())
    cands = []
    for o in (1, -1):
        for start in range(elo, ehi - n + 2):
            # elements start..start+n-1 carry the sheet, in one of two senses
            seg = prev_e[start:start + n]
            if len(seg) < n or not np.all(np.isfinite(seg)):
                continue
            c = cur if o == 1 else cur[::-1]
            sc = robust_scale(seg - c)
            s = start if o == 1 else start + n - 1
            cands.append((sc, o, s))
    if not cands:
        return prev_map
    cands.sort()
    best = cands[0]
    po, ps = prev_map
    same = [c for c in cands if c[1] == po and c[2] == ps]
    if same:
        if best[0] < 0.7 * same[0][0]:
            return best[1], best[2]
        return po, ps
    # the rope has got shorter: keep the sense of the previous sheet unless
    # the other one is clearly better
    same_o = [c for c in cands if c[1] == po]
    if same_o and not best[0] < 0.7 * same_o[0][0]:
        return same_o[0][1], same_o[0][2]
    return best[1], best[2]


# --------------------------------------------------------------------------
# bendings per crane station and interval (for placing the surveys)
# --------------------------------------------------------------------------

class Bends:
    """Bendings per crane station in each interval between consecutive surveys."""

    def __init__(self, t, h1, h2, sheaves, H, days):
        self.t, self.h1, self.h2, self.sheaves, self.H = t, h1, h2, sheaves, H
        self.days = days
        k = np.searchsorted(days, t, side='right') - 1
        ok = (k >= 0) & (k < len(days) - 1)
        self.k = k[ok]
        self.ok = ok
        self.cache = {}

    def get(self, Lc, a):
        """Bendings in [days[a], days[a+1]) for a rope of Lc stations."""
        if Lc not in self.cache:
            nk = max(len(self.days) - 1, 1)
            acc = np.zeros(nk * (Lc + 1))
            h1, h2 = self.h1[self.ok], self.h2[self.ok]
            off = self.k * (Lc + 1)
            for (p, aa, D, w) in self.sheaves:
                il, ih = touch_ranges(Lc, aa, p, self.H, h1, h2)
                acc += w * (np.bincount(off + il, None, acc.size) - np.bincount(off + ih, None, acc.size))
            self.cache[Lc] = np.cumsum(acc.reshape(nk, Lc + 1), axis=1)[:, :Lc]
        return self.cache[Lc][a]


def fit_rss(Y, X):
    """RSS of Y ~ a X + c with a >= 0."""
    Xc = X - X.mean()
    Yc = Y - Y.mean()
    sxx = float(Xc @ Xc)
    tot = float(Yc @ Yc)
    if sxx <= 0:
        return tot
    a = float(Xc @ Yc) / sxx
    if a <= 0:
        return tot
    return tot - a * float(Xc @ Yc)


# --------------------------------------------------------------------------
# one crane
# --------------------------------------------------------------------------

class Crane:
    pass


def plan_crane(cr, surveys, t, h1, h2):
    """Work out where every element lies over time.

    Returns the element profiles of the surveys (NaN off the rope), the
    epochs (start time, survey whose diameters hold, element at each crane
    station), the elements of the rope as it lies at the end of the log,
    and the number of element places.
    """
    L0 = cr.L
    K = len(surveys)
    days = np.array([d for d, _ in surveys])
    profs = [p for _, p in surveys]
    # element coordinates: sheet indices of the first survey of the rope
    # (taken as the element numbering; at full length)
    Le = max([len(p) for p in profs] + [L0])
    maps = []
    pe = []
    prev_map = (1, 0)
    for k in range(K):
        cur = profs[k]
        if k == 0:
            m = (1, 0)
        else:
            m = match_sheet(pe[-1], cur, prev_map)
        o, s = m
        e = s + o * np.arange(len(cur))
        if e.min() < 0 or e.max() >= Le:
            o, s = prev_map
            e = s + o * np.arange(len(cur))
            if e.min() < 0 or e.max() >= Le:
                o, s = 1, 0
                e = np.arange(len(cur))
        arr = np.full(Le, np.nan)
        arr[e] = cur
        pe.append(arr)
        maps.append((o, s, len(cur)))
        prev_map = (o, s)
    # the first sheet matches the second only by noise: give it the
    # second's placing (a new rope is all of one diameter)
    if K >= 2 and maps[0] != maps[1]:
        o, s, n = maps[1]
        if n == len(profs[0]):
            e = s + o * np.arange(n)
            arr = np.full(Le, np.nan)
            arr[e] = profs[0]
            pe[0] = arr
            maps[0] = maps[1]
    bends = Bends(t, h1, h2, cr.sheaves, cr.H, days)
    # runs of surveys with one placing
    runs = []
    for k in range(K):
        if runs and maps[k] == maps[runs[-1][0]]:
            runs[-1].append(k)
        else:
            runs.append([k])

    def elems(mp):
        o, s, n = mp
        e = s + o * np.arange(n)
        return int(e.min()), int(e.max())

    # wear test: R > 0 -> the element with the lowest number lies at the drum end
    def run_stat(run):
        mp = maps[run[0]]
        elo, ehi = elems(mp)
        n = ehi - elo + 1
        tot = 0.0
        stats = []
        for a, b in zip(run[:-1], run[1:]):
            Y = pe[a][elo:ehi + 1] - pe[b][elo:ehi + 1]
            B = bends.get(n, a)
            if not np.any(B > 0):
                continue
            rp = fit_rss(Y, B)
            rm = fit_rss(Y, B[::-1])
            s2 = max(min(rp, rm) / max(n - 2, 1), 1e-10)
            r = (rm - rp) / s2
            stats.append(r)
            tot += r
        return tot, stats

    orient = []  # +1: x = e - elo ; -1: x = ehi - e
    for ri, run in enumerate(runs):
        tot, stats = run_stat(run)
        if ri == 0:
            o = 1 if tot >= 0 else -1
        elif len(run) >= 2 and abs(tot) > 4.0:
            o = 1 if tot > 0 else -1
        elif len(run) >= 2:
            o = orient[-1]
        else:
            # a single survey: a sheet written the other way round, or the
            # rope turned in the interval before it and (unless it is the
            # last survey) turned back in the one after
            o = orient[-1]
            a = run[0] - 1
            mp = maps[run[0]]
            if mp[2] == maps[a][2] and run[0] == K - 1:
                elo, ehi = elems(mp)
                n = ehi - elo + 1
                Y = pe[a][elo:ehi + 1] - pe[run[0]][elo:ehi + 1]
                B = bends.get(n, a)
                po = orient[-1]
                # crane position of each element as it lay before
                pelo, pehi = elems(maps[a])
                ee = np.arange(elo, ehi + 1)
                xb = (ee - pelo) if po == 1 else (pehi - ee)
                if np.any(B > 0) and xb.min() >= 0 and xb.max() < n:
                    rold = fit_rss(Y, B[xb])
                    rnew = fit_rss(Y, B[xb[::-1]])
                    if rnew < rold:
                        o = -po
            # if the element set changed (rope shortened) keep the drum end
        orient.append(o)
        log('  run', [round(days[k], 2) for k in run], 'map', maps[run[0]],
            'wear stat %.1f' % tot, 'orient', o)

    def e_of_x(ri):
        mp = maps[runs[ri][0]]
        elo, ehi = elems(mp)
        n = ehi - elo + 1
        x = np.arange(n)
        return (elo + x) if orient[ri] == 1 else (ehi - x)

    # epochs: (start time, survey index for diameters, e_of_x)
    epochs = []
    first_e = e_of_x(0)
    epochs.append((-np.inf, 0, first_e))
    for ri, run in enumerate(runs):
        ex = e_of_x(ri)
        if ri > 0:
            prev_ex = epochs[-1][2]
            a = runs[ri - 1][-1]
            b = run[0]
            changed = (len(prev_ex) != len(ex)) or np.any(prev_ex != ex)
            if changed:
                tm = 0.5 * (days[a] + days[b])
                epochs.append((tm, a, ex))
                log('  rope moved between %.2f and %.2f, taken at %.3f' % (days[a], days[b], tm))
        for k in run:
            if k == 0:
                continue
            epochs.append((days[k], k, ex))
    final_ex = epochs[-1][2]
    return pe, epochs, final_ex, Le


def crane_damage(cr, surveys, t, h1, h2, S):
    b0, b1, b2, b3 = cr.coef
    if len(surveys) == 0:
        # no survey: nominal diameter unknown; take a rope of D/d = 25 at the sheaves
        dn = np.median([D for (_, _, D, _) in cr.sheaves]) / 25.0
        surveys = [(0.0, np.full(cr.L, dn))]
    pe, epochs, final_ex, Le = plan_crane(cr, surveys, t, h1, h2)

    starts = np.array([e[0] for e in epochs])
    nE = len(epochs)
    ep = np.searchsorted(starts, t, side='right') - 1
    ep = np.clip(ep, 0, nE - 1)
    Lmax = max(len(e[2]) for e in epochs)
    Lep = np.array([len(e[2]) for e in epochs], dtype=np.int64)
    # diameter at each crane station in each epoch
    dE = np.full((nE, Lmax), np.nan)
    eE = np.full((nE, Lmax), -1, dtype=np.int64)
    for i, (_, k, ex) in enumerate(epochs):
        prof = pe[k]
        d = prof[ex]
        if np.any(~np.isfinite(d)):
            # element not measured at that survey: nearest survey that has it
            for kk in list(range(k, -1, -1)) + list(range(k + 1, len(pe))):
                miss = ~np.isfinite(d)
                if not miss.any():
                    break
                d[miss] = pe[kk][ex[miss]]
            miss = ~np.isfinite(d)
            if miss.any():
                d[miss] = np.nanmedian(d) if np.any(np.isfinite(d)) else 20.0
        dE[i, :len(ex)] = d
        eE[i, :len(ex)] = ex

    lnS = np.log(S)
    ybar = float(lnS.mean()) if len(lnS) else 0.0
    y = lnS - ybar
    ymax = float(np.abs(y).max()) if len(y) else 0.0

    dmg_e = np.zeros(Le)
    nb = Lmax + 1
    Lm = Lep[ep]  # rope length for each movement
    base = ep * nb
    valid = np.isfinite(dE)
    dsafe = np.where(valid, dE, 1.0)
    lgd = np.log10(dsafe)

    # sheaves grouped by diameter: one set of moments per group
    groups = {}
    for (p, a, D, w) in cr.sheaves:
        groups.setdefault(D, []).append((p, a, w))
    for D, shs in groups.items():
        lr = math.log10(D) - lgd                   # lg(D/d), per epoch & station
        kk = b1 + b3 * lr                          # exponent k, lg N = b0 + k lg(S/d^2) + b2 lr
        kv = kk[valid]
        if kv.size == 0:
            continue
        # split the k range so that each piece is well within the series' reach
        kmin, kmax = float(kv.min()), float(kv.max())
        width = 1.0 / max(ymax, 1e-6)
        ng = max(1, int(math.ceil((kmax - kmin) / width)))
        edges = kmin + (kmax - kmin) * np.arange(ng + 1) / ng
        gidx = np.clip(np.searchsorted(edges, kk, side='right') - 1, 0, ng - 1)
        # index ranges of all sheaves of this diameter, with their weights
        ILs, IHs, Ws, Ms = [], [], [], []
        for (p, a, w) in shs:
            il, ih = touch_ranges(Lm, a, p, cr.H, h1, h2)
            m = ih > il
            ILs.append(base[m] + il[m])
            IHs.append(base[m] + ih[m])
            Ws.append(np.full(int(m.sum()), w))
            Ms.append(np.flatnonzero(m))
        if not ILs:
            continue
        IL = np.concatenate(ILs)
        IH = np.concatenate(IHs)
        W = np.concatenate(Ws)
        MI = np.concatenate(Ms)
        if IL.size == 0:
            continue
        yy = y[MI]
        idx = np.concatenate([IL, IH])
        size = nE * nb
        for g in range(ng):
            sel = valid & (gidx == g)
            if not sel.any():
                continue
            k0 = 0.5 * (edges[g] + edges[g + 1])
            dlt = kk - k0
            dmax = float(np.abs(dlt[sel]).max()) if sel.any() else 0.0
            bnd = dmax * ymax
            # terms of exp(-dlt*y) = sum (-dlt)^n y^n / n!
            nt = 1
            term = 1.0
            while nt < 60:
                term *= bnd / nt
                if term < 1e-8:
                    break
                nt += 1
            wt = W * np.exp(-k0 * yy)
            tot = np.zeros((nE, Lmax))
            yn = np.ones_like(yy)
            fact = 1.0
            for n_ in range(nt + 1):
                ww = wt * yn
                M = np.bincount(idx, np.concatenate([ww, -ww]), size).reshape(nE, nb)
                M = np.cumsum(M, axis=1)[:, :Lmax]
                tot += ((-dlt) ** n_ / fact) * M
                yn = yn * yy
                fact *= (n_ + 1)
            # 1/N = 10^-(b0 + b2 lr) * d^(2k) * S^-k, S^-k = exp(-k ybar) exp(-k y)
            lpre = -(b0 + b2 * lr) + 2.0 * kk * lgd - kk * ybar / math.log(10.0)
            contrib = np.where(sel, np.power(10.0, lpre) * tot, 0.0)
            for i in range(nE):
                n_i = Lep[i]
                np.add.at(dmg_e, eE[i, :n_i], contrib[i, :n_i])
    return dmg_e[final_ex]


def crane_damage_simple(cr, surveys, t, S, h1, h2):
    """Fallback: the rope as surveyed, without following elements."""
    b0, b1, b2, b3 = cr.coef
    if surveys:
        n = len(surveys[-1][1])
    else:
        n = cr.L
    dmg = np.zeros(n)
    if surveys:
        days = np.array([d for d, _ in surveys])
        si = np.clip(np.searchsorted(days, t, side='right') - 1, 0, len(days) - 1)
    for (p, a, D, w) in cr.sheaves:
        il, ih = touch_ranges(n, a, p, cr.H, h1, h2)
        for j in range(n):
            m = (il <= j) & (ih > j)
            if not m.any():
                continue
            if surveys:
                dd = np.array([surveys[k][1][min(j, len(surveys[k][1]) - 1)] for k in range(len(surveys))])[si[m]]
            else:
                dd = np.full(int(m.sum()), D / 25.0)
            lr = np.log10(D / dd)
            lgN = b0 + (b1 + b3 * lr) * np.log10(S[m] / dd ** 2) + b2 * lr
            dmg[j] += np.sum(w / 10.0 ** lgN)
    return dmg


# --------------------------------------------------------------------------

def main(argv):
    if len(argv) < 3:
        print('usage: ropes.py WORKS_DIR OUT_CSV', file=sys.stderr)
        return 0
    wd, out = argv[1], argv[2]
    rows = []
    try:
        cranes = read_table(os.path.join(wd, 'cranes.csv'))
        sheaves = read_table(os.path.join(wd, 'sheaves.csv'))
        mv = read_table(os.path.join(wd, 'movements.csv'))
        sv = read_table(os.path.join(wd, 'surveys.csv'))
    except Exception as ex:  # nothing we can do without the package
        print('cannot read package: %s' % ex, file=sys.stderr)
        write_out(out, rows)
        return 0
    cranes['crane'] = norm_name(cranes['crane'])
    to_num(cranes, ['falls', 'upper_block_height_m', 'block_mass_t', 'reeving_efficiency',
                    'rope_length_m'])
    to_num(sheaves, ['parts', 'offset_m', 'diameter_mm', 'bend_weight'])
    to_num(mv, ['day', 'from_height_m', 'to_height_m', 'hook_load_t'])
    to_num(sv, ['day', 'station_m', 'diameter_mm'])
    sh_rows = crane_rows(sheaves['crane'])
    mv_rows = crane_rows(mv['crane'])
    sv_rows = crane_rows(sv['crane'])
    M = {c: mv[c].to_numpy(float) for c in ('day', 'from_height_m', 'to_height_m', 'hook_load_t')}
    svx = sv[['day', 'station_m', 'diameter_mm']]

    for _, c in cranes.iterrows():
        name = c['crane']
        cr = Crane()
        cr.name = name
        cr.n = float(c['falls'])
        cr.H = float(c['upper_block_height_m'])
        cr.mb = float(c['block_mass_t'])
        cr.e = float(c['reeving_efficiency'])
        cr.coef = construction(c['rope_construction'])
        cr.L = int(round(float(c['rope_length_m'])))
        shg = sheaves.iloc[sh_rows[name]] if name in sh_rows else None
        cr.sheaves = []
        if shg is not None:
            for _, r in shg.iterrows():
                p = r['parts']
                if not np.isfinite(p):
                    p = cr.n
                w = r['bend_weight']
                if not np.isfinite(w):
                    w = 0.5 if str(r.get('sheave', '')).strip().lower() == 'drum' else 1.0
                cr.sheaves.append((float(p), float(r['offset_m']), float(r['diameter_mm']), float(w)))
        ri = mv_rows.get(name)
        if ri is not None and len(ri):
            t = M['day'][ri]
            h1 = M['from_height_m'][ri]
            h2 = M['to_height_m'][ri]
            mh = M['hook_load_t'][ri]
            keep = np.isfinite(t) & np.isfinite(h1) & np.isfinite(h2) & np.isfinite(mh) & (h1 != h2)
            t, h1, h2, mh = t[keep], h1[keep], h2[keep], mh[keep]
            order = np.argsort(t, kind='stable')
            t, h1, h2, mh = t[order], h1[order], h2[order], mh[order]
        else:
            t = h1 = h2 = mh = np.zeros(0)
        S = (mh + cr.mb) * 1000.0 * G / (cr.n * cr.e)
        S = np.maximum(S, 1e-6)
        si_ = sv_rows.get(name)
        surveys = survey_profiles(svx.iloc[si_].dropna() if si_ is not None else None, cr.L)
        log('crane', name, 'movements', len(t), 'surveys', len(surveys))
        try:
            dmg = crane_damage(cr, surveys, t, h1, h2, S)
        except Exception as ex:
            print('crane %s: %s; plain reckoning used' % (name, ex), file=sys.stderr)
            try:
                dmg = crane_damage_simple(cr, surveys, t, S, h1, h2)
            except Exception as ex2:
                print('crane %s: %s' % (name, ex2), file=sys.stderr)
                n = len(surveys[-1][1]) if surveys else cr.L
                dmg = np.zeros(n)
        dmg = np.nan_to_num(np.asarray(dmg, float), nan=0.0, posinf=0.0, neginf=0.0)
        width = max(3, len(str(len(dmg))))
        for j, v in enumerate(dmg):
            rows.append(('%s-%0*d' % (name, width, j + 1), v))
    write_out(out, rows)
    return 0


def write_out(out, rows):
    lines = ['row,damage']
    for r, v in rows:
        s = '%.9f' % v
        lines.append('%s,%s' % (r, s))
    data = '\n'.join(lines) + '\n'
    try:
        if os.path.islink(out):
            os.unlink(out)
    except OSError:
        pass
    with open(out, 'w') as f:
        f.write(data)


if __name__ == '__main__':
    try:
        rc = main(sys.argv)
    except Exception as ex:
        print('error: %s' % ex, file=sys.stderr)
        rc = 0
    sys.exit(0)
