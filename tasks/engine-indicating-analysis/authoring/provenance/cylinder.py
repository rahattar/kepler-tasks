"""The sealed definition: what a cylinder of one of the group's engines does, and its results to IS-2.

Two things live here and nowhere else in the bundle that a submitted program can reach:

  simulate   the pressure in a cylinder over the compression and expansion strokes, from the charge trapped
             at inlet valve closing, the heat it gives to the walls and the heat its combustion releases;
  results    IS-2 applied to that pressure at the crank angles it really occurred at.

`results` is the truth the verifier holds a program to. It works on the pressure itself, on a grid five times
finer than a record, with the true crank angle and the true level; it never sees a record, a transducer or an
encoder, and it is never a run of the reference solution. The records a program is given are made from the
same pressure by authoring/provenance/cells.py, through each cell's transducer and encoder.
"""
import numpy as np

R_GAS = 287.0          # J/(kg K), IS-2 section 4
WIEBE_A = 6.908        # 99.9 per cent burned at the end of the burn duration


def volume(theta_deg, eng):
    """Cylinder volume (m3) at crank angle from firing top dead centre, IS-2 section 2."""
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


def swept(eng):
    B = eng["bore_mm"] * 1e-3
    S = eng["stroke_mm"] * 1e-3
    return np.pi * B * B / 4 * S


def gamma(T, xb):
    """Ratio of specific heats of the charge, IS-2 section 5."""
    gu = 1.375 - 6.99e-5 * T
    gb = 1.330 - 4.50e-5 * T
    return gu + (gb - gu) * xb


def hohenberg(p_pa, T, V, sp):
    """Wall heat transfer coefficient, W/(m2 K), IS-2 section 6."""
    return 130.0 * V ** -0.06 * (p_pa * 1e-5) ** 0.8 * T ** -0.4 * (sp + 1.4) ** 0.8


def wall_area(V, eng):
    B = eng["bore_mm"] * 1e-3
    return np.pi * B * B / 2 + 4 * V / B


def wiebe(theta, th0, dur, m):
    z = np.clip((theta - th0) / dur, 0.0, None)
    return 1 - np.exp(-WIEBE_A * z ** (m + 1))


def dwiebe(theta, th0, dur, m):
    z = np.clip((theta - th0) / dur, 0.0, None)
    return WIEBE_A * (m + 1) / dur * z ** m * np.exp(-WIEBE_A * z ** (m + 1))


def simulate(eng, speed, p_man, t_ivc, t_wall, q_tot, th0, dur, mw, p_exh, f_ht, grid):
    """True cylinder pressure (Pa) on `grid` (degrees, uniform, covering the two strokes) for a batch of cycles.

    q_tot, th0, dur and mw are arrays over the cycles: the heat each cycle's combustion releases and the start,
    length and form factor of its Wiebe burn. f_ht scales Hohenberg's coefficient for this engine (IS-2 says
    the correlation holds within 10 per cent). Before inlet valve closing the cylinder is at manifold pressure;
    from there the energy equation of a closed ideal-gas charge is integrated by the classical Runge-Kutta
    rule; after exhaust valve opening the cylinder blows down towards the exhaust pressure p_exh.
    """
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
    late = grid > evo
    blend = np.exp(-(grid[late] - evo) / 14.0)
    p[:, late] = p_exh + (p[:, late] - p_exh) * blend
    return p


def results(theta, p, eng, speed, p_man, t_ivc, t_wall, iters=12):
    """IS-2 applied to true pressures p (Pa, cycles by samples) at true crank angles theta (degrees, uniform).

    Returns each cycle's imep_bar, pmax_bar, apmax_deg, ca10_deg, ca50_deg and q_gross_J; the result of a point
    and cylinder is the mean over its cycles (IS-2 section 8)."""
    ivc, evo = eng["ivc_deg"], eng["evo_deg"]
    V = volume(theta, eng)
    sel = (theta >= -180 - 1e-9) & (theta <= 180 + 1e-9)
    Vs, ps = V[sel], p[:, sel]
    imep = np.sum(0.5 * (ps[:, 1:] + ps[:, :-1]) * np.diff(Vs), axis=1) / swept(eng) * 1e-5
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
