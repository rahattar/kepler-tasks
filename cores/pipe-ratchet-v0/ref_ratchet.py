#!/usr/bin/env python3
"""Reference for the pipe-ratchet core: python3 ratchet.py WORKS_DIR OUT_CSV

All lines of a works are carried together, one load state after another. Each ramp is solved at its end in one
step (two equal steps where the pressure changes along it) with the exact laws of the Chaboche and Voce
hardening under plastic flow of one sign, by one Newton iteration on the hoop strain and every layer's plastic
increment together: the layers' equations are each in one unknown besides the hoop strain, so the equilibrium
row is closed by elimination."""
import csv, os, sys
import numpy as np

NL = 24
INV = 1.0 / NL
ITS = [0]
Z = (np.arange(NL) + 0.5) / NL - 0.5


def main(wd, out):
    mats = {r["material"]: r for r in csv.DictReader(open(os.path.join(wd, "materials.csv")))}
    lines = list(csv.DictReader(open(os.path.join(wd, "lines.csv"))))
    hist = {}
    for r in csv.DictReader(open(os.path.join(wd, "history.csv"))):
        hist.setdefault(r["line"], []).append((int(r["state"]), float(r["pressure_MPa"]), float(r["dT_K"]), r["checkpoint"] == "1"))
    n = len(lines)
    f = lambda key: np.array([float(mats[l["material"]][key]) for l in lines])[:, None]
    E, A, k0, Q, b = f("E_MPa"), f("alpha_per_K"), f("k0_MPa"), f("Q_MPa"), f("b")
    C = np.stack([f("C%d_MPa" % i)[:, 0] for i in (1, 2, 3)], -1)[:, None, :]
    G = np.stack([f("gamma%d" % i)[:, 0] for i in (1, 2, 3)], -1)[:, None, :]
    sat = C / G
    Rt = np.array([float(l["mean_radius_mm"]) / float(l["wall_mm"]) for l in lines])
    H = [sorted(hist[l["line"]]) for l in lines]
    T = max(len(h) for h in H)
    P = np.array([[h[min(k, len(h) - 1)][1] for k in range(T)] for h in H]) * Rt[:, None]
    D = np.array([[h[min(k, len(h) - 1)][2] for k in range(T)] for h in H])
    ck = [[(k, h[k][3]) for k in range(len(h))] for h in H]
    ep = np.zeros((n, NL)); X = np.zeros((n, NL, 3)); R = np.zeros((n, NL)); eps = np.zeros(n)
    rows = []
    nz = -Z[None, :]
    for k in range(1, T):
        parts = 2 if np.any(P[:, k] != P[:, k - 1]) else 1
        for j in range(1, parts + 1):
            w = j / parts
            sm = P[:, k - 1] + w * (P[:, k] - P[:, k - 1]); dT = D[:, k - 1] + w * (D[:, k] - D[:, k - 1])
            epth = A * dT[:, None] * nz
            Xs = X.sum(-1); kk = k0 + R
            base = epth + ep
            # elastic predictor of equilibrium with the plastic strains frozen
            e = sm / E[:, 0] + base.sum(1) * INV
            tr = E * (e[:, None] - base)
            over = np.abs(tr - Xs) - kk
            if (over <= 0).all():
                eps = e
                continue
            act = over > 0
            nn = np.where(tr >= Xs, 1.0, -1.0)
            dp = np.zeros((n, NL))
            for it in range(60):
                ITS[0] += 1
                tr = E * (e[:, None] - base)
                ex = np.exp(-G * dp[..., None]); a = X - nn[..., None] * sat
                Xn = (nn[..., None] * sat + a * ex).sum(-1); dX = (G * a * ex).sum(-1)
                eb = (R - Q) * np.exp(-b * dp)
                sig = tr - E * nn * dp
                g = np.where(act, nn * (sig - Xn) - Q - k0 - eb, 0.0)
                dgdp = np.where(act, nn * dX - E + b * eb, 1.0)
                q = np.where(act, nn * E / dgdp, 0.0)              # d dp / d e = -q
                r = sig.sum(1) * INV - sm
                gd = np.where(act, g / dgdp, 0.0)
                de = (-r - (E * nn * gd).sum(1) * INV) / (E[:, 0] + (E * nn * q).sum(1) * INV)
                ddp = -gd - q * de[:, None]
                e = e + de; dp = dp + ddp
                if np.abs(ddp).max() < 1e-10 and np.abs(r).max() < 1e-5:
                    neg = act & (dp < 0)
                    tr2 = E * (e[:, None] - base)
                    beyond = (~act) & (np.abs(tr2 - Xs) > kk + 1e-9)
                    if not (neg.any() or beyond.any()):
                        break
                    act = (act & ~neg) | beyond
                    nn = np.where(beyond, np.where(tr2 >= Xs, 1.0, -1.0), nn)
                    dp = np.where(act, np.maximum(dp, 0.0), 0.0)
            ex = np.exp(-G * dp[..., None])
            X = nn[..., None] * sat + (X - nn[..., None] * sat) * ex
            R = Q + (R - Q) * np.exp(-b * dp)
            ep = ep + nn * dp
            eps = e
        for i in range(n):
            if k < len(H[i]) and H[i][k][3]:
                rows.append(["%s-%05d" % (lines[i]["line"], k), "%.6f" % (100 * (eps[i] - P[i, k] / E[i, 0]))])
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["row", "ratchet_pct"]); w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
