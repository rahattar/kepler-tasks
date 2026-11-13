"""pair.py: sealed definition of a pair of like lines between common manifolds, to TS-2.
Every steady division of the delivered flow between the two lines, and which divisions are stable. A division
is stable when moving a little flow from one line to the other raises the pressure drop of the line that gains
it above that of the line that loses it: with f(a) = dp(a) - dp(M - a), a the flow in the lesser line, a root
where f rises through zero. The even division a = M/2 is always a root; it is stable when f < 0 just below it."""
import numpy as np
from line import march

KEYS = ("D", "L", "Uo", "Tin", "Ta", "rho", "cp", "k", "A", "B")
FR = np.concatenate([np.geomspace(2e-4, 0.30, 72), np.linspace(0.31, 0.497, 24)])

def take(par, idx):
    return {k: par[k][idx] for k in KEYS}

def single(m, par, n):
    return march(m, *[par[k] for k in KEYS], n=n)

def splits(M, par, n=240, fr=FR, iters=44):
    """for each case: the even division (dp, Tout, stable) and the uneven ones as arrays
    (case, a, dp, Tout, stable)."""
    R, J = len(M), len(fr)
    a = fr[None, :] * M[:, None]
    big = {k: np.repeat(par[k], J) for k in KEYS}
    dpa, _ = single(a.ravel(), big, n); dpb, _ = single((M[:, None] - a).ravel(), big, n)
    f = (dpa - dpb).reshape(R, J)
    dps, Ts = single(M / 2, par, n)
    sym_stable = f[:, -1] < 0
    r, j = np.nonzero(f[:, :-1] * f[:, 1:] < 0)
    if len(r) == 0:
        z = np.zeros(0)
        return (dps, Ts, sym_stable), (r, z, z, z, z.astype(bool))
    lo = a[r, j].copy(); hi = a[r, j + 1].copy(); flo = f[r, j].copy()
    pr = take(par, r); Mr = M[r]
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fm = single(mid, pr, n)[0] - single(Mr - mid, pr, n)[0]
        left = fm * flo > 0
        lo = np.where(left, mid, lo); hi = np.where(left, hi, mid)
    root = 0.5 * (lo + hi)
    d1, T1 = single(root, pr, n); d2, T2 = single(Mr - root, pr, n)
    return (dps, Ts, sym_stable), (r, root, 0.5 * (d1 + d2), (root * T1 + (Mr - root) * T2) / Mr, flo < 0)

def follow(order, sym, asym):
    """the state of each case, the cases taken in the given order as consecutive records of one pair: the
    pair keeps the kind of division it has (even or uneven) for as long as that division is steady and stable,
    and otherwise takes the one that is. Returns kind (0 even, 1 uneven), dp, Tout, and flags."""
    dps, Ts, ss = sym
    r, root, dpa, Ta_, st = asym
    stable_asym = {}
    for i in np.nonzero(st)[0]:
        stable_asym.setdefault(int(r[i]), []).append(i)
    kind = np.zeros(len(dps), int); dp = np.zeros(len(dps)); T = np.zeros(len(dps)); a = np.zeros(len(dps))
    flags = []
    prev = None
    for c in order:
        ua = stable_asym.get(int(c), [])
        if len(ua) > 1: flags.append((int(c), "two uneven"))
        have_sym = bool(ss[c]); have_asym = len(ua) > 0
        if not have_sym and not have_asym: flags.append((int(c), "none")); have_sym = True
        if prev is None:
            if have_sym and have_asym: flags.append((int(c), "first record has two"))
            k = 0 if have_sym else 1
        elif prev == 0:
            k = 0 if have_sym else 1
        else:
            k = 1 if have_asym else 0
        kind[c] = k
        if k == 0: dp[c], T[c], a[c] = dps[c], Ts[c], 0.5
        else:
            i = ua[0]; dp[c], T[c], a[c] = dpa[i], Ta_[i], root[i]
        prev = k
    return kind, dp, T, a, flags
