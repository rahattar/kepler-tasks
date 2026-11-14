"""Moving finite line source (Molina-Giraldo et al. 2011) with the mirror source for the surface, averaged over the
receiving borehole's length: the borehole-to-borehole response of a field, and the field's mean wall temperature."""
import numpy as np
from scipy.special import erfc

GL_X, GL_W = np.polynomial.legendre.leggauss(20)


def pair_response(dx, dy, H, t, lam, alpha, U, ns=400):
    """Mean temperature rise over a receiving borehole (0..H) per unit heat rate per length (W/m) of a source
    borehole (0..H) at offset (dx, dy) [arrays], groundwater along +x with effective velocity U, at times t [array].
    The double integral over both lengths is reduced to one over the difference of depths (and one over their sum
    for the mirror source), with u = r sinh(s) taking out the 1/R peak."""
    dx = np.asarray(dx, float)[:, None, None]
    dy = np.asarray(dy, float)[:, None, None]
    t = np.asarray(t, float)[None, :, None]
    r = np.sqrt(dx ** 2 + dy ** 2)
    sq = 2 * np.sqrt(alpha * t)
    def f_times_R(R):
        if U == 0:
            return 2 * erfc(R / sq)
        return np.exp(-U * R / (2 * alpha)) * erfc((R - U * t) / sq) + np.exp(U * R / (2 * alpha)) * erfc((R + U * t) / sq)
    x, w = np.polynomial.legendre.leggauss(ns)
    def integral(L, weight):
        smax = np.arcsinh(L / r)
        sn = smax / 2 * (x[None, None, :] + 1)
        ws = w[None, None, :] * smax / 2
        u = r * np.sinh(sn)
        R = r * np.cosh(sn)
        return (weight(u) * f_times_R(R) * ws).sum(-1)
    direct = 2 * integral(H, lambda u: H - u)
    mirror = integral(2 * H, lambda v: H - np.abs(v - H))
    return np.exp(U * dx[:, :, 0] / (2 * alpha)) * (direct - mirror) / H / (8 * np.pi * lam)


def field_response(xy, H, t, lam, alpha, U, rb=0.075, ns=200):
    """Mean wall temperature rise of a field (uniform heat rate per length on every borehole), per W/m.
    Pairs are grouped by offset; the response is evaluated at up to 40 log-spaced times and interpolated."""
    n = len(xy)
    dx = np.round((xy[:, None, 0] - xy[None, :, 0]).ravel(), 6)      # receiver minus source
    dy = np.round(np.abs((xy[:, None, 1] - xy[None, :, 1]).ravel()), 6)
    off, cnt = np.unique(np.c_[dx, dy], axis=0, return_counts=True)
    dyy = np.where((off[:, 0] == 0) & (off[:, 1] == 0), rb, off[:, 1])
    t = np.asarray(t, float)
    tg = np.unique(np.r_[np.geomspace(t.min(), t.max(), 40), t.min(), t.max()]) if len(t) > 40 else t
    out = np.zeros(len(tg))
    for k in range(0, len(off), 64):
        g = pair_response(off[k:k + 64, 0], dyy[k:k + 64], H, tg, lam, alpha, U, ns=ns)
        out += (g * cnt[k:k + 64, None]).sum(0)
    out /= n
    return np.interp(np.log(t), np.log(tg), out) if len(t) > 40 else out


def grid(nx, ny, s):
    return np.array([(i * s, j * s) for i in range(nx) for j in range(ny)], float)
