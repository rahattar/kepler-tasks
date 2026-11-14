#!/usr/bin/env python3
"""Quench calculation to HT-5 for one site package.

usage: python3 quench.py PACKAGE_DIR OUT_CSV
"""
import json, os, subprocess, sys
from datetime import date
import numpy as np
import pandas as pd

KPROBE = 14200.0
RHO = 7800.0
STEELS = {
    "C45": ([20, 300, 600, 800, 900], [50, 44, 34, 26, 26],
            [20, 300, 600, 720, 800, 900], [470, 560, 750, 900, 650, 650]),
    "42CrMo4": ([20, 300, 600, 800, 900], [43, 40, 33, 27, 27],
                [20, 300, 600, 720, 800, 900], [460, 550, 720, 850, 640, 640]),
}
FIG = ["cr_max_K_s", "t_crmax_C", "cr_300_K_s"]


def dnum(s):
    return date.fromisoformat(str(s).strip()).toordinal()


# ---------------------------------------------------------------- oil -----
def same_oil(a, b):
    """a, b: arrays of figures. Same charge if within lab repeatability."""
    return (abs(a[0] - b[0]) <= 0.008 * max(a[0], b[0]) and
            abs(a[2] - b[2]) <= 0.008 * max(a[2], b[2]) + 0.011 and
            abs(a[1] - b[1]) <= 1.5)


def tank_similar(sa, sb):
    """sa, sb: dict date -> figures. Compare on common dates, else nearest."""
    common = set(sa) & set(sb)
    if common:
        return all(same_oil(sa[d], sb[d]) for d in common)
    best = None
    for d1 in sa:
        for d2 in sb:
            g = abs(d1 - d2)
            if best is None or g < best[0]:
                best = (g, d1, d2)
    if best[0] > 200:
        return False
    return same_oil(sa[best[1]], sb[best[2]])


class Charge:
    def __init__(self, start, end):
        self.start, self.end = start, end   # end None => current charge
        self.an = {}                        # date -> list of figure arrays

    def points(self):
        ds = sorted(self.an)
        return ds, np.array([np.mean(self.an[d], axis=0) for d in ds])


def charge_figs(ch, d, lab=None):
    """figures of the charge at date d. lab: (date, figs) analysis at the lab date."""
    ds, vs = ch.points()
    if lab is not None:
        ds = ds + [lab[0]]
        vs = np.vstack([vs, lab[1]]) if len(vs) else np.array([lab[1]])
    if not ds:
        return None
    if d <= ds[0]:
        return vs[0]
    if d >= ds[-1]:
        if ch.end is None and lab is None and len(ds) >= 2:
            # extrapolate the aging trend of the charge (least squares)
            x = np.array(ds, float)
            A = np.vstack([x - x[-1], np.ones_like(x)]).T
            coef, *_ = np.linalg.lstsq(A, vs, rcond=None)
            return coef[1] + coef[0] * (d - x[-1])
        return vs[-1]
    out = np.empty(3)
    for j in range(3):
        out[j] = np.interp(d, ds, vs[:, j])
    return out


def settle_oil(pkg, loads):
    site = json.load(open(os.path.join(pkg, "site.json")))
    nlab = int(site.get("lab_samples", 0))
    dlab = dnum(site["samples_drawn"])
    tanks = pd.read_csv(os.path.join(pkg, "tanks.csv"), dtype=str)
    systems = pd.read_csv(os.path.join(pkg, "oil_systems.csv"), dtype=str)
    try:
        log = pd.read_csv(os.path.join(pkg, "oil_log.csv"), dtype=str)
    except Exception:
        log = pd.DataFrame(columns=["date", "oil_system", "work", "remarks"])
    try:
        samp = pd.read_csv(os.path.join(pkg, "oil_samples.csv"))
    except Exception:
        samp = pd.DataFrame(columns=["date", "sampled_at"] + FIG)
    tanks["tank"] = tanks["tank"].str.strip()
    tanks["oil_system"] = tanks["oil_system"].str.strip()
    reg = dict(zip(tanks.tank, tanks.oil_system))
    for t in loads.tank.unique():
        reg.setdefault(t, "UNREG-" + t)
    kinds = dict(zip(systems.oil_system.str.strip(), systems.kind.str.strip()))
    otype = dict(zip(systems.oil_system.str.strip(), systems.oil_type.str.strip()))
    renew = {}
    for _, r in log.iterrows():
        if str(r["work"]).strip().upper() == "CHARGE_RENEWED":
            renew.setdefault(str(r["oil_system"]).strip(), []).append(dnum(r["date"]))
    for k in renew:
        renew[k] = sorted(set(renew[k]))

    # samples per tank
    ts = {}
    for _, r in samp.iterrows():
        t = str(r["sampled_at"]).strip()
        ts.setdefault(t, {}).setdefault(dnum(r["date"]), []).append(
            np.array([float(r[f]) for f in FIG]))
    # compare only samples within the same charge period of the register system
    def period_key(t, d):
        rs = renew.get(reg.get(t), [])
        return sum(1 for x in rs if x <= d)
    tsm = {t: {d: np.mean(v, axis=0) for d, v in dd.items()} for t, dd in ts.items()}

    # cluster tanks into oils, within each register system (single systems: one tank)
    sys_tanks = {}
    for t, s in reg.items():
        sys_tanks.setdefault(s, []).append(t)
    groups = []   # dict(system, tanks, main)
    for s, tl in sys_tanks.items():
        withs = [t for t in tl if t in tsm]
        without = [t for t in tl if t not in tsm]
        parent = {t: t for t in withs}

        def find(x):
            while parent[x] != x:
                x = parent[x]
            return x
        for i in range(len(withs)):
            for j in range(i + 1, len(withs)):
                a, b = withs[i], withs[j]
                # use only the latest charge period's samples (and older if none)
                if tank_similar(tsm[a], tsm[b]):
                    parent[find(a)] = find(b)
        cl = {}
        for t in withs:
            cl.setdefault(find(t), []).append(t)
        cls = sorted(cl.values(), key=lambda c: -len(c))
        if not cls:
            groups.append(dict(system=s, tanks=list(without), main=True))
            continue
        # main cluster: largest; on ties prefer the one whose samples agree in more dates
        groups.append(dict(system=s, tanks=cls[0] + without, main=True))
        for c in cls[1:]:
            if len(c) == len(cls[0]):
                groups.append(dict(system=s, tanks=c, main=None))   # undecided
            else:
                groups.append(dict(system=s, tanks=c, main=False))
        if len(cls) > 1 and len(cls[1]) == len(cls[0]):
            groups[-len(cls) ]["main"] = None

    lastload = loads.groupby("tank").dn.max().to_dict()

    def build(g, renewed_dates):
        bounds = [-10 ** 9] + list(renewed_dates)
        chs = [Charge(bounds[i], bounds[i + 1] if i + 1 < len(bounds) else None)
               for i in range(len(bounds))]
        for t in g["tanks"]:
            for d, lst in ts.get(t, {}).items():
                k = sum(1 for x in renewed_dates if x <= d)
                chs[k].an.setdefault(d, []).extend(lst)
        return chs

    # needs for the lab
    cand = []
    for gi, g in enumerate(groups):
        lt = [t for t in g["tanks"] if t in lastload]
        if not lt:
            continue
        lmax = max(lastload[t] for t in lt)
        rd = renew.get(g["system"], [])
        chs = build(g, rd)
        cur = chs[-1]
        prio = None
        if g["main"] is not True and rd and lmax >= rd[-1]:
            prio = 1   # unknown whether the renewal reached it
        elif not cur.an and lmax >= cur.start:
            prio = 0   # renewed charge with no analysis on file
        else:
            ds, vs = cur.points()
            if ds and lmax > ds[-1]:
                prio = 3
                if len(ds) >= 2:
                    rate = np.max(np.abs(np.diff(vs[:, [0, 2]], axis=0)) /
                                  vs[:-1, [0, 2]] / (np.diff(ds)[:, None] / 182.0))
                    if rate > 0.006:
                        prio = 2
                else:
                    prio = 2
                if not ds:
                    prio = 0
        if prio is None:
            continue
        nl = int((loads.tank.isin(g["tanks"])).sum())
        # prefer a tank with loads, and among them the one with most loads
        cnt = loads[loads.tank.isin(lt)].tank.value_counts()
        tk = cnt.index[0]
        cand.append((prio, -nl, gi, tk))
    cand.sort()
    order = cand[:max(nlab, 0)]
    labres = {}
    if order:
        try:
            out = subprocess.run(["labsample", pkg] + [c[3] for c in order],
                                 capture_output=True, text=True, timeout=30).stdout
            for line in out.splitlines():
                p = line.strip().split(",")
                if len(p) == 4 and p[0] != "sampled_at":
                    try:
                        labres.setdefault(p[0], []).append([float(x) for x in p[1:]])
                    except ValueError:
                        pass
        except Exception as e:
            sys.stderr.write("labsample failed: %s\n" % e)

    # figures function per group
    tank_group = {}
    gfun = []
    for gi, g in enumerate(groups):
        for t in g["tanks"]:
            tank_group[t] = gi
        rd = renew.get(g["system"], [])
        lab = None
        labt = [t for t in g["tanks"] if t in labres]
        if labt:
            lab = (dlab, np.mean([v for t in labt for v in labres[t]], axis=0))
        if g["main"] is not True and rd:
            # decide whether the renewal reached this oil
            old = build(g, [])[0]
            reached = False
            if lab is not None:
                pred = charge_figs(old, dlab)
                if pred is None or not same_oil_loose(pred, lab[1]):
                    reached = True
            elif g["main"] is None:
                reached = True
            if not reached:
                rd = []
        chs = build(g, rd)
        gfun.append((chs, lab))

    # fallback by oil type
    def type_mean(s):
        ty = otype.get(s)
        vals = []
        for t, dd in ts.items():
            if otype.get(reg.get(t)) == ty:
                for lst in dd.values():
                    vals.extend(lst)
        if not vals:
            vals = [v for dd in ts.values() for lst in dd.values() for v in lst]
        return np.mean(vals, axis=0)

    res = np.zeros((len(loads), 3))
    for i, (t, dn) in enumerate(zip(loads.tank, loads.dn)):
        gi = tank_group[t]
        chs, lab = gfun[gi]
        k = 0
        for j, ch in enumerate(chs):
            if dn >= ch.start:
                k = j
        ch = chs[k]
        f = charge_figs(ch, dn, lab if ch.end is None else None)
        if f is None:
            # no analysis of this charge: nearest previous charge, else type
            f = None
            for j in range(k - 1, -1, -1):
                f = charge_figs(chs[j], dn)
                if f is not None:
                    break
            if f is None:
                f = type_mean(groups[gi]["system"])
        res[i] = f
    info = dict(order=[c[3] for c in order], groups=groups)
    return res, info


def same_oil_loose(a, b):
    return (abs(a[0] - b[0]) <= 0.015 * max(a[0], b[0]) and
            abs(a[2] - b[2]) <= 0.015 * max(a[2], b[2]) + 0.011 and
            abs(a[1] - b[1]) <= 3)


# -------------------------------------------------------------- solver ----
def solve(steel_k, steel_c, R, Tf, Tb, figs, N=24, DTF=2.0):
    """Vectorised Crank-Nicolson finite volume solution for many loads."""
    M = len(R)
    cr, tc, c3 = figs[:, 0], figs[:, 1], figs[:, 2]
    hp = KPROBE * cr / (tc - 40.0)
    h3 = KPROBE * c3 / 260.0
    x0, x1, x2, x3 = np.full(M, 100.0), np.full(M, 300.0), tc, tc + 120.0
    y0, y1, y2, y3 = 0.6 * h3, h3, hp, 0.15 * hp

    def hv(Ts):
        return np.where(Ts <= x0, y0,
               np.where(Ts <= x1, y0 + (y1 - y0) * (Ts - x0) / (x1 - x0),
               np.where(Ts <= x2, y1 + (y2 - y1) * (Ts - x1) / (x2 - x1),
               np.where(Ts <= x3, y2 + (y3 - y2) * (Ts - x2) / (x3 - x2), y3))))

    kx, ky = steel_k
    cx, cy = steel_c
    kt, ct = 0, 1

    def lut(tab, X):
        if tab == 0:
            return np.interp(X, kx, ky)
        return np.interp(X, cx, cy)

    dr = R / N
    rf = np.arange(N + 1)[None, :] * dr[:, None]
    vol = 0.5 * (rf[:, 1:] ** 2 - rf[:, :-1] ** 2)
    area = rf[:, 1:-1]
    Tbc = Tb

    def surf(Tl, kl):
        g = kl / (0.5 * dr)
        Ts = Tl.copy()
        for _ in range(4):
            h = hv(Ts)
            Ts = (g * Tl + h * Tbc) / (g + h)
        return Ts, h

    def coeffs(Tm):
        k = lut(kt, Tm)
        c = lut(ct, Tm)
        kf = 2 * k[:, 1:] * k[:, :-1] / (k[:, 1:] + k[:, :-1])
        G = kf * area / dr[:, None]
        Ts, h = surf(Tm[:, -1], k[:, -1])
        U = R / (1.0 / h + 0.5 * dr / k[:, -1])
        return RHO * c * vol, G, U

    def Lop(T, G, U):
        q = G * (T[:, 1:] - T[:, :-1])
        L = np.zeros_like(T)
        L[:, :-1] += q
        L[:, 1:] -= q
        L[:, -1] -= U * (T[:, -1] - Tbc)
        return L

    def cn_step(T, dt, C, G, U):
        # (C/dt) dT = 0.5 L(T+dT) + 0.5 L(T) = L(T) + 0.5 L_lin(dT)
        rhs = Lop(T, G, U)
        a = np.zeros_like(T); b = C / dt[:, None]; cc = np.zeros_like(T)
        b = b.copy()
        b[:, :-1] += 0.5 * G; b[:, 1:] += 0.5 * G
        b[:, -1] += 0.5 * U
        a[:, 1:] = -0.5 * G
        cc[:, :-1] = -0.5 * G
        # Thomas
        n = T.shape[1]
        cp = np.empty_like(T); dp = np.empty_like(T)
        cp[:, 0] = cc[:, 0] / b[:, 0]; dp[:, 0] = rhs[:, 0] / b[:, 0]
        for i in range(1, n):
            m = b[:, i] - a[:, i] * cp[:, i - 1]
            cp[:, i] = cc[:, i] / m
            dp[:, i] = (rhs[:, i] - a[:, i] * dp[:, i - 1]) / m
        x = np.empty_like(T)
        x[:, -1] = dp[:, -1]
        for i in range(n - 2, -1, -1):
            x[:, i] = dp[:, i] - cp[:, i] * x[:, i + 1]
        return T + x

    T = np.repeat(Tf[:, None], N, 1).astype(float)
    t = np.zeros(M)
    dt0 = DTF * R
    targets = [800.0, 725.0, 675.0, 500.0, 150.0]
    tt = np.full((M, 5), np.nan)
    ts500 = np.full(M, np.nan)
    dTmax = np.zeros(M)
    Tc_prev = (9 * T[:, 0] - T[:, 1]) / 8.0
    Ts_prev = surf(T[:, -1], lut(kt, T[:, -1]))[0]
    full = dict(dr=dr, vol=vol, area=area, R=R, Tb=Tb, x0=x0, x1=x1, x2=x2, x3=x3,
                y0=y0, y1=y1, y2=y2, y3=y3)
    act = np.arange(M)
    # local views
    loc = dict(full)
    T_a, t_a, Tcp, Tsp = T, t, Tc_prev, Ts_prev
    tt_a, ts_a, dT_a, dt0_a = tt, ts500, dTmax, dt0
    it = 0
    while len(act):
        it += 1
        dr, vol, area, R, Tbc = loc["dr"], loc["vol"], loc["area"], loc["R"], loc["Tb"]
        x0, x1, x2, x3 = loc["x0"], loc["x1"], loc["x2"], loc["x3"]
        y0, y1, y2, y3 = loc["y0"], loc["y1"], loc["y2"], loc["y3"]
        late = ~np.isnan(tt_a[:, 3])
        dt = np.where(late, 3 * dt0_a, dt0_a)
        C, G, U = coeffs(T_a)
        Tp = cn_step(T_a, dt, C, G, U)
        C, G, U = coeffs(0.5 * (T_a + Tp))
        Tn = cn_step(T_a, dt, C, G, U)
        tn = t_a + dt
        Tc = (9 * Tn[:, 0] - Tn[:, 1]) / 8.0
        Tsn = surf(Tn[:, -1], lut(kt, Tn[:, -1]))[0]
        dT_a = np.maximum(dT_a, Tc - Tsn)
        for j, Tg_ in enumerate(targets):
            m = np.isnan(tt_a[:, j]) & (Tc <= Tg_)
            if m.any():
                f = (Tcp[m] - Tg_) / (Tcp[m] - Tc[m])
                tt_a[m, j] = t_a[m] + f * dt[m]
                if j == 3:
                    ts_a[m] = Tsp[m] + f * (Tsn[m] - Tsp[m])
        T_a, t_a, Tcp, Tsp = Tn, tn, Tc, Tsn
        done = ~np.isnan(tt_a[:, 4])
        if done.any() or it % 200 == 0:
            tt[act] = tt_a; ts500[act] = ts_a; dTmax[act] = dT_a
            if done.any():
                keep = ~done
                act = act[keep]
                T_a, t_a, Tcp, Tsp = T_a[keep], t_a[keep], Tcp[keep], Tsp[keep]
                tt_a, ts_a, dT_a, dt0_a = tt_a[keep], ts_a[keep], dT_a[keep], dt0_a[keep]
                loc = {k: v[keep] for k, v in loc.items()}
    return tt, ts500, dTmax


def compute(loads, figs, N=24, chunk=4000, DTF=2.0):
    M = len(loads)
    out = np.zeros((M, 5))
    for s in range(0, M, chunk):
        sl = slice(s, min(M, s + chunk))
        L = loads.iloc[sl]
        R = L.diameter_mm.values.astype(float) / 2000.0
        tt = np.zeros((len(L), 5)); ts500 = np.zeros(len(L)); dT = np.zeros(len(L))
        for st in L.steel.unique():
            m = (L.steel == st).values
            S = STEELS[st]
            a_, b_, c_ = solve((S[0], S[1]), (S[2], S[3]), R[m],
                               L.furnace_C.values[m].astype(float),
                               L.bath_C.values[m].astype(float), figs[sl][m], N, DTF)
            tt[m] = a_; ts500[m] = b_; dT[m] = c_
        out[sl, 0] = tt[:, 3] - tt[:, 0]
        out[sl, 1] = 50.0 / (tt[:, 2] - tt[:, 1])
        out[sl, 2] = dT
        out[sl, 3] = ts500
        out[sl, 4] = tt[:, 4]
    return out


def main():
    pkg, outp = sys.argv[1], sys.argv[2]
    loads = pd.read_csv(os.path.join(pkg, "loads.csv"), dtype={"load": str, "tank": str})
    loads["tank"] = loads["tank"].str.strip()
    loads["steel"] = loads["steel"].str.strip()
    loads["dn"] = [dnum(x) for x in loads["date"]]
    figs, info = settle_oil(pkg, loads)
    sys.stderr.write("lab order: %s\n" % info["order"])
    N = int(os.environ.get("QN", "28"))
    res = compute(loads, figs, N, DTF=float(os.environ.get("QDT", "4.0")))
    df = pd.DataFrame({"load": loads["load"].values,
                       "t85_core_s": res[:, 0], "cr700_core_K_s": res[:, 1],
                       "dT_max_K": res[:, 2], "ts_core500_C": res[:, 3],
                       "t150_core_s": res[:, 4]})
    df.to_csv(outp, index=False, float_format="%.6g")


if __name__ == "__main__":
    main()
