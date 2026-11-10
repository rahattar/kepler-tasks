"""A second route diagnosis program, written apart from solution/diagnose.py and sharing no code with it.

    python3 independent_diagnose.py ROUTE_DIR OUT_CSV

Different choices: scipy.signal for windows, filters and the Hilbert envelope; a flat-top window and zero padding;
speed from the median tach interval with the marks per turn found from the interval pattern; the sample-rate check
by matching the high capture's line positions to the low capture's; the channel check from a moving-average drift
in the time domain; crossed points from the electrical line alone; and a score for every condition code, the
largest winning, instead of an ordered rule list.
"""
import csv
import json
import os
import sys

import numpy as np
from scipy import signal

GMM = 9806.65


def rows(p):
    if not os.path.exists(p):
        return []
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


class Spec:
    """Velocity (mm/s, peak) or acceleration (g, peak) spectrum with peak reading near a frequency."""

    def __init__(self, x, fs, velocity=True, pad=2):
        n = len(x)
        w = signal.windows.flattop(n)
        X = np.abs(np.fft.rfft((x - np.mean(x)) * w, pad * n)) * 2 / w.sum()
        self.f = np.fft.rfftfreq(pad * n, 1 / fs)
        if velocity:
            X = X * GMM / (2 * np.pi * np.maximum(self.f, 1e-9))
            X[self.f < 1.0] = 0
        self.A = X

    def at(self, f0, half_width):
        sel = np.abs(self.f - f0) <= half_width
        return float(self.A[sel].max()) if sel.any() else 0.0

    def floor(self, f0, span=8.0):
        sel = (np.abs(self.f - f0) <= span) & (np.abs(self.f - f0) > 0.5)
        return float(np.median(self.A[sel])) if sel.any() else 0.0


def drifted(x, fs):
    """Ski slope: a sensor or cable fault leaves a slow wander far above any machine line below 4 Hz. Welch PSD of
    acceleration, turned into velocity amplitude per line, compared with an absolute limit."""
    f, P = signal.welch(x - x.mean(), fs=fs, nperseg=8192)
    sel = (f > 0.7) & (f < 4.0)
    v = np.sqrt(P[sel] * (f[1] - f[0]) * 2) * GMM / (2 * np.pi * f[sel])
    return float(np.median(v)) > 0.3              # mm/s; no machine line lies below 4 Hz


def speed_from_tach(path, sync):
    t = np.array([float(r["pulse_time_s"]) for r in rows(path)])
    d = np.diff(t)
    med = np.median(d)
    # two marks per turn give alternating short and long intervals summing to one turn
    if np.std(d) / np.mean(d) > 0.05:
        turn = np.median(d[:-1] + d[1:])
        return 1.0 / turn
    f = 1.0 / med
    m = 1
    while f / m > sync * 1.001:
        m += 1
    return f / m


def high_rate(xh, fs_plan, low_spec, f1):
    """Sample rate of the high capture: the candidate whose strong low-frequency lines sit where the low capture's do."""
    cands = [fs_plan, 0.8 * fs_plan, 0.5 * fs_plan, 0.625 * fs_plan, 0.4 * fs_plan]
    ref_lines = [h * f1 for h in (1, 2, 3)]
    best, bs = fs_plan, 0
    for c in cands:
        s = Spec(xh, c, velocity=False, pad=4)
        sc = sum(s.at(q, 0.8) > 10 * s.floor(q, 20) for q in ref_lines)
        if sc > bs:
            best, bs = c, sc
    return best


def envelope_spec(x, fs):
    hi = min(7000.0, 0.45 * fs)
    sos = signal.butter(4, [1500.0, hi], btype="band", fs=fs, output="sos")
    e = np.abs(signal.hilbert(signal.sosfiltfilt(sos, x - x.mean())))
    return Spec(e, fs, velocity=False, pad=2)


def bearing_freqs(b):
    n, d, D, a = int(b["rolling_elements"]), float(b["element_diameter_mm"]), float(b["pitch_diameter_mm"]), \
        np.radians(float(b["contact_angle_deg"]))
    c = d / D * np.cos(a)
    return {"BEARING_OUTER": 0.5 * n * (1 - c), "BEARING_INNER": 0.5 * n * (1 + c),
            "BEARING_BALL": D / d * (1 - c * c), "BEARING_CAGE": 0.5 * (1 - c)}


def main(route, out_path):
    meta = json.load(open(os.path.join(route, "route.json")))
    data = {}
    for c in meta["captures"]:
        arr = np.load(os.path.join(route, c["file"]))[c["capture"]] * c["g_per_count"]
        data[(c["machine"], c["point"], c["capture"])] = (arr, float(c["sample_rate_hz"]))
    bear = {r["designation"]: r for r in rows(os.path.join(route, "bearing_data.csv"))}
    log = rows(os.path.join(route, "maintenance_log.csv"))
    proc = {r["machine"]: r for r in rows(os.path.join(route, "process_snapshot.csv"))}
    results = []
    for r in rows(os.path.join(route, "register.csv")):
        m = r["machine"]
        pts = r["points"].split()
        vert = "vertical" in r["kind"]
        c_lo, c_ax, c_hi = ("low_x", "low_y", "high_x") if vert else ("low_r", "low_a", "high_r")
        poles = int(r["motor_poles"])
        sync = 120.0 / poles
        # channel check
        use = [p for p in pts if not drifted(*data[(m, p, c_lo)])] or pts
        # speed
        lo = {p: Spec(*data[(m, p, c_lo)]) for p in pts}
        drive = 60.0
        tp = os.path.join(route, m.lower() + "_tach.csv")
        if os.path.exists(tp):
            f1 = speed_from_tach(tp, sync)
        elif "VFD" in r["drive"]:
            s = lo[use[0]]
            ratio = float(r["motor_sheave_mm"]) / float(r["fan_sheave_mm"]) if r["fan_sheave_mm"] else None
            best = (-1, None, None)
            for fd in np.arange(30.0, 61.0, 0.05):           # drive frequency: its 2x line and a motor line just below
                e = s.at(2 * fd, 0.03)
                fsyn = 2 * fd / poles
                cand = s.f[(s.f > 0.97 * fsyn) & (s.f < 0.999 * fsyn)]
                if not len(cand):
                    continue
                seg = (s.f > 0.97 * fsyn) & (s.f < 0.999 * fsyn)
                fm = s.f[seg][np.argmax(s.A[seg])]
                score = e * s.A[seg].max() * (s.at(fm * ratio, 0.05) if ratio else 1)
                if score > best[0]:
                    best = (score, fm, fd)
            f1, drive = best[1], best[2]
        else:
            s = lo[use[0]]
            seg = (s.f > 0.95 * sync) & (s.f < 0.9995 * sync)
            i = int(np.where(seg)[0][np.argmax(s.A[seg])])
            a, b, c = s.A[i - 1], s.A[i], s.A[i + 1]           # parabola through the peak and its neighbours
            f1 = float(s.f[i] + 0.5 * (a - c) / (a - 2 * b + c) * (s.f[1] - s.f[0]))
        bw = 0.04
        # crossed points: the motor's 2 x drive-frequency line belongs to the motor file
        if not vert and len(pts) == 2:
            em, ed = lo[pts[0]].at(2 * drive, bw), lo[pts[1]].at(2 * drive, bw)
            if ed > 4 * em and ed > 0.05:
                lo = {pts[0]: lo[pts[1]], pts[1]: lo[pts[0]]}
                for k in (c_lo, c_ax, c_hi):
                    data[(m, pts[0], k)], data[(m, pts[1], k)] = data[(m, pts[1], k)], data[(m, pts[0], k)]
                use = [{pts[0]: pts[1], pts[1]: pts[0]}[p] for p in use]
        ratio = float(r["motor_sheave_mm"]) / float(r["fan_sheave_mm"]) if r["fan_sheave_mm"] else 1.0
        rot = {p: f1 * ratio if p == "FAN" else f1 for p in pts}
        elem = {"MOT": "motor", "PMP": "pump", "FAN": "fan", "CMP": "compressor"}
        score = {}

        def put(key, val):
            if val > score.get(key, (0,))[0]:
                score[key] = (val,)
        for p in use:
            s = lo[p]
            one, two = s.at(rot[p], bw), s.at(2 * f1, bw)
            halves = [s.at(h * rot[p], bw) / (s.floor(h * rot[p]) + 1e-9) for h in (0.5, 1.5, 2.5)]
            if p == "MOT":
                e2 = s.at(2 * drive, bw) if abs(2 * drive - 2 * f1) > 0.1 else 0.0
                put(("ELECTRICAL", "motor"), e2 / 2.5)
                fp = poles * (2 * drive / poles - f1)
                if fp > 0.25:
                    lsb, usb = s.at(f1 - fp, bw), s.at(f1 + fp, bw)
                    if min(lsb / (s.floor(f1 - fp) + 1e-9), usb / (s.floor(f1 + fp) + 1e-9)) > 4:
                        put(("ROTOR_BAR", "motor"), min(lsb, usb) / 0.45)
            if not r["belt_length_mm"] and not vert:
                put(("MISALIGNMENT", "coupling"), two / 2.5)
            if min(sorted(halves)[1:]) > 5 and p in elem:
                put(("LOOSENESS", elem[p]), 1.0 + max(s.at(h * rot[p], bw) for h in (0.5, 1.5, 2.5)) / 0.5)
            if r["belt_length_mm"]:
                fb = np.pi * float(r["motor_sheave_mm"]) * f1 / float(r["belt_length_mm"])
                put(("BELT", "belt"), max(s.at(h * fb, 0.08) for h in (1, 2, 3)) / 1.0)
            if p in elem:
                put(("UNBALANCE", elem[p]), 0.9 * one / 3.5)
            if vert:
                imp = rows(os.path.join(route, m.lower() + "_impact_test.csv"))
                fr = np.array([float(q["frequency_hz"]) for q in imp])
                hx = np.array([float(q["x_response_rel"]) for q in imp])
                sy = Spec(*data[(m, p, "low_y")])
                if abs(fr[np.argmax(hx)] / f1 - 1) < 0.08 and one > 3 * sy.at(f1, bw):
                    put(("RESONANCE", "structure"), one / 3.5)
        if r["gearbox_pinion_teeth"] and "GBX" in use:
            sa = Spec(*data[(m, "GBX", c_lo)], velocity=False)
            z1, z2 = int(r["gearbox_pinion_teeth"]), int(r["gearbox_gear_teeth"])
            seg = np.abs(sa.f - z1 * f1) < 0.01 * z1 * f1      # mesh line fixes the input speed precisely
            gm = float(sa.f[seg][np.argmax(sa.A[seg])])
            fg = gm / z2
            f1g = gm / z1
            sg = sum(sa.at(gm + j * fg, bw) for j in (-2, -1, 1, 2))
            sp = sum(sa.at(gm + j * f1g, bw) for j in (-2, -1, 1, 2))
            put(("GEAR_TOOTH", "gear" if sg > sp else "pinion"), max(sg, sp) / 0.03)
        for p in use:
            col = "motor_bearings_de_nde" if p == "MOT" else "driven_bearings_de_nde"
            if p not in elem or not r.get(col):
                continue
            des = r[col].split("/")[0]
            for e in log:
                txt = e["entry"]
                if e["machine"] == m and "replaced" in txt and "issued" in txt and txt.startswith("Motor") == (p == "MOT"):
                    des = txt.split("issued")[1].strip().split()[0].rstrip(".")
            if des not in bear:
                continue
            xh, fsp = data[(m, p, c_hi)]
            es = envelope_spec(xh, high_rate(xh, fsp, lo[p], f1))
            bf = bearing_freqs(bear[des])

            def rel(q):
                return es.at(q, 0.012 * q + 0.6) / (es.floor(q, 40) + 1e-12)
            ftf = bf["BEARING_CAGE"] * rot[p]
            for code in ("BEARING_OUTER", "BEARING_INNER"):
                q = bf[code] * rot[p]
                if rel(q) > 6 and rel(2 * q) > 3:
                    put((code, elem[p]), 1.0 + min(rel(q), rel(2 * q)) / 10.0)
            q = bf["BEARING_BALL"] * rot[p]           # ball spin (twice per turn), with cage-rate sidebands
            ball = rel(q) > 4 and rel(2 * q) > 3 and max(rel(q - ftf), rel(q + ftf)) > 2
            if ball:
                put(("BEARING_BALL", elem[p]), 1.0 + min(rel(q), rel(2 * q)) / 10.0)
            if not ball and rel(ftf) > 8 and rel(bf["BEARING_BALL"] * rot[p]) < 3:
                put(("BEARING_CAGE", elem[p]), 1.0 + rel(ftf) / 20.0)
        if m in proc and proc[m].get("npsh_available_m") and "PMP" in use:
            if float(proc[m]["npsh_available_m"]) < float(proc[m]["npsh_required_m"]):
                xh, _ = data[(m, "PMP", c_hi)]
                kurt = np.mean((xh - xh.mean()) ** 4) / np.var(xh) ** 2
                if kurt > 4:
                    put(("CAVITATION", "pump"), 3.0)
        best = max(score.items(), key=lambda kv: kv[1][0], default=(("NONE", "none"), (0,)))
        results.append((m,) + (best[0] if best[1][0] >= 1.0 else ("NONE", "none")))
    with open(out_path, "w") as f:
        f.write("machine,fault,component\n")
        for row in results:
            f.write("%s,%s,%s\n" % row)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
