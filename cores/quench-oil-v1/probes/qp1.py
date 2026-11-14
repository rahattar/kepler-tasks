#!/usr/bin/env python3
"""HT-5 bar quench calculation for one site package.
usage: python3 quench.py PACKAGE_DIR OUT_CSV
"""
import sys, os, json, subprocess, io
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
import numpy as np
import pandas as pd

KTAB = {"C45": ([20, 300, 600, 800, 900], [50, 44, 34, 26, 26]),
        "42CrMo4": ([20, 300, 600, 800, 900], [43, 40, 33, 27, 27])}
CTAB = {"C45": ([20, 300, 600, 720, 800, 900], [470, 560, 750, 900, 650, 650]),
        "42CrMo4": ([20, 300, 600, 720, 800, 900], [460, 550, 720, 850, 640, 640])}
RHO = 7800.0
KP = 14200.0


def _tab(T, xs, ys):
    """piecewise-linear table, xs/ys: lists of (M,) arrays per breakpoint; T: (..., M)."""
    out = np.full(T.shape, 0.0) + ys[0]
    for j in range(len(xs) - 1):
        w = np.clip((T - xs[j]) * (1.0 / (xs[j + 1] - xs[j])), 0.0, 1.0)
        out += w * (ys[j + 1] - ys[j])
    return out


def _enth(T, xs, ys):
    out = (np.minimum(T, xs[0]) - xs[0]) * ys[0]
    for j in range(len(xs) - 1):
        u = np.clip(T, xs[j], xs[j + 1]) - xs[j]
        out += u * (ys[j] + (0.5 * (ys[j + 1] - ys[j]) / (xs[j + 1] - xs[j])) * u)
    out += (np.maximum(T, xs[-1]) - xs[-1]) * ys[-1]
    return out


def simulate(steel, D_mm, Tf, Tb, crmax, tcr, cr300, N=30, nsteps=1500):
    """Crank-Nicolson finite volumes, all loads at once. Arrays are (N+1, M)."""
    steel = np.asarray(steel); M = len(steel)
    R = np.asarray(D_mm, float) / 2000.0
    Tf = np.asarray(Tf, float); Tb = np.asarray(Tb, float)
    crmax = np.asarray(crmax, float); tcr = np.asarray(tcr, float); cr300 = np.asarray(cr300, float)
    hp = KP * crmax / (tcr - 40.0); h300 = KP * cr300 / 260.0
    hx = [np.full(M, 100.0), np.full(M, 300.0), tcr, tcr + 120]
    hy = [0.6 * h300, h300, hp, 0.15 * hp]
    kxa = np.array([KTAB[s][0] for s in steel], float).T; kya = np.array([KTAB[s][1] for s in steel], float).T
    cxa = np.array([CTAB[s][0] for s in steel], float).T; cya = np.array([CTAB[s][1] for s in steel], float).T
    kx = [r[None] for r in kxa]; ky = [r[None] for r in kya]
    cx = [r[None] for r in cxa]; cy = [r[None] for r in cya]
    dr = R / N
    i = np.arange(N + 1, dtype=float)
    vol = i.copy(); vol[0] = 0.125; vol[N] = 0.5 * (N - 0.25)
    V = RHO * vol[:, None] * dr[None, :] ** 2          # rho * volume / (2 pi L)
    Gf = (np.arange(N) + 0.5)[:, None] * np.ones((1, M))   # face radius / dr * dr / dr
    tau = RHO * 600 * R ** 2 / 30.0
    tend = tau * 6.0
    dt0 = tau * 2e-5
    g = 1.002
    for _ in range(80):
        g = (tend / dt0 * (g - 1) + 1) ** (1.0 / nsteps)
    T = np.repeat(Tf[None, :], N + 1, 0)
    Tprev = T.copy()
    dtprev = None
    t = np.zeros(M); dt = dt0.copy()
    keys = (800, 725, 675, 500, 150)
    res_t = {Tc: np.full(M, np.nan) for Tc in keys}
    ts500 = np.full(M, np.nan); dTmax = np.zeros(M)
    a = np.empty((N + 1, M)); b = np.empty((N + 1, M)); c = np.empty((N + 1, M))
    cpp = np.empty((N + 1, M)); dp = np.empty((N + 1, M)); Tn = np.empty((N + 1, M))
    for n in range(nsteps * 3):
        # predictor: extrapolate the last step
        if dtprev is None:
            Tg = T
        else:
            Tg = T + (T - Tprev) * (dt / dtprev)
        Tav = 0.5 * (T + Tg)
        kf = _tab(0.5 * (Tav[1:] + Tav[:-1]), kx, ky)
        dTg = Tg - T
        small = np.abs(dTg) < 1e-3
        cpm = _tab(Tav, cx, cy)
        cpc = (_enth(Tg, cx, cy) - _enth(T, cx, cy)) / np.where(small, 1.0, dTg)
        cp = np.where(small, cpm, cpc)
        hs = _tab(Tav[N], hx, hy)
        Cn = cp * V / dt
        G = kf * Gf
        hA = hs * R
        # explicit half
        fl = G * (T[1:] - T[:-1])
        d = Cn * T
        d[:-1] += 0.5 * fl; d[1:] -= 0.5 * fl
        d[N] += hA * (Tb - 0.5 * T[N])
        hG = 0.5 * G
        a[0] = 0; a[1:] = -hG
        c[:-1] = -hG; c[N] = 0
        b[:] = Cn; b[:-1] += hG; b[1:] += hG; b[N] += 0.5 * hA
        cpp[0] = c[0] / b[0]; dp[0] = d[0] / b[0]
        for j in range(1, N + 1):
            m = 1.0 / (b[j] - a[j] * cpp[j - 1])
            cpp[j] = c[j] * m
            dp[j] = (d[j] - a[j] * dp[j - 1]) * m
        Tn[N] = dp[N]
        for j in range(N - 1, -1, -1):
            Tn[j] = dp[j] - cpp[j] * Tn[j + 1]
        c0, c1 = T[0], Tn[0]
        for Tc in keys:
            arr = res_t[Tc]
            hit = (c1 <= Tc) & (c0 > Tc)
            if hit.any():
                w = (c0[hit] - Tc) / (c0[hit] - c1[hit])
                arr[hit] = t[hit] + w * dt[hit]
                if Tc == 500:
                    ts500[hit] = T[N, hit] + w * (Tn[N, hit] - T[N, hit])
        np.maximum(dTmax, Tn[0] - Tn[N], out=dTmax)
        chg = np.abs(Tn - T).max(0)
        Tprev = T; T = Tn.copy(); t = t + dt; dtprev = dt
        if DTSTEP:
            cc = np.abs(Tn[0] - Tprev[0])
            fac = DTSTEP / np.maximum(chg, 1e-9)
            inr = (Tn[0] > 450) & (Tn[0] < 850)
            fac = np.where(inr, np.minimum(fac, DTC / np.maximum(cc, 1e-9)), fac)
            dt = dt * np.clip(fac, 0.7, 1.3)
            dt = np.minimum(dt, tau * 0.02)
        else:
            dt = dt * g
        if not np.isnan(res_t[150]).any():
            break
    simulate.steps = n
    return dict(t85_core_s=res_t[500] - res_t[800],
                cr700_core_K_s=50.0 / (res_t[675] - res_t[725]),
                dT_max_K=dTmax, ts_core500_C=ts500, t150_core_s=res_t[150])


# ---------------------------------------------------------------- oil figures
FIG = ["cr_max_K_s", "t_crmax_C", "cr_300_K_s"]


def close(a, b, tol=0.012, ttol=2.5):
    return (abs(a[0] / b[0] - 1) < tol and abs(a[1] - b[1]) <= ttol and abs(a[2] / b[2] - 1) < tol)


def assign_charges(tanks, systems, samples, log):
    """tank -> oil system holding its charge: the register, checked against the analyses on file.
    Tanks of one charge show the same figures (lab repeat 0.5 %, ageing < 0.5 % per round)."""
    reg = dict(zip(tanks.tank, tanks.oil_system))
    rec = {}
    for r in samples.itertuples():
        rec.setdefault(r.sampled_at, []).append(
            (pd.Timestamp(r.date).toordinal(), np.array([r.cr_max_K_s, r.t_crmax_C, r.cr_300_K_s], float)))
    tk = [t for t in tanks.tank if t in rec]

    def rel(x, y):
        """+1 same charge, -1 different, 0 unknown"""
        same = diff = 0
        for near in (30, 200):
            for dx, fx in rec[x]:
                for dy, fy in rec[y]:
                    gap = abs(dx - dy)
                    if gap > near or (near > 30 and gap <= 30):
                        continue
                    if close(fx, fy, 0.012 if gap <= 30 else 0.016, 3.0):
                        same += 1
                    else:
                        diff += 1
            if same + diff:
                break
        if same + diff == 0:
            return 0
        return 1 if same >= diff else -1

    R = {(x, y): rel(x, y) for x in tk for y in tk if x < y}
    relf = lambda x, y: R[(x, y) if x < y else (y, x)]
    sysof = dict(reg)
    for sname in sorted(set(reg.values())):
        members = [t for t in tk if reg[t] == sname]
        if len(members) < 2:
            continue
        par = {t: t for t in members}

        def find(t):
            while par[t] != t:
                t = par[t]
            return t
        for x in members:
            for y in members:
                if x < y and relf(x, y) == 1:
                    par[find(x)] = find(y)
        comps = {}
        for t in members:
            comps.setdefault(find(t), []).append(t)
        if len(comps) == 1:
            continue
        cl = sorted(comps.values(), key=lambda c: (-len(c), -sum(len(rec[t]) for t in c)))
        for c in cl[1:]:
            # a stray group: does its oil match another system?
            cand = set()
            for t in c:
                for o in tk:
                    if reg[o] != sname and relf(t, o) == 1:
                        cand.add(reg[o])
            new = cand.pop() if len(cand) == 1 else "SELF-" + c[0]
            for t in c:
                sysof[t] = new
                print("note: %s registered on %s, its oil analyses put it on %s" % (t, sname, new), file=sys.stderr)
    # single tanks whose oil matches a central system they are not registered on
    return sysof


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    site = json.load(open(os.path.join(pkg, "site.json")))
    nlab = int(site.get("lab_samples", 0)); drawn = str(site["samples_drawn"])
    tanks = pd.read_csv(os.path.join(pkg, "tanks.csv"), dtype=str)
    systems = pd.read_csv(os.path.join(pkg, "oil_systems.csv"), dtype=str)
    log = pd.read_csv(os.path.join(pkg, "oil_log.csv"), dtype=str)
    samples = pd.read_csv(os.path.join(pkg, "oil_samples.csv"), dtype={"date": str, "sampled_at": str})
    loads = pd.read_csv(os.path.join(pkg, "loads.csv"), dtype={"load": str, "tank": str, "date": str, "steel": str})
    for df in (tanks, systems, log, samples, loads):
        df.columns = [c.strip() for c in df.columns]
    for df, cols in ((tanks, ["tank", "oil_system"]), (log, ["date", "oil_system", "work"]),
                     (samples, ["date", "sampled_at"]), (loads, ["load", "tank", "date", "steel"])):
        for c in cols:
            df[c] = df[c].astype(str).str.strip()

    # tanks seen in loads/samples but missing in the register: own charge
    known = set(tanks.tank)
    extra = (set(loads.tank) | set(samples.sampled_at)) - known
    if extra:
        tanks = pd.concat([tanks, pd.DataFrame({"tank": sorted(extra), "oil_system": ["SELF-" + t for t in sorted(extra)]})])
    sysof = assign_charges(tanks, systems, samples, log)
    selfs = {s for s in set(sysof.values()) if s.startswith("SELF-")}

    renew = {}
    for r in log.itertuples():
        if r.work.upper() == "CHARGE_RENEWED":
            renew.setdefault(r.oil_system, []).append(r.date)
    for s in renew:
        renew[s].sort()

    def charge_of(system, date):
        """index of the charge (number of renewals on or before date)."""
        return sum(1 for d in renew.get(system, []) if d <= date)

    # analyses per (system, charge, date) -> list of figure vectors
    ana = {}
    for r in samples.itertuples():
        s = sysof.get(r.sampled_at)
        if s is None:
            continue
        ana.setdefault((s, charge_of(s, r.date)), {}).setdefault(r.date, []).append(
            np.array([getattr(r, f) for f in FIG], float))

    # which charges the loads need, and whether the lab is needed
    loads["sys"] = loads.tank.map(sysof)
    loads["chg"] = [charge_of(s, d) for s, d in zip(loads.sys, loads.date)]
    need = []  # (priority, system)
    for (s, ch), grp in loads.groupby(["sys", "chg"]):
        current = ch == charge_of(s, "9999-99-99")
        if not current:
            continue  # an old charge: latest analysis holds till renewal
        a = ana.get((s, ch), {})
        last = max(a) if a else None
        if last is not None and grp.date.max() <= last:
            continue
        if not a:
            pri = 0 if s not in selfs else 1          # renewed charge without analysis
            inst = 1e9
        else:
            pri = 1 if s in selfs else 2
            ds = sorted(a)
            vals = [np.mean(a[d], 0) for d in ds]
            if len(ds) >= 2:
                inst = max(abs(vals[i + 1][0] / vals[i][0] - 1) for i in range(len(ds) - 1))
            else:
                inst = 1.0
        need.append((pri, -inst, -len(grp), s))
    need.sort()
    order_sys = [n[3] for n in need[:max(nlab, 0)]]
    skipped = [n[3] for n in need[max(nlab, 0):]]
    if skipped:
        print("note: lab budget %d, not sampled: %s" % (nlab, skipped), file=sys.stderr)

    lab = {}
    if order_sys:
        pick = []
        cnt = samples.sampled_at.value_counts()
        for s in order_sys:
            cands = [t for t in tanks.tank if sysof[t] == s]
            cands.sort(key=lambda t: (-(loads.tank == t).sum(), t))
            pick.append(cands[0])
        try:
            p = subprocess.run(["labsample", pkg] + pick, capture_output=True, text=True, timeout=30)
            print("labsample %s -> %s" % (" ".join(pick), p.stdout.strip().replace("\n", " | ")), file=sys.stderr)
            df = pd.read_csv(io.StringIO(p.stdout), dtype={"sampled_at": str})
            for r in df.itertuples():
                lab[sysof.get(str(r.sampled_at).strip(), "?")] = np.array([getattr(r, f) for f in FIG], float)
        except Exception as e:
            print("labsample failed: %r" % (e,), file=sys.stderr)
    for s, v in lab.items():
        ana.setdefault((s, charge_of(s, drawn)), {}).setdefault(drawn, []).append(v)

    def ordinal(d):
        return pd.Timestamp(d).toordinal()

    def figures(s, ch, date):
        a = ana.get((s, ch), {})
        if not a:
            return None
        ds = sorted(a); x = np.array([ordinal(d) for d in ds], float)
        v = np.array([np.mean(a[d], 0) for d in ds])
        t = ordinal(date)
        current = ch == charge_of(s, "9999-99-99")
        if t <= x[0]:
            return v[0]
        if t >= x[-1]:
            if current and drawn not in a and len(ds) >= 2 and ds[-1] < drawn:
                # extrapolate the ageing trend of the last rounds (lab not available)
                k = min(len(ds), 3)
                sl = (v[-1] - v[-k]) / (x[-1] - x[-k])
                sl = np.maximum(sl, 0.0) * np.array([1, 1, 1])
                tt = min(t, ordinal(drawn))
                return v[-1] + sl * (tt - x[-1])
            return v[-1]
        return np.array([np.interp(t, x, v[:, j]) for j in range(3)])

    figs = []
    for s, ch, d, tk in zip(loads.sys, loads.chg, loads.date, loads.tank):
        f = figures(s, ch, d)
        if f is None:
            # fall back: previous charge, then any analysis of the tank
            for c2 in range(ch - 1, -1, -1):
                f = figures(s, c2, d)
                if f is not None:
                    break
        if f is None:
            sub = samples[samples.sampled_at == tk]
            f = sub[FIG].mean().values if len(sub) else samples[FIG].mean().values
        figs.append(f)
    figs = np.array(figs, float)

    M = len(loads)
    res = {k: np.full(M, np.nan) for k in COLS}
    if M:
        steel = loads.steel.values
        unknown = ~np.isin(steel, list(KTAB))
        steel = np.where(unknown, "C45", steel)
        chunk = 500
        for i0 in range(0, M, chunk):
            sl = slice(i0, i0 + chunk)
            r = simulate(steel[sl], loads.diameter_mm.values[sl].astype(float), loads.furnace_C.values[sl].astype(float),
                         loads.bath_C.values[sl].astype(float), figs[sl, 0], figs[sl, 1], figs[sl, 2], N=NR, nsteps=NT)
            for k in COLS:
                res[k][sl] = r[k]
    o = pd.DataFrame({"load": loads.load})
    for k in COLS:
        o[k] = res[k]
    o.to_csv(out, index=False, float_format="%.6g")


COLS = ["t85_core_s", "cr700_core_K_s", "dT_max_K", "ts_core500_C", "t150_core_s"]
DTC = 0.5
DTSTEP = 2.0
NR, NT = 30, 5000

if __name__ == "__main__":
    main()
