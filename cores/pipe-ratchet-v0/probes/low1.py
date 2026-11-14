#!/usr/bin/env python3
"""PW-5 progressive hoop strain (ratchet strain) for one line package.

usage: python3 ratchet.py WORKS_DIR OUT_CSV

Method
------
Every ramp of a line's history is split into substeps (more for ramps that change the
elastic stress more).  Within a substep a flowing layer flows in one direction n, and the
1-D laws of PW-5 section 2 are then exact functions of the accumulated plastic strain dp:
    n Xj(dp) = n Xj0 exp(-gj dp) + Cj (1 - exp(-gj dp)) / gj
    K(dp)    = Q + (K0 - Q) exp(-b dp)
so the state at the end of the substep follows exactly from the end hoop strain.
The hoop strain eps of each line and the dp of its 24 layers are found by Newton's
method on: yield consistency |sigma - X| = k0 + K of every flowing layer, and
mean layer stress = p R / t.  A safeguarded nested solver (exact layer update for a
given eps, bracketed Newton / Illinois on eps) is used whenever that fails.
All lines are advanced together, vectorised over lines x layers.
"""
import sys, os, time
import numpy as np
import pandas as pd

NL = 24
H_SUB = float(os.environ.get("PW5_H", "0.7"))      # substep size, in units of k0 of stress change
NSUB_MAX = 64
SUB_BUDGET = int(os.environ.get("PW5_BUDGET", "36000"))   # total substeps of a run, at most
CPU_LIMIT = float(os.environ.get("PW5_CPU", "7.0"))      # s, projected loop time that makes it coarsen
MAXIT = 12
GMIN = 1e-250
STATS = {"substeps": 0, "fallbacks": 0}


def simulate(E, al, k0, C, G, Q, B, Rt, P, D):
    """E, al, k0, Q, B: (L,1); C, G: (3,L,1); Rt: (L,) = R/t; P, D: (L,ns).
    Returns the hoop strain eps (L,ns) at every state."""
    L, ns = P.shape
    M = L * NL

    def full(a):
        return np.ascontiguousarray(np.broadcast_to(a, (L, NL)).reshape(M)).astype(float)

    z = ((np.arange(NL) + 0.5) / NL - 0.5)[None, :]              # z_i / t
    G = np.maximum(G, GMIN)
    Ev = E[:, 0].astype(float).copy()
    k0v = k0[:, 0].astype(float).copy()
    Ef, k0f, Qf, Bf = full(E), full(k0), full(Q), full(B)
    G0, G1, G2 = full(G[0]), full(G[1]), full(G[2])
    C0, C1, C2 = full(C[0]), full(C[1]), full(C[2])
    Cg0, Cg1, Cg2 = C0 / G0, C1 / G1, C2 / G2
    aez = full(al * z * E)                                       # E alpha z/t
    S = np.kron(np.eye(L), np.ones((NL, 1))) / NL                # (M,L): mean over a line
    rep = lambda v: v.repeat(NL)

    ep = np.zeros(M); X0 = np.zeros(M); X1 = np.zeros(M); X2 = np.zeros(M); K = np.zeros(M)
    eps = np.zeros(L)
    dp_prev = np.zeros(M)
    kt = Ev.copy()
    EPS = np.zeros((L, ns))

    # substeps per ramp: in proportion to the change of elastic stress over k0
    meas = (np.abs(np.diff(D, axis=1)) * (E * al) / 2
            + np.abs(np.diff(P, axis=1)) * Rt[:, None]) / np.maximum(k0, 1e-6)
    meas = meas.max(0) if meas.size else np.zeros(0)
    h = H_SUB
    nsub = np.clip(np.ceil(meas / h), 1, NSUB_MAX).astype(int)
    while nsub.sum() > SUB_BUDGET and h < 1e3:
        h *= 1.1
        nsub = np.clip(np.ceil(meas / h), 1, NSUB_MAX).astype(int)
    STATS["substeps"] = int(nsub.sum())

    def terms(dp, n, X0, X1, X2, KQ):
        # nX(dp), K(dp) - K0 and the derivative of the flow function phi
        m0 = np.expm1(-G0 * dp); m1 = np.expm1(-G1 * dp); m2 = np.expm1(-G2 * dp)
        mb = np.expm1(-Bf * dp)
        nx0 = n * X0; nx1 = n * X1; nx2 = n * X2
        nX = nx0 + nx1 + nx2 + nx0 * m0 + nx1 * m1 + nx2 * m2 - (Cg0 * m0 + Cg1 * m1 + Cg2 * m2)
        dnX = (C0 - G0 * nx0) * (1 + m0) + (C1 - G1 * nx1) * (1 + m1) + (C2 - G2 * nx2) * (1 + m2)
        dK = -KQ * mb                         # K(dp) - K0, KQ = Q - K0
        ddK = Bf * KQ * (1 + mb)
        return nX, dK, -(Ef + dnX + ddK)

    def layers(eps, sb, Xs, ky0, X0, X1, X2, KQ, dp0=None):
        # exact layer state for a given hoop strain: sigma, tangent, dp, n
        s_tr = Ef * rep(eps) + sb
        xi = s_tr - Xs
        n = np.where(xi >= 0, 1.0, -1.0)
        act = np.abs(xi) > ky0
        dp = np.zeros(M) if dp0 is None else dp0 * act
        tan = Ef.copy()
        if act.any():
            lo = np.zeros(M); hi = np.full(M, np.inf)
            tolp = 1e-10 * k0f
            for _ in range(100):
                nX, dK, dph = terms(dp, n, X0, X1, X2, KQ)
                ph = (n * s_tr - nX - Ef * dp - ky0 - dK) * act
                dph = np.minimum(dph, -1e-6 * Ef)
                if (np.abs(ph) < tolp).all():
                    break
                lo = np.where(ph > 0, dp, lo); hi = np.where(ph < 0, dp, hi)
                dpn = dp - ph / dph
                bad = ~((dpn >= lo) & (dpn <= hi))
                dp = np.where(bad, np.where(np.isfinite(hi), 0.5 * (lo + hi), 2 * lo + 1e-9), dpn)
            tan = np.where(act, Ef + Ef * Ef / dph, Ef)
        return s_tr - Ef * n * dp, tan, dp, n

    def robust(eps0, sb, Xs, ky0, X0, X1, X2, KQ, tgt, dp=None):
        # bracketed Newton on eps of each line (mean stress is continuous and increasing
        # in eps), with Illinois regula falsi when Newton leaves the bracket or stalls
        eps = eps0.copy()
        lo = np.full(L, -np.inf); hi = np.full(L, np.inf)
        Flo = np.zeros(L); Fhi = np.zeros(L)
        side = np.zeros(L)
        Fprev = np.full(L, np.inf)
        tol = 1e-8 * (np.abs(tgt) + k0v)
        for _ in range(200):
            sig, tan, dp, n = layers(eps, sb, Xs, ky0, X0, X1, X2, KQ, dp)
            F = sig @ S - tgt
            ok = np.abs(F) < tol
            if ok.all():
                break
            kt_ = np.maximum(tan @ S, 1e-6 * Ev)
            neg = F < 0
            Fhi = np.where(neg & (side == -1), 0.5 * Fhi, Fhi)
            Flo = np.where(~neg & (side == 1), 0.5 * Flo, Flo)
            lo = np.where(neg, eps, lo); Flo = np.where(neg, F, Flo)
            hi = np.where(~neg, eps, hi); Fhi = np.where(~neg, F, Fhi)
            side = np.where(neg, -1, 1)
            e_new = eps - F / kt_
            both = np.isfinite(lo) & np.isfinite(hi)
            dF = np.where(Fhi - Flo == 0, 1.0, Fhi - Flo)
            rf = lo - Flo * (hi - lo) / dF
            slow = np.abs(F) > 0.3 * Fprev
            use_rf = both & (slow | ~((e_new > lo) & (e_new < hi)))
            Fprev = np.abs(F)
            eps = np.where(ok, eps, np.where(use_rf, rf, e_new))
        return eps, dp, n

    de_max = 0.5 * k0v / Ev
    t_start = time.process_time()
    scale = 1.0
    remaining = np.concatenate([np.cumsum(nsub[::-1])[::-1], [0]])   # nominal substeps from ramp s
    done_sub = 0
    for s in range(1, ns):
        if s % 50 == 0 and done_sub > 0:
            # CPU guard: from the cost per substep so far, scale the substeps of the
            # remaining ramps so that the loop ends within CPU_LIMIT
            used = time.process_time() - t_start
            per = used / done_sub
            left = max(CPU_LIMIT - used, 0.05 * CPU_LIMIT)
            scale = min(1.0, max(0.02, left / per / max(remaining[s - 1], 1)))
        nsj = max(1, int(np.ceil(nsub[s - 1] * scale)))
        done_sub += nsj
        p0 = P[:, s - 1]; p1 = P[:, s]; d0 = D[:, s - 1]; d1 = D[:, s]
        if (p0 == p1).all() and (d0 == d1).all():
            EPS[:, s] = eps
            continue
        for j in range(1, nsj + 1):
            f = j / nsj
            tgt = (p0 + (p1 - p0) * f) * Rt
            dT = d0 + (d1 - d0) * f
            sb = aez * rep(dT) - Ef * ep                           # sigma_trial = E eps + sb
            Xs = X0 + X1 + X2
            ky0 = k0f + K
            KQ = Qf - K
            eps_el = (tgt - sb @ S) / Ev                           # elastic solution
            s_tr = Ef * rep(eps_el) + sb
            xi = s_tr - Xs
            act = np.abs(xi) > ky0
            if not act.any():
                eps = eps_el
                dp_prev[:] = 0.0
                kt[:] = Ev
                continue
            # predictor with the tangent stiffness of the last substep
            eps = eps + (eps_el - eps) * Ev / np.maximum(kt, 0.02 * Ev)
            s_tr = Ef * rep(eps) + sb
            xi = s_tr - Xs
            act = np.abs(xi) > ky0
            n = np.where(xi >= 0, 1.0, -1.0)
            dp = dp_prev * act
            failed = True
            for it in range(MAXIT):
                nX, dK, dph = terms(dp, n, X0, X1, X2, KQ)
                Edp = Ef * dp
                ph = (n * s_tr - nX - Edp - ky0 - dK) * act
                inv = act / dph
                Rg = (s_tr - n * Edp) @ S - tgt
                pi = ph * inv
                kt = Ev + Ev * Ev * (inv @ S)
                de = -(Rg - Ev * ((n * pi) @ S)) / kt
                np.minimum(de, de_max, out=de); np.maximum(de, -de_max, out=de)
                dpn = dp - pi - n * Ef * rep(de) * inv
                np.maximum(dpn, 0.0, out=dpn)
                eps = eps + de
                s_tr = Ef * rep(eps) + sb
                xi = s_tr - Xs
                n_new = np.where(xi >= 0, 1.0, -1.0)
                act_new = np.abs(xi) > ky0
                chg = (act_new != act).any() or ((n_new != n) & act_new).any()
                small = np.abs(dpn - dp).max() < 1e-8 and np.abs(de).max() < 1e-8
                dp = dpn * act_new
                if small and (not chg or it >= 3):
                    # converged (a set change now is a layer just touching the yield limit)
                    n = np.where(act_new, n_new, n)
                    failed = False
                    break
                if chg and it >= 4:
                    break                     # active set keeps changing
                if chg:
                    act = act_new
                    n = n_new
            if failed or not np.isfinite(eps).all() or not np.isfinite(dp).all():
                STATS["fallbacks"] += 1
                e0 = np.where(np.isfinite(eps), eps, eps_el)
                d0_ = np.where(np.isfinite(dp), dp, 0.0)
                eps, dp, n = robust(e0, sb, Xs, ky0, X0, X1, X2, KQ, tgt, d0_)
            m0 = np.expm1(-G0 * dp); m1 = np.expm1(-G1 * dp); m2 = np.expm1(-G2 * dp)
            X0 = X0 * (1 + m0) - n * Cg0 * m0
            X1 = X1 * (1 + m1) - n * Cg1 * m1
            X2 = X2 * (1 + m2) - n * Cg2 * m2
            K = K - KQ * np.expm1(-Bf * dp)
            ep = ep + n * dp
            dp_prev = dp
        EPS[:, s] = eps
    return EPS


def main(wd, out):
    np.seterr(all="ignore")
    rd = lambda f: pd.read_csv(os.path.join(wd, f), skipinitialspace=True)
    mat, lines, hist = rd("materials.csv"), rd("lines.csv"), rd("history.csv")
    for df, cs in ((mat, ["material"]), (lines, ["line", "material"]), (hist, ["line"])):
        for c in cs:
            df[c] = df[c].astype(str).str.strip()
    mat = mat.drop_duplicates("material").set_index("material")
    names = list(lines["line"])
    L = len(names)
    rows, vals = [], []
    if L:
        m = mat.loc[lines["material"]]
        col = lambda c: m[c].to_numpy(float)[:, None]
        E = col("E_MPa"); al = col("alpha_per_K"); k0 = col("k0_MPa")
        C = np.stack([col("C1_MPa"), col("C2_MPa"), col("C3_MPa")])
        G = np.stack([col("gamma1"), col("gamma2"), col("gamma3")])
        Q = col("Q_MPa"); B = col("b")
        R = lines["mean_radius_mm"].to_numpy(float)
        t = lines["wall_mm"].to_numpy(float)
        groups = {k: g.sort_values("state") for k, g in hist.groupby("line")}
        ns = max([len(groups[n]) for n in names if n in groups] + [1])
        P = np.zeros((L, ns)); D = np.zeros((L, ns))
        info = []
        for i, n in enumerate(names):
            g = groups.get(n)
            if g is None or len(g) == 0:
                info.append(None)
                continue
            k = len(g)
            P[i, :k] = g["pressure_MPa"].to_numpy(float); P[i, k:] = P[i, k - 1]
            D[i, :k] = g["dT_K"].to_numpy(float); D[i, k:] = D[i, k - 1]
            info.append((g["state"].to_numpy(int), g["checkpoint"].to_numpy(int)))
        EPS = simulate(E, al, k0, C, G, Q, B, R / t, P, D)
        for i, n in enumerate(names):
            if info[i] is None:
                continue
            st, cp = info[i]
            for k in np.nonzero(cp == 1)[0]:
                e = EPS[i, k] - P[i, k] * R[i] / (t[i] * E[i, 0])
                rows.append("%s-%05d" % (n, st[k]))
                vals.append(100.0 * e)
    pd.DataFrame({"row": rows, "ratchet_pct": vals}).to_csv(out, index=False, float_format="%.6g")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
