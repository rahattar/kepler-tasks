"""Sealed physics of the rod-pump core: a rod string as a chain of masses and springs driven at the polished
rod, a pump with two valves, gas in the barrel and a tubing string that stretches with the load it carries.
Time domain, explicit central differences, a batch of settings of one well at a time.
Positions are upward, depths downward, SI units throughout."""
import numpy as np

G = 9.80665
MATERIAL = {"steel": (200e9, 8000.0), "fibreglass": (50e9, 2400.0)}      # E Pa, rho kg/m3 (fittings included)
TUBING = {"60.3": (60.3, 50.7), "73.0": (73.0, 62.0), "88.9": (88.9, 76.0)}   # OD, ID mm
E_TUBING = 200e9


def area(d_mm):
    return np.pi * (d_mm * 1e-3) ** 2 / 4.0


def tubing_area(size):
    od, idm = TUBING[size]
    return np.pi * ((od * 1e-3) ** 2 - (idm * 1e-3) ** 2) / 4.0


def buoyant_weight(sections, rho_f):
    """Weight in the fluid of a string given as [(material, d_mm, length_m), ...], N."""
    return sum(area(d) * L * G * (MATERIAL[m][1] - rho_f) for m, d, L in sections)


def motion(theta, stroke, lam):
    """Polished rod position above the bottom of its stroke, and its first two derivatives in theta."""
    z = 0.5 * (1 - np.cos(theta)) + lam / 8.0 * (1 - np.cos(2 * theta))
    z1 = 0.5 * np.sin(theta) + lam / 4.0 * np.sin(2 * theta)
    z2 = 0.5 * np.cos(theta) + lam / 2.0 * np.cos(2 * theta)
    return stroke * z, stroke * z1, stroke * z2


def pump_step(sig, kap, Fo, Ap, pd, pi, h_av, s_low, s_high):
    """One step of the pump: the load F and plunger position s in the barrel that satisfy both
    s = sig - kap F (rods and tubing) and the pump (valves, gas). Returns F, s, new s_low, s_high, tv_open."""
    r = pi / pd
    lg = np.maximum(0.0, (s_high - s_low) - h_av)          # gas column when the standing valve shut
    s_tv = s_high - lg * (1.0 - r)
    s_Fo = sig - kap * Fo
    up = s_Fo >= s_high
    dn = (sig <= s_tv) & ~up
    mid = ~(up | dn)
    F = np.where(up, Fo, 0.0)
    s = np.where(up, s_Fo, sig)
    # compression of the gas, or a barrel full of liquid
    gas = mid & (lg > 1e-12)
    q = lg - s_high + sig
    b = kap * Ap * pd - q
    z = 0.5 * (-b + np.sqrt(b * b + 4.0 * kap * Ap * pi * lg))
    zs = np.where(gas, np.maximum(z, 1e-12), 1.0)
    Fg = np.clip(Ap * pd - Ap * pi * lg / zs, 0.0, Fo)
    F = np.where(gas, Fg, F)
    s = np.where(gas, s_high - lg + zs, s)
    full = mid & ~gas
    F = np.where(full, np.clip((sig - s_high) / kap, 0.0, Fo), F)
    s = np.where(full, s_high, s)
    nlow = np.where(dn, s, s_low)
    nhigh = np.where(up | dn, s, s_high)
    return F, s, nlow, nhigh, dn, up


def simulate(sections, c, Ap, pd, pi, kt, rho_f, stroke, spm, lam, q_in, nx=120, settle=11.5, record=None,
             refine=1):
    """Steady cycle of one well at a batch of settings.
    sections: [(material, d_mm, length_m)] from the top; c: damping 1/s; kt: tubing stiffness N/m (inf: held);
    stroke, spm, q_in (liquid supply m3/s, inf: all the barrel takes): arrays over the batch.
    Returns a dict of arrays: stroke of the plunger in the barrel, liquid height, peak and minimum polished rod
    load, counts of valve events in the last cycle. record: number of samples of the last cycle to return for
    row 0 (position, load)."""
    stroke = np.atleast_1d(np.asarray(stroke, float)); spm = np.atleast_1d(np.asarray(spm, float))
    q_in = np.broadcast_to(np.asarray(q_in, float), stroke.shape).copy()
    R = stroke.size
    Fo = Ap * (pd - pi)
    tt = sum(L / np.sqrt(MATERIAL[m][0] / MATERIAL[m][1]) for m, d, L in sections)
    dt0 = tt / (nx * refine)
    k_e, m_e = [], []
    for m, d, L in sections:
        E, rho = MATERIAL[m]; a = np.sqrt(E / rho)
        n = max(2, int(np.floor(L / (a * dt0))))
        dx = L / n
        k_e += [E * area(d) / dx] * n
        m_e += [rho * area(d) * dx] * n
    k_e = np.array(k_e); m_e = np.array(m_e); M = k_e.size
    m_n = np.zeros(M + 1); m_n[:-1] += m_e / 2; m_n[1:] += m_e / 2
    dt = 0.999 * dt0
    W = buoyant_weight(sections, rho_f)
    T = 60.0 / spm; om = 2 * np.pi / T
    ncyc = np.ceil(2.0 * settle / c / T) + 1
    t_end = ncyc * T
    nsteps = int(np.ceil(t_end.max() / dt)) + 2
    cd = c * dt
    y = np.zeros((R, M + 1)); yo = np.zeros((R, M + 1))
    inv_kt = 0.0 if np.isinf(kt) else 1.0 / kt
    beta = dt * dt / (m_n[M] * (1 + cd / 2))
    kap = beta + inv_kt
    s_low = np.full(R, Fo * inv_kt); s_high = s_low.copy()
    h_av = q_in / (Ap * spm / 60.0)
    pmax = np.full(R, -np.inf); pmin = np.full(R, np.inf)
    S_p = np.zeros(R); h_l = np.zeros(R); n_tv = np.zeros(R, int); n_sv = np.zeros(R, int); n_fl = np.zeros(R, int)
    n_bad = np.zeros(R, int); level = np.full(R, -np.inf); s_prev = np.zeros(R)
    was_up = np.zeros(R, bool); was_dn = np.ones(R, bool)
    rec = None
    if record:
        rec_t = t_end[0] - T[0] + T[0] * np.arange(record) / record
        rec = np.zeros((record, 5)); ri = 0; prev = None
    coef = dt * dt / m_n[1:M]
    for n in range(nsteps):
        t1 = (n + 1) * dt
        th = om * t1
        ys, ys1, ys2 = motion(th, stroke, lam)
        f_e = k_e * (y[:, :-1] - y[:, 1:])                       # tension in every element
        yn = np.empty_like(y)
        yn[:, 1:M] = (2 * y[:, 1:M] - (1 - cd / 2) * yo[:, 1:M] + coef * (f_e[:, :-1] - f_e[:, 1:])) / (1 + cd / 2)
        yn[:, 0] = ys
        base = (2 * y[:, M] - (1 - cd / 2) * yo[:, M] + dt * dt / m_n[M] * f_e[:, -1]) / (1 + cd / 2)
        sig = base + Fo * inv_kt
        last = (t1 > t_end - T) & (t1 <= t_end)
        sh0, sl0 = s_high, s_low
        F, s, s_low, s_high, dn, up = pump_step(sig, kap, Fo, Ap, pd, pi, h_av, s_low, s_high)
        yn[:, M] = base - beta * F
        # the standing valve shuts when the plunger stops rising with the full load on it
        sv_shut = was_up & ~up
        tv_opens = dn & ~was_dn
        S_now = sh0 - sl0
        big = S_now > 0.2 * stroke                 # the stroke proper, not a flutter of the valve
        take = tv_opens & last & (S_now > S_p)
        S_p = np.where(take, S_now, S_p)
        h_l = np.where(take, np.minimum(h_av, S_now), h_l)
        n_tv += (tv_opens & last & big); n_sv += (sv_shut & last & big)
        n_fl += (tv_opens & last & ~big)
        level = np.where(tv_opens, sl0 + np.minimum(h_av, S_now), level)
        n_bad += (was_dn & ~dn & last & (s_prev > level + 1e-3))
        s_prev = s
        was_up, was_dn = up, dn
        # polished rod load at the new time
        f0 = k_e[0] * (yn[:, 0] - yn[:, 1]) + m_n[0] * (ys2 * om * om + c * ys1 * om)
        prl = W + f0
        pmax = np.where(last, np.maximum(pmax, prl), pmax)
        pmin = np.where(last, np.minimum(pmin, prl), pmin)
        if record:
            cur = (t1, ys[0], prl[0], F[0], s[0], yn[0, M])
            while ri < record and prev is not None and rec_t[ri] <= t1:
                w = (rec_t[ri] - prev[0]) / (t1 - prev[0])
                rec[ri] = [prev[k] + w * (cur[k] - prev[k]) for k in (1, 2, 3, 4, 5)]
                ri += 1
            prev = cur
        yo, y = y, yn
    out = dict(stroke=S_p, h_liq=h_l, pprl=pmax, mprl=pmin, n_tv=n_tv, n_sv=n_sv, n_flutter=n_fl, n_bad=n_bad, Fo=Fo, W=W)
    if record:
        out["card"] = rec
    return out
