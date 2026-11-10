"""Sealed signal synthesis for vibration route packages. A machine is a dict (see gen2.py); capture() returns one
capture in g, tach() the optical tach pulse times.

Captures per point: low_r / low_a (16 s at 2560 Hz, radial horizontal and axial) and high_r (1 s, 25600 Hz planned).
Vertical pumps (kind VTP) have one point, MOT, with low_x / low_y / high_x.
"""
import numpy as np

G = 9.80665
LOW_FS, LOW_N = 2560.0, 40960
HIGH_FS, HIGH_N = 25600.0, 25600

BEARINGS = {
    "6309": ("deep groove ball", 8, 17.462, 72.5, 0.0),
    "6310": ("deep groove ball", 8, 19.050, 77.5, 0.0),
    "6311": ("deep groove ball", 8, 20.638, 85.0, 0.0),
    "6312": ("deep groove ball", 8, 22.225, 95.0, 0.0),
    "6313": ("deep groove ball", 8, 23.812, 100.0, 0.0),
    "6314": ("deep groove ball", 8, 25.400, 110.0, 0.0),
    "NU309": ("cylindrical roller", 13, 15.0, 72.0, 0.0),
    "NU310": ("cylindrical roller", 13, 16.0, 78.0, 0.0),
    "NU311": ("cylindrical roller", 13, 18.0, 87.0, 0.0),
    "NU312": ("cylindrical roller", 13, 19.0, 95.0, 0.0),
    "7310": ("angular contact ball", 13, 17.462, 77.5, 40.0),
    "7311": ("angular contact ball", 13, 19.05, 85.0, 40.0),
    "22213": ("spherical roller", 17, 14.0, 92.5, 10.0),
    "22216": ("spherical roller", 19, 15.0, 112.5, 10.0),
    "22218": ("spherical roller", 18, 17.5, 125.0, 10.0),
}


def defect_orders(code):
    _, n, d, D, a = BEARINGS[code]
    r = d / D * np.cos(np.radians(a))
    return dict(bpfo=n / 2 * (1 - r), bpfi=n / 2 * (1 + r), bsf=D / (2 * d) * (1 - r * r), ftf=0.5 * (1 - r))


def vel_to_g(v_mm_s, f):
    return v_mm_s * 1e-3 * 2 * np.pi * f / G


class Sig:
    def __init__(self, fs, n, rng):
        self.fs, self.n, self.rng = fs, n, rng
        self.t = np.arange(n) / fs
        self.x = np.zeros(n)

    def tone(self, f, v_mm_s):
        if 0 < f < self.fs / 2.2:
            self.x += vel_to_g(v_mm_s, f) * np.sin(2 * np.pi * f * self.t + self.rng.uniform(0, 2 * np.pi))

    def tone_g(self, f, a_g):
        if 0 < f < self.fs / 2.2:
            self.x += a_g * np.sin(2 * np.pi * f * self.t + self.rng.uniform(0, 2 * np.pi))

    def noise(self, rms):
        self.x += self.rng.normal(0, rms, self.n)

    def band_noise(self, f_lo, f_hi, rms):
        X = np.fft.rfft(self.rng.normal(0, 1, self.n))
        f = np.fft.rfftfreq(self.n, 1 / self.fs)
        X[(f < f_lo) | (f > f_hi)] = 0
        y = np.fft.irfft(X, self.n)
        self.x += rms * y / (y.std() + 1e-12)

    def impulses(self, rate, f_res, peak_g, tau=4e-4, jitter=0.01, mod=None):
        L = int(8 * tau * self.fs)
        tt = np.arange(L) / self.fs
        kern = np.exp(-tt / tau) * np.sin(2 * np.pi * min(f_res, 0.4 * self.fs) * tt)
        t = self.rng.uniform(0, 1 / rate)
        T = self.n / self.fs
        while t < T:
            i = int(t * self.fs)
            a = peak_g * (mod(t) if mod else 1.0) * (1 + self.rng.normal(0, 0.1))
            j = min(self.n, i + L)
            self.x[i:j] += a * kern[: j - i]
            t += (1 / rate) * (1 + self.rng.normal(0, jitter))


def element(m, point):
    return {"MOT": "motor", "PMP": "pump", "FAN": "fan", "CMP": "compressor", "GBX": "gearbox"}[point]


def capture(m, point, kind, seed, neighbours=None):
    """m: machine dict. point: point label as physically measured. kind: capture name."""
    rng = np.random.default_rng(seed)
    low = kind.startswith("low")
    fs = LOW_FS if low else m.get("high_fs_true", HIGH_FS)
    n = LOW_N if low else HIGH_N
    s = Sig(fs, n, rng)
    f1 = m["rpm"] / 60.0
    lf = m.get("vfd_hz", 60.0)
    axial = kind.endswith("_a")
    ydir = kind.endswith("_y")
    driven = point != "MOT"
    k = 0.45 if axial else 1.0
    kind_m = m["kind"]
    # baseline
    s.tone(f1, rng.uniform(0.6, 1.4) * k)
    s.tone(2 * f1, rng.uniform(0.2, 0.6) * k)
    s.tone(3 * f1, rng.uniform(0.05, 0.25) * k)
    if not driven:
        s.tone(2 * lf, rng.uniform(0.1, 0.4) * (0.4 if axial else 1.0))
    if m.get("vanes") and (driven or kind_m == "VTP"):
        s.tone(m["vanes"] * f1, rng.uniform(0.5, 1.2) * k)
    if kind_m == "CTF":
        fg = f1 * m["pinion_teeth"] / m["gear_teeth"]
        s.tone(fg, 0.5 * k)
        s.tone(m["blades"] * fg, 0.5 * k)
        if point == "GBX":
            s.tone_g(m["pinion_teeth"] * f1, rng.uniform(0.08, 0.15))
            s.tone_g(2 * m["pinion_teeth"] * f1, 0.04)
    if kind_m == "BF":
        ff = f1 * m["motor_sheave_mm"] / m["fan_sheave_mm"]
        s.tone(ff, (1.1 if driven else 0.4) * k)
        s.tone(m["blades"] * ff, (0.5 if driven else 0.1) * k)
    if kind_m == "SC" and driven:
        s.tone(m["lobes"] * f1, 0.8 * k)
        s.tone(2 * m["lobes"] * f1, 0.3 * k)
    if low:
        s.noise(0.006)
    else:
        s.noise(0.015)
        s.band_noise(2000, min(6000, 0.4 * fs), 0.01)

    fault, comp = m["fault"], m["component"]
    # shaft speed of the element the fault is in: a belt-driven fan turns at the sheave ratio
    fe_ = f1 * m["motor_sheave_mm"] / m["fan_sheave_mm"] if (kind_m == "BF" and comp == "fan") else f1
    at = {"motor": not driven, "pump": driven, "fan": driven, "compressor": driven, "coupling": True, "gear": True,
          "pinion": True, "belt": True, "structure": True, "none": True}[comp]
    tr = 1.0 if at else 0.45
    sev = m.get("severity", 1.0)
    if fault == "ELECTRICAL":
        s.tone(2 * lf, sev * (4.5 if not axial else 1.0) * (1.0 if not driven else 0.6))
    elif fault == "MISALIGNMENT":
        s.tone(2 * f1, sev * (3.8 if not axial else 1.1))
        s.tone(f1, sev * (1.6 if not axial else 0.9))
        s.tone(3 * f1, sev * 0.9 * k)
    elif fault == "UNBALANCE":
        s.tone(fe_, sev * (7.0 if not axial else 0.8) * tr)
    elif fault == "LOOSENESS":
        if not axial:
            for h, v in zip(range(1, 9), (3.0, 2.4, 2.0, 1.7, 1.4, 1.2, 1.0, 0.8)):
                s.tone(h * fe_, sev * v * tr)
            for h in (0.5, 1.5, 2.5, 3.5):
                s.tone(h * fe_, sev * 0.9 * tr)
    elif fault == "ROTOR_BAR":
        fp = m["poles"] * (2 * lf / m["poles"] - f1)
        s.tone(f1, sev * 3.2 * k * tr)
        for c in (f1, 2 * f1, 3 * f1):
            s.tone(c - fp, sev * 0.9 * k * tr)
            s.tone(c + fp, sev * 0.9 * k * tr)
    elif fault == "BELT":
        fb = np.pi * m["motor_sheave_mm"] * f1 / m["belt_length_mm"]
        for h, v in ((1, 1.6), (2, 3.0), (3, 1.1), (4, 0.6)):
            s.tone(h * fb, sev * v * k)
    elif fault == "RESONANCE":
        s.tone(f1, sev * (7.5 if not ydir else 1.4))
    elif fault == "GEAR_TOOTH":
        if point == "GBX":
            z1, z2 = m["pinion_teeth"], m["gear_teeth"]
            fm = z1 * f1
            fsb = f1 * z1 / z2 if comp == "gear" else f1
            for kk in range(1, 6):
                s.tone_g(fm - kk * fsb, sev * 0.06 * 0.75 ** kk)
                s.tone_g(fm + kk * fsb, sev * 0.06 * 0.75 ** kk)
            if not low:
                s.impulses(fsb, 2600.0, sev * 0.6, tau=5e-4, jitter=0.002)
    elif fault.startswith("BEARING_") and at:
        code = m["bearing_actual"]
        o = defect_orders(code)
        res = m.get("bearing_resonance", 3300.0)
        if fault == "BEARING_OUTER":
            if not low:
                s.impulses(o["bpfo"] * fe_, res, sev * 0.9)
            elif not axial:
                s.tone(o["bpfo"] * fe_, sev * 0.5)
        elif fault == "BEARING_INNER":
            ph = rng.uniform(0, 2 * np.pi)
            if not low:
                s.impulses(o["bpfi"] * fe_, res, sev * 1.0,
                           mod=lambda t: 0.6 + 0.4 * np.cos(2 * np.pi * fe_ * t + ph))
            elif not axial:
                s.tone(o["bpfi"] * fe_, sev * 0.4)
        elif fault == "BEARING_BALL":
            ph = rng.uniform(0, 2 * np.pi)
            ftf = o["ftf"] * fe_
            if not low:
                s.impulses(2 * o["bsf"] * fe_, res, sev * 0.9,
                           mod=lambda t: 0.55 + 0.45 * np.cos(2 * np.pi * ftf * t + ph))
            elif not axial:
                s.tone(2 * o["bsf"] * fe_, sev * 0.35)
        elif fault == "BEARING_CAGE":
            # a damaged cage rubs once per cage turn: bearing-resonance noise whose level swings at the cage rate
            # (envelope lines at FTF and 2 FTF only), and the FTF line itself in the velocity spectrum
            ftf = o["ftf"] * fe_
            if not low:
                X = np.fft.rfft(rng.normal(0, 1, n))
                ff = np.fft.rfftfreq(n, 1 / fs)
                X[np.abs(ff - res) > 600] = 0
                y = np.fft.irfft(X, n)
                y /= y.std()
                ph = rng.uniform(0, 2 * np.pi)
                s.x += sev * 0.25 * y * (1 + 0.8 * np.cos(2 * np.pi * ftf * s.t + ph) + 0.25 * np.cos(4 * np.pi * ftf * s.t))
            elif not axial:
                s.tone(ftf, sev * 1.2)
    elif fault == "CAVITATION":
        if driven and not low:
            times = np.cumsum(rng.exponential(1 / 900.0, 3000))
            times = times[times < n / fs]
            L = int(3e-4 * fs)
            for t0 in times:
                i = int(t0 * fs)
                j = min(n, i + L)
                s.x[i:j] += rng.normal(0, 1, j - i) * rng.exponential(0.35) * np.exp(-np.arange(j - i) / (0.6e-4 * fs))
        if driven and low and not axial:
            s.band_noise(150, 1200, 0.05)
            s.tone(m["vanes"] * f1, 1.6)
    # sensor cable fault at one point (data problem, not the machine's condition)
    if m.get("bad_sensor") == point:
        if low:
            X = np.fft.rfft(rng.normal(0, 1, n))
            ff = np.fft.rfftfreq(n, 1 / fs)
            X *= 1.0 / np.maximum(ff, 0.5) ** 1.6
            X[0] = 0
            y = np.fft.irfft(X, n)
            s.x += 0.15 * y / y.std()
        for t0 in np.sort(rng.uniform(0, n / fs, int(rng.integers(6, 12) * n / fs))):
            i = int(t0 * fs)
            j = min(n, i + int(0.002 * fs))
            s.x[i:j] += rng.choice([-1, 1]) * rng.uniform(1.5, 4.0) * np.exp(-np.arange(j - i) / (0.0004 * fs))
    # transmitted 1x of a neighbouring machine on the same skid
    if m.get("neighbour_rpm"):
        s.tone(m["neighbour_rpm"] / 60.0, 0.4 if axial else (4.6 if driven else 3.6))
    return s.x


def tach(m, seed):
    rng = np.random.default_rng(seed)
    f1 = m["rpm"] / 60.0
    T = LOW_N / LOW_FS
    t = rng.uniform(0, 1 / f1)
    out = []
    while t < T:
        out.append(t)
        if m.get("tach_marks") == 2:
            t2 = t + (m.get("mark_angle", 137.0) / 360.0) / f1
            if t2 < T:
                out.append(t2)
        t += (1 / f1) * (1 + rng.normal(0, 1e-4))
    return np.array(out)
