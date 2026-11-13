#!/usr/bin/env python3
"""Sucker-rod well calculation to RL-2 for one field package.

python3 rodlift.py FIELD_DIR OUT_CSV
"""
import sys, os, json
import numpy as np
import pandas as pd

G = 9.80665
MAT = {"steel": (200e9, 8000.0), "fibreglass": (50e9, 2400.0)}
TUBING_ID = {60.3: 50.7, 73.0: 62.0, 88.9: 76.0}
E_T = 200e9

K_STEPS = 500     # time steps per stroke cycle in the card fit
N_CYC = 9         # cycles simulated; the last is the steady one
CFL = 0.999
FINAL_K = 720
SETTLE = 14.0     # s times c: settling time of the transient
MIN_CYC = 3
MAX_CYC = 11

UP, GAS, DOWN, LOCK = 0, 1, 2, 3


class Well:
    pass


def load_package(d):
    with open(os.path.join(d, "field.json")) as f:
        fj = json.load(f)
    wells = pd.read_csv(os.path.join(d, "wells.csv"))
    rods = pd.read_csv(os.path.join(d, "rods.csv"))
    cards = pd.read_csv(os.path.join(d, "cards.csv"))
    sets = pd.read_csv(os.path.join(d, "settings.csv"))
    c = float(fj["damping_per_s"])
    rho_l = float(fj["liquid_density_kg_m3"])
    W = {}
    for _, r in wells.iterrows():
        w = Well()
        w.name = str(r["well"]).strip()
        w.L = float(r["pump_depth_m"])
        w.Ap = np.pi * (float(r["plunger_mm"]) / 1000) ** 2 / 4
        od = float(r["tubing_od_mm"])
        idd = min(TUBING_ID.items(), key=lambda kv: abs(kv[0] - od))[1]
        w.At = np.pi * ((od / 1000) ** 2 - (idd / 1000) ** 2) / 4
        a = r["anchor_depth_m"]
        w.anchor = None if pd.isna(a) or str(a).strip() == "" else float(a)
        w.pt = float(r["tubing_head_pressure_kPa"]) * 1000
        w.k = float(r["unit_factor"])
        w.S0 = float(r["found_surface_stroke_m"])
        w.N0 = float(r["found_spm"])
        rr = rods[rods["well"].astype(str).str.strip() == w.name].sort_values("taper")
        w.tapers = []
        Wt = 0.0
        for _, t in rr.iterrows():
            E, rho = MAT[str(t["material"]).strip().lower()]
            A = np.pi * (float(t["diameter_mm"]) / 1000) ** 2 / 4
            Lt = float(t["length_m"])
            w.tapers.append((E, rho, A, Lt))
            Wt += A * Lt * G * (rho - rho_l)
        w.Wr = Wt
        w.pd = w.pt + rho_l * G * w.L
        cw = cards[cards["well"].astype(str).str.strip() == w.name]
        w.cards = []
        for cn, cc in cw.groupby("card"):
            cc = cc.sort_values("sample")
            w.cards.append((cc["sample"].to_numpy(float), cc["position_m"].to_numpy(float),
                            cc["load_kN"].to_numpy(float) * 1000))
        W[w.name] = w
    return c, rho_l, W, sets


def _simulate(rows, c, K=K_STEPS, ncyc=N_CYC, record=False):
    """rows: list of dicts with well, S, N, Fo, hs (inf for full), Lf.
    Returns arrays Sp, hl, PPRL, MPRL (and the last cycle's PRL if record)."""
    n = len(rows)
    dts = np.array([60.0 / r["N"] / K for r in rows])
    # build grids
    segs = []
    for r, dt in zip(rows, dts):
        w = r["well"]
        kk, mm = [], []
        for (E, rho, A, Lt) in w.tapers:
            a = np.sqrt(E / rho)
            ns = max(1, int(np.floor(Lt * CFL / (a * dt))))
            dx = Lt / ns
            kk += [E * A / dx] * ns
            mm += [rho * A * dx] * ns
        segs.append((np.array(kk), np.array(mm)))
    M = max(len(s[0]) for s in segs)  # segments; nodes 0..M (node 0 top, node M plunger)
    kseg = np.zeros((n, M))
    mnode = np.ones((n, M + 1))
    for i, (kk, mm) in enumerate(segs):
        m = len(kk)
        # pad at the top with very stiff massive? Instead pad at bottom: pad segments as rigid links
        kseg[i, :m] = kk
        nm = np.zeros(m + 1)
        nm[:-1] += mm / 2
        nm[1:] += mm / 2
        mnode[i, :m + 1] = nm
        mnode[i, m + 1:] = 1.0
    nseg = np.array([len(s[0]) for s in segs])
    # padded rows: the plunger is node nseg; nodes beyond are dummies (kseg 0)
    idx = np.arange(n)
    S = np.array([r["S"] for r in rows])
    kf = np.array([r["well"].k for r in rows])
    Ap = np.array([r["well"].Ap for r in rows])
    Fo = np.array([r["Fo"] for r in rows])
    Fd = np.array([r["well"].pd * r["well"].Ap for r in rows])
    Fi = np.maximum(Fd - Fo, 1.0)
    hs = np.array([r["hs"] for r in rows])
    kt = np.array([E_T * r["well"].At / r["Lf"] if r["Lf"] > 0 else np.inf for r in rows])
    invkt = 1.0 / kt
    damp = np.exp(-c * dts)[:, None]  # velocity damping factor per step

    y = np.zeros((n, M + 1))
    v = np.zeros((n, M + 1))
    inner = np.zeros((n, M + 1), bool)
    for i in range(n):
        inner[i, 1:nseg[i] + 1] = True
    dtm = (dts[:, None] / mnode) * inner
    mp = mnode[idx, nseg]
    Cc = 1.0 / kt + dts ** 2 * np.exp(-c * dts) / mp

    state = np.full(n, LOCK)
    s = np.zeros(n)
    s_lock = np.zeros(n)
    s_min = np.zeros(n)
    s_top = np.zeros(n)
    g0 = np.zeros(n)
    Sp = np.zeros(n)
    hl = np.zeros(n)
    Fp = np.zeros(n)
    pmax = np.full(n, -np.inf)
    pmin = np.full(n, np.inf)
    Wr = np.array([r["well"].Wr for r in rows])
    rec = np.zeros((n, K)) if record else None
    total = K * ncyc
    Cfo = Fo * Cc
    bconst = -Cc * Fd
    c0k = Cc * Fi
    alpha = dts ** 2 * np.exp(-c * dts) / mp
    beta = dts * np.exp(-c * dts) / mp
    dampv = np.broadcast_to(damp, y.shape).copy()
    kdt = dtm * damp
    dtcol = dts[:, None]
    qs = 2 * np.pi * np.arange(total + 1) / K
    ytop = S[None, :] * ((1 - np.cos(qs))[:, None] / 2 + kf[None, :] / 8 * (1 - np.cos(2 * qs))[:, None])
    d = np.empty((n, M))
    f = np.zeros((n, M + 1))
    for step in range(1, total + 1):
        last = step > total - K
        np.subtract(y[:, :-1], y[:, 1:], out=d)
        d *= kseg
        f[:, 1:] = d
        f[:, 1:-1] -= d[:, 1:]
        v *= dampv
        f *= kdt
        v += f
        y += v * dtcol
        y[:, 0] = ytop[step]
        u = y[idx, nseg] + Fo * invkt
        s_prev = s
        st = state
        for _ in range(3):
            changed = False
            # UP: standing valve open
            sc_up = u - Cfo
            trig = (st == UP) & (sc_up < s_prev)
            if trig.any():
                changed = True
                Sp = np.where(trig, s_prev - s_min, Sp)
                hl = np.where(trig, np.minimum(Sp, hs), hl)
                g0 = np.where(trig, Sp - hl, g0)
                s_top = np.where(trig, s_prev, s_top)
                gas = g0 > 1e-9
                st = np.where(trig, np.where(gas, GAS, LOCK), st)
                s_lock = np.where(trig & ~gas, s_prev, s_lock)
            # GAS: both valves shut on gas
            mg = st == GAS
            if mg.any():
                bb = u - s_top + g0 + bconst
                z = (bb + np.sqrt(np.maximum(bb * bb + 4 * c0k * g0, 0))) / 2
                sc_g = z - g0 + s_top
                F_g = (u - sc_g) / Cc
                to_up = mg & (sc_g >= s_top)
                to_dn = mg & ~to_up & (F_g <= 0)
                if to_up.any() or to_dn.any():
                    changed = True
                    st = np.where(to_up, UP, np.where(to_dn, DOWN, st))
            # LOCK: both valves shut on liquid
            F_l = (u - s_lock) / Cc
            ml = st == LOCK
            hi = ml & (F_l > Fo)
            lo = ml & (F_l < 0)
            if hi.any() or lo.any():
                changed = True
                st = np.where(hi, UP, np.where(lo, DOWN, st))
            # DOWN: travelling valve open
            trig = (st == DOWN) & (u > s_prev)
            if trig.any():
                changed = True
                s_min = np.where(trig, s_prev, s_min)
                s_lock = np.where(trig, s_prev, s_lock)
                st = np.where(trig, LOCK, st)
                F_l = (u - s_lock) / Cc
            if not changed:
                break
        state = st
        if (st == GAS).any():
            bb = u - s_top + g0 + bconst
            z = (bb + np.sqrt(np.maximum(bb * bb + 4 * c0k * g0, 0))) / 2
            sc_g = z - g0 + s_top
            F_g = (u - sc_g) / Cc
        else:
            sc_g = F_g = 0.0
        s = np.select([st == UP, st == GAS, st == LOCK], [u - Cfo, sc_g, s_lock], u)
        Fp = np.select([st == UP, st == GAS, st == LOCK], [Fo, F_g, F_l], 0.0)
        y[idx, nseg] -= alpha * Fp
        v[idx, nseg] -= beta * Fp
        if last:
            prl = Wr + kseg[:, 0] * (y[:, 0] - y[:, 1])
            np.maximum(pmax, prl, out=pmax)
            np.minimum(pmin, prl, out=pmin)
            if record:
                rec[:, step - (total - K) - 1] = prl
    out = dict(Sp=Sp, hl=hl, pprl=pmax, mprl=pmin, N=np.array([r["N"] for r in rows]), Ap=Ap)
    if record:
        out["rec"] = rec
    return out


def simulate(rows, c, K=K_STEPS, ncyc=None, record=False, chunk=1300):
    """Runs the rows in groups of like speed and grid size. ncyc None: enough cycles for the
    start-up transient to die out under the damping (amplitude decays as exp(-c t / 2))."""
    n = len(rows)
    N = np.array([r["N"] for r in rows])
    if ncyc is None:
        tset = SETTLE / max(c, 0.05)
        cyc = np.clip(np.ceil(tset * N / 60.0), MIN_CYC, MAX_CYC).astype(int) + 1
    else:
        cyc = np.full(n, ncyc)
    size = np.array([sum(Lt / np.sqrt(E / rho) for (E, rho, A, Lt) in r["well"].tapers) * r["N"] for r in rows])
    res = None
    for nc in np.unique(cyc):
        sel = np.where(cyc == nc)[0]
        order = sel[np.argsort(size[sel], kind="stable")]
        for a in range(0, len(order), chunk):
            ii = order[a:a + chunk]
            o = _simulate([rows[i] for i in ii], c, K=K, ncyc=int(nc), record=record)
            if res is None:
                res = {k: np.zeros((n,) + v.shape[1:]) for k, v in o.items()}
            for k, v in o.items():
                res[k][ii] = v
    return res


def card_rms(ws, P, c, K):
    """P: list of (well index, Fo, hs_frac, Lf). Returns rms misfit to the cards and sim output."""
    rows = [dict(well=ws[i], S=ws[i].S0, N=ws[i].N0, Fo=Fo, hs=h * ws[i].S0, Lf=Lf)
            for (i, Fo, h, Lf) in P]
    o = simulate(rows, c, K=K, record=True)
    J = (np.arange(200) * K // 200 - 1) % K
    r = np.empty(len(P))
    for j, (i, Fo, h, Lf) in enumerate(P):
        w = ws[i]
        sim = o["rec"][j][J]
        r[j] = np.sqrt(np.mean([np.mean((cd[2] - sim[cd[0].astype(int)]) ** 2) for cd in w.cards]))
    return r, o


def fit(ws, c, K=600):
    lf_opts = []
    for w in ws:
        o = [w.L - w.anchor] if w.anchor is not None else []
        o.append(w.L)
        lf_opts.append(o)
    # coarse grid
    P = []
    for i, w in enumerate(ws):
        Fd = w.pd * w.Ap
        for Lf in lf_opts[i]:
            for fo in np.linspace(0.3, 0.98, 8):
                for h in np.linspace(0.25, 1.05, 6):
                    P.append((i, fo * Fd, h, Lf))
    r, _ = card_rms(ws, P, c, 300)
    best = {}
    for j, p in enumerate(P):
        key = (p[0], p[3])
        if key not in best or r[j] < best[key][0]:
            best[key] = (r[j], p)
    # drop anchor alternatives that the cards clearly reject
    for i in range(len(ws)):
        opts = [k for k in best if k[0] == i]
        b0 = min(best[k][0] for k in opts)
        lf_opts[i] = [k[1] for k in opts if best[k][0] <= 2.0 * b0]
    cur = {k: [np.array([v[1][1], v[1][2]]), np.array([0.05 * ws[k[0]].pd * ws[k[0]].Ap, 0.08])]
           for k, v in best.items() if k[1] in lf_opts[k[0]]}
    out = {}
    offs = [(a, b) for a in (-2, -1, 0, 1, 2) for b in (-2, -1, 0, 1, 2)]
    nn = len(offs)
    for it in range(6):
        P = []
        for k, (p, st) in cur.items():
            Fd = ws[k[0]].pd * ws[k[0]].Ap
            for a, b in offs:
                q = p + np.array([a, b]) * st
                q[0] = min(max(q[0], 0.05 * Fd), 0.999 * Fd)
                q[1] = min(max(q[1], 0.02), 1.3)
                P.append((k[0], q[0], q[1], k[1]))
        r, o = card_rms(ws, P, c, K if it >= 3 else 400)
        j0 = 0
        for k in cur:
            rr = r[j0:j0 + nn]
            jb = int(np.argmin(rr))
            pb = P[j0 + jb]
            cur[k][0] = np.array([pb[1], pb[2]])
            cur[k][1] = cur[k][1] * 0.45
            out[k] = (rr[jb], pb, o["Sp"][j0 + jb], o["hl"][j0 + jb])
            j0 += nn
    res = {}
    for i, w in enumerate(ws):
        cands = [out[(i, Lf)] for Lf in lf_opts[i]]
        rms, p, Sp, hl = min(cands, key=lambda t: t[0])
        Fo, h, Lf = p[1], p[2], p[3]
        hs = h * w.S0
        full = (Sp - min(Sp, hs)) < 0.03 * Sp
        res[w.name] = dict(Fo=Fo, hs=np.inf if full else hs, Lf=Lf, rms=rms, Sp=Sp, full=full,
                           alts=[(t[0], t[1][3]) for t in cands])
    return res


def main():
    d, out = sys.argv[1], sys.argv[2]
    c, rho_l, W, sets = load_package(d)
    ws = list(W.values())
    fr = fit(ws, c)
    if os.environ.get("RODLIFT_DEBUG"):
        for k, v in fr.items():
            print(k, {a: (np.round(b, 4) if isinstance(b, float) else b) for a, b in v.items()}, file=sys.stderr)
    rows = []
    for r in sets.itertuples(index=False):
        w = W[str(r.well).strip()]
        f = fr[w.name]
        N = float(r.spm)
        hs = f["hs"] * w.N0 / N  # liquid supply a minute is fixed: h_s = Q_s / (A_p N)
        rows.append(dict(well=w, S=float(r.surface_stroke_m), N=N, Fo=f["Fo"], hs=hs, Lf=f["Lf"]))
    o = simulate(rows, c, K=FINAL_K)
    liq = o["Ap"] * o["hl"] * o["N"] * 1440
    df = pd.DataFrame(dict(setting=sets["setting"].astype(str), plunger_stroke_m=np.round(o["Sp"], 5),
                           liquid_m3_d=np.round(liq, 4), pprl_kN=np.round(o["pprl"] / 1000, 4),
                           mprl_kN=np.round(o["mprl"] / 1000, 4)))
    df.to_csv(out, index=False)


if __name__ == "__main__":
    main()
