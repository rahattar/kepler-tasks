"""Puller 11 / HZ-B supervisory controller for perfect-silicon recipe PS-R07.

Pull rate: holds the growth rate on the PS-R07 program: program + feedforward of the meniscus
height change needed as the melt-side terms move (crucible-rotation steps, superheat changes).
Heater: model predictive control of the true diameter (heater -> superheat -> meniscus height
-> diameter), with the rotation schedule known ahead so the superheat change that cancels each
rotation step is placed in advance.
State: Kalman filter on camera + pyrometer. States: true diameter D, meniscus height deviation dh,
growth bias b, superheat gain factor g, superheat model error sc, pyrometer drift pd and its rate pv.
Model constants (camera offset, heater->superheat delay/lags, kh0, rotation coefficient and settling)
were identified from the HZ-B logs B2411-B2418 (params.json).
"""
import os, json
import numpy as np

_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_DIR, 'params.json')) as f:
    PRM = json.load(f)
_rec = np.genfromtxt(os.path.join(_DIR, 'perfect_si_r07.csv'), delimiter=',', names=True)
_RL = _rec['length_mm']; _RV = _rec['growth_rate_program_mm_min']; _RR = _rec['crucible_rpm']

A_M = np.exp(-0.3)
B_M = (1 - A_M) / 0.3


def prog(L):
    return np.interp(L, _RL, _RV)


def rpm_at(L):
    i = np.clip(np.searchsorted(_RL, L, side='right') - 1, 0, len(_RL) - 1)
    return _RR[i]


def v0(L):
    L = np.asarray(L, dtype=float)
    return 0.98 - 0.10 * (1 - np.exp(-L / 400.0)) - 0.04 * L / 1500.0


def p0(L):
    return 100.0 - 14.0 * np.asarray(L, dtype=float) / 1500.0


def _ff_shape(d, t1, t2, trot, slew_units, lam, wS, T0=200, N=420, blk=5):
    """Heater profile (per unit of needed superheat change, in units of 1/kh) that makes the
    modelled superheat follow a rotation step at tau=0 (with drive + convection lag), placed
    so the integrated mismatch (diameter effect) is minimal. Index i <-> tau = i - T0."""
    from scipy.optimize import lsq_linear

    def resp(P):
        b = [0.0] * (d + 1); x1 = x2 = 0.0; S = np.empty(len(P))
        for i, p in enumerate(P):
            b.append(p); pd = b.pop(0); x1 += (pd - x1) / t1; x2 += (x1 - x2) / t2; S[i] = x2
        return S
    idx = np.arange(0, N, blk)
    B = np.zeros((N, len(idx)))
    base = resp(np.ones(N))
    for k, j in enumerate(idx):
        B[j:, k] = base[:N - j]
    # needed superheat: rotation setpoint step at tau=0 (drive ~1 min), convection lag trot
    Hs = np.zeros(N); r = 0.0
    for i in range(N):
        tgt = 1.0 if i >= T0 + 1 else 0.0
        r += (tgt - r) / trot; Hs[i] = r
    C = np.tril(np.ones((N, N)))
    A = np.vstack([C @ B, wS * B, lam * np.eye(len(idx)), 30 * np.ones((1, len(idx)))])
    y = np.concatenate([C @ Hs, wS * Hs, np.zeros(len(idx)), [30.0]])
    res = lsq_linear(A, y, bounds=(-slew_units * blk, slew_units * blk))
    P = np.zeros(N)
    for k, j in enumerate(idx):
        P[j:] += res.x[k]
    # smooth block edges into ramps (slew)
    return P, T0


# state indices
iD, iH, iB, iG, iC, iP, iV = range(7)


class Controller:
    def __init__(self):
        p = PRM
        self.d = int(round(p['delay'])); self.t1 = p['t1']; self.t2 = p['t2']
        self.kh0 = p['kh0']; self.crot = p['crot']; self.trot = p['trot']
        self.off = p['cam_off']; self.Dt = p['D_target']
        self.tsc = p['tau_sc']
        self.k = 0
        self.e = 0.0
        self.ffP, self.ffT0 = _ff_shape(self.d, self.t1, self.t2, self.trot, p['ff_slew_units'], p['ff_lam'], p['ff_wS'])
        steps = []
        for i in range(1, len(_RL)):
            if _RR[i] != _RR[i - 1]:
                steps.append((_RL[i], _RR[i] - _RR[i - 1]))
        self.rsteps = steps
        self._since = {}
        self.init = False

    # ---- model pieces -------------------------------------------------
    def kh(self, L):
        return self.kh0 * (1 + 0.6 * np.asarray(L) / 1500.0)

    def wns(self, L, rot):
        """growth terms other than superheat, bias and meniscus"""
        return v0(L) + self.crot * (rot - 8.0)

    def S_true(self, x2=None):
        if x2 is None:
            x2 = self.x2
        return self.x20 + self.x[iG] * (x2 - self.x20) + self.x[iC]

    def _init(self, m):
        L = m['length_mm']; P = m['heater_power_kw']
        self.buf = [P] * (self.d + 1)
        u = self.kh(L) * (P - p0(L))
        self.x1 = u; self.x2 = u; self.x20 = u
        self.rot = m['crucible_rpm_set']
        x = np.zeros(7)
        x[iD] = m['camera_diameter_mm'] - self.off
        x[iH] = 0.0
        x[iG] = 1.0
        x[iB] = prog(L) - self.wns(L, self.rot) + 0.05 * u
        x[iP] = m['pyrometer_c'] - u
        self.x = x
        self.Pc = np.diag([0.06 ** 2, 0.02 ** 2, 0.002 ** 2, PRM['g_sd0'] ** 2, 0.05 ** 2, 0.5 ** 2,
                           PRM['pv_sd0'] ** 2])
        self.Pset = P
        self.plan = None
        self.init = True
        self.ff0 = 0.0
        self.ff0 = float(self._ff(L, 1)[0])

    def step(self, m):
        if not self.init:
            self._init(m)
        else:
            self._update(m)
        L = m['length_mm']
        for Lk, _ in self.rsteps:
            if L >= Lk:
                self._since[Lk] = self._since.get(Lk, -1.0) + 1.0
        if self.k % PRM['mpc_every'] == 0 and L >= PRM['mpc_start_L']:
            try:
                self._mpc(m)
            except Exception:
                self.plan = None
        if self.plan is not None and len(self.plan):
            self.Pset = float(self.plan[0]); self.plan = self.plan[1:]
        vset = self._pull(m)
        self.k += 1
        Pout = self.Pset + self._ff(L, 1)[0] - self.ff0
        return float(vset), float(np.clip(Pout, 60.0, 140.0))

    def _ff(self, L, n):
        """rotation feedforward heater offsets (kW) for the next n minutes (index 0 = now)"""
        out = np.zeros(n)
        if not PRM['ff_on']:
            return out
        g = float(np.clip(self.x[iG], 0.6, 1.4))
        for Lk, drpm in self.rsteps:
            # minutes until L reaches Lk at the program growth rate
            if Lk > L:
                ll = np.linspace(L, Lk, 60)
                tk = np.trapezoid(1.0 / prog(ll), ll) if hasattr(np, 'trapezoid') else np.trapz(1.0 / prog(ll), ll)
            else:
                tk = -self._since.get(Lk, 0.0)
            amp = self.crot * drpm / 0.05 / (self.kh(Lk) * g)
            tau = np.arange(n) - tk
            i = np.round(tau).astype(int) + self.ffT0
            v = np.where(i < 0, 0.0, np.where(i >= len(self.ffP), 1.0, self.ffP[np.clip(i, 0, len(self.ffP) - 1)]))
            out += amp * v
        return out

    # ---- estimator -----------------------------------------------------
    def _update(self, m):
        L = m['length_mm']; P = m['heater_power_kw']; vp = m['pull_rate_mm_min']
        x = self.x
        # values that held over the last minute
        x2 = self.x2
        dx2 = x2 - self.x20
        S = self.S_true()
        w = self.wns(L, self.rot) - 0.05 * S + x[iB]
        vg = 0.3 * x[iH] + w
        dh_new = A_M * x[iH] + B_M * (vp - w)
        D_new = x[iD] - 0.48 * vg * 0.5 * (x[iH] + dh_new)
        F = np.eye(7)
        # dh_new partials: w depends on b (+1), g (-0.05 dx2), sc (-0.05)
        F[iH, iH] = A_M
        F[iH, iB] = -B_M
        F[iH, iG] = B_M * 0.05 * dx2
        F[iH, iC] = B_M * 0.05
        c = -0.48 * vg * 0.5
        F[iD, iH] = c * (1 + A_M)
        F[iD, iB] = c * (-B_M)
        F[iD, iG] = c * B_M * 0.05 * dx2
        F[iD, iC] = c * B_M * 0.05
        esc = np.exp(-1.0 / self.tsc)
        F[iC, iC] = esc
        F[iP, iV] = 1.0
        xn = x.copy()
        xn[iH] = dh_new; xn[iD] = D_new
        xn[iC] = esc * x[iC]
        xn[iP] = x[iP] + x[iV]
        Q = np.diag([1e-6, PRM['q_dh'] ** 2, PRM['q_b'] ** 2, PRM['q_g'] ** 2, PRM['q_sc'] ** 2,
                     PRM['q_pd'] ** 2, PRM['q_pv'] ** 2])
        self.Pc = F @ self.Pc @ F.T + Q
        self.x = xn
        # melt thermal pipeline (model) and rotation
        self.buf.append(P); Pd = self.buf.pop(0)
        u = self.kh(L) * (Pd - p0(L))
        self.x1 += (u - self.x1) / self.t1; self.x2 += (self.x1 - self.x2) / self.t2
        self.rot += (m['crucible_rpm_set'] - self.rot) / self.trot
        # measurements: camera and pyrometer
        x = self.x
        dx2 = self.x2 - self.x20
        Hc = np.zeros(7); Hc[iD] = 1.0; Hc[iH] = -1.2
        Hp = np.zeros(7); Hp[iG] = dx2; Hp[iC] = 1.0; Hp[iP] = 1.0
        yc = m['camera_diameter_mm'] - (x[iD] + self.off - 1.2 * x[iH])
        yp = m['pyrometer_c'] - (self.S_true() + x[iP])
        for H, y, r in ((Hc, yc, PRM['r_cam']), (Hp, yp, PRM['r_pyro'])):
            Sv = H @ self.Pc @ H + r ** 2
            y = float(np.clip(y, -4 * np.sqrt(Sv), 4 * np.sqrt(Sv)))
            K = self.Pc @ H / Sv
            self.x = self.x + K * y
            self.Pc = self.Pc - np.outer(K, H @ self.Pc)
        self.x[iG] = float(np.clip(self.x[iG], 0.5, 1.6))
        self.Pc = 0.5 * (self.Pc + self.Pc.T)

    # ---- pull rate -----------------------------------------------------
    def _pull(self, m):
        L = m['length_mm']; x = self.x
        v = prog(L)
        Ln = L + v
        rotn = self.rot + (rpm_at(Ln) - self.rot) / self.trot
        Pd = self.buf[1] if len(self.buf) > 1 else self.buf[0]
        un = self.kh(Ln) * (Pd - p0(Ln))
        x1n = self.x1 + (un - self.x1) / self.t1
        x2n = self.x2 + (x1n - self.x2) / self.t2
        esc = np.exp(-1.0 / self.tsc)
        Sn = self.x20 + x[iG] * (x2n - self.x20) + esc * x[iC]
        S = self.S_true()
        wn = self.wns(Ln, rotn) - 0.05 * Sn
        w = self.wns(L, self.rot) - 0.05 * S
        # meniscus height giving growth = program: dh* = (prog - w - b)/0.3
        ddet = ((prog(Ln) - prog(L)) - (wn - w)) / 0.3
        vp = prog(L) + ddet
        if L < PRM['trim_end_L']:
            Dfin = x[iD] - 1.25 * x[iH]
            vp += float(np.clip(PRM['trim_k'] * (Dfin - self.Dt - PRM['trim_bias']), 0.0, PRM['trim_max']))
        else:
            # small growth trim (well inside the +-1 % window) as fast diameter feedback
            etg = float(np.clip(PRM['kD_gr'] * (x[iD] - self.Dt), -PRM['e_max'], PRM['e_max']))
            if L < PRM['trim_end_L'] + PRM['e_ramp_L']:
                etg *= max(0.0, (L - PRM['trim_end_L']) / PRM['e_ramp_L'])
            e_old = self.e
            self.e += (etg - self.e) / PRM['tau_e']
            vp += self.e * prog(L) + (self.e - e_old) * prog(L) / 0.3
            dhs = (prog(L) * (1 + self.e) - w - x[iB]) / 0.3
            vp += PRM['kdh'] * (dhs - x[iH])
        return float(np.clip(vp, 0.2, 1.6))

    # ---- heater MPC ----------------------------------------------------
    def _mpc(self, m):
        H = PRM['horizon']; blk = PRM['block']; nb = PRM['nblocks']
        L = m['length_mm']; x = self.x; g = x[iG]
        Lf = np.empty(H); l = L
        for i in range(H):
            l += prog(l); Lf[i] = l
        rpm = rpm_at(Lf)
        rot = np.empty(H); r = self.rot
        for i in range(H):
            r += (rpm[i] - r) / self.trot; rot[i] = r
        khf = self.kh(Lf); p0f = p0(Lf)
        # base: feedback part held, plus rotation feedforward
        ffv = self._ff(L, H) - self.ff0
        b = list(self.buf); x1 = self.x1; x2 = self.x2; X2 = np.empty(H)
        for i in range(H):
            b.append(self.Pset + ffv[i]); Pd = b.pop(0)
            u = khf[i] * (Pd - p0f[i])
            x1 += (u - x1) / self.t1; x2 += (x1 - x2) / self.t2; X2[i] = x2
        esc = np.exp(-np.arange(1, H + 1) / self.tsc)
        S0 = self.x20 + g * (X2 - self.x20) + x[iC] * esc
        # unit step responses of S for block moves
        G = np.zeros((H, nb))
        for j in range(nb):
            st = j * blk
            if st >= H:
                break
            x1 = 0.0; x2 = 0.0; col = np.zeros(H)
            for i in range(st, H):
                u = khf[i] if i - st >= self.d else 0.0
                x1 += (u - x1) / self.t1; x2 += (x1 - x2) / self.t2; col[i] = x2
            G[:, j] = g * col
        pr = prog(Lf)
        dhs = (pr - (self.wns(Lf, rot) - 0.05 * S0) - x[iB]) / 0.3
        dh = np.empty(H); h = x[iH]
        for i in range(H):
            h += (dhs[i] - h) * 0.26; dh[i] = h
        Db = x[iD] - np.cumsum(0.48 * pr * dh)
        Gd = -np.cumsum((0.48 * pr * 0.05 / 0.3)[:, None] * G, axis=0)
        Gdh = (0.05 / 0.3) * G
        wv = PRM['wD'] * (np.arange(H) >= PRM['wD_from'])
        A = [np.sqrt(wv)[:, None] * Gd, PRM['wdh'] * Gdh, PRM['wmove'] * np.eye(nb)]
        y = [np.sqrt(wv) * (self.Dt - Db), -PRM['wdh'] * dh, np.zeros(nb)]
        A = np.vstack(A); y = np.concatenate(y)
        u = np.linalg.lstsq(A, y, rcond=None)[0]
        for _ in range(PRM['asym_iter']):
            Dp = Db + Gd @ u
            lw = wv * (1.0 + PRM['asym'] * (Dp < self.Dt - PRM['asym_margin']))
            A[:H] = np.sqrt(lw)[:, None] * Gd; y[:H] = np.sqrt(lw) * (self.Dt - Db)
            u = np.linalg.lstsq(A, y, rcond=None)[0]
        u0 = float(np.clip(u[0], -PRM['dP_max'], PRM['dP_max']))
        self.plan = [float(np.clip(self.Pset + u0, 60, 140))] * PRM['mpc_every']
