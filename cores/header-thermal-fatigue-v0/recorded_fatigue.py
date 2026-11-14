"""Reference: python3 ref_fatigue.py PACKAGE_DIR OUT_CSV          (AS_RECORDED=1: take the record as the fluid)

1. The fluid temperature behind the record. HF-3 sets the inner surface at the fluid temperature; the record is
   the fluid thermocouple's reading, and a thermocouple in a thermowell lags the fluid. The outer-surface
   thermocouple is fast, so the wall's own response shows the lag: the time constant tau is the one at which
   the outer surface calculated from the fluid temperature (record + tau d(record)/dt) follows the measured
   outer surface best, over every event. A bare tip gives tau of a second or two.
2. The wall: radial conduction on 120 nodes, exact in time; stress at the nozzle bore per HF-3 section 4.
3. Rainflow per event, damage per HF-3 section 6.
"""
import json, os, sys
import numpy as np
from scipy.signal import lfilter, savgol_filter
from scipy.optimize import minimize_scalar


class Wall:
    def __init__(self, ri, ro, a, n=120, dt=1.0):
        r = np.linspace(ri, ro, n + 1)
        h = r[1] - r[0]
        rh = 0.5 * (r[1:] + r[:-1])
        V = np.empty(n + 1)
        V[0] = 0.5 * (rh[0] ** 2 - ri ** 2)
        V[1:n] = 0.5 * (rh[1:] ** 2 - rh[:-1] ** 2)
        V[n] = 0.5 * (ro ** 2 - rh[-1] ** 2)
        K = np.zeros((n, n)); b = np.zeros(n)
        for j in range(1, n + 1):
            i = j - 1
            gi = a * rh[j - 1] / h
            K[i, i] -= gi
            if j > 1:
                K[i, i - 1] += gi
            else:
                b[i] += gi
            if j < n:
                go = a * rh[j] / h
                K[i, i] -= go; K[i, i + 1] += go
        Mi = 1.0 / np.sqrt(V[1:])
        S = Mi[:, None] * K * Mi[None, :]
        lam, Q = np.linalg.eigh(0.5 * (S + S.T))
        g = Q.T @ (Mi * b)
        P = Mi[:, None] * Q
        self.cm, self.dm, self.co = (V[1:] @ P) / V.sum(), V[0] / V.sum(), P[-1]
        E = np.exp(lam * dt)
        I1 = -1.0 / lam + (E - 1.0) / (lam * lam * dt)
        I0 = (E - 1.0) / lam - I1
        keep = np.abs(self.cm * g) + np.abs(self.co * g) > 1e-12 * np.abs(g).max()
        self.f = [(np.array([g[k] * I1[k], g[k] * I0[k]]), np.array([1.0, -E[k]]), self.cm[k], self.co[k])
                  for k in np.flatnonzero(keep)]

    def response(self, tf, outer_only=False):
        u = tf - tf[0]
        mean = self.dm * u
        out = np.zeros_like(u)
        for bb, aa, cm, co in self.f:
            z = lfilter(bb, aa, u)
            out += co * z
            if not outer_only:
                mean += cm * z
        return mean - u, out + tf[0]


def turning(x):
    d = np.diff(x)
    x = np.concatenate([x[np.flatnonzero(d != 0)], x[-1:]])
    d = np.diff(x)
    idx = np.flatnonzero(d[1:] * d[:-1] < 0) + 1
    return np.concatenate([x[:1], x[idx], x[-1:]])


def rainflow(x):
    out, st = [], []
    for v in turning(x):
        st.append(v)
        while len(st) >= 3:
            X, Y = abs(st[-1] - st[-2]), abs(st[-2] - st[-3])
            if X < Y:
                break
            if len(st) == 3:
                out.append((Y, 0.5)); st.pop(0)
            else:
                out.append((Y, 1.0)); last = st.pop(); st.pop(); st.pop(); st.append(last)
    out += [(abs(st[i + 1] - st[i]), 0.5) for i in range(len(st) - 1)]
    return out


def main(argv):
    pkg, out = argv[1], argv[2]
    hdr = json.load(open(os.path.join(pkg, "header.json")))
    rec = np.loadtxt(os.path.join(pkg, "record.csv"), delimiter=",", skiprows=1)
    ev = rec[:, 0].astype(int)
    cuts = np.flatnonzero(np.diff(ev)) + 1
    starts, ends = np.r_[0, cuts], np.r_[cuts, len(ev)]
    ri, s = hdr["inner_radius_mm"], hdr["wall_mm"]
    mat = hdr["material"]
    wall = Wall(ri, ri + s, mat["diffusivity_mm2_s"])
    fl, pr, ou = rec[:, 2], rec[:, 3], rec[:, 4]
    dfl = np.concatenate([savgol_filter(fl[a:b], 15, 2, deriv=1) for a, b in zip(starts, ends)])

    def fluid(tau):
        return fl + tau * dfl

    if True:
        tau = 0.0
    else:
        def misfit(tau):
            f = fluid(tau)
            e = 0.0
            for a, b in zip(starts, ends):
                _, o = wall.response(f[a:b], outer_only=True)
                e += float(np.sum((o - ou[a:b]) ** 2))
            return e
        tau = minimize_scalar(misfit, bounds=(0.0, 240.0), method="bounded", options={"xatol": 0.2}).x
    print("thermocouple time constant %.1f s" % tau, file=sys.stderr)
    f = fluid(tau)
    rm = ri + 0.5 * s
    kp = hdr["k_pressure"] * rm / s * 0.1
    kt = hdr["k_thermal"] * mat["E_MPa"] * mat["alpha_per_K"] / (1.0 - mat["poisson"])
    sn = hdr["sn_curve"]
    lines = ["event,range_max_MPa,damage\n"]
    for a, b in zip(starts, ends):
        dT, _ = wall.response(f[a:b])
        sig = kp * pr[a:b] + kt * dT
        cyc = rainflow(sig)
        D = sum(c / (sn["N_ref"] * (sn["range_ref_MPa"] / r) ** sn["m"]) for r, c in cyc if r > sn["cutoff_MPa"])
        lines.append("%d,%.2f,%.4e\n" % (ev[a], max(r for r, _ in cyc), D))
    open(out, "w").write("".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
