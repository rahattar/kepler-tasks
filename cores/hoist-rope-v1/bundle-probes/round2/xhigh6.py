#!/usr/bin/env python3
"""Bending fatigue damage along crane hoist ropes to RS-4 (issue 3), for one works package.

    python3 ropes.py WORKS_DIR OUT_CSV

WORKS_DIR holds cranes.csv, sheaves.csv, movements.csv and surveys.csv as works_package.md lays out.
OUT_CSV gets the table `row,damage`, one row per station of each crane's rope at its last survey.

The model (RS-4)
----------------
A sheave with p falls between it and the dead end touches the rope at x = L - a - p (H - h). In a movement
from h0 to h1 every element strictly between the two touch points is bent once over it, which counts
w / N, with

    lg N = b0 + (b1 + b3 lg(D/d)) lg(S/d^2) + b2 lg(D/d),     S = (m_h + m_b) g / (n e),

and d the element's diameter at the last survey not later than the movement. The damage asked for is the
sum at each station of the last survey, at the end of the log.

The computation
---------------
Station s is touched by contact k at the hook height h_ks = H - (L - a_k - x_s) / p_k, which rises with s,
so a movement bends a contiguous run of stations over every contact. 1/N splits into a factor of the
movement and contact, a factor of the station and contact, and the cross term 10^(b3 lg d lg S). With both
logarithms centred, the cross term is a short power series in (lg d - c_d)(lg S - c_S), so the damage is a
sum of difference arrays (one bincount per contact and power) times station factors. The result is exact
to about 1e-12 relative, in O(movements x contacts).

Rope turns and mirrored surveys
-------------------------------
The surveys are the only record of what happened to a rope. Two events look the same when one survey is
compared with the next (the diameter profile comes out reversed):

  A  the rope was turned end for end: every element moved from x to L - x. Its damage goes with it, and
     its later wear follows the bending at its new place;
  B  the gauge was run, and the survey recorded, from the dead end: the rope did not move.

The worn profile of a rope follows its bending closely. Each element wears as u(t) + k_i C_i(t)^alpha,
where C_i is the element's own accumulated damage, u(t) is the uniform settling of the rope, k_i is a
factor of the element and alpha < 1. That law fits the example packages to gauge noise. So each event
found in the surveys is tested both ways. For A the turn is tried at every point of the survey window,
and the reading that fits the surveys best is kept. If the fit cannot tell the two apart, the program
takes B: a turn that happened just before the next survey is the only form of A that looks like B. The
time of a turn is then pinned, where possible, to a time that cannot be more than SAFE (as a fraction of
the rope's greatest damage) from the result for any other time in the window.
"""
import math
import os
import sys
import tempfile
import time
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
np.seterr(all='ignore')

G_ACC = 9.80665
LN10 = math.log(10.0)
COEF = {'8x36': (-1.214, 0.887, 7.432, -2.103),
        '6x36': (-1.371, 0.934, 7.518, -2.146)}
NSUB = 32            # parts a survey window with a rope event is cut into, to place a turn in time
SAFE = 0.07          # error allowed by the choice of the time of a turn, fraction of the greatest damage
ALPHAS = np.arange(0.35, 1.30, 0.05)   # exponents tried for the wear law
SERIES_TOL = 1e-11   # truncation of the power series of the cross term
TIME_GUARD = 3.0     # CPU seconds after which no further wear analysis is started
MAX_EVENTS = 8       # more reversals than this in one rope's surveys are not analysed


# ----------------------------------------------------------------------------------------------- input

def read_table(path):
    df = pd.read_csv(path, skipinitialspace=True)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def text_col(df, name):
    s = df[name]
    return s.astype(str).str.strip()


def num_col(df, name):
    return pd.to_numeric(df[name], errors='coerce').to_numpy(dtype=np.float64)


def construction_key(s):
    k = str(s).strip().lower().replace(' ', '').replace('×', 'x').replace('*', 'x')
    return k


# ------------------------------------------------------------------------------------- crane geometry

class Crane:
    pass


def build_surveys(sv, L):
    """Readings of every survey on the station grid of the last survey: (days, grid, rd[E, ns])."""
    sv = sv[np.isfinite(sv['day']) & np.isfinite(sv['station_m'])]
    good = np.isfinite(sv['diameter_mm']) & (sv['diameter_mm'] > 0)
    sv = sv[good]
    if len(sv) == 0:
        return None
    days = np.unique(sv['day'].to_numpy())
    rows = []
    for dday in days:
        g = sv[sv['day'] == dday]
        g = g.groupby('station_m', sort=True)['diameter_mm'].mean()
        rows.append((dday, g.index.to_numpy(dtype=np.float64), g.to_numpy(dtype=np.float64)))
    grid = rows[-1][1]
    rd = np.empty((len(rows), len(grid)))
    for j, (_, x, d) in enumerate(rows):
        if len(x) == len(grid) and np.allclose(x, grid):
            rd[j] = d
        elif len(x) == 1:
            rd[j] = d[0]
        else:
            rd[j] = np.interp(grid, x, d)
    return days, grid, rd


def mad(r):
    med = np.median(r)
    return np.median(np.abs(r - med))


def find_flips(rd):
    """Survey windows w across which the recorded profile comes out reversed (survey w -> w+1)."""
    flips = []
    for j in range(len(rd) - 1):
        a, b = rd[j], rd[j + 1]
        ri = mad(b - a)
        rr = mad(b - a[::-1])
        if rr < 0.5 * ri and ri - rr > 0.02:
            flips.append(j)
    return flips


# ------------------------------------------------------------------------------- damage accumulation

def accumulate(cr, seg, nseg):
    """Difference-array sums A[m, seg, k, s] = sum over movements of segment seg that bend station s
    over contact k of W_jk tau_j^m."""
    ns = cr.ns
    K = len(cr.p)
    M = cr.M
    A = np.zeros((M, nseg, K, ns))
    if cr.nmov == 0:
        return A
    tau = cr.tau
    width = ns + 1
    base = seg * width
    size = nseg * width
    powers = [np.ones_like(tau)]
    for m in range(1, M):
        powers.append(powers[-1] * tau)
    grid = cr.grid
    dx = grid[1] - grid[0] if ns > 1 else 1.0
    uniform = ns > 1 and dx > 0 and np.allclose(np.diff(grid), dx, rtol=0, atol=1e-9)
    for k in range(K):
        if uniform:
            # station s is passed iff lo < h_ks < hi, i.e. X(lo) < x_s < X(hi), X(h) = L - a - p (H - h)
            pk, ak = cr.p[k], cr.a[k]
            zlo = (cr.L - ak - pk * (cr.H - cr.lo) - grid[0]) / dx
            zhi = (cr.L - ak - pk * (cr.H - cr.hi) - grid[0]) / dx
            i0 = (np.floor(np.clip(zlo, -1.0, ns)) + 1).astype(np.int64)
            i1 = np.ceil(np.clip(zhi, 0.0, ns)).astype(np.int64)
            np.clip(i0, 0, ns, out=i0)
        else:
            hk = cr.hk[k]
            i0 = np.searchsorted(hk, cr.lo, side='right')
            i1 = np.searchsorted(hk, cr.hi, side='left')
        use = i1 > i0
        if not use.any():
            continue
        if not use.all():
            i0 = i0[use]; i1 = i1[use]
            b = base[use]
            W = cr.W[k][use]
            pw = [q[use] for q in powers]
        else:
            b = base
            W = cr.W[k]
            pw = powers
        ia = b + i0
        ib = b + i1
        for m in range(M):
            wm = W * pw[m] if m else W
            acc = np.bincount(ia, wm, minlength=size) - np.bincount(ib, wm, minlength=size)
            A[m, :, k, :] = np.cumsum(acc.reshape(nseg, width), axis=1)[:, :ns]
    return A


def station_damage(cr, A, dseg):
    """Damage per station for every segment, the rope elements there having diameters dseg[seg, s]."""
    b0, b1, b2, b3 = cr.coef
    dl = np.log10(dseg)                         # (nseg, ns)
    t = dl - cr.dbar
    c = b3 * LN10
    out = np.zeros(dseg.shape)
    # sum_m (c t)^m / m! A_m
    ser = []
    term = np.ones_like(t)
    for m in range(cr.M):
        if m:
            term = term * (c * t) / m
        ser.append(term)
    for k in range(len(cr.p)):
        Dk = cr.lD[k]
        e = (2 * (b1 + b3 * Dk) * dl - 2 * b3 * dl * dl - b0 - b2 * Dk + b2 * dl
             + b3 * dl * cr.sbar - (b1 + b3 * Dk) * cr.sbar)
        P = cr.w[k] * np.power(10.0, e)
        acc = ser[0] * A[0, :, k, :]
        for m in range(1, cr.M):
            acc = acc + ser[m] * A[m, :, k, :]
        out += P * acc
    # the difference arrays leave rounding residues of either sign where no bending was summed
    return np.maximum(out, 0.0)


# ------------------------------------------------------------------------------------- the wear fit

def wear_sse(Lo, C, alphas):
    """Least-squares fit of Lo[c, j, i] = u[c, j] + kappa[c, i] C[c, j, i]^alpha for a batch of candidates
    c and each exponent in alphas (u and kappa solved exactly, as one linear problem).
    Returns sse[c, alpha]."""
    nc, E1, ns = Lo.shape
    out = np.full((nc, len(alphas)), np.inf)
    sumL = Lo.sum(axis=2)
    eye = np.eye(E1)[None]
    with np.errstate(divide='ignore'):
        lC = np.log(np.maximum(C, 0.0))
    for ia, al in enumerate(alphas):
        F = np.exp(al * lC)
        SFF = (F * F).sum(axis=1)
        SFL = (F * Lo).sum(axis=1)
        top = SFF.max(axis=1, keepdims=True)
        inv = np.where(SFF > 1e-12 * np.maximum(top, 1e-300), 1.0 / np.where(SFF > 0, SFF, 1.0), 0.0)
        Fi = F * inv[:, None, :]
        Mm = ns * eye - np.matmul(Fi, F.transpose(0, 2, 1)) + 1e-9 * ns * eye
        rhs = sumL - np.matmul(Fi, SFL[:, :, None])[:, :, 0]
        try:
            u = np.linalg.solve(Mm, rhs[..., None])[..., 0]
        except np.linalg.LinAlgError:
            u = np.stack([np.linalg.lstsq(Mm[i], rhs[i], rcond=None)[0] for i in range(nc)])
        kap = (SFL - np.matmul(u[:, None, :], F)[:, 0, :]) * inv
        r = Lo - u[:, :, None] - kap[:, None, :] * F
        sse = (r * r).sum(axis=(1, 2))
        out[:, ia] = np.where(np.isfinite(sse), sse, np.inf)
    return out


# --------------------------------------------------------------------------------- the event model

class Model:
    """Segments of the log in time order, with the survey each belongs to and, for windows with an event,
    the event and the part of the window."""

    def __init__(self, cr, flips):
        self.cr = cr
        days = cr.sdays
        E = len(days)
        self.flips = flips
        bounds = []
        seg_epoch = [0]
        seg_event = [-1]
        seg_part = [0]
        ev_of_window = {w: i for i, w in enumerate(flips)}
        # segment list: epoch 0 starts at -inf
        for j in range(E):
            if j > 0:
                bounds.append(days[j])
                seg_epoch.append(j); seg_event.append(-1); seg_part.append(0)
            if j in ev_of_window:
                # this epoch is cut into NSUB parts; the first part is the segment just opened
                seg_event[-1] = ev_of_window[j]
                seg_part[-1] = 0
                t0, t1 = days[j], days[j + 1]
                for q in range(1, NSUB):
                    bounds.append(t0 + (t1 - t0) * q / NSUB)
                    seg_epoch.append(j); seg_event.append(ev_of_window[j]); seg_part.append(q)
        self.bounds = np.array(bounds)
        self.seg_epoch = np.array(seg_epoch)
        self.seg_event = np.array(seg_event)
        self.seg_part = np.array(seg_part)
        self.nseg = len(seg_epoch)
        self.part_time = {}
        for i, w in enumerate(flips):
            t0, t1 = days[w], days[w + 1]
            self.part_time[i] = t0 + (t1 - t0) * np.arange(NSUB + 1) / NSUB
        # sum over the segments of each survey window
        self.onehot = np.zeros((E, self.nseg))
        self.onehot[self.seg_epoch, np.arange(self.nseg)] = 1.0

    def segment_of(self, day):
        return np.searchsorted(self.bounds, day, side='right')

    def states(self, hyp):
        """hyp: list per event of ('B', None) or ('A', q).  Returns survey orientation o_j, recording
        flag r_j, segment orientation, whether the segment follows a turn since its survey, and the
        final orientation."""
        E = len(self.cr.sdays)
        o = np.zeros(E, dtype=int)
        r = np.zeros(E, dtype=int)
        for i, w in enumerate(self.flips):
            if hyp[i][0] == 'A':
                o[w + 1:] ^= 1
            else:
                r[w + 1:] ^= 1
        so = o[self.seg_epoch].copy()
        turned = np.zeros(self.nseg, dtype=int)
        for i, w in enumerate(self.flips):
            if hyp[i][0] == 'A':
                q = hyp[i][1]
                m = (self.seg_event == i) & (self.seg_part >= q)
                so[m] ^= 1
                turned[m] = 1
        # all events lie before the last survey: the orientation at the end of the log is the last survey's
        oF = int(o[-1])
        return o, r, so, turned, oF


def element_damage(model, P0, P1, hyp):
    """Damage of every element (indexed by its final station) at the end of the log, from the station
    damage of each segment for the readings as recorded (P0) and mirrored (P1)."""
    o, r, so, turned, oF = model.states(hyp)
    v = (r[model.seg_epoch] ^ turned).astype(bool)
    prof = np.where(v[:, None], P1, P0)
    same = so == oF
    return prof[same].sum(axis=0) + prof[~same].sum(axis=0)[::-1]


def wear_arrays(model, Pd, hyp):
    """Loss and cumulative damage of every element at every survey (j >= 1) under a hypothesis."""
    cr = model.cr
    o, r, so, turned, oF = model.states(hyp)
    same = (so == oF)[:, None]
    prof = np.where(same, Pd, Pd[:, ::-1])
    inc = model.onehot @ prof
    C = np.cumsum(inc, axis=0)[:-1]                   # damage before survey j = 1 .. E-1
    flip = ((o != oF) ^ (r == 1))[:, None]
    R = np.where(flip, cr.rd[:, ::-1], cr.rd)
    Lo = R[0][None, :] - R[1:]
    return Lo, C


def event_sse(model, Pd, hyp, i, cands, alphas):
    Ls, Cs = [], []
    for cnd in cands:
        h = list(hyp); h[i] = cnd
        Lo, C = wear_arrays(model, Pd, h)
        Ls.append(Lo); Cs.append(C)
    return wear_sse(np.array(Ls), np.array(Cs), alphas).min(axis=1)


def choose_hypothesis(model, Pd, P0, P1):
    cr = model.cr
    nev = len(model.flips)
    hyp = [('B', None)] * nev
    E = len(cr.sdays)
    nobs = (E - 1) * cr.ns
    profiles = {}
    step = ALPHAS[1] - ALPHAS[0]
    coarse = list(range(0, NSUB + 1, 4))
    if coarse[-1] != NSUB:
        coarse.append(NSUB)
    for _round in range(3):
        changed = False
        # exponent of the wear law for the present reading of the events
        Lo, C = wear_arrays(model, Pd, hyp)
        al = float(ALPHAS[int(np.argmin(wear_sse(Lo[None], C[None], ALPHAS)[0]))])
        alphas = np.array([al - step, al, al + step])
        alphas = alphas[alphas > 0.05]
        for i in range(nev):
            # B, and A on a coarse grid of times, then A on every time next to the best coarse one
            sA = np.full(NSUB + 1, np.nan)
            sse = event_sse(model, Pd, hyp, i, [('B', None)] + [('A', q) for q in coarse], alphas)
            sB = sse[0]
            sA[coarse] = sse[1:]
            qc = coarse[int(np.argmin(np.where(np.isfinite(sse[1:]), sse[1:], np.inf)))]
            fine = [q for q in range(max(0, qc - 3), min(NSUB, qc + 3) + 1) if np.isnan(sA[q])]
            if fine:
                sA[fine] = event_sse(model, Pd, hyp, i, [('A', q) for q in fine], alphas)
            known = np.nonzero(np.isfinite(sA))[0]
            sA = np.interp(np.arange(NSUB + 1), known, sA[known]) if len(known) else np.full(NSUB + 1, np.inf)
            qa = int(np.argmin(sA))
            sig2 = max(min(sB, sA[qa]) / max(nobs - E - cr.ns, 1), 1e-12)
            if np.isfinite(sA[qa]) and (not np.isfinite(sB) or sB - sA[qa] > 25.0 * sig2):
                new = ('A', qa)
            else:
                new = ('B', None)
            profiles[i] = (sA, sig2)
            if new != hyp[i]:
                changed = True
            hyp[i] = new
        if not changed:
            break
    # time of each turn: keep the error a wrong time could cause within SAFE where possible
    for i in range(nev):
        if hyp[i][0] != 'A':
            continue
        sA, sig2 = profiles[i]
        qhat = hyp[i][1]
        res = []
        for q in range(NSUB + 1):
            h = list(hyp); h[i] = ('A', q)
            res.append(element_damage(model, P0, P1, h))
        res = np.array(res)
        mx = np.maximum(res.max(axis=1), 1e-300)
        err = np.abs(res[:, None, :] - res[None, :, :]).max(axis=2) / mx[None, :]   # [pick, truth]
        worst = err.max(axis=1)
        safe = np.nonzero(worst <= SAFE)[0]
        if qhat in safe:
            q = qhat
        elif len(safe):
            q = int(safe[np.argmin(np.abs(safe - qhat))])
        else:
            band = np.nonzero(sA - sA.min() <= 25.0 * sig2)[0]
            q = int(np.argmin(err[:, band].max(axis=1)))
        hyp[i] = ('A', q)
    return hyp


# ------------------------------------------------------------------------------------------ a crane

def crane_result(cr, mv_day, mv_h0, mv_h1, mv_load, sh, sv):
    """Damage at the stations of the crane's last survey, and a note on what was found."""
    note = ''
    n = int(round(cr.falls))
    surveys = build_surveys(sv, cr.L)
    if surveys is None:
        ns = max(int(round(cr.L)), 1)
        grid = np.arange(ns) + 0.5
        days = np.array([0.0])
        rd = np.full((1, ns), np.nan)
    else:
        days, grid, rd = surveys
    cr.sdays = days
    cr.grid = grid
    cr.ns = ns = len(grid)
    if not np.isfinite(rd).all():
        # no usable survey of the rope: there is no diameter to reckon with
        return grid, np.zeros(ns), 'no survey'
    cr.rd = rd
    # contacts
    p = sh['parts'].to_numpy(dtype=np.float64)
    a = sh['offset_m'].to_numpy(dtype=np.float64)
    D = sh['diameter_mm'].to_numpy(dtype=np.float64)
    w = sh['bend_weight'].to_numpy(dtype=np.float64)
    ok = np.isfinite(p) & np.isfinite(a) & np.isfinite(D) & np.isfinite(w) & (p > 0) & (D > 0)
    p, a, D, w = p[ok], a[ok], D[ok], w[ok]
    cr.p, cr.a, cr.w, cr.lD = p, a, w, np.log10(D)
    cr.hk = [cr.H - (cr.L - a[k] - grid) / p[k] for k in range(len(p))]
    # movements
    S = (mv_load + cr.mb) * 1000.0 * G_ACC / (n * cr.e)
    use = (np.isfinite(mv_day) & np.isfinite(mv_h0) & np.isfinite(mv_h1) & np.isfinite(S) & (S > 0)
           & (mv_h0 != mv_h1))
    day = mv_day[use]
    cr.lo = np.minimum(mv_h0[use], mv_h1[use])
    cr.hi = np.maximum(mv_h0[use], mv_h1[use])
    sig = np.log10(S[use])
    cr.nmov = len(day)
    b0, b1, b2, b3 = cr.coef
    if cr.nmov:
        cr.sbar = 0.5 * (sig.min() + sig.max())
    else:
        cr.sbar = 0.0
    cr.tau = sig - cr.sbar
    dlog = np.log10(rd)
    cr.dbar = 0.5 * (dlog.min() + dlog.max())
    xmax = abs(b3 * LN10) * 0.5 * (dlog.max() - dlog.min()) * (np.abs(cr.tau).max() if cr.nmov else 0.0)
    M, term = 1, 1.0
    while M < 40:
        term *= xmax / M
        if term < SERIES_TOL:
            break
        M += 1
    cr.M = M
    cr.W = [np.exp(LN10 * (b3 * cr.dbar - b1 - b3 * cr.lD[k]) * cr.tau) for k in range(len(p))]

    flips = find_flips(rd) if np.allclose(grid + grid[::-1], grid[0] + grid[-1]) else []
    model = Model(cr, flips)
    seg = model.segment_of(day)
    A = accumulate(cr, seg, model.nseg)
    d_rec = rd[model.seg_epoch]
    P0 = station_damage(cr, A, d_rec)
    if not flips:
        return grid, P0.sum(axis=0), note
    P1 = station_damage(cr, A, d_rec[:, ::-1])
    if time.process_time() > TIME_GUARD or len(flips) > MAX_EVENTS:
        # last resort against running out of time on a pathological package: take every event as a
        # survey recorded from the dead end (no wear analysis)
        hyp = [('B', None)] * len(flips)
        note = 'events not analysed (time guard); '
    else:
        hyp = choose_hypothesis(model, P0, P0, P1)
    parts = []
    for i, wdw in enumerate(flips):
        if hyp[i][0] == 'A':
            t = model.part_time[i][hyp[i][1]]
            parts.append(f'rope turned end for end between surveys of day {days[wdw]:g} and {days[wdw + 1]:g},'
                         f' taken at day {t:.2f}')
        else:
            parts.append(f'surveys from day {days[wdw + 1]:g} recorded from the dead end (rope not moved)')
    note += '; '.join(parts)
    return grid, element_damage(model, P0, P1, hyp), note


def fallback_result(cr, mv_day, mv_h0, mv_h1, mv_load, sh, sv):
    """Plain computation without event analysis, used only if the full one fails."""
    n = int(round(cr.falls))
    surveys = build_surveys(sv, cr.L)
    if surveys is None:
        ns = max(int(round(cr.L)), 1)
        return np.arange(ns) + 0.5, np.zeros(ns)
    days, grid, rd = surveys
    b0, b1, b2, b3 = cr.coef
    S = (mv_load + cr.mb) * 1000.0 * G_ACC / (n * cr.e)
    lo = np.minimum(mv_h0, mv_h1); hi = np.maximum(mv_h0, mv_h1)
    ep = np.clip(np.searchsorted(days, mv_day, side='right') - 1, 0, len(days) - 1)
    out = np.zeros(len(grid))
    for _, rrow in sh.iterrows():
        pk, ak, Dk, wk = float(rrow['parts']), float(rrow['offset_m']), float(rrow['diameter_mm']), float(rrow['bend_weight'])
        if not (pk > 0 and Dk > 0):
            continue
        hk = cr.H - (cr.L - ak - grid) / pk
        for si in range(len(grid)):
            cov = (lo < hk[si]) & (hk[si] < hi) & np.isfinite(S) & (S > 0)
            if not cov.any():
                continue
            d = rd[ep[cov], si]
            u = np.log10(Dk / d); v = np.log10(S[cov]) - 2 * np.log10(d)
            out[si] += wk * np.sum(10.0 ** (-(b0 + (b1 + b3 * u) * v + b2 * u)))
    return grid, out


# ------------------------------------------------------------------------------------------- output

def write_output(path, rows):
    text = 'row,damage\n' + ''.join(f'{name},{val:.8f}\n' for name, val in rows)
    data = text.encode('ascii', 'replace')
    out_dir = os.path.dirname(os.path.abspath(path)) or '.'
    try:
        fd, tmp = tempfile.mkstemp(prefix='.ropes_', suffix='.tmp', dir=out_dir)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
            os.chmod(tmp, 0o644)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError:
        if os.path.islink(path):
            os.unlink(path)
        with open(path, 'wb') as f:
            f.write(data)


def fmt_station(i, width):
    return str(i).zfill(width)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: python3 ropes.py WORKS_DIR OUT_CSV\n')
        return 0
    pkg, out = argv[1], argv[2]
    rows = []
    try:
        cranes = read_table(os.path.join(pkg, 'cranes.csv'))
        sheaves = read_table(os.path.join(pkg, 'sheaves.csv'))
        surveys = read_table(os.path.join(pkg, 'surveys.csv'))
        moves = pd.read_csv(os.path.join(pkg, 'movements.csv'), skipinitialspace=True)
        moves.columns = [str(c).strip().lower() for c in moves.columns]
    except Exception as exc:  # nothing can be reckoned without the package
        sys.stderr.write(f'ropes.py: cannot read package: {exc}\n')
        write_output(out, rows)
        return 0

    cranes['crane'] = text_col(cranes, 'crane')
    sheaves['crane'] = text_col(sheaves, 'crane')
    for col in ('parts', 'offset_m', 'diameter_mm', 'bend_weight'):
        sheaves[col] = pd.to_numeric(sheaves[col], errors='coerce')
    surveys['crane'] = text_col(surveys, 'crane')
    for col in ('day', 'station_m', 'diameter_mm'):
        surveys[col] = pd.to_numeric(surveys[col], errors='coerce')

    mcr = moves['crane'].astype('category')
    cats = [str(c).strip() for c in mcr.cat.categories]
    codes = mcr.cat.codes.to_numpy()
    m_day = num_col(moves, 'day')
    m_h0 = num_col(moves, 'from_height_m')
    m_h1 = num_col(moves, 'to_height_m')
    m_load = num_col(moves, 'hook_load_t')
    by_name = {}
    for ci, name in enumerate(cats):
        by_name.setdefault(name, []).append(ci)

    sv_groups = {k: g for k, g in surveys.groupby('crane', sort=False)}
    sh_groups = {k: g for k, g in sheaves.groupby('crane', sort=False)}

    seen = set()
    for _, row in cranes.iterrows():
        name = row['crane']
        if name in seen:
            continue
        seen.add(name)
        cr = Crane()
        cr.name = name
        try:
            cr.falls = float(row['falls'])
            cr.H = float(row['upper_block_height_m'])
            cr.mb = float(row['block_mass_t'])
            cr.e = float(row['reeving_efficiency'])
            cr.L = float(row['rope_length_m'])
            cr.coef = COEF.get(construction_key(row['rope_construction']))
        except Exception:
            cr.coef = None
        sel = np.zeros(len(codes), dtype=bool)
        for ci in by_name.get(name, []):
            sel |= codes == ci
        idx = np.nonzero(sel)[0]
        sh = sh_groups.get(name, sheaves.iloc[0:0])
        sv = sv_groups.get(name, surveys.iloc[0:0])
        grid, dmg, note = None, None, ''
        if cr.coef is not None:
            try:
                grid, dmg, note = crane_result(cr, m_day[idx], m_h0[idx], m_h1[idx], m_load[idx], sh, sv)
                if not np.all(np.isfinite(dmg)):
                    raise ValueError('non-finite damage')
            except Exception as exc:
                sys.stderr.write(f'ropes.py: {name}: {exc}; plain computation used\n')
                try:
                    grid, dmg = fallback_result(cr, m_day[idx], m_h0[idx], m_h1[idx], m_load[idx], sh, sv)
                    note = 'plain computation'
                except Exception as exc2:
                    sys.stderr.write(f'ropes.py: {name}: {exc2}\n')
                    grid = None
        else:
            sys.stderr.write(f'ropes.py: {name}: unknown rope construction {row.get("rope_construction")!r}\n')
        if grid is None:
            try:
                ns = max(int(round(float(row['rope_length_m']))), 1)
            except Exception:
                ns = 1
            grid, dmg = np.arange(ns) + 0.5, np.zeros(ns)
        dmg = np.where(np.isfinite(dmg), np.maximum(dmg, 0.0), 0.0)
        width = max(3, len(str(len(grid))))
        for i, v in enumerate(dmg):
            rows.append((f'{name}-{fmt_station(i + 1, width)}', float(v)))
        if note:
            sys.stderr.write(f'ropes.py: {name}: {note}\n')
    write_output(out, rows)
    return 0


if __name__ == '__main__':
    try:
        code = main(sys.argv)
    except Exception as exc:
        sys.stderr.write(f'ropes.py: {exc}\n')
        code = 0
    sys.exit(0)
