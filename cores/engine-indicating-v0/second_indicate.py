#!/usr/bin/env python3
"""A second solution, written apart from the reference: python3 indicate.py PACKAGE_DIR OUT_CSV
Plain loops over cycles; the encoder's index error is found by simulating the motored compression."""
import csv, json, math, os, sys
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares
from scipy.interpolate import CubicSpline


class Engine:
    def __init__(self, d):
        self.b = d["bore_mm"] / 1000.0
        self.s = d["stroke_mm"] / 1000.0
        self.l = d["conrod_mm"] / 1000.0
        self.r = d["compression_ratio"]
        self.ivc = d["ivc_deg"]
        self.evo = d["evo_deg"]
        self.ncyl = d["cylinders"]
        self.k = d["bar_per_count"]
        self.vd = math.pi / 4 * self.b ** 2 * self.s

    def vol(self, deg):
        t = np.radians(deg)
        a = self.s / 2
        return self.vd / (self.r - 1) + math.pi / 4 * self.b ** 2 * (a * (1 - np.cos(t)) + self.l - np.sqrt(self.l ** 2 - (a * np.sin(t)) ** 2))

    def dvol(self, deg):
        t = np.radians(deg)
        a = self.s / 2
        return math.pi / 4 * self.b ** 2 * (a * np.sin(t) + a * a * np.sin(t) * np.cos(t) / np.sqrt(self.l ** 2 - (a * np.sin(t)) ** 2)) * math.pi / 180

    def area(self, v):
        return math.pi / 2 * self.b ** 2 + 4 * v / self.b


def g_u(t):
    return 1.375 - 6.99e-5 * t


def g_b(t):
    return 1.330 - 4.50e-5 * t


def wall_rate(eng, p, t, v, n, tw):
    """Wall heat per degree of crank angle (J/deg)."""
    cm = 2 * eng.s * n / 60
    h = 130.0 * v ** -0.06 * (p / 1e5) ** 0.8 * t ** -0.4 * (cm + 1.4) ** 0.8
    return h * eng.area(v) * (t - tw) / (6.0 * n)


def motored_model(eng, pt, f):
    """Pressure of a motored charge from IVC to EVO with the wall heat scaled by f, as a spline in crank angle."""
    mass = pt["pman"] * eng.vol(eng.ivc) / (287.0 * pt["tivc"])

    def rhs(th, y):
        v = eng.vol(th)
        t = y[0] * v / (mass * 287.0)
        g = g_u(t)
        return [(-g * y[0] * eng.dvol(th) - (g - 1) * f * wall_rate(eng, y[0], t, v, pt["n"], pt["tw"])) / v]

    grid = np.arange(eng.ivc, eng.evo + 1e-9, 0.25)
    sol = solve_ivp(rhs, (eng.ivc, eng.evo), [pt["pman"]], t_eval=grid, rtol=1e-9, atol=1e-3, method="DOP853")
    return CubicSpline(grid, sol.y[0])


def find_index_error(eng, mot, enc):
    """Least squares on the motored mean cycles over 70 degrees either side of top dead centre."""
    def resid(x):
        eps, f = x
        out = []
        for pt, mean in mot:
            model = motored_model(eng, pt, f)
            th = enc + eps
            use = (enc > -70) & (enc < 70)
            for cyl in range(eng.ncyl):
                out.append((mean[cyl][use] - model(th[use])) / pt["pman"])
        return np.concatenate(out)
    best = None
    for start in (-2.0, 0.0, 2.0):
        fit = least_squares(resid, [start, 1.0], diff_step=1e-3)
        if best is None or fit.cost < best.cost:
            best = fit
    return float(best.x[0])


def one_cycle(eng, pt, th, v, p, fired):
    """Results of one pegged cycle p (Pa) at crank angles th."""
    n = len(p)
    work = 0.0
    for i in range(n - 1):
        work += 0.5 * (p[i] + p[i + 1]) * (v[i + 1] - v[i])
    imep = work / eng.vd / 1e5
    top = 0
    for i in range(n):
        if p[i] > p[top]:
            top = i
    top = min(max(top, 10), n - 11)
    xs = np.array([0.5 * (i - top) for i in range(top - 10, top + 11)])
    c2, c1, c0 = np.polyfit(xs, p[top - 10:top + 11], 2)
    xv = -c1 / (2 * c2)
    res = [imep, (c0 + c1 * xv + c2 * xv * xv) / 1e5, th[top] + xv]
    if not fired:
        return res
    mass = pt["pman"] * eng.vol(eng.ivc) / (287.0 * pt["tivc"])
    idx = [i for i in range(n) if eng.ivc <= th[i] <= eng.evo]
    x = [0.0] * len(idx)
    q_last = None
    while True:
        q = [0.0]
        for j in range(len(idx) - 1):
            i = idx[j]
            pm = 0.5 * (p[i] + p[i + 1])
            vm = 0.5 * (v[i] + v[i + 1])
            tm = pm * vm / (mass * 287.0)
            xm = 0.5 * (x[j] + x[j + 1])
            g = (1 - xm) * g_u(tm) + xm * g_b(tm)
            dq = g / (g - 1) * pm * (v[i + 1] - v[i]) + vm * (p[i + 1] - p[i]) / (g - 1) + wall_rate(eng, pm, tm, vm, pt["n"], pt["tw"]) * 0.5
            q.append(q[-1] + dq)
        x = [min(max(qq / q[-1], 0.0), 1.0) for qq in q]
        if q_last is not None and abs(q[-1] - q_last) < 1e-5 * abs(q[-1]):
            break
        q_last = q[-1]
    for level in (0.1, 0.5):
        j = next(j for j in range(1, len(q)) if q[j] / q[-1] >= level)
        f0, f1 = q[j - 1] / q[-1], q[j] / q[-1]
        res.append(th[idx[j - 1]] + (level - f0) / (f1 - f0) * 0.5)
    res.append(q[-1])
    return res


def main():
    pkg, dst = sys.argv[1], sys.argv[2]
    every = int(os.environ.get("EVERY", "1"))      # for cut-down runs in the evidence only
    eng = Engine(json.load(open(os.path.join(pkg, "engine.json"))))
    enc = np.array([k / 2 - 180 for k in range(720)])
    pts = []
    for row in csv.DictReader(open(os.path.join(pkg, "points.csv"))):
        pt = dict(name=row["point"], fired=row["kind"] == "fired", n=float(row["speed_rpm"]), pman=float(row["p_man_bar"]) * 1e5,
                  tivc=float(row["t_ivc_K"]), tw=float(row["t_wall_K"]))
        raw = np.load(os.path.join(pkg, row["record"])).astype(float) * eng.k * 1e5
        raw = raw - raw[:, :, :20].mean(axis=2, keepdims=True) + pt["pman"]
        pt["p"] = raw
        pts.append(pt)
    mot = [(pt, pt["p"].mean(axis=1)) for pt in pts if not pt["fired"]]
    eps = find_index_error(eng, mot, enc) if mot else 0.0
    sys.stderr.write("index error %.3f deg\n" % eps)
    th = enc + eps
    v = eng.vol(th)
    with open(dst, "w") as out:
        out.write("point,cylinder,imep_bar,pmax_bar,apmax_deg,ca10_deg,ca50_deg,q_gross_J\n")
        for pt in pts:
            for cyl in range(eng.ncyl):
                acc = []
                for cyc in range(0, pt["p"].shape[1], every):
                    acc.append(one_cycle(eng, pt, th, v, pt["p"][cyl, cyc], pt["fired"]))
                mean = np.mean(np.array(acc), axis=0)
                cells = ["%.4f" % m for m in mean] + [""] * (6 - len(mean))
                out.write("%s,%d,%s\n" % (pt["name"], cyl + 1, ",".join(cells)))


if __name__ == "__main__":
    main()
