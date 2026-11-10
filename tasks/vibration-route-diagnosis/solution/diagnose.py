"""Route diagnosis program (reference).

    python3 diagnose.py ROUTE_DIR OUT_CSV

ROUTE_DIR is a route package: route.json, the <machine>_<point>.npz captures, <machine>_tach.csv, register.csv,
bearing_data.csv, maintenance_log.csv, process_snapshot.csv and <machine>_impact_test.csv. OUT_CSV gets
machine,fault,component for every machine in the register.

Every capture is checked before it is used: the tach's pulses per turn, the sample rate of the high capture, which
physical point a file holds, and whether the sensor channel is sound.
"""
import csv
import json
import os
import sys

import numpy as np

G = 9806.65                      # mm/s2 per g
ELEMENT = {"MOT": "motor", "PMP": "pump", "FAN": "fan", "CMP": "compressor", "GBX": "gearbox"}


# ---------------------------------------------------------------- spectra
def spec(x, fs):
    w = np.hanning(len(x))
    X = np.abs(np.fft.rfft((x - x.mean()) * w)) * 2 / w.sum()
    return np.fft.rfftfreq(len(x), 1 / fs), X


def vel(f, X):
    v = np.zeros_like(X)
    v[1:] = X[1:] * G / (2 * np.pi * f[1:])
    return v


def amp(f, A, f0, tol=0):
    if f0 <= 0 or f0 >= f[-1]:
        return 0.0
    i = int(round(f0 / (f[1] - f[0])))
    return float(A[max(i - tol, 1):i + tol + 1].max())


def prominent(f, A, f0, k=4.0, tol=0):
    if f0 <= 0 or f0 >= f[-1]:
        return False
    i = int(round(f0 / (f[1] - f[0])))
    loc = np.median(A[max(i - 30, 1):i + 31])
    return amp(f, A, f0, tol) > k * loc


def refine(f, A, f0):
    i = int(round(f0 / (f[1] - f[0])))
    i = i - 1 + int(np.argmax(A[i - 1:i + 2]))
    a, b, c = np.log(A[i - 1:i + 2] + 1e-15)
    den = a - 2 * b + c
    return f[i] + (0.5 * (a - c) / den if den != 0 else 0.0) * (f[1] - f[0])


def envelope(x, fs, lo=1500.0, hi=7000.0):
    n = len(x)
    X = np.fft.fft(x - x.mean())
    f = np.abs(np.fft.fftfreq(n, 1 / fs))
    X[(f < lo) | (f > min(hi, 0.45 * fs))] = 0
    h = np.zeros(n)
    h[0] = 1
    h[1:(n + 1) // 2] = 2
    if n % 2 == 0:
        h[n // 2] = 1
    e = np.abs(np.fft.ifft(X * h))
    return spec(e, fs)


# ---------------------------------------------------------------- route package
def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load(route_dir):
    meta = json.load(open(os.path.join(route_dir, "route.json")))
    caps = {}
    for c in meta["captures"]:
        z = np.load(os.path.join(route_dir, c["file"]))
        caps[(c["machine"], c["point"], c["capture"])] = [z[c["capture"]].astype(float) * c["g_per_count"],
                                                         float(c["sample_rate_hz"])]
    reg = {r["machine"]: r for r in read_csv(os.path.join(route_dir, "register.csv"))}
    brg = {r["designation"]: r for r in read_csv(os.path.join(route_dir, "bearing_data.csv"))}
    log = read_csv(os.path.join(route_dir, "maintenance_log.csv"))
    proc = {r["machine"]: r for r in read_csv(os.path.join(route_dir, "process_snapshot.csv"))}
    return caps, reg, brg, log, proc


def bearing_orders(b, ball_x2=True):
    n, d, D, a = int(b["rolling_elements"]), float(b["element_diameter_mm"]), float(b["pitch_diameter_mm"]), \
        float(b["contact_angle_deg"])
    r = d / D * np.cos(np.radians(a))
    return {"BEARING_OUTER": n / 2 * (1 - r), "BEARING_INNER": n / 2 * (1 + r),
            "BEARING_BALL": (2 if ball_x2 else 1) * D / (2 * d) * (1 - r * r), "BEARING_CAGE": 0.5 * (1 - r)}


# ---------------------------------------------------------------- data checks
def sensor_ok(x, fs):
    """A sound accelerometer channel has no low-frequency drift (ski slope) under the machine lines."""
    f, X = spec(x, fs)
    return np.median(vel(f, X)[(f > 0.7) & (f < 4)]) < 0.5        # mm/s; no machine line lies below 4 Hz


def high_fs(x, fs_planned, f1):
    """The high capture's true sample rate: the one at which its running-speed family lines up with f1."""
    best, score = fs_planned, 0
    for fs in (fs_planned, fs_planned * 0.8, fs_planned * 0.5, fs_planned * 0.625, fs_planned * 0.4):
        f, X = spec(x, fs)
        floor = np.median(X)
        s = sum(amp(f, X, k * f1, 1) > 10 * floor for k in (1, 2, 3))
        if s > score:
            best, score = fs, s
    return best


def sync_hz(r, drive_hz=60.0):
    return 2 * drive_hz / int(r["motor_poles"])


def tach_speed(path, r):
    t = np.array([float(q["pulse_time_s"]) for q in read_csv(path)])
    ft = (len(t) - 1) / (t[-1] - t[0])
    k = max(1, int(round(ft / (0.985 * sync_hz(r)))))      # more than one bright mark per turn
    return ft / k


def find_speed(m, r, caps, route_dir, pts):
    vtp = r["kind"].startswith("vertical")
    x, fs = caps[(m, pts[0], "low_x" if vtp else "low_r")]
    f, X = spec(x, fs)
    v = vel(f, X)
    tp = os.path.join(route_dir, "%s_tach.csv" % m.lower())
    if os.path.exists(tp):
        f0 = tach_speed(tp, r)
        return refine(f, v, f0) if abs(refine(f, v, f0) - f0) < 0.05 else f0, 60.0
    poles = int(r["motor_poles"])
    if "VFD" in r["drive"]:
        # motor 1x: the line whose drive line (2 x drive frequency, a few percent slip above poles x 1x) is present,
        # with the fan line at the sheave ratio for a belt drive
        ratio = float(r["motor_sheave_mm"]) / float(r["fan_sheave_mm"]) if r["motor_sheave_mm"] else None
        best, sc, bdrive = None, -1.0, 60.0
        nom = sync_hz(r)
        for i in np.where((f > 0.3 * nom) & (f < 1.02 * nom))[0]:
            fm = f[i]
            el, fd = 0.0, None
            for s_ in np.arange(0.003, 0.03, 0.001):
                a = amp(f, v, 2 * fm * poles / 2 / (1 - s_))
                if a > el:
                    el, fd = a, fm * poles / 2 / (1 - s_)
            s_ = v[i] * el * (amp(f, v, fm * ratio, 1) if ratio else 1.0)
            if s_ > sc:
                best, sc, bdrive = fm, s_, fd
        fm = refine(f, v, best)
        return fm, refine(f, v, 2 * bdrive) / 2
    band = (f > 0.95 * sync_hz(r)) & (f < 0.9995 * sync_hz(r))
    return refine(f, v, f[np.argmax(v * band)]), 60.0


def crossed(m, r, caps, f1, drive_hz):
    """True when the file labelled MOT holds the driven-machine bearing and the other file holds the motor."""
    pts = r["points"].split()
    if len(pts) != 2:
        return False
    xm, fs = caps[(m, pts[0], "low_r")]
    xd, _ = caps[(m, pts[1], "low_r")]
    fm, Xm = spec(xm, fs)
    fd, Xd = spec(xd, fs)
    vm, vd = vel(fm, Xm), vel(fd, Xd)
    lines = []
    if r["impeller_vanes"]:
        lines.append(int(r["impeller_vanes"]) * f1)
    if r["compressor_lobes"]:
        lines.append(int(r["compressor_lobes"]) * f1)
    if r["fan_sheave_mm"]:
        ff = f1 * float(r["motor_sheave_mm"]) / float(r["fan_sheave_mm"])
        lines += [ff] + ([int(r["fan_blades"]) * ff] if r["fan_blades"] else [])
    if r["gearbox_pinion_teeth"]:
        lines.append(int(r["gearbox_pinion_teeth"]) * f1)
    drv_m = sum(amp(fm, vm, q, 1) for q in lines)
    drv_d = sum(amp(fd, vd, q, 1) for q in lines)
    el_m, el_d = amp(fm, vm, 2 * drive_hz, 1), amp(fd, vd, 2 * drive_hz, 1)
    return drv_m > drv_d and el_d > 3 * el_m


# ---------------------------------------------------------------- diagnosis
def diagnose(route_dir):
    caps, reg, brg, log, proc = load(route_dir)
    out = {}
    for m, r in reg.items():
        vtp = r["kind"].startswith("vertical")
        kinds = ["low_x", "low_y", "high_x"] if vtp else ["low_r", "low_a", "high_r"]
        pts = r["points"].split()
        f1, drive_hz = find_speed(m, r, caps, route_dir, pts)
        if not vtp and crossed(m, r, caps, f1, drive_hz):
            for k in kinds:
                caps[(m, pts[0], k)], caps[(m, pts[1], k)] = caps[(m, pts[1], k)], caps[(m, pts[0], k)]
        good = [p for p in pts if all(sensor_ok(*caps[(m, p, k)]) for k in kinds if k.startswith("low"))]
        if good and good != pts:
            f1, drive_hz = find_speed(m, r, caps, route_dir, good)
        pts_ok = good or pts
        poles = int(r["motor_poles"])
        ratio = float(r["motor_sheave_mm"]) / float(r["fan_sheave_mm"]) if r["fan_sheave_mm"] else 1.0
        shaft = {p: (f1 * ratio if p == "FAN" else f1) for p in pts}    # speed of the shaft at each point
        F = {}
        for p in pts_ok:
            x, fs = caps[(m, p, kinds[0])]
            f, X = spec(x, fs)
            v = vel(f, X)
            fs_ = shaft[p]
            fe = dict(f=f, v=v, X=X, one=amp(f, v, fs_), two=amp(f, v, 2 * f1))
            fe["half"] = max(amp(f, v, h * fs_) if prominent(f, v, h * fs_, 5) else 0.0 for h in (0.5, 1.5, 2.5))
            if vtp:
                xy, fsy = caps[(m, p, "low_y")]
                fy, Xy = spec(xy, fsy)
                fe["one_y"] = amp(fy, vel(fy, Xy), f1)
            F[p] = fe
        mot = F.get("MOT")
        res = None
        # electrical: 2 x drive frequency at the motor, distinct from 2x running speed
        if mot is not None and amp(mot["f"], mot["v"], 2 * drive_hz) > 2.5 and \
                abs(2 * drive_hz - 2 * f1) > 2.5 * (mot["f"][1] - mot["f"][0]):
            res = ("ELECTRICAL", "motor")
        # rotor bars: pole-pass sidebands around 1x at the motor
        fp = poles * (sync_hz(r, drive_hz) - f1)
        if res is None and mot is not None and fp > 0.25:
            sb = min(amp(mot["f"], mot["v"], f1 - fp), amp(mot["f"], mot["v"], f1 + fp))
            if sb > 0.45 and prominent(mot["f"], mot["v"], f1 - fp, 4) and prominent(mot["f"], mot["v"], f1 + fp, 4):
                res = ("ROTOR_BAR", "motor")
        # belt: belt frequency family at the actual speed
        if res is None and r["belt_length_mm"]:
            fb = np.pi * float(r["motor_sheave_mm"]) * f1 / float(r["belt_length_mm"])
            if max(max(amp(fe["f"], fe["v"], h * fb, 1) for h in (1, 2, 3)) for fe in F.values()) > 1.0:
                res = ("BELT", "belt")
        # looseness: half orders on a long harmonic series
        if res is None:
            p = max(F, key=lambda q: F[q]["half"])
            if F[p]["half"] > 0.5:
                res = ("LOOSENESS", ELEMENT[p] if p != "GBX" else "gearbox")
        # misalignment: 2x running speed high across the coupling
        if res is None and r["drive"].startswith("direct") or r["drive"].startswith("right-angle"):
            if res is None and not vtp and max(fe["two"] for fe in F.values()) > 2.5:
                res = ("MISALIGNMENT", "coupling")
        # gear: mesh sidebands, spacing = pinion (input) or gear (output) speed
        if res is None and r["gearbox_pinion_teeth"] and "GBX" in F:
            z1, z2 = int(r["gearbox_pinion_teeth"]), int(r["gearbox_gear_teeth"])
            f, X = F["GBX"]["f"], F["GBX"]["X"]
            fm, fg = z1 * f1, f1 * z1 / z2
            sg = sum(amp(f, X, fm + s_ * k * fg) for k in (1, 2) for s_ in (-1, 1))
            sp = sum(amp(f, X, fm + s_ * k * f1) for k in (1, 2) for s_ in (-1, 1))
            if max(sg, sp) > 0.03:
                res = ("GEAR_TOOTH", "gear" if sg > sp else "pinion")
        # rolling-element bearings: envelope lines at a defect frequency of the bearing actually fitted
        if res is None:
            best = None
            for p in pts_ok:
                col = "motor_bearings_de_nde" if p == "MOT" else "driven_bearings_de_nde"
                if not r[col]:
                    continue
                code = r[col].split("/")[0]
                pos = "Motor DE" if p == "MOT" else "DE"
                for e in log:
                    if e["machine"] == m and "bearing replaced" in e["entry"] and "issued" in e["entry"] and \
                            ((p == "MOT") == e["entry"].startswith("Motor")):
                        code = e["entry"].split("issued ")[1].split(".")[0].split()[0].replace(" ", "")
                if code not in brg:
                    continue
                xh, fsn = caps[(m, p, kinds[2])]
                fe_, E = envelope(xh, high_fs(xh, fsn, f1))
                floor = np.median(E[(fe_ > 3) & (fe_ < 600)])
                for kind, o in bearing_orders(brg[code]).items():
                    a1, a2 = amp(fe_, E, o * shaft[p], 1), amp(fe_, E, 2 * o * shaft[p], 1)
                    score = min(a1 / floor, 2 * a2 / floor)
                    if a1 > 8 * floor and a2 > 4 * floor and (best is None or score > best[0]):
                        best = (score, kind, "motor" if p == "MOT" else ELEMENT[p])
            if best:
                res = (best[1], best[2])
        # cavitation: NPSH margin negative and random impacts at the pump
        if res is None and m in proc and proc[m]["npsh_available_m"] and "PMP" in F:
            pr = proc[m]
            xh, _ = caps[(m, "PMP", kinds[2])]
            kurt = ((xh - xh.mean()) ** 4).mean() / xh.var() ** 2
            if float(pr["npsh_available_m"]) < float(pr["npsh_required_m"]) and kurt > 4:
                res = ("CAVITATION", "pump")
        # 1x dominated: resonance (one direction, natural frequency at 1x) or unbalance
        if res is None:
            p = max(F, key=lambda q: F[q]["one"])
            if F[p]["one"] > 3.5:
                if vtp:
                    rows = read_csv(os.path.join(route_dir, "%s_impact_test.csv" % m.lower()))
                    fr = np.array([float(q["frequency_hz"]) for q in rows])
                    hx = np.array([float(q["x_response_rel"]) for q in rows])
                    fn = fr[np.argmax(hx)]
                    if abs(fn / f1 - 1) < 0.08 and F[p]["one"] > 3 * F[p]["one_y"]:
                        res = ("RESONANCE", "structure")
                if res is None:
                    res = ("UNBALANCE", ELEMENT[p] if p != "GBX" else "gearbox")
        out[m] = res or ("NONE", "none")
    return out


def main():
    route_dir, out = sys.argv[1], sys.argv[2]
    d = diagnose(route_dir)
    with open(out, "w") as f:
        f.write("machine,fault,component\n")
        for m, (a, b) in d.items():
            f.write("%s,%s,%s\n" % (m, a, b))


if __name__ == "__main__":
    main()
