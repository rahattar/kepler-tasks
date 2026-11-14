#!/usr/bin/env python3
"""PW-5 ratchet strain for every checkpoint of every line of a line package.

Usage: python3 ratchet.py WORKS_DIR OUT_CSV

Layered hoop-wall model (24 layers, common strain eps, mean stress = pR/t),
Chaboche 3-backstress kinematic + Voce isotropic hardening.  Each ramp is
split into sub-increments; in each one the flow direction of a layer is
fixed and the hardening variables are integrated exactly in dp
(exponential solution), with one coupled Newton solve for eps and the
plastic multipliers of all layers.  All lines are advanced together.
"""
import os
import sys
import time
import numpy as np
import pandas as pd

NL = 24
ONE = np.full((NL, 1), 1.0 / NL)
NSUB = int(os.environ.get("PW5_NSUB", "0"))   # 0: adaptive to CPU budget
BUDGET = 9.0   # CPU seconds for the integration loop


def run(works, out):
    mat = pd.read_csv(os.path.join(works, "materials.csv")).set_index("material")
    lines = pd.read_csv(os.path.join(works, "lines.csv"))
    hist = pd.read_csv(os.path.join(works, "history.csv"))
    names = list(lines["line"])
    L = len(names)
    hs = []
    for nm in names:
        h = hist[hist["line"] == nm].sort_values("state")
        hs.append(h)
    S = max(len(h) for h in hs)
    P = np.zeros((L, S)); D = np.zeros((L, S))
    for l, h in enumerate(hs):
        n = len(h)
        P[l, :n] = h["pressure_MPa"].values; P[l, n:] = P[l, n - 1]
        D[l, :n] = h["dT_K"].values; D[l, n:] = D[l, n - 1]

    def col(c):
        return np.array([float(mat.loc[m, c]) for m in lines["material"]])[:, None]
    E = col("E_MPa"); al = col("alpha_per_K"); k0 = col("k0_MPa")
    C = np.stack([col("C%d_MPa" % j) for j in (1, 2, 3)])   # (3,L,1)
    G = np.stack([col("gamma%d" % j) for j in (1, 2, 3)])
    Q = col("Q_MPa"); b = col("b")
    CG = C / G
    CGs = CG.sum(0)
    R = lines["mean_radius_mm"].values.astype(float)[:, None]
    t = lines["wall_mm"].values.astype(float)[:, None]
    zt = ((np.arange(NL) + 0.5) / NL - 0.5)[None, :]          # z/t
    shp = (L, NL)
    ep = np.zeros(shp); X = np.zeros((3,) + shp); K = np.zeros(shp)
    eps = np.zeros((L, 1))
    epsrec = np.zeros((L, S))
    Ebig = np.broadcast_to(E, shp)
    p0 = P[:, 0:1]; d0 = D[:, 0:1]
    nsub = NSUB if NSUB > 0 else 6
    t0 = time.process_time(); nsteps = 0; nsub_hist = 0.0
    for k in range(1, S):
        if NSUB == 0 and k % 100 == 0 and nsteps:
            used = time.process_time() - t0
            per = used / nsteps                      # cost of one sub-increment
            rate = nsub_hist / k                       # plastic ramps per ramp
            left = BUDGET - used
            need = lambda m: (S - k) * rate * m * per
            nsub = 6
            while nsub > 2 and need(nsub) > left:
                nsub -= 1
        p1 = P[:, k:k + 1]; d1 = D[:, k:k + 1]
        # elastic trial for the whole ramp
        sm = p1 * R / t
        eth = -al * d1 * zt
        e_tr = (sm / E + ((eth + ep) @ ONE))
        str_ = E * (e_tr - eth - ep)
        Xs = X.sum(0)
        x1 = str_ - Xs
        rr = k0 + K
        if np.all(np.abs(x1) <= rr):
            eps = e_tr
        else:
            # state at the start of the ramp is elastic: find first yield
            eth0 = -al * d0 * zt
            x0 = E * (eps - eth0 - ep) - Xs
            dx = x1 - x0
            with np.errstate(divide="ignore", invalid="ignore"):
                fu = np.where(x1 > rr, (rr - x0) / dx, 1.0)
                fl = np.where(x1 < -rr, (-rr - x0) / dx, 1.0)
            f0 = min(fu.min(), fl.min())
            f0 = float(np.clip(f0, 0.0, 1.0)) if np.isfinite(f0) else 0.0
            nsteps += nsub; nsub_hist += 1.0
            for s in range(1, nsub + 1):
                f = f0 + (1.0 - f0) * s / nsub
                pp = p0 + (p1 - p0) * f; dd = d0 + (d1 - d0) * f
                sm = pp * R / t
                eth = -al * dd * zt
                base = eth + ep
                e = sm / E + (base @ ONE)
                Kd = K - Q
                bKd = b * Kd
                sb = E * (-base)
                cst = k0 + Q + CGs
                sbX = sb - Xs
                dp = np.zeros(shp)
                for it in range(60):
                    # flow direction = sign of the trial overstress at the current eps
                    n = np.where(E * e + sbX >= 0, 1.0, -1.0)
                    A = n * X - CG                           # nX = CG + A e^{-g dp}
                    En = E * n
                    eg = np.exp(-G * dp)
                    eb = np.exp(-b * dp)
                    sig = E * e + sb - En * dp
                    g = n * sig - np.add.reduce(A * eg, 0) - Kd * eb - cst
                    h = np.add.reduce(G * A * eg, 0) + bKd * eb - E
                    w = ((dp > 0) | (g > 0)) / h
                    r = (sig @ ONE) - sm
                    de = -(r + E * ((n * g * w) @ ONE)) / (E + E * E * (w @ ONE))
                    e = e + de
                    dpn = np.maximum(dp - (g + En * de) * w, 0.0)
                    if np.abs(dpn - dp).max() < 1e-12 and np.abs(de).max() < 1e-12:
                        dp = dpn
                        break
                    dp = dpn
                eg = np.exp(-G * dp); eb = np.exp(-b * dp)
                X = n * (CG + A * eg)
                K = Q + Kd * eb
                ep = ep + n * dp
                Xs = X.sum(0)
                eps = e
        epsrec[:, k] = eps[:, 0]
        p0 = p1; d0 = d1
    rows = []
    for l, h in enumerate(hs):
        st = h["state"].values; cp = h["checkpoint"].values
        for i in np.nonzero(cp == 1)[0]:
            s = int(st[i]); kk = i
            r = (epsrec[l, kk] - P[l, kk] * R[l, 0] / (t[l, 0] * E[l, 0])) * 100.0
            rows.append(("%s-%05d" % (names[l], s), r))
    pd.DataFrame(rows, columns=["row", "ratchet_pct"]).to_csv(out, index=False, float_format="%.6g")


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
