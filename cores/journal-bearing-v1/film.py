"""Journal bearing film solver: Reynolds equation with Reynolds (complementarity) rupture, two axial grooves.

theta is measured from the top of the bearing in the direction of rotation. Grooves at 90 and 270 deg.
The journal centre is displaced eps*c toward theta = psi, so H = 1 - eps*cos(theta - psi).
Dimensionless pressure Pb = p c^2 / (mu omega R^2); half length Z in [0, 1] with symmetry at Z = 0.
"""
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl


def coeffs(Reh, turbulent):
    if not turbulent:
        return 12.0 + 0 * Reh, 12.0 + 0 * Reh, 1.0 + 0 * Reh
    return 12.0 + 0.0136 * Reh ** 0.90, 12.0 + 0.0043 * Reh ** 0.96, 1.0 + 0.0012 * Reh ** 0.94


class Film:
    def __init__(self, nth, nz, lod, grooves=(0.25, 0.75)):
        assert nth % 4 == 0
        self.nth, self.nz, self.lod = nth, nz, lod
        self.th = np.arange(nth) * 2 * np.pi / nth
        self.dth = 2 * np.pi / nth
        self.dz = 1.0 / nz
        self.lam = (1.0 / lod) ** 2          # (2R/L)^2 = (D/L)^2
        self.groove = np.zeros(nth, bool)
        for g in grooves:
            self.groove[int(round(g * nth))] = True
        self.free = np.where(~np.repeat(self.groove[:, None], nz, 1).ravel())[0]   # unknown nodes (i, j), j = 0..nz-1
        self.wz = np.ones(nz); self.wz[0] = 0.5                                      # trapezoid on [0,1], end value 0
        self.last = None

    def assemble(self, eps, psi, Rec=0.0, turbulent=False):
        nth, nz, dth, dz = self.nth, self.nz, self.dth, self.dz
        thf = self.th + dth / 2                                   # face i+1/2
        Hf = 1 - eps * np.cos(thf - psi)
        Hn = 1 - eps * np.cos(self.th - psi)
        kt, _, _ = coeffs(Rec * Hf, turbulent)
        _, kzn, _ = coeffs(Rec * Hn, turbulent)
        Gf = Hf ** 3 / kt                                          # theta faces
        Gz = Hn ** 3 / kzn                                         # axial, at nodes
        idx = np.arange(nth * nz).reshape(nth, nz)
        ip, im = np.roll(idx, -1, 0), np.roll(idx, 1, 0)
        ae = np.repeat((Gf / dth ** 2)[:, None], nz, 1)            # to i+1
        aw = np.repeat((np.roll(Gf, 1) / dth ** 2)[:, None], nz, 1)
        an = np.repeat((self.lam * Gz / dz ** 2)[:, None], nz, 1)  # to j+1 (j = nz-1 -> end, p = 0)
        as_ = an.copy()
        rows, cols, vals = [], [], []
        diag = ae + aw + an + as_
        # symmetry at j = 0: p[-1] = p[1], so the j+1 coefficient doubles and there is no j-1 neighbour
        rows.append(idx.ravel()); cols.append(idx.ravel()); vals.append(diag.ravel())
        rows.append(idx.ravel()); cols.append(ip.ravel()); vals.append(-ae.ravel())
        rows.append(idx.ravel()); cols.append(im.ravel()); vals.append(-aw.ravel())
        up = an.copy(); up[:, 0] *= 2
        rows.append(idx[:, :-1].ravel()); cols.append(idx[:, 1:].ravel()); vals.append(-up[:, :-1].ravel())
        rows.append(idx[:, 1:].ravel()); cols.append(idx[:, :-1].ravel()); vals.append(-as_[:, 1:].ravel())
        A = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(nth * nz,) * 2)
        b = -0.5 * (Hf - np.roll(Hf, 1)) / dth                      # -(S dH/dtheta), S = 1/2 ; A p = b
        b = np.repeat(b[:, None], nz, 1).ravel()
        return A, b, Hn, Hf

    def solve(self, eps, psi, Rec=0.0, turbulent=False, warm=True):
        A, b, Hn, Hf = self.assemble(eps, psi, Rec, turbulent)
        n = self.nth * self.nz
        free = np.zeros(n, bool); free[self.free] = True
        act = free.copy()
        if warm and self.last is not None and self.last.shape[0] == n:
            act = free & self.last
        p = np.zeros(n)
        for it in range(60):
            ids = np.where(act)[0]
            p[:] = 0.0
            if len(ids):
                p[ids] = spl.spsolve(A[ids][:, ids].tocsc(), b[ids])
            neg = act & (p < 0)
            res = b - A @ p                                        # at inactive free nodes: want res <= 0
            pos = free & ~act & (res > 1e-13)
            if not neg.any() and not pos.any():
                break
            act = (act & ~neg) | pos
            p[neg] = 0.0
        self.last = act
        self.its = it + 1
        P = p.reshape(self.nth, self.nz)
        return P, Hn, Hf

    def integrals(self, P, Hn, Hf, Rec=0.0, turbulent=False):
        """Dimensionless: force components (toward theta=0 and theta=90 deg, of the pressure resultant), friction, peak."""
        w = self.wz[None, :] * self.dz * self.dth * 2.0              # both halves
        fx = np.sum(P * np.cos(self.th)[:, None] * w)
        fy = np.sum(P * np.sin(self.th)[:, None] * w)
        _, _, cf = coeffs(Rec * Hn, turbulent)
        couette = np.sum(cf / Hn) * self.dth * 2.0                   # full length, Z in [-1,1]
        dP = (np.roll(P, -1, 0) - np.roll(P, 1, 0)) / (2 * self.dth)
        poise = np.sum(0.5 * Hn[:, None] * dP * w)
        return fx, fy, couette + poise, P.max()
