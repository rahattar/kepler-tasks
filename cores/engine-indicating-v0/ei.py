"""Truth physics and the sealed definition of results for the engine-indicating core.
Not visible to probes. The agent's documents describe the same standard in words."""
import numpy as np

R_GAS = 287.0
A_W = 6.908


def volume(theta_deg, eng):
    """Cylinder volume (m3) at crank angle from firing TDC."""
    B = eng["bore_mm"] * 1e-3
    S = eng["stroke_mm"] * 1e-3
    L = eng["conrod_mm"] * 1e-3
    rc = eng["compression_ratio"]
    a = S / 2
    Vd = np.pi * B * B / 4 * S
    Vc = Vd / (rc - 1)
    th = np.deg2rad(theta_deg)
    s = a * (1 - np.cos(th)) + L - np.sqrt(L * L - (a * np.sin(th)) ** 2)
    return Vc + np.pi * B * B / 4 * s


def dvolume(theta_deg, eng):
    """dV/dtheta (m3 per degree)."""
    B = eng["bore_mm"] * 1e-3
    S = eng["stroke_mm"] * 1e-3
    L = eng["conrod_mm"] * 1e-3
    a = S / 2
    th = np.deg2rad(theta_deg)
    sn, cs = np.sin(th), np.cos(th)
    ds = a * sn + a * a * sn * cs / np.sqrt(L * L - (a * sn) ** 2)
    return np.pi * B * B / 4 * ds * np.pi / 180


def vd(eng):
    B = eng["bore_mm"] * 1e-3
    S = eng["stroke_mm"] * 1e-3
    return np.pi * B * B / 4 * S


def gamma(T, xb):
    gu = 1.375 - 6.99e-5 * T
    gb = 1.330 - 4.50e-5 * T
    return gu + (gb - gu) * xb


def hohenberg(p_pa, T, V, sp):
    return 130.0 * V ** -0.06 * (p_pa * 1e-5) ** 0.8 * T ** -0.4 * (sp + 1.4) ** 0.8


def wall_area(V, eng):
    B = eng["bore_mm"] * 1e-3
    return np.pi * B * B / 2 + 4 * V / B


def wiebe(theta, th0, dur, m):
    z = np.clip((theta - th0) / dur, 0.0, None)
    return 1 - np.exp(-A_W * z ** (m + 1))


def dwiebe(theta, th0, dur, m):
    z = np.clip((theta - th0) / dur, 0.0, None)
    return A_W * (m + 1) / dur * z ** m * np.exp(-A_W * z ** (m + 1))


def simulate(eng, speed, p_man, t_ivc, t_wall, q_tot, th0, dur, mw, p_exh, f_ht, grid):
    """True cylinder pressure (Pa) on `grid` (deg, uniform, covering IVC..EVO) for a batch of cycles.
    q_tot, th0, dur, mw are arrays over cycles (q_tot 0 for motored)."""
    ivc, evo = eng["ivc_deg"], eng["evo_deg"]
    n = len(q_tot)
    h = grid[1] - grid[0]
    p = np.empty((n, len(grid)))
    m = p_man * volume(ivc, eng) / (R_GAS * t_ivc)
    sp = 2 * eng["stroke_mm"] * 1e-3 * speed / 60
    w = 6.0 * speed

    def rhs(th, pp):
        V = volume(th, eng)
        dV = dvolume(th, eng)
        T = pp * V / (m * R_GAS)
        xb = wiebe(th, th0, dur, mw) * (q_tot > 0)
        g = gamma(T, xb)
        dqc = q_tot * dwiebe(th, th0, dur, mw)
        dqw = f_ht * hohenberg(pp, T, V, sp) * wall_area(V, eng) * (T - t_wall) / w
        return (-g * pp * dV + (g - 1) * (dqc - dqw)) / V

    cur = np.full(n, float(p_man))
    for j, th in enumerate(grid):
        p[:, j] = cur
        if th < ivc - 1e-9:
            continue
        k1 = rhs(th, cur)
        k2 = rhs(th + h / 2, cur + h / 2 * k1)
        k3 = rhs(th + h / 2, cur + h / 2 * k2)
        k4 = rhs(th + h, cur + h * k3)
        cur = cur + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    # blowdown after EVO towards the exhaust pressure
    late = grid > evo
    blend = np.exp(-(grid[late] - evo) / 14.0)
    p[:, late] = p_exh + (p[:, late] - p_exh) * blend
    return p


def analyse(theta, p, eng, speed, p_man, t_ivc, t_wall, fired, iters=12):
    """The standard applied to pressures p (Pa, cycles x samples) at true crank angles theta (deg, uniform).
    Returns per-cycle imep_bar, pmax_bar, apmax_deg, ca10, ca50, ca90, q_gross_J."""
    ivc, evo = eng["ivc_deg"], eng["evo_deg"]
    V = volume(theta, eng)
    # gross IMEP over the compression and expansion strokes
    sel = (theta >= -180 - 1e-9) & (theta <= 180 + 1e-9)
    Vs, ps = V[sel], p[:, sel]
    imep = np.sum(0.5 * (ps[:, 1:] + ps[:, :-1]) * np.diff(Vs), axis=1) / vd(eng) * 1e-5
    # peak: least-squares parabola through the samples within 5 degrees of the highest
    h = theta[1] - theta[0]
    half = int(round(5.0 / h))
    kmax = np.argmax(p, axis=1)
    kmax = np.clip(kmax, half, p.shape[1] - half - 1)
    idx = kmax[:, None] + np.arange(-half, half + 1)[None, :]
    x = np.arange(-half, half + 1) * h
    y = np.take_along_axis(p, idx, axis=1)
    X = np.stack([np.ones_like(x), x, x * x], axis=1)
    coef = y @ np.linalg.pinv(X).T
    xv = -coef[:, 1] / (2 * coef[:, 2])
    apmax = theta[kmax] + xv
    pmax = (coef[:, 0] + coef[:, 1] * xv + coef[:, 2] * xv * xv) * 1e-5
    out = dict(imep_bar=imep, pmax_bar=pmax, apmax_deg=apmax)
    if not fired:
        return out
    win = (theta >= ivc - 1e-9) & (theta <= evo + 1e-9)
    th, Vw, pw = theta[win], V[win], p[:, win]
    m = p_man * volume(ivc, eng) / (R_GAS * t_ivc)
    sp = 2 * eng["stroke_mm"] * 1e-3 * speed / 60
    pm = 0.5 * (pw[:, 1:] + pw[:, :-1])
    Vm = 0.5 * (Vw[1:] + Vw[:-1])
    dV = np.diff(Vw)
    dp = np.diff(pw, axis=1)
    Tm = pm * Vm / (m * R_GAS)
    dqw = hohenberg(pm, Tm, Vm, sp) * wall_area(Vm, eng) * (Tm - t_wall) * (th[1] - th[0]) / (6.0 * speed)
    xbm = np.zeros_like(pm)
    for _ in range(iters):
        g = gamma(Tm, xbm)
        dq = g / (g - 1) * pm * dV + Vm * dp / (g - 1) + dqw
        Q = np.concatenate([np.zeros((len(p), 1)), np.cumsum(dq, axis=1)], axis=1)
        xb = np.clip(Q / Q[:, -1:], 0.0, 1.0)
        xbm = 0.5 * (xb[:, 1:] + xb[:, :-1])
    frac = Q / Q[:, -1:]
    res = []
    for level in (0.1, 0.5):
        k = np.argmax(frac >= level, axis=1)
        k = np.clip(k, 1, frac.shape[1] - 1)
        r = np.arange(len(p))
        f0, f1 = frac[r, k - 1], frac[r, k]
        res.append(th[k - 1] + (level - f0) / (f1 - f0) * (th[1] - th[0]))
    out.update(ca10_deg=res[0], ca50_deg=res[1], q_gross_J=Q[:, -1])
    return out
