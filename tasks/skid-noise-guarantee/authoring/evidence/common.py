"""Shared machinery for the evidence scripts: an in-process copy of the booked instrument (the same readings as
environment/rig/lab.py for the same seed and reading order), the reference's model with switches for the routes, and
grading against the sealed definition.
"""
import json
import math
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
sys.path.insert(0, os.path.join(ROOT, "solution"))
import isim as S  # noqa: E402
import solve  # noqa: E402

DATA = os.path.join(ROOT, "environment", "data")
SEED = json.load(open(os.path.join(ROOT, "authoring", "provenance", "seed.json")))["seed"]
SEEDS = list(range(7101, 7121))
IDS = list(S.MACHINES)
KEYS = [S.LABEL[b] for b in S.BANDS] + ["A"]
LABEL = [S.LABEL[b] for b in S.BANDS]


def e(x):
    return 10.0 ** (0.1 * x)


def db(x):
    return 10.0 * math.log10(x)


class Lab:
    """the instrument of environment/rig/lab.py, in process"""

    def __init__(self, seed=SEED):
        self.seed, self.n, self.log = seed, 0, []

    def _rng(self, cmd, pid, state):
        return np.random.default_rng([self.seed, self.n, 3, ("slm", "rt").index(cmd), list(S.POS).index(pid),
                                      list(S.STATES).index(state)])

    def slm(self, pid, state):
        self.n += 1
        if self.n > S.BUDGET:
            raise RuntimeError("over the booking")
        v = S.lab_slm(pid, state, self._rng("slm", pid, state))
        self.log.append(("slm", pid, state))
        return dict(zip(LABEL, v))

    def rt(self, pid):
        self.n += 1
        if self.n > S.BUDGET:
            raise RuntimeError("over the booking")
        v = S.lab_rt(pid, self._rng("rt", pid, "off"))
        self.log.append(("rt", pid, "-"))
        return dict(zip(LABEL, v))


class Agent(solve.Model):
    """the reference model with switches"""

    def __init__(self, C, M, P, BG, changed, t60=None, surface="standard", meter="row", background="position",
                 drop="standard", average="energy", k2=True, speed="50", drop_extra=(), rss_bg="first"):
        super().__init__(C, M, P, BG, changed, t60)
        self.mode_surface, self.meter, self.background = surface, meter, background
        self.drop, self.average, self.use_k2, self.speed = drop, average, k2, speed
        self.drop_extra = set(drop_extra)
        self.rss_bg = rss_bg

    def surface(self, m):
        """the nominal radius route takes the radius from the register but still uses the positions as recorded"""
        r = self.M[m]["nominal_r"] if self.mode_surface == "nominal" else self.array_radius(m)
        half = True if self.mode_surface == "half" else self.M[m]["wall"] >= self.C["clear"]
        return (2.0 * math.pi if half else math.pi) * r * r

    def corrected(self, level, pid):
        """row: the certificate of the instrument that read the position; m2 or m9: that one's for every row;
        none: no correction at all"""
        if self.meter == "none":
            return {k: level[k] for k in LABEL}
        if self.meter in ("m2", "m9"):
            c = self.C["cert"]["M-%s" % self.meter[1]]
            return {k: level[k] + c[k] for k in LABEL}
        return super().corrected(level, pid)

    def machine_only(self, m, p):
        on = self.corrected(self.M[m]["survey"][p], p)
        if self.background == "none":
            return on
        if self.background == "average":   # the mean background of the valid positions, not the position's own
            pos = self.valid(m)
            off = {k: db(sum(e(self.corrected(self.BG[q], q)[k]) for q in pos) / len(pos)) for k in LABEL}
        else:
            q = self.M[m]["pos"][0] if self.background == "first" else p
            off = self.corrected(self.BG[q], q)
        return {k: db(max(e(on[k]) - e(off[k]), 1e-12)) for k in LABEL}

    def valid(self, m):
        if self.drop == "all":
            out = list(self.M[m]["pos"])
        elif self.drop == "radius":        # the radius rule only, not the background rule
            out = [p for p in self.M[m]["pos"] if abs(self.P[p]["r"] - self.array_radius(m)) < 1e-9]
        elif self.drop == "background":    # the background rule only, not the radius rule
            out = []
            for p in self.M[m]["pos"]:
                on, off = self.corrected(self.M[m]["survey"][p], p), self.corrected(self.BG[p], p)
                if min(on[k] - off[k] for k in LABEL) >= self.C["margin"]:
                    out.append(p)
        else:
            out = super().valid(m)
        return [p for p in out if p not in self.drop_extra] or out

    def absorption(self):
        """the room check, with the hall's background taken from the position rss_bg, or the mean of the quiet
        positions when rss_bg is "mean" """
        if self.rss_bg == "first":
            return super().absorption()
        rss = self.C["rss"]
        quiet = [p for p in self.BG if p not in ("P19", "P20", "P68", "P69")]
        if self.rss_bg == "mean":
            off = {k: db(sum(e(self.corrected(self.BG[q], q)[k]) for q in quiet) / len(quiet)) for k in LABEL}
        else:
            off = self.corrected(self.BG[self.rss_bg], self.rss_bg)
        s = 2.0 * math.pi * self.C["rss_r"] ** 2
        out = {}
        for k in LABEL:
            vals = [db(max(e(self.corrected(rss[p], p)[k]) - e(off[k]), 1e-12)) for p in rss]
            lp = db(sum(e(v) for v in vals) / len(vals))
            out[k] = 4.0 / (e(lp - self.C["rss_lw"][k]) - 1.0 / s)
        return out

    def k2(self, m, k):
        if self.use_k2 == "nofour":          # the 4 of 4 S / A dropped
            return db(1.0 + self.surface(m) / self.area(k))
        return super().k2(m, k) if self.use_k2 else 0.0

    def lw(self, m):
        pos = self.valid(m)
        s = self.surface(m)
        out = {}
        for k in LABEL:
            vals = [self.machine_only(m, p)[k] for p in pos]
            lp = db(sum(e(v) for v in vals) / len(vals)) if self.average == "energy" else sum(vals) / len(vals)
            out[k] = lp + db(s) - self.k2(m, k)
        if self.M[m]["speed"] != self.M[m]["rated"] and self.speed != "none":
            n = {"50": 50.0, "20": 20.0, "sign": -50.0}[self.speed]
            r = n * math.log10(self.M[m]["rated"] / self.M[m]["speed"])
            out = {k: v + r for k, v in out.items()}
        if m in self.delta:
            out = {k: v + self.delta[m][k] for k, v in out.items()}
        return out


def relabel(M, P):
    """the machines' rows taken from the survey sheet's own machine column instead of the position table"""
    for m in M:
        M[m]["survey"], M[m]["pos"], speeds = {}, [], []
        for r in solve.rows(DATA, "survey_levels.csv"):
            if r["machine"] != m:
                continue
            M[m]["survey"][r["position"]] = {k: float(r["lp_%s" % k]) for k in LABEL}
            M[m]["pos"].append(r["position"])
            speeds.append(float(r["speed_rpm"]))
        M[m]["speed"] = max(set(speeds), key=speeds.count)


def solve_route(seed=SEED, absorption="rss", rt_pos=None, deltas=("C1", "C3", "C7"), delta_mode="band",
                delta_pos=None, waste=None, labels="position", certified=True, **kw):
    """one route: returns ({machine: {key: dB}}, the readings used)

    absorption: how the hall's equivalent absorption area is found: "rss" (the survey's own room check, which
                costs no reading), "rt" (a reverberation reading, which costs one of the three), "report" (the
                acoustic report's reverberation time), "rt-mid" (a reading, its 1 kHz value for every band),
                "rt-inverse" (a reading, the relation turned over)
    deltas:     the machines whose configuration difference is measured, in order
    delta_mode: "band" (per band), "dba" (one A-weighted figure for every band), "none"
    certified:  True takes the difference of the machine whose register note certifies it from that note, which
                costs no reading; False measures it like the others, which the booking cannot pay for
    waste:      a reading spent on something else first, e.g. ("slm", "P9", "c2")
    """
    C, M, P, BG, changed = solve.load(DATA)
    if labels == "sheet":
        relabel(M, P)
    A = Agent(C, M, P, BG, changed, **kw)
    lab = Lab(seed)
    if waste:
        getattr(lab, waste[0])(*waste[1:])
    if absorption == "report":
        rep = solve.text(DATA, "docs/room_report.md")
        A.t60 = dict(zip(LABEL, solve.band_row(rep, "T (s)")))
    elif absorption != "rss":
        A.t60 = lab.rt(rt_pos or M["C1"]["pos"][0])
        if absorption == "rt-mid":
            A.t60 = {k: A.t60["1k"] for k in LABEL}
        elif absorption == "rt-inverse":      # A = 0.161 V T, the relation turned over
            A.t60 = {k: 1.0 / v for k, v in A.t60.items()}
    if delta_mode != "none":
        for m in deltas:
            if certified and M[m]["certified"]:
                A.delta[m] = M[m]["certified"]
                continue
            want = delta_pos.get(m) if isinstance(delta_pos, dict) else delta_pos
            p = want or A.valid(m)[0]
            try:
                now = lab.slm(p, m.lower())
            except RuntimeError:
                continue
            then = A.machine_only(m, p)
            d = {k: db(max(e(now[k]) - e(A.corrected(BG[p], p)[k]), 1e-12)) - then[k] for k in LABEL}
            if delta_mode == "dba":
                aw = C["aw"]
                da = db(sum(e(then[k] + d[k] + aw[k]) for k in LABEL)) - db(sum(e(then[k] + aw[k]) for k in LABEL))
                d = {k: da for k in LABEL}
            elif delta_mode == "sign":
                d = {k: -v for k, v in d.items()}
            A.delta[m] = d
    sheet = {}
    for m in IDS:
        lw = A.lw(m)
        sheet[m] = dict(lw)
        sheet[m]["A"] = A.lwa(lw)
    return sheet, lab.log


def grade(sheet):
    """(values right, {machine: {key: error}}, (worst machine, worst key, worst error))"""
    truth = S.truth()
    err = {m: {k: sheet[m][k] - truth[m][k] for k in KEYS} for m in IDS}
    n = sum(abs(err[m][k]) <= S.TOL for m in IDS for k in KEYS)
    wm = max(IDS, key=lambda m: max(abs(v) for v in err[m].values()))
    wk = max(KEYS, key=lambda k: abs(err[wm][k]))
    return n, err, (wm, wk, err[wm][wk])


def worst(err):
    return max(abs(err[m][k]) for m in IDS for k in KEYS)


def failed_items(err):
    return [(m, k) for m in IDS for k in KEYS if abs(err[m][k]) > S.TOL]
