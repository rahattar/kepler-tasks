#!/usr/bin/env python3
"""RS-4 bending damage along crane hoist ropes, for one works package.

    python3 ropes.py WORKS_DIR OUT_CSV

Damage is reckoned per rope element (a piece of rope), as RS-4 section 5 asks.
The survey sheets are used for two things:

* the diameter d of each element (RS-4 section 4), and
* finding out how each sheet and the rope itself lay at each survey.

A sheet may give its stations from the wrong end of the rope (a sheet
error), and a rope may have been turned end for end on the crane between two
surveys (then every element moves from x to L - x).  Neither is written in
the package, so both are inferred from the diameters:

* the diameter profile is a fingerprint of the rope: consecutive sheets, put
  in the same element order, differ only by a little wear and gauge noise, and
* the wear in a period follows the bendings the elements had in it, which
  tells where on the crane each element lay.

A small Viterbi search over the states (sheet orientation, rope placement) at
each survey picks the most likely story; when the rope was turned within a
period the turning moment is estimated from the wear pattern of that period.
"""
import sys
import os
import math

import numpy as np

G = 9.80665
COEF = {
    '8x36': (-1.214, 0.887, 7.432, -2.103),
    '6x36': (-1.371, 0.934, 7.518, -2.146),
}
LN10 = math.log(10.0)

NCH = 64                    # chunks per survey period when locating a turn
LOG_P_TURN = math.log(0.02)     # prior: rope turned end for end in a period
LOG_P_TURN_FIRST = math.log(0.002)  # ... in the first period (frame not yet fixed)
LOG_P_STAY = math.log(0.98)
LOG_P_HIDDEN_TURN = math.log(0.05)   # extra: turn hidden by a sheet given from the other end
MIX_TEMPER = 0.5                # weight of within-period evidence for a turning moment
LOG_P_OFLIP = math.log(0.10)    # prior: sheet orientation differs from previous sheet
LOG_P_OSAME = math.log(0.90)
LOG_P_O0REV = math.log(0.20)    # prior: first sheet given from the wrong end
LOG_P_O0OK = math.log(0.80)
LAST_MARGIN = 0.0               # diagnostics (ROPES_DEBUG)
_LAST_BEST = 0.0


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def _read_csv(path):
    import pandas as pd
    df = pd.read_csv(path, skipinitialspace=True)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def _num(series):
    import pandas as pd
    return pd.to_numeric(series, errors='coerce').to_numpy(dtype=float)


def _names(series):
    return np.array([str(x).strip() for x in series.to_numpy()], dtype=object)


def _groups(series):
    """{stripped name: row indices}, fast for long columns."""
    import pandas as pd
    codes, uniq = pd.factorize(series, use_na_sentinel=False)
    names = [str(u).strip() for u in uniq]
    order = np.argsort(codes, kind='stable')
    bounds = np.searchsorted(codes[order], np.arange(len(uniq) + 1))
    out = {}
    for j, nm in enumerate(names):
        idx = order[bounds[j]:bounds[j + 1]]
        if nm in out:
            out[nm] = np.sort(np.concatenate([out[nm], idx]), kind='stable')
        else:
            out[nm] = idx
    return out


def coef_for(construction):
    key = str(construction).strip().lower().replace(' ', '').replace('×', 'x')
    if key in COEF:
        return COEF[key]
    for k, v in COEF.items():
        if k in key:
            return v
    return COEF['6x36']


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------

def sheave_ranges(L, K, H, h0, h1, parts, offset):
    """Physical station index range [lo, hi) passed by a sheave's touch point."""
    x0 = L - offset - parts * (H - h0)
    x1 = L - offset - parts * (H - h1)
    lo = np.ceil(np.minimum(x0, x1) - 0.5)
    hi = np.floor(np.maximum(x0, x1) - 0.5) + 1.0
    lo = np.nan_to_num(lo, nan=0.0, posinf=K, neginf=0.0)
    hi = np.nan_to_num(hi, nan=0.0, posinf=K, neginf=0.0)
    lo = np.clip(lo, 0, K).astype(np.int64)
    hi = np.clip(hi, 0, K).astype(np.int64)
    hi = np.maximum(hi, lo)
    return lo, hi


def seg_cover(lo, hi, seg, nseg, K, w=None):
    """For every (segment, station): sum of w over movements covering it."""
    n = nseg * (K + 1)
    base = seg * (K + 1)
    a = np.bincount(base + lo, weights=w, minlength=n)
    a -= np.bincount(base + hi, weights=w, minlength=n)
    return np.cumsum(a.reshape(nseg, K + 1), axis=1)[:, :K]


# --------------------------------------------------------------------------
# surveys
# --------------------------------------------------------------------------

def build_sheets(days, stations, diams, K):
    """Return (sheet_days, array nsheet x K of diameters, NaN where missing)."""
    ok = np.isfinite(days) & np.isfinite(stations)
    days, stations, diams = days[ok], stations[ok], diams[ok]
    if len(days) == 0:
        return np.zeros(0), np.zeros((0, K))
    order = np.argsort(days, kind='stable')
    days, stations, diams = days[order], stations[order], diams[order]
    out_days, out_sheets = [], []
    udays, starts = np.unique(days, return_index=True)
    ends = list(starts[1:]) + [len(days)]
    for d, s, e in zip(udays, starts, ends):
        st = stations[s:e]
        dm = diams[s:e]
        idx = np.rint(st - 0.5).astype(np.int64)
        good = (idx >= 0) & (idx < K) & (np.abs(st - 0.5 - idx) < 0.26)
        if good.mean() < 0.8:
            # stations not on the 0.5 m + 1 m grid: map by rank / scale
            u = np.unique(st)
            if len(u) == K:
                idx = np.searchsorted(u, st)
            else:
                lo_, hi_ = st.min(), st.max()
                if hi_ > lo_:
                    idx = np.rint((st - lo_) / (hi_ - lo_) * (K - 1)).astype(np.int64)
                else:
                    idx = np.zeros(len(st), np.int64)
            good = (idx >= 0) & (idx < K)
        idx, dm = idx[good], dm[good]
        if len(idx) == 0:
            continue
        cnt = np.bincount(idx, minlength=K)
        if cnt.max() > 1 and len(idx) >= 1.5 * K:
            # several sheets written on the same day: split by occurrence
            occ = np.zeros(len(idx), np.int64)
            seen = {}
            for j, k in enumerate(idx):
                c = seen.get(k, 0)
                occ[j] = c
                seen[k] = c + 1
            for o in range(int(occ.max()) + 1):
                m = occ == o
                if m.sum() < 0.3 * K:
                    continue
                arr = np.full(K, np.nan)
                arr[idx[m]] = dm[m]
                out_days.append(d)
                out_sheets.append(arr)
        else:
            sm = np.bincount(idx, weights=np.nan_to_num(dm, nan=0.0), minlength=K)
            cv = np.bincount(idx, weights=np.isfinite(dm).astype(float), minlength=K)
            with np.errstate(invalid='ignore', divide='ignore'):
                arr = np.where(cv > 0, sm / np.maximum(cv, 1), np.nan)
            out_days.append(d)
            out_sheets.append(arr)
    if not out_sheets:
        return np.zeros(0), np.zeros((0, K))
    return np.array(out_days, float), np.array(out_sheets, float)


def _running_median(a, w=7):
    K = len(a)
    h = w // 2
    p = np.pad(a, h, mode='edge')
    from numpy.lib.stride_tricks import sliding_window_view
    return np.median(sliding_window_view(p, w), axis=1)[:K]


def clean_sheets(days, S):
    """Drop impossible readings, fill gaps; drop sheets that are mostly empty."""
    keep_d, keep_s = [], []
    K = S.shape[1] if S.ndim == 2 else 0
    for d, a in zip(days, S):
        a = a.astype(float).copy()
        a[~np.isfinite(a) | (a <= 0)] = np.nan
        if np.isfinite(a).sum() < max(3, 0.5 * K):
            continue
        med = np.nanmedian(a)
        a[np.abs(a - med) > 0.25 * med] = np.nan
        if np.isfinite(a).sum() < max(3, 0.5 * K):
            continue
        v = np.isfinite(a)
        if not v.all():
            a = np.interp(np.arange(K), np.flatnonzero(v), a[v])
        if K >= 7:
            rm = _running_median(a, 7)
            bad = np.abs(a - rm) > max(0.5, 0.03 * med)
            if bad.any() and bad.mean() < 0.2:
                a[bad] = rm[bad]
        keep_d.append(d)
        keep_s.append(a)
    if not keep_s:
        return np.zeros(0), np.zeros((0, K))
    # a sheet out of scale with the others (wrong unit, misplaced point)
    meds = np.array([np.median(a) for a in keep_s])
    ref = float(np.median(meds))
    out_d, out_s = [], []
    for d, a, md in zip(keep_d, keep_s, meds):
        if ref > 0 and abs(md / ref - 1.0) > 0.2:
            for f in (10.0, 0.1, 25.4, 1 / 25.4, 100.0, 0.01):
                if abs(md * f / ref - 1.0) < 0.05:
                    a = a * f
                    break
            else:
                continue
        out_d.append(d)
        out_s.append(a)
    if not out_s:
        return np.zeros(0), np.zeros((0, K))
    return np.array(out_d, float), np.array(out_s, float)


# --------------------------------------------------------------------------
# where did the rope and the sheets lie: Viterbi over survey states
# --------------------------------------------------------------------------

def _ll(ss, n):
    return -0.5 * n * np.log(np.maximum(ss, 0.0) / n + 1e-8)


def _pat_stats(P, Q=None):
    """Centred wear patterns and their sums of squares, for _ss()."""
    pc = P - P.mean(axis=-1, keepdims=True)
    st = {'pc': pc, 'spp': np.einsum('...k,...k->...', pc, pc), 'q': Q is not None}
    if Q is not None:
        qc = Q - Q.mean(axis=-1, keepdims=True)
        st['qc'] = qc
        st['sqq'] = np.einsum('...k,...k->...', qc, qc)
        st['spq'] = np.einsum('...k,...k->...', pc, qc)
    return st


def _ss(inc, st):
    """Residual SS of inc ~ a*P + b*Q + c with a, b >= 0.  P is the wear
    pattern of the sheaves, Q that of the drum (the two wear the rope at
    different rates); st from _pat_stats(P, Q), possibly stacked over a
    leading axis."""
    ic = inc - inc.mean()
    sii = float(ic @ ic)
    spp = st['spp']
    sip = st['pc'] @ ic
    with np.errstate(invalid='ignore', divide='ignore', over='ignore'):
        red = np.where((spp > 0) & (sip > 0), sip * sip / np.where(spp > 0, spp, 1.0), 0.0)
        if st['q']:
            sqq, spq = st['sqq'], st['spq']
            siq = st['qc'] @ ic
            red2 = np.where((sqq > 0) & (siq > 0), siq * siq / np.where(sqq > 0, sqq, 1.0), 0.0)
            det = spp * sqq - spq * spq
            okd = det > 1e-12 * np.maximum(spp * sqq, 1e-300)
            dd = np.where(okd, det, 1.0)
            a = (sqq * sip - spq * siq) / dd
            b = (spp * siq - spq * sip) / dd
            full = np.where(okd & (a >= 0) & (b >= 0), a * sip + b * siq, 0.0)
            red = np.maximum(np.maximum(red, red2), full)
    return sii - red


def _fit_ss(inc, P, Q=None):
    return _ss(inc, _pat_stats(P, Q))


def infer_layout(sheets, Bch, Dch=None, nch=NCH):
    """sheets: nb x K diameters.  Bch: (nb-1) x NCH x K wear-weighted bendings
    over the sheaves per period chunk, physical positions; Dch the same over
    the drum (or None).  Returns (q, pi, turn) where q[i] = +1/-1 maps
    sheet i listing to element frame (element = index if +1, reversed if -1),
    pi[i] = placement at survey i (+1: element k at physical k, -1: at K-1-k),
    turn[i] = fractional chunk boundary in period i (between sheets i-1 and i)
    at which the placement changed, or None."""
    nb, K = sheets.shape
    states = [(1, 1), (-1, 1), (1, -1), (-1, -1)]   # (q, pi)
    NEG = -1e300

    def o_of(s):
        return s[0] * s[1]

    score = np.full(4, NEG)
    for a, s in enumerate(states):
        if s[1] == 1:   # element frame defined by placement at day 0
            score[a] = LOG_P_O0OK if o_of(s) == 1 else LOG_P_O0REV
    back = []
    turn_post = []
    rev = slice(None, None, -1)
    def patterns(Xc):
        Xt = Xc.sum(axis=0)
        C = np.concatenate([np.zeros((1, K)), np.cumsum(Xc, axis=0)], axis=0)   # NCH+1 x K
        R = Xt[None, :] - C
        return {(1, 1): Xt, (-1, -1): Xt[rev],
                (1, -1): C + R[:, rev], (-1, 1): C[:, rev] + R}

    for i in range(1, nb):
        Va, Vb = sheets[i - 1], sheets[i]
        PB = patterns(Bch[i - 1])
        PD = patterns(Dch[i - 1]) if Dch is not None else None
        stats = {k: _pat_stats(PB[k], PD[k] if PD is not None else None) for k in PB}
        # wear fit of each (qa, qb, pa, pb); flipping all four signs reverses
        # both the increments and the patterns, which leaves the fit unchanged
        fit = {}
        for qb in (1, -1):
            inc = Va - (Vb if qb == 1 else Vb[rev])
            for (pa, pb), st in stats.items():
                ss = _ss(inc, st)
                if pa == pb:
                    fit[(1, qb, pa, pb)] = (float(_ll(ss, K)), None)
                else:
                    # turned within the period: the wear is a mixture of the
                    # two placements.  The gain of the mixture over the better
                    # of its two ends is tempered, as the wear model is only
                    # approximate and a free turning moment can fit noise.
                    llj = MIX_TEMPER * _ll(ss, K)
                    mx = llj.max()
                    pj = np.exp(llj - mx)
                    ll = float(mx + math.log(pj.sum() / len(pj))) / MIX_TEMPER
                    lend = float(max(llj[0], llj[-1])) / MIX_TEMPER
                    ll = lend + MIX_TEMPER * (ll - lend)
                    fit[(1, qb, pa, pb)] = (ll, float((pj * np.arange(len(pj))).sum() / pj.sum()))
        trans = np.full((4, 4), NEG)
        tpost = {}
        for a, sa in enumerate(states):
            if score[a] <= NEG / 2:
                continue
            for b, sb in enumerate(states):
                qa, pa = sa
                qb, pb = sb
                if qa == 1:
                    ll, tj = fit[(1, qb, pa, pb)]
                else:
                    ll, tj = fit[(1, -qb, -pa, -pb)]
                if pa == pb:
                    lp = LOG_P_STAY
                else:
                    lp = LOG_P_TURN if i > 1 else LOG_P_TURN_FIRST
                    tpost[(a, b)] = tj
                lo = LOG_P_OSAME if o_of(sa) == o_of(sb) else LOG_P_OFLIP
                if pa != pb and qa == qb:
                    # turned, yet the sheets run on as before: only the wear
                    # can tell, so ask for more of it
                    lo += LOG_P_HIDDEN_TURN
                trans[a, b] = ll + lp + lo
        new = np.full(4, NEG)
        bk = np.zeros(4, np.int64)
        for b in range(4):
            cand = score + trans[:, b]
            a = int(np.argmax(cand))
            new[b] = cand[a]
            bk[b] = a
        back.append(bk)
        turn_post.append(tpost)
        score = new
    # backtrack
    global LAST_MARGIN
    LAST_MARGIN = float(max(score[0], score[1]) - max(score[2], score[3]))
    global _LAST_BEST
    _LAST_BEST = float(score.max())
    path = [int(np.argmax(score))]
    for i in range(nb - 1, 0, -1):
        path.append(int(back[i - 1][path[-1]]))
    path.reverse()
    if os.environ.get('ROPES_DEBUG'):
        alt = [2 + int(np.argmax(score[2:]))] if states[path[-1]][1] == 1 else [int(np.argmax(score[:2]))]
        for i in range(nb - 1, 0, -1):
            alt.append(int(back[i - 1][alt[-1]]))
        alt.reverse()
        sys.stderr.write('  alternative: %s\n' % ' '.join(
            '%d:q%+d,p%+d' % (i, states[a][0], states[a][1]) for i, a in enumerate(alt)
            if i == 0 or alt[i] != alt[i - 1]))
    q = [states[s][0] for s in path]
    pi = [states[s][1] for s in path]
    turn = [None] * nb
    for i in range(1, nb):
        if pi[i] != pi[i - 1]:
            turn[i] = turn_post[i - 1].get((path[i - 1], path[i]), nch / 2.0)
    return q, pi, turn


# --------------------------------------------------------------------------
# one crane
# --------------------------------------------------------------------------

def crane_damage(cr, shv, mov, sv, analyse=True):
    L = float(cr['L'])
    K = int(round(L))
    if K <= 0:
        return np.zeros(0)
    n = float(cr['n'])
    H = float(cr['H'])
    b0, b1, b2, b3 = coef_for(cr['constr'])

    t, h0, h1, mh = mov
    ok = np.isfinite(t) & np.isfinite(h0) & np.isfinite(h1) & np.isfinite(mh)
    t, h0, h1, mh = t[ok], h0[ok], h1[ok], mh[ok]
    order = np.argsort(t, kind='stable')
    t, h0, h1, mh = t[order], h0[order], h1[order], mh[order]
    M = len(t)

    sdays, sheets = build_sheets(sv[0], sv[1], sv[2], K)
    sdays, sheets = clean_sheets(sdays, sheets)
    nb = len(sdays)
    if M == 0 or nb == 0 or len(shv) == 0:
        return np.zeros(K)

    S = (np.maximum(mh, 0.0) + float(cr['mb'])) * 1000.0 * G / (n * float(cr['e']))
    S = np.maximum(S, 1e-6)
    lgS = np.log10(S)

    ranges = []
    for (parts, offset, D, w, _isdrum) in shv:
        lo, hi = sheave_ranges(L, K, H, h0, h1, parts, offset)
        ranges.append((lo, hi, D, w))

    per_raw = np.searchsorted(sdays, t, side='right') - 1       # sheet in force
    per = np.maximum(per_raw, 0)

    # ---- layout of sheets and rope
    q = [1] * nb
    pi = [1] * nb
    turn = [None] * nb
    nch = int(max(8, min(NCH, 2400 // max(nb - 1, 1))))
    if analyse and nb >= 2:
        try:
            npd = nb - 1
            NCHl = nch
            starts = np.searchsorted(per_raw, np.arange(nb), side='left')
            ends = np.searchsorted(per_raw, np.arange(nb), side='right')
            segid = np.full(M, npd * NCHl, np.int64)
            for i in range(1, nb):
                s, e = starts[i - 1], ends[i - 1]      # movements between sheet i-1 and i
                if e > s:
                    segid[s:e] = (i - 1) * NCHl + ((np.arange(e - s) * NCHl) // (e - s))
            # wear follows the bendings, heavier lifts wearing more; the drum
            # and the sheaves wear the rope at their own rates
            sw = S / S.mean()
            sw = sw * sw
            drum = [j for j, s_ in enumerate(shv) if s_[4]]
            if not drum or len(drum) == len(shv):
                drum = [j for j, s_ in enumerate(shv) if s_[3] < 1.0]
            if len(drum) == len(shv):
                drum = []
            groups = [[j for j in range(len(shv)) if j not in drum]]
            if drum:
                groups.append(drum)
            chs = []
            for grp in groups:
                lo_all = np.concatenate([ranges[j][0] for j in grp])
                hi_all = np.concatenate([ranges[j][1] for j in grp])
                sg_all = np.tile(segid, len(grp))
                w_all = np.tile(sw, len(grp))
                B = seg_cover(lo_all, hi_all, sg_all, npd * NCHl + 1, K, w_all)
                chs.append(B[:npd * NCHl].reshape(npd, NCHl, K))
            q, pi, turn = infer_layout(sheets, chs[0], chs[1] if len(chs) > 1 else None, NCHl)
        except Exception:
            q, pi, turn = [1] * nb, [1] * nb, [None] * nb
    if os.environ.get('ROPES_DEBUG'):
        msg = []
        for i in range(nb):
            tn = ''
            if turn[i] is not None:
                s0 = np.searchsorted(per_raw, i - 1, side='left')
                e0 = np.searchsorted(per_raw, i - 1, side='right')
                c0 = min(max(s0 + int(round(turn[i] * (e0 - s0) / nch)), 0), M - 1)
                tn = ' turned@%.2f' % t[c0]
            msg.append('%.2f:q%+d,p%+d%s' % (sdays[i], q[i], pi[i], tn))
        sys.stderr.write('%s margin(final as laid vs turned)=%.1f %s\n' % (
            cr.get('name', '?'), LAST_MARGIN, ' '.join(msg)))

    # element-frame diameters of each sheet
    dE = np.array([sheets[i] if q[i] == 1 else sheets[i][::-1] for i in range(nb)])

    # placement of every movement
    place = np.array(pi, np.int64)[per]
    if any(tn is not None for tn in turn):
        starts = np.searchsorted(per_raw, np.arange(nb), side='left')
        ends = np.searchsorted(per_raw, np.arange(nb), side='right')
        for i in range(1, nb):
            if turn[i] is None:
                continue
            s, e = starts[i - 1], ends[i - 1]
            cut = s + int(round(turn[i] * (e - s) / nch))
            place[s:cut] = pi[i - 1]
            place[cut:e] = pi[i]
    seg = per * 2 + (place < 0)
    nseg = 2 * nb

    # ---- damage, by moments of the load over each segment
    # Every (segment, station) needs sum_m 10^-(A_k + B_k lg S_m), with A_k, B_k
    # from the element's diameter.  Around a central exponent Bc this is
    # 10^-(A_k + B_k yc) * sum_j (-(B_k - Bc) ln10)^j / j! * M_j, with the load
    # moments M_j = sum_m 10^(-Bc y_m) y_m^j, y = lg S - yc, each one cumulative
    # sum over the stations.  The load range is cut into bins if it is wide.
    lgd_all = np.log10(dE)                                   # nb x K, element frame
    lgd_seg = np.empty((nseg, K))
    lgd_seg[0::2] = lgd_all
    lgd_seg[1::2] = lgd_all[:, ::-1]                         # physical order when turned
    ymin, ymax_ = float(lgS.min()), float(lgS.max())
    dB = []
    for (lo, hi, D, w) in ranges:
        Bk_all = b1 + b3 * (math.log10(D) - lgd_all)
        dB.append(float(Bk_all.max() - Bk_all.min()))
    zfull = max(dB + [0.0]) * 0.5 * LN10 * max(ymax_ - ymin, 0.0)
    nyb = int(min(64, max(1, math.ceil(zfull / 0.5))))
    if nyb > 1:
        width = (ymax_ - ymin) / nyb
        yb = np.minimum(((lgS - ymin) / width).astype(np.int64), nyb - 1)
        ycs = ymin + (np.arange(nyb) + 0.5) * width
    else:
        yb = np.zeros(M, np.int64)
        ycs = np.array([0.5 * (ymin + ymax_)])
    y = lgS - ycs[yb]
    yhalf = float(np.abs(y).max()) if M else 0.0
    seg2 = seg * nyb + yb
    nseg2 = nseg * nyb
    lgd2 = np.repeat(lgd_seg, nyb, axis=0)                   # nseg2 x K
    yc2 = np.tile(ycs, nseg)[:, None]
    dmgE = np.zeros(K)
    # sheaves of one diameter and bend weight share all coefficients
    grouped = {}
    for (lo, hi, D, w) in ranges:
        if w != 0:
            grouped.setdefault((D, w), []).append((lo, hi))
    for (D, w), lst in grouped.items():
        lo = np.concatenate([g[0] for g in lst])
        hi = np.concatenate([g[1] for g in lst])
        ng = len(lst)
        sgg = np.tile(seg2, ng) if ng > 1 else seg2
        lgD = math.log10(D)
        Bk_all = b1 + b3 * (lgD - lgd_all)
        Bc = 0.5 * (Bk_all.min() + Bk_all.max())
        z = 0.5 * float(Bk_all.max() - Bk_all.min()) * LN10 * yhalf
        J = 0
        term = 1.0
        while J < 60:
            term = term * z / (J + 1)
            if term * math.exp(z) < 1e-9:
                break
            J += 1
        base = np.exp(-Bc * LN10 * y)
        lDd = lgD - lgd2
        Bk = b1 + b3 * lDd
        Ak = b0 - 2.0 * Bk * lgd2 + b2 * lDd
        dl = -(Bk - Bc) * LN10
        acc = np.zeros((nseg2, K))
        fac = np.ones((nseg2, K))
        yj = np.ones_like(y)
        for j in range(J + 1):
            wj = base * yj
            acc += fac * seg_cover(lo, hi, sgg, nseg2, K, np.tile(wj, ng) if ng > 1 else wj)
            fac *= dl / (j + 1)
            yj = yj * y
        with np.errstate(over='ignore', under='ignore', invalid='ignore'):
            dphys = w * np.power(10.0, -Ak - Bk * yc2) * acc     # nseg2 x K, physical
        dphys = np.where(np.isfinite(dphys), dphys, 0.0)
        dseg = dphys.reshape(nseg, nyb, K).sum(axis=1)
        dmgE += dseg[0::2].sum(axis=0) + dseg[1::2].sum(axis=0)[::-1]
    # ---- the rope as it lies at the end of the log
    final = pi[-1]
    if M:
        final = int(place[-1])
    out = dmgE if final == 1 else dmgE[::-1]
    out = np.where(np.isfinite(out), out, 0.0)
    out = np.maximum(out, 0.0)
    if out.size and out.max() > 0:
        out[out < 1e-12 * out.max()] = 0.0       # round-off of the cumulative sums
    return out


# --------------------------------------------------------------------------
# package
# --------------------------------------------------------------------------

def run(wd):
    import pandas as pd
    cr = _read_csv(os.path.join(wd, 'cranes.csv'))
    cranes = []
    cn = _names(cr['crane'])
    falls = _num(cr['falls'])
    Hs = _num(cr['upper_block_height_m'])
    mbs = _num(cr['block_mass_t'])
    es = _num(cr['reeving_efficiency'])
    Ls = _num(cr['rope_length_m'])
    cons = cr['rope_construction'].astype(str).to_numpy()
    for i in range(len(cn)):
        cranes.append({'name': cn[i], 'n': falls[i], 'H': Hs[i], 'mb': mbs[i], 'e': es[i],
                       'constr': cons[i], 'L': Ls[i]})

    shv = {}
    try:
        sh = _read_csv(os.path.join(wd, 'sheaves.csv'))
        sn = _names(sh['crane'])
        nm_ = _names(sh['sheave']) if 'sheave' in sh.columns else np.array([''] * len(sn))
        p_ = _num(sh['parts'])
        a_ = _num(sh['offset_m'])
        D_ = _num(sh['diameter_mm'])
        w_ = _num(sh['bend_weight'])
        for i in range(len(sn)):
            if np.isfinite(p_[i]) and np.isfinite(a_[i]) and np.isfinite(D_[i]) and D_[i] > 0:
                isdrum = 'drum' in str(nm_[i]).lower()
                w = w_[i] if np.isfinite(w_[i]) else (0.5 if isdrum else 1.0)
                shv.setdefault(sn[i], []).append((p_[i], a_[i], D_[i], w, isdrum))
    except Exception:
        pass

    movs = {}
    try:
        mv = _read_csv(os.path.join(wd, 'movements.csv'))
        cols = [_num(mv['day']), _num(mv['from_height_m']), _num(mv['to_height_m']),
                _num(mv['hook_load_t'])]
        for nm, sl in _groups(mv['crane']).items():
            movs[nm] = tuple(c[sl] for c in cols)
        del mv
    except Exception:
        pass

    svs = {}
    try:
        sv = _read_csv(os.path.join(wd, 'surveys.csv'))
        cols = [_num(sv['day']), _num(sv['station_m']), _num(sv['diameter_mm'])]
        for nm, sl in _groups(sv['crane']).items():
            svs[nm] = tuple(c[sl] for c in cols)
    except Exception:
        pass

    rows = []
    for c in cranes:
        K = int(round(c['L'])) if np.isfinite(c['L']) else 0
        if K <= 0:
            continue
        dm = None
        emp = (np.zeros(0),) * 4
        for analyse in (True, False):
            try:
                dm = crane_damage(c, shv.get(c['name'], []), movs.get(c['name'], emp),
                                  svs.get(c['name'], (np.zeros(0),) * 3), analyse=analyse)
                if dm is not None and len(dm) == K and np.all(np.isfinite(dm)):
                    break
            except Exception:
                dm = None
        if dm is None or len(dm) != K:
            dm = np.zeros(K)
        width = max(3, len(str(K)))
        for k in range(K):
            rows.append('%s-%0*d,%s' % (c['name'], width, k + 1, _fmt(dm[k])))
    return rows


def _fmt(x):
    x = float(x)
    if not math.isfinite(x) or x <= 0:
        return '0'
    s = '%.12f' % x
    if float(s) == 0.0 or x < 1e-6:
        s = np.format_float_positional(x, precision=8, unique=False, fractional=False, trim='-')
    return s


def write_out(path, rows):
    data = ('row,damage\n' + ''.join(r + '\n' for r in rows)).encode('ascii', 'replace')
    d = os.path.dirname(os.path.abspath(path)) or '.'
    tmp = os.path.join(d, '.%s.tmp%d' % (os.path.basename(path), os.getpid()))
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
        return
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
    try:
        if os.path.islink(path):
            os.unlink(path)
    except Exception:
        pass
    with open(path, 'wb') as f:
        f.write(data)


def main():
    if len(sys.argv) < 3:
        sys.stderr.write('usage: ropes.py WORKS_DIR OUT_CSV\n')
        return
    wd, out = sys.argv[1], sys.argv[2]
    try:
        rows = run(wd)
    except Exception as ex:
        sys.stderr.write('ropes.py: %s\n' % ex)
        rows = []
    write_out(out, rows)


if __name__ == '__main__':
    try:
        main()
    except Exception as ex:
        sys.stderr.write('ropes.py: %s\n' % ex)
    sys.exit(0)
