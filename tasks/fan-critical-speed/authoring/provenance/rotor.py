"""The sealed rotor model of MS-RD: an overhung fan rotor on two pedestals.

- Shaft: Euler-Bernoulli beam elements (consistent mass) in the horizontal and the vertical plane, from the sections
  of the shaft as installed; the shaft's own polar inertia lumped at the nodes.
- Impeller and coupling hub: rigid bodies at their centers of gravity (mass, transverse and polar inertia).
- Each bearing: a radial spring between the shaft and its pedestal; each pedestal: a lumped mass on a horizontal and
  a vertical spring to the foundation (a list gives the drive-end and fan-end values when they differ, as in a test
  with a stay removed).
- Gyroscopic coupling of the planes through the polar inertias.

DOFs per shaft node: u, v (lateral), a = du/dz, b = dv/dz; then uP, vP per bearing.
standstill() gives the lowest natural frequencies in each plane at rest (what an impact test measures);
criticals() the critical speeds: the running speeds W at which K - W^2 (M - iG) is singular, so that the undamped
synchronous response to unbalance is unbounded (a Hermitian generalized eigenproblem, solved for 1/W^2);
response() the damped synchronous unbalance response, used only to confirm that every critical speed is a response
peak."""
import numpy as np
from scipy.linalg import eigh

E, RHO = 2.07e11, 7850.0


def beam(L, d, di=0.0):
    A = np.pi * (d ** 2 - di ** 2) / 4; I = np.pi * (d ** 4 - di ** 4) / 64
    k = E * I / L ** 3 * np.array([[12, 6 * L, -12, 6 * L], [6 * L, 4 * L * L, -6 * L, 2 * L * L],
                                    [-12, -6 * L, 12, -6 * L], [6 * L, 2 * L * L, -6 * L, 4 * L * L]])
    m = RHO * A * L / 420 * np.array([[156, 22 * L, 54, -13 * L], [22 * L, 4 * L * L, 13 * L, -3 * L * L],
                                       [54, 13 * L, 156, -22 * L], [-13 * L, -3 * L * L, -22 * L, 4 * L * L]])
    Ip = RHO * 2 * I * L          # polar inertia of the element, lumped half to each node
    return k, m, Ip


def assemble(R, mesh=0.02):
    """R: dict(shaft=[(z0, z1, d), ...] in m, disks=[(z, m, Id, Ip)], bearings=[z1, z2], kb, mp, kpH, kpV).
    Returns K, M, G and dof helpers."""
    pts = {0.0}
    for z0, z1, d in R["shaft"]:
        n = max(1, int(np.ceil((z1 - z0) / mesh)))
        pts.update(np.linspace(z0, z1, n + 1))
    for z in [x[0] for x in R["disks"]] + list(R["bearings"]):
        pts.add(z)
    z = np.array(sorted(round(p, 6) for p in pts)); z = np.unique(z)
    N = len(z); nd = 4 * N + 4
    K = np.zeros((nd, nd)); M = np.zeros((nd, nd)); G = np.zeros((nd, nd))
    def dia(zm):
        for z0, z1, d in R["shaft"]:
            if z0 - 1e-9 <= zm <= z1 + 1e-9:
                return d
        raise ValueError(zm)
    for e in range(N - 1):
        L = z[e + 1] - z[e]; d = dia(0.5 * (z[e] + z[e + 1]))
        k, m, Ip = beam(L, d)
        for plane, (iu, ia) in enumerate(((0, 2), (1, 3))):
            idx = [4 * e + iu, 4 * e + ia, 4 * (e + 1) + iu, 4 * (e + 1) + ia]
            K[np.ix_(idx, idx)] += k; M[np.ix_(idx, idx)] += m
        for nn in (e, e + 1):
            G[4 * nn + 2, 4 * nn + 3] += Ip / 2; G[4 * nn + 3, 4 * nn + 2] -= Ip / 2
    node = lambda zz: int(np.argmin(abs(z - zz)))
    for zd, md, Id, Ipd in R["disks"]:
        n = node(zd)
        M[4 * n, 4 * n] += md; M[4 * n + 1, 4 * n + 1] += md
        M[4 * n + 2, 4 * n + 2] += Id; M[4 * n + 3, 4 * n + 3] += Id
        G[4 * n + 2, 4 * n + 3] += Ipd; G[4 * n + 3, 4 * n + 2] -= Ipd
    for j, zb in enumerate(R["bearings"]):
        n = node(zb); p = 4 * N + 2 * j
        kH = R["kpH"][j] if np.ndim(R["kpH"]) else R["kpH"]; kV = R["kpV"][j] if np.ndim(R["kpV"]) else R["kpV"]
        for s, pd, kp in ((0, p, kH), (1, p + 1, kV)):
            i = 4 * n + s
            K[i, i] += R["kb"]; K[pd, pd] += R["kb"] + kp; K[i, pd] -= R["kb"]; K[pd, i] -= R["kb"]
            M[pd, pd] += R["mp"]
    return K, M, G, z, node, N


def standstill(R, n=2):
    """Lowest natural frequencies (Hz) in the horizontal and the vertical plane, rotor at rest."""
    K, M, G, z, node, N = assemble(R)
    lam, V = eigh(K, M)
    f = np.sqrt(np.maximum(lam, 0)) / (2 * np.pi)
    out = {"H": [], "V": []}
    hor = np.r_[np.arange(0, 4 * N, 4), np.arange(2, 4 * N, 4), [4 * N, 4 * N + 2]]
    for i in range(len(f)):
        eh = np.sum(V[hor, i] ** 2) / np.sum(V[:, i] ** 2)
        out["H" if eh > 0.5 else "V"].append(f[i])
    return {k: v[:n] for k, v in out.items()}


def criticals(R, gyro=True, n=2):
    """Synchronous critical speeds (rpm): det(K - W^2 (M - iG)) = 0."""
    K, M, G, z, node, N = assemble(R)
    B = M - 1j * G if gyro else M.astype(complex)
    mu = eigh(B, K.astype(complex), eigvals_only=True)
    mu = np.sort(mu[mu > 1e-12])[::-1]
    return [60 / (2 * np.pi) * np.sqrt(1 / m) for m in mu[:n]]


if __name__ == "__main__":
    R = dict(shaft=[(0.0, 0.25, 0.085), (0.25, 0.40, 0.110), (0.40, 1.60, 0.125), (1.60, 1.75, 0.110), (1.75, 2.05, 0.100)],
             disks=[(0.05, 25.0, 0.4, 0.7), (1.95, 420.0, 45.0, 85.0)], bearings=[0.32, 1.67],
             kb=8e8, mp=160.0, kpH=6e7, kpV=1.6e8)
    print("standstill", standstill(R))
    print("crit gyro", criticals(R), "no gyro", criticals(R, gyro=False))


def response(R, rpms, zeta_c=None, cH=None, cV=None, at=None):
    """Synchronous response amplitude (m) of the pedestal at bearing index `at` (default the fan end) in H and V
    to a unit unbalance (1 kg m) at the impeller, with viscous pedestal dampers cH, cV (N s/m)."""
    K, M, G, z, node, N = assemble(R)
    nd = K.shape[0]; C = np.zeros_like(K)
    j = len(R["bearings"]) - 1 if at is None else at
    for jj in range(len(R["bearings"])):
        p = 4 * N + 2 * jj
        C[p, p] += cH; C[p + 1, p + 1] += cV
    n = node(R["disks"][-1][0])
    out = []
    for rpm in rpms:
        W = rpm * 2 * np.pi / 60
        F = np.zeros(nd, complex); F[4 * n] = W ** 2; F[4 * n + 1] = -1j * W ** 2   # rotating force, u + i v
        A = K - W ** 2 * M + 1j * W * (C + W * G)
        q = np.linalg.solve(A, F)
        p = 4 * N + 2 * j
        out.append((abs(q[p]), abs(q[p + 1])))
    return np.array(out)
