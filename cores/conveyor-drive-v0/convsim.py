"""Sealed physics of the conveyor core: a line of belt flights in series, each with one to three slip drives and
a gravity take-up, carried step by step through a feed log. The load rides the belt at the belt's own speed, so
the calculation is sequential: the speed of a step comes from the load on the belt, which came from the speeds
before. SI units; feed in t/h, power in kW at the interfaces only."""
import numpy as np

G = 9.80665
N0 = 1500.0          # synchronous speed of every drive, rpm


def v0(D_mm, ratio):
    return np.pi * D_mm * 1e-3 * N0 / (60.0 * ratio)


def solve_drives(fl, Ftot, Rr, drives, v_guess):
    """Belt speed and drive forces for a required total force. drives: list of dicts with role, k (N per unit
    slip), v0 (m/s). Returns v, forces, entry and exit tensions per drive, tension at the weigher."""
    EA = fl["EA"]; Ttu = fl["T_tu"]; mBgH = fl["m_belt"] * G * fl["rise"]
    F = {d["role"]: 0.0 for d in drives}
    v = v_guess
    for _ in range(6):
        Fh2 = F.get("head2", 0.0); Fh1 = F.get("head1", 0.0)
        ent = {"head1": Ttu + Fh2 + Fh1, "head2": Ttu + Fh2, "tail": Ttu + Rr - mBgH}
        a = [(1.0 + ent[d["role"]] / EA) / d["v0"] for d in drives]
        v = (sum(d["k"] for d in drives) - Ftot) / sum(d["k"] * ai for d, ai in zip(drives, a))
        F = {d["role"]: d["k"] * (1.0 - v * ai) for d, ai in zip(drives, a)}
    Fh2 = F.get("head2", 0.0); Fh1 = F.get("head1", 0.0); Ft = F.get("tail", 0.0)
    ent = {"head1": Ttu + Fh2 + Fh1, "head2": Ttu + Fh2, "tail": Ttu + Rr - mBgH}
    ext = {"head1": Ttu + Fh2, "head2": Ttu, "tail": Ttu + Rr - mBgH - Ft}
    return v, F, ent, ext, Ttu + Rr - mBgH - Ft


def drive_consts(fl, true=True):
    out = []
    for d in fl["drives"]:
        D = d["D_true"] if true else d["D_reg"]
        vv = v0(D, d["ratio"])
        out.append(dict(role=d["role"], v0=vv, k=d["eta"] * d["P_rated"] * 1e3 / (d["s_rated"] * vv), eta=d["eta"]))
    return out


def resist(fl, M, Gm, q_kg_s, v):
    """Carry-side and return-side resistance, N: main and secondary resistance, lift of the load, and the push
    that brings the feed up to belt speed."""
    L = fl["length"]; Cf = fl["C"] * fl["f"]
    Rc = Cf * G * (L * (fl["m_belt"] + fl["m_idler_carry"]) + M) + G * Gm + q_kg_s * v
    Rr = Cf * G * L * (fl["m_belt"] + fl["m_idler_return"])
    return Rc, Rr


def survey_state(fl, q_th):
    """Steady running at a constant feed: belt speed, weigher speed, and input speed and power of each drive."""
    dr = drive_consts(fl)
    q = q_th / 3.6
    v = dr[0]["v0"] * 0.97
    for _ in range(30):
        mL = q / v
        M = mL * fl["length"]; Gm = mL * fl["rise"]
        Rc, Rr = resist(fl, M, Gm, q, v)
        v, F, ent, ext, Tw = solve_drives(fl, Rc + Rr, Rr, dr, v)
    out = []
    for d, c in zip(fl["drives"], dr):
        s = 1.0 - v * (1.0 + ent[c["role"]] / fl["EA"]) / c["v0"]
        out.append(dict(role=c["role"], rpm=N0 * (1 - s), kW=F[c["role"]] * c["v0"] / c["eta"] / 1e3, s=s))
    return v, v * (1.0 + Tw / fl["EA"]), out


def run_flight(fl, feed_th, dt):
    """A flight through a feed log (t/h at each step, held over the step). Returns per step and drive the motor
    power in kW and the traction ratio, the belt speed, and the discharge in t/h for the next flight."""
    n = feed_th.size
    dr = drive_consts(fl)
    L = fl["length"]
    sec_end = np.cumsum([s[0] for s in fl["sections"]])
    sec_sin = np.array([s[1] / s[0] for s in fl["sections"]])
    xi = np.zeros(n + 1); Mc = np.zeros(n + 1)          # belt travel and mass loaded, at the start of each step
    P = {d["role"]: np.zeros(n) for d in dr}; TR = {d["role"]: np.zeros(n) for d in dr}
    vs = np.zeros(n); out = np.zeros(n)
    v = dr[0]["v0"] * 0.97
    edges = np.concatenate([[0.0], sec_end])
    for k in range(n):
        q = feed_th[k] / 3.6
        # mass now lying between the section ends, from the mass loaded against belt travel
        m_at = np.interp(xi[k] - edges, xi[:k + 1], Mc[:k + 1], left=0.0)
        m_sec = m_at[:-1] - m_at[1:]
        M = m_sec.sum(); Gm = float(m_sec @ sec_sin)
        Rc, Rr = resist(fl, M, Gm, q, v)
        v, F, ent, ext, Tw = solve_drives(fl, Rc + Rr, Rr, dr, v)
        vs[k] = v
        for c in dr:
            r = c["role"]
            P[r][k] = F[r] * c["v0"] / c["eta"] / 1e3
            TR[r][k] = max(ent[r], ext[r]) / min(ent[r], ext[r])
        xi[k + 1] = xi[k] + v * dt
        Mc[k + 1] = Mc[k] + q * dt
        # what left over the head in this step
        a, b = np.interp([xi[k] - L, xi[k + 1] - L], xi[:k + 2], Mc[:k + 2], left=0.0)
        out[k] = (b - a) / dt * 3.6
    return P, TR, vs, out
