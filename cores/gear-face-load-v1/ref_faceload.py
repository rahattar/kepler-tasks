"""Reference: python3 ref_faceload.py PACKAGE_DIR OUT_CSV      (NAMED=1: take the charts' flank names as given)

1. Which charts are the flanks in mesh. Pitting is contact fatigue: it forms only on a flank that carries load.
   A gear whose flank named as working shows no pits while its other flank is pitted has its charts named the
   other way round, and its working flank is the pitted one. A pit is a local dip of more than 2.5 um below the
   tooth's smooth lead curve (a quadratic fitted with the dips left out).
2. Lead curves: the mean over the charted teeth of each gear's working flank, as GF-4 section 2 says.
3. The load at every duty point: the exact contact problem of GF-4 section 4 on 240 stations. Full contact has a
   closed form, done for all points at once; a point with part of the face unloaded is solved on its own
   contact set, warm-started from the last such point.
"""
import csv, json, math, os, sys
import numpy as np

E, G = 206000.0, 79000.0


def kernel(pin, x):
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


def solve(A, sep, F, dx, active):
    n = len(sep)
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


def charts(rows):
    out = {}
    for r in rows:
        out.setdefault((r["gear"], r["flank"], r["tooth"]), []).append((float(r["x_mm"]), float(r["dev_um"])))
    return {k: np.array(sorted(v)).T for k, v in out.items()}


def pits(x, y):
    keep = np.ones(len(x), bool)
    for _ in range(5):
        c = np.polyfit(x[keep], y[keep], 2)
        res = y - np.polyval(c, x)
        keep = res > -2.5
    dips = res < -2.5
    return int(np.sum(dips[1:] & ~dips[:-1]) + dips[0])


def main(argv):
    pkg, out = argv[1], argv[2]
    pair = json.load(open(os.path.join(pkg, "pair.json")))
    ch = charts(csv.DictReader(open(os.path.join(pkg, "lead_charts.csv"))))
    other = {"L": "R", "R": "L"}
    flank = {}
    for gear in ("pinion", "wheel"):
        wf = pair[gear]["working_flank"]
        n_pits = {f: sum(pits(*ch[k]) for k in ch if k[0] == gear and k[1] == f) for f in ("L", "R")}
        flank[gear] = wf
        if not os.environ.get("NAMED") and n_pits[wf] == 0 and n_pits[other[wf]] >= 2:
            flank[gear] = other[wf]
        print(gear, "pits by flank", n_pits, "-> working flank charts:", flank[gear], file=sys.stderr)

    def mean_curve(gear):
        c = [ch[k] for k in ch if k[0] == gear and k[1] == flank[gear]]
        xs = c[0][0]
        return xs, np.mean([v[1] for v in c], axis=0)

    b, cp = pair["face_width_mm"], pair["mesh_stiffness_N_mm_um"]
    n = 240
    dx = b / n
    x = (np.arange(n) + 0.5) * dx
    (xp, yp), (xw, yw) = mean_curve("pinion"), mean_curve("wheel")
    base = -(np.interp(x, xp, yp) + np.interp(x, xw, yw))
    A = kernel(pair["pinion"], x) * dx + np.eye(n) / cp
    Ai = np.linalg.inv(A)
    a1, ab, ax = Ai @ np.ones(n), Ai @ base, Ai @ (x / b)
    s1 = a1.sum() * dx

    duty = np.genfromtxt(os.path.join(pkg, "duty.csv"), delimiter=",", names=True, dtype=None, encoding=None)
    T, oil = duty["torque_Nm"].astype(float), duty["oil_C"].astype(float)
    F = 2000.0 * T / pair["pinion"]["base_diameter_mm"]
    m = pair["mesh_misalignment_um"] + pair["thermal_um_per_K"] * (oil - pair["reference_C"])

    # full contact in closed form for every point at once; the points where that gives a negative load
    # are solved exactly on their own contact set, warm-started from the previous one
    D = (F + dx * (ab.sum() + m * ax.sum())) / s1
    wmax = np.empty(len(F))
    for lo in range(0, len(F), 20000):
        sl = slice(lo, lo + 20000)
        W = D[sl, None] * a1[None, :] - ab[None, :] - m[sl, None] * ax[None, :]
        wmax[sl] = W.max(axis=1)
        bad = np.flatnonzero((W < -1e-12).any(axis=1)) + lo
        act = np.ones(n, bool)
        for i in bad:
            w, act = solve(A, base + m[i] * x / b, F[i], dx, act.copy())
            wmax[i] = w.max()
    k_face = wmax / (F / b)
    d1, u, Z = pair["pinion"]["pitch_diameter_mm"], pair["ratio"], pair["Z_MPa_sqrt"]
    sig = Z * np.sqrt(wmax * (u + 1) / (d1 * u))
    with open(out, "w") as f:
        f.write("point,k_face,sigma_H_MPa\n")
        f.write("".join("%s,%.4f,%.1f\n" % t for t in zip(duty["point"], k_face, sig)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
