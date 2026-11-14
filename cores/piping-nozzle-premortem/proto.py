"""Prototype 3D pipe line for the pre-mortem: beams with bend flexibility, weight, thermal growth, imposed
anchor movements, variable spring hangers, rod hangers (tension only), guides with gaps (one-sided contacts)."""
import numpy as np

NU = 0.3
PEN = 1e13


def E_of(T):   # P91-like, Pa
    return np.interp(T, [20, 200, 400, 500, 550, 600], [213e9, 203e9, 188e9, 178e9, 170e9, 162e9])


def alpha_of(T):   # mean from 20 C, 1/K
    return np.interp(T, [20, 200, 400, 500, 550, 600], [10.9e-6, 11.6e-6, 12.4e-6, 12.8e-6, 13.0e-6, 13.2e-6])


def route(points, R, seg=2.0, nbend=4):
    """Nodes along a polyline with arcs of radius R at the corners. Returns xyz, elements (i, j, is_bend)."""
    P = [np.array(p, float) for p in points]
    xyz = [P[0]]
    elems = []
    cur = P[0]
    for k in range(1, len(P)):
        a = P[k] - P[k - 1]
        la = np.linalg.norm(a)
        ea = a / la
        if k < len(P) - 1:
            b = P[k + 1] - P[k]
            eb = b / np.linalg.norm(b)
            theta = np.arccos(np.clip(ea @ eb, -1, 1))
            t = R * np.tan(theta / 2)
            end = P[k] - ea * t
        else:
            end = P[k]
        # straight part from cur to end
        L = np.linalg.norm(end - cur)
        n = max(1, int(np.ceil(L / seg)))
        for s in range(1, n + 1):
            xyz.append(cur + (end - cur) * s / n)
            elems.append((len(xyz) - 2, len(xyz) - 1, False))
        if k < len(P) - 1:
            # arc from end to P[k] + eb t, centre on the bisector
            nrm = eb - ea
            nrm /= np.linalg.norm(nrm)
            C = end + nrm * R
            u0 = end - C
            for s in range(1, nbend + 1):
                phi = theta * s / nbend
                # rotate u0 towards eb within the plane
                v = np.cos(phi) * u0 + np.sin(phi) * R * ea
                xyz.append(C + v)
                elems.append((len(xyz) - 2, len(xyz) - 1, True))
            cur = xyz[-1]
    return np.array(xyz), elems


class Line:
    def __init__(self, xyz, elems, OD, wall, w_per_m, R, supports, T_cold=20.0):
        self.xyz, self.elems, self.n = xyz, elems, len(xyz)
        ro, ri = OD / 2, OD / 2 - wall
        self.A = np.pi * (ro ** 2 - ri ** 2)
        self.I = np.pi / 4 * (ro ** 4 - ri ** 4)
        rm = (ro + ri) / 2
        h = wall * R / rm ** 2
        self.kflex = max(1.0, 1.65 / h)
        self.w = w_per_m
        self.sup = supports
        self.Tc = T_cold

    def element_K(self, i, j, E, bend):
        d = self.xyz[j] - self.xyz[i]
        L = np.linalg.norm(d)
        ex = d / L
        ref = np.array([0, 0, 1.0]) if abs(ex[2]) < 0.9 else np.array([1.0, 0, 0])
        ey = np.cross(ref, ex); ey /= np.linalg.norm(ey)
        ez = np.cross(ex, ey)
        Rm = np.array([ex, ey, ez])
        I = self.I / (self.kflex if bend else 1.0)
        G = E / (2 * (1 + NU))
        J = 2 * self.I
        A = self.A
        k = np.zeros((12, 12))
        k[0, 0] = k[6, 6] = E * A / L; k[0, 6] = k[6, 0] = -E * A / L
        k[3, 3] = k[9, 9] = G * J / L; k[3, 9] = k[9, 3] = -G * J / L
        for (v, th, s) in ((1, 5, 1), (2, 4, -1)):
            a = 12 * E * I / L ** 3; b = 6 * E * I / L ** 2; c = 4 * E * I / L; e2 = 2 * E * I / L
            vi, ti, vj, tj = v, th, v + 6, th + 6
            k[vi, vi] = k[vj, vj] = a; k[vi, vj] = k[vj, vi] = -a
            k[vi, ti] = k[ti, vi] = s * b; k[vi, tj] = k[tj, vi] = s * b
            k[vj, ti] = k[ti, vj] = -s * b; k[vj, tj] = k[tj, vj] = -s * b
            k[ti, ti] = k[tj, tj] = c; k[ti, tj] = k[tj, ti] = e2
        T = np.zeros((12, 12))
        for q in range(4):
            T[3 * q:3 * q + 3, 3 * q:3 * q + 3] = Rm
        return T.T @ k @ T, ex, L

    def solve(self, T, dA, dB, cold=None, state=None, override=None):
        """One state. T: line temperature; dA, dB: imposed displacements of the anchors (3,), m.
        cold: the cold solution (needed for springs in hot states); override: dict of condition changes."""
        ov = override or {}
        N = 6 * self.n
        K = np.zeros((N, N))
        f = np.zeros(N)
        E = E_of(T)
        eps = alpha_of(T) * (T - self.Tc)
        for (i, j, bend) in self.elems:
            ke, ex, L = self.element_K(i, j, E, bend)
            idx = np.r_[6 * i:6 * i + 6, 6 * j:6 * j + 6]
            K[np.ix_(idx, idx)] += ke
            P = E * self.A * eps
            f[6 * i:6 * i + 3] -= P * ex
            f[6 * j:6 * j + 3] += P * ex
            q = np.array([0, 0, -self.w])
            f[6 * i:6 * i + 3] += q * L / 2
            f[6 * j:6 * j + 3] += q * L / 2
            m = L ** 2 / 12 * np.cross(ex, q)
            f[6 * i + 3:6 * i + 6] += m
            f[6 * j + 3:6 * j + 6] -= m
        fixed = {}
        for a in range(6):
            fixed[6 * 0 + a] = dA[a] if a < 3 else 0.0
            fixed[6 * (self.n - 1) + a] = dB[a] if a < 3 else 0.0
        springs, unis = [], []
        for s in self.sup:
            kind = ov.get(s["name"], {}).get("kind", s["kind"])
            nd = s["node"]
            if kind == "spring":
                # a variable spring set at its cold load at the installed (design) elevation: F = Fc - k u_z
                kk = ov.get(s["name"], {}).get("rate", s["rate"])
                Fc = s["cold_load"] + ov.get(s["name"], {}).get("dload", 0.0)
                K[6 * nd + 2, 6 * nd + 2] += kk
                f[6 * nd + 2] += Fc
                springs.append(s["name"])
            elif kind == "locked":
                # travel stop left in: rigid at the position it was set to, the design elevation
                fixed[6 * nd + 2] = ov.get(s["name"], {}).get("set", 0.0)
            elif kind == "rod":
                unis.append((s["name"], 6 * nd + 2, +1, ov.get(s["name"], {}).get("set", 0.0)))   # u_z >= set
            elif kind == "rigid":
                fixed[6 * nd + 2] = ov.get(s["name"], {}).get("set", 0.0)
            elif kind == "guide":
                ax = {"x": 0, "y": 1}[s["dir"]]
                g1 = ov.get(s["name"], {}).get("gap_minus", s["gap"])
                g2 = ov.get(s["name"], {}).get("gap_plus", s["gap"])
                unis.append((s["name"] + "-", 6 * nd + ax, +1, -g1))   # u >= -g1
                unis.append((s["name"] + "+", 6 * nd + ax, -1, -g2))   # -u >= -g2
        active = set(state or [])
        for it in range(40):
            Kc, fc = K.copy(), f.copy()
            for (nm, dof, sgn, lim) in unis:
                if nm in active:
                    Kc[dof, dof] += PEN
                    fc[dof] += PEN * sgn * lim
            free = np.ones(N, bool)
            u = np.zeros(N)
            for dof, val in fixed.items():
                free[dof] = False
                u[dof] = val
            fr = np.nonzero(free)[0]
            u[fr] = np.linalg.solve(Kc[np.ix_(fr, fr)], fc[fr] - Kc[np.ix_(fr, ~free)] @ u[~free])
            new = set()
            for (nm, dof, sgn, lim) in unis:
                if nm in active:
                    if lim - sgn * u[dof] > 0:      # still pressed into the stop: the stop pushes, keep it
                        new.add(nm)
                else:
                    if sgn * u[dof] < lim - 1e-9:
                        new.add(nm)
            if new == active:
                break
            active = new
        else:
            raise RuntimeError("contact set did not settle")
        R = K @ u - f     # reactions at fixed dofs (support on pipe) incl. penalties not counted
        nb = 6 * (self.n - 1)
        reaction_B = R[nb:nb + 6]
        # take moments of the reaction at node B itself
        return u, -reaction_B, active
