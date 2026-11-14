import sys, os, math, time
import numpy as np
import pandas as pd

NL = 24
SUB_SCALE = float(os.environ.get("RATCHET_SUB", "0.5"))  # max d(eps)*gamma per substep


def main():
    wd, out = sys.argv[1], sys.argv[2]
    mats = pd.read_csv(os.path.join(wd, "materials.csv"), dtype={"material": str}).set_index("material")
    lines = pd.read_csv(os.path.join(wd, "lines.csv"), dtype={"line": str, "material": str})
    hist = pd.read_csv(os.path.join(wd, "history.csv"), dtype={"line": str})
    L = len(lines)
    names = list(lines["line"].astype(str))
    hist["line"] = hist["line"].astype(str)
    groups = {n: g.sort_values("state") for n, g in hist.groupby("line")}
    S = max(len(groups[n]) for n in names)
    P = np.zeros((S, L)); T = np.zeros((S, L)); CK = np.zeros((S, L), bool)
    for j, n in enumerate(names):
        g = groups[n]; k = len(g)
        P[:k, j] = g["pressure_MPa"].values; T[:k, j] = g["dT_K"].values
        CK[:k, j] = g["checkpoint"].values == 1
        P[k:, j] = P[k - 1, j]; T[k:, j] = T[k - 1, j]
    def col(c):
        return np.array([float(mats.loc[m, c]) for m in lines["material"]])[:, None]
    E = col("E_MPa"); al = col("alpha_per_K"); k0 = col("k0_MPa")
    C = [col("C%d_MPa" % i) for i in (1, 2, 3)]; G = [col("gamma%d" % i) for i in (1, 2, 3)]
    Q = col("Q_MPa"); b = np.maximum(col("b"), 1e-12)
    G = [np.maximum(g, 1e-12) for g in G]
    C3 = np.stack(C); G3 = np.stack(G); iG3 = 1.0 / G3; kmin = float(k0.min())
    R = lines["mean_radius_mm"].values.astype(float)[:, None]; t = lines["wall_mm"].values.astype(float)[:, None]
    z = ((np.arange(NL) + 0.5) / NL - 0.5)[None, :]  # z/t
    gmax = np.maximum(np.maximum(G[0], G[1]), np.maximum(G[2], b))[:, 0]
    # load per unit: membrane stress pm = pR/t, thermal strain eth = -al*dT*z
    PM = P * (R[:, 0] / t[:, 0])[None, :]
    AT = T * al[:, 0][None, :]

    ep = np.zeros((L, NL)); X = [np.zeros((L, NL)) for _ in range(3)]; K = np.zeros((L, NL))
    res = {}

    def trial(pm, at):
        # sigma_i = pm + E(al dT z_i - ep_i + mean ep)
        return pm[:, None] + E * (at[:, None] * z - ep + ep.mean(1, keepdims=True))

    prev = [None, None]

    def step(pm, at):
        nonlocal ep, K
        Xs = X[0] + X[1] + X[2]
        st = trial(pm, at)
        xi = st - Xs
        f = np.abs(xi) - k0 - K
        if not (f > 0).any():
            return
        n = np.sign(xi)
        act = f > 0
        dp = np.zeros((L, NL))
        X0 = np.stack(X); K0 = K
        QK = Q - K0
        R0 = k0 + K0
        xs0 = st - Xs
        for it in range(80):
            if it:
                m = (n * dp).mean(1, keepdims=True)
                xin = xs0 + E * m
                ina = dp <= 0
                n = np.where(ina, np.sign(xin), n)
                newact = (dp > 0) | (ina & (np.abs(xin) - R0 > 1e-10 * R0))
                chg = (newact != act).any()
                act = newact
            hs = C3 - G3 * n * X0
            e = np.exp(-G3 * dp)
            he = hs * e
            Xn = ((hs - he) * iG3).sum(0)
            eb = np.exp(-b * dp)
            r = n * xs0 - R0 + E * (n * (n * dp).mean(1, keepdims=True) - dp) - Xn - QK * (1 - eb)
            D = -E - he.sum(0) - b * QK * eb
            r = np.where(act, r, 0.0); D = np.where(act, D, 1.0)
            u = np.where(act, E * n / NL, 0.0); v = np.where(act, n, 0.0)
            if it and not chg and np.abs(r).max() < 1e-7 * kmin:
                break
            y = -r / D; w = u / D
            d = y - w * ((v * y).sum(1, keepdims=True) / (1 + (v * w).sum(1, keepdims=True)))
            dp = np.maximum(dp + d, 0.0)
        hs = C3 - G3 * n * X0
        Xn = X0 + n * hs * (-np.expm1(-G3 * dp)) * iG3
        for j in range(3):
            X[j] = Xn[j]
        K = K0 + QK * (-np.expm1(-b * dp))
        ep = ep + n * dp

    sc = SUB_SCALE
    t0 = time.process_time(); tw = t0
    BUDGET = float(os.environ.get("RATCHET_BUDGET", "10.0"))
    for s in range(1, S):
        if s % 50 == 0:
            now = time.process_time()
            el = now - t0
            rate = (now - tw) / 50.0
            tw = now
            req = max(BUDGET - el, 0.2 * BUDGET * 0 + 1e-3) / max(S - 1 - s, 1)
            if rate > req:
                sc = min(sc * min(rate / req, 2.0), 1e6)
            elif rate < 0.6 * req and sc > SUB_SCALE:
                sc = max(sc / 1.3, SUB_SCALE)
        dpm = PM[s] - PM[s - 1]; dat = AT[s] - AT[s - 1]
        # elastic check at end of ramp (elastic if trial both ends inside; convex in load for linear path)
        st = trial(PM[s], AT[s])
        Xs = X[0] + X[1] + X[2]
        Ry = k0 + K
        xb = st - Xs
        fb = np.abs(xb) - Ry
        pl = fb > 0
        if pl.any():
            xa = trial(PM[s - 1], AT[s - 1]) - Xs
            dx = xb - xa
            with np.errstate(divide="ignore", invalid="ignore"):
                lr = np.where(dx > 0, (Ry - xa) / dx, (-Ry - xa) / dx)
            lr = np.where(pl, np.clip(lr, 0.0, 1.0), 1.0)
            lam0 = float(lr.min())
            pll = pl.any(1)
            de = (np.abs(dpm / E[:, 0]) + np.abs(dat)) * (1.0 - lam0)
            ns = int(math.ceil(max((de * gmax)[pll].max() / sc, 1)))
            ns = min(ns, 200)
            for q in range(1, ns + 1):
                lam = lam0 + (1.0 - lam0) * q / ns
                step(PM[s - 1] + lam * dpm, AT[s - 1] + lam * dat)
        for j in np.nonzero(CK[s])[0]:
            res[(j, s)] = ep[j].mean() * 100
    if os.environ.get("RATCHET_DEBUG"):
        print("final sc", sc, "cpu", time.process_time() - t0, file=sys.stderr)
    rows = []
    for j, n in enumerate(names):
        for s in np.nonzero(CK[:, j])[0]:
            rows.append(("%s-%05d" % (n, s), "%.6g" % res[(j, s)]))
    pd.DataFrame(rows, columns=["row", "ratchet_pct"]).to_csv(out, index=False)


if __name__ == "__main__":
    main()
