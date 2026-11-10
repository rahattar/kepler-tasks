"""Reference controller for the two-zone TABS group (agent-level: uses only the public data).

Per zone: a 4-state grey-box (pipe-plane slab, soffit-side slab, air, furnishings) identified from the
trend log, with the soffit's convective/radiant split fixed from physics; glazing inner-surface
temperature from a steady-state window balance. A Kalman filter per zone with an unmeasured-heat
state. A joint economic MPC: heat extraction per zone and the chiller leaving temperature, 48 h,
condensed LP with 1/COP linearised sequentially, chiller capacity, forecast temperature de-biased with
the factor estimated from the forecast archive, US federal holidays.

Self-contained (standard library, numpy, scipy only); fit.py writes it out with PARAMS embedded as a
Python literal and the comfort margins set there."""
import datetime as dt
import numpy as np
import scipy.sparse as sp
from scipy.linalg import expm
from scipy.optimize import linprog

PARAMS = None  # @@PARAMS@@

DT = 900.0
ZONES = ("west", "east")
MCV = 160e-3 * 1.2 * 1005 / 120.0
T_DOAS = 19.0
TS_MIN, TS_MAX = 15.0, 22.0
HOLIDAYS = {dt.date(2017, 5, 29), dt.date(2017, 7, 4), dt.date(2017, 9, 4)}
W_AIR, W_SOFF, W_GLASS, W_MASS = 0.5, 0.5 * 0.35, 0.5 * 0.12, 0.5 * 0.53
G_OUT, G_SOL = 0.18, 0.006          # glazing: Tg = Ta + G_OUT (Tout - Ta) + G_SOL * I


def sched(ts, holidays=True):
    wk = ts.weekday() < 5 and (ts.date() not in HOLIDAYS or not holidays)
    h = ts.hour + ts.minute / 60.0
    occ = wk and 8 <= h < 18
    doas = 1.0 if (wk and 6 <= h < 19) else 0.3
    price = 0.18 if (wk and 12 <= h < 19) else 0.06
    q = (22.0 * (0.8 if 12 <= h < 13 else 1.0)) if occ else 3.0
    return occ, doas, price, q


class Model:
    NAMES = ["Cc", "Cl", "Ca", "Cm", "Rcl", "hc", "hr", "ham", "UA", "G", "fsol", "fa_sol"]
    nx, ip = 4, 0

    def __init__(self, th):
        self.th = dict(th)
        self.G = self.th["G"]
        self.C = np.array([self.th[k] for k in ("Cc", "Cl", "Ca", "Cm")])
        self._c = {}

    def AB(self, doas):
        t = self.th
        K = np.zeros((4, 4)); B = np.zeros((4, 4))   # u = [Tout, Tdoas, Qa, Qm]

        def link(i, j, g):
            K[i, i] -= g; K[j, j] -= g; K[i, j] += g; K[j, i] += g
        link(0, 1, 1.0 / t["Rcl"]); link(1, 2, t["hc"]); link(1, 3, t["hr"]); link(2, 3, t["ham"])
        K[2, 2] -= t["UA"] + MCV * doas; B[2, 0] = t["UA"]; B[2, 1] = MCV * doas
        B[2, 2] = 1.0; B[3, 3] = 1.0
        return K / self.C[:, None], B / self.C[:, None]

    def disc(self, doas):
        """x+ = A x + B u - bq q  (q = heat extracted at the pipe plane, W/m2, held over the step)."""
        key = float(doas)
        if key not in self._c:
            A, B = self.AB(doas)
            Bx = np.zeros((4, 5)); Bx[:, :4] = B; Bx[0, 4] = 1.0 / self.C[0]
            M = np.zeros((9, 9)); M[:4, :4] = A; M[:4, 4:] = Bx
            E = expm(M * DT)
            self._c[key] = (E[:4, :4], E[:4, 4:8], E[:4, 8])
        return self._c[key]

    def gains(self, q_int, ivert):
        t = self.th
        return 0.4 * q_int + t["fa_sol"] * t["fsol"] * ivert, 0.6 * q_int + (1 - t["fa_sol"]) * t["fsol"] * ivert

    def op_row(self):
        return np.array([0.0, W_SOFF, W_AIR + W_GLASS * (1 - G_OUT), W_MASS])

    def op_offset(self, tout, ivert):
        return W_GLASS * (G_OUT * tout + G_SOL * ivert)


def interp2(table, T_axis, S_axis, T, S):
    T = np.clip(T, T_axis[0], T_axis[-1]); S = np.clip(S, S_axis[0], S_axis[-1])
    i = np.clip(np.searchsorted(T_axis, T) - 1, 0, len(T_axis) - 2)
    j = np.clip(np.searchsorted(S_axis, S) - 1, 0, len(S_axis) - 2)
    ft = (T - T_axis[i]) / (T_axis[i + 1] - T_axis[i]); fs = (S - S_axis[j]) / (S_axis[j + 1] - S_axis[j])
    return ((1 - ft) * (1 - fs) * table[i, j] + ft * (1 - fs) * table[i + 1, j]
            + (1 - ft) * fs * table[i, j + 1] + ft * fs * table[i + 1, j + 1])


def running_mean(x, w=96):
    pad = np.concatenate([np.full(w // 2, x[0]), x, np.full(w // 2, x[-1])])
    return np.convolve(pad, np.ones(w) / w, mode="same")[w // 2:w // 2 + len(x)]


def responses(m, x0, d):
    H = len(d["tout"])
    op = m.op_row()
    x = x0.copy()
    fo = np.zeros(H + 1); ft = np.zeros(H + 1)
    fo[0] = op @ x; ft[0] = x[0]
    As, bs = [], []
    for k in range(H):
        A, B, bq = m.disc(d["doas"][k])
        x = A @ x + B @ np.array([d["tout"][k], T_DOAS, d["qa"][k], d["qm"][k]])
        fo[k + 1] = op @ x + m.op_offset(d["tout"][k], d["iv"][k]); ft[k + 1] = x[0]
        As.append(A); bs.append(bq)
    Ro = np.zeros((H + 1, H)); Rt = np.zeros((H + 1, H))
    for j in range(H):
        v = bs[j]
        for k in range(j + 1, H + 1):
            Ro[k, j] = op @ v; Rt[k, j] = v[0]
            if k < H:
                v = As[k] @ v
    return fo, ft, Ro, Rt


class Controller:
    def __init__(self):
        P = PARAMS
        self.m = {z: Model(P["theta"][z]) for z in ZONES}
        self.Tax = np.array(P["chiller"]["outdoor_temp_c"]); self.Sax = np.array(P["chiller"]["leaving_temp_c"])
        self.copt = np.array(P["chiller"]["cop"]); self.capt = np.array(P["chiller"]["capacity_kw"])
        self.kappa = P["kappa"] if P.get("debias", True) else 0.0
        self.cop_var = P.get("cop_var", True)
        self.use_cap = P.get("use_cap", True)
        self.holidays = P.get("holidays", True)
        self.margin_hi, self.margin_lo = P["margin_hi"], P["margin_lo"]
        self.H = 192
        self.x = {z: None for z in ZONES}
        self.P = {z: np.diag([0.5, 0.5, 0.5, 0.5, 4.0]) for z in ZONES}
        self.Q = np.diag([0.02, 0.02, 0.05, 0.05, 0.4]) ** 2
        self.Rm = np.diag([0.1, 0.1]) ** 2
        self.Hm = np.array([[0, 0, 1.0, 0, 0], [1.0, 0, 0, 0, 0]])
        self.last = None
        self.plan = None
        self.t_plan = None
        self.Ts_prev = None; self.Q_prev = None

    def _cop(self, T, S):
        return interp2(self.copt, self.Tax, self.Sax, T, S)

    def _cap(self, T, S):
        return interp2(self.capt, self.Tax, self.Sax, T, S) * 1000.0 / 120.0

    def _filter(self, obs):
        for z in ZONES:
            o = obs["zones"][z]
            y = np.array([o["air_temp_c"], o["slab_temp_c"]])
            m = self.m[z]
            if self.x[z] is None:
                self.x[z] = np.array([y[1], 0.5 * (y[0] + y[1]), y[0], y[0], 0.0])
            else:
                _, _, tout, doas, qint = self.last
                Ts = obs["supply_temp_c"]
                dz = o["valve_duty"]
                iv = obs["facade_irradiance_w_m2"][z]
                qa, qm = m.gains(qint, iv)
                A, B, bq = m.disc(doas)
                xs = self.x[z]
                q = dz * m.G * max(xs[0] - Ts, 0.0)
                x4 = A @ xs[:4] + B @ np.array([tout, T_DOAS, qa + xs[4], qm]) - bq * q
                Aa = np.zeros((5, 5)); Aa[:4, :4] = A; Aa[:4, 4] = B[:, 2]; Aa[4, 4] = 1.0
                Aa[:4, 0] -= bq * dz * m.G
                self.x[z] = np.concatenate([x4, [xs[4]]])
                self.P[z] = Aa @ self.P[z] @ Aa.T + self.Q
            Pz = self.P[z]
            S = self.Hm @ Pz @ self.Hm.T + self.Rm
            K = Pz @ self.Hm.T @ np.linalg.inv(S)
            self.x[z] = self.x[z] + K @ (y - self.Hm @ self.x[z])
            self.P[z] = (np.eye(5) - K @ self.Hm) @ Pz

    def _solve(self, D, price, occ, Tout, Ts0, Q0, tr=1.5):
        H = len(price)
        R = {z: responses(self.m[z], self.x[z][:4], D[z]) for z in ZONES}
        nv = 7 * H
        iq = {"west": 0, "east": H}; iTs = 2 * H
        isl = {("west", 0): 3 * H, ("west", 1): 4 * H, ("east", 0): 5 * H, ("east", 1): 6 * H}
        if self.cop_var:
            c0 = 1.0 / self._cop(Tout, Ts0)
            dc = (1.0 / self._cop(Tout, Ts0 + 0.05) - 1.0 / self._cop(Tout, Ts0 - 0.05)) / 0.1
        else:
            c0 = 1.0 / self._cop(Tout, np.full(H, 16.0)); dc = np.zeros(H)
        w = price * DT / 3.6e6 * 120.0
        c = np.zeros(nv)
        for z in ZONES:
            c[iq[z]:iq[z] + H] = w * c0
        c[iTs:iTs + H] = w * dc * Q0
        oi = np.nonzero(occ)[0]
        for key in isl:
            c[isl[key] + oi] = 50.0 * 0.25
        rows, b = [], []
        lo = 21.0 + self.margin_lo; hi = 26.0 - self.margin_hi
        for z in ZONES:
            fo, ft, Ro, Rt = R[z]
            for k in oi:
                r = np.zeros(nv); r[iq[z]:iq[z] + H] = -Ro[k + 1]; r[isl[(z, 0)] + k] = -1.0
                rows.append(r); b.append(hi - fo[k + 1])
                r = np.zeros(nv); r[iq[z]:iq[z] + H] = Ro[k + 1]; r[isl[(z, 1)] + k] = -1.0
                rows.append(r); b.append(fo[k + 1] - lo)
        blocks = [sp.csr_matrix(np.array(rows))] if rows else []
        bl = [np.array(b)] if rows else []
        for z in ZONES:
            fo, ft, Ro, Rt = R[z]
            G = self.m[z].G
            for e in (0, 1):
                M = np.zeros((H, nv))
                M[:, iq[z]:iq[z] + H] = G * Rt[e:e + H] + np.eye(H)
                M[np.arange(H), iTs + np.arange(H)] = G
                blocks.append(sp.csr_matrix(M)); bl.append(G * ft[e:e + H])
        # capacity, linear in Ts about Ts0
        cap0 = self._cap(Tout, Ts0)
        dcap = (self._cap(Tout, Ts0 + 0.05) - self._cap(Tout, Ts0 - 0.05)) / 0.1
        Mc = sp.lil_matrix((H, nv))
        for k in range(H):
            Mc[k, k] = 1.0; Mc[k, H + k] = 1.0; Mc[k, iTs + k] = -dcap[k]
        if self.use_cap:
            blocks.append(Mc.tocsr()); bl.append(cap0 - dcap * Ts0)
        lo_ts = np.maximum(TS_MIN, Ts0 - tr); hi_ts = np.minimum(TS_MAX, Ts0 + tr)
        bounds = [(0, None)] * (2 * H) + list(zip(lo_ts, hi_ts)) + [(0, None)] * (4 * H)
        res = None
        for method in ("highs", "highs-ipm"):
            res = linprog(c, A_ub=sp.vstack(blocks).tocsr(), b_ub=np.concatenate(bl), bounds=bounds, method=method)
            if res.status == 0:
                break
        if res.status != 0:
            return None
        v = res.x
        return {z: v[iq[z]:iq[z] + H] for z in ZONES}, v[iTs:iTs + H]

    def step(self, obs):
        now = dt.datetime.fromisoformat(obs["time"])
        self._filter(obs)
        if self.plan is None or (now - self.t_plan).total_seconds() >= 3600 - 1:
            fc = obs["forecast"]
            off = int(round((now - dt.datetime.fromisoformat(fc["issued"])).total_seconds() / 900))
            fT = np.array(fc["outdoor_temp_c"])
            m = running_mean(fT)
            Tall = m + (fT - m) / (1 - self.kappa)
            Tout = Tall[off:off + self.H]
            H = len(Tout)
            S_ = [sched(now + dt.timedelta(minutes=15 * k), self.holidays) for k in range(H)]
            occ = np.array([s[0] for s in S_]); doas = np.array([s[1] for s in S_])
            price = np.array([s[2] for s in S_]); qint = np.array([s[3] for s in S_])
            D = {}
            for z in ZONES:
                iv = np.array(fc["facade_irradiance_w_m2"][z][off:off + H])
                qa, qm = self.m[z].gains(qint, iv)
                qa = qa + self.x[z][4] * np.exp(-np.arange(H) / 12.0)
                D[z] = dict(tout=Tout, doas=doas, qa=qa, qm=qm, iv=iv)
            if self.Ts_prev is not None:
                sh = int(round((now - self.t_plan).total_seconds() / 900))
                Ts0 = np.concatenate([self.Ts_prev[sh:], np.full(sh, self.Ts_prev[-1])])[:H]
                Q0 = np.concatenate([self.Q_prev[sh:], np.zeros(sh)])[:H]
                iters = 1
            else:
                Ts0, Q0, iters = np.full(H, 18.0), np.zeros(H), 3
            out = None
            for _ in range(iters):
                r = self._solve(D, price, occ, Tout, Ts0, Q0)
                if r is None:
                    break
                out = r
                Ts0, Q0 = r[1], r[0]["west"] + r[0]["east"]
            if out is not None:
                self.plan, self.t_plan = out, now
                self.Ts_prev, self.Q_prev = out[1], out[0]["west"] + out[0]["east"]
        if self.plan is None:
            Ts, duty = 18.0, {"west": 1.0, "east": 1.0}
        else:
            k = int(round((now - self.t_plan).total_seconds() / 900))
            q, Tsp = self.plan
            k = min(k, len(Tsp) - 1)
            Ts = float(Tsp[k])
            duty = {}
            for z in ZONES:
                dT = self.x[z][0] - Ts
                duty[z] = float(np.clip(q[z][k] / (self.m[z].G * dT), 0, 1)) if dT > 0.05 else 0.0
        _, doas_now, _, q_now = sched(now, self.holidays)
        self.last = (Ts, duty, obs["outdoor_temp_c"], doas_now, q_now)
        return {"supply_temp_c": Ts, "valve_duty": duty}
