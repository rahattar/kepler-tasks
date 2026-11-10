"""Reference: each screen's Miner sum at the monitored gusset weld toe to 2026-10-31, from the records and one
outage programme of field tests.

    python3 solve.py DATA_DIR FIELD_DIR OUT_JSON

1. Records. Hot-spot stress = E x linear extrapolation to the toe from the two gauges' actual positions (S2: 10 and
   30 mm on a 20 mm plate). S4's gauges are the 2.12 lot (strain x 2.00/2.12). S7's channels are swapped (the gauge
   behind reads more than the one at the toe). S8's records since the spare logger went in are at 200 samples per
   second. A gauge whose ratio to its partner shifts during the campaign is rescaled to its earlier relation: S1's G2
   (wet from August, logged in September) and S9's G1 (nothing logged; G2 keeps its relation to the feed and the
   October inspection found no crack, so it is the gauge).
2. Steady running: one cycle per revolution; the full-cycle range is linear in the feed (fitted per screen, empty
   records at feed 0). Damage per band hour: the S-N rate averaged across the band.
3. Starts and braked stops: their records' rainflow damage, per event.
4. Coast-downs before the brakes (2026-03-02): the body's two modes are fitted to each screen's braked stops (ring-down
   after standstill for the frequencies, then the forced response with the speed channel for the two weights and
   each record's phase); the coast-down w_op exp(-t/tau) is then simulated and rainflow-counted. tau from the
   commissioning table (S2: 25.0 s after its 2021-10-05 bearing job).
5. What the records cannot settle, and the outage programme (three tests, ordered at once):
   - S5 has no strain records at all -> strain survey.
   - S6 has no event records, and most of its damage is its pre-brake stops -> coast-down test.
   - S8 and S10 have the larger drive, never timed, identical on both -> one coast-down test (S8) gives tau for both.
   - Left to proxies: S3's untimed coast-down (standard drive: the standard-drive median); S4's and S5's events and
     S6's starts and braked stops (siblings' damage per event / empty range^3, median, x the screen's own range^3).
6. Operating log: S8's starts since 2024-07-01 are halved (the pilot historian counts start and stop commands); S9's
   2024 comes from the production report, loaded hours split across bands as in S9's other years; S6 counts from its
   2025-11-14 replacement.
"""
import json
import os
import re
import subprocess
import sys
import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from scipy.signal import cont2discrete, lfilter

DATA, FIELD, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
E = 207000.0
BRAKE = "2026-03-02"
BAND_COLS = ["h_empty", "h_0_200", "h_200_400", "h_400_600", "h_600_800"]
BANDS = [(0.0, 0.0), (0.0, 200.0), (200.0, 400.0), (400.0, 600.0), (600.0, 800.0)]
UNITS = ["S%d" % i for i in range(1, 11)]
PLAN = [("S5", "strain-survey"), ("S6", "coast-down"), ("S8", "coast-down")]


def doc(name):
    return open(os.path.join(DATA, "docs", name)).read()


# ---------------------------------------------------------------- fatigue arithmetic (plant standard FS-07)
def n_fail(dS, fat):
    dS = np.asarray(dS, float)
    knee = fat * 0.2 ** (1 / 3)
    with np.errstate(divide="ignore"):
        return np.where(dS >= knee, 2e6 * (fat / dS) ** 3, 1e7 * (knee / dS) ** 5)


def rainflow(x):
    x = np.asarray(x, float)
    x = x[np.r_[0, np.nonzero(np.diff(x))[0] + 1]]
    s = np.sign(np.diff(x))
    tp = x[np.r_[True, s[1:] != s[:-1], True]]
    st, R, C = [], [], []
    for v in tp:
        st.append(v)
        while len(st) >= 3:
            X, Y = abs(st[-1] - st[-2]), abs(st[-2] - st[-3])
            if X < Y:
                break
            if len(st) == 3:
                R.append(Y); C.append(0.5); st.pop(0)
            else:
                R.append(Y); C.append(1.0); last = st.pop(); st.pop(); st.pop(); st.append(last)
    for i in range(len(st) - 1):
        R.append(abs(st[i + 1] - st[i])); C.append(0.5)
    return np.array(R), np.array(C)


def miner(sig, fat):
    r, c = rainflow(sig)
    m = r > 0
    return float(np.sum(c[m] / n_fail(r[m], fat)))


def full_range(sig):
    r, c = rainflow(sig)
    return float(np.median(r[c == 1.0]))


# ---------------------------------------------------------------- records and documents
reg = pd.read_csv(os.path.join(DATA, "screen_register.csv")).set_index("screen")
idx = pd.read_csv(os.path.join(DATA, "records", "index.csv"))
LOG = pd.read_csv(os.path.join(DATA, "operating_log.csv"))
mlog = pd.read_csv(os.path.join(DATA, "maintenance_log.csv"))
REC = {r: pd.read_csv(os.path.join(DATA, f)) for r, f in zip(idx.record, idx.file)}

gi = doc("gauge_installation.md")
pos = {u: (0.4, 1.0) for u in UNITS}
m = re.search(r"\| (S\d+) \(stiffener in the way\) \| (\d+) mm \| (\d+) mm \|", gi)
pos[m.group(1)] = (float(m.group(2)) / reg.loc[m.group(1), "side_plate_mm"], float(m.group(3)) / reg.loc[m.group(1), "side_plate_mm"])
gf = {u: 2.00 for u in UNITS}
m = re.search(r"gauge factor ([\d.]+)\) on (S\d+)\.", gi)
gf[m.group(2)] = float(m.group(1))
fs_rec = {u: 500.0 for u in UNITS}
spare = mlog[mlog.work_done.str.contains("spare logger")].iloc[0]
spare_fs = float(re.search(r"DL-200 \(same input, (\d+) samples per second\)", doc("logger_notes.md")).group(1))
fat_cls = {"rev A": 90.0, "rev B": 100.0}
FAT = {u: fat_cls[reg.loc[u, "gusset"]] * ((25.0 / reg.loc[u, "side_plate_mm"]) ** 0.3 if reg.loc[u, "side_plate_mm"] > 25 else 1.0)
       for u in UNITS}
table = {}
for u, v in re.findall(r"\| (S\d+) \| ([\d.]+|not timed) \|", doc("screen_description.md")):
    if v != "not timed":
        table[u] = float(v) / np.log(2.0)                 # half-speed time -> exponential time constant
bear = mlog[mlog.work_done.str.contains("coast-down re-timed")].iloc[0]
retime = (bear.screen, bear.date, float(re.search(r"half speed ([\d.]+) s", bear.work_done).group(1)) / np.log(2.0))
frame_b = [u for u in UNITS if reg.loc[u, "drive_kw"] == reg.drive_kw.max()]
tau_a_med = float(np.median([table[u] for u in UNITS if u in table and u not in frame_b]))


def rec_fs(u, start):
    return spare_fs if (u == spare.screen and start >= spare.date) else fs_rec[u]


def raw(rid, u):
    d = REC[rid]
    e1, e2 = d.ch1_ue.values * 2.00 / gf[u], d.ch2_ue.values * 2.00 / gf[u]
    return e1, e2


# channel order: the gauge at 0.4t must read more than the one behind it
swap = {}
for u in UNITS:
    rows = idx[(idx.screen == u) & idx.kind.isin(["loaded", "empty"])]
    if len(rows) == 0:
        continue
    r = [np.ptp(REC[rid].ch2_ue) / np.ptp(REC[rid].ch1_ue) for rid in rows.record]
    swap[u] = bool(np.median(r) > 1.0)


def channels(rid, u):
    e1, e2 = raw(rid, u)
    return (e2, e1) if swap.get(u) else (e1, e2)


# a gauge that drifts away from its partner during the campaign: find the change and the channel that moved
fix = {}
for u in UNITS:
    rows = idx[(idx.screen == u) & idx.kind.isin(["loaded", "empty"])].sort_values("start")
    if len(rows) < 6:
        continue
    a1 = np.array([np.ptp(channels(rid, u)[0]) for rid in rows.record])
    a2 = np.array([np.ptp(channels(rid, u)[1]) for rid in rows.record])
    F = rows.feed_tph.values.astype(float)
    ratio = a2 / a1
    best = None
    for k in range(2, len(ratio) - 1):                    # change point: least spread of the ratio on each side
        sse = np.sum((ratio[:k] - ratio[:k].mean()) ** 2) + np.sum((ratio[k:] - ratio[k:].mean()) ** 2)
        if best is None or sse < best[0]:
            best = (sse, k)
    k = best[1]
    if abs(ratio[k:].mean() / ratio[:k].mean() - 1) < 0.08:
        continue
    when = rows.start.values[k]
    moved = {}
    for ch, a in ((1, a1), (2, a2)):                      # which channel left its own relation to the feed
        p = np.polyfit(F[:k], a[:k], 1)
        moved[ch] = float(np.median(a[k:] / np.polyval(p, F[k:])))
    ch = min(moved, key=lambda c: moved[c])
    fix[u] = (when, ch, 1.0 / moved[ch], ratio[:k].mean(), ratio[k:].mean())


def after_change(rid, u, start):
    """Steady records by date; an event record by its own gauge ratio at full speed (first or last second)."""
    kind = idx.set_index("record").loc[rid, "kind"]
    if kind in ("loaded", "empty"):
        return start >= fix[u][0]
    e1, e2 = channels(rid, u)
    n = int(rec_fs(u, start))
    seg = slice(0, n // 2) if kind == "stop" else slice(-n, None)
    r = np.ptp(e2[seg]) / np.ptp(e1[seg])
    return abs(r - fix[u][4]) < abs(r - fix[u][3])


def hotspot(rid, u, start):
    e1, e2 = channels(rid, u)
    if u in fix and after_change(rid, u, start):
        if fix[u][1] == 1:
            e1 = e1 * fix[u][2]
        else:
            e2 = e2 * fix[u][2]
    p1, p2 = pos[u]
    return (p2 * e1 - p1 * e2) / (p2 - p1) * E * 1e-6


def hs_std(e1, e2):
    return (1.0 * e1 - 0.4 * e2) / 0.6 * E * 1e-6


# ---------------------------------------------------------------- two-mode suspension
def modal(f, z, fs):
    wn = 2 * np.pi * f
    num, den, _ = cont2discrete(([1.0], [1.0, 2 * z * wn, wn * wn]), 1 / fs, method="foh")
    return lambda u: lfilter(np.ravel(num), den, u)


def ringdown(s, rpm, fs):
    k = int(np.argmax(rpm < 1.0)) + int(0.2 * fs)
    seg = s[k:]
    t = np.arange(seg.size) / fs
    n = 8 * seg.size
    sp = np.abs(np.fft.rfft((seg - seg.mean()) * np.hanning(seg.size), n))
    fr = np.fft.rfftfreq(n, 1 / fs)
    m = (fr > 2) & (fr < 5)
    sp, fq = sp[m], fr[m]
    i1 = int(np.argmax(sp))
    i2 = int(np.argmax(np.where(np.abs(fq - fq[i1]) > 0.35, sp, 0)))
    fa, fb = sorted([fq[i1], fq[i2]])
    def mdl(p):
        A1, a1, f1, p1, A2, a2, f2, p2, c = p
        return A1 * np.exp(-a1 * t) * np.sin(2 * np.pi * f1 * t + p1) + A2 * np.exp(-a2 * t) * np.sin(2 * np.pi * f2 * t + p2) + c
    best = None
    amp = np.ptp(seg[:int(fs)]) / 4
    for p1 in np.linspace(0, 2 * np.pi, 4, endpoint=False):
        for p2 in np.linspace(0, 2 * np.pi, 4, endpoint=False):
            r = least_squares(lambda p: mdl(p) - seg, [amp, 0.3, fa, p1, amp, 0.3, fb, p2, 0.0], max_nfev=4000)
            if best is None or r.cost < best.cost:
                best = r
    A1, a1, f1, p1, A2, a2, f2, p2, c = best.x
    out = []
    for a, f in ((a1, f1), (a2, f2)):
        wn = np.hypot(a, 2 * np.pi * abs(f))
        out.append((wn / (2 * np.pi), a / wn))
    return sorted(out)


def forced_fit(recs, fs, init):
    (f1, z1), (f2, z2) = init
    def qs(p, rpm, th0):
        w = rpm / 60 * 2 * np.pi
        W = np.r_[np.full(int(15 * fs), w[0]), w]
        th = np.cumsum(W) / fs + th0
        u = W * W * np.sin(th)
        return modal(p[0], p[1], fs)(u)[int(15 * fs):], modal(p[2], p[3], fs)(u)[int(15 * fs):]
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
        out = []
        for (s, rpm), th0, off in zip(recs, x[6:6 + len(recs)], x[6 + len(recs):]):
            q1, q2 = qs(x[:4], rpm, th0)
            out.append(x[4] * q1 + x[5] * q2 + off - s)
        return np.concatenate(out)
    q1, q2 = qs(p, recs[0][1], ths[0])
    c, *_ = np.linalg.lstsq(np.c_[q1, q2], recs[0][0], rcond=None)
    x0 = np.r_[p, c, ths, np.zeros(len(recs))]
    sol = least_squares(res, x0, x_scale=np.r_[0.01, 0.001, 0.01, 0.001, np.abs(c) + 1e-9, np.ones(2 * len(recs))])
    return sol.x[:4], sol.x[4:6]


def coast(p, c, tau, f_op, fat, fs=1000.0, n=8):
    f1, z1, f2, z2 = p
    d = []
    for k in range(n):
        t = np.arange(int((15 + 5.5 * tau) * fs)) / fs - 15
        w = 2 * np.pi * f_op * np.exp(-np.maximum(t, 0) / tau)
        th = np.cumsum(w) / fs + 2 * np.pi * k / n
        u = w * w * np.sin(th)
        x = c[0] * modal(f1, z1, fs)(u) + c[1] * modal(f2, z2, fs)(u)
        d.append(miner(x[int(15 * fs):], fat))
    return float(np.mean(d))


# ---------------------------------------------------------------- outage programme
def order_programme():
    if os.path.exists(os.path.join(FIELD, "fieldwork_index.csv")):
        return
    plan = json.dumps(dict(tests=[dict(screen=u, test=k) for u, k in PLAN]))
    r = subprocess.run(["fieldwork", "submit"], input=plan, text=True, capture_output=True)
    print(r.stdout.strip() or r.stderr.strip())


def operating_log(u):
    L = LOG[LOG.screen == u].copy()
    note = doc("operating_log_notes.md")
    m = re.search(r"(S\d+) has been the pilot screen for the new historian since (\d{4}-\d\d-\d\d)", note)
    if m and m.group(1) == u:
        L.loc[L.date >= m.group(2), "starts"] = L.loc[L.date >= m.group(2), "starts"] / 2.0
    m = re.search(r"(S\d+)'s rows for (\d{4}) are missing", note)
    if m and m.group(1) == u:
        txt = doc("s9_production_2024.md")
        cols = BAND_COLS[1:]
        frac = L[cols].sum() / L[cols].sum().sum()
        add = []
        for mth, run, emp, st in re.findall(r"\| (%s-\d\d) \| (\d+) \| (\d+) \| (\d+) \|" % m.group(2), txt):
            d = dict(screen=u, date=mth + "-15", h_empty=float(emp), starts=float(st))
            d.update({c: (float(run) - float(emp)) * float(frac[c]) for c in cols})
            add.append(d)
        L = pd.concat([L, pd.DataFrame(add)], ignore_index=True)
    rep = mlog[(mlog.screen == u) & mlog.work_done.str.contains("replaced") & mlog.work_done.str.contains("Gusset")]
    if len(rep):
        L = L[L.date >= rep.date.iloc[0]]
    return L


def main():
    order_programme()
    fidx = pd.read_csv(os.path.join(FIELD, "fieldwork_index.csv"))
    tested = set(zip(fidx.screen, fidx.test))
    comp = {}
    for u in UNITS:
        c = dict(fat=FAT[u], L=operating_log(u))
        rows = idx[idx.screen == u]
        F, R, ev = [], [], {"start": [], "stop": []}
        stops = []
        for rid, kind, feed, start in zip(rows.record, rows.kind, rows.feed_tph, rows.start):
            s = hotspot(rid, u, start)
            if kind in ("loaded", "empty"):
                F.append(feed); R.append(full_range(s))
            else:
                ev[kind].append(miner(s, FAT[u]))
                if kind == "stop":
                    stops.append((s, REC[rid].speed_rpm.values, rec_fs(u, start)))
        if (u, "strain-survey") in tested:
            F, R = [], []
            for f, feed in zip(fidx.file[(fidx.screen == u) & (fidx.test == "strain-survey")],
                               fidx.feed_tph[(fidx.screen == u) & (fidx.test == "strain-survey")]):
                d = pd.read_csv(os.path.join(FIELD, f))
                F.append(feed); R.append(full_range(hs_std(d.ch1_ue.values, d.ch2_ue.values)))
        c["ab"] = np.polyfit(F, R, 1)[::-1] if F else None
        c["start"] = float(np.mean(ev["start"])) if ev["start"] else None
        c["stop"] = float(np.mean(ev["stop"])) if ev["stop"] else None
        if stops:
            fs = stops[0][2]
            recs = [(s, rpm) for s, rpm, _ in stops]
            c["modes"] = forced_fit(recs, fs, ringdown(recs[0][0], recs[0][1], fs))
        if (u, "coast-down") in tested:
            f = fidx.file[(fidx.screen == u) & (fidx.test == "coast-down")].iloc[0]
            d = pd.read_csv(os.path.join(FIELD, f))
            c["coast_test"] = miner(hs_std(d.ch1_ue.values, d.ch2_ue.values), FAT[u])
            sp = d.speed_rpm.values
            t = np.arange(sp.size) / 500.0
            mk = (sp < 0.95 * sp[0]) & (sp > 0.05 * sp[0])
            c["tau_test"] = -1.0 / np.polyfit(t[mk], np.log(sp[mk]), 1)[0]
        comp[u] = c
        print(u, "read", flush=True)
    tau_b = [comp[u]["tau_test"] for u in frame_b if "tau_test" in comp[u]]
    tau_b = tau_b[0] if tau_b else None
    def tau_of(u):
        if u in frame_b and tau_b:
            return tau_b
        return table.get(u, tau_a_med)
    Ae = {u: comp[u]["ab"][0] for u in UNITS}
    for u in UNITS:
        c = comp[u]
        f_op = reg.loc[u, "motor_rpm"] / 60.0
        if "coast_test" in c:
            c["coast"] = c["coast_test"]
        elif "modes" in c:
            p, cc = c["modes"]
            if u == retime[0]:
                L = c["L"]; pre = L.date < BRAKE; late = L.date >= retime[1]
                n1, n2 = float(L.starts[pre & ~late].sum()), float(L.starts[pre & late].sum())
                c["coast"] = (n1 * coast(p, cc, tau_of(u), f_op, c["fat"]) + n2 * coast(p, cc, retime[2], f_op, c["fat"])) / max(n1 + n2, 1)
            else:
                c["coast"] = coast(p, cc, tau_of(u), f_op, c["fat"])
        else:
            c["coast"] = None
        print(u, "coast-down model", flush=True)
    norm = {k: [comp[u][k] / Ae[u] ** 3 for u in UNITS if comp[u][k] is not None and u not in frame_b]
            for k in ("start", "stop", "coast")}
    out = {}
    for u in UNITS:
        c = comp[u]; L = c["L"]
        a, b = c["ab"]
        cph = reg.loc[u, "motor_rpm"] * 60.0
        D = 0.0
        for (lo, hi), col in zip(BANDS, BAND_COLS):
            if hi == lo:
                r = cph / float(n_fail(a + b * lo, c["fat"]))
            else:
                Fv = np.linspace(lo, hi, 201)
                r = float(np.trapezoid(cph / n_fail(a + b * Fv, c["fat"]), Fv) / (hi - lo))
            D += float(L[col].sum()) * r
        pre = (L.date < BRAKE).values
        n_all, n_pre = float(L.starts.sum()), float(L.starts[pre].sum())
        get = lambda k: c[k] if c[k] is not None else float(np.median(norm[k])) * Ae[u] ** 3
        D += n_all * get("start") + (n_all - n_pre) * get("stop") + n_pre * get("coast")
        out[u] = round(D, 4)
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(out)


if __name__ == "__main__":
    main()
