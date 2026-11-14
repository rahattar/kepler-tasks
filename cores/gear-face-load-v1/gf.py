"""Truth physics of the v1 core: the load along a spur gear pair's face width to GF-4 (core/data/docs)."""
import math
import numpy as np

E, G = 206000.0, 79000.0        # MPa


def kernel(pin, x):
    """Pinion body deflection at the mesh, mm per (N/mm * mm), between face stations x (mm from the datum end)."""
    r = pin["base_diameter_mm"] / 2.0
    d = pin["body_diameter_mm"]
    J, I = math.pi * d ** 4 / 32.0, math.pi * d ** 4 / 64.0
    X, U = np.meshgrid(x, x, indexing="ij")
    Kt = r * r * np.minimum(X, U) / (G * J)
    a = pin["datum_to_bearing_mm"]
    lo, hi = np.minimum(X, U) + a, np.maximum(X, U) + a
    if pin["mounting"] == "straddle":
        L = pin["bearing_span_mm"]
        g = L - hi
        Kb = g * lo * (L * L - g * g - lo * lo) / (6.0 * E * I * L)
    else:
        Kb = lo * lo * (3.0 * hi - lo) / (6.0 * E * I)
    return 1000.0 * (Kt + Kb)


def solve(A, sep, F, dx, active=None):
    """Exact solution on the stations: A = K dx + I / c'. Returns w (N/mm) and the active set."""
    n = len(sep)
    if active is None:
        active = np.ones(n, bool)
    for _ in range(400):
        idx = np.flatnonzero(active)
        k = len(idx)
        M = np.zeros((k + 1, k + 1))
        M[:k, :k] = A[np.ix_(idx, idx)]
        M[:k, k] = -1.0
        M[k, :k] = dx
        sol = np.linalg.solve(M, np.concatenate([-sep[idx], [F]]))
        w = np.zeros(n)
        w[idx] = sol[:k]
        neg = w < -1e-12
        if neg.any():
            active = active & ~neg
            continue
        gap = A @ w + sep - sol[k]
        pen = (~active) & (gap < -1e-9)
        if pen.any():
            active = active | pen
            continue
        break
    return w, active


def curve(rows, gear, flank):
    pts = {}
    for r in rows:
        if r["gear"] == gear and r["flank"] == flank:
            pts.setdefault(float(r["x_mm"]), []).append(float(r["dev_um"]))
    xs = np.array(sorted(pts))
    ys = np.array([np.mean(pts[v]) for v in xs])
    return lambda x: np.interp(x, xs, ys)


def loads(pair, lead, F_all, m_all, n=240):
    """Exact w for many (F, m): full contact in closed form for all points at once, the rest one by one."""
    b = pair["face_width_mm"]
    dx = b / n
    x = (np.arange(n) + 0.5) * dx
    A = kernel(pair["pinion"], x) * dx + np.eye(n) / pair["mesh_stiffness_N_mm_um"]
    Ai = np.linalg.inv(A)
    base = -lead(x)
    a1, ab, ax = Ai @ np.ones(n), Ai @ base, Ai @ (x / b)
    s1 = a1.sum() * dx
    # full contact: w = D a1 - ab - m ax, with dx * sum(w) = F
    D = (F_all + dx * (ab.sum() + m_all * ax.sum())) / s1
    W = D[:, None] * a1[None, :] - ab[None, :] - m_all[:, None] * ax[None, :]
    bad = np.flatnonzero((W < -1e-12).any(axis=1))
    act = None
    for i in bad:
        w, act = solve(A, base + m_all[i] * x / b, F_all[i], dx, None if act is None else act.copy())
        W[i] = w
    return x, W, len(bad)
