#!/usr/bin/env python3
"""BC-3 conveyor drive loads from a line package.  Usage: drives.py LINE_DIR OUT_CSV"""
import sys, os, json, math
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

G = 9.80665
N0 = 1500.0
ORDER = {"tail": 0, "head2": 1, "head1": 2}


class Flight:
    def __init__(self, name, fr, prof, drv):
        self.name = name
        self.mB = fr.belt_kg_m
        self.mc = fr.idlers_carry_kg_m
        self.mr = fr.idlers_return_kg_m
        self.C = fr.secondary_factor
        self.K = fr.belt_stiffness_MN * 1e6
        self.Tt = fr.take_up_tension_kN * 1e3
        prof = prof.sort_values("section")
        self.l = prof.length_m.values.astype(float)
        self.h = prof.rise_m.values.astype(float)
        self.L = self.l.sum()
        self.H = self.h.sum()
        self.bounds = np.concatenate([[0.0], np.cumsum(self.l)])  # x from tail
        drv = drv.copy()
        drv["o"] = drv.drive.map(ORDER)
        drv = drv.sort_values("o")
        self.names = list(drv.drive)
        self.Pr = drv.rated_kW.values * 1e3
        self.i = drv.gear_ratio.values.astype(float)
        self.D = drv.pulley_diameter_mm.values / 1e3
        self.e = drv.efficiency.values.astype(float)
        self.sr = np.full(len(self.names), 0.02)
        self.f = 0.02

    def v0(self):
        return math.pi * self.D * N0 / (60.0 * self.i)

    def solve(self, q, Mtot, Mgrad, vg):
        """q kg/s, Mtot kg, Mgrad = sum M_j h_j/l_j. Returns v, P(W), traction."""
        v0 = self.v0()
        A = self.e * self.Pr / (self.sr * v0)
        Rr = self.C * self.f * G * self.L * (self.mB + self.mr)
        Ttail = self.Tt + Rr - self.mB * G * self.H
        Fc = self.C * self.f * G * (self.L * (2 * self.mB + self.mc + self.mr) + Mtot) + G * Mgrad
        names = self.names
        K, Tt = self.K, self.Tt

        def forces(v):
            F = np.zeros(len(names))
            Ton = np.zeros(len(names))
            Tcur = Tt
            for k, n in enumerate(names):
                a = A[k] * (1 - v / v0[k])
                b = A[k] * v / (K * v0[k])
                if n == "tail":
                    Ton[k] = Ttail
                    F[k] = a - b * Ttail
                else:
                    F[k] = (a - b * Tcur) / (1 + b)
                    Tcur = Tcur + F[k]
                    Ton[k] = Tcur
            return F, Ton

        def r(v):
            F, _ = forces(v)
            return F.sum() - Fc - q * v

        v = vg
        r0 = r(v)
        for _ in range(30):
            dv = 1e-6
            d = (r(v + dv) - r0) / dv
            vn = v - r0 / d
            if abs(vn - v) < 1e-12:
                v = vn
                break
            v = vn
            r0 = r(v)
        F, Ton = forces(v)
        Toff = Ton - F
        trac = np.maximum(Ton, Toff) / np.minimum(Ton, Toff)
        P = F * v0 / self.e
        return v, P, Ton, Ttail, trac


def calibrate(fl, sv):
    sv = sv[sv.flight == fl.name]
    camps = sorted(sv.campaign.unique())
    nd = len(fl.names)
    data = []
    for c in camps:
        s = sv[sv.campaign == c].set_index("drive")
        data.append((s.feed_t_h.iloc[0] / 3.6, s.belt_speed_m_s.iloc[0],
                     s.loc[fl.names, "input_rpm"].values, s.loc[fl.names, "motor_kW"].values * 1e3))
    # initial s_r from direct readings
    sr0 = []
    for k in range(nd):
        ss = np.array([1 - d[2][k] / N0 for d in data])
        pp = np.array([d[3][k] for d in data])
        sr0.append(fl.Pr[k] * (ss @ ss) / (ss @ pp))
    D0 = fl.D.copy()

    def setp(p):
        fl.f = p[0]
        fl.sr = np.array(p[1:1 + nd])
        fl.D = D0 * (1 + np.array(p[1 + nd:]))

    def res(p):
        setp(p)
        out = []
        for q, vw, rpm, P in data:
            vg = vw
            for _ in range(3):
                v, Pm, Ton, Ttail, _t = fl.solve(q, q / vg * fl.L, q / vg * fl.H, vw)
                vg = v
            # loading-point tension: tension leaving tail
            Tload = Ttail - (Pm[0] * fl.e[0] / fl.v0()[0] if fl.names[0] == "tail" else 0.0)
            vwm = v * (1 + Tload / fl.K)
            u = v * (1 + Ton / fl.K)
            rpmm = u * 60 * fl.i / (math.pi * fl.D)
            out.append((vwm - vw) / (0.0005 * vw))
            out.extend((rpmm - rpm) / 0.1)
            out.extend((Pm - P) / (0.005 * np.maximum(np.abs(P), 1e3)))
        return np.array(out)

    p0 = np.concatenate([[0.02], sr0, np.zeros(nd)])
    sol = least_squares(res, p0, x_scale=np.concatenate([[0.005], np.array(sr0) * 0.1, np.full(nd, 1e-3)]))
    setp(sol.x)
    return sol


class Belt:
    """Load on belt as cumulative mass vs belt coordinate (piecewise linear)."""

    def __init__(self, n):
        self.S = np.zeros(n + 2)
        self.Mc = np.zeros(n + 2)
        self.n = 1

    def add(self, S1, m):
        self.S[self.n] = S1
        self.Mc[self.n] = self.Mc[self.n - 1] + m
        self.n += 1

    def cum(self, x):
        n = self.n
        return np.interp(x, self.S[:n], self.Mc[:n])


def run(line_dir):
    meta = json.load(open(os.path.join(line_dir, "line.json")))
    fr = pd.read_csv(os.path.join(line_dir, "flights.csv")).set_index("flight")
    prof = pd.read_csv(os.path.join(line_dir, "profile.csv"))
    drv = pd.read_csv(os.path.join(line_dir, "drives.csv"))
    sv = pd.read_csv(os.path.join(line_dir, "surveys.csv"))
    feed = pd.read_csv(os.path.join(line_dir, "feed.csv")).sort_values("step").feed_t_h.values / 3.6
    dt = float(meta["step_s"])
    nI = int(meta["interval_steps"])
    N = len(feed)
    rows = []
    qin = feed.astype(float)
    for name in meta["flights"]:
        fl = Flight(name, fr.loc[name], prof[prof.flight == name], drv[drv.flight == name])
        calibrate(fl, sv)
        belt = Belt(N)
        S = 0.0
        v = fl.solve(0, 0, 0, 5.0)[0]
        nd = len(fl.names)
        Ps = np.zeros((N, nd))
        Tr = np.zeros((N, nd))
        qout = np.zeros(N)
        grad = fl.h / fl.l
        for k in range(N):
            # load currently on flight: belt coords [S-L, S]; x = S - s
            pts = S - fl.bounds  # coords of section boundaries (tail..head)
            c = belt.cum(pts)
            Mj = c[:-1] - c[1:]
            q = qin[k]
            v, P, Ton, Ttail, trac = fl.solve(q, Mj.sum(), (Mj * grad).sum(), v)
            Ps[k] = P
            Tr[k] = trac
            S1 = S + v * dt
            belt.add(S1, q * dt)
            # mass passing head during step
            qout[k] = (belt.cum(S1 - fl.L) - c[-1]) / dt
            S = S1
        qin = qout
        for k, dn in enumerate(fl.names):
            for j in range(0, N, nI):
                p = Ps[j:j + nI, k] / 1e3
                rows.append(("%s-%s-%03d" % (name, dn, j // nI + 1), p.mean(), p.max(), p.min(),
                             Tr[j:j + nI, k].max()))
    return pd.DataFrame(rows, columns=["row", "mean_kW", "max_kW", "min_kW", "traction_peak"])


if __name__ == "__main__":
    df = run(sys.argv[1])
    df.to_csv(sys.argv[2], index=False, float_format="%.6f")
