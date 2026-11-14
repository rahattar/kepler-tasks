"""Truth physics of the header-thermal-fatigue core: HF-3 (core/data/docs/hf3_header_fatigue.md)."""
import numpy as np
from scipy.signal import lfilter


class Wall:
    """Radial conduction in the header wall: inner surface at the fluid temperature, outer surface insulated.
    Exact in time for an input linear between samples (1 s), modal in space on n nodes."""

    def __init__(self, ri, ro, a, n=200, dt=1.0):
        r = np.linspace(ri, ro, n + 1)
        h = r[1] - r[0]
        rh = 0.5 * (r[1:] + r[:-1])                      # faces between nodes
        V = np.empty(n + 1)
        V[0] = 0.5 * (rh[0] ** 2 - ri ** 2)
        V[1:n] = 0.5 * (rh[1:] ** 2 - rh[:-1] ** 2)
        V[n] = 0.5 * (ro ** 2 - rh[-1] ** 2)
        # unknowns: nodes 1..n; node 0 is the input
        K = np.zeros((n, n))
        b = np.zeros(n)
        for j in range(1, n + 1):
            i = j - 1
            g_in = a * rh[j - 1] / h
            K[i, i] -= g_in
            if j - 1 >= 1:
                K[i, i - 1] += g_in
            else:
                b[i] += g_in
            if j < n:
                g_out = a * rh[j] / h
                K[i, i] -= g_out
                K[i, i + 1] += g_out
        Mi = 1.0 / np.sqrt(V[1:])
        S = Mi[:, None] * K * Mi[None, :]
        lam, Q = np.linalg.eigh(0.5 * (S + S.T))
        self.lam = lam
        g = Q.T @ (Mi * b)
        P = Mi[:, None] * Q                               # T_dev = P z
        Vt = V.sum()
        self.c_mean = (V[1:] @ P) / Vt
        self.d_mean = V[0] / Vt
        self.c_out = P[-1]
        E = np.exp(lam * dt)
        I1 = -1.0 / lam + (E - 1.0) / (lam * lam * dt)
        I0 = (E - 1.0) / lam - I1
        self.filters = [(np.array([g[k] * I1[k], g[k] * I0[k]]), np.array([1.0, -E[k]])) for k in range(n)]

    def response(self, tf):
        """tf: fluid temperature of one event at 1 s, the wall uniform at tf[0] before it. Returns the inner
        surface's difference from the mean wall temperature (Tmean - Ti) and the outer surface temperature."""
        u = tf - tf[0]
        mean = self.d_mean * u
        out = np.zeros_like(u)
        for k, (bb, aa) in enumerate(self.filters):
            z = lfilter(bb, aa, u)
            mean += self.c_mean[k] * z
            out += self.c_out[k] * z
        return mean - u, out + tf[0]


def lag(tf, tau, dt=1.0):
    """A first-order sensor of time constant tau (s) on the signal tf, in step with it at the start."""
    if tau <= 0:
        return tf.copy()
    lam = -1.0 / tau
    E = np.exp(lam * dt)
    I1 = -1.0 / lam + (E - 1.0) / (lam * lam * dt)
    I0 = (E - 1.0) / lam - I1
    g = 1.0 / tau
    return lfilter([g * I1, g * I0], [1.0, -E], tf - tf[0]) + tf[0]


def stress(hdr, dT, p_bar):
    ri, s = hdr["inner_radius_mm"], hdr["wall_mm"]
    rm = ri + 0.5 * s
    m = hdr["material"]
    sp = hdr["k_pressure"] * (0.1 * p_bar) * rm / s
    st = hdr["k_thermal"] * m["E_MPa"] * m["alpha_per_K"] / (1.0 - m["poisson"]) * dT
    return sp + st


def turning(x):
    d = np.diff(x)
    keep = np.flatnonzero(d != 0)
    if len(keep) == 0:
        return x[:1]
    x2 = np.concatenate([x[keep], x[-1:]])
    d = np.diff(x2)
    idx = np.flatnonzero(d[1:] * d[:-1] < 0) + 1
    return np.concatenate([x2[:1], x2[idx], x2[-1:]])


def rainflow(x):
    """ASTM E1049 rainflow: list of (range, count) with residue as half cycles."""
    out = []
    st = []
    for v in turning(x):
        st.append(v)
        while len(st) >= 3:
            X = abs(st[-1] - st[-2])
            Y = abs(st[-2] - st[-3])
            if X < Y:
                break
            if len(st) == 3:
                out.append((Y, 0.5))
                st.pop(0)
            else:
                out.append((Y, 1.0))
                last = st.pop()
                st.pop(); st.pop()
                st.append(last)
    for i in range(len(st) - 1):
        out.append((abs(st[i + 1] - st[i]), 0.5))
    return out


def damage(hdr, cycles):
    sn = hdr["sn_curve"]
    D = 0.0
    for r, c in cycles:
        if r > sn["cutoff_MPa"]:
            D += c / (sn["N_ref"] * (sn["range_ref_MPa"] / r) ** sn["m"])
    return D
