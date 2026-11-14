#!/usr/bin/env python3
"""Bending fatigue damage of crane hoist ropes to RS-4 (Issue 3).

Usage: python3 ropes.py WORKS_DIR OUT_CSV

For every crane of the works package the damage of the rope element at each
station of the rope's last survey is summed over all movements of the log
(RS-4 sections 1-5):

  * the point of touch of a sheave (or the drum) lies at
        x = L - a - p (H - h)
    from the drum anchorage, so a movement from h1 to h2 bends every element
    between x(h1) and x(h2) once over that sheave, with weight w;
  * a bending counts w / N with
        lg N = b0 + (b1 + b3 lg(D/d)) lg(S/d^2) + b2 lg(D/d),
        S = (m_h + m_b) g / (n e),
    d being the element's diameter as measured at the last survey on or
    before the movement.

The damage belongs to the rope *element*, and RS-4 measures positions from
the drum anchorage.  A rope can be turned end for end between two surveys;
then the element now at x lay at L - x before the turn.  The surveys show such
a turn: the worn part of the rope's diameter profile appears mirrored.  The
program finds turns, and the time of each turn inside its survey interval,
by fitting the survey diameters to the element damage histories (the rope
thins with its accumulated damage, d = c_k - A D^g, c_k a uniform loss of
survey k), and then reckons the damage element by element.

The damage at a station is evaluated exactly at the station's element, so no
discretisation of the rope is needed.
"""

import math
import os
import re
import sys
import time

import numpy as np
import pandas as pd

G = 9.80665
LN10 = math.log(10.0)

# RS-4 section 4: construction -> (b0, b1, b2, b3)
COEFFS = {
    "8x36": (-1.214, 0.887, 7.432, -2.103),
    "6x36": (-1.371, 0.934, 7.518, -2.146),
}

STATION_TOL = 1e-3        # m: two stations closer than this are one place
CHUNK_CELLS = 1_500_000   # movements x stations evaluated at a time

# turn detection
NB = 24                   # sub-intervals of a survey interval for the turn time
FLIP_GAIN = 0.05          # a turn must lower the rms misfit by 5 per cent
MAX_FLIPS = 6
ABNORMAL_RMS = 0.02       # mm: misfit beyond the caliper's repeatability
PAIR_SPAN = 3             # survey intervals apart, at most, of a turn and turn back
SEARCH_CPU = 2.5          # s of CPU time for the turn search of one rope
GEXP = np.arange(0.30, 1.2001, 0.05)   # exponents tried for the wear law


def log(msg):
    sys.stderr.write(msg + "\n")


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------
TEXT_COLS = ("crane", "sheave", "rope_construction")


def read_table(wd, name):
    path = os.path.join(wd, name)
    if not os.path.exists(path):
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig", skipinitialspace=True,
                     dtype={c: str for c in TEXT_COLS})
    df.columns = [str(c).strip().lower() for c in df.columns]
    for c in df.columns:
        if c in TEXT_COLS:
            s = df[c].astype("object")
            df[c] = s.where(s.isna(), s.astype(str).str.strip())
        elif not pd.api.types.is_numeric_dtype(df[c]):
            s = df[c].astype("object")
            s = s.where(s.isna(), s.astype(str).str.strip())
            df[c] = pd.to_numeric(s, errors="coerce")
    if "crane" in df.columns:
        df = df[df["crane"].notna() & (df["crane"] != "")]
    return df


def construction_key(text):
    t = str(text).strip().lower()
    nums = re.findall(r"\d+", t)
    if len(nums) >= 2:
        key = "%sx%s" % (nums[0], nums[1])
        if key in COEFFS:
            return key
    return t if t in COEFFS else None


# --------------------------------------------------------------------------
# surveys
# --------------------------------------------------------------------------
class Surveys:
    """The surveys of one rope, in order of time."""

    def __init__(self, sv):
        sv = sv[sv["day"].notna() & sv["station_m"].notna()]
        self.days = np.sort(sv["day"].unique()) if not sv.empty else np.zeros(0)
        self.xs, self.ds = [], []
        keep_days = []
        for dday in self.days:
            g = sv[(sv["day"] == dday) & sv["diameter_mm"].notna()
                   & (sv["diameter_mm"] > 0)]
            if g.empty:
                continue
            gg = g.groupby("station_m")["diameter_mm"].mean().sort_index()
            keep_days.append(dday)
            self.xs.append(gg.index.values.astype(float))
            self.ds.append(gg.values.astype(float))
        last_day = self.days[-1] if self.days.size else None
        self.days = np.array(keep_days, dtype=float)
        # stations of the rope's last survey (measured or not)
        if last_day is not None:
            st = np.sort(sv.loc[sv["day"] == last_day, "station_m"].unique())
            if st.size > 1:
                st = st[np.concatenate(([True], np.diff(st) > STATION_TOL))]
            self.stations = st.astype(float)
        else:
            self.stations = np.zeros(0)

    @property
    def K(self):
        return self.days.size

    def at(self, k, pos):
        """Diameters measured at survey k at positions pos (interpolated)."""
        xs, ds = self.xs[k], self.ds[k]
        if xs.size == 1:
            return np.full(np.shape(pos), ds[0])
        return np.interp(pos, xs, ds)


# --------------------------------------------------------------------------
# turn detection
# --------------------------------------------------------------------------
def wear_misfit(E, D, gset=None):
    """Least-squares misfit of E[h,k,j] = c_hk - A_h D[h,k,j]^g, A_h >= 0,
    for a batch of hypotheses h.  Returns the smallest sum of squares over the
    exponents GEXP, one value per hypothesis."""
    Ed = E - E.mean(axis=2, keepdims=True)
    see = np.einsum("hkj,hkj->h", Ed, Ed)
    best = see.copy()
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        lnD = np.log(np.maximum(D, 1e-300))
        zero = D <= 0
        for g in (GEXP if gset is None else gset):
            Q = np.exp(g * lnD)
            Q[zero] = 0.0
            Qd = Q - Q.mean(axis=2, keepdims=True)
            sqq = np.einsum("hkj,hkj->h", Qd, Qd)
            seq = np.einsum("hkj,hkj->h", Ed, Qd)
            ok = (sqq > 0) & (seq < 0)       # the rope thins with damage
            sse = np.where(ok, see - seq * seq / np.where(ok, sqq, 1.0), see)
            best = np.minimum(best, sse)
    return best


class TurnModel:
    """Damage increments by position in sub-intervals of the survey intervals,
    for the stations and their mirror positions."""

    def __init__(self, sur, L, mov, sheaves, coeffs):
        self.ok = False
        K = sur.K
        X = sur.stations
        J = X.size
        if K < 2 or J < 4:
            return
        t, u, h1, h2, kidx = mov
        b0, b1, b2, b3 = coeffs
        grid = np.unique(np.round(np.concatenate([X, L - X]), 6))
        iid = np.searchsorted(grid, np.round(X, 6))
        irev = np.searchsorted(grid, np.round(L - X, 6))
        Vpos = np.array([sur.at(k, grid) for k in range(K)])
        nb = (K - 1) * NB
        R = np.zeros((nb, grid.size))
        sel = kidx <= K - 2
        if not sel.any():
            return
        days = sur.days
        for k in range(K - 1):
            m = np.nonzero(kidx == k)[0]
            if m.size == 0:
                continue
            span = days[k + 1] - days[k]
            if span > 0:
                frac = (t[m] - days[k]) / span
            else:
                frac = np.zeros(m.size)
            sub = np.clip(np.floor(frac * NB).astype(int), 0, NB - 1)
            gb = k * NB + sub
            starts = np.concatenate(([0], np.nonzero(np.diff(gb))[0] + 1))
            rows = gb[starts]
            lgd = np.log10(Vpos[k])
            acc = np.zeros((m.size, grid.size))
            for p, a, D, w in sheaves:
                lD = math.log10(D) - lgd
                beta = b1 + b3 * lD
                alpha = b0 + b2 * lD - 2.0 * lgd * beta
                base = L - a - p * sheaves.H
                x1 = base + p * h1[m]
                x2 = base + p * h2[m]
                lo = np.minimum(x1, x2)[:, None]
                hi = np.maximum(x1, x2)[:, None]
                hit = (grid[None, :] >= lo) & (grid[None, :] <= hi)
                E = alpha[None, :] + np.outer(u[m], beta)
                acc += np.where(hit, w * np.exp(-LN10 * E), 0.0)
            R[rows] += np.add.reduceat(acc, starts, axis=0)
        self.K, self.J = K, J
        zero = np.zeros((1, J))
        self.Pid = np.vstack([zero, np.cumsum(R[:, iid], axis=0)])
        self.Prev = np.vstack([zero, np.cumsum(R[:, irev], axis=0)])
        self.Vid = Vpos[:, iid]
        self.Vrev = Vpos[:, irev]
        self.nb = nb
        self.survey_bin = np.arange(K) * NB
        self.n_obs = K * J
        self.gset = None
        self.ok = True

    def sse_batch(self, hyps):
        """Misfit of the surveys for each hypothesis, a hypothesis being a
        list of turns [(interval k, edge i)]."""
        H = len(hyps)
        K, J = self.K, self.J
        D = np.zeros((H, K, J))
        os_ = np.ones((H, K), dtype=bool)
        sb = self.survey_bin                       # bin index of survey k
        ks = np.arange(K)
        for h, flips in enumerate(hyps):
            gs = sorted(kf * NB + i for kf, i in flips)
            F = len(gs)
            edges = [0] + gs + [self.nb]
            for s in range(F + 1):
                a, b = edges[s], edges[s + 1]
                if b <= a:
                    continue
                P = self.Pid if (F - s) % 2 == 0 else self.Prev
                lo = np.minimum(a, sb)
                hi = np.minimum(b, sb)
                D[h] += P[hi] - P[lo]
            for kf, _ in flips:
                os_[h] ^= kf >= ks
        E = np.where(os_[:, :, None], self.Vid[None], self.Vrev[None])
        return wear_misfit(E, D, self.gset)

    def best_exponent(self, flips):
        """Exponent of the wear law that fits a hypothesis best."""
        vals = [float(self.sse_batch_g([flips], (g,))[0]) for g in GEXP]
        return float(GEXP[int(np.argmin(vals))])

    def sse_batch_g(self, hyps, gset):
        keep = self.gset
        self.gset = gset
        try:
            return self.sse_batch(hyps)
        finally:
            self.gset = keep

    def sse(self, flips):
        return float(self.sse_batch([flips])[0])

    def rms(self, sse):
        return math.sqrt(max(sse, 0.0) / self.n_obs)


def find_turns(model, name):
    """Search for turns end for end.  Returns [(k, f)]: a turn at
    days[k] + f (days[k+1] - days[k]), f in [0, 1]."""
    if not model.ok:
        return []
    K1 = model.K - 1
    model.gset = None
    base = model.sse([])
    base_rms = model.rms(base)

    def set_g(flips):
        # search with the exponents next to the one that fits best now
        g = model.best_exponent(flips)
        model.gset = tuple(x for x in (g - 0.05, g, g + 0.05)
                           if GEXP[0] - 1e-9 <= x <= GEXP[-1] + 1e-9)
        return model.sse(flips)

    def better(s, ref):
        return model.rms(s) < model.rms(ref) * (1.0 - FLIP_GAIN)

    def best_single(fixed):
        used = {kf for kf, _ in fixed}
        best = (np.inf, None)
        for kf in range(K1):
            if kf in used:
                continue
            ss = model.sse_batch([fixed + [(kf, i)] for i in range(NB + 1)])
            i = int(np.argmin(ss))
            if ss[i] < best[0]:
                best = (float(ss[i]), (kf, i))
        return best

    def best_pair(fixed):
        used = {kf for kf, _ in fixed}
        free = [kf for kf in range(K1) if kf not in used]
        coarse = (0, NB // 2, NB)
        best = (np.inf, None)
        for a_, k1 in enumerate(free):
            hyps = [[(k1, i1), (k2, i2)] for k2 in free[a_ + 1:]
                    if k2 - k1 <= PAIR_SPAN
                    for i1 in coarse for i2 in coarse]
            if not hyps:
                continue
            ss = model.sse_batch([fixed + h for h in hyps])
            n = int(np.argmin(ss))
            if ss[n] < best[0]:
                best = (float(ss[n]), hyps[n])
        return best

    def refine(flips, cur):
        for _ in range(6):
            if time.process_time() > t_end:
                break
            changed = False
            # drop a turn that no longer earns its place
            for n in range(len(flips)):
                others = flips[:n] + flips[n + 1:]
                s = model.sse(others)
                if not better(cur, s):
                    flips, cur, changed = others, s, True
                    break
            if changed:
                continue
            # move each turn to its best place, the others fixed
            for n in range(len(flips)):
                others = flips[:n] + flips[n + 1:]
                s, f = best_single(others)
                if f is not None and s < cur * (1.0 - 1e-9) and f != flips[n]:
                    flips = others + [f]
                    cur, changed = s, True
            if not changed:
                break
        return flips, cur

    t_end = time.process_time() + SEARCH_CPU
    flips = []
    cur = set_g(flips)
    while len(flips) < MAX_FLIPS and time.process_time() < t_end:
        s, f = best_single(flips)
        add = None
        if f is not None and better(s, cur):
            add = ([f], s)
        elif model.rms(cur) > ABNORMAL_RMS and len(flips) + 2 <= MAX_FLIPS:
            # a rope turned and turned back: no single turn fits, try pairs
            s, ff = best_pair(flips)
            if ff is not None and better(s, cur):
                add = (ff, s)
        if add is None:
            break
        flips, cur = refine(flips + add[0], add[1])
        cur = set_g(flips)
        flips, cur = refine(flips, cur)
    model.gset = None
    if not flips:
        log("%s: no turn found (rms misfit %.4f mm)" % (name, base_rms))
        return []
    cur = model.sse(flips)
    out = []
    for n, (kf, i) in enumerate(flips):
        others = flips[:n] + flips[n + 1:]
        f = float(i)
        if 0 < i < NB:
            sm = model.sse(others + [(kf, i - 1)])
            s0 = model.sse(others + [(kf, i)])
            sp = model.sse(others + [(kf, i + 1)])
            den = sm - 2.0 * s0 + sp
            if den > 0:
                f = i + max(-0.5, min(0.5, 0.5 * (sm - sp) / den))
        out.append((kf, f / NB))
    out.sort()
    log("%s: rms misfit %.4f mm without turns, %.4f mm with %d turn(s) %s"
        % (name, base_rms, model.rms(cur), len(out),
           ", ".join("in survey interval %d at fraction %.2f" % (k, f)
                     for k, f in out)))
    return out


# --------------------------------------------------------------------------
# damage of one crane
# --------------------------------------------------------------------------
class Sheaves(list):
    pass


def crane_damage(name, cr, shv, mv, sur):
    X = sur.stations
    J = X.size
    dmg = np.zeros(J)
    if J == 0 or sur.K == 0 or mv is None or mv.empty or shv is None or shv.empty:
        return dmg

    key = construction_key(cr.get("rope_construction"))
    if key is None:
        log("%s: unknown rope construction %r, 6x36 taken"
            % (name, cr.get("rope_construction")))
        key = "6x36"
    coeffs = COEFFS[key]
    b0, b1, b2, b3 = coeffs

    n = float(cr["falls"])
    H = float(cr["upper_block_height_m"])
    mb = float(cr["block_mass_t"])
    e = float(cr["reeving_efficiency"])
    L = float(cr["rope_length_m"])

    mv = mv[mv["day"].notna() & mv["from_height_m"].notna()
            & mv["to_height_m"].notna()]
    mv = mv[mv["day"] >= 0.0]           # bendings since the rope was put on
    if mv.empty:
        return dmg
    mv = mv.sort_values("day", kind="stable")
    t = mv["day"].values.astype(float)
    h1 = mv["from_height_m"].values.astype(float)
    h2 = mv["to_height_m"].values.astype(float)
    mh = mv["hook_load_t"].fillna(0.0).values.astype(float)
    S = (mh + mb) * 1000.0 * G / (n * e)
    good = (S > 0) & np.isfinite(S) & (h1 != h2)
    t, h1, h2, S = t[good], h1[good], h2[good], S[good]
    if t.size == 0:
        return dmg
    u = np.log10(S)

    days = sur.days
    K = days.size
    kidx = np.clip(np.searchsorted(days, t, side="right") - 1, 0, K - 1)

    sp = shv["parts"].values.astype(float)
    sa = shv["offset_m"].values.astype(float)
    sD = shv["diameter_mm"].values.astype(float)
    sw = shv["bend_weight"].fillna(1.0).values.astype(float)
    ok = np.isfinite(sp) & np.isfinite(sa) & np.isfinite(sD) & (sD > 0)
    sheaves = Sheaves((p, a, D, w) for p, a, D, w in
                      zip(sp[ok], sa[ok], sD[ok], sw[ok]) if p != 0 and w != 0)
    sheaves.H = H
    if not sheaves:
        return dmg

    # ---- turns end for end
    turns = []
    try:
        model = TurnModel(sur, L, (t, u, h1, h2, kidx), sheaves, coeffs)
        turns = find_turns(model, name)
    except Exception as exc:  # pragma: no cover
        log("%s: turn search failed: %r" % (name, exc))
        turns = []
    taus = []
    for k, f in turns:
        taus.append((k, days[k] + f * (days[k + 1] - days[k])))

    # orientation of each survey relative to the end of the log
    # (+1: the element at x lies at x, -1: at L - x)
    s_or = np.ones(K)
    for k, _ in taus:
        s_or[: k + 1] *= -1.0          # surveys 0..k saw the rope before the turn
    # orientation of each movement
    m_or = np.ones(t.size)
    for k, tau in taus:
        m_or[t < tau] *= -1.0

    # element diameters as measured at each survey
    E = np.array([sur.at(k, X if s_or[k] > 0 else L - X) for k in range(K)])

    rows = max(1, CHUNK_CELLS // max(J, 1))
    order_breaks = np.nonzero((np.diff(kidx) != 0) | (np.diff(m_or) != 0))[0] + 1
    seg_starts = np.concatenate(([0], order_breaks))
    seg_ends = np.concatenate((order_breaks, [t.size]))
    for s0, s1 in zip(seg_starts, seg_ends):
        k = kidx[s0]
        pos = X if m_or[s0] > 0 else L - X
        xs = pos[None, :]
        lgd = np.log10(E[k])
        for p, a, D, w in sheaves:
            lD = math.log10(D) - lgd
            beta = b1 + b3 * lD
            alpha = b0 + b2 * lD - 2.0 * lgd * beta
            base = L - a - p * H
            for c0 in range(s0, s1, rows):
                c1 = min(s1, c0 + rows)
                x1 = base + p * h1[c0:c1]
                x2 = base + p * h2[c0:c1]
                lo = np.minimum(x1, x2)[:, None]
                hi = np.maximum(x1, x2)[:, None]
                hit = (xs >= lo) & (xs <= hi)
                if not hit.any():
                    continue
                Ex = alpha[None, :] + np.outer(u[c0:c1], beta)
                dmg += w * np.where(hit, np.exp(-LN10 * Ex), 0.0).sum(axis=0)
    return dmg


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def fmt(v):
    if not np.isfinite(v):
        v = 0.0
    return "%.12f" % v


def main(argv):
    if len(argv) < 3:
        log("usage: ropes.py WORKS_DIR OUT_CSV")
        return 0
    wd, out = argv[1], argv[2]
    rows = []
    try:
        cranes = read_table(wd, "cranes.csv")
        sheaves = read_table(wd, "sheaves.csv")
        moves = read_table(wd, "movements.csv")
        surveys = read_table(wd, "surveys.csv")

        crane_names = []
        if "crane" in cranes.columns:
            for c in cranes["crane"]:
                if c not in crane_names:
                    crane_names.append(c)
        extra = []
        if "crane" in surveys.columns:
            for c in surveys["crane"].unique():
                if c not in crane_names and c not in extra:
                    extra.append(c)

        def groups(df):
            if "crane" not in df.columns:
                return {}
            return {k: g for k, g in df.groupby("crane", sort=False)}

        sv_groups = groups(surveys)
        mv_groups = groups(moves)
        sh_groups = groups(sheaves)

        for name in crane_names + extra:
            sv = sv_groups.get(name)
            if sv is None or sv.empty:
                continue
            try:
                sur = Surveys(sv)
            except Exception as exc:  # pragma: no cover
                log("surveys of %s: %r" % (name, exc))
                continue
            stations = sur.stations
            dmg = np.zeros(stations.size)
            if name in crane_names:
                try:
                    cr = cranes[cranes["crane"] == name].iloc[0]
                    dmg = crane_damage(name, cr, sh_groups.get(name),
                                       mv_groups.get(name), sur)
                except Exception as exc:  # pragma: no cover
                    log("crane %s: %r" % (name, exc))
            width = max(3, len(str(stations.size)))
            for j in range(stations.size):
                rows.append(("%s-%0*d" % (name, width, j + 1), dmg[j]))
    except Exception as exc:  # pragma: no cover
        log("error: %r" % (exc,))

    d = os.path.dirname(os.path.abspath(out))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(out, "w", newline="") as f:
        f.write("row,damage\n")
        for r, v in rows:
            f.write("%s,%s\n" % (r, fmt(v)))
    return 0


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as exc:  # pragma: no cover
        log("fatal: %r" % (exc,))
    sys.exit(0)
