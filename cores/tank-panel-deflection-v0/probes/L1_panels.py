#!/usr/bin/env python3
"""PS-4 flat wall panels: clamped, in-plane immovable rectangular plate under
uniform pressure, large-deflection (von Karman) theory, solved by a Ritz method
(Legendre-polynomial basis, quarter-plate symmetry) with Newton iteration and
load continuation.  Usage: python3 panels.py PACKAGE_DIR OUT_CSV"""
import sys, os, csv, json
for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')
import numpy as np
from numpy.polynomial import legendre as L

NW, NU, NQ = 10, 10, 14      # basis terms per direction (w, u/v), quad points

def basis(power, parity, n, x):
    """(1-x^2)^power * P_k(x), k of given parity; returns values, d1, d2 (n funcs)."""
    base = L.poly2leg(np.polynomial.polynomial.polypow([1, 0, -1], power))
    V, D1, D2 = [], [], []
    for i in range(n):
        k = 2 * i + parity
        c = L.legmul(base, np.eye(k + 1)[k])
        V.append(L.legval(x, c)); D1.append(L.legval(x, L.legder(c, 1)))
        D2.append(L.legval(x, L.legder(c, 2)))
    return np.array(V).T, np.array(D1).T, np.array(D2).T

_cache = {}
def bases(NW, NU, NQ):
    if (NW, NU, NQ) not in _cache:
        xg, wg = L.leggauss(2 * NQ)
        m = xg > 0; xq, wq = xg[m], wg[m]        # half-interval [0,1]
        pts = np.array([0.0, 1.0])
        _cache[NW, NU, NQ] = (xq, wq, basis(2, 0, NW, xq), basis(2, 0, NW, pts),
            basis(1, 1, NU, xq), basis(1, 0, NU, xq), basis(1, 0, NU, pts), basis(1, 1, NU, pts))
    return _cache[NW, NU, NQ]

def kron2(fx, fy):  # fx: (nq, nx), fy: (nq, ny) -> (nq*nq, nx*ny)
    return np.einsum('ia,jb->ijab', fx, fy).reshape(fx.shape[0] * fy.shape[0], -1)

class Shape:
    def __init__(self, r, nu, NW=NW, NU=NU, NQ=NQ):
        xq, wq, Wv, Wp, Ao, Ae, Aep, Aop = bases(NW, NU, NQ)
        self.its = 0; self.tan = None; self.q = 0.0
        self.r, self.nu = r, nu
        ix = 1.0 / r
        W, W1, W2 = Wv
        self.Wx = kron2(W1, W) * ix; self.Wy = kron2(W, W1)
        Wxx = kron2(W2, W) * ix * ix; Wyy = kron2(W, W2); Wxy = kron2(W1, W1) * ix
        Ao0, Ao1, _ = Ao; Ae0, Ae1, _ = Ae
        self.Ux = kron2(Ao1, Ae0) * ix; self.Uy = kron2(Ao0, Ae1)
        self.Vx = kron2(Ae1, Ao0) * ix; self.Vy = kron2(Ae0, Ao1)
        om = np.outer(wq, wq).ravel() * r
        self.om = om
        C = 1.0 / (1 - nu * nu); self.C = C; D = C / 12.0
        Bxx = Wxx * om[:, None]; Byy = Wyy * om[:, None]; Bxy = Wxy * om[:, None]
        self.Kb = D * (Wxx.T @ Bxx + Wyy.T @ Byy + nu * (Wxx.T @ Byy + Wyy.T @ Bxx)
                       + 2 * (1 - nu) * (Wxy.T @ Bxy))
        self.F = (kron2(W, W) * om[:, None]).sum(0)
        self.nw = NW * NW; self.nu_ = NU * NU
        # edge-middle (X=0, Y=1) and centre
        self.wc = np.kron(Wp[0][0], Wp[0][0])
        self.wyy_e = np.kron(Wp[0][0], Wp[2][1])
        self.vy_e = np.kron(Aep[0][0], Aop[1][1])
        self.x = np.zeros(self.nw + 2 * self.nu_)
        nq = len(om); so = np.sqrt(C * om)[:, None]; self.so = so
        self.l21 = nu; self.l22 = np.sqrt(1 - nu * nu); self.l33 = np.sqrt(0.5 * (1 - nu))
        Z = np.zeros_like(self.Ux)
        self.Buv = np.vstack([np.hstack([self.Ux, nu * self.Vy]) * so,
                              np.hstack([Z, self.l22 * self.Vy]) * so,
                              np.hstack([self.l33 * self.Uy, self.l33 * self.Vx]) * so])
        self.Huu_inv = np.linalg.inv(self.Buv.T @ self.Buv)

    def solve(self, q):
        nw, nn, C, nu, om = self.nw, self.nu_, self.C, self.nu, self.om
        x = self.x.copy()
        if self.tan is not None:
            x += (q - self.q) * self.tan
        for it in range(60):
            c, a, b = x[:nw], x[nw:nw + nn], x[nw + nn:]
            wx = self.Wx @ c; wy = self.Wy @ c
            ex = self.Ux @ a + 0.5 * wx * wx
            ey = self.Vy @ b + 0.5 * wy * wy
            gxy = self.Uy @ a + self.Vx @ b + wx * wy
            Nx = C * (ex + nu * ey) * om; Ny = C * (ey + nu * ex) * om
            Nxy = C * 0.5 * (1 - nu) * gxy * om
            gc = self.Kb @ c + self.Wx.T @ (Nx * wx + Nxy * wy) + self.Wy.T @ (Ny * wy + Nxy * wx) - q * self.F
            ga = self.Ux.T @ Nx + self.Uy.T @ Nxy
            gb = self.Vy.T @ Ny + self.Vx.T @ Nxy
            g = np.concatenate([gc, ga, gb])
            # Jacobian of strains, w columns (u, v columns are constant)
            Bw = np.vstack([(wx[:, None] * self.Wx + self.l21 * wy[:, None] * self.Wy) * self.so,
                            (self.l22 * wy[:, None] * self.Wy) * self.so,
                            (self.l33 * (wy[:, None] * self.Wx + wx[:, None] * self.Wy)) * self.so])
            Hg = self.Wx.T @ (Nx[:, None] * self.Wx + Nxy[:, None] * self.Wy) + \
                 self.Wy.T @ (Ny[:, None] * self.Wy + Nxy[:, None] * self.Wx)
            Hww = Bw.T @ Bw + self.Kb + Hg
            G = self.Buv.T @ Bw                       # (nuv, nw)
            HiG = self.Huu_inv @ G
            gu = g[nw:]
            S = Hww - G.T @ HiG
            rhs = g[:nw] - G.T @ (self.Huu_inv @ gu)
            dw = np.linalg.solve(S, rhs)
            du = self.Huu_inv @ gu - HiG @ dw
            dx = np.concatenate([dw, du]); self.its += 1
            x -= dx
            if np.abs(dx[:nw]).max() <= 1e-8 * max(np.abs(x[:nw]).max(), 1e-30):
                break
        self.x = x; self.q = q
        tw = np.linalg.solve(S, self.F)
        self.tan = np.concatenate([tw, -HiG @ tw])
        c, b = x[:nw], x[nw + nn:]
        w0 = self.wc @ c
        sig = C * (self.vy_e @ b) + 0.5 * C * abs(self.wyy_e @ c)
        return w0, sig

NR = 7            # Chebyshev nodes in aspect ratio over [1, 3]
QMIN, QSTEP = 0.1, 2.0

def table(nu, qmax):
    """log w and log sigma (sim units) on a grid of r nodes x log Q."""
    k = np.arange(NR)
    rn = 2.0 + np.cos(np.pi * (2 * k + 1) / (2 * NR))
    nq = max(2, int(np.ceil(np.log(max(qmax, QMIN) * 1.001 / QMIN) / np.log(QSTEP))) + 1)
    lq = np.log(QMIN) + np.arange(nq) * np.log(QSTEP)
    LW = np.empty((NR, nq)); LS = np.empty((NR, nq))
    for j, r in enumerate(rn):
        sh = Shape(r, nu, *((12, 12, 16) if qmax > 3000 else (NW, NU, NQ)))
        for m_, l in enumerate(lq):
            w, s = sh.solve(np.exp(l) / 16.0)
            LW[j, m_] = np.log(w); LS[j, m_] = np.log(s)
    return rn, lq, LW, LS

def bary(rn, r):
    """barycentric weights for Chebyshev(1st kind) nodes, evaluated at r."""
    NRl = len(rn); k = np.arange(NRl)
    wb = (-1.0) ** k * np.sin(np.pi * (2 * k + 1) / (2 * NRl))
    d = r - rn
    if np.any(np.abs(d) < 1e-14):
        e = np.zeros(NRl); e[np.argmin(np.abs(d))] = 1; return e
    c = wb / d
    return c / c.sum()

def evaluate(tab, r, Qs):
    from scipy.interpolate import CubicSpline
    rn, lq, LW, LS = tab
    c = bary(rn, r)
    lw = c @ LW; ls = c @ LS
    lQ = np.log(np.maximum(Qs, 1e-300))
    if len(lq) >= 4:
        fw, fs = CubicSpline(lq, lw)(lQ), CubicSpline(lq, ls)(lQ)
    else:
        fw, fs = np.interp(lQ, lq, lw), np.interp(lQ, lq, ls)
    lo = lQ <= lq[0]          # linear range: scale from first node
    fw[lo] = lw[0] + lQ[lo] - lq[0]; fs[lo] = ls[0] + lQ[lo] - lq[0]
    return np.exp(fw), np.exp(fs)

def main(pkg, out):
    from scipy.interpolate import CubicSpline
    mats = {r['material']: (float(r['E_GPa']) * 1e3, float(r['poisson']))
            for r in csv.DictReader(open(os.path.join(pkg, 'materials.csv')))}
    pans = {r['panel']: r for r in csv.DictReader(open(os.path.join(pkg, 'panels.csv')))}
    conds = list(csv.DictReader(open(os.path.join(pkg, 'conditions.csv'))))
    rows = []
    for c in conds:
        p = pans[c['panel']]
        a, b, t = float(p['a_mm']), float(p['b_mm']), float(p['t_mm'])
        if a < b: a, b = b, a
        E, nu = mats[p['material']]
        Q = abs(float(c['pressure_kPa'])) * 1e-3 * b ** 4 / (E * t ** 4)
        rows.append((c['row'], a / b, nu, Q, E, b, t))
    tabs = {}
    for nu in set(r[2] for r in rows):
        tabs[nu] = table(nu, max(r[3] for r in rows if r[2] == nu))
    groups = {}
    for i, rw in enumerate(rows):
        groups.setdefault((rw[1], rw[2]), []).append(i)
    res = [None] * len(rows)
    for (r, nu), idx in groups.items():
        Qs = np.array([rows[i][3] for i in idx])
        w, s = evaluate(tabs[nu], r, Qs)
        for k, i in enumerate(idx):
            name, _, _, Q, E, b, t = rows[i]
            res[i] = (0.0, 0.0) if Q == 0 else (w[k] * t, s[k] * E * (2 * t / b) ** 2)
    with open(out, 'w', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['row', 'deflection_mm', 'edge_stress_MPa'])
        for rw, (w, s) in zip(rows, res):
            wr.writerow([rw[0], '%.6g' % w, '%.6g' % s])

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
