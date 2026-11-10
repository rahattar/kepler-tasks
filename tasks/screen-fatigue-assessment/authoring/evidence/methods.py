"""Record-level helpers for the evidence studies: hot-spot stress with the record corrections (each switchable), the
two-mode suspension fit and coast-down simulation, S9's 2024 fill. The sealed module is imported for its rainflow
and S-N helpers and to score. plans.py assembles estimates from these."""
import os
import sys
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "provenance"))
import screens as S

DATA = os.path.join(HERE, "..", "..", "environment", "data")
IDX = pd.read_csv(os.path.join(DATA, "records", "index.csv"))
LOG = pd.read_csv(os.path.join(DATA, "operating_log.csv"))
REG = pd.read_csv(os.path.join(DATA, "screen_register.csv")).set_index("screen")
REC = {r: pd.read_csv(os.path.join(DATA, f)) for r, f in zip(IDX.record, IDX.file)}
E = 207000.0


def hotspot(u, rid, o):
    d = REC[rid]
    e1, e2 = d.ch1_ue.values.astype(float), d.ch2_ue.values.astype(float)
    if u == "S7" and o["swap"]:
        e1, e2 = e2, e1
    if u == "S4" and o["gf"]:
        e1, e2 = e1 * 2.00 / 2.12, e2 * 2.00 / 2.12
    p1, p2 = (0.5, 1.5) if (u == "S2" and o["pos"]) else (0.4, 1.0)
    if u == "S9" and o["s9debond"]:
        when = pd.Timestamp(IDX.set_index("record").loc[rid, "start"])
        if when >= pd.Timestamp("2026-07-20"):
            e1 = e1 * o["r9_fix"]
    if u == "S1" and o["debond"] != "none":
        when = pd.Timestamp(IDX.set_index("record").loc[rid, "start"])
        if when >= pd.Timestamp(o["debond_from"]):
            if o["debond"] == "g1only":       # G1 alone with the pre-damage gradient ratio
                return e1 * (p2 - p1 * o["r_pre"]) / (p2 - p1) * E * 1e-6
            e2 = e2 * o["r_fix"]
    return (p2 * e1 - p1 * e2) / (p2 - p1) * E * 1e-6


def ratio_s1(o, u="S1"):
    """G2/G1 amplitude ratio on a screen's steady records before and after the change."""
    rows = IDX[(IDX.screen == u) & IDX.kind.isin(["loaded", "empty"])]
    pre, post = [], []
    for rid, st in zip(rows.record, rows.start):
        d = REC[rid]
        r = np.ptp(d.ch2_ue.values) / np.ptp(d.ch1_ue.values)
        (pre if pd.Timestamp(st) < pd.Timestamp(o["debond_from"]) else post).append(r)
    return float(np.median(pre)), float(np.median(post))


def fat(u, o):
    f = 100.0 if (u == "S5" and o["fat5"]) else 90.0
    t = 32.0 if (u == "S9" and o["thick"]) else 20.0
    return f * ((25.0 / t) ** 0.3 if t > 25 else 1.0)


def s9_fill(L):
    import re
    txt = open(os.path.join(DATA, "docs", "s9_production_2024.md")).read()
    rows = re.findall(r"\| (2024-\d\d) \| (\d+) \| (\d+) \| (\d+) \|", txt)
    loaded_cols = S.BAND_COLS[1:]
    frac = L[loaded_cols].sum() / L[loaded_cols].sum().sum()
    out = []
    for mth, run, emp, st in rows:
        ld = float(run) - float(emp)
        d = dict(screen="S9", date=mth + "-15", h_empty=float(emp), starts=float(st))
        d.update({c: ld * float(frac[c]) for c in loaded_cols})
        out.append(d)
    return pd.DataFrame(out)


def grade(est):
    res = S.grade(est)
    worst = max(res, key=lambda u: abs(res[u][0]))
    return abs(res[worst][0]), worst, sorted(u for u in res if not res[u][1]), res


# ---- coast-downs before the brakes: identify the suspension from the braked stops' ring-down, simulate the coast


def ringdown(s, fs):
    """Fit C exp(-a t) sin(wd t + p) + m to the free decay after the resonance peak."""
    from scipy.optimize import curve_fit
    env = np.abs(s - np.median(s))
    k = int(np.argmax(env))
    seg = s[k + int(1.5 * fs):]
    t = np.arange(seg.size) / fs
    spec = np.abs(np.fft.rfft(seg - seg.mean()))
    fr = np.fft.rfftfreq(seg.size, 1 / fs)
    f0 = fr[np.argmax(spec * (fr < 8))]
    def mdl(t, C, a, wd, p, m):
        return C * np.exp(-a * t) * np.sin(wd * t + p) + m
    best = None
    for p0 in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        try:
            par, _ = curve_fit(mdl, t, seg, p0=[np.ptp(seg[:int(fs)]) / 2, 0.5, 2 * np.pi * f0, p0, 0.0], maxfev=20000)
        except Exception:
            continue
        r = np.sum((mdl(t, *par) - seg) ** 2)
        if best is None or r < best[0]:
            best = (r, par)
    C, a, wd, p, m = best[1]
    wn = np.hypot(a, wd)
    return wn / (2 * np.pi), a / wn


def coast_damage(fr, zeta, tau, f_op, R_e, fa, fs=1000.0, n=8, method="sdof"):
    from scipy.signal import cont2discrete, lfilter
    wn, wop = 2 * np.pi * fr, 2 * np.pi * f_op
    Xop = wop ** 2 / np.hypot(wn ** 2 - wop ** 2, 2 * zeta * wn * wop)
    if method == "quasi":
        f = np.linspace(0.05, f_op, 20000)
        w = 2 * np.pi * f
        X = w ** 2 / np.hypot(wn ** 2 - w ** 2, 2 * zeta * wn * w)
        return tau * float(np.trapezoid(1 / S.cycles_to_failure(R_e * X / Xop, fa), f))
    num, den, _ = cont2discrete(([1.0], [1.0, 2 * zeta * wn, wn * wn]), 1 / fs, method="foh")
    d = []
    for k in range(n):
        t = np.arange(int((15 + 5.5 * tau) * fs)) / fs - 15
        w = wop * np.exp(-np.maximum(t, 0) / tau)
        th = np.cumsum(w) / fs + 2 * np.pi * k / n
        x = lfilter(np.ravel(num), den, w * w * np.sin(th))[int(15 * fs):]
        r, c = S.rainflow(R_e / 2 * x / Xop)
        d.append(S.miner(r, c, fa))
    return float(np.mean(d))


# ---- two-mode identification from the braked stops (speed channel), and coast simulation with it
def _modal(fr, z, w, fs):
    from scipy.signal import cont2discrete, lfilter
    wn = 2 * np.pi * fr
    num, den, _ = cont2discrete(([1.0], [1.0, 2 * z * wn, wn * wn]), 1 / fs, method="foh")
    return lambda u: lfilter(np.ravel(num), den, u)


def ringdown2(s, rpm, fs):
    """Two decaying sinusoids fitted to the free decay once the drive is at rest."""
    from scipy.optimize import least_squares
    k = int(np.argmax(rpm < 1.0)) + int(0.2 * fs)
    seg = s[k:]
    t = np.arange(seg.size) / fs
    n = 8 * seg.size
    spec = np.abs(np.fft.rfft((seg - seg.mean()) * np.hanning(seg.size), n))
    fr = np.fft.rfftfreq(n, 1 / fs)
    m = (fr > 2) & (fr < 5)
    sp, fq = spec[m], fr[m]
    i1 = int(np.argmax(sp))
    mask = np.abs(fq - fq[i1]) > 0.35
    i2 = int(np.argmax(np.where(mask, sp, 0)))
    fa, fb = sorted([fq[i1], fq[i2]])
    def mdl(p):
        A1, a1, f1, p1, A2, a2, f2, p2, c = p
        return A1 * np.exp(-a1 * t) * np.sin(2 * np.pi * f1 * t + p1) + A2 * np.exp(-a2 * t) * np.sin(2 * np.pi * f2 * t + p2) + c
    best = None
    amp = np.ptp(seg[:int(fs)]) / 4
    for p1 in np.linspace(0, 2 * np.pi, 4, endpoint=False):
        for p2 in np.linspace(0, 2 * np.pi, 4, endpoint=False):
            x0 = [amp, 0.3, fa, p1, amp, 0.3, fb, p2, 0.0]
            try:
                r = least_squares(lambda p: mdl(p) - seg, x0, max_nfev=4000)
            except Exception:
                continue
            if best is None or r.cost < best.cost:
                best = r
    A1, a1, f1, p1, A2, a2, f2, p2, c = best.x
    out = []
    for a, f in ((a1, f1), (a2, f2)):
        wd = 2 * np.pi * abs(f)
        wn = np.hypot(a, wd)
        out.append((wn / (2 * np.pi), a / wn))
    return sorted(out)


def forced_fit(recs, fs, modes_):
    """Stress = c1 q1 + c2 q2, q_i driven by w^2 sin(theta), theta from the speed channel plus an unknown start
    phase per record. Grid the phase, solve c by linear least squares; then refine everything."""
    from scipy.optimize import least_squares
    (f1, z1), (f2, z2) = modes_
    def resp(p, s, rpm):
        f1, z1, f2, z2 = p[:4]
        w = rpm / 60 * 2 * np.pi
        lead = np.full(int(15 * fs), w[0])
        W = np.r_[lead, w]
        return W, [_modal(f1, z1, 1, fs), _modal(f2, z2, 1, fs)]
    def qs(p, rpm, th0):
        f1, z1, f2, z2 = p[:4]
        w = rpm / 60 * 2 * np.pi
        W = np.r_[np.full(int(15 * fs), w[0]), w]
        th = np.cumsum(W) / fs + th0
        u = W * W * np.sin(th)
        q1 = _modal(f1, z1, 1, fs)(u)[int(15 * fs):]
        q2 = _modal(f2, z2, 1, fs)(u)[int(15 * fs):]
        return q1, q2
    p = np.array([f1, z1, f2, z2])
    ths = []
    for s, rpm in recs:
        best = None
        for th0 in np.linspace(0, 2 * np.pi, 48, endpoint=False):
            q1, q2 = qs(p, rpm, th0)
            M = np.c_[q1, q2, np.ones_like(q1)]
            c, *_ = np.linalg.lstsq(M, s, rcond=None)
            r = np.sum((M @ c - s) ** 2)
            if best is None or r < best[0]:
                best = (r, th0)
        ths.append(best[1])
    def res(x):
        p = x[:4]; c1, c2 = x[4:6]
        out = []
        for (s, rpm), th0, off in zip(recs, x[6:6 + len(recs)], x[6 + len(recs):]):
            q1, q2 = qs(p, rpm, th0)
            out.append(c1 * q1 + c2 * q2 + off - s)
        return np.concatenate(out)
    # initial c from the first record at its best phase
    q1, q2 = qs(p, recs[0][1], ths[0])
    c, *_ = np.linalg.lstsq(np.c_[q1, q2], recs[0][0], rcond=None)
    x0 = np.r_[p, c, ths, np.zeros(len(recs))]
    sol = least_squares(res, x0, x_scale=np.r_[0.01, 0.001, 0.01, 0.001, np.abs(c) + 1e-9, np.ones(2 * len(recs))])
    return sol.x[:4], sol.x[4:6], sol


def coast2(p, c, tau, f_op, fa, fs=1000.0, n=8):
    f1, z1, f2, z2 = p
    out = []
    for k in range(n):
        t = np.arange(int((15 + 5.5 * tau) * fs)) / fs - 15
        w = 2 * np.pi * f_op * np.exp(-np.maximum(t, 0) / tau)
        th = np.cumsum(w) / fs + 2 * np.pi * k / n
        u = w * w * np.sin(th)
        x = c[0] * _modal(f1, z1, 1, fs)(u) + c[1] * _modal(f2, z2, 1, fs)(u)
        r, cc = S.rainflow(x[int(15 * fs):])
        out.append(S.miner(r, cc, fa))
    return float(np.mean(out))
