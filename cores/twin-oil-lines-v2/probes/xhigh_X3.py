#!/usr/bin/env python3
"""Heated fuel oil lines to terminal standard TS-2, for one site package.

    python3 lines.py PACKAGE_DIR OUT_CSV

Writes OUT_CSV with the header record,dp_kPa,t_out_C and one row for every row
of the package's records.csv.

Outline
  1. The TS-2 model of one pipe (sections 2, 3).  The heat balance and the
     pressure gradient are integrated from the inlet manifold in s = (x/L)^(1/3),
     in which the entry-length rise of the Nusselt number is smooth, and the heat
     balance is carried in ln(Tb - Ta), which stays well behaved where a pipe
     given little oil brings it to the surroundings' temperature within a short
     distance.  The wall temperature of 3.2/3.3 is solved by Newton at every point.
  2. Pairs (section 4).  A pipe given less oil cools it more and the oil thickens,
     so the pressure drop of a pipe need not rise with its flow, and the division
     of a line's flow for equal pressure drops is often not unique.  The records of
     a line are an unbroken run in time order, so each record is solved from the
     division of the record before: the flow moves towards the pipe of the lower
     pressure drop until the pressure drops are equal.
  3. Uo of every pipe from the heat-loss surveys on file (5.2).  A survey made
     before (or on the day of) work renewing or repairing the pipe's covering is
     not used (5.3).  In a pair, every survey reading also gives the division of
     the line's flow, which must agree with equal pressure drops; where it does
     not, the pipe that takes too little flow has a bore smaller than the
     register's as-laid bore (5.1: pipes are not gauged in service), and its bore
     and Uo are fitted together.  A pipe whose Uo or bore moves from campaign to
     campaign is changing.
  4. One order to the survey crew for pipes as they stand now: the pipes with no
     valid survey on file (one per pair is enough, the division giving the other),
     then the changing pipes by their effect on the results, then the pipes whose
     state is least well known, up to the allowance.
  5. The present state of every line from the new readings and the surveys on
     file together (weighted least squares), then every record.
"""
import csv
import datetime
import json
import math
import os
import re
import subprocess
import sys

import numpy as np

# reading accuracy of a survey (TS-2 5.4)
SIG_T = 0.02     # oil temperature, K
SIG_TA = 0.1     # surroundings, K
SIG_F = 0.002    # flow, relative

# decision thresholds, in units of the reading accuracy above
Z_SPLIT = 3.0    # a pair's flow division against equal pressure drops
CHI_DRIFT = 1.0  # chi2 per degree of freedom of a pipe's Uo or bore between campaigns
Z_TREND = 1.5    # change from the first to the last campaign
# (on the steady pipes of the example packages chi2/dof is at most 0.4 and the
#  trend at most 0.7: the readings are well inside their stated accuracy)
Z_FRESH = 3.0    # a new survey against the surveys on file

LN10 = math.log(10.0)
NSTEP = 20       # RK4 steps in s: 4e-5 K and 2e-3 % against a tight adaptive integration
NSTEP_PAIR = 12  # in the search for the divisions of pairs: 3e-4 K and 1.5e-2 %


def log(*a):
    print(*a, file=sys.stderr)


# ---------------------------------------------------------------- the model

def visc(A, B, Tc):
    """ASTM D341 kinematic viscosity (cSt) and dln(nu)/dT."""
    TK = Tc + 273.15
    tz = 10.0 ** (A - B * np.log10(TK))
    nup = 10.0 ** tz
    nu = nup - 0.7
    return nu, (-LN10 * B / TK) * tz * nup / nu


def visc_nu(A, B, Tc):
    """ASTM D341 kinematic viscosity (cSt)."""
    return 10.0 ** (10.0 ** (A - B * np.log10(Tc + 273.15))) - 0.7


def solve_pipes(D, L, m, Tin, Ta, Uo, A, B, cp, k, N=NSTEP):
    """TS-2 section 3 for many pipes at once (numpy arrays, broadcast).
    D, L in m, m in kg/s, temperatures in C, Uo in W/m2K.
    Returns (outlet bulk temperature C, pressure drop Pa)."""
    D, L, m, Tin, Ta, Uo, A, B, cp, k = np.broadcast_arrays(
        *[np.asarray(v, dtype=float) for v in (D, L, m, Tin, Ta, Uo, A, B, cp, k)])
    gzx3 = np.cbrt(4.0 * m * cp / (math.pi * k * L))   # Gz^(1/3) at x = L (Gz = Re Pr D / x)
    k_D = k / D
    rate = math.pi * D * Uo * L / (m * cp)              # d ln(Tb-Ta) / d(x/L) = -rate theta
    dpc = 128e-6 * m * L / (math.pi * D ** 4)           # dp / d(x/L) = dpc sqrt(nu_b nu_w), nu in cSt
    c0 = 3.66 ** 3 + 0.7 ** 3
    sgn = np.where(Tin >= Ta, 1.0, -1.0)
    ZMIN = -60.0
    hs = 1.0 / N
    stage = []
    for i in range(2 * N + 1):                          # s = i / 2N, x = L s^3
        s = max(i * 0.5 * hs, 1e-9)
        c = 1.077 * gzx3 / s - 0.7
        h0 = np.cbrt(c0 + c * c * c) * k_D              # inside film without the viscosity correction
        stage.append((h0, 3.0 * s * s))
    th = stage[0][0] / (stage[0][0] + Uo)               # theta = (Tw - Ta) / (Tb - Ta)

    def rhs(i, z, th):
        h0, w = stage[i]
        d = sgn * np.exp(np.maximum(z, ZMIN))
        nub = visc_nu(A, B, Ta + d)
        for _ in range(2):                              # Newton on h (Tb - Tw) = Uo (Tw - Ta)
            nuw, dlw = visc(A, B, Ta + th * d)
            h = h0 * (nub / nuw) ** 0.14
            th = th - (h * (1.0 - th) - Uo * th) / (-0.14 * h * dlw * d * (1.0 - th) - h - Uo)
            th = np.minimum(np.maximum(th, 1e-12), 1.0)
        nuw = visc_nu(A, B, Ta + th * d)
        return -rate * th * w, dpc * np.sqrt(nub * nuw) * w, th

    z = np.log(np.maximum(np.abs(Tin - Ta), 1e-300))
    P = np.zeros_like(z)
    for j in range(N):
        i0 = 2 * j
        k1T, k1P, th = rhs(i0, z, th)
        k2T, k2P, th = rhs(i0 + 1, z + 0.5 * hs * k1T, th)
        k3T, k3P, th = rhs(i0 + 1, z + 0.5 * hs * k2T, th)
        k4T, k4P, th = rhs(i0 + 2, z + hs * k3T, th)
        z = z + hs / 6.0 * (k1T + 2.0 * k2T + 2.0 * k3T + k4T)
        P = P + hs / 6.0 * (k1P + 2.0 * k2P + 2.0 * k3P + k4P)
    return Ta + sgn * np.exp(np.maximum(z, ZMIN)), P


YMAX = 14.0                       # ln(mA/mB) searched over [-YMAX, YMAX]
TOL_G = 1e-8                      # |ln(dpA/dpB)| at a division of equal pressure drops
MARCH = np.concatenate([[0.01, 0.03, 0.07, 0.15], np.arange(0.3, 2.0 * YMAX + 0.3, 0.15)])
MARCH_CHUNKS = [(4, 14), (14, 44), (44, len(MARCH))]


def track_pairs(runs):
    """TS-2 section 4 for runs of records of pairs, each run in time order.

    The division of record j is the division of equal pressure drops that the
    flow reaches from the division of record j-1, moving towards the pipe of the
    lower pressure drop.  The first record of a run starts from the division in
    proportion to the bores' conductances.

    runs: list of dicts with arrays M (kg/s), Tin, Ta and scalars DA, DB, L, UA,
    UB, A, B, cp, k.  Returns a list of dicts of arrays phi (fraction to A),
    T (mixed outlet), dp (Pa)."""
    nr = len(runs)
    J = max((len(r['M']) for r in runs), default=0)
    out = [dict(phi=np.full(len(r['M']), np.nan), T=np.full(len(r['M']), np.nan),
                dp=np.full(len(r['M']), np.nan)) for r in runs]
    if nr == 0:
        return out
    yprev = np.array([4.0 * math.log(r['DA'] / r['DB']) for r in runs])
    par = {key: np.array([r[key] for r in runs], float)
           for key in ('DA', 'DB', 'L', 'UA', 'UB', 'A', 'B', 'cp', 'k')}

    for j in range(J):
        act = np.array([i for i in range(nr) if len(runs[i]['M']) > j], int)
        M = np.array([runs[i]['M'][j] for i in act])
        Tin = np.array([runs[i]['Tin'][j] for i in act])
        Ta = np.array([runs[i]['Ta'][j] for i in act])
        p = {key: v[act] for key, v in par.items()}

        def g(sel, y):
            """g = ln(dpA/dpB) at y = ln(mA/mB) for active runs sel (flat arrays)."""
            sel = np.asarray(sel, int)
            y = np.asarray(y, float)
            phi = 1.0 / (1.0 + np.exp(-y))
            Mr = M[sel]
            n = phi.size
            two = lambda a, b: np.concatenate([a, b])
            dbl = lambda a: np.tile(a[sel], 2)
            T, P = solve_pipes(two(p['DA'][sel], p['DB'][sel]), dbl(p['L']), two(phi * Mr, (1 - phi) * Mr),
                               dbl(Tin), dbl(Ta), two(p['UA'][sel], p['UB'][sel]), dbl(p['A']), dbl(p['B']),
                               dbl(p['cp']), dbl(p['k']), N=NSTEP_PAIR)
            return np.log(P[:n] / P[n:]), phi, T[:n], T[n:], P[:n], P[n:]

        na = len(act)
        y0 = yprev[act]
        # the previous division and the first steps either way from it
        offs = np.concatenate([[0.0], MARCH[:4], -MARCH[:4]])
        yy = np.clip(np.repeat(y0, len(offs)) + np.tile(offs, na), -YMAX, YMAX)
        ev = g(np.repeat(np.arange(na), len(offs)), yy)
        gg = ev[0].reshape(na, len(offs))
        evo = np.stack(ev[1:], axis=1).reshape(na, len(offs), 5)    # phi, TA, TB, PA, PB
        g0 = gg[:, 0]
        direction = np.where(g0 > 0, -1.0, 1.0)
        tmax = np.where(direction > 0, YMAX - y0, YMAX + y0)   # distance to the end of the range
        a = y0.copy(); ga = g0.copy()
        b = y0.copy(); gb = g0.copy()
        ob = evo[:, 0, :].copy()                                     # the outputs at b
        done = np.abs(g0) < TOL_G
        # the path of each run from y0 in its direction: distances, s0*g, refinement depth
        path, scan, chunk = [], [1] * na, [0] * na
        for i in range(na):
            cols = range(1, 5) if direction[i] > 0 else range(5, 9)
            ts, gs, os_ = [0.0], [g0[i]], [evo[i, 0]]
            for c in cols:
                t = min(MARCH[c - 1 if c < 5 else c - 5], tmax[i])
                if t > ts[-1] + 1e-12:
                    ts.append(t); gs.append(gg[i, c]); os_.append(evo[i, c])
            path.append([ts, gs, [0] * len(ts), os_])
        while True:
            req_i, req_t, req_d = [], [], []
            for i in np.where(~done)[0]:
                ts, gs, ds, os_ = path[i]
                s0 = 1.0 if g0[i] > 0 else -1.0
                k = scan[i]
                refine = None
                while k < len(ts):
                    if gs[k] * s0 <= 0:
                        yk1, yk = y0[i] + direction[i] * ts[k - 1], y0[i] + direction[i] * ts[k]
                        a[i], ga[i], b[i], gb[i] = yk1, gs[k - 1], yk, gs[k]
                        ob[i] = os_[k]
                        done[i] = True
                        break
                    if k >= 2 and ds[k - 1] < 2 and dip(ts[k - 2:k + 1], [s0 * v for v in gs[k - 2:k + 1]]):
                        # two roots may lie between these points: look closer
                        new = [t for t in np.linspace(ts[k - 2], ts[k], 12)[1:-1]
                               if all(abs(t - u) > 1e-9 for u in ts[k - 2:k + 1])]
                        if new:
                            refine = (new, ds[k - 1] + 1)
                            scan[i] = k - 1
                            break
                        ds[k - 1] = 2
                    k += 1
                if done[i]:
                    continue
                if refine is not None:
                    new, d = refine
                    req_i += [i] * len(new); req_t += new; req_d += [d] * len(new)
                    continue
                scan[i] = len(ts)
                new = []
                while not new and chunk[i] < len(MARCH_CHUNKS) and ts[-1] < tmax[i] - 1e-12:
                    c0, c1 = MARCH_CHUNKS[chunk[i]]
                    chunk[i] += 1
                    new = sorted(set(min(t, tmax[i]) for t in MARCH[c0:c1] if t > ts[-1] + 1e-12))
                if not new:
                    # one pipe all but stopped at the end of the range
                    a[i] = b[i] = y0[i] + direction[i] * ts[-1]
                    ga[i] = gb[i] = gs[-1]
                    ob[i] = os_[-1]
                    done[i] = True
                    continue
                req_i += [i] * len(new); req_t += new; req_d += [0] * len(new)
            if not req_i:
                break
            req_i = np.array(req_i)
            req_t = np.array(req_t)
            ev = g(req_i, y0[req_i] + direction[req_i] * req_t)
            evo = np.stack(ev[1:], axis=1)
            for i, t, d, v, o in zip(req_i, req_t, req_d, ev[0], evo):
                ts, gs, ds, os_ = path[i]
                q = int(np.searchsorted(ts, t))
                ts.insert(q, float(t)); gs.insert(q, float(v)); ds.insert(q, d); os_.insert(q, o)
        # Illinois refinement of the brackets [a, b]
        for _ in range(60):
            live = np.where((np.abs(gb) > TOL_G) & (np.abs(b - a) > 1e-11))[0]
            if live.size == 0:
                break
            den = gb[live] - ga[live]
            c = b[live] - gb[live] * (b[live] - a[live]) / np.where(den == 0, 1.0, den)
            lo, hi = np.minimum(a[live], b[live]), np.maximum(a[live], b[live])
            c = np.where((c > lo) & (c < hi) & (den != 0), c, 0.5 * (lo + hi))
            ev = g(live, c)
            gc = ev[0]
            flip = gc * gb[live] < 0
            a[live], ga[live] = np.where(flip, b[live], a[live]), np.where(flip, gb[live], 0.5 * ga[live])
            b[live], gb[live] = c, gc
            ob[live] = np.stack(ev[1:], axis=1)
        phi, TA, TB, PA, PB = ob.T
        for t, i in enumerate(act):
            out[i]['phi'][j] = phi[t]
            out[i]['T'][j] = phi[t] * TA[t] + (1 - phi[t]) * TB[t]
            out[i]['dp'][j] = 0.5 * (PA[t] + PB[t])
        yprev[act] = b
    return out


def dip(t, v):
    """Do three values v > 0 at t0 < t1 < t2 dip so low that a parabola
    through them could reach zero near t1 (a pair of close roots)?"""
    if not (v[1] <= v[0] and v[1] <= v[2]):
        return False
    f01 = (v[1] - v[0]) / (t[1] - t[0])
    f12 = (v[2] - v[1]) / (t[2] - t[1])
    c = (f12 - f01) / (t[2] - t[0])
    if c <= 0:
        return v[1] < 0.3 * min(v[0], v[2])
    tv = 0.5 * (t[0] + t[1]) - f01 / (2.0 * c)
    vmin = v[1] + f01 * (tv - t[1]) + c * (tv - t[0]) * (tv - t[1])
    return vmin < 0.3 * v[1]


def invert_uo(D, L, m, Tin, Tout, Ta, A, B, cp, k):
    """TS-2 5.2: the Uo for which 3.1-3.3 give the outlet temperature read."""
    arg = (Tin - Ta) / (Tout - Ta)
    bad = ~(np.isfinite(arg) & (arg > 1.0))
    arg = np.where(bad, 1.5, arg)
    uinf = m * cp * np.log(arg) / (math.pi * D * L)   # the limit of a very large inside film coefficient
    u0, u1 = np.log(uinf), np.log(1.3 * uinf)
    f = lambda u: solve_pipes(D, L, m, Tin, Ta, np.exp(u), A, B, cp, k)[0] - Tout
    f0, f1 = f(u0), f(u1)
    for _ in range(40):
        if np.max(np.abs(np.where(bad, 0, f1))) < 1e-9:
            break
        den = f1 - f0
        du = u1 - u0
        ok = (np.abs(den) > 1e-13) & (np.abs(du) > 1e-13)
        slope = np.where(ok, den / np.where(ok, du, 1.0), -1.0)
        slope = np.where(slope < -1e-6, slope, -1.0)   # the outlet temperature falls as Uo rises
        step = np.where((np.abs(f1) < 1e-10) | bad, 0.0, -f1 / slope)
        step = np.clip(step, -2.0, 2.0)
        u0, f0 = u1, f1
        u1 = u1 + step
        f1 = f(u1)
    U = np.exp(u1)
    U[bad] = np.nan
    return U


def lsq_multi(fun, X0, iters=40, tol=1e-9):
    """Levenberg-Marquardt for C independent small problems at once.
    fun(X, prob) gives the residuals (n, nres) of parameter rows X (n, p) of
    problems prob (n,).  Each iteration costs two calls of fun."""
    X = np.array(X0, float)
    C, p = X.shape
    R = fun(X, np.arange(C))
    nres = R.shape[1]
    cost = np.sum(R * R, axis=1)
    lam = np.full(C, 1e-3)
    active = np.ones(C, bool)
    mult = np.array([0.1, 1.0, 10.0])
    for _ in range(iters):
        idx = np.where(active)[0]
        if idx.size == 0:
            break
        n = idx.size
        H = 1e-6 * np.maximum(1.0, np.abs(X[idx]))
        Xp = np.repeat(X[idx], p, axis=0).reshape(n, p, p)
        Xp[:, np.arange(p), np.arange(p)] += H
        Rp = fun(Xp.reshape(n * p, p), np.repeat(idx, p)).reshape(n, p, nres)
        Jt = (Rp - R[idx][:, None, :]) / H[:, :, None]          # (n, p, nres) = J^T
        JTJ = Jt @ Jt.transpose(0, 2, 1)
        grad = (Jt @ R[idx][:, :, None])[:, :, 0]
        lams = lam[idx][:, None] * mult[None, :]
        dg = np.diagonal(JTJ, axis1=1, axis2=2)
        Amat = JTJ[:, None, :, :] + (lams[:, :, None, None] * (dg[:, None, :, None] + 1e-12)
                                     * np.eye(p)[None, None, :, :])
        try:
            dx = -np.linalg.solve(Amat, np.broadcast_to(grad[:, None, :, None], (n, 3, p, 1)))[..., 0]
        except np.linalg.LinAlgError:
            dx = np.zeros((n, 3, p))
        Xt = X[idx][:, None, :] + dx
        Rt = fun(Xt.reshape(n * 3, p), np.repeat(idx, 3)).reshape(n, 3, nres)
        ct = np.sum(Rt * Rt, axis=2)
        ct = np.where(np.isfinite(ct), ct, np.inf)
        best = np.argmin(ct, axis=1)
        cb = ct[np.arange(n), best]
        better = cb < cost[idx]
        for t, i in enumerate(idx):
            if better[t]:
                step = dx[t, best[t]]
                X[i] = Xt[t, best[t]]
                R[i] = Rt[t, best[t]]
                gain = cost[i] - cb[t]
                cost[i] = cb[t]
                lam[i] = max(lams[t, best[t]] / 3.0, 1e-9)
                if np.max(np.abs(step)) < tol or gain < 1e-12 * (1.0 + cost[i]):
                    active[i] = False
            else:
                lam[i] *= 100.0
                if lam[i] > 1e8:
                    active[i] = False
    return X, R


# ---------------------------------------------------------------- the package

def read_csv(path):
    with open(path, newline='') as f:
        return [{(kk or '').strip(): (v or '').strip() for kk, v in r.items()} for r in csv.DictReader(f)]


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float('nan')


def day(d):
    try:
        return datetime.date.fromisoformat(str(d).strip()).toordinal()
    except Exception:
        return None


COVER_RE = re.compile(r'covering|re-?cover|\blag|relag|insulat|cladd')
NOT_WORK_RE = re.compile(r'inspect|check|examin|survey|measur|test|photo|looked')
WORK_RE = re.compile(r'renew|repair|replac|patch|refit|re-?fit|reinstat|restor|mend|fix|new|re-?lag|re-?cover|redone|rebuil|install')


def covering_job(job):
    """True for work that renews or repairs the covering (TS-2 5.3)."""
    j = ' '.join(job.lower().replace('_', ' ').split())
    if not COVER_RE.search(j):
        return False
    if NOT_WORK_RE.search(j) and not WORK_RE.search(j):
        return False
    return True


class Pipe:
    def __init__(self, name, line):
        self.name = name
        self.line = line
        self.rows = []          # survey readings on file
        self.fresh = []         # readings of the new survey
        self.cover_dates = []   # dates of covering work
        self.status = 'steady'  # steady, nohist, drift, fouling
        self.fouled = False     # bore smaller than laid
        self.bore_moving = False
        self.U_hist = None      # Uo from the surveys on file, carried to the present
        self.sU_hist = None     # its uncertainty, relative
        self.D_hist = None      # bore from the surveys on file
        self.sD_hist = 0.05
        self.latest_any = None
        self.score = 0.0
        self.U = None           # present state
        self.D = None


class Line:
    def __init__(self, row, oils):
        self.name = row['line']
        self.npipes = 2 if str(row.get('pipes', '1')).strip().startswith('2') else 1
        self.D = fnum(row['bore_mm']) / 1000.0
        self.L = fnum(row['length_m'])
        o = oils[row['oil']]
        self.A, self.B, self.cp, self.k = o['A'], o['B'], o['cp'], o['k']
        self.pipes = [Pipe(f'{self.name}-{c}', self) for c in 'AB'[:self.npipes]]


def load_oils(rows):
    oils = {}
    for r in rows:
        v1, v2 = fnum(r['nu50_cSt']), fnum(r['nu100_cSt'])
        T1, T2 = 323.15, 373.15
        z1 = math.log10(math.log10(v1 + 0.7))
        z2 = math.log10(math.log10(v2 + 0.7))
        B = (z1 - z2) / (math.log10(T2) - math.log10(T1))
        A = z1 + B * math.log10(T1)
        oils[r['oil']] = dict(A=A, B=B, cp=fnum(r['cp_J_kgK']), k=fnum(r['k_W_mK']),
                              rho=fnum(r['density_kg_m3']))
    return oils


def norm_pipe(name):
    return ''.join(str(name).upper().split())


class Reading:
    """One survey reading of one pipe."""

    def __init__(self, pipe, date, M, m, Tin, Tout, Ta):
        self.pipe, self.date = pipe, date
        self.M, self.m, self.Tin, self.Tout, self.Ta = M, m, Tin, Tout, Ta
        if pipe.line.npipes == 1:
            # line flow and pipe flow are two readings of the same flow
            self.m = self.M = 0.5 * (M + m)
        self.U = None
        self.sU = None
        self.Dfit = None


def partner(p):
    ln = p.line
    if ln.npipes == 1:
        return None
    return ln.pipes[1] if p is ln.pipes[0] else ln.pipes[0]


def sig_T(r):
    """Uncertainty of an outlet temperature reading as the model sees it."""
    a = (r.Tout - r.Ta) / max(r.Tin - r.Ta, 1e-6)
    a = min(max(a, 1e-6), 1.0)
    dlnm = (r.Tout - r.Ta) * math.log(1.0 / a)
    return math.sqrt(SIG_T ** 2 + (SIG_T * a) ** 2 + (SIG_TA * (1 - a)) ** 2 + (SIG_F * dlnm) ** 2)


def sig_split(r):
    """Uncertainty of ln(dp_P / dp_Q) from the flow readings of a pair."""
    mq = max(r.M - r.m, 1e-9)
    return SIG_F * math.sqrt((1.0 + r.m / mq) ** 2 + (r.M / mq) ** 2)


def solve_specs(specs):
    """Pipes given as rows (line, D, m kg/s, Tin, Ta, U); one call of the model."""
    if not specs:
        return np.zeros(0), np.zeros(0)
    ln = [s[0] for s in specs]
    a = lambda j: np.array([s[j] for s in specs], float)
    return solve_pipes(a(1), np.array([l.L for l in ln]), a(2), a(3), a(4), a(5),
                       np.array([l.A for l in ln]), np.array([l.B for l in ln]),
                       np.array([l.cp for l in ln]), np.array([l.k for l in ln]))


def apparent_uo(readings):
    """Uo of each reading with the register bore, and its uncertainty."""
    if not readings:
        return
    ln = [r.pipe.line for r in readings]
    a = lambda f: np.array([f(i, r) for i, r in enumerate(readings)], float)
    D, L = a(lambda i, r: ln[i].D), a(lambda i, r: ln[i].L)
    m, Tin = a(lambda i, r: r.m / 3.6), a(lambda i, r: r.Tin)
    Tout, Ta = a(lambda i, r: r.Tout), a(lambda i, r: r.Ta)
    A, B = a(lambda i, r: ln[i].A), a(lambda i, r: ln[i].B)
    cp, k = a(lambda i, r: ln[i].cp), a(lambda i, r: ln[i].k)
    U = invert_uo(D, L, m, Tin, Tout, Ta, A, B, cp, k)
    Us = np.where(np.isfinite(U), U, 1.0)
    n = len(readings)
    # sensitivities, all in one call
    rep = lambda v: np.tile(v, 5)
    Ux = np.concatenate([Us, Us * 1.001, Us, Us, Us])
    mx = np.concatenate([m, m, m, m, m * 1.001])
    Tx = np.concatenate([Tin, Tin, Tin + 0.01, Tin, Tin])
    Tax = np.concatenate([Ta, Ta, Ta, Ta + 0.05, Ta])
    T = solve_pipes(rep(D), rep(L), mx, Tx, Tax, Ux, rep(A), rep(B), rep(cp), rep(k))[0].reshape(5, n)
    dU = (T[1] - T[0]) / (Us * 0.001)
    dTin = (T[2] - T[0]) / 0.01
    dTa = (T[3] - T[0]) / 0.05
    dm = (T[4] - T[0]) / 0.001
    sU = np.sqrt(SIG_T ** 2 + (SIG_T * dTin) ** 2 + (SIG_TA * dTa) ** 2 + (SIG_F * dm) ** 2) / np.abs(dU)
    for i, r in enumerate(readings):
        r.U = float(U[i]) if np.isfinite(U[i]) else None
        r.sU = float(sU[i] / Us[i]) if np.isfinite(U[i]) else None


# ---------------------------------------------------------------- surveys on file

def analyse_history(lines, pipes, dates, t_now=None):
    allrows = [r for p in pipes.values() for r in p.rows]
    apparent_uo(allrows)

    # the flow division of every pair at every campaign, in one call
    items = []
    for ln in lines:
        if ln.npipes != 2:
            continue
        pa, pb = ln.pipes
        ra_by = {r.date: r for r in pa.rows if r.U is not None}
        rb_by = {r.date: r for r in pb.rows if r.U is not None}
        for d in sorted(set(ra_by) & set(rb_by)):
            items.append((ln, d, ra_by[d], rb_by[d]))
    specs = []
    for ln, d, ra, rb in items:
        specs += [(ln, ln.D, ra.m / 3.6, ra.Tin, ra.Ta, ra.U), (ln, ln.D, (ra.M - ra.m) / 3.6, ra.Tin, ra.Ta, rb.U),
                  (ln, ln.D, rb.m / 3.6, rb.Tin, rb.Ta, rb.U), (ln, ln.D, (rb.M - rb.m) / 3.6, rb.Tin, rb.Ta, ra.U)]
    _, P = solve_specs(specs)
    zc = {}
    for t, (ln, d, ra, rb) in enumerate(items):
        za = math.log(P[4 * t] / P[4 * t + 1]) / sig_split(ra)
        zb = math.log(P[4 * t + 2] / P[4 * t + 3]) / sig_split(rb)
        zc.setdefault(ln.name, {})[d] = 0.5 * (za - zb)   # from A's side: < 0 when A takes too little flow
    fouled = []
    for ln in lines:
        z = zc.get(ln.name)
        if not z:
            continue
        dmax = max(z, key=lambda d: abs(z[d]))
        if abs(z[dmax]) > Z_SPLIT:
            bad, good = (ln.pipes[0], ln.pipes[1]) if z[dmax] < 0 else (ln.pipes[1], ln.pipes[0])
            bad.fouled = True
            fouled.append((ln, bad, good))
            log(f'{ln.name}: flow division off equal pressure drops (z {z[dmax]:+.1f} at {dmax}); '
                f'{bad.name} has a smaller bore than laid')
    fit_bores(fouled)
    for p in pipes.values():
        summarise_pipe(p, dates, t_now)


def fit_bores(fouled):
    """Bore and Uo of each fouled pipe P at each campaign, its partner Q as laid."""
    probs = []
    for ln, P, Q in fouled:
        q_by = {r.date: r for r in Q.rows if r.U is not None}
        for r in P.rows:
            if r.U is not None and r.date in q_by:
                probs.append((ln, r, q_by[r.date]))
    if not probs:
        return
    sTs = np.array([sig_T(r) for _, r, _ in probs])
    sSp = np.array([sig_split(r) for _, r, _ in probs])
    sSq = np.array([sig_split(rq) for _, _, rq in probs])

    def fun(X, prob):
        specs = []
        for x, c in zip(X, prob):
            ln, r, rq = probs[c]
            U, D = math.exp(x[0]), x[1] * ln.D
            specs += [(ln, D, r.m / 3.6, r.Tin, r.Ta, U), (ln, ln.D, (r.M - r.m) / 3.6, r.Tin, r.Ta, rq.U),
                      (ln, ln.D, rq.m / 3.6, rq.Tin, rq.Ta, rq.U), (ln, D, (rq.M - rq.m) / 3.6, rq.Tin, rq.Ta, U)]
        T, Pp = solve_specs(specs)
        T, Pp = T.reshape(-1, 4), Pp.reshape(-1, 4)
        Tout = np.array([probs[c][1].Tout for c in prob])
        return np.stack([(T[:, 0] - Tout) / sTs[prob], np.log(Pp[:, 0] / Pp[:, 1]) / sSp[prob],
                         np.log(Pp[:, 2] / Pp[:, 3]) / sSq[prob]], axis=1)

    # a start from the pressure drop going with the bore to the fourth power
    X0 = np.array([[math.log(r.U), 1.0] for _, r, _ in probs])
    R0 = fun(X0, np.arange(len(probs)))
    X0[:, 1] = np.exp(R0[:, 1] * sSp / 4.0)
    X, _ = lsq_multi(fun, X0)
    for (ln, r, rq), x in zip(probs, X):
        r.U_app = r.U
        r.U = math.exp(x[0])
        r.Dfit = x[1] * ln.D
        log(f'  {r.pipe.name} {r.date}: bore {r.Dfit*1000:.2f} mm, Uo {r.U:.3f} (with the laid bore {r.U_app:.3f})')


def extrapolate(series, t_now, lo, hi):
    """Value at t_now on the line through the last two (date, value) points."""
    pts = sorted((day(d), v) for d, v in series if day(d) is not None)
    if not pts:
        return series[-1][1] if series else None
    if len(pts) < 2 or t_now is None:
        return pts[-1][1]
    (t1, v1), (t2, v2) = pts[-2], pts[-1]
    if t2 <= t1:
        return v2
    v = v2 + (v2 - v1) / (t2 - t1) * max(0, t_now - t2)
    return min(max(v, lo * v2), hi * v2)


def summarise_pipe(p, dates, t_now=None):
    last_cover = max(p.cover_dates) if p.cover_dates else ''
    # a survey on the day of the work cannot be placed before or after it
    valid = [r for r in p.rows if r.U is not None and r.date > last_cover]
    p.latest_any = max((r for r in p.rows if r.U is not None), key=lambda r: r.date, default=None)
    dD = 0.0
    if p.fouled:
        Ds = sorted((r for r in p.rows if r.Dfit is not None), key=lambda r: r.date)
        if Ds:
            lnD = np.array([math.log(r.Dfit) for r in Ds])
            sD = np.array([sig_split(r) / 4.0 for r in Ds])
            w = 1.0 / sD ** 2
            mD = float(np.sum(w * lnD) / np.sum(w))
            chiD = float(np.sum(w * (lnD - mD) ** 2) / (len(Ds) - 1)) if len(Ds) > 1 else 0.0
            if chiD > CHI_DRIFT:
                # the bore is still closing: carry it on to the present
                p.bore_moving = True
                p.D_hist = extrapolate([(r.date, r.Dfit) for r in Ds], t_now, 0.7, 1.0)
                dD = abs(Ds[-1].Dfit - Ds[-2].Dfit) / Ds[-1].Dfit
                log(f'{p.name}: bore closing (' + ', '.join(f'{r.date} {r.Dfit*1000:.2f}' for r in Ds) +
                    f' mm; chi2/dof {chiD:.1f}); carried on to {p.D_hist*1000:.2f} mm')
            else:
                p.D_hist = math.exp(mD)
                p.sD_hist = max(float(1.0 / math.sqrt(np.sum(w))), 1e-4)
    if not valid:
        p.status = 'nohist'
        p.score = 1e6
        log(f'{p.name}: no survey on file since its covering work of {last_cover}')
        return
    u = np.array([r.U for r in valid])
    s = np.array([r.sU for r in valid]) * u
    w = 1.0 / s ** 2
    mu = float(np.sum(w * u) / np.sum(w))
    p.U_hist = mu
    p.sU_hist = float(1.0 / math.sqrt(np.sum(w)) / mu)
    chi = float(np.sum(w * (u - mu) ** 2) / (len(valid) - 1)) if len(valid) >= 2 else 0.0
    srt = sorted(valid, key=lambda r: r.date)
    trend = 0.0
    if len(srt) >= 2:
        trend = abs(srt[-1].U - srt[0].U) / math.hypot(srt[-1].U * srt[-1].sU, srt[0].U * srt[0].sU)
    if chi > CHI_DRIFT or trend > Z_TREND:
        # the covering is changing: carry its Uo on to the present
        p.status = 'drift'
        p.U_hist = extrapolate([(r.date, r.U) for r in srt], t_now, 0.5, 2.0)
        p.score = 1e5 + 1e3 * abs(srt[-1].U - srt[-2].U) / srt[-1].U
        log(f'{p.name}: Uo moves between campaigns (' + ', '.join(f'{r.date} {r.U:.3f}' for r in srt) +
            f'; chi2/dof {chi:.1f}, trend {trend:.1f}); carried on to {p.U_hist:.3f}')
    elif p.bore_moving:
        p.status = 'fouling'
        p.score = 1e5 + 1e3 * 4.0 * dD          # the pressure drop goes with the bore to the fourth power
    else:
        # how well the present state is known: fewer campaigns, larger spread
        p.score = chi + (1.0 if len(valid) == 1 else 0.0) + 0.1 * len(dates) / len(valid)


# ---------------------------------------------------------------- the survey order

def choose_order(lines, allowance):
    cand = []
    for ln in lines:
        nh = [p for p in ln.pipes if p.status == 'nohist']
        for i, p in enumerate(nh):
            # one new survey of a pair also gives the other pipe, through the division
            cand.append((1e6 if i == 0 else 1e3, p.name))
        for p in ln.pipes:
            if p.status == 'nohist':
                continue
            sc = p.score
            q = partner(p)
            if q is not None and q.status in ('fouling', 'drift') and sc < 10:
                sc += 10.0
            cand.append((sc, p.name))
    cand.sort(key=lambda c: -c[0])
    return [n for _, n in cand[:max(0, allowance)]]


def order_surveys(pkg_dir, names):
    if not names:
        return []
    try:
        pr = subprocess.run(['heatsurvey', pkg_dir] + names, capture_output=True, text=True, timeout=45)
    except Exception as e:      # no crew: carry on from the surveys on file
        log('survey order failed:', e)
        return []
    if pr.returncode != 0:
        log('survey order refused:', pr.stdout.strip(), pr.stderr.strip())
    out = []
    rows = [l for l in pr.stdout.splitlines() if l.strip()]
    hdr = next((i for i, l in enumerate(rows) if 'pipe' in l and 't_out_C' in l), None)
    if hdr is None:
        return []
    for r in csv.DictReader(rows[hdr:]):
        out.append({(kk or '').strip(): (v or '').strip() for kk, v in r.items()})
    log(f'new surveys: {len(out)} rows')
    return out


# ---------------------------------------------------------------- present state

def present_state(ln):
    """Uo and bore of the line's pipes as they stand now."""
    pipes = ln.pipes
    prior = {}
    for p in pipes:
        if p.status in ('steady', 'fouling') and p.U_hist:
            prior[p.name] = (math.log(p.U_hist), max(p.sU_hist, 1e-3))
        elif p.status == 'drift':
            prior[p.name] = (math.log(p.U_hist), 0.3)
        else:
            u0 = p.latest_any.U if p.latest_any is not None else 5.0
            prior[p.name] = (math.log(u0), 1.0)
        p.D = p.D_hist if (p.fouled and p.D_hist) else ln.D
        p.U = math.exp(prior[p.name][0])
    obs = [(p, r) for p in pipes for r in p.fresh if r.U is not None]
    if not obs:
        return
    sT = np.array([sig_T(r) for _, r in obs])
    sS = np.array([sig_split(r) for _, r in obs])
    Tout = np.array([r.Tout for _, r in obs])
    pidx = {p.name: i for i, p in enumerate(pipes)}

    free_D = [p for p in pipes if p.fouled]
    for attempt in range(4):
        dpos = {p.name: len(pipes) + j for j, p in enumerate(free_D)}

        def fun(X, prob):
            specs = []
            for x in X:
                U = [math.exp(x[i]) for i in range(len(pipes))]
                D = [x[dpos[p.name]] * ln.D if p.name in dpos else ln.D for p in pipes]
                for p, r in obs:
                    i = pidx[p.name]
                    specs.append((ln, D[i], r.m / 3.6, r.Tin, r.Ta, U[i]))
                    if ln.npipes == 2:
                        specs.append((ln, D[1 - i], (r.M - r.m) / 3.6, r.Tin, r.Ta, U[1 - i]))
            T, P = solve_specs(specs)
            per = 2 if ln.npipes == 2 else 1
            T, P = T.reshape(len(X), len(obs), per), P.reshape(len(X), len(obs), per)
            res = [np.stack([(X[:, i] - prior[p.name][0]) / prior[p.name][1] for i, p in enumerate(pipes)], axis=1)]
            for p in free_D:
                d0 = (p.D_hist or ln.D) / ln.D
                res.append(((X[:, dpos[p.name]] - d0) / max(p.sD_hist, 1e-4))[:, None])
            res.append((T[:, :, 0] - Tout[None, :]) / sT[None, :])
            if per == 2:
                res.append(np.log(P[:, :, 0] / P[:, :, 1]) / sS[None, :])
            return np.concatenate(res, axis=1)

        x0 = [prior[p.name][0] for p in pipes]
        for i, p in enumerate(pipes):           # start from the new readings where there are some
            rows = [r for r in p.fresh if r.U is not None]
            if rows and not p.fouled:
                x0[i] = math.log(np.mean([r.U for r in rows]))
        x0 += [(p.D_hist or ln.D) / ln.D for p in free_D]
        X, _ = lsq_multi(fun, np.array([x0]))
        x = X[0]
        U = {p.name: math.exp(x[i]) for i, p in enumerate(pipes)}
        D = {p.name: (x[dpos[p.name]] * ln.D if p.name in dpos else ln.D) for p in pipes}

        # does the line stand as the surveys on file say?
        changed = False
        for i, p in enumerate(pipes):
            mu, s = prior[p.name]
            if s < 0.2 and p.fresh and abs((x[i] - mu) / s) > Z_FRESH:
                log(f'{p.name}: new survey Uo {U[p.name]:.3f} against {math.exp(mu):.3f} on file: changed')
                prior[p.name] = (mu, 1.0)
                changed = True
        if ln.npipes == 2 and not changed and not free_D:
            specs = []
            for p, r in obs:
                q = partner(p)
                specs += [(ln, D[p.name], r.m / 3.6, r.Tin, r.Ta, U[p.name]),
                          (ln, D[q.name], (r.M - r.m) / 3.6, r.Tin, r.Ta, U[q.name])]
            _, P = solve_specs(specs)
            zs = np.log(P[0::2] / P[1::2]) / sS
            for (p, r), z in zip(obs, zs):
                if abs(z) > Z_SPLIT:
                    bad = p if z < 0 else partner(p)
                    log(f'{ln.name}: new flow division off equal pressure drops (z {z:+.1f}); '
                        f'{bad.name} has a smaller bore than laid')
                    bad.fouled = True
                    free_D = [bad]
                    changed = True
                    break
        if not changed:
            break
    for p in pipes:
        p.U, p.D = U[p.name], D[p.name]


# ---------------------------------------------------------------- main

def main():
    if len(sys.argv) != 3:
        sys.exit('usage: python3 lines.py PACKAGE_DIR OUT_CSV')
    pkg, out_csv = sys.argv[1], sys.argv[2]
    J = lambda f: os.path.join(pkg, f)

    try:
        with open(J('site.json')) as f:
            site = json.load(f)
    except Exception:
        site = {}
    allowance = int(fnum(site.get('survey_allowance', 0)) or 0)
    oils = load_oils(read_csv(J('oils.csv')))
    lines = [Line(r, oils) for r in read_csv(J('lines.csv'))]
    byline = {ln.name: ln for ln in lines}
    pipes = {p.name: p for ln in lines for p in ln.pipes}

    def find_pipes(name):
        n = norm_pipe(name)
        if n in pipes:
            return [pipes[n]]
        if n in byline:
            return list(byline[n].pipes)
        return []

    job_dates = []
    if os.path.exists(J('work_log.csv')):
        for w in read_csv(J('work_log.csv')):
            job_dates.append(w.get('date', ''))
            if covering_job(w.get('job', '')):
                for p in find_pipes(w.get('pipe', '')):
                    p.cover_dates.append(w.get('date', ''))

    cols = ('line_flow_t_h', 'flow_t_h', 't_in_C', 't_out_C', 't_amb_C')
    dates = set()
    if os.path.exists(J('surveys.csv')):
        for s in read_csv(J('surveys.csv')):
            ps = find_pipes(s.get('pipe', ''))
            vals = [fnum(s.get(c)) for c in cols]
            if len(ps) != 1 or not all(np.isfinite(vals)):
                continue
            ps[0].rows.append(Reading(ps[0], s.get('date', ''), *vals))
            dates.add(s.get('date', ''))

    # the present: after every survey and job on file (the records follow them)
    known = [t for t in (day(d) for d in list(dates) + job_dates) if t is not None]
    t_now = max(known) + 3 if known else None
    analyse_history(lines, pipes, dates, t_now)

    # the one order to the survey crew
    names = choose_order(lines, allowance)
    log('survey order:', ' '.join(names))
    newr = []
    for s in order_surveys(pkg, names):
        ps = find_pipes(s.get('pipe', ''))
        vals = [fnum(s.get(c)) for c in cols]
        if len(ps) != 1 or not all(np.isfinite(vals)):
            continue
        r = Reading(ps[0], 'now', *vals)
        ps[0].fresh.append(r)
        newr.append(r)
    apparent_uo(newr)

    for ln in lines:
        present_state(ln)
        log(f'{ln.name}: ' + '  '.join(f'{p.name} Uo {p.U:.3f} bore {p.D*1000:.2f} mm [{p.status}]'
                                       for p in ln.pipes))

    # the records
    recs = read_csv(J('records.csv'))
    n = len(recs)
    dp = np.full(n, np.nan)
    tout = np.full(n, np.nan)
    singles, runs_idx = [], {}
    for i, r in enumerate(recs):
        ln = byline.get(r.get('line'))
        if ln is None:
            continue
        if ln.npipes == 1:
            singles.append(i)
        else:
            runs_idx.setdefault(ln.name, []).append(i)
    if singles:
        T, P = solve_specs([(byline[recs[i]['line']], byline[recs[i]['line']].pipes[0].D,
                             fnum(recs[i]['flow_t_h']) / 3.6, fnum(recs[i]['t_in_C']),
                             fnum(recs[i]['t_amb_C']), byline[recs[i]['line']].pipes[0].U) for i in singles])
        dp[singles], tout[singles] = P, T
    runs, order = [], []
    for name, idx in runs_idx.items():
        ln = byline[name]
        hour = lambda i: fnum(recs[i].get('hour'))
        idx = sorted(idx, key=lambda i: (hour(i) if np.isfinite(hour(i)) else float(i), i))   # in time order
        order.append(idx)
        runs.append(dict(M=np.array([fnum(recs[i]['flow_t_h']) / 3.6 for i in idx]),
                         Tin=np.array([fnum(recs[i]['t_in_C']) for i in idx]),
                         Ta=np.array([fnum(recs[i]['t_amb_C']) for i in idx]),
                         DA=ln.pipes[0].D, DB=ln.pipes[1].D, L=ln.L, UA=ln.pipes[0].U, UB=ln.pipes[1].U,
                         A=ln.A, B=ln.B, cp=ln.cp, k=ln.k))
    for idx, rr in zip(order, track_pairs(runs)):
        dp[idx], tout[idx] = rr['dp'], rr['T']

    with open(out_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['record', 'dp_kPa', 't_out_C'])
        for i, r in enumerate(recs):
            d, t = dp[i] / 1000.0, tout[i]
            w.writerow([r['record'], f'{d:.4f}' if np.isfinite(d) else '', f'{t:.3f}' if np.isfinite(t) else ''])


if __name__ == '__main__':
    main()
