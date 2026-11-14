"""Unoptimised second solution: the same method as the reference, but the wall stepped in time by Crank-Nicolson
in a plain loop, one banded solve a second, for every model run (the lag fit's runs included)."""
import json, os, sys
import numpy as np
from scipy.linalg import solve_banded
from scipy.signal import savgol_filter
from scipy.optimize import minimize_scalar
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))


class Wall:
    def __init__(self, ri, ro, a, n=60, dt=1.0):
        r = np.linspace(ri, ro, n + 1); h = r[1] - r[0]; rh = 0.5 * (r[1:] + r[:-1])
        V = np.empty(n + 1); V[0] = 0.5 * (rh[0] ** 2 - ri ** 2); V[1:n] = 0.5 * (rh[1:] ** 2 - rh[:-1] ** 2)
        V[n] = 0.5 * (ro ** 2 - rh[-1] ** 2)
        K = np.zeros((n, n)); b = np.zeros(n)
        for j in range(1, n + 1):
            i = j - 1; gi = a * rh[j - 1] / h; K[i, i] -= gi
            if j > 1: K[i, i - 1] += gi
            else: b[i] += gi
            if j < n:
                go = a * rh[j] / h; K[i, i] -= go; K[i, i + 1] += go
        M = V[1:]
        L = np.diag(M) - 0.5 * dt * K
        self.R = np.diag(M) + 0.5 * dt * K
        self.ab = np.zeros((3, n))
        self.ab[0, 1:] = np.diag(L, 1); self.ab[1] = np.diag(L); self.ab[2, :-1] = np.diag(L, -1)
        self.b, self.dt, self.V, self.n = b, dt, V, n

    def response(self, tf, outer_only=False):
        T = np.full(self.n, tf[0]); mean = np.empty(len(tf)); out = np.empty(len(tf))
        for k in range(len(tf)):
            if k:
                rhs = self.R @ T + 0.5 * self.dt * self.b * (tf[k - 1] + tf[k])
                T = solve_banded((1, 1), self.ab, rhs)
            out[k] = T[-1]
            mean[k] = (self.V[0] * tf[k] + self.V[1:] @ T) / self.V.sum()
        return mean - tf, out


spec = importlib.util.spec_from_file_location("ref", os.path.join(HERE, "ref_fatigue.py"))
ref = importlib.util.module_from_spec(spec); spec.loader.exec_module(ref)
ref.Wall = Wall

if __name__ == "__main__":
    sys.exit(ref.main(sys.argv))
