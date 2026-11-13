#!/usr/bin/env python3
"""PS-4 flat panel calculation: clamped rectangular plate, edges held in-plane,
von Karman large-deflection theory solved by Ritz (Legendre-polynomial bases) + Newton."""
import sys, csv, json, os
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
from numpy.polynomial import polynomial as P
from numpy.polynomial import legendre as L
from scipy.linalg import lu_factor, lu_solve

# (S limit, basis terms per direction, Gauss points per half side); S = edge stress * b^2 / (E t^2)
TIERS = [(60.0, 6, 12), (150.0, 7, 14), (350.0, 8, 16), (650.0, 9, 18), (1100.0, 10, 20), (2000.0, 12, 24), (float("inf"), 16, 32)]


def leg(n):
    c = np.zeros(n + 1); c[n] = 1
    return L.leg2poly(c)


def fam(kind, n):
    """1D basis polynomials (power coefficients)."""
    out = []
    for i in range(n):
        if kind == "w":   # even, clamped: (1-x^2)^2 P_2i
            out.append(P.polymul([1, 0, -2, 0, 1], leg(2 * i)))
        elif kind == "e":  # even, zero at ends: (1-x^2) P_2i
            out.append(P.polymul([1, 0, -1], leg(2 * i)))
        else:              # odd, zero at ends: (1-x^2) P_2i+1
            out.append(P.polymul([1, 0, -1], leg(2 * i + 1)))
    return out


def tab(polys, x, d):
    return np.array([P.polyval(x, P.polyder(p, d)) if d else P.polyval(x, p) for p in polys]).T


class Basis:
    """Ritz bases with NB terms per direction, NQ Gauss points per half side."""
    def __init__(self, NB, NQ):
        xg, wg = L.leggauss(NQ)
        xg = 0.5 * (xg + 1); wg = wg  # [0,1], weights x0.5 then x2 for symmetry
        W2 = np.outer(wg, wg).ravel()  # integrands are even in x and y
        T = {}
        for k in ("w", "e", "o"):
            ps = fam(k, NB)
            T[k] = [tab(ps, xg, d) for d in range(3)]


        def prod(kx, dx, ky, dy):
            # basis value at (xi_i, eta_j) -> rows i*NQ+j, cols p*NB+q
            A = T[kx][dx]; B = T[ky][dy]
            return np.einsum("ip,jq->ijpq", A, B).reshape(NQ * NQ, NB * NB)


        # w basis: w(x)e(y) ; u: o(x)e(y) ; v: e(x)o(y)
        Wb = {(dx, dy): prod("w", dx, "w", dy) for dx, dy in [(0, 0), (1, 0), (0, 1), (2, 0), (0, 2), (1, 1)]}
        Ub = {d: prod("o", d[0], "e", d[1]) for d in [(1, 0), (0, 1)]}
        Vb = {d: prod("e", d[0], "o", d[1]) for d in [(1, 0), (0, 1)]}
        # edge-middle evaluation (xi=0, eta=1)
        def at(kind, d, x):
            return np.array([P.polyval(x, P.polyder(p, d)) if d else P.polyval(x, p) for p in fam(kind, NB)])
        EDGE = {}
        EDGE["wyy"] = np.outer(at("w", 0, 0.0), at("w", 2, 1.0)).ravel()
        EDGE["wxx"] = np.outer(at("w", 2, 0.0), at("w", 0, 1.0)).ravel()
        EDGE["vy"] = np.outer(at("e", 0, 0.0), at("o", 1, 1.0)).ravel()
        EDGE["ux"] = np.outer(at("o", 1, 0.0), at("e", 0, 1.0)).ravel()
        CEN = np.outer(at("w", 0, 0.0), at("w", 0, 0.0)).ravel()
        LOADV = Wb[(0, 0)].T @ W2



        self.NB, self.Wb, self.Ub, self.Vb = NB, Wb, Ub, Vb
        self.EDGE, self.CEN, self.LOADV, self.W2 = EDGE, CEN, LOADV, W2


class Panel:
    """Dimensionless: x=xi*a/2, y=eta*b/2, w=t*W, u=(t^2/b)*U, v=(t^2/b)*V.
    Energy scaled by D t^2 /(ab) ... built directly from physical expressions."""
    def __init__(s, a, b, t, E, nu, bs):
        Wb, Ub, Vb, W2, NB, LOADV = bs.Wb, bs.Ub, bs.Vb, bs.W2, bs.NB, bs.LOADV
        s.bs = bs
        s.a, s.b, s.t, s.E, s.nu = a, b, t, E, nu
        hx, hy = 2.0 / a, 2.0 / b
        n = NB * NB; s.n = n
        # derivative matrices in physical coords; w = t*cW, u,v = t^2/b * c
        s.wx = Wb[(1, 0)] * hx * t; s.wy = Wb[(0, 1)] * hy * t
        s.wxx = Wb[(2, 0)] * hx * hx * t; s.wyy = Wb[(0, 2)] * hy * hy * t
        s.wxy = Wb[(1, 1)] * hx * hy * t
        su = t * t / b
        s.ux = Ub[(1, 0)] * hx * su; s.uy = Ub[(0, 1)] * hy * su
        s.vx = Vb[(1, 0)] * hx * su; s.vy = Vb[(0, 1)] * hy * su
        s.jw = W2 * (a * b / 4.0)
        D = E * t ** 3 / (12 * (1 - nu * nu)); C = E * t / (1 - nu * nu)
        s.D, s.C = D, C
        # bending stiffness (constant)
        j = s.jw[:, None]
        Kb = D * (s.wxx.T @ (j * s.wxx) + s.wyy.T @ (j * s.wyy)
                  + nu * (s.wxx.T @ (j * s.wyy) + s.wyy.T @ (j * s.wxx))
                  + 2 * (1 - nu) * s.wxy.T @ (j * s.wxy))
        s.Kb = Kb
        s.f = t * (a * b / 4.0) * LOADV
        s.x = np.zeros(3 * n)
        s.Bu = np.hstack([s.ux, np.zeros_like(s.ux)])        # eps_x lin part wrt (u,v)
        s.Bv = np.hstack([np.zeros_like(s.vy), s.vy])
        s.Bg = np.hstack([s.uy, s.vx])

    def prep(s):
        j = s.jw; nu = s.nu; C = s.C
        s.jc = j * C
        s.Bx = s.Bu + nu * s.Bv; s.By = s.Bv + nu * s.Bu
        jc = s.jc[:, None]
        s.Kmm = (s.Bu.T @ (jc * s.Bx) + s.Bv.T @ (jc * s.By)
                 + (1 - nu) / 2 * s.Bg.T @ (jc * s.Bg))
        s.Kmi = np.linalg.inv(s.Kmm)
        s.Bxt = s.Bx.T.copy(); s.Byt = s.By.T.copy(); s.Bgt = (s.Bg.T * ((1 - nu) / 2)).copy()

    def memb(s, c, wx=None, wy=None):
        n = s.n; jc = s.jc
        if wx is None:
            wx = s.wx @ c[:n]; wy = s.wy @ c[:n]
        Rm0 = s.Bxt @ (jc * (0.5 * wx * wx)) + s.Byt @ (jc * (0.5 * wy * wy)) + s.Bgt @ (jc * (wx * wy))
        c[n:] = -s.Kmi @ Rm0
        return c[n:]

    def resid_jac(s, c, q, jac=True):
        n = s.n; cw = c[:n]
        wx = s.wx @ cw; wy = s.wy @ cw
        # membrane displacements in equilibrium with w (exact: membrane problem is linear)
        jc = s.jc
        cm = s.memb(c, wx, wy)
        ex = s.Bu @ cm + 0.5 * wx * wx
        ey = s.Bv @ cm + 0.5 * wy * wy
        g = s.Bg @ cm + wx * wy
        nu, j = s.nu, s.jw
        jc = s.jc
        jNx = jc * (ex + nu * ey); jNy = jc * (ey + nu * ex); jNxy = jc * ((1 - nu) / 2) * g
        Rw = s.Kb @ cw + s.wx.T @ (wx * jNx + wy * jNxy) + s.wy.T @ (wy * jNy + wx * jNxy) - q * s.f
        if not jac:
            return Rw
        h = (1 - nu) / 2
        dA = jc * (wx * wx + h * wy * wy) + jNx
        dB = jc * (wy * wy + h * wx * wx) + jNy
        dC = jc * wx * wy * (nu + h) + jNxy
        WxA = s.wx * dA[:, None]; WyC = s.wy * dC[:, None]
        Kww = s.Kb + s.wx.T @ (WxA + WyC) + s.wy.T @ (s.wy * dB[:, None] + s.wx * dC[:, None])
        # coupling: d(eps)/dcw = wx*Wx etc.; Kwm = sum over strains
        jwx = (jc * wx)[:, None]; jwy = (jc * wy)[:, None]
        Pu = np.hstack([jwx * s.ux, jwx * s.vy * nu])      # eps_x coupling: wx*Wx * C(Bu+nu Bv)
        Qv = np.hstack([jwy * s.ux * nu, jwy * s.vy])      # eps_y
        Rg = np.hstack([s.uy, s.vx]) * h
        Kwm = s.wx.T @ (Pu + jwy * Rg) + s.wy.T @ (Qv + jwx * Rg)
        Kred = Kww - (Kwm @ s.Kmi) @ Kwm.T
        return Rw, Kred

    def solve(s, q, c0):
        """Newton on the deflection coefficients (membrane condensed out exactly);
        the last factorised tangent is reused while it converges fast enough."""
        c = c0.copy()
        n = s.n
        prev = None
        for it in range(80):
            if s.lu is None:
                R, K = s.resid_jac(c, q)
                s.lu = lu_factor(K)
                prev = None
            else:
                R = s.resid_jac(c, q, jac=False)
            dc = -lu_solve(s.lu, R)
            nd = np.max(np.abs(dc))
            if prev is not None and nd > 0.3 * prev:
                s.lu = None           # slow or diverging: fresh tangent next time
            c[:n] += dc
            prev = nd
            if nd < 1e-5 * np.max(np.abs(c[:n])):
                break
        else:
            raise RuntimeError("no convergence")
        s.memb(c)
        return c

    def linear_S(s, q):
        c = np.zeros(3 * s.n); c[:s.n] = q * np.linalg.solve(s.Kb, s.f)
        return s.results(c, q)[1] * s.b * s.b / (s.E * s.t * s.t)

    def results(s, c, q):
        n = s.n; cw = c[:n]; cu = c[n:2 * n]; cv = c[2 * n:]
        t, a, b, E, nu = s.t, s.a, s.b, s.E, s.nu
        EDGE = s.bs.EDGE
        w0 = t * s.bs.CEN @ cw
        wyy = t * (2 / b) ** 2 * EDGE["wyy"] @ cw
        wxx = t * (2 / a) ** 2 * EDGE["wxx"] @ cw   # zero at clamped edge
        su = t * t / b
        ey = su * (2 / b) * EDGE["vy"] @ cv     # slopes vanish at edge
        ex = su * (2 / a) * EDGE["ux"] @ cu
        sm = E / (1 - nu * nu) * (ey + nu * ex)
        sb = E / (1 - nu * nu) * (t / 2) * abs(wyy + nu * wxx)
        return abs(w0), sm + sb

    def run(s, qs):
        # continuation in increasing |q| (result is symmetric in the sign of q)
        s.prep()
        s.lu = None
        out = {}
        hist = [(0.0, np.zeros(3 * s.n))]
        lin = np.linalg.solve(s.Kb, s.f)
        for q in sorted(set(abs(q) for q in qs)):
            if q == 0:
                out[q] = (0.0, 0.0); continue
            if len(hist) == 1:
                c0 = np.zeros(3 * s.n); c0[:s.n] = q * lin
            else:
                (q1, c1), (q2, c2) = hist[-2], hist[-1]
                c0 = c2 + (c2 - c1) * min((q - q2) / (q2 - q1), 2.0)
            try:
                c = s.solve(q, c0)
            except (RuntimeError, np.linalg.LinAlgError, ValueError):
                s.lu = None
                q2, c = hist[-1]
                for qq in np.linspace(q2, q, 41)[1:]:
                    c = s.solve(qq, c); s.lu = None
            hist.append((q, c))
            out[q] = s.results(c, q)
        return [out[abs(q)] for q in qs]


BASES = {}


def dec(x):
    """Plain decimal (no exponent), six significant figures."""
    return np.format_float_positional(float(x), precision=6, unique=False, fractional=False, trim="-")


def main(pkg, outp):
    mats = {r["material"]: (float(r["E_GPa"]) * 1e3, float(r["poisson"]))
            for r in csv.DictReader(open(os.path.join(pkg, "materials.csv"), newline="", encoding="utf-8-sig"))}
    pans = {}
    for r in csv.DictReader(open(os.path.join(pkg, "panels.csv"), newline="", encoding="utf-8-sig")):
        a, b = float(r["a_mm"]), float(r["b_mm"])
        if b > a: a, b = b, a
        pans[r["panel"].strip()] = (a, b, float(r["t_mm"]), r["material"].strip())
    conds = list(csv.DictReader(open(os.path.join(pkg, "conditions.csv"), newline="", encoding="utf-8-sig")))
    by = {}
    for i, r in enumerate(conds):
        by.setdefault(r["panel"].strip(), []).append(i)
    res = [None] * len(conds)
    for pn, idx in by.items():
        a, b, t, m = pans[pn]
        E, nu = mats[m]
        qs = [float(conds[i]["pressure_kPa"]) * 1e-3 for i in idx]
        # predictor: the cheapest basis gives the edge stress parameter S to a few per cent
        if 6 not in BASES:
            BASES[6] = Basis(6, 12)
        rr = Panel(a, b, t, E, nu, BASES[6]).run(qs)
        S = 1.08 * max(r_[1] for r_ in rr) * b * b / (E * t * t)
        k = next(k for k, tr in enumerate(TIERS) if S < tr[0])
        if k > 0:
            lim, nb, nq = TIERS[k]
            if nb not in BASES:
                BASES[nb] = Basis(nb, nq)
            rr = Panel(a, b, t, E, nu, BASES[nb]).run(qs)
        for i, r_ in zip(idx, rr):
            res[i] = r_
    with open(outp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["row", "deflection_mm", "edge_stress_MPa"])
        for r, (d, sg) in zip(conds, res):
            w.writerow([r["row"].strip(), dec(d), dec(sg)])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
