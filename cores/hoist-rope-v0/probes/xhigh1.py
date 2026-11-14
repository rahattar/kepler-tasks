#!/usr/bin/env python3
"""Bending fatigue damage of crane hoist ropes to RS-4 (issue 3).

    python3 ropes.py WORKS_DIR OUT_CSV

Reads cranes.csv, sheaves.csv, movements.csv and surveys.csv of one works
package and writes OUT_CSV with the header ``row,damage``: one row for every
station of the last survey of every crane's rope, named ``<crane>-<nnn>``
(stations numbered from the drum anchorage from 001).

Model (RS-4)
------------
* A sheave with p falls between it and the dead end touches the rope at
  x = L - a - p (H - h); the drum likewise with p = n.  In a movement from
  h1 to h2 every element between x(h1) and x(h2) is bent once over it,
  counting w (1 for a sheave, 0.5 for the drum).
* S = (m_h + m_b) g / (n e);
  lg N = b0 + (b1 + b3 lg(D/d)) lg(S/d^2) + b2 lg(D/d),
  d the element's diameter at the last survey on or before the movement.
* Damage of an element = sum of w / N since the rope was put on, reported for
  the element at each station of the rope's last survey.

Rope reversal
-------------
Works turn hoist ropes end for end to spread the wear.  No file of the
package records it, but the surveys show it: after a reversal the element at
station x is the element that was at L - x, and the diameter profile comes
out mirrored.  The damage then has to follow the element, not the station.

The surveys follow the rope's damage closely: an element's diameter is
d0 - alpha t - beta D^gamma (D its damage so far) within the caliper's
repeatability.  For each crane the program finds the reversals (none, one or
more, each in some interval between surveys, or before the first survey) that
best explain all its surveys under that law.  A reversal is accepted only on
strong evidence (a large drop of the residual sum of squares measured against
the survey scatter).  The moment of each reversal inside its interval comes
out as a likelihood over candidate moments.  Every movement of that interval
is counted in the old and the new orientation in proportion to the
probability that it came before or after the reversal.  A rope renewal (a
later survey flat, like a new rope, and clearly thicker than the one before)
restarts the count.
"""
import sys
import numpy as np
import pandas as pd

G = 9.80665
COEF = {
    "8x36": (-1.214, 0.887, 7.432, -2.103),
    "6x36": (-1.371, 0.934, 7.518, -2.146),
}
CHUNK = 8192            # movements per block in the vectorised damage pass
N_CAND = 80             # candidate reversal moments per interval
PEN = 30.0              # SS drop, in units of the residual variance, to accept a reversal
GAMMAS = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)   # wear exponents tried
MAX_EVENTS = 6
TEMPER = 4.0            # widening of the moment's likelihood for model error


# ----------------------------------------------------------------------------
# reading
# ----------------------------------------------------------------------------
def read_table(path):
    try:
        df = pd.read_csv(path, dtype=str, skipinitialspace=True,
                         encoding="utf-8-sig", keep_default_na=False)
    except Exception:
        return pd.DataFrame()
    df.columns = [str(c).strip().lower() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()
    return df


def num(df, col, default=np.nan):
    if col not in df.columns:
        return np.full(len(df), default, dtype=float)
    return pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)


def text(df, col):
    if col not in df.columns:
        return np.array([""] * len(df), dtype=object)
    return df[col].to_numpy(dtype=object)


def construction_coef(name):
    key = str(name).strip().lower().replace("×", "x").replace(" ", "")
    if key in COEF:
        return COEF[key]
    for k, v in COEF.items():
        if k in key:
            return v
    return COEF["6x36"]


# ----------------------------------------------------------------------------
# one crane
# ----------------------------------------------------------------------------
class Crane:
    def __init__(self, name, row, sheaves, moves, surveys):
        self.name = name
        self.n = float(row["falls"])
        self.H = float(row["upper_block_height_m"])
        self.mb = float(row["block_mass_t"])
        self.e = float(row["reeving_efficiency"])
        self.L = float(row["rope_length_m"])
        self.coef = construction_coef(row["rope_construction"])
        self.sheaves = sheaves      # list of (p, a, D, w)
        self.moves = moves          # dict of arrays, sorted by day
        self.surveys = surveys      # list of (day, stations, diameters), by day
        self.events = []

    # -- positions -----------------------------------------------------------
    def setup(self):
        L = self.L
        days = np.array([s[0] for s in self.surveys], dtype=float)
        self.days = days
        K = len(days)
        X = self.surveys[-1][1]
        self.X = X
        # positions where damage is reckoned: the stations and their mirror
        Q = np.unique(np.round(np.concatenate([X, L - X]), 6))
        self.Q = Q
        self.iX = np.clip(np.searchsorted(Q, np.round(X, 6)), 0, len(Q) - 1)
        self.iR = np.clip(np.searchsorted(Q, np.round(L - X, 6)), 0, len(Q) - 1)
        self.iQR = np.clip(np.searchsorted(Q, np.round(L - Q, 6)), 0, len(Q) - 1)
        # survey diameters at the positions Q (physical positions at the time
        # of that survey)
        F = np.empty((K, len(Q)))
        for k, (_, st, dm) in enumerate(self.surveys):
            F[k] = np.interp(Q, st, dm)
        self.F = F
        md = self.moves["day"]
        M = len(md)
        # survey whose diameters a movement uses (the first one before it)
        self.kk = np.clip(np.searchsorted(days, md, side="right") - 1, 0, K - 1)
        # slots: slot 0 = movements before survey 0, slot k = between survey
        # k-1 and k, slot K = after the last survey
        bnd = [int(np.searchsorted(md, t, side="left")) for t in days]
        self.rows = [(0, bnd[0])] + [(bnd[k - 1], bnd[k]) for k in range(1, K)] + [(bnd[-1], M)]
        start = min(float(md[0]), days[0]) if M else days[0]
        self.span = [(start, days[0])] + [(days[k - 1], days[k]) for k in range(1, K)]

    # -- damage of movements at positions Q -----------------------------------
    def contrib(self, rows, dsel):
        """Damage (w/N summed over sheaves) of the movements `rows` at the
        positions Q, with rope diameters dsel (len(rows) x len(Q))."""
        b0, b1, b2, b3 = self.coef
        mv = self.moves
        Q = self.Q
        out = np.zeros((len(rows), len(Q)))
        if len(rows) == 0 or not self.sheaves:
            return out
        S = (mv["load"][rows] + self.mb) * 1000.0 * G / (self.n * self.e)
        good = np.isfinite(S) & (S > 0)
        with np.errstate(all="ignore"):
            lgS = np.log10(np.where(good, S, 1.0))
            dsel = np.where(np.isfinite(dsel) & (dsel > 0), dsel, np.nan)
            lgd = np.log10(dsel)
        h1 = mv["h1"][rows]
        h2 = mv["h2"][rows]
        base = lgS[:, None] - 2.0 * lgd
        for (p, a, D, w) in self.sheaves:
            x1 = self.L - a - p * (self.H - h1)
            x2 = self.L - a - p * (self.H - h2)
            lo = np.minimum(x1, x2)
            hi = np.maximum(x1, x2)
            ok = good & (hi > lo)
            hit = (Q[None, :] >= lo[:, None]) & (Q[None, :] <= hi[:, None]) & ok[:, None]
            if not hit.any():
                continue
            lgDd = np.log10(D) - lgd
            lgN = b0 + (b1 + b3 * lgDd) * base + b2 * lgDd
            with np.errstate(all="ignore"):
                val = w * np.power(10.0, -lgN[hit])
            val[~np.isfinite(val)] = 0.0
            out[hit] += val
        return out

    def contrib_rows(self, rows, drow):
        """As contrib, with one diameter row drow (len(Q)) for all movements."""
        out = np.zeros((len(rows), len(self.Q)))
        for r0 in range(0, len(rows), CHUNK):
            rr = rows[r0:r0 + CHUNK]
            out[r0:r0 + len(rr)] = self.contrib(rr, np.repeat(drow[None, :], len(rr), 0))
        return out

    def positional(self):
        """P[i, q]: damage of movement i at position q, the diameter being the
        one surveyed at that position at the last survey before i."""
        M = len(self.moves["day"])
        P = np.zeros((M, len(self.Q)))
        for r0 in range(0, M, CHUNK):
            rows = np.arange(r0, min(M, r0 + CHUNK))
            P[rows] = self.contrib(rows, self.F[self.kk[rows]])
        self.P = P

    # -- reversals found from the surveys -------------------------------------
    def prepare_slots(self):
        """Per slot: total damage T and damage before each candidate moment."""
        md = self.moves["day"]
        K = len(self.days)
        self.T, self.Cc, self.tc = [], [], []
        for k in range(K):
            a, b = self.rows[k]
            Pk = self.P[a:b]
            t0, t1 = self.span[k]
            tc = np.linspace(t0, t1, N_CAND + 1)
            if b > a:
                C = np.vstack([np.zeros((1, Pk.shape[1])), np.cumsum(Pk, axis=0)])
                mc = np.searchsorted(md[a:b], tc, side="left")
                Cc = C[mc]
                T = C[-1]
            else:
                Cc = np.zeros((len(tc), len(self.Q)))
                T = np.zeros(len(self.Q))
            self.T.append(T)
            self.Cc.append(Cc)
            self.tc.append(tc)

    def _step(self, D, k, ev):
        """Damage state after slot k (D rows: hypotheses x positions)."""
        if ev is None:
            return D + self.T[k]
        W = ev @ self.Cc[k]                 # damage taken before the reversal
        return (D + W)[..., self.iQR] + self.T[k] - W

    def _ss(self, Zs, y, t, gamma):
        """Least squares y = d0 - alpha t - beta Z^gamma with beta >= 0 for a
        batch of hypotheses.  Zs: (H, Kobs, J); y: (Kobs, J); t: (Kobs,)."""
        H = Zs.shape[0]
        z = -np.power(np.maximum(Zs, 0.0), gamma).reshape(H, -1)
        yy = y.ravel()
        tt = np.repeat(t, y.shape[1])
        N = len(yy)
        # centre on the intercept, then two regressors -t and z
        ym = yy.mean()
        tm = tt.mean()
        yc = yy - ym
        tcn = -(tt - tm)
        zm = z.mean(axis=1, keepdims=True)
        zc = z - zm
        a11 = tcn @ tcn
        a12 = zc @ tcn
        a22 = np.einsum("ij,ij->i", zc, zc)
        b1 = tcn @ yc
        b2 = zc @ yc
        det = a11 * a22 - a12 ** 2
        with np.errstate(all="ignore"):
            c1 = np.where(det > 1e-18, (a22 * b1 - a12 * b2) / det, b1 / a11 if a11 > 0 else 0.0)
            c2 = np.where(det > 1e-18, (a11 * b2 - a12 * b1) / det, 0.0)
        syy = yc @ yc
        ss = syy - c1 * b1 - c2 * b2
        # beta >= 0: z enters with -beta, so c2 must be >= 0
        bad = ~np.isfinite(ss) | (c2 < 0)
        if np.any(bad):
            ss_t = syy - (b1 ** 2 / a11 if a11 > 0 else 0.0)
            ss = np.where(bad, ss_t, ss)
        return np.maximum(ss, 1e-12), N

    def _observe(self, start):
        F = self.F[start:, :][:, self.iX]
        return F, self.days[start:]

    def evaluate_slot(self, k, events, gamma, start):
        """SS for slot k without a reversal (index 0) and with one at each
        candidate moment (1..), the other slots as in `events`."""
        K = len(self.days)
        nQ = len(self.Q)
        D = self.D0.copy()
        states = []
        for s in range(start, K):
            if s == k:
                Hn = np.vstack([D[None, :] + self.T[s],
                                (D[None, :] + self.Cc[s])[:, self.iQR] + self.T[s] - self.Cc[s]])
                break
            D = self._step(D, s, events[s])
            states.append(D)
        Hn_states = [Hn]
        for s in range(k + 1, K):
            Hn = self._step(Hn, s, events[s])
            Hn_states.append(Hn)
        nh = Hn_states[0].shape[0]
        fixed = np.array(states).reshape(len(states), nQ) if states else np.zeros((0, nQ))
        Z = np.concatenate([np.repeat(fixed[None, :, :], nh, 0),
                            np.stack(Hn_states, axis=1)], axis=1)[:, :, self.iX]
        y, t = self._observe(start)
        return self._ss(Z, y, t, gamma)

    def evaluate(self, events, gamma, start):
        K = len(self.days)
        D = self.D0.copy()
        Z = []
        for s in range(start, K):
            D = self._step(D, s, events[s])
            Z.append(D[self.iX])
        y, t = self._observe(start)
        ss, N = self._ss(np.array(Z)[None, :, :], y, t, gamma)
        return float(ss[0]), N

    def proposals(self, start):
        """Slots after which a survey looks like its predecessor mirrored."""
        props = []
        n = len(self.X)
        for k in range(max(start, 1), len(self.days)):
            a = self.F[k - 1, self.iX] - self.F[k, self.iX]
            b = self.F[k - 1, self.iR] - self.F[k, self.iX]
            ssi = max(float(((a - a.mean()) ** 2).sum()), 1e-12)
            ssm = max(float(((b - b.mean()) ** 2).sum()), 1e-12)
            if ssm < 0.5 * ssi and n * np.log(ssi / ssm) > 8.0:
                props.append(k)
        return props

    def search(self, gamma, start, seed=()):
        """Search for the reversals under wear exponent gamma: start from the
        slots in `seed`, add reversals one at a time while they pay, then
        re-time each and drop those that no longer pay."""
        K = len(self.days)
        events = [None] * K
        p0 = 3
        slots = list(range(start, K))
        onehot = np.eye(N_CAND + 1)
        nev = 0
        for k in seed:
            if k in slots and nev < MAX_EVENTS:
                s, _ = self.evaluate_slot(k, events, gamma, start)
                events[k] = onehot[int(np.argmin(s[1:]))]
                nev += 1
        ss, N = self.evaluate(events, gamma, start)
        while nev < MAX_EVENTS:
            best = None
            for k in slots:
                if events[k] is not None:
                    continue
                s, _ = self.evaluate_slot(k, events, gamma, start)
                j = int(np.argmin(s[1:]))
                if best is None or s[1 + j] < best[0]:
                    best = (float(s[1 + j]), k, j)
            if best is None:
                break
            dof = max(N - p0 - 2 * (nev + 1), 1)
            var = best[0] / dof
            if (ss - best[0]) / var <= PEN:
                break
            events[best[1]] = onehot[best[2]]
            ss = best[0]
            nev += 1
        # re-time the reversals and drop, one at a time, the weakest of those
        # that no longer pay their way
        for _ in range(4 * MAX_EVENTS):
            changed = False
            weakest = None
            for k in [k for k in range(K) if events[k] is not None]:
                s, _ = self.evaluate_slot(k, events, gamma, start)
                j = int(np.argmin(s[1:]))
                var = s[1 + j] / max(N - p0 - 2 * nev, 1)
                stat = (s[0] - s[1 + j]) / var
                if stat <= PEN and (weakest is None or stat < weakest[0]):
                    weakest = (stat, k)
                if not np.array_equal(events[k], onehot[j]):
                    events[k] = onehot[j]
                    changed = True
            if weakest is not None:
                events[weakest[1]] = None
                nev -= 1
                changed = True
            if not changed:
                break
        ss, N = self.evaluate(events, gamma, start)
        return events, ss, N, nev

    def posterior(self, events, gamma, start):
        """Probabilities of the candidate moments of each reversal."""
        K = len(self.days)
        out = list(events)
        nev = sum(e is not None for e in events)
        for k in range(K):
            if events[k] is None:
                continue
            s, N = self.evaluate_slot(k, out, gamma, start)
            sr = s[1:]
            dof = max(N - 3 - 2 * nev, 1)
            var = sr.min() / dof
            ll = -(sr - sr.min()) / (2.0 * var * TEMPER)
            w = np.exp(ll)
            w[0] *= 0.5            # trapezoid weights of a uniform prior in time
            w[-1] *= 0.5
            out[k] = w / w.sum()
        return out

    def renewal_start(self):
        """Index of the survey after the last rope renewal, or 0."""
        start = 0
        for k in range(1, len(self.days)):
            d0X, d1X = self.F[k - 1, self.iX], self.F[k, self.iX]
            inc = d1X - d0X
            if (len(inc) >= 4 and np.median(inc) > 0.08 and np.mean(inc > 0) > 0.9
                    and np.std(d1X) < 0.035 and np.std(d0X) > np.std(d1X)):
                start = k
        return start

    def detect(self):
        K = len(self.days)
        self.start = self.renewal_start()
        self.prepare_slots()
        start = self.start
        # damage state at survey `start` (before slot start+1)
        if start == 0:
            self.D0 = np.zeros(len(self.Q))
            first = 0
        else:
            self.D0 = 0.5 * self.T[start]
            first = start + 1
        events = [None] * K
        if len(self.X) < 3 or K - start < 3:
            return events
        # D0 is the damage state before slot `first`; surveys first .. K-1
        # are fitted
        props = self.proposals(first)
        best = None
        for g in GAMMAS:
            for seed in ([(), props] if props else [()]):
                ev, ss, N, nev = self.search(g, first, seed)
                bic = N * np.log(ss / N) + (3 + 2 * nev) * np.log(N)
                if best is None or bic < best[0]:
                    best = (bic, g, ev)
        _, g, ev = best
        self.gamma = g
        return self.posterior(ev, g, first)

    # -- damage of the elements at the last survey's stations ----------------
    def assemble(self, events, start=0):
        K = len(self.days)
        md = self.moves["day"]
        nX = len(self.X)
        # orientation of the frame of survey k relative to the last survey's
        orient = np.ones(K, dtype=int)
        for k in range(K - 1, 0, -1):
            orient[k - 1] = -orient[k] if events[k] is not None else orient[k]

        def pos(o):
            return self.iX if o > 0 else self.iR

        dmg = np.zeros(nX)
        for k in range(K + 1):
            a, b = self.rows[k]
            if start > 0 and k < start:
                continue
            if b <= a:
                continue
            Pk = self.P[a:b]
            o_after = orient[min(k, K - 1)]
            if start > 0 and k == start:
                # renewal in this slot: only what the new rope took counts
                dn = self.contrib_rows(np.arange(a, b), self.F[k])
                dmg += 0.5 * dn.sum(axis=0)[pos(o_after)]
                continue
            ev = events[k] if k < K else None
            if ev is None:
                dmg += Pk.sum(axis=0)[pos(o_after)]
                continue
            t = md[a:b]
            tc = self.tc[k]
            # probability that the reversal came after each movement
            cdf = np.cumsum(ev)                       # P(t_r <= tc_m)
            m = np.searchsorted(tc, t, side="right") - 1
            pi = 1.0 - cdf[np.clip(m, 0, len(tc) - 1)]
            pi = np.clip(pi, 0.0, 1.0)
            o_before = -o_after
            rows = np.arange(a, b)
            # diameters: those of the survey a movement uses, measured where
            # the element was at that survey
            if k >= 1:      # survey k-1 came before the reversal
                Pb = Pk
                Pa = self.contrib_rows(rows, self.F[k - 1][self.iQR]) if np.any(pi < 1) else None
            else:           # slot 0: survey 0 came after the reversal
                Pb = self.contrib_rows(rows, self.F[0][self.iQR]) if np.any(pi > 0) else None
                Pa = Pk
            if Pb is not None:
                dmg += (pi @ Pb)[pos(o_before)]
            if Pa is not None:
                dmg += ((1.0 - pi) @ Pa)[pos(o_after)]
        return dmg

    def run(self):
        self.setup()
        self.positional()
        K = len(self.days)
        self.start = 0
        try:
            events = self.detect()
        except Exception as exc:
            sys.stderr.write(f"{self.name}: reversal search failed ({exc})\n")
            events = [None] * K
        self.events = events
        try:
            return self.assemble(events, self.start)
        except Exception as exc:
            sys.stderr.write(f"{self.name}: {exc}\n")
            return self.assemble([None] * K, 0)


# ----------------------------------------------------------------------------
# package
# ----------------------------------------------------------------------------
def load_package(wd):
    cr = read_table(f"{wd}/cranes.csv")
    sh = read_table(f"{wd}/sheaves.csv")
    mv = read_table(f"{wd}/movements.csv")
    sv = read_table(f"{wd}/surveys.csv")

    sh_crane = text(sh, "crane")
    sh_name = np.array([str(s).strip().lower() for s in text(sh, "sheave")], dtype=object)
    sh_p, sh_a = num(sh, "parts"), num(sh, "offset_m")
    sh_D, sh_w = num(sh, "diameter_mm"), num(sh, "bend_weight")

    mv_crane = text(mv, "crane")
    mv_day, mv_h1 = num(mv, "day"), num(mv, "from_height_m")
    mv_h2, mv_load = num(mv, "to_height_m"), num(mv, "hook_load_t")

    sv_crane = text(sv, "crane")
    sv_day, sv_st, sv_d = num(sv, "day"), num(sv, "station_m"), num(sv, "diameter_mm")

    cranes = []
    seen = set()
    for i in range(len(cr)):
        name = str(cr["crane"].iloc[i]) if "crane" in cr.columns else ""
        if name == "" or name in seen:
            continue
        seen.add(name)
        row = {}
        for col in ["falls", "upper_block_height_m", "block_mass_t",
                    "reeving_efficiency", "rope_length_m"]:
            row[col] = pd.to_numeric(cr[col].iloc[i], errors="coerce") if col in cr.columns else np.nan
        row["rope_construction"] = cr["rope_construction"].iloc[i] if "rope_construction" in cr.columns else ""

        # surveys -> list of (day, stations, diameters), merged per day
        m = (sv_crane == name) & np.isfinite(sv_day) & np.isfinite(sv_st) & np.isfinite(sv_d) & (sv_d > 0)
        surveys = []
        if m.any():
            df = pd.DataFrame({"day": sv_day[m], "st": np.round(sv_st[m], 6), "d": sv_d[m]})
            for dd, g in df.groupby("day", sort=True):
                gg = g.groupby("st", sort=True)["d"].mean()
                surveys.append((float(dd), gg.index.to_numpy(dtype=float), gg.to_numpy(dtype=float)))

        # sheaves and drum
        sheaves = []
        n = row["falls"]
        for j in np.nonzero(sh_crane == name)[0]:
            is_drum = sh_name[j] == "drum"
            p = sh_p[j]
            if not np.isfinite(p):
                p = n
            w = sh_w[j]
            if not np.isfinite(w) or w < 0:
                w = 0.5 if is_drum else 1.0
            a, D = sh_a[j], sh_D[j]
            if not (np.isfinite(p) and np.isfinite(a) and np.isfinite(D) and D > 0):
                continue
            sheaves.append((float(p), float(a), float(D), float(w)))

        # movements since the rope was put on, in order of time
        m = ((mv_crane == name) & np.isfinite(mv_day) & np.isfinite(mv_h1)
             & np.isfinite(mv_h2) & (mv_day >= 0))
        load = np.where(np.isfinite(mv_load), mv_load, 0.0)
        idx = np.nonzero(m)[0]
        order = idx[np.argsort(mv_day[idx], kind="mergesort")]
        moves = {"day": mv_day[order], "h1": mv_h1[order], "h2": mv_h2[order], "load": load[order]}
        cranes.append((name, row, sheaves, moves, surveys))
    return cranes


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: python3 ropes.py WORKS_DIR OUT_CSV\n")
        return 0
    wd, out = sys.argv[1], sys.argv[2]
    lines = ["row,damage"]
    try:
        cranes = load_package(wd)
    except Exception as exc:  # never fail the run
        sys.stderr.write(f"could not read package: {exc}\n")
        cranes = []
    for name, row, sheaves, moves, surveys in cranes:
        if not surveys:
            continue
        nst = len(surveys[-1][1])
        try:
            dmg = Crane(name, row, sheaves, moves, surveys).run()
        except Exception as exc:
            sys.stderr.write(f"{name}: {exc}\n")
            dmg = np.zeros(nst)
        dmg = np.where(np.isfinite(dmg), dmg, 0.0)
        for j in range(nst):
            lines.append(f"{name}-{j + 1:03d},{dmg[j]:.10f}")
    with open(out, "w") as f:
        f.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.stderr.write(f"error: {exc}\n")
    sys.exit(0)
