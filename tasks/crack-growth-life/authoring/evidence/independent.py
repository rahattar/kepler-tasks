"""An independent second solution, written apart from solution/solve.py: its own campaign, its own fit and its own
integration, run on the shipped scenario through the emulated laboratory.

Campaign: five Paris tests and no threshold test: heat H1 at R 0.10, 0.25 and 0.90, heat H2 at R 0.50 (so that the
second S355J2 heat is measured rather than read from its example), and S460NL heat H4 at R 0.90. The R 0.90 tests, held
to dK 2-7.5 by the laboratory's Kmax limit, give the near-threshold shape. Fit (scipy least squares, all reports together): a closure model da/dN = C (U dK)^m (1 - dKth/(U dK))^p
with U(R) = min(1, U0 + (1 - U0) R / Rc), U0 and Rc free, one closure-free threshold, so that the threshold rises at low
R with the same closure as the Paris regime (a different threshold model from the reference's), and a rate factor
for each tested heat (H3 takes H4's, the same grade). Crack model: BS 7910 2D Mk (own implementation), residual stress per BS 7910 with the log's
site welds, loading per the log; integration in log-spaced crack depth steps; interval 0.45 x life.

    python3 authoring/evidence/independent.py > authoring/evidence/independent.txt
"""
import numpy as np
from scipy.optimize import least_squares
import common as C

CAMPAIGN = [("paris", 0.10, "H1"), ("paris", 0.25, "H1"), ("paris", 0.90, "H1"), ("paris", 0.50, "H2"),
            ("paris", 0.90, "H4")]


def fit_closure(data):
    R = np.concatenate([np.full(len(d), r) for _, r, d, _, _ in data])
    dK = np.concatenate([d for _, _, d, _, _ in data])
    v = np.concatenate([x for _, _, _, x, _ in data])
    hs = sorted({h for _, _, _, _, h in data} - {"H1"})
    masks = [np.concatenate([np.full(len(d), h == k, float) for _, _, d, _, h in data]) for k in hs]

    def U(Rv, u0, rc):
        return np.minimum(1.0, u0 + (1 - u0) * np.asarray(Rv, float) / rc)

    def model(q, Rv, dKv):
        lc, m, p, th, u0, rc = q[:6]
        de = U(Rv, u0, rc) * dKv
        return lc + sum(q[6 + i] * masks[i] for i in range(len(hs))) + m * np.log(de) + p * np.log(
            np.clip(1 - th / de, 1e-6, None))

    q = least_squares(lambda q: model(q, R, dK) - np.log(v), [-25.0, 3.0, 0.5, 2.0, 0.6, 0.6] + [0.0] * len(hs),
                      bounds=([-60, 1.5, 0.05, 0.5, 0.2, 0.2] + [-2.0] * len(hs),
                              [10, 6, 3, 2.9, 1.0, 1.0] + [2.0] * len(hs))).x

    def law(dKx, Rx):
        dKx = np.asarray(dKx, float)
        de = U(Rx, q[4], q[5]) * dKx
        out = np.exp(q[0]) * de ** q[1] * np.clip(1 - q[3] / np.maximum(de, 1e-9), 0, None) ** q[2]
        return np.where(de > q[3], out, 0.0)
    law.q = q
    hf = {"H1": 1.0}
    hf.update({h: float(np.exp(q[6 + i])) for i, h in enumerate(hs)})
    for h in C.GRADE:                   # an untested heat: a tested heat of its grade, else H1
        hf.setdefault(h, next((hf[k] for k in hs if C.GRADE[k] == C.GRADE[h]), 1.0))
    law.hf = hf
    return law


def mk2d(aT, LT):
    LT = min(LT, 2.0)
    knee = 0.05 * LT ** 0.55
    out = np.where(aT <= knee, 0.51 * LT ** 0.27 * aT ** -0.31, 0.83 * aT ** (-0.15 * LT ** 0.46))
    return np.maximum(out, 1.0)


def life(law, cid):
    c = C.crack(cid)
    T, L = c["T"], c["tatt"] + 2 * c["leg"]
    g = lambda a: mk2d(a / T, L / T) * C.Y(a / T) * np.sqrt(np.pi * a)  # noqa: E731
    pwht = c["fab"].startswith("pwht") and c["where"] not in C.SITE_WELDED
    sres = 0.2 * c["sy"] if pwht else c["sy"]
    unit = c["member"].rsplit(" ", 1)[0]
    ds = c["ds"] * C.GRAB.get(unit, 1.0)
    R = np.minimum((c["smin"] + sres) / (c["smin"] + sres + ds), 0.95)
    a_end = 0.5 * T
    for a in np.linspace(c["a0"], 0.5 * T, 4000):
        if (c["smin"] + ds.max()) * g(a) >= c["kmat"]:
            a_end = a
            break
    a = np.geomspace(c["a0"], a_end, 2500)
    rate = law.hf[c["heat"]] * (law(ds[None, :] * g(a)[:, None], R[None, :]) * (c["n"] / c["n"].sum())[None, :]).sum(1)
    N = float(np.sum(np.diff(a) * 0.5 * (1 / rate[1:] + 1 / rate[:-1])))
    days = C.SURVEY_DAYS - C.DOWN.get(unit, 0)
    per_month = C.GRAB_CYCLES.get(unit, 1.0) * c["n"].sum() / days * 25.0
    return N / per_month


if __name__ == "__main__":
    law = fit_closure(C.lab(CAMPAIGN))
    print("Independent solution: campaign %s" % ", ".join("%s %.2f %s" % k for k in CAMPAIGN))
    print("fit: C %.3e, m %.3f, p %.3f, threshold %.2f, U0 %.3f, closure-free from R %.3f; heat factors %s\n" % (
        np.exp(law.q[0]), law.q[1], law.q[2], law.q[3], law.q[4], law.q[5],
        ", ".join("%s %.3f" % kv for kv in sorted(law.hf.items()))))
    iv = {c: 0.45 * life(law, c) for c in C.IDS}
    n, ok, r = C.grade(iv)
    for c in C.IDS:
        print("%s  interval %7.3f  true life %6.2f  interval/life %.3f %s" % (c, iv[c], C.TRUTH[c], r[c], "ok" if c in ok else "BAD"))
    print("\n%d of 16 right; interval/life %.3f to %.3f against the window 0.40-0.50." % (n, min(r.values()), max(r.values())))
