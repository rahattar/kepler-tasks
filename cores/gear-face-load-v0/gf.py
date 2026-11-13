"""Truth physics of the core: the load along a spur gear pair's face width to GF-4 (see core/data/docs)."""
import math
import numpy as np

E, G = 206000.0, 79000.0        # MPa


def kernel(pin, x):
    """Pinion body deflection at the mesh, um per (N/mm * mm), between face stations x (mm from the datum end)."""
    r = pin["base_diameter_mm"] / 2.0
    d = pin["body_diameter_mm"]
    J = math.pi * d ** 4 / 32.0
    I = math.pi * d ** 4 / 64.0
    X, U = np.meshgrid(x, x, indexing="ij")
    Kt = r * r * np.minimum(X, U) / (G * J)                    # torque enters at the datum end
    if pin["mounting"] == "straddle":
        L, a = pin["bearing_span_mm"], pin["datum_to_bearing_mm"]
        xa, ua = X + a, U + a
        lo, hi = np.minimum(xa, ua), np.maximum(xa, ua)
        bb = L - hi
        Kb = bb * lo * (L * L - bb * bb - lo * lo) / (6.0 * E * I * L)
    else:                                                      # overhung: built in at the bearing
        a = pin["datum_to_bearing_mm"]
        xa, ua = X + a, U + a
        lo, hi = np.minimum(xa, ua), np.maximum(xa, ua)
        Kb = lo * lo * (3.0 * hi - lo) / (6.0 * E * I)
    return 1000.0 * (Kt + Kb)


def solve(K, cp, sep, F, dx):
    """Load intensity w (N/mm) at the stations for a normal force F (N). sep: separation of the unloaded
    flanks (um, any datum)."""
    n = len(sep)
    A = K * dx + np.eye(n) / cp
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
    return w


def curve(rows, gear, flank, x):
    """Mean lead deviation (um, material plus) of a gear's flank at the stations x, from the chart rows."""
    pts = {}
    for r in rows:
        if r["gear"] == gear and r["flank"] == flank:
            pts.setdefault(float(r["x_mm"]), []).append(float(r["dev_um"]))
    xs = np.array(sorted(pts))
    ys = np.array([np.mean(pts[v]) for v in xs])
    return np.interp(x, xs, ys)


def stations(b, n):
    dx = b / n
    return (np.arange(n) + 0.5) * dx, dx


def pattern(pair, f1, f2, m0, n=400):
    """Extent of the contact marking (from, to), mm from the datum end, at the pattern check force and the
    reference temperature."""
    b = pair["face_width_mm"]
    x, dx = stations(b, n)
    w = solve(kernel(pair["pinion"], x), pair["mesh_stiffness_N_mm_um"], -(f1(x) + f2(x)) + m0 * x / b,
              pair["pattern_check"]["force_N"], dx)
    on = np.flatnonzero(w > 0)
    return on[0] * dx, (on[-1] + 1) * dx


def results(pair, f1, f2, m0, points, n=240):
    b = pair["face_width_mm"]
    x, dx = stations(b, n)
    K = kernel(pair["pinion"], x)
    cp = pair["mesh_stiffness_N_mm_um"]
    base = -(f1(x) + f2(x))
    d1 = pair["pinion"]["pitch_diameter_mm"]
    u = pair["ratio"]
    out = []
    for pt in points:
        F = 2000.0 * pt["torque_Nm"] / pair["pinion"]["base_diameter_mm"]
        m = m0 + pair["thermal_um_per_K"] * (pt["oil_C"] - pair["reference_C"])
        wmax = float(solve(K, cp, base + m * x / b, F, dx).max())
        out.append({"point": pt["point"], "k_face": wmax / (F / b),
                    "sigma_H_MPa": pair["Z_MPa_sqrt"] * math.sqrt(wmax * (u + 1.0) / (d1 * u))})
    return out
