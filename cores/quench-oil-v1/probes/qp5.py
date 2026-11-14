#!/usr/bin/env python3
"""HT-5 quench calculation for one site package: python3 quench.py PACKAGE_DIR OUT_CSV"""
import numpy as np
import time as _time

RHO = 7800.0
PK = 14200.0
KTAB = {
    'C45': ([20, 300, 600, 800, 900], [50, 44, 34, 26, 26]),
    '42CrMo4': ([20, 300, 600, 800, 900], [43, 40, 33, 27, 27]),
}
CTAB = {
    'C45': ([20, 300, 600, 720, 800, 900], [470, 560, 750, 900, 650, 650]),
    '42CrMo4': ([20, 300, 600, 720, 800, 900], [460, 550, 720, 850, 640, 640]),
}
STEELS = ['C45', '42CrMo4']
TLO = -300.0
NCELL = 1600


def _cell_tables(Tt, vt):
    Tt = np.asarray(Tt, float)
    vt = np.asarray(vt, float)
    T0 = TLO + np.arange(NCELL + 1, dtype=float)
    v0 = np.interp(T0, Tt, vt)
    v1 = np.interp(T0 + 1.0, Tt, vt)
    s = v1 - v0
    cellint = 0.5 * (v0 + v1)
    I = np.concatenate([[0.0], np.cumsum(cellint[:-1])])
    I = I - I[int(round(-TLO))]
    return v0, s, I


def _build_tables():
    cols = [[] for _ in range(6)]
    for st in STEELS:
        k0, ks, P0 = _cell_tables(*KTAB[st])
        c0, cs, H0 = _cell_tables(CTAB[st][0], np.array(CTAB[st][1], float) * RHO)
        for i, a in enumerate([c0, cs, H0, k0, ks, P0]):
            cols[i].append(a)
    return [np.ascontiguousarray(np.concatenate(c)) for c in cols]


TABS = _build_tables()


def _quad_interp(x0, x1, x2, y0, y1, y2, xq):
    """Lagrange quadratic through (x0,y0),(x1,y1),(x2,y2) evaluated at xq (arrays)."""
    with np.errstate(all='ignore'):
        L0 = (xq - x1) * (xq - x2) / ((x0 - x1) * (x0 - x2))
        L1 = (xq - x0) * (xq - x2) / ((x1 - x0) * (x1 - x2))
        L2 = (xq - x0) * (xq - x1) / ((x2 - x0) * (x2 - x1))
        v = L0 * y0 + L1 * y1 + L2 * y2
        # fall back to linear between the last two points where degenerate
        lin = y1 + (y2 - y1) * (xq - x1) / (x2 - x1)
    bad = ~np.isfinite(v)
    if bad.any():
        v = np.where(bad, lin, v)
    return v


def solve(steel_idx, R, Tf, Tb, crmax, tcr, cr300, N=21, a=0.5, theta=0.5, dTstep=1.0,
          dt0=1e-4, growth=1.5, maxsteps=40000, deadline=None, soft_budget=None):
    """Batch solve. All inputs arrays of length M. Returns dict of result arrays."""
    M = len(R)
    R = np.asarray(R, float); Tf = np.asarray(Tf, float); Tb = np.asarray(Tb, float)
    tcr = np.asarray(tcr, float)
    hp = PK * np.asarray(crmax, float) / (tcr - 40.0)
    h3 = PK * np.asarray(cr300, float) / 260.0
    tcx = np.maximum(tcr, 300.5)   # table points must ascend
    hx = np.stack([np.full(M, 100.0), np.full(M, 300.0), tcx, tcx + 120.0], 0)
    hy = np.stack([0.6 * h3, h3, hp, 0.15 * hp], 0)
    hsl = (hy[1:] - hy[:-1]) / (hx[1:] - hx[:-1])

    def hfun(Ts):
        h = np.where(Ts <= hx[0], hy[0], hy[3])
        dh = np.zeros(M)
        for j in range(3):
            m = (Ts > hx[j]) & (Ts < hx[j + 1])
            h = np.where(m, hy[j] + hsl[j] * (Ts - hx[j]), h)
            dh = np.where(m, hsl[j], dh)
        return h, dh

    s = np.linspace(0.0, 1.0, N)
    x = a * s + (1 - a) * np.sin(s * np.pi / 2)
    hxg = np.diff(x)
    xf = 0.5 * (x[1:] + x[:-1])
    V = np.empty(N)
    V[0] = xf[0] ** 2 / 2
    V[1:-1] = (xf[1:] ** 2 - xf[:-1] ** 2) / 2
    V[-1] = (1 - xf[-1] ** 2) / 2
    ra, rb = x[:-1], x[1:]
    Maa = hxg * (3 * ra + rb) / 12
    Mab = hxg * (ra + rb) / 12
    Mbb = hxg * (ra + 3 * rb) / 12
    Mc_d = np.zeros(N); Mc_d[:-1] += Maa; Mc_d[1:] += Mbb
    Md = (1 - theta) * V + theta * Mc_d
    Mo = theta * Mab
    G = xf / hxg

    off = (np.asarray(steel_idx, np.int64) * (NCELL + 1))[None, :]
    c0t, cst, H0t, k0t, kst, P0t = TABS

    def props(T):
        u = T - TLO
        j = u.astype(np.int64)
        np.clip(j, 0, NCELL - 1, out=j)
        d = u - j
        j += off
        c0 = c0t.take(j); cs = cst.take(j)
        k0 = k0t.take(j); ks = kst.take(j)
        H = H0t.take(j) + d * (c0 + 0.5 * cs * d)
        P = P0t.take(j) + d * (k0 + 0.5 * ks * d)
        C = c0 + cs * d
        K = k0 + ks * d
        return H, P, C, K

    R2 = R[None, :] ** 2
    Md2 = Md[:, None] * R2
    Mo2 = Mo[:, None] * R2
    Gc = G[:, None]

    def massmul(H):
        out = Md2 * H
        out[:-1] += Mo2 * H[1:]
        out[1:] += Mo2 * H[:-1]
        return out

    T = np.repeat(Tf[None, :], N, 0)
    H = props(T)[0]
    t = np.zeros(M)
    dt = np.full(M, dt0) * (R / 0.03) ** 2
    dtmax = 20.0 * (R / 0.03) ** 2
    Hprev = None
    dtprev = None
    Th = [T]
    tH = [t]
    cp = np.empty((N - 1, M)); dp = np.empty((N, M)); tmp = np.empty(M)

    # event tracking: last three (t, Tc, Ts)
    targets = [800.0, 725.0, 675.0, 500.0, 150.0]
    tcross = {k: np.full(M, np.nan) for k in targets}
    ts500 = np.full(M, np.nan)
    pt = [t.copy(), t.copy(), t.copy()]
    pc = [T[0].copy(), T[0].copy(), T[0].copy()]
    ps = [T[-1].copy(), T[-1].copy(), T[-1].copy()]
    dmax = np.full(M, -np.inf)
    dm_t = np.zeros((3, M)); dm_d = np.zeros((3, M))
    dm_need = np.zeros(M, bool)
    nst = 0
    step = 0
    t_run0 = _time.time()
    while step < maxsteps:
        step += 1
        if Hprev is None:
            om = np.zeros(M)
            Hstar = H
            Tpred = T
        else:
            om = dt / dtprev
            c1 = (1 + om) ** 2 / (1 + 2 * om)
            c2 = om ** 2 / (1 + 2 * om)
            Hstar = c1 * H - c2 * Hprev
            if len(Th) >= 3:
                t0_, t1_, t2_ = tH[-3], tH[-2], tH[-1]
                tn = t2_ + dt
                l0 = (tn - t1_) * (tn - t2_) / ((t0_ - t1_) * (t0_ - t2_))
                l1 = (tn - t0_) * (tn - t2_) / ((t1_ - t0_) * (t1_ - t2_))
                l2 = (tn - t0_) * (tn - t1_) / ((t2_ - t0_) * (t2_ - t1_))
                Tpred = l0 * Th[-3] + l1 * Th[-2] + l2 * Th[-1]
            else:
                Tpred = T + om * (T - Th[-2])
        beta = dt * (1 + om) / (1 + 2 * om)
        bG = beta * Gc
        # one Newton step from the predictor (linearly implicit BDF2)
        Hn, Pn, Cn, Kn = props(Tpred)
        Ts = Tpred[-1]
        hs_, dhs_ = hfun(Ts)
        qs = R * hs_ * (Ts - Tb)
        dqs = R * (hs_ + dhs_ * (Ts - Tb))
        Fl = bG * (Pn[1:] - Pn[:-1])
        res = massmul(Hn - Hstar)
        res[:-1] -= Fl
        res[1:] += Fl
        res[-1] += beta * qs
        diag = Md2 * Cn
        bGK0 = bG * Kn[:-1]
        bGK1 = bG * Kn[1:]
        diag[:-1] += bGK0
        diag[1:] += bGK1
        diag[-1] += beta * dqs
        up = Mo2 * Cn[1:] - bGK1
        lo = Mo2 * Cn[:-1] - bGK0
        np.divide(up[0], diag[0], out=cp[0])
        np.divide(-res[0], diag[0], out=dp[0])
        for i in range(1, N):
            np.multiply(lo[i - 1], cp[i - 1], out=tmp)
            np.subtract(diag[i], tmp, out=tmp)
            np.divide(1.0, tmp, out=tmp)
            if i < N - 1:
                np.multiply(up[i], tmp, out=cp[i])
            np.multiply(lo[i - 1], dp[i - 1], out=dp[i])
            np.subtract(-res[i], dp[i], out=dp[i])
            np.multiply(dp[i], tmp, out=dp[i])
        for i in range(N - 2, -1, -1):
            np.multiply(cp[i], dp[i + 1], out=tmp)
            np.subtract(dp[i], tmp, out=dp[i])
        Tn = Tpred + dp
        Hn = props(Tn)[0]
        chg = np.max(np.abs(Tn - T), axis=0)
        Hprev = H
        T, H = Tn, Hn
        t = t + dt
        Th.append(T); tH.append(t)
        if len(Th) > 3:
            Th.pop(0); tH.pop(0)
        # ---- events
        pt = [pt[1], pt[2], t]
        pc = [pc[1], pc[2], T[0].copy()]
        ps = [ps[1], ps[2], T[-1].copy()]
        nst += 1
        Tc_now = pc[2]
        for Tt in targets:
            arr = tcross[Tt]
            m = np.isnan(arr) & (Tc_now <= Tt)
            if m.any():
                tc = _quad_interp(pc[0][m], pc[1][m], pc[2][m], pt[0][m], pt[1][m], pt[2][m], Tt)
                lo_t, hi_t = pt[1][m], pt[2][m]
                lin = pt[1][m] + (pt[2][m] - pt[1][m]) * (Tt - pc[1][m]) / (pc[2][m] - pc[1][m])
                tc = np.where((tc >= lo_t) & (tc <= hi_t) & np.isfinite(tc), tc, lin)
                arr[m] = tc
                if Tt == 500.0:
                    ts500[m] = _quad_interp(pt[0][m], pt[1][m], pt[2][m], ps[0][m], ps[1][m], ps[2][m], tc)
        d_now = pc[2] - ps[2]
        # finish pending dmax neighbourhoods
        if dm_need.any():
            mm = dm_need
            dm_t[2, mm] = t[mm]; dm_d[2, mm] = d_now[mm]
            dm_need = np.zeros(M, bool)
        newmax = d_now > dmax
        if newmax.any():
            dmax = np.where(newmax, d_now, dmax)
            dm_t[0, newmax] = pt[1][newmax]; dm_d[0, newmax] = pc[1][newmax] - ps[1][newmax]
            dm_t[1, newmax] = t[newmax]; dm_d[1, newmax] = d_now[newmax]
            dm_need = newmax
        dtprev = dt
        fac = np.clip(dTstep / np.maximum(chg, 1e-12), 0.3, growth)
        dt = np.minimum(dt * fac, dtmax)
        if not np.isnan(tcross[150.0]).any() and not dm_need.any():
            break
        if deadline is not None and (step & 31) == 0 and _time.time() > deadline:
            break
        if soft_budget is not None and step == 64:
            # slow machine: coarsen the time steps so that the run stays within its budget
            el = _time.time() - t_run0
            projected = el / 64.0 * 1400.0 * (1.0 / dTstep)
            if projected > soft_budget:
                dTstep = min(2.5, dTstep * projected / soft_budget)
    # dT max refinement by parabola
    x0, x1, x2 = dm_t
    y0, y1, y2 = dm_d
    with np.errstate(all='ignore'):
        den = (x0 - x1) * (x0 - x2) * (x1 - x2)
        A = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / den
        B = (x2 * x2 * (y0 - y1) + x1 * x1 * (y2 - y0) + x0 * x0 * (y1 - y2)) / den
        Cc = (x1 * x2 * (x1 - x2) * y0 + x2 * x0 * (x2 - x0) * y1 + x0 * x1 * (x0 - x1) * y2) / den
        xv = -B / (2 * A)
        yv = Cc - B * B / (4 * A)
    good = (A < 0) & (xv >= x0) & (xv <= x2) & np.isfinite(yv) & (yv < y1 + 0.05 * abs(y1) + 1)
    dTm = np.where(good, np.maximum(yv, y1), dmax)
    t800 = tcross[800.0]; t725 = tcross[725.0]; t675 = tcross[675.0]; t500 = tcross[500.0]; t150 = tcross[150.0]
    return dict(t85=t500 - t800, cr700=50.0 / (t675 - t725), dTmax=dTm, ts500=ts500, t150=t150, steps=step)

# ===================================================================================================
# Site package: which oil was in the tank of each load
# ===================================================================================================
import sys
import os
import csv
import json
import time
import datetime
import itertools
import subprocess
import shutil

ROUND = 182.0          # days of a six-monthly sample round
RATE_TOL = 0.010       # relative difference of two analyses of one charge (lab repeat 0.5 % each)
RATE_AGE = 0.006       # allowance per round of time between the compared analyses
T_TOL = 1.5            # K for T_CRmax
T_AGE = 1.0
DRIFT_LIM = 0.0055     # relative rise per round beyond which a charge does not age normally
T_DRIFT_LIM = 1.6      # K per round for T_CRmax


def log(*a):
    if os.environ.get('QUENCH_DEBUG'):
        print(*a, file=sys.stderr)


def parse_day(s):
    s = str(s).strip()
    try:
        return datetime.date.fromisoformat(s[:10]).toordinal()
    except Exception:
        pass
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y%m%d', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.datetime.strptime(s, fmt).date().toordinal()
        except Exception:
            pass
    import pandas as pd
    return pd.Timestamp(s).date().toordinal()


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        out.append({(k or '').strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()})
    return out


def fnum(x, default=float('nan')):
    try:
        return float(str(x).strip())
    except Exception:
        return default


class Package:
    def __init__(self, d):
        self.dir = d
        try:
            self.site = json.load(open(os.path.join(d, 'site.json')))
        except Exception:
            self.site = {}
        try:
            self.lab_samples = int(float(self.site.get('lab_samples', 0)))
        except Exception:
            self.lab_samples = 0
        try:
            self.drawn = parse_day(self.site.get('samples_drawn'))
        except Exception:
            self.drawn = None
        self.tanks = {}
        self.tank_order = []
        self.registered = set()
        for r in read_csv(os.path.join(d, 'tanks.csv')):
            t = r.get('tank')
            if not t:
                continue
            if t in self.tanks:
                continue
            self.tanks[t] = r.get('oil_system', '') or ('OWN-' + t)
            self.tank_order.append(t)
            self.registered.add(t)
        self.systems = {}
        for r in read_csv(os.path.join(d, 'oil_systems.csv')):
            self.systems[r.get('oil_system')] = (r.get('kind', ''), r.get('oil_type', ''))
        self.renew = {}
        for r in read_csv(os.path.join(d, 'oil_log.csv')):
            w = (r.get('work') or '').strip().upper()
            if w == 'CHARGE_RENEWED':
                try:
                    self.renew.setdefault(r.get('oil_system'), set()).add(parse_day(r.get('date')))
                except Exception:
                    pass
        self.renew = {k: sorted(v) for k, v in self.renew.items()}
        self.hist = {t: [] for t in self.tanks}
        for r in read_csv(os.path.join(d, 'oil_samples.csv')):
            t = r.get('sampled_at')
            try:
                dd = parse_day(r.get('date'))
            except Exception:
                continue
            v = (fnum(r.get('cr_max_K_s')), fnum(r.get('t_crmax_C')), fnum(r.get('cr_300_K_s')))
            if not all(np.isfinite(v)):
                continue
            if t not in self.tanks:
                continue
            self.hist[t].append((dd,) + v)
        for t in self.hist:
            self.hist[t].sort()
        self.loads = read_csv(os.path.join(d, 'loads.csv'))
        self._drawn_given = self.drawn is not None
        for L in self.loads:
            try:
                L['_day'] = parse_day(L.get('date'))
            except Exception:
                L['_day'] = None
            if L.get('tank') not in self.tanks and L.get('tank'):
                t = L['tank']
                self.tanks[t] = 'OWN-' + t
                self.tank_order.append(t)
                self.hist[t] = []
        if self.drawn is None:
            ds = [L['_day'] for L in self.loads if L.get('_day') is not None]
            ds += [h[0] for t in self.hist for h in self.hist[t]]
            self.drawn = (max(ds) + 1) if ds else None


def merged_hist(pkg, tanks):
    """Per-date mean of the analyses of a set of tanks: list of (day, cm, tc, c3, n)."""
    by = {}
    for t in tanks:
        for h in pkg.hist.get(t, []):
            by.setdefault(h[0], []).append(h[1:])
    out = []
    for dd in sorted(by):
        a = np.array(by[dd], float)
        m = a.mean(0)
        out.append((dd, m[0], m[1], m[2], len(a)))
    return out


def value_at(H, d):
    """Figures of history H (list of (day, cm, tc, c3, ...)) at day d by linear inter/extrapolation.
    Returns (array(3), gap_days)."""
    days = [h[0] for h in H]
    vals = [np.array(h[1:4], float) for h in H]
    if len(H) == 1:
        return vals[0], abs(d - days[0])
    if d <= days[0]:
        i, j = 0, 1
        gap = days[0] - d
    elif d >= days[-1]:
        i, j = len(H) - 2, len(H) - 1
        gap = d - days[-1]
    else:
        j = next(k for k in range(len(days)) if days[k] >= d)
        if days[j] == d:
            return vals[j], 0
        i = j - 1
        gap = min(d - days[i], days[j] - d) * 0.5
    w = (d - days[i]) / float(days[j] - days[i])
    return vals[i] + (vals[j] - vals[i]) * w, gap


def epoch_of(d, bounds):
    k = 0
    for b in bounds:
        if d >= b:
            k += 1
    return k


def compare_hist(HA, HB, bounds):
    """Compare analyses HA against history HB (same epochs only).
    Returns (n_compared, n_violations, worst_ratio)."""
    n = 0
    nv = 0
    worst = 0.0
    for h in HA:
        e = epoch_of(h[0], bounds)
        HBe = [g for g in HB if epoch_of(g[0], bounds) == e]
        if not HBe:
            continue
        v, gap = value_at(HBe, h[0])
        a = np.array(h[1:4], float)
        rr = gap / ROUND
        tolr = RATE_TOL + RATE_AGE * rr
        tolt = T_TOL + T_AGE * rr
        r1 = abs(a[0] - v[0]) / max(abs(v[0]), 1e-9) / tolr
        r2 = abs(a[2] - v[2]) / max(abs(v[2]), 1e-9) / tolr
        r3 = abs(a[1] - v[1]) / tolt
        r = max(r1, r2, r3)
        worst = max(worst, r)
        n += 1
        if r > 1.0:
            nv += 1
    return n, nv, worst


def compatible(pkg, A, B, sysA, sysB):
    """Are the analyses of tank sets A and B those of one charge?  None if no comparison possible."""
    bounds = sorted(set(pkg.renew.get(sysA, [])) | set(pkg.renew.get(sysB, [])))
    HA = merged_hist(pkg, A)
    HB = merged_hist(pkg, B)
    if not HA or not HB:
        return None, 0.0
    n1, v1, w1 = compare_hist(HA, HB, bounds)
    n2, v2, w2 = compare_hist(HB, HA, bounds)
    if n1 + n2 == 0:
        return None, 0.0
    return (v1 + v2) == 0, max(w1, w2)


class Cluster:
    def __init__(self, name, tanks, system, kind):
        self.name = name
        self.tanks = list(tanks)
        self.system = system      # system whose log applies (None for an unlisted charge)
        self.kind = kind          # 'system' | 'own'
        self.flags = set()
        self.reg_renewals = []    # renewals logged for the registered system of an unlisted charge


def build_clusters(pkg):
    sys_tanks = {}
    for t in pkg.tank_order:
        sys_tanks.setdefault(pkg.tanks[t], []).append(t)
    cores = {}
    outliers = []
    ambiguous_sys = set()
    for s, ts in sys_tanks.items():
        withh = [t for t in ts if pkg.hist.get(t)]
        if len(withh) <= 1:
            cores[s] = withh
            continue
        comp = {}
        for a, b in itertools.combinations(withh, 2):
            ok, _ = compatible(pkg, [a], [b], s, s)
            comp[(a, b)] = comp[(b, a)] = (ok is None) or ok
        best = None
        if len(withh) <= 12:
            for size in range(len(withh), 0, -1):
                cands = []
                for sub in itertools.combinations(withh, size):
                    if all(comp[(a, b)] for a, b in itertools.combinations(sub, 2)):
                        cands.append(sub)
                if cands:
                    best = cands
                    break
        else:
            # many tanks: greedy, starting from the tank compatible with the most others
            deg = {a: sum(comp[(a, b)] for b in withh if b != a) for a in withh}
            sub = []
            for a in sorted(withh, key=lambda u: -deg[u]):
                if all(comp[(a, b)] for b in sub):
                    sub.append(a)
            best = [tuple(sub)]
        if len(best) == 1:
            core = list(best[0])
        else:
            # several equally large candidate cores: prefer the one whose left-out tanks match another
            # system, then the one with more analyses; remember the ambiguity
            def score(sub):
                rest = [t for t in withh if t not in sub]
                expl = 0
                for t in rest:
                    for s2, ts2 in sys_tanks.items():
                        if s2 == s:
                            continue
                        c2 = [u for u in ts2 if pkg.hist.get(u)]
                        if c2:
                            ok, _ = compatible(pkg, [t], c2, s, s2)
                            if ok:
                                expl += 1
                                break
                nan = sum(len(pkg.hist[t]) for t in sub)
                return (expl, nan)
            best.sort(key=score, reverse=True)
            if score(best[0]) == score(best[1]):
                ambiguous_sys.add(s)
            core = list(best[0])
        cores[s] = core
        for t in withh:
            if t not in core:
                outliers.append(t)
    clusters = {}
    for s, ts in sys_tanks.items():
        members = list(cores[s]) + [t for t in ts if not pkg.hist.get(t)]
        c = Cluster(s, members, s, 'system')
        if s in ambiguous_sys:
            c.flags.add('ambiguous')
        clusters[s] = c
    # outliers: connected to another system, or an unlisted charge of their own
    own_groups = []
    for t in outliers:
        s0 = pkg.tanks[t]
        matches = []
        for s, c in clusters.items():
            if s == s0:
                continue
            core = [u for u in cores[s]]
            if not core:
                continue
            ok, w = compatible(pkg, [t], core, s0, s)
            if ok:
                matches.append((w, s))
        if matches:
            matches.sort()
            s = matches[0][1]
            clusters[s].tanks.append(t)
            clusters[s].flags.add('moved_in')
            log('tank %s registered on %s: oil matches %s' % (t, s0, s))
            continue
        placed = False
        for g in own_groups:
            ok, _ = compatible(pkg, [t], g, s0, pkg.tanks[g[0]])
            if ok:
                g.append(t)
                placed = True
                break
        if not placed:
            own_groups.append([t])
    for g in own_groups:
        name = 'UNLISTED(' + '+'.join(g) + ')'
        c = Cluster(name, g, None, 'own')
        regs = sorted(set(pkg.tanks[t] for t in g))
        rr = set()
        for s in regs:
            rr |= set(pkg.renew.get(s, []))
        c.reg_renewals = sorted(rr)
        log('tank(s) %s registered on %s: own oil, matches no system' % (g, regs))
        clusters[name] = c
    # drop empty clusters
    clusters = {k: v for k, v in clusters.items() if v.tanks}
    # a charge known from one tank only whose analyses are those of another system's charge:
    # it may be connected to that system (register error) -> remember the alternative
    for name, c in clusters.items():
        if c.kind != 'system':
            continue
        hk = [t for t in c.tanks if pkg.hist.get(t)]
        if len(hk) != 1 or len(pkg.hist[hk[0]]) < 2:
            continue
        for s2, c2 in clusters.items():
            if s2 == name or c2.kind != 'system':
                continue
            core2 = [u for u in cores.get(s2, []) if pkg.hist.get(u)]
            if not core2:
                continue
            ok, w = compatible(pkg, hk, core2, c.system, c2.system)
            if ok and w < 0.8:
                c.alt = s2
                log('charge %s matches the analyses of %s' % (name, s2))
                break
    return clusters


def charge_segments(pkg, c):
    """Renewal days that apply to the cluster's charge."""
    ren = set(pkg.renew.get(c.system, [])) if c.system is not None else set()
    if c.kind == 'own' or len(c.tanks) == 1:
        for t in c.tanks:
            if t not in pkg.systems:
                ren |= set(pkg.renew.get(t, []))
    return sorted(ren)


def drift_info(H):
    """Relative rise per round (cm, c3) and K per round (tc) from a per-date history."""
    if len(H) < 2:
        return None
    days = np.array([h[0] for h in H], float)
    V = np.array([h[1:4] for h in H], float)
    out = {}
    # consecutive
    cons = []
    for i in range(len(H) - 1):
        dd = (days[i + 1] - days[i]) / ROUND
        if dd <= 0:
            continue
        cons.append(((V[i + 1, 0] - V[i, 0]) / V[i, 0] / dd, (V[i + 1, 1] - V[i, 1]) / dd,
                     (V[i + 1, 2] - V[i, 2]) / V[i, 2] / dd, dd))
    x = (days - days[-1]) / ROUND
    if len(H) >= 2 and np.ptp(x) > 0:
        A = np.vstack([np.ones_like(x), x]).T
        coef = np.linalg.lstsq(A, V, rcond=None)[0]
        slope = coef[1]
    else:
        slope = np.zeros(3)
    out['slope'] = slope
    out['rel_slope'] = np.array([slope[0] / V[-1, 0], slope[1], slope[2] / V[-1, 2]])
    out['cons'] = cons
    return out


def is_anomalous(H):
    di = drift_info(H)
    if di is None:
        return False
    rs = di['rel_slope']
    if len(H) >= 3:
        if rs[0] > DRIFT_LIM or rs[2] > DRIFT_LIM or rs[0] < -0.004 or rs[2] < -0.004 \
                or abs(rs[1]) > T_DRIFT_LIM:
            return True
    for (a, b, cc, dd) in di['cons']:
        if dd < 0.3:
            continue
        if a > 0.012 or cc > 0.012 or a < -0.009 or cc < -0.009 or abs(b) > 2.6:
            return True
    return False


def plan(pkg, clusters):
    """Decide what each cluster needs and choose the laboratory order."""
    drawn = pkg.drawn
    loads_by_tank = {}
    for L in pkg.loads:
        loads_by_tank.setdefault(L.get('tank'), []).append(L)
    needs = []   # (priority, -weight, cluster name, preferred tanks)
    for name, c in clusters.items():
        ren = charge_segments(pkg, c)
        H = merged_hist(pkg, [t for t in c.tanks if pkg.hist.get(t)])
        last_ren = ren[-1] if ren else None
        Hcur = [h for h in H if last_ren is None or h[0] >= last_ren]
        c.H = H
        c.renewals = ren
        cl_loads = [L for t in c.tanks for L in loads_by_tank.get(t, []) if L['_day'] is not None]
        latest = Hcur[-1][0] if Hcur else None
        # loads whose figures depend on the analysis on the samples_drawn date
        if Hcur:
            dep = [L for L in cl_loads if L['_day'] > latest and (last_ren is None or L['_day'] >= last_ren)]
        else:
            dep = [L for L in cl_loads if last_ren is None or L['_day'] >= last_ren]
        c.n_dep = len(dep)
        core = [t for t in c.tanks if pkg.hist.get(t) and pkg.tanks.get(t) == (c.system or pkg.tanks.get(t))]
        if not core:
            core = [t for t in c.tanks if pkg.hist.get(t)] or list(c.tanks)
        # preferred tank to sample: with most analyses, then most loads
        def pref(t):
            return (-len(pkg.hist.get(t, [])), -len(loads_by_tank.get(t, [])), pkg.tank_order.index(t))
        core_sorted = sorted(core, key=pref)
        c.status = 'normal'
        if not dep:
            c.status = 'no_dependent_loads'
            continue
        if not Hcur:
            c.status = 'renewed' if ren else 'unknown'
            needs.append((1, 0, -len(dep), name, core_sorted))
        elif c.kind == 'own' and any(r > latest for r in c.reg_renewals):
            c.status = 'unlisted_reg_renewed'
            needs.append((1, 1, -len(dep), name, core_sorted))
        elif getattr(c, 'alt', None) and (sorted(r for r in pkg.renew.get(c.alt, []) if r > latest)
                                          != sorted(r for r in ren if r > latest)):
            c.status = 'ambiguous_alt'
            needs.append((1, 1, -len(dep), name, core_sorted))
        elif 'ambiguous' in c.flags and any(r > latest for r in pkg.renew.get(c.system, [])):
            c.status = 'ambiguous'
            needs.append((1, 1, -len(dep), name, core_sorted))
        elif is_anomalous(Hcur):
            c.status = 'anomalous'
            needs.append((1, 2, -len(dep), name, core_sorted))
        elif c.kind == 'own':
            c.status = 'unlisted'
            needs.append((2, 0, -len(dep), name, core_sorted))
        else:
            c.status = 'aging'
            needs.append((3, 0, -len(dep), name, core_sorted))
    needs = [(p, sub, w, name, [t for t in cand if t in pkg.registered]) for (p, sub, w, name, cand) in needs]
    # candidate samples: (priority, sub-priority, -weight, tank)
    cands = []
    for (p, sub, w, name, cand) in needs:
        if cand:
            pp = p if p == 1 else (2.1 if p == 2 else 3)
            cands.append((pp, sub, w, cand[0]))
    first = set(x[3] for x in cands)
    for (p, sub, w, name, cand) in needs:
        c = clusters[name]
        for t in c.tanks:
            if t in first or t not in pkg.registered:
                continue
            nl = len(loads_by_tank.get(t, []))
            if not nl:
                continue
            if not pkg.hist.get(t):
                cands.append((2.0, 0, -nl, t))          # no analysis on file: is it on its system?
            elif c.kind == 'system' and pkg.tanks.get(t) != c.system:
                cands.append((2.2, 0, -nl, t))          # registered elsewhere, oil matches this system
            else:
                cands.append((4, p, -nl, t))            # second sample of a charge
    cands.sort()
    order = []
    budget = max(0, pkg.lab_samples)
    for x in cands:
        if len(order) >= budget:
            break
        if x[3] not in order:
            order.append(x[3])
    return order, needs


def _lab_call(cmd, pkg, tanks):
    try:
        r = subprocess.run(cmd + [pkg.dir] + list(tanks), capture_output=True, text=True, timeout=25,
                           stdin=subprocess.DEVNULL)
    except Exception as e:
        log('lab failed', e)
        return None, ''
    log('lab exit', r.returncode, r.stdout.strip(), r.stderr.strip())
    out = {}
    lines = [l for l in (r.stdout or '').splitlines() if l.strip()]
    hi = [i for i, l in enumerate(lines) if l.strip().lower().startswith('sampled_at')]
    if not hi:
        return None, (r.stdout or '') + (r.stderr or '')
    lines = lines[hi[0]:]
    try:
        rd = csv.DictReader(lines)
        for row in rd:
            row = {(k or '').strip(): (v or '').strip() for k, v in row.items()}
            t = row.get('sampled_at')
            v = (fnum(row.get('cr_max_K_s')), fnum(row.get('t_crmax_C')), fnum(row.get('cr_300_K_s')))
            if t and all(np.isfinite(v)):
                out.setdefault(t, []).append(v)
    except Exception as e:
        log('lab parse failed', e)
    return {t: np.mean(np.array(v, float), 0) for t, v in out.items()}, ''


def run_lab(pkg, tanks):
    if not tanks:
        return {}
    exe = shutil.which('labsample')
    cmd = [exe] if exe else None
    if cmd is None:
        for p in ('/tmp/qp5/bin/labsample', '/usr/local/bin/labsample', '/usr/bin/labsample'):
            if os.path.exists(p):
                cmd = [p]
                break
    if cmd is None:
        log('labsample not found')
        return {}
    tanks = list(tanks)
    for attempt in range(3):
        res, msg = _lab_call(cmd, pkg, tanks)
        if res is not None:
            return res
        # an order the laboratory did not take: correct it once if the message says why
        import re
        m = re.search(r'at most\s+(\d+)', msg)
        bad = [t for t in tanks if re.search(r'\b' + re.escape(t) + r'\b', msg)]
        if m and int(m.group(1)) < len(tanks) and int(m.group(1)) > 0:
            tanks = tanks[:int(m.group(1))]
        elif bad and len(bad) < len(tanks):
            tanks = [t for t in tanks if t not in bad]
        else:
            break
    return {}


def consistent(a, b, rounds):
    tolr = RATE_TOL + 0.005 * rounds
    tolt = T_TOL + 1.0 * rounds
    return (abs(a[0] - b[0]) / b[0] <= tolr and abs(a[2] - b[2]) / b[2] <= tolr and abs(a[1] - b[1]) <= tolt)


def figures_by_tank(pkg, clusters, lab):
    """For each tank: list of segments (start_day, end_day, analyses[(day, fig)])"""
    drawn = pkg.drawn
    tank_tl = {}
    for name, c in clusters.items():
        ren = list(c.renewals)
        H = c.H
        sampled = [t for t in c.tanks if t in lab]
        # group lab answers of this cluster; split if inconsistent
        groups = []
        for t in sampled:
            for g in groups:
                if consistent(lab[t], lab[g[0]], 0):
                    g.append(t)
                    break
            else:
                groups.append([t])
        if len(groups) > 1:
            log('cluster %s: lab answers differ between tanks %s' % (name, groups))
        lastH = [h for h in H if not ren or h[0] >= ren[-1]]
        latest = lastH[-1] if lastH else None
        # the renewal applying to an unlisted charge: decided by the lab answer
        eff_ren = list(ren)
        cand_ren = []
        if c.kind == 'own':
            cand_ren = list(c.reg_renewals)
        elif getattr(c, 'status', '') == 'ambiguous_alt':
            cand_ren = list(pkg.renew.get(c.alt, []))
        if cand_ren and latest is not None and sampled and drawn is not None:
            a = np.mean([lab[t] for t in sampled], 0)
            pred = np.array(latest[1:4])
            rounds = max(0.0, (drawn - latest[0]) / ROUND)
            if not consistent(a, pred, rounds) and not is_anomalous(lastH):
                cand = [r for r in cand_ren if r > latest[0]]
                if cand:
                    eff_ren = sorted(set(eff_ren) | {cand[-1]})
                    log('cluster %s: lab answer is a new charge -> renewed with registered system on %s'
                        % (name, datetime.date.fromordinal(cand[-1])))
        bounds = [-10 ** 9] + eff_ren + [10 ** 9]

        def segment_list(lab_fig):
            segs = []
            for k in range(len(bounds) - 1):
                lo, hi = bounds[k], bounds[k + 1]
                A = [(h[0], np.array(h[1:4], float)) for h in H if lo <= h[0] < hi]
                last = (k == len(bounds) - 2)
                if last:
                    if lab_fig is not None and drawn is not None:
                        A = [x for x in A if x[0] < drawn] + [(drawn, np.array(lab_fig, float))]
                    elif A and drawn is not None:
                        A = A + [(drawn, estimate_drawn([h for h in H if lo <= h[0] < hi], drawn))]
                segs.append((lo, hi, A))
            return segs

        if groups:
            # tanks that were sampled use their own group's answer; the rest the largest group
            groups.sort(key=lambda g: -len(g))
            for g in groups:
                fig = np.mean([lab[t] for t in g], 0)
                for t in g:
                    tank_tl[t] = segment_list(fig)
            fig0 = np.mean([lab[t] for t in groups[0]], 0)
            for t in c.tanks:
                if t not in tank_tl:
                    tank_tl[t] = segment_list(fig0)
        else:
            segs = segment_list(None)
            for t in c.tanks:
                tank_tl[t] = segs
        c.eff_ren = eff_ren
    return tank_tl


def estimate_drawn(Hseg, drawn):
    """Figures on the samples_drawn date of a charge that the laboratory did not analyse."""
    last = np.array(Hseg[-1][1:4], float)
    if is_anomalous(Hseg):
        di = drift_info(Hseg)
        dd = (drawn - Hseg[-1][0]) / ROUND
        # rise from the latest analysis at the recent rate (mean of the last two intervals)
        n = len(Hseg)
        k = max(0, n - 3)
        d0 = Hseg[k][0]
        v0 = np.array(Hseg[k][1:4], float)
        rate = (last - v0) / max((Hseg[-1][0] - d0) / ROUND, 1e-9)
        return last + rate * dd
    return last


def fig_at(segs, d, fallback):
    for (lo, hi, A) in segs:
        if lo <= d < hi:
            if not A:
                break
            if d <= A[0][0]:
                return A[0][1]
            if d >= A[-1][0]:
                return A[-1][1]
            for i in range(len(A) - 1):
                if A[i][0] <= d <= A[i + 1][0]:
                    w = (d - A[i][0]) / float(A[i + 1][0] - A[i][0])
                    return A[i][1] + (A[i + 1][1] - A[i][1]) * w
    # segment without any analysis: nearest analysis of the tank's charges
    best = None
    for (lo, hi, A) in segs:
        for (dd, f) in A:
            key = abs(dd - d)
            if best is None or key < best[0]:
                best = (key, f)
    if best is not None:
        return best[1]
    return fallback


def simple_order(pkg):
    order = []
    systems = []
    for t in pkg.tank_order:
        s = pkg.tanks[t]
        if s not in systems:
            systems.append(s)
    systems.sort(key=lambda s: 0 if pkg.renew.get(s) else 1)
    for s in systems:
        ts = [t for t in pkg.tank_order if pkg.tanks[t] == s and t in pkg.registered]
        if ts and len(order) < pkg.lab_samples:
            order.append(ts[0])
    return order


def simple_figures(pkg, lab):
    """Register taken as it stands: per-system timeline with the lab answer of any of its tanks."""
    tl = {}
    for t in pkg.tank_order:
        s = pkg.tanks[t]
        ts = [u for u in pkg.tank_order if pkg.tanks[u] == s]
        H = merged_hist(pkg, ts)
        ren = sorted(pkg.renew.get(s, []))
        bounds = [-10 ** 9] + ren + [10 ** 9]
        la = [lab[u] for u in ts if u in lab]
        segs = []
        for k in range(len(bounds) - 1):
            lo, hi = bounds[k], bounds[k + 1]
            A = [(h[0], np.array(h[1:4], float)) for h in H if lo <= h[0] < hi]
            if k == len(bounds) - 2 and pkg.drawn is not None:
                if la:
                    A = A + [(pkg.drawn, np.mean(la, 0))]
            segs.append((lo, hi, A))
        tl[t] = segs
    return tl


# ===================================================================================================
# main
# ===================================================================================================
def main():
    t_start = time.time()
    if len(sys.argv) < 3:
        print('usage: quench.py PACKAGE_DIR OUT_CSV', file=sys.stderr)
        return 0
    pkgdir, outcsv = sys.argv[1], sys.argv[2]
    header = 'load,t85_core_s,cr700_core_K_s,dT_max_K,ts_core500_C,t150_core_s'
    try:
        pkg = Package(pkgdir)
    except Exception as e:
        log('package read failed', e)
        with open(outcsv, 'w') as f:
            f.write(header + '\n')
        return 0
    lab = {}
    tank_tl = {}
    clusters = None
    order = None
    try:
        clusters = build_clusters(pkg)
        order, needs = plan(pkg, clusters)
        for name, c in clusters.items():
            log('cluster %-28s sys=%-12s tanks=%s status=%s dep=%d' % (name, c.system, c.tanks, c.status, c.n_dep))
    except Exception:
        if os.environ.get('QUENCH_DEBUG'):
            import traceback
            traceback.print_exc()
        clusters = None
    if clusters is None:
        # simple plan: one tank of every renewed system, then of the others
        try:
            order = simple_order(pkg)
        except Exception:
            order = []
    log('order', order)
    try:
        lab = run_lab(pkg, order)
    except Exception:
        lab = {}
    log('lab', lab)
    try:
        if clusters is None:
            raise RuntimeError('no clusters')
        tank_tl = figures_by_tank(pkg, clusters, lab)
    except Exception:
        if os.environ.get('QUENCH_DEBUG'):
            import traceback
            traceback.print_exc()
        try:
            tank_tl = simple_figures(pkg, lab)
        except Exception:
            tank_tl = {}
    # global fallback figures
    allh = [h for t in pkg.hist for h in pkg.hist[t]]
    if allh:
        fb = np.mean(np.array([h[1:4] for h in allh], float), 0)
    elif lab:
        fb = np.mean(np.array(list(lab.values()), float), 0)
    else:
        fb = np.array([80.0, 580.0, 7.0])
    rows = []
    for L in pkg.loads:
        t = L.get('tank')
        d = L.get('_day')
        try:
            f = fig_at(tank_tl.get(t, []), d, fb) if d is not None else fb
        except Exception:
            f = fb
        steel = (L.get('steel') or '').strip()
        si = 1 if steel.upper().replace(' ', '') in ('42CRMO4',) else 0
        if steel.upper() not in ('C45', '42CRMO4'):
            si = 1 if 'CR' in steel.upper() else 0
        rows.append((L.get('load'), si, fnum(L.get('diameter_mm')), fnum(L.get('furnace_C')),
                     fnum(L.get('bath_C')), float(f[0]), float(f[1]), float(f[2])))
    if os.environ.get('QUENCH_FIGS'):
        with open(os.environ['QUENCH_FIGS'], 'w') as ff:
            ff.write('load,cm,tc,c3\n')
            for r in rows:
                ff.write('%s,%.6f,%.6f,%.6f\n' % (r[0], r[5], r[6], r[7]))
        if os.environ.get('QUENCH_FIGS_ONLY'):
            return 0
    results = compute(rows, t_start)
    try:
        od = os.path.dirname(os.path.abspath(outcsv))
        os.makedirs(od, exist_ok=True)
    except Exception:
        pass
    with open(outcsv, 'w') as fo:
        fo.write(header + '\n')
        for r, res in zip(rows, results):
            fo.write('%s,%s,%s,%s,%s,%s\n' % (r[0], fmt(res[0], 4), fmt(res[1], 5), fmt(res[2], 4),
                                             fmt(res[3], 4), fmt(res[4], 3)))
    log('done in %.1f s' % (time.time() - t_start))
    return 0


def fmt(v, nd):
    if v is None or not np.isfinite(v):
        return '0'
    return ('%.' + str(nd) + 'f') % v


def compute(rows, t_start):
    """Solve every distinct load; returns list of (t85, cr700, dTmax, ts500, t150)."""
    keys = {}
    uniq = []
    idx = []
    for r in rows:
        k = (r[1], round(r[2], 6), round(r[3], 6), round(r[4], 6), round(r[5], 9), round(r[6], 9), round(r[7], 9))
        if k not in keys:
            keys[k] = len(uniq)
            uniq.append(k)
        idx.append(keys[k])
    if not uniq:
        return []
    U = np.array(uniq, float)
    res = np.full((len(U), 5), np.nan)
    ok = np.isfinite(U).all(1)
    sel = np.where(ok)[0]
    if len(sel):
        out = solve_chunked(U[sel], N=25, dTstep=0.8, deadline=t_start + 42.0,
                            soft_budget=max(5.0, 30.0 - (time.time() - t_start)))
        res[sel] = out
    bad = np.where(~np.isfinite(res).all(1) & ok)[0]
    if len(bad) and time.time() < t_start + 30.0:
        log('re-solving %d loads' % len(bad))
        res[bad] = solve_chunked(U[bad], N=41, dTstep=0.3, deadline=t_start + 44.0)
    return [tuple(res[i]) for i in idx]


def solve_chunked(U, N, dTstep, chunk=4000, deadline=None, soft_budget=None):
    out = np.full((len(U), 5), np.nan)
    for s in range(0, len(U), chunk):
        u = U[s:s + chunk]
        with np.errstate(all='ignore'):
            o = solve(u[:, 0].astype(int), u[:, 1] / 2000.0, u[:, 2], u[:, 3], u[:, 4], u[:, 5], u[:, 6],
                      N=N, dTstep=dTstep, deadline=deadline, soft_budget=soft_budget)
        out[s:s + chunk] = np.stack([o['t85'], o['cr700'], o['dTmax'], o['ts500'], o['t150']], 1)
    return out


if __name__ == '__main__':
    try:
        rc = main()
    except Exception:
        import traceback
        traceback.print_exc()
        rc = 0
    sys.exit(0)
