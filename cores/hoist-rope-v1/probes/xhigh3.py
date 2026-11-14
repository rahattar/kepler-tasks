#!/usr/bin/env python3
"""Bending fatigue damage of crane hoist ropes to RS-4 (issue 3).

Usage: python3 ropes.py WORKS_DIR OUT_CSV

For every crane of the works package the damage of the rope element at each
station of the rope's last survey is reckoned from the movement log:

    damage = sum over movements, over the sheaves and the drum whose point of
             touch x = L - a - p (H - h) passes the element, of  w / N

    lg N = b0 + (b1 + b3 lg(D/d)) lg(S/d^2) + b2 lg(D/d),
    S = (m_h + m_b) g / (n e),

d being the element's diameter at the last survey on or before the movement.

Rope turned end for end
-----------------------
Damage belongs to the rope element, not to the place on the crane.  When a
rope is turned end for end, the element now at x was at L - x before, and it
took its damage and its measured diameter with it.  A package does not record
such a turn, but the surveys show it:

* From the second survey on, the diameter profile carries the wear pattern of
  the reeving.  Each survey is compared with the one before, both as measured
  and mirrored (x -> L - x); the rope is taken as turned between them when the
  mirrored comparison fits far better.
* Early in the rope's life the pattern is still faint, so every interval is
  also tried against the whole survey history: the wear of each element is
  fitted, over all surveys, as  d = c - a t - b D^g,  D the element's damage
  history from the log, with and without a turn in the interval.  A turn is
  added only on overwhelming evidence.

The date of a turn is only known to lie between two surveys.  The span is
narrowed to the dates the whole survey history does not rule out, and the
turn is placed where the greatest possible error of any station of that rope,
over all dates the turn could have had in that span, is least.

Should anything in the reckoning of turns fail, the crane's damage is reckoned
without turns, so that every station still gets its value.
"""
import sys
import os
import csv
import math

import numpy as np

G = 9.80665
COEF = {
    '8x36': (-1.214, 0.887, 7.432, -2.103),
    '6x36': (-1.371, 0.934, 7.518, -2.146),
}

TURN_RATIO = 0.25      # mirrored / as-measured residual variance for a turn
HIST_CHI2 = 20.0       # whole-history evidence needed for a further turn
HIST_GAMMAS = (0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 1.0)
HIST_GRID = 15         # trial turn dates inside an interval
DATE_BY_WEAR = True    # narrow a turn's date by the survey history
DATE_CHI2 = 30.0       # misfit beyond which a trial date is ruled out
CHUNK = 20000


# ----------------------------------------------------------------------------
# reading
# ----------------------------------------------------------------------------

def read_table(path):
    if not os.path.exists(path):
        return []
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return []
    head = [h.strip().lower() for h in rows[0]]
    out = []
    for r in rows[1:]:
        r = [c.strip() for c in r]
        r += [''] * (len(head) - len(r))
        out.append(dict(zip(head, r)))
    return out


def fnum(s, default=float('nan')):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def construction_coefs(name):
    key = str(name).strip().lower().replace(' ', '').replace('×', 'x')
    if key in COEF:
        return COEF[key]
    for k, v in COEF.items():
        if k in key:
            return v
    raise KeyError('unknown rope construction %r' % name)


# ----------------------------------------------------------------------------
# one crane
# ----------------------------------------------------------------------------

class Crane:
    def __init__(self, row, sheaves, movements, surveys):
        self.name = row['crane']
        self.n = fnum(row.get('falls'))
        self.H = fnum(row.get('upper_block_height_m'))
        self.mb = fnum(row.get('block_mass_t'), 0.0)
        self.e = fnum(row.get('reeving_efficiency'), 1.0)
        self.L = fnum(row.get('rope_length_m'))
        self.b0, self.b1, self.b2, self.b3 = construction_coefs(row.get('rope_construction'))

        # sheaves and drum: parts p, offset a, diameter D, weight w
        sp = []
        for s in sheaves:
            p = fnum(s.get('parts'))
            a = fnum(s.get('offset_m'), 0.0)
            D = fnum(s.get('diameter_mm'))
            w = fnum(s.get('bend_weight'))
            if math.isnan(w):
                w = 0.5 if s.get('sheave', '').strip().lower() == 'drum' else 1.0
            if math.isnan(p) or math.isnan(D) or D <= 0 or w <= 0:
                continue
            sp.append((p, a, D, w))
        self.sheaves = sp

        # movements in order of time (stable for equal times)
        mv = []
        for i, m in enumerate(movements):
            t = fnum(m.get('day'))
            h0 = fnum(m.get('from_height_m'))
            h1 = fnum(m.get('to_height_m'))
            q = fnum(m.get('hook_load_t'), 0.0)
            if math.isnan(t) or math.isnan(h0) or math.isnan(h1):
                continue
            mv.append((t, i, h0, h1, q))
        mv.sort()
        self.t = np.array([r[0] for r in mv], dtype=float)
        self.h0 = np.array([r[2] for r in mv], dtype=float)
        self.h1 = np.array([r[3] for r in mv], dtype=float)
        load = np.array([r[4] for r in mv], dtype=float)
        S = (load + self.mb) * 1000.0 * G / (self.n * self.e)
        self.lgS = np.log10(np.maximum(S, 1e-9))

        # surveys: day -> {station: diameter}
        by_day = {}
        for s in surveys:
            t = fnum(s.get('day'))
            x = fnum(s.get('station_m'))
            d = fnum(s.get('diameter_mm'))
            if math.isnan(t) or math.isnan(x) or math.isnan(d) or d <= 0:
                continue
            by_day.setdefault(t, {}).setdefault(x, []).append(d)
        self.sdays = np.array(sorted(by_day), dtype=float)
        self.sx, self.sd = [], []
        for t in self.sdays:
            xs = sorted(by_day[t])
            self.sx.append(np.array(xs, dtype=float))
            self.sd.append(np.array([np.mean(by_day[t][x]) for x in xs], dtype=float))
        self.st = self.sx[-1] if len(self.sdays) else np.zeros(0)
        K = len(self.sdays)
        self.km = np.clip(np.searchsorted(self.sdays, self.t, side='right') - 1, 0, max(K - 1, 0))
        self.turn = np.zeros(max(K - 1, 0), dtype=bool)
        self.turn_choice = []
        self.hist_log = []

    # ------------------------------------------------------------------
    def diam(self, k, y):
        """diameter measured at survey k at rope positions y (as then placed)"""
        x, d = self.sx[k], self.sd[k]
        if len(x) == 1:
            return np.full(np.shape(y), d[0])
        return np.interp(y, x, d)

    def pairwise_turns(self):
        """turn[k] when the rope was plainly turned between surveys k and k+1"""
        K = len(self.sdays)
        turn = np.zeros(max(K - 1, 0), dtype=bool)
        for k in range(K - 1):
            x1, d1 = self.sx[k + 1], self.sd[k + 1]
            if len(x1) < 3:
                continue
            v_id = np.var(self.diam(k, x1) - d1)
            v_tu = np.var(self.diam(k, self.L - x1) - d1)
            if v_tu < TURN_RATIO * v_id:
                turn[k] = True
        return turn

    def set_frames(self, turn):
        """element frames and endurance coefficients for a set of turns"""
        st = self.st
        ns = len(st)
        K = len(self.sdays)
        self.turn = turn
        flip = np.zeros(K, dtype=bool)  # at survey k element x was at L - x
        for k in range(K - 2, -1, -1):
            flip[k] = flip[k + 1] ^ turn[k]
        self.flip = flip
        dt = np.empty((K, ns))
        for k in range(K):
            dt[k] = self.diam(k, self.L - st if flip[k] else st)
        lgd = np.log10(dt)
        # lg(w/N) = A + B lg S, per survey, element, sheave
        self.A, self.B = [], []
        for (p, a, D, w) in self.sheaves:
            u = math.log10(D) - lgd
            e = self.b1 + self.b3 * u
            self.A.append(math.log10(w) - (self.b0 + self.b2 * u) + 2.0 * e * lgd)
            self.B.append(-e)

    def contrib(self, idx, flipm):
        """damage of each element (final station) from movements idx;
        flipm[i]: the rope was then turned relative to its final placing"""
        st = self.st
        y = np.where(flipm[:, None], self.L - st[None, :], st[None, :])
        out = np.zeros((len(idx), len(st)))
        lgS = self.lgS[idx]
        km = self.km[idx]
        h0 = self.h0[idx]
        h1 = self.h1[idx]
        for si, (p, a, D, w) in enumerate(self.sheaves):
            base = self.L - a - p * self.H
            x0 = base + p * h0
            x1 = base + p * h1
            lo = np.minimum(x0, x1)[:, None]
            hi = np.maximum(x0, x1)[:, None]
            ii, jj = np.nonzero((y > lo) & (y < hi))
            if len(ii) == 0:
                continue
            k = km[ii]
            out[ii, jj] += np.power(10.0, self.A[si][k, jj] + self.B[si][k, jj] * lgS[ii])
        return out

    def cum_at(self, cps, flip_value):
        """cumulative damage of movements before each time in cps, every
        element placed as at the end (False) or mirrored (True)"""
        ns = len(self.st)
        C = np.zeros((len(cps), ns))
        M = len(self.t)
        for c0 in range(0, M, CHUNK):
            idx = np.arange(c0, min(M, c0 + CHUNK))
            E = self.contrib(idx, np.full(len(idx), flip_value))
            cE = np.vstack([np.zeros(ns), np.cumsum(E, 0)])
            C += cE[np.searchsorted(self.t[idx], cps, side='left')]
        return C

    # ------------------------------------------------------------------
    # whole-history wear model
    # ------------------------------------------------------------------
    def history_model(self, turn):
        """Misfit of the survey history for a trial set of turn dates.

        Every element is fitted over all surveys with  d = c - a t - b D^g,
        b >= 0, D its bending damage history from the log for the trial turns,
        g the best of a few exponents.  Trial dates are taken from a grid."""
        K = len(self.sdays)
        ns = len(self.st)
        days = self.sdays
        grids = [np.linspace(days[k], days[k + 1], HIST_GRID + 2)[1:-1] for k in range(K - 1)]
        mids = 0.5 * (days[:-1] + days[1:])
        cps = np.unique(np.concatenate([days, mids] + grids))
        self.set_frames(turn)
        C0 = self.cum_at(cps, False)
        C1 = self.cum_at(cps, True)
        cidx = {float(v): i for i, v in enumerate(cps)}
        X1 = np.c_[np.ones(K), days]
        R1 = np.eye(K) - X1 @ np.linalg.pinv(X1)  # removes c + a t

        def element_D(tt):
            nt = len(tt)
            out = np.empty((K, ns))
            for k, t in enumerate(days):
                D = np.zeros(ns)
                start = None
                for q, bnd in enumerate([x for x in tt if x < t] + [t]):
                    C = C1 if (nt - q) % 2 == 1 else C0
                    D += C[cidx[float(bnd)]] - (C[cidx[float(start)]] if start is not None else 0.0)
                    start = bnd
                out[k] = D
            return out

        def readings(tt):
            tt = np.array(tt)
            Y = np.empty((K, ns))
            for k, t in enumerate(days):
                mir = int(np.sum(tt > t)) % 2 == 1
                Y[k] = self.diam(k, self.L - self.st if mir else self.st)
            return Y

        def rss(tt):
            tt = sorted(float(x) for x in tt)
            Yr = R1 @ readings(tt)
            r2 = np.sum(Yr * Yr, axis=0)
            D = np.maximum(element_D(tt), 0.0)
            best_r = None
            for g in HIST_GAMMAS:
                Qr = R1 @ (D ** g)
                qq = np.sum(Qr * Qr, axis=0)
                qy = np.sum(Qr * Yr, axis=0)
                ok = (qq > 1e-300) & (qy < 0)  # wear grows with damage
                gain = np.where(ok, qy * qy / np.where(ok, qq, 1.0), 0.0)
                r = float(np.sum(r2 - gain))
                if best_r is None or r < best_r:
                    best_r = r
            return best_r

        def snap(t):
            return float(cps[int(np.argmin(np.abs(cps - t)))])

        return dict(rss=rss, grids=grids, mids=[snap(m) for m in mids],
                    dof=max(K * ns - 3 * ns - 2, 1))

    def best_dates(self, turn, hm):
        """grid dates of the turns that fit the survey history best"""
        rss, grids, mids = hm['rss'], hm['grids'], hm['mids']
        ks = list(np.flatnonzero(turn))
        dates = {k: mids[k] for k in ks}
        for _ in range(2):
            for k in ks:
                others = [dates[q] for q in ks if q != k]
                cand = [mids[k]] + [float(x) for x in grids[k]]
                dates[k] = min(cand, key=lambda tau: rss(others + [tau]))
        return dates

    def history_turns(self, turn, hm):
        """add turns the pairwise comparison cannot show"""
        K = len(self.sdays)
        rss, grids = hm['rss'], hm['grids']
        for _ in range(3):
            base = list(self.best_dates(turn, hm).values())
            r0 = rss(base)
            best = None
            for k in range(K - 1):
                if turn[k]:
                    continue
                for tau in grids[k]:
                    r = rss(base + [tau])
                    if best is None or r < best[0]:
                        best = (r, k)
            if best is None:
                break
            s2 = best[0] / hm['dof']
            evidence = (r0 - best[0]) / s2 if s2 > 0 else 0.0
            self.hist_log.append((best[1], evidence))
            if evidence <= HIST_CHI2:
                break
            turn = turn.copy()
            turn[best[1]] = True
        return turn

    def plausible_dates(self, k, turn, hm):
        """span of turn dates in interval k the survey history does not rule out"""
        lo_t, hi_t = self.sdays[k], self.sdays[k + 1]
        if hm is None or not DATE_BY_WEAR:
            return lo_t, hi_t
        grid = hm['grids'][k]
        dates = self.best_dates(turn, hm)
        others = [dates[q] for q in dates if q != k]
        r = np.array([hm['rss'](others + [tau]) for tau in grid])
        s2 = r.min() / hm['dof']
        if not s2 > 0:
            return lo_t, hi_t
        ok = np.flatnonzero((r - r.min()) / s2 <= DATE_CHI2)
        a, b = ok.min() - 1, ok.max() + 1  # one grid step of margin
        return (grid[a] if a >= 0 else lo_t), (grid[b] if b < len(grid) else hi_t)

    # ------------------------------------------------------------------
    def plain_damage(self):
        """damage with the rope never turned"""
        ns = len(self.st)
        if ns == 0:
            return np.zeros(0)
        total = np.zeros(ns)
        if len(self.t) == 0 or not self.sheaves:
            return total
        self.set_frames(np.zeros(max(len(self.sdays) - 1, 0), dtype=bool))
        M = len(self.t)
        for c0 in range(0, M, CHUNK):
            idx = np.arange(c0, min(M, c0 + CHUNK))
            total += self.contrib(idx, np.zeros(len(idx), dtype=bool)).sum(0)
        return total

    def safe_damage(self):
        try:
            with np.errstate(all='ignore'):
                d = self.damage()
            if len(d) == len(self.st) and np.all(np.isfinite(d)):
                return d
        except Exception as exc:  # noqa: BLE001 - keep every station
            sys.stderr.write('%s: turns not reckoned (%s)\n' % (self.name, exc))
        with np.errstate(all='ignore'):
            return self.plain_damage()

    def damage(self):
        st = self.st
        ns = len(st)
        K = len(self.sdays)
        M = len(self.t)
        if ns == 0:
            return np.zeros(0)
        if M == 0 or not self.sheaves:
            return np.zeros(ns)
        turn = self.pairwise_turns()
        hm = None
        if K >= 5 and ns >= 4 and M >= 10:
            try:
                hm = self.history_model(turn)
                turn = self.history_turns(turn, hm)
            except (np.linalg.LinAlgError, ValueError, FloatingPointError):
                hm = None
        self.set_frames(turn)

        total = np.zeros(ns)
        in_turn = np.zeros(M, dtype=bool)
        turn_iv = []
        for k in range(K - 1):
            if turn[k]:
                lo = 0 if k == 0 else np.searchsorted(self.t, self.sdays[k], side='left')
                hi = np.searchsorted(self.t, self.sdays[k + 1], side='left')
                in_turn[lo:hi] = True
                turn_iv.append((k, lo, hi))
        # movements outside turn intervals: placed as at the survey in force
        rest = np.flatnonzero(~in_turn)
        for c0 in range(0, len(rest), CHUNK):
            idx = rest[c0:c0 + CHUNK]
            total += self.contrib(idx, self.flip[self.km[idx]]).sum(0)
        # turn intervals: date the turn by least worst-case error over the
        # dates the surveys leave open
        for (k, lo, hi) in turn_iv:
            idx = np.arange(lo, hi)
            if len(idx) == 0:
                continue
            E_old = self.contrib(idx, np.full(len(idx), self.flip[k]))
            E_new = self.contrib(idx, np.full(len(idx), self.flip[k + 1]))
            c_old = np.vstack([np.zeros(ns), np.cumsum(E_old, 0)])
            c_new = np.vstack([np.zeros(ns), np.cumsum(E_new, 0)])
            Dm = c_old + (c_new[-1] - c_new)  # turned just before movement i
            try:
                t_lo, t_hi = self.plausible_dates(k, turn, hm)
            except (np.linalg.LinAlgError, ValueError, FloatingPointError):
                t_lo, t_hi = self.sdays[k], self.sdays[k + 1]
            tt = self.t[idx]
            i_lo = int(np.searchsorted(tt, t_lo, side='left'))
            i_hi = int(np.searchsorted(tt, t_hi, side='right'))
            if t_lo <= self.sdays[k]:
                i_lo = 0
            if t_hi >= self.sdays[k + 1]:
                i_hi = len(idx)
            sub = Dm[i_lo:i_hi + 1]
            worst = np.maximum(sub.max(0)[None, :] - sub, sub - sub.min(0)[None, :]).max(1)
            i = i_lo + int(np.argmin(worst))
            total += Dm[i]
            t_turn = tt[i] if i < len(idx) else self.sdays[k + 1]
            self.turn_choice.append((self.sdays[k], self.sdays[k + 1], t_turn,
                                     float(worst.min()), t_lo, t_hi))
        return total


# ----------------------------------------------------------------------------
# package
# ----------------------------------------------------------------------------

def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: python3 ropes.py WORKS_DIR OUT_CSV\n')
        return 2
    wd, out_path = argv[1], argv[2]
    cranes = read_table(os.path.join(wd, 'cranes.csv'))
    sheaves = read_table(os.path.join(wd, 'sheaves.csv'))
    movements = read_table(os.path.join(wd, 'movements.csv'))
    surveys = read_table(os.path.join(wd, 'surveys.csv'))

    def group(rows):
        g = {}
        for r in rows:
            g.setdefault(r.get('crane', '').strip(), []).append(r)
        return g

    gs, gm, gv = group(sheaves), group(movements), group(surveys)
    lines = []
    for row in cranes:
        name = row.get('crane', '').strip()
        if not name:
            continue
        row['crane'] = name
        try:
            c = Crane(row, gs.get(name, []), gm.get(name, []), gv.get(name, []))
            dmg = c.safe_damage()
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write('%s: %s\n' % (name, exc))
            continue
        for j, v in enumerate(dmg):
            v = float(v) if np.isfinite(v) else 0.0
            lines.append('%s-%03d,%.10f' % (name, j + 1, v))
    with open(out_path, 'w', newline='') as f:
        f.write('row,damage\n')
        for ln in lines:
            f.write(ln + '\n')
    return 0


if __name__ == '__main__':
    try:
        status = main(sys.argv)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write('ropes.py: %s\n' % exc)
        status = 1
    sys.exit(status)
