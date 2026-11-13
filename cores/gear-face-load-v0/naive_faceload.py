"""A correct but unoptimised second solution: the contact problem at every duty point by projected Gauss-Seidel
in plain loops on 240 stations, the misalignment by the same scan as the reference. Charts handled as the
reference handles them (it imports nothing: the reference's text is used for everything but the solver)."""
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
        bb = L - hi
        Kb = bb * lo * (L * L - bb * bb - lo * lo) / (6.0 * E * I * L)
    else:
        Kb = lo * lo * (3.0 * hi - lo) / (6.0 * E * I)
    return 1000.0 * (Kt + Kb)


def solve(A, sep, F, dx, active=None):
    """Projected Gauss-Seidel on the load, bisection on the approach, plain loops."""
    n = len(sep)
    Al = A.tolist(); sl = sep.tolist()
    def at(D):
        w = [0.0] * n
        for _ in range(4000):
            ch = 0.0
            for i in range(n):
                row = Al[i]; acc = 0.0
                for j in range(n):
                    acc += row[j] * w[j]
                new = max(0.0, w[i] + (D - sl[i] - acc) / row[i])
                ch = max(ch, abs(new - w[i])); w[i] = new
            if ch < 1e-9:
                break
        return w
    lo, hi = min(sl), max(sl) + F * max(max(r) for r in Al) * n
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        w = at(mid)
        if sum(w) * dx < F:
            lo = mid
        else:
            hi = mid
    return np.array(at(hi)), None


def curve(rows, gear, flank):
    pts = {}
    for r in rows:
        if r["gear"] == gear and r["flank"] == flank:
            pts.setdefault(float(r["x_mm"]), []).append(float(r["dev_um"]))
    xs = np.array(sorted(pts))
    ys = np.array([np.mean(pts[v]) for v in xs])
    return lambda x: np.interp(x, xs, ys)


def main(argv):
    pkg, out = argv[1], argv[2]
    pair = json.load(open(os.path.join(pkg, "pair.json")))
    rows = list(csv.DictReader(open(os.path.join(pkg, "lead_charts.csv"))))
    pts = list(csv.DictReader(open(os.path.join(pkg, "duty.csv"))))
    b, cp = pair["face_width_mm"], pair["mesh_stiffness_N_mm_um"]
    pc = pair["pattern_check"]
    n_p = 60
    xp = (np.arange(n_p) + 0.5) * b / n_p
    Ap = kernel(pair["pinion"], xp) * (b / n_p) + np.eye(n_p) / cp

    def edges(lead, m0):
        w, _ = solve(Ap, -lead(xp) + m0 * xp / b, pc["force_N"], b / n_p)
        on = np.flatnonzero(w > 0)
        return on[0] * b / n_p, (on[-1] + 1) * b / n_p

    def fit(lead):
        def miss(m0):
            lo, hi = edges(lead, m0)
            return max(abs(lo - pc["from_mm"]), abs(hi - pc["to_mm"]))
        grid = np.linspace(-30, 30, 13)
        vals = [miss(m) for m in grid]
        i = int(np.argmin(vals))
        a, c = grid[max(i - 1, 0)], grid[min(i + 1, len(grid) - 1)]
        for _ in range(4):
            m1, m2 = a + 0.382 * (c - a), a + 0.618 * (c - a)
            if miss(m1) < miss(m2):
                c = m2
            else:
                a = m1
        m0 = 0.5 * (a + c)
        return miss(m0), m0

    other = {"L": "R", "R": "L"}
    wp, ww = pair["pinion"]["working_flank"], pair["wheel"]["working_flank"]
    arrangements = [("as named", wp, ww)]
    if not os.environ.get("NAMED"):
        arrangements += [("pinion exchanged", other[wp], ww), ("wheel exchanged", wp, other[ww])]
    best = None
    for name, fp, fw in arrangements:
        c1, c2 = curve(rows, "pinion", fp), curve(rows, "wheel", fw)
        lead = lambda x, c1=c1, c2=c2: c1(x) + c2(x)        # noqa: E731
        miss, m0 = fit(lead)
        print(name, "pattern missed by %.2f mm at m0 %.2f" % (miss, m0), file=sys.stderr)
        if best is None or (miss < best[0] and best[0] > 1.5):
            best = (miss, m0, lead, name)
        if name == "as named" and miss <= 1.5:
            break
    _, m0, lead, name = best
    n = 240
    x = (np.arange(n) + 0.5) * b / n
    dx = b / n
    A = kernel(pair["pinion"], x) * dx + np.eye(n) / cp
    base = -lead(x)
    d1, u, Z = pair["pinion"]["pitch_diameter_mm"], pair["ratio"], pair["Z_MPa_sqrt"]
    with open(out, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["point", "k_face", "sigma_H_MPa"])
        for pt in pts:
            F = 2000.0 * float(pt["torque_Nm"]) / pair["pinion"]["base_diameter_mm"]
            m = m0 + pair["thermal_um_per_K"] * (float(pt["oil_C"]) - pair["reference_C"])
            w, _ = solve(A, base + m * x / b, F, dx)
            wmax = float(w.max())
            wr.writerow([pt["point"], "%.4f" % (wmax / (F / b)), "%.1f" % (Z * math.sqrt(wmax * (u + 1) / (d1 * u)))])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
