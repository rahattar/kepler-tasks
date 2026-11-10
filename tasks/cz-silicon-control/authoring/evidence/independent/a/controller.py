"""PS-R07 supervisory controller for Puller 11 / HZ-B.

Pull rate: PS-R07 growth-rate program plus a feedforward that cancels the meniscus transient caused by the
crucible-rotation steps (so the growth rate, not the pull rate, stays on the program), plus a small trim.
Heater: model predictive control of the true diameter, using a Kalman filter on (meniscus deviation, true diameter,
lumped growth offset) built on the HZ-B model identified from bodies B2411-B2418:
transport delay ~28 min, lags ~32 / 6 min, kh0 0.36 K/kW, rotation effect -0.0145 mm/min/rpm (~6 min settle),
meniscus coefficient 0.30 1/min, camera offset +0.80 mm vs caliper.
The pull feedforward covers every modelled change of the growth drive (rotation steps, heater moves, v0(L)),
so the growth rate stays on the program while the meniscus absorbs the change; the heater MPC then steers the
diameter (ramp from the start diameter to 302.25 mm over 300 mm, soft floor 301.9 mm).
"""
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_rec = np.genfromtxt(os.path.join(HERE, 'perfect_si_r07.csv'), delimiter=',', names=True)
RL = _rec['length_mm']; RV = _rec['growth_rate_program_mm_min']; RR = _rec['crucible_rpm']

DELAY = 28; T1 = 32.0; T2 = 6.0; KH0 = 0.36; KR = -0.0145; TR = 6.2; KM = 0.30; OFF = 0.80; RLAG = 1
DREF = 302.25; DLOW = 301.9; D_START = 304.0; L_DESC = 300.0; WV = 2.0; LAM = 0.5; WLOW = 30.0
H = 240; NB = 12; BLK = 20


def v0(L): return 0.98 - 0.10 * (1 - np.exp(-L / 400.0)) - 0.04 * L / 1500.0
def p0(L): return 100 - 14 * L / 1500.0
def prog(L): return np.interp(L, RL, RV)
def rpm_at(L):
    i = np.searchsorted(RL, L, side='right') - 1
    return RR[np.clip(i, 0, len(RR) - 1)]
def kh(L): return KH0 * (1 + 0.6 * L / 1500.0)


class Controller:
    def __init__(self):
        self.k = 0

    def _init(self, m):
        L = m['length_mm']; P = m['heater_power_kw']
        self.Phist = [P] * (DELAY + 1)
        u = P - p0(L)
        self.x1 = self.x2 = u
        self.rf = m['crucible_rpm_set']; self.rset = self.rf
        self.x = np.array([0.0, m['camera_diameter_mm'] - OFF, 0.0])  # e, D, dist
        self.dist0 = prog(L) - v0(L) - KR * (self.rf - 8) + 0.05 * kh(L) * self.x2
        self.Pc = np.diag([0.15 ** 2, 0.3 ** 2, 0.01 ** 2])
        self.Pcmd = P; self.vcmd = m['pull_rate_mm_min']
        self.du = np.zeros(NB)
        self.Dstart = self.x[1]

    def bknown(self, L, rf, x2):
        return v0(L) + KR * (rf - 8) + self.dist0 - 0.05 * kh(L) * x2

    def step(self, meas):
        try:
            return self._step(meas)
        except Exception:
            L = float(meas.get('length_mm', 0.0))
            Pl = getattr(self, 'Pcmd', None)
            if Pl is None:
                Pl = float(meas.get('heater_power_kw', 100.0))
            self.k += 1
            return float(prog(L)), float(Pl)

    def _step(self, m):
        if self.k == 0:
            self._init(m)
        L = m['length_mm']; cam = m['camera_diameter_mm']
        vp = m['pull_rate_mm_min']; P = m['heater_power_kw']
        # ---- Kalman measurement update
        Hm = np.array([-1.2, 1.0, 0.0])
        yhat = self.x[1] + OFF - 1.2 * self.x[0]
        S = Hm @ self.Pc @ Hm + 0.15 ** 2
        K = self.Pc @ Hm / S
        r = cam - yhat
        self.x = self.x + K * r
        self.Pc = self.Pc - np.outer(K, Hm @ self.Pc)
        e, D, dist = self.x
        rset = m['crucible_rpm_set']
        # ---- controller outputs
        if self.k % 2 == 0:
            self.Pmpc = self._mpc(L, vp, P)
        Pset = self.Pmpc
        vset = self._pull(L, rset)
        self.Pcmd = Pset; self.vcmd = vset
        # ---- time update (one minute, using actual drive values; drives slew toward setpoints)
        self.Phist.append(P)
        Pd = self.Phist[-1 - DELAY]
        nsub = 4; h = 0.25
        rtgt = rset if RLAG == 0 else self.rset
        Fsum = np.eye(3)
        for _ in range(nsub):
            u = Pd - p0(L)
            self.x1 += h * (u - self.x1) / T1
            self.x2 += h * (self.x1 - self.x2) / T2
            self.rf += (rtgt - self.rf) * (1 - np.exp(-h / TR))
            b = self.bknown(L, self.rf, self.x2) + self.x[2]
            e, D, dist = self.x
            vg = b + KM * e
            F = np.array([[1 - h * KM, 0, -h], [-h * 0.48 * (vg + KM * e), 1, -h * 0.48 * e], [0, 0, 1]])
            self.x = np.array([e + h * (vp - vg), D - h * 0.48 * vg * e, dist])
            Fsum = F @ Fsum
        Q = np.diag([0.003 ** 2, 0.002 ** 2, 0.0015 ** 2])
        self.Pc = Fsum @ self.Pc @ Fsum.T + Q
        self.rset = rset
        self.k += 1
        return float(vset), float(Pset)

    def _pull(self, L, rset_now):
        # Growth stays on the program if the meniscus deviation follows e* = (program - b) / KM, where b is
        # the modelled growth drive (rotation, heater through its delay and lags, v0(L)).  The pull therefore
        # runs ahead of the program by de*/dt; both ends of the coming minute are predicted with the model.
        v = prog(L)
        tgt = rset_now if RLAG == 0 else self.rset
        Pd = self.Phist[-DELAY]
        x1, x2, rf = self.x1, self.x2, self.rf
        b_a = self.bknown(L, rf, x2)
        es_a = (prog(L) - b_a) / KM
        for _ in range(4):
            x1 += 0.25 * (Pd - p0(L) - x1) / T1
            x2 += 0.25 * (x1 - x2) / T2
            rf += (tgt - rf) * (1 - np.exp(-0.25 / TR))
        L1 = L + v
        b_b = self.bknown(L1, rf, x2)
        es_b = (prog(L1) - b_b) / KM
        return prog(L + 0.5 * v) + (es_b - es_a)

    def _mpc(self, L, vp, P):
        # vectorised simulation of base + NB block perturbations
        n = NB + 1
        e = np.full(n, self.x[0]); D = np.full(n, self.x[1]); dist = self.x[2]
        x1 = np.full(n, self.x1); x2 = np.full(n, self.x2); rf = self.rf; rset = self.rset
        Pfut = np.zeros((n, H + 1)) + self.Pcmd
        eps = 1.0
        for j in range(NB):
            Pfut[j + 1, j * BLK:] += eps
        Phist = self.Phist + [P]
        Lp = L
        Dtraj = np.zeros((n, H)); Vtraj = np.zeros((n, H)); Vp = np.zeros(H)
        for t in range(H):
            idx = len(Phist) - 1 - DELAY + t
            if idx < len(Phist):
                Pd = Phist[idx]
            else:
                Pd = Pfut[:, idx - len(Phist)]
            v = prog(Lp)
            r_new = rpm_at(Lp)
            u = Pd - p0(Lp)
            x1 = x1 + (u - x1) / T1
            x2 = x2 + (x1 - x2) / T2
            rf = rf + (rset - rf) / TR
            rset = r_new
            b = v0(Lp) + KR * (rf - 8) + self.dist0 + dist - 0.05 * kh(Lp) * x2
            es = (v - b) / KM
            ff = 0.0 if t == 0 else es - es_old
            es_old = es
            for _ in range(2):
                vg = b + KM * e
                e = e + 0.5 * (v + ff - vg)
                D = D - 0.5 * 0.48 * vg * e
                Vtraj[:, t] += 0.5 * vg
            Dtraj[:, t] = D; Vp[t] = v
            Lp += v
        base = Dtraj[0]; G = (Dtraj[1:] - base).T / eps  # H x NB
        vbase = Vtraj[0]; GV = (Vtraj[1:] - vbase).T / eps
        Lf = L + np.cumsum(Vp)
        ref = DREF + (self.Dstart - DREF) * np.clip(1 - Lf / L_DESC, 0, 1)
        w = np.ones(H); w[:20] = 0.3
        wv = WV * 100 / Vp  # per-cent growth deviation
        A = np.vstack([G * w[:, None], GV * wv[:, None],
                       np.sqrt(LAM) * (np.eye(NB) - np.eye(NB, k=-1)), 0.05 * np.eye(NB)])
        bb = np.concatenate([(ref - base) * w, (Vp - vbase) * wv, np.zeros(NB), np.zeros(NB)])
        du = np.linalg.lstsq(A, bb, rcond=None)[0]
        for _ in range(3):
            pred = base + G @ du
            low = pred < DLOW
            if not low.any():
                break
            wl = np.where(low, WLOW, 0.0)
            A2 = np.vstack([A, G * wl[:, None]])
            b2 = np.concatenate([bb, (DLOW + 0.1 - base) * wl])
            du = np.linalg.lstsq(A2, b2, rcond=None)[0]
        Pset = self.Pcmd + du[0]
        return float(np.clip(Pset, 60, 140))
