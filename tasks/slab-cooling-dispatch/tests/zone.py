"""Sealed plant v3: one perimeter office zone with a thermally activated slab, cooling only.
Two instances (west, east) share one TABS supply in world.py; chiller in chiller.py.

Per m2 of floor. Nodes: N slab cells (0 next to the soffit), a thin soffit surface layer, zone air,
furnishings/floor/walls (one mass), and the glazing inner surface. What a design-sheet RC model
does not have:
  - soffit convection that depends on the air-soffit temperature difference (cooled ceiling,
    hc = 1.6 + 2.1 |dT|^0.31), so the slab-to-room coupling changes with load;
  - a glazing surface node that absorbs sun, exchanges with air, furnishings and soffit, and
    counts in the mean radiant temperature;
  - occupant-operated interior blinds in five bays with irradiance thresholds, which change both
    how much sun enters and where it lands (blind-absorbed heat goes to the air);
  - radiant internal and solar gains partly absorbed by the soffit;
  - occupancy that varies by day and within the day.
"""
import numpy as np
from scipy.linalg import expm

PAR = dict(
    L=0.26, N=12, k=1.8, rhoc=2300.0 * 900.0, pipe_depth=0.12, sens_depth=0.17, Cs=4.1e3,
    mdot=10.5 / 3600.0, cw=4186.0, Rt=0.028,
    hc_a=1.6, hc_b=2.1, hc_n=0.31, hc_bin=0.25, hr_m=5.3, hr_g=0.7,
    Ca=10e3, Cm=60e3, Cg=2.6e3, ham=8.0, g_ga=1.0, g_gm=1.4, g_go=0.565, UA_air=0.55,
    mcv=1.6, Tdoas=19.0, doas_night=0.3,
    W_soffit=0.35, W_glass=0.12, W_mass=0.53,
    tau_up=0.055, tau_dn=0.012, ag_up=0.018, ag_dn=0.022, ab_dn=0.025,
    sol_mass=0.75, sol_soffit=0.10, sol_air=0.15,
    gain_occ=22.0, gain_base=3.0, conv_int=0.4, rad_int_soffit=0.3,
    bays=(220.0, 270.0, 320.0, 370.0, 420.0),
    area=120.0,
)

WEST = dict(PAR, name="west", facade_az=270.0)
EAST = dict(PAR, name="east", facade_az=90.0, mdot=11.8 / 3600.0, UA_air=0.50, Cm=52e3, ham=7.0,
            bays=(200.0, 260.0, 320.0, 380.0, 440.0))


def G_pipe(p=PAR):
    mc = p["mdot"] * p["cw"]
    return mc * (1.0 - np.exp(-1.0 / (mc * p["Rt"])))


def hc_of(dT, p=PAR):
    return p["hc_a"] + p["hc_b"] * np.abs(dT) ** p["hc_n"]


def hc_bin(h, p=PAR):
    return float(np.clip(np.round(h / p["hc_bin"]) * p["hc_bin"], 1.5, 8.0))


class Plant:
    """x = [slab 0..N-1, soffit S, air A, mass M, glass Gl];
    u = [Ts, Tout, Tdoas, Q_air, Q_mass, Q_soffit, Q_glass]."""
    NU = 7

    def __init__(self, p=PAR):
        self.p = p
        N = p["N"]
        dz = p["L"] / N
        self.N, self.dz = N, dz
        self.ip = min(N - 1, int(p["pipe_depth"] / dz))
        self.isens = min(N - 1, int(p["sens_depth"] / dz))
        self.iS, self.ia, self.im, self.ig = N, N + 1, N + 2, N + 3
        self.nx = N + 4
        self.G = G_pipe(p)
        K = np.zeros((self.nx, self.nx))

        def link(i, j, g):
            K[i, i] -= g; K[j, j] -= g; K[i, j] += g; K[j, i] += g
        for i in range(N - 1):
            link(i, i + 1, p["k"] / dz)
        link(0, self.iS, 2 * p["k"] / dz)
        link(self.iS, self.im, p["hr_m"]); link(self.iS, self.ig, p["hr_g"])
        link(self.ia, self.im, p["ham"]); link(self.ia, self.ig, p["g_ga"]); link(self.im, self.ig, p["g_gm"])
        self.K0 = K
        C = np.full(self.nx, p["rhoc"] * dz)
        C[self.iS] = p["Cs"]; C[self.ia] = p["Ca"]; C[self.im] = p["Cm"]; C[self.ig] = p["Cg"]
        self.C = C
        self._cache = {}
        r = np.zeros(self.nx)
        r[self.ia] = 0.5
        r[self.iS] += 0.5 * p["W_soffit"]; r[self.ig] += 0.5 * p["W_glass"]; r[self.im] += 0.5 * p["W_mass"]
        self._op = r

    def AB(self, pump, doas, hc):
        p = self.p
        K = self.K0.copy()
        B = np.zeros((self.nx, self.NU))
        K[self.iS, self.iS] -= hc; K[self.ia, self.ia] -= hc; K[self.iS, self.ia] += hc; K[self.ia, self.iS] += hc
        if pump:
            K[self.ip, self.ip] -= self.G; B[self.ip, 0] = self.G
        K[self.ia, self.ia] -= p["UA_air"] + p["mcv"] * doas
        B[self.ia, 1] = p["UA_air"]; B[self.ia, 2] = p["mcv"] * doas
        K[self.ig, self.ig] -= p["g_go"]; B[self.ig, 1] = p["g_go"]
        B[self.ia, 3] = 1.0; B[self.im, 4] = 1.0; B[self.iS, 5] = 1.0; B[self.ig, 6] = 1.0
        return K / self.C[:, None], B / self.C[:, None]

    def _expm(self, pump, doas, hc, dt, integral):
        key = (integral, bool(pump), float(doas), float(hc), dt)
        if key not in self._cache:
            A, B = self.AB(pump, doas, hc)
            n, m = B.shape
            M = np.zeros((n + m, n + m)); M[:n, :n] = A; M[:n, n:] = B
            if integral:
                Z = np.zeros((2 * (n + m), 2 * (n + m)))
                Z[:n + m, :n + m] = M; Z[:n + m, n + m:] = np.eye(n + m)
                E = expm(Z * dt)[:n, n + m:]
                self._cache[key] = (E[:, :n], E[:, n:])
            else:
                E = expm(M * dt)
                self._cache[key] = (E[:n, :n], E[:n, n:])
        return self._cache[key]

    def disc_q(self, doas, hc, dt):
        """Pump off (valve closed), plus a column for a constant heat extraction q (W/m2) at the pipe
        plane: x+ = A x + Bd u - bq q."""
        key = ("q", float(doas), float(hc), dt)
        if key not in self._cache:
            A, B = self.AB(False, doas, hc)
            n, m = B.shape
            Bx = np.zeros((n, m + 1)); Bx[:, :m] = B; Bx[self.ip, m] = 1.0 / self.C[self.ip]
            M = np.zeros((n + m + 1, n + m + 1)); M[:n, :n] = A; M[:n, n:] = Bx
            E = expm(M * dt)
            self._cache[key] = (E[:n, :n], E[:n, n:n + m], E[:n, n + m])
        return self._cache[key]

    def disc(self, pump, doas, hc, dt):
        return self._expm(pump, doas, hc, dt, False)

    def disc_int(self, pump, doas, hc, dt):
        return self._expm(pump, doas, hc, dt, True)

    def hc_now(self, x):
        return hc_bin(hc_of(x[self.ia] - x[self.iS], self.p), self.p)

    def op_row(self):
        return self._op

    def top(self, x):
        return self._op @ x

    def surf(self, x):
        return x[self.iS]


def gain_inputs(qint, Ivert, b, p=PAR):
    """qint: internal gain W/m2; Ivert: facade irradiance; b: blind fraction down. Returns Q_air, Q_mass,
    Q_soffit, Q_glass (arrays or scalars)."""
    tau = p["tau_up"] * (1 - b) + p["tau_dn"] * b
    ag = p["ag_up"] * (1 - b) + p["ag_dn"] * b
    ab = p["ab_dn"] * b
    trans = tau * Ivert
    rad = (1 - p["conv_int"]) * qint
    Qa = p["conv_int"] * qint + p["sol_air"] * trans + ab * Ivert
    Qm = (1 - p["rad_int_soffit"]) * rad + p["sol_mass"] * trans
    Qs = p["rad_int_soffit"] * rad + p["sol_soffit"] * trans
    Qg = ag * Ivert
    return Qa, Qm, Qs, Qg


class Blinds:
    """Five bays. During occupied hours a bay is lowered when the last 15-min facade irradiance exceeds
    its threshold; all bays are raised at 08:00 on weekdays (the west facade is never in sun then).
    Outside occupied hours nothing changes, so Friday's afternoon state lasts the weekend."""

    def __init__(self, p=PAR, down=None):
        self.th = np.array(p["bays"])
        self.down = np.zeros(len(self.th), bool) if down is None else np.array(down, bool)

    def update(self, occ, t_h, I_last):
        if occ and abs(t_h - 8.0) < 1e-9:
            self.down[:] = I_last > self.th
        elif occ:
            self.down |= I_last > self.th
        return float(self.down.mean())


def blinds_series(occ, t_h, I_prev, down0=None, p=PAR, keep=False):
    bl = Blinds(p, down0)
    out = np.zeros(len(occ))
    states = np.zeros((len(occ), len(bl.th)), bool) if keep else None
    for k in range(len(occ)):
        out[k] = bl.update(bool(occ[k]), float(t_h[k]), float(I_prev[k]))
        if keep:
            states[k] = bl.down
    return (out, bl.down.copy(), states) if keep else (out, bl.down.copy())
