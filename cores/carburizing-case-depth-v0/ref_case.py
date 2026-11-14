"""Reference: python3 ref_case.py PACKAGE_DIR OUT_CSV          (AS_PROBE=1: take the probe as the atmosphere)

1. The atmosphere behind the record. CD-2 carburizes at the atmosphere's carbon potential; the record gives the
   oxygen probe's reading, which the controller holds at setpoint. The enrichment gas the controller needs is
   the carbon the load takes up plus what the exhaust carries, at the furnace's efficiency:
       q = a + b Cp + c U,        U the load's carbon uptake (g/h) at that minute,
   with the furnace's own a, b, c. A probe reading high shows as a load needing less gas than its reading and
   its uptake call for. a, b, c come from the loads just after the probe's calibration (the record starts
   there); each load's offset d (true Cp = probe - d) follows from its own gas, with d >= 0 and never
   falling (a probe that soots reads higher and higher until it is replaced).
2. Every load's carbon profile on 60 nodes, exact enough for CD-2 section 6; surface carbon and case depth.
"""
import csv, json, os, sys
import numpy as np

R_CAL, RHO = 1.987, 7.85e-3


def D(C, T):
    return 47.0 * np.exp(-1.6 * C) * np.exp(-(37000.0 - 6600.0 * C) / (R_CAL * (T + 273.15)))


def run(T, Cp, act, L, C0, beta, n=60, sub=2):
    from scipy.linalg import solve_banded
    m, K = T.shape
    dx = L / n
    C = np.repeat(C0[:, None], n + 1, axis=1).astype(float)
    dt = 60.0 / sub
    vol = np.ones(n + 1); vol[0] = vol[-1] = 0.5
    up = np.zeros((m, K))
    N = m * (n + 1)
    for k in range(K):
        on = act[:, k]
        b = np.where(on, beta, 0.0)
        for _ in range(sub):
            g = np.where(on[:, None], D(0.5 * (C[:, 1:] + C[:, :-1]), T[:, k][:, None]), 0.0) / dx[:, None] ** 2
            r = dt / vol
            ab = np.zeros((3, m, n + 1))
            ab[1] = 1.0
            ab[1][:, :-1] += r[:-1] * g; ab[1][:, 1:] += r[1:] * g
            ab[1][:, 0] += r[0] * b / dx
            ab[0][:, 1:] = -r[:-1] * g                     # super-diagonal, row j holds a[j-1, j]
            ab[2][:, :-1] = -r[1:] * g                     # sub-diagonal, row j holds a[j+1, j]
            rhs = C.copy(); rhs[:, 0] += r[0] * b / dx * Cp[:, k]
            C = solve_banded((1, 1), ab.reshape(3, N), rhs.reshape(N)).reshape(m, n + 1)
        up[:, k] = b * (Cp[:, k] - C[:, 0]) / 100.0 * RHO          # g per mm^2 per s, end of the minute
    return C, dx, up


def depth(C, dx, level=0.35):
    out = np.empty(len(C))
    for i, c in enumerate(C):
        j = np.flatnonzero(c < level)
        if len(j) == 0:
            out[i] = dx[i] * (len(c) - 1); continue
        j = j[0]
        out[i] = 0.0 if j == 0 else dx[i] * (j - 1 + (c[j - 1] - level) / (c[j - 1] - c[j]))
    return out


def isotonic(y):
    """Non-decreasing least-squares fit (pool adjacent violators)."""
    v, w, idx = [], [], []
    for i, yi in enumerate(y):
        v.append(yi); w.append(1.0); idx.append([i])
        while len(v) > 1 and v[-2] > v[-1]:
            tot = w[-2] + w[-1]
            v[-2] = (v[-2] * w[-2] + v[-1] * w[-1]) / tot; w[-2] = tot; idx[-2] += idx[-1]
            v.pop(); w.pop(); idx.pop()
    out = np.empty(len(y))
    for vi, ii in zip(v, idx):
        out[ii] = vi
    return out


def main(argv):
    pkg, out = argv[1], argv[2]
    fur = json.load(open(os.path.join(pkg, "furnace.json")))
    loads = list(csv.DictReader(open(os.path.join(pkg, "loads.csv"))))
    order = {r["load"]: i for i, r in enumerate(loads)}
    m = len(loads)
    raw = np.genfromtxt(os.path.join(pkg, "record.csv"), delimiter=",", skip_header=1, dtype=None, encoding=None,
                        names=["load", "t", "T", "p", "sp", "q"])
    li = np.array([order[x] for x in raw["load"]])
    K = int(raw["t"].max()) + 1
    T = np.full((m, K), 900.0); P = np.zeros((m, K)); Q = np.zeros((m, K)); act = np.zeros((m, K), bool)
    T[li, raw["t"]] = raw["T"]; P[li, raw["t"]] = raw["p"]; Q[li, raw["t"]] = raw["q"]; act[li, raw["t"]] = True
    g = fur["grades"]
    alloy = np.array([g[r["grade"]]["alloy_factor"] for r in loads])
    C0 = np.array([g[r["grade"]]["core_C_pct"] for r in loads])
    area = np.array([float(r["area_m2"]) for r in loads]) * 1e6
    L = np.minimum(4.0, np.array([float(r["section_mm"]) for r in loads]) / 2.0)
    beta = fur["mass_transfer_mm_s"]
    day = np.array([float(r["day"]) for r in loads])
    so = np.argsort(day)

    def solve(d, n=60, sub=2):
        return run(T, (P - d[:, None]) * alloy[:, None], act, L, C0, beta, n, sub)

    d = np.zeros(m)
    if not os.environ.get("AS_PROBE"):
        DH = 0.25
        _, _, u0 = solve(np.zeros(m), 40, 2)
        _, _, u1 = solve(np.full(m, DH), 40, 2)
        U0, U1 = u0 * area[:, None] * 3600.0, u1 * area[:, None] * 3600.0
        # the furnace's balance from the loads run just after the probe's calibration, when it reads true
        first = so[: max(10, m // 10)]
        on = act[first]
        X = np.stack([np.ones(on.sum()), P[first][on], U0[first][on]], 1)
        (a, b, c), *_ = np.linalg.lstsq(X, Q[first][on], rcond=None)
        for i in range(m):
            on = act[i]
            s_ = -b + c * (U1[i, on] - U0[i, on]) / DH
            r = Q[i, on] - (a + b * P[i, on] + c * U0[i, on])
            d[i] = float(np.sum(s_ * r) / np.sum(s_ * s_))
        d[so] = np.clip(isotonic(d[so]), 0.0, None)
        # the uptake is not linear in the offset: once more about the first estimate, with the balance refitted
        # on every load the first estimate finds the probe true on
        for _ in range(2):
            _, _, ua = solve(d, 40, 2)
            _, _, ub = solve(d + 0.05, 40, 2)
            Ua, Ub = ua * area[:, None] * 3600.0, ub * area[:, None] * 3600.0
            clean = np.flatnonzero(d == 0.0)
            on = act[clean]
            X = np.stack([np.ones(on.sum()), P[clean][on], Ua[clean][on]], 1)
            (a, b, c), *_ = np.linalg.lstsq(X, Q[clean][on], rcond=None)
            for i in range(m):
                on = act[i]
                s_ = -b + c * (Ub[i, on] - Ua[i, on]) / 0.05
                r = Q[i, on] - (a + b * (P[i, on] - d[i]) + c * Ua[i, on])
                d[i] = d[i] + float(np.sum(s_ * r) / np.sum(s_ * s_))
            d[first] = 0.0
            d[so] = np.clip(isotonic(d[so]), 0.0, None)
            d = np.where(d < 0.01, 0.0, d)
        # an offset within the fit's scatter is no offset
        d = np.where(d < 0.01, 0.0, d)
        print("furnace balance a %.3f b %.3f c %.5f; largest probe offset %.3f %%C" % (a, b, c, d.max()), file=sys.stderr)
    C, dx, _ = solve(d)
    cs, dep = C[:, 0], depth(C, dx)
    with open(out, "w") as f:
        f.write("load,surface_C_pct,case_depth_mm\n")
        for i, r in enumerate(loads):
            f.write("%s,%.3f,%.3f\n" % (r["load"], cs[i], dep[i]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
