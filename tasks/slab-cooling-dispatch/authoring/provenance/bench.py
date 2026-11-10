"""Joint economic MPC for the two-zone TABS group (condensed LP, sequential linearisation of 1/COP),
and the information-matched benchmark built on it.

Decisions per 15-min step: heat extraction q_w, q_e (W per m2 of each zone) and the chiller leaving
temperature Ts. Valve modulation makes any 0 <= q_z <= G_z (Tp_z - Ts) reachable, so the dynamics
are linear in q; the chiller couples the zones through Ts (efficiency, and q_z <= G_z (Tp_z - Ts))
and through its capacity q_w + q_e <= cap(Ts, Tout).
"""
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path.insert(0, _os.path.join(_HERE, "..", "..", "tests"))
_sys.path.insert(0, _HERE)
import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog
from chiller import cop, TS_MIN, TS_MAX, CAP_KW_NOM, CAP_DTS, CAP_DTOUT
from instance import DT, SPD, ZONES, ZP, LO_OCC, HI_OCC, internal_gain, debias_T
from zone import gain_inputs, blinds_series, hc_of, hc_bin

AREA = 120.0
PEN = 50.0


def responses(model, x0, d, hc, dt=DT):
    """Free response and q-impulse responses of operative and pipe-plane temperature.
    d: dict of disturbance arrays (Tout, Qa, Qm, Qs, Qg, doas); hc: per-step convection."""
    H = len(d["Tout"])
    p = model.p
    As, bs = [], []
    x = x0.copy()
    op = model.op_row()
    free_op = np.zeros(H + 1); free_tp = np.zeros(H + 1)
    free_op[0] = op @ x; free_tp[0] = x[model.ip]
    for k in range(H):
        A, Bd, bq = model.disc_q(d["doas"][k], hc[k], dt)
        u = np.array([0.0, d["Tout"][k], p["Tdoas"], d["Qa"][k], d["Qm"][k], d["Qs"][k], d["Qg"][k]])
        x = A @ x + Bd @ u
        free_op[k + 1] = op @ x; free_tp[k + 1] = x[model.ip]
        As.append(A); bs.append(bq)
    R_op = np.zeros((H + 1, H)); R_tp = np.zeros((H + 1, H))
    for j in range(H):
        v = bs[j]
        for k in range(j + 1, H + 1):
            R_op[k, j] = op @ v; R_tp[k, j] = v[model.ip]
            if k < H:
                v = As[k] @ v
    return free_op, free_tp, R_op, R_tp


def cap_coeffs(Tout):
    k = CAP_KW_NOM * 1000.0 / AREA * (1 + CAP_DTOUT * (np.asarray(Tout) - 30.0))
    return k * (1 - CAP_DTS * 16.0), k * CAP_DTS


def solve(models, X0, D, HC, price, occ, lo, hi, Ts0, Q0, tr=1.5, cop_var=True, use_cap=True):
    """One linearised LP. D[z], HC[z]: per-zone disturbances and convection; Ts0, Q0: linearisation."""
    H = len(price)
    Z = list(ZONES)
    R = {z: responses(models[z], X0[z], D[z], HC[z]) for z in Z}
    G = {z: models[z].G for z in Z}
    # variable layout: [q_w (H), q_e (H), Ts (H), slack hi/lo per zone (4H)]
    iq = {Z[0]: 0, Z[1]: H}
    iTs = 2 * H
    isl = {(Z[0], "hi"): 3 * H, (Z[0], "lo"): 4 * H, (Z[1], "hi"): 5 * H, (Z[1], "lo"): 6 * H}
    nv = 7 * H
    Tout = D[Z[0]]["Tout"]
    if cop_var:
        c0 = 1.0 / cop(Ts0, Tout)
        eps = 0.05
        dc = (1.0 / cop(Ts0 + eps, Tout) - 1.0 / cop(Ts0 - eps, Tout)) / (2 * eps)
    else:   # treats the chilled water as fixed at 16 C: efficiency independent of Ts
        c0 = 1.0 / cop(np.full(H, 16.0), Tout); dc = np.zeros(H)
    w = price * DT / 3.6e6 * AREA
    c = np.zeros(nv)
    for z in Z:
        c[iq[z]:iq[z] + H] = w * c0
    c[iTs:iTs + H] = w * dc * Q0
    occ_idx = np.nonzero(occ)[0]
    for z in Z:
        c[isl[(z, "hi")] + occ_idx] = PEN * DT / 3600.0
        c[isl[(z, "lo")] + occ_idx] = PEN * DT / 3600.0
    rows = []; bub = []
    for z in Z:
        fo, ft, Ro, Rt = R[z]
        # comfort at end of occupied steps: op_{k+1}
        for k in occ_idx:
            r = np.zeros(nv); r[iq[z]:iq[z] + H] = -Ro[k + 1]; r[isl[(z, "hi")] + k] = -1.0
            rows.append(r); bub.append(hi[k] - fo[k + 1])
            r = np.zeros(nv); r[iq[z]:iq[z] + H] = Ro[k + 1]; r[isl[(z, "lo")] + k] = -1.0
            rows.append(r); bub.append(fo[k + 1] - lo[k])
    A1 = sp.csr_matrix(np.array(rows)) if rows else None
    # flux limits: q_k <= G (Tp_k - Ts_k), q_k <= G (Tp_{k+1} - Ts_k)
    blocks = []; bfl = []
    for z in Z:
        fo, ft, Ro, Rt = R[z]
        for end in (0, 1):
            M = np.zeros((H, nv))
            M[:, iq[z]:iq[z] + H] = G[z] * Rt[end:end + H] + np.eye(H)
            M[np.arange(H), iTs + np.arange(H)] = G[z]
            blocks.append(sp.csr_matrix(M)); bfl.append(G[z] * ft[end:end + H])
    a, b = cap_coeffs(Tout)
    Mc = sp.lil_matrix((H, nv))
    for k in range(H):
        Mc[k, iq[Z[0]] + k] = 1.0; Mc[k, iq[Z[1]] + k] = 1.0; Mc[k, iTs + k] = -b[k]
    if use_cap:
        blocks.append(Mc.tocsr()); bfl.append(a)
    Aub = sp.vstack(([A1] if A1 is not None else []) + blocks).tocsr()
    bub = np.concatenate([np.array(bub)] + bfl) if rows else np.concatenate(bfl)
    lo_ts = np.maximum(TS_MIN, Ts0 - tr); hi_ts = np.minimum(TS_MAX, Ts0 + tr)
    bounds = [(0, None)] * (2 * H) + list(zip(lo_ts, hi_ts)) + [(0, None)] * (4 * H)
    for method in ("highs", "highs-ipm", "highs-ds"):
        res = linprog(c, A_ub=Aub, b_ub=bub, bounds=bounds, method=method)
        if res.status == 0:
            break
    if res.status != 0:
        raise RuntimeError(res.message)
    v = res.x
    q = {z: v[iq[z]:iq[z] + H] for z in Z}
    Ts = v[iTs:iTs + H]
    # predicted trajectories for the next linearisation
    pred = {}
    for z in Z:
        fo, ft, Ro, Rt = R[z]
        pred[z] = dict(op=fo - Ro @ q[z], tp=ft - Rt @ q[z])
    return q, Ts, pred


def plan(models, X0, D, HC, price, occ, lo, hi, Ts0=None, Q0=None, iters=2, cop_var=True, use_cap=True):
    H = len(price)
    Ts0 = np.full(H, 18.0) if Ts0 is None else Ts0
    Q0 = np.zeros(H) if Q0 is None else Q0
    for _ in range(iters):
        q, Ts, pred = solve(models, X0, D, HC, price, occ, lo, hi, Ts0, Q0, cop_var=cop_var, use_cap=use_cap)
        Ts0, Q0 = Ts, q["west"] + q["east"]
    return q, Ts, pred


class InfoMatchedMPC:
    """Exact models and states of both zones, the agent's forecast feed corrected for its diurnal bias,
    design internal gains, comfort margin, 48 h horizon, re-planned hourly."""

    def __init__(self, plants, ep, fc, H=192, every=4, margin=0.3, debias=True, cop_var=True, use_cap=True,
                 holidays=True):
        self.pl, self.ep, self.fc, self.H, self.every, self.margin = plants, ep, fc, H, every, margin
        self.debias, self.cop_var, self.use_cap, self.holidays = debias, cop_var, use_cap, holidays
        self.plan, self.tp = None, None
        sch = ep["sch"]
        if not holidays:
            from instance import schedules
            import instance as _I
            saved = _I.HOLIDAYS; _I.HOLIDAYS = ()
            sch = schedules(ep["d0"], ep["d1"]); _I.HOLIDAYS = saved
        self.sch = {k: np.concatenate([sch[k]] + [sch[k][-7 * SPD:]] * 2)
                    for k in ("occ", "doas", "price", "t_h")}
        self.hc_traj = None
        self.Ts_prev = None; self.Q_prev = None
        self.failures = 0

    def __call__(self, obs, t, X):
        if self.plan is None or t - self.tp >= self.every:
            ep, H = self.ep, self.H
            f = self.fc.latest(t)
            off = t - f["issued_step"]
            idx = np.arange(t, t + H)
            sch = {k: self.sch[k][idx] for k in self.sch}
            Tout = (debias_T(f["Tout"]) if self.debias else f["Tout"])[off:off + H]
            D, HC = {}, {}
            for z, key, Ikey in (("west", "Iw", "Iw"), ("east", "Ie", "Ie")):
                p = ZP[z]
                Iv = f[Ikey][off:off + H]
                I_prev = np.concatenate([[ep["wx"][key][t - 1] if t > 0 else 0.0], Iv[:-1]])
                down0 = ep["g"][z]["down"][t - 1] if t > 0 else None
                b, _ = blinds_series(sch["occ"], sch["t_h"], I_prev, down0, p)
                q = internal_gain(sch, np.ones(H), p)
                Qa, Qm, Qs, Qg = gain_inputs(q, Iv, b, p)
                D[z] = dict(Tout=Tout, Qa=Qa, Qm=Qm, Qs=Qs, Qg=Qg, doas=sch["doas"])
                if self.hc_traj is not None:
                    sh = t - self.tp
                    HC[z] = np.concatenate([self.hc_traj[z][sh:], np.full(sh, self.hc_traj[z][-1])])
                else:
                    HC[z] = np.full(H, self.pl[z].hc_now(X[z]))
            lo = np.where(sch["occ"], LO_OCC + self.margin, 10.0)
            hi = np.where(sch["occ"], HI_OCC - self.margin, 35.0)
            if self.Ts_prev is not None:
                sh = t - self.tp
                Ts0 = np.concatenate([self.Ts_prev[sh:], np.full(sh, self.Ts_prev[-1])])
                Q0 = np.concatenate([self.Q_prev[sh:], np.zeros(sh)])
                iters = 1
            else:
                Ts0, Q0, iters = None, None, 3
            try:
                q, Ts, pred = plan(self.pl, X, D, HC, sch["price"], sch["occ"], lo, hi, Ts0, Q0, iters,
                                   cop_var=self.cop_var, use_cap=self.use_cap)
            except RuntimeError:
                self.failures += 1
                if self.plan is None:
                    return 18.0, {"west": 1.0, "east": 1.0}
                return self._act(t, X)
            self.hc_traj = {}
            for z in ZONES:
                pl = self.pl[z]
                # convection along the plan: air - soffit is not in pred; approximate with current dT
                self.hc_traj[z] = np.full(H, pl.hc_now(X[z]))
            self.plan = (q, Ts)
            self.Ts_prev, self.Q_prev = Ts, q["west"] + q["east"]
            self.tp = t
        return self._act(t, X)

    def _act(self, t, X):
        q, Ts = self.plan
        k = min(t - self.tp, len(Ts) - 1)
        duty = {}
        for z in ZONES:
            pl = self.pl[z]
            dT = X[z][pl.ip] - Ts[k]
            duty[z] = float(np.clip(q[z][k] / (pl.G * dT), 0, 1)) if dT > 0.05 else 0.0
        return float(Ts[k]), duty
