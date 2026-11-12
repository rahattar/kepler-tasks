"""A correct but unoptimised version of ref_demand.py, for the time limit: each placement's demand by bisection on
the base pressure, every network solve from a cold start. Same test design and identification."""
import sys

import numpy as np

import ref_demand as R

PSI_FT = R.PSI_FT


def area_demand_bisect(self, r, heads, q0=None):
    en = [self.ix[h] for h in heads]
    eK = np.array([self.heads[h]["K"] for h in heads], float)
    req = np.maximum(R.P_HEAD_MIN, (self.q_min / eK) ** 2)

    def solve(P0):
        # fixed base, emitters: the general solver, from scratch
        B, c, Rr, NN = self._links(np.array(en), eK, r)
        import scipy.sparse as sp
        import scipy.sparse.linalg as spla
        BT = B.T.tocsr()
        free = np.ones(self.n, bool)
        free[self.base] = False
        H = PSI_FT * self.z + P0
        Q = np.full(B.shape[0], 5.0)
        for _ in range(80):
            aq = np.maximum(np.abs(Q), 1e-4)
            hl = Rr * aq ** (NN - 1) * Q
            invD = 1.0 / (NN * Rr * aq ** (NN - 1))
            M = (BT @ sp.diags(invD) @ B).tocsr()
            rhs = -BT @ (Q - invD * (hl + c))
            Mf = M[free]
            H[free] = spla.spsolve(Mf[:, free].tocsc(), rhs[free] - Mf[:, ~free] @ H[~free])
            Qn = Q - invD * (hl + c) + invD * (B @ H)
            Qn[self.m:] = np.maximum(Qn[self.m:], 0)
            if np.max(np.abs(Qn - Q)) < 1e-7 * max(1, np.max(np.abs(Qn))):
                Q = Qn
                break
            Q = Qn
        p = H - PSI_FT * self.z
        return float(np.min(p[en] - req)), float(np.sum(Q[self.m:]))

    lo, hi = 5.0, 400.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        mg, qt = solve(mid)
        if mg < 0:
            lo = mid
        else:
            hi = mid
    return hi, qt, None


R.System.area_demand = area_demand_bisect

if __name__ == "__main__":
    sys.exit(R.main(sys.argv))
