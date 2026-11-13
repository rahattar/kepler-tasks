"""fd_check.py: a second solution of the fixed-edge plate, written apart from plate.py: nodal displacements on a
uniform grid, the stretching of the middle surface on bilinear cells with 2 x 2 Gauss points, the bending by
finite differences of the Laplacian with mirrored ghost nodes, Newton on the sparse system, Richardson in the
mesh size. Dimensionless as in plate.py."""
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spl

def operators(r, N):
    Ny = N; Nx = int(round(r * N)); hx = r / Nx; hy = 1.0 / Ny
    nid = -np.ones((Nx + 1, Ny + 1), int)
    k = 0
    for i in range(1, Nx):
        for j in range(1, Ny):
            nid[i, j] = k; k += 1
    n = k
    # Laplacian at every node, ghost values mirrored (zero slope), boundary values zero
    rows, cols, vals = [], [], []
    wt = np.zeros((Nx + 1) * (Ny + 1))
    def add(row, i, j, v):
        if 0 <= i <= Nx and 0 <= j <= Ny and nid[i, j] >= 0:
            rows.append(row); cols.append(nid[i, j]); vals.append(v)
    for i in range(Nx + 1):
        for j in range(Ny + 1):
            row = i * (Ny + 1) + j
            wt[row] = hx * hy * (0.5 if i in (0, Nx) else 1.0) * (0.5 if j in (0, Ny) else 1.0)
            for (di, h) in ((1, hx),):
                im, ip = i - 1, i + 1
                if im < 0: im = 1
                if ip > Nx: ip = Nx - 1
                add(row, im, j, 1 / h ** 2); add(row, ip, j, 1 / h ** 2); add(row, i, j, -2 / h ** 2)
            jm, jp = j - 1, j + 1
            if jm < 0: jm = 1
            if jp > Ny: jp = Ny - 1
            add(row, i, jm, 1 / hy ** 2); add(row, i, jp, 1 / hy ** 2); add(row, i, j, -2 / hy ** 2)
    Lap = sp.csr_matrix((vals, (rows, cols)), shape=((Nx + 1) * (Ny + 1), n))
    # gradients at the four Gauss points of every cell
    g = 0.5 / np.sqrt(3.0)
    rx, cx, vx, ry, cy, vy, rv, cv, vv = [], [], [], [], [], [], [], [], []
    row = 0
    for i in range(Nx):
        for j in range(Ny):
            for (s, t) in ((0.5 - g, 0.5 - g), (0.5 + g, 0.5 - g), (0.5 - g, 0.5 + g), (0.5 + g, 0.5 + g)):
                for (a, b, Nv, dNs, dNt) in ((0, 0, (1 - s) * (1 - t), -(1 - t), -(1 - s)), (1, 0, s * (1 - t), (1 - t), -s),
                                             (0, 1, (1 - s) * t, -t, (1 - s)), (1, 1, s * t, t, s)):
                    c = nid[i + a, j + b]
                    if c >= 0:
                        rx.append(row); cx.append(c); vx.append(dNs / hx)
                        ry.append(row); cy.append(c); vy.append(dNt / hy)
                row += 1
    Gx = sp.csr_matrix((vx, (rx, cx)), shape=(row, n)); Gy = sp.csr_matrix((vy, (ry, cy)), shape=(row, n))
    wg = np.full(row, hx * hy / 4.0)
    return dict(Nx=Nx, Ny=Ny, hx=hx, hy=hy, nid=nid, n=n, Lap=Lap, wt=wt, Gx=Gx, Gy=Gy, wg=wg)

def solve(r, nu, Qs, N):
    o = operators(r, N); n = o["n"]; Gx, Gy, wg, Lap, wt = o["Gx"], o["Gy"], o["wg"], o["Lap"], o["wt"]
    Cm = np.array([[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]])
    Kb = (Lap.T @ sp.diags(wt) @ Lap) / 12.0
    Z = sp.csr_matrix((Gx.shape[0], n))
    Bm = [sp.hstack([Gx, Z]).tocsr(), sp.hstack([Z, Gy]).tocsr(), sp.hstack([Gy, Gx]).tocsr()]
    Km = sum(Cm[i, j] * (Bm[i].T @ sp.diags(wg) @ Bm[j]) for i in range(3) for j in range(3) if Cm[i, j])
    nid = o["nid"]
    fl = np.zeros(n)
    for i in range(1, o["Nx"]):
        for j in range(1, o["Ny"]):
            fl[nid[i, j]] = o["hx"] * o["hy"]
    fl *= (1 - nu * nu)
    z = np.zeros(3 * n); out = []; prev = None
    for Q in Qs:
        if prev is not None: z = z.copy(); z[:n] *= (Q / prev) ** (1 / 3.0)
        for it in range(60):
            c, d = z[:n], z[n:]
            wx = Gx @ c; wy = Gy @ c
            e = np.array([Bm[0] @ d + 0.5 * wx * wx, Bm[1] @ d + 0.5 * wy * wy, Bm[2] @ d + wx * wy])
            s = Cm @ e
            gw = Kb @ c + Gx.T @ (wg * (s[0] * wx + s[2] * wy)) + Gy.T @ (wg * (s[1] * wy + s[2] * wx)) - Q * fl
            gd = Bm[0].T @ (wg * s[0]) + Bm[1].T @ (wg * s[1]) + Bm[2].T @ (wg * s[2])
            Ew = [sp.diags(wx) @ Gx, sp.diags(wy) @ Gy, sp.diags(wx) @ Gy + sp.diags(wy) @ Gx]
            CE = [Cm[0, 0] * Ew[0] + Cm[0, 1] * Ew[1], Cm[1, 0] * Ew[0] + Cm[1, 1] * Ew[1], Cm[2, 2] * Ew[2]]
            D = sp.diags(wg)
            Hww = Kb + sum(Ew[i].T @ D @ CE[i] for i in range(3)) + Gx.T @ sp.diags(wg * s[0]) @ Gx + Gy.T @ sp.diags(wg * s[1]) @ Gy
            t = Gx.T @ sp.diags(wg * s[2]) @ Gy; Hww = Hww + t + t.T
            Hwd = sum(CE[i].T @ D @ Bm[i] for i in range(3))
            H = sp.bmat([[Hww, Hwd], [Hwd.T, Km]]).tocsc()
            dz = spl.spsolve(H, -np.concatenate([gw, gd]))
            z = z + dz
            if np.abs(dz).max() < 1e-9 * max(1.0, np.abs(z).max()): break
        else:
            raise RuntimeError("no convergence")
        prev = Q
        Nx, Ny, hy = o["Nx"], o["Ny"], o["hy"]
        W = z[:n]; V = z[2 * n:]
        ic = Nx // 2
        Wc = W[nid[ic, Ny // 2]]
        w1, w2, w3 = (W[nid[ic, j]] for j in (1, 2, 3))
        A = np.array([[1, 1, 1], [4, 8, 16], [9, 27, 81]], float)
        a2 = np.linalg.solve(A, [w1, w2, w3])[0]              # w = a2 (y/h)^2 + ...
        Wyy = 2 * a2 / hy ** 2
        v1, v2, v3 = (V[nid[ic, j]] for j in (1, 2, 3))
        Vy = (18 * v1 - 9 * v2 + 2 * v3) / (6 * hy)
        k = 1 / (1 - nu * nu)
        out.append((Wc, k * Vy + 0.5 * k * abs(Wyy)))
    return np.array(out)

def richardson(r, nu, Qs, Ns=(24, 36, 48)):
    """second-order extrapolation from the two finest grids; the third shows the order."""
    res = [solve(r, nu, Qs, N) for N in Ns]
    h = [1.0 / N for N in Ns]
    ext = res[2] + (res[2] - res[1]) * h[2] ** 2 / (h[1] ** 2 - h[2] ** 2)
    return res, ext

if __name__ == "__main__":
    import sys, time
    from plate import curve
    np.set_printoptions(precision=5, suppress=True, linewidth=150)
    Qs = [5.0, 60.0, 400.0, 2000.0]
    for r, nu in ((1.0, 0.3), (2.0, 0.33)):
        t = time.time(); res, ext = richardson(r, nu, Qs); ref = curve(r, nu, Qs, n=12)[:, [0, 2]]
        print("r", r, "nu", nu, "%.0fs" % (time.time() - t))
        for a in res: print("  grid   ", a.T.ravel())
        print("  extrap ", ext.T.ravel()); print("  Ritz   ", ref.T.ravel())
        print("  extrap/Ritz - 1, %:", (100 * (ext / ref - 1)).T.ravel())
