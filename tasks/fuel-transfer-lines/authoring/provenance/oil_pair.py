"""oil_pair.py: the sealed definition of a pair of pipes between common manifolds, to TS-2 section 4, the two pipes
each with their own bore and covering.

a is the flow in pipe A, M the delivered flow, f(a) = dp_A(a) - dp_B(M - a). A steady division is a root of f.
Flow moves from the pipe with the higher pressure drop to the other, so a division is stable where f rises
through zero, and a pair that is not at a root goes down in a where f > 0 and up where f < 0 until it meets
one. Followed through gradual changes, a pair therefore stays on the root it has for as long as that root
exists and, when it ceases, goes to the next root on the side f sends it. f < 0 at a = 0 and f > 0 at a = M,
so the signs of f between successive roots alternate from negative."""
import numpy as np
from oil_line import march

KP = ("L", "Tin", "Ta", "rho", "cp", "k", "A", "B")           # shared by the two pipes
_t = np.geomspace(2e-4, 0.30, 44)
FR = np.concatenate([_t, np.linspace(0.31, 0.69, 39), (1 - _t)[::-1]])
_c = np.geomspace(2e-4, 0.30, 26)
FR_CHECK = np.concatenate([_c, np.linspace(0.32, 0.68, 19), (1 - _c)[::-1]])

def pipe(m, par, which, n):
    return march(m, par["D" + which], par["L"], par["U" + which], par["Tin"], par["Ta"], par["rho"], par["cp"], par["k"], par["A"], par["B"], n=n)

def rep(par, J):
    return {k: np.repeat(v, J) for k, v in par.items()}

def take(par, idx):
    return {k: v[idx] for k, v in par.items()}

def roots(M, par, n=240, fr=FR, iters=40):
    """every steady division of every case: arrays (case, share of A, dp, mixed outlet temperature, stable),
    sorted by case and share."""
    R, J = len(M), len(fr)
    a = fr[None, :] * M[:, None]
    big = rep(par, J)
    f = (pipe(a.ravel(), big, "a", n)[0] - pipe((M[:, None] - a).ravel(), big, "b", n)[0]).reshape(R, J)
    sg = np.where(f >= 0, 1.0, -1.0)                      # an exact zero on the grid counts as positive
    r, j = np.nonzero(sg[:, :-1] * sg[:, 1:] < 0)
    lo = a[r, j].copy(); hi = a[r, j + 1].copy(); flo = sg[r, j].copy()
    pr = take(par, r); Mr = M[r]
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fm = pipe(mid, pr, "a", n)[0] - pipe(Mr - mid, pr, "b", n)[0]
        left = np.where(fm >= 0, 1.0, -1.0) * flo > 0
        lo = np.where(left, mid, lo); hi = np.where(left, hi, mid)
    x = 0.5 * (lo + hi)
    d1, T1 = pipe(x, pr, "a", n); d2, T2 = pipe(Mr - x, pr, "b", n)
    return r, x / Mr, 0.5 * (d1 + d2), (x * T1 + (Mr - x) * T2) / Mr, flo < 0, T1, T2

def follow(order, sol, start=None):
    """the cases in the given order as consecutive states of one pair. Returns the index into sol of the root
    each case sits on, and flags."""
    r, share, dp, T, stable = sol[:5]
    by = {}
    for i in range(len(r)): by.setdefault(int(r[i]), []).append(i)
    pick = {}; flags = []; prev = start
    for c in order:
        idx = by.get(int(c), [])
        if not idx: flags.append((int(c), "no root")); continue
        sh = share[idx]
        if prev is None:
            st = [i for i in idx if stable[i]]
            if len(st) != 1: flags.append((int(c), "first state not unique"))
            i = st[0] if st else idx[0]
        else:
            below = int(np.sum(sh < prev))                 # f > 0 at prev when an odd number of roots lie below
            if below % 2 == 1: i = idx[below - 1]          # down to the next root
            else:
                if below >= len(idx): flags.append((int(c), "no root above")); i = idx[-1]
                else: i = idx[below]                       # up to the next root
            if not stable[i]: flags.append((int(c), "landed on an unstable root"))
        pick[int(c)] = i; prev = share[i]
    return pick, flags
