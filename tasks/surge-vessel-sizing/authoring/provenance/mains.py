"""Sealed definitions of the mains (the example and the hidden ones), their SCADA records, and the MS-SV check."""
import csv, math, os, random
import numpy as np
import moc

BAR = 10.197
LIM = dict(pmin=-3.0, pmax=160.0, gas=0.85, economy=1.15)


def colebrook(k, D, v=1.6, nu=1.0e-6):
    Re = v * D / nu; f = 0.02
    for _ in range(60):
        f = (-2 * math.log10(k / (3.7 * D) + 2.51 / (Re * math.sqrt(f)))) ** -2
    return f


def ridge_profile(L, z0, z_end, knee_x, knee_z, dip, n=27):
    """Rising main to a knee, a dip after it, then a gentle rise to the reservoir."""
    ch = np.linspace(0, L, n)
    ch = np.unique(np.concatenate([ch, [knee_x - 150, knee_x - 100, knee_x - 50, knee_x, knee_x + 50, knee_x + 100,
                                         knee_x + 150]]))
    z = np.where(ch <= knee_x, z0 + (knee_z - z0) * (ch / knee_x) ** 1.15,
                 knee_z - dip * np.sin(np.clip((ch - knee_x) / (L - knee_x), 0, 1) * math.pi * 0.5) ** 0.6
                 + (z_end - (knee_z - dip)) * ((ch - knee_x) / (L - knee_x)).clip(0, 1) ** 2)
    return ch, np.round(z, 1)


def main_def(name, L, D, k_design, k_true, z0, knee_frac, knee_z, dip, z_end, BWL, TWL, ww, new, old, seed,
             diversion=None, datum=0.0, throttle=None, a=1100.0, chamber_name="AV-4", tag="PT401"):
    knee_x = round(knee_frac * L / 50) * 50
    if throttle:    # logged start and end (local time); the SCADA applies the throttle loss exactly between them
        r = random.Random(seed + 1)
        throttle = dict(throttle, t0="2026-09-%02d 08:%02d" % (1 + throttle["day0"], r.randint(0, 59)),
                        t1="2026-09-%02d 16:%02d" % (throttle["day1"], r.randint(0, 59)))
    ch, z = ridge_profile(L, z0, z_end, knee_x, knee_z, dip)
    zd = z.copy()
    if diversion:   # the design route ran lower (or higher) by `diversion` m at the knee over a 300 m stretch
        c0, c1 = knee_x - 150, knee_x + 150
        k0, k1 = np.searchsorted(ch, c0), np.searchsorted(ch, c1)
        base = np.interp(ch, [c0, c1], [z[k0], z[k1]])
        for i in range(len(ch)):
            if c0 < ch[i] < c1:
                zd[i] = round(z[i] - diversion * math.sin(math.pi * (ch[i] - c0) / 300.0), 1)
    return dict(name=name, L=L, D=D, a=a, k_design=k_design, k_true=k_true or k_design, ch=ch, z=z, z_drawing=zd, knee_x=knee_x,
                diversion=diversion, datum=datum, throttle=throttle, BWL=BWL, TWL=TWL, ww=ww, header=z0, new=new,
                old=old, seed=seed, chamber=chamber_name, tag=tag)


def pump(n, QR, HR, I_pump, I_motor, eta=0.84):
    return dict(n=n, QR=QR, HR=HR, NR=1480.0, eta=eta, I=I_pump + I_motor, I_pump=I_pump, I_motor=I_motor,
                a0=1.30, a1=0.0, a2=-0.30, b0=0.45, b1=0.55, b2=0.0)


VESSEL = dict(n=1.2, R_out=10.0, R_in=25.0)

MAINS = [
    # the example: drawings as laid, design roughness right, transmitter on the crown tapping
    main_def("kestrel-lane", 5200.0, 0.6, 0.15e-3, None, 12.0, 0.65, 68.0, 5.0, 70.0, 75.0, 78.0, 14.0,
             pump(2, 0.30, 75.0, 6.5, 11.5), pump(1, 0.24, 72.0, 5.0, 7.0), seed=101),
    # hidden
    main_def("orchard-rise", 6400.0, 0.7, 0.15e-3, 0.40e-3, 8.0, 0.70, 61.0, 6.0, 63.0, 66.0, 69.5, 10.0,
             pump(2, 0.40, 72.0, 9.0, 15.0), pump(1, 0.32, 70.0, 7.0, 10.0), seed=202, diversion=4.5),
    main_def("mill-brook", 4300.0, 0.5, 0.15e-3, None, 20.0, 0.60, 71.0, 4.0, 72.0, 76.0, 79.0, 22.0,
             pump(2, 0.22, 70.0, 4.0, 8.0), pump(1, 0.18, 68.0, 3.5, 6.0), seed=303, datum=2.4),
    main_def("saddle-hill", 7100.0, 0.7, 0.15e-3, 0.05e-3, 15.0, 0.55, 80.0, 7.0, 82.0, 85.0, 88.0, 17.0,
             pump(3, 0.30, 85.0, 7.0, 13.0), pump(2, 0.28, 82.0, 6.0, 10.0), seed=404,
             throttle=dict(day0=4, day1=21, K=95.0)),
    main_def("fern-gully", 5600.0, 0.6, 0.15e-3, 0.37e-3, 11.0, 0.68, 66.0, 5.0, 67.0, 71.0, 74.0, 13.0,
             pump(2, 0.29, 74.0, 6.0, 11.0), pump(1, 0.23, 72.0, 5.0, 7.0), seed=505, diversion=-3.8, datum=1.8),
    main_def("lark-hollow", 4900.0, 0.5, 0.15e-3, 0.25e-3, 16.0, 0.62, 69.0, 5.0, 70.0, 74.0, 77.5, 18.0,
             pump(2, 0.21, 72.0, 4.0, 8.0), pump(1, 0.17, 70.0, 3.5, 6.0), seed=707, diversion=-3.5),
    main_def("cobb-ridge", 4800.0, 0.6, 0.15e-3, 0.13e-3, 9.0, 0.72, 63.0, 6.0, 64.0, 68.0, 71.0, 11.0,
             pump(2, 0.31, 72.0, 6.5, 11.5), pump(1, 0.25, 70.0, 5.0, 7.0), seed=606, diversion=4.0, datum=2.0,
             throttle=dict(day0=6, day1=22, K=120.0)),
]
BY = {m["name"]: m for m in MAINS}
EXAMPLE = "kestrel-lane"
HIDDEN = [m["name"] for m in MAINS if m["name"] != EXAMPLE]


def f_of(m, Ht=None, pumpset=None):
    """Colebrook friction factor of the steady flow (installed roughness), found with the flow it gives."""
    Ht = m["BWL"] if Ht is None else Ht
    f = colebrook(m["k_true"], m["D"], 1.5); A = math.pi * m["D"] ** 2 / 4
    for _ in range(8):
        P = dict(dt=0.02, sections=[dict(L=m["L"], D=m["D"], a=m["a"], f=f)], profile=(m["ch"], m["z"]), Hs=m["ww"],
                 Ht=Ht, pump=dict(pumpset or m["new"]))
        Q0 = moc.steady(P)[4]
        f = colebrook(m["k_true"], m["D"], max(Q0 / A, 0.05))
    return f


def case(m, Ht, pumpset=None, ves=None, dt=0.02):
    return dict(dt=dt, sections=[dict(L=m["L"], D=m["D"], a=m["a"], f=f_of(m, Ht, pumpset))], profile=(m["ch"], m["z"]),
                Hs=m["ww"], Ht=Ht, pump=dict(pumpset or m["new"]), vessel=ves)


def check(m, V, Vg, levels=None):
    levels = levels or (m["BWL"], 0.5 * (m["BWL"] + m["TWL"]), m["TWL"])
    worst = dict(pmin=1e9, pmax=-1e9, gas=0.0)
    for Ht in levels:
        r = moc.run(case(m, Ht, ves=dict(VESSEL, V=V, Vg0=Vg, zw=m["header"] + 1.0)), T=120.0)
        pc = r["pmin"] - m["D"] / 2
        worst["pmin"] = min(worst["pmin"], pc.min()); worst["pmax"] = max(worst["pmax"], r["pmax"].max())
        worst["gas"] = max(worst["gas"], r["Vgmax"] / V)
    ok = worst["pmin"] >= LIM["pmin"] and worst["pmax"] <= LIM["pmax"] and worst["gas"] <= LIM["gas"]
    return ok, worst


def response(m, Vg, levels=None):
    """Worst crown pressure, worst pressure and largest gas volume over the reservoir levels, for gas volume Vg."""
    levels = levels or (m["BWL"], 0.5 * (m["BWL"] + m["TWL"]), m["TWL"])
    pmin, pmax, gmax = 1e9, -1e9, 0.0
    for Ht in levels:
        r = moc.run(case(m, Ht, ves=dict(VESSEL, V=1e9, Vg0=Vg, zw=m["header"] + 1.0)), T=120.0)
        pmin = min(pmin, (r["pmin"] - m["D"] / 2).min()); pmax = max(pmax, r["pmax"].max()); gmax = max(gmax, r["Vgmax"])
    return pmin, pmax, gmax


def vmin(m):
    """Smallest vessel meeting MS-SV clause 3: the least gas volume that holds the crown pressure limit at every
    level, and the vessel whose 85 percent that gas expands to (the vessel volume does not enter the dynamics)."""
    lo, hi = 0.5, 20.0
    while response(m, hi)[0] < LIM["pmin"]: hi *= 2
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        if response(m, mid)[0] >= LIM["pmin"]: hi = mid
        else: lo = mid
    pmin, pmax, gmax = response(m, hi)
    assert pmax <= LIM["pmax"]
    return gmax / LIM["gas"], hi


def steady_old(m, npump, Ht, extra_K=0.0):
    """Steady state with the existing pumps (and an extra loss at the pump station outlet when throttled)."""
    P = case(m, Ht, pumpset=dict(m["old"], n=npump))
    if extra_K:     # friction at the throttled flow
        fq = P["sections"][0]["f"]; Am0 = math.pi * m["D"] ** 2 / 4
        head0, _, _ = moc.pump_fns(P["pump"])
        for _ in range(8):
            lc = fq * m["L"] / m["D"] / (2 * 9.81 * Am0 ** 2); lo, hi = 1e-5, 5.0
            for _ in range(80):
                Qt = 0.5 * (lo + hi)
                if m["ww"] + head0(1.0, Qt / npump) > Ht + (lc + extra_K) * Qt ** 2: lo = Qt
                else: hi = Qt
            fq = colebrook(m["k_true"], m["D"], max(0.5 * (lo + hi) / Am0, 0.05))
        P["sections"][0]["f"] = fq
    x, D, a, f, Q0, H = moc.steady(P)
    if extra_K:
        head, _, _ = moc.pump_fns(P["pump"])
        seg = np.diff(x); Am = math.pi * m["D"] ** 2 / 4
        lossc = np.sum(f[:-1] * seg / m["D"]) / (2 * 9.81 * Am ** 2)
        lo, hi = 1e-5, 5.0
        for _ in range(100):
            Q = 0.5 * (lo + hi)
            if m["ww"] + head(1.0, Q / npump) > Ht + (lossc + extra_K) * Q ** 2: lo = Q
            else: hi = Q
        Q0 = 0.5 * (lo + hi)
        Hmain0 = Ht + lossc * Q0 ** 2
        H = Hmain0 - np.concatenate([[0], np.cumsum(f[:-1] * seg / m["D"] * (Q0 / Am) ** 2 / (2 * 9.81))])
        return Q0, Hmain0 + extra_K * Q0 ** 2, np.interp(m["knee_x"], x, H)
    return Q0, H[0], np.interp(m["knee_x"], x, H)


def write_scada(m, out):
    rng = np.random.default_rng(m["seed"])
    t0 = np.datetime64("2026-09-01T00:00")
    rows = []; level = 0.5 * (m["BWL"] + m["TWL"])
    nmax = m["old"]["n"] + 1
    zc = np.interp(m["knee_x"], m["ch"], m["z"]) + m["D"] / 2
    for k in range(30 * 96):
        t = t0 + np.timedelta64(15 * k, "m"); hour = (k % 96) / 4; day = k // 96
        npump = 2 if (7 <= hour < 10 or 17 <= hour < 21) else 1
        npump = min(npump, nmax)
        if rng.random() < 0.02: npump = 0
        K = m["throttle"]["K"] if m["throttle"] and (np.datetime64(m["throttle"]["t0"].replace(" ", "T")) <= t <
                                                     np.datetime64(m["throttle"]["t1"].replace(" ", "T"))) else 0.0
        if npump:
            Q, Hps, Hk = steady_old(m, npump, level, K)
        else:
            Q, Hps, Hk = 0.0, level, level
        demand = 0.62 * m["old"]["QR"] * (1 + 0.35 * math.sin(2 * math.pi * (hour - 8) / 24))
        level = float(np.clip(level + (Q - demand) * 900 / 2200.0, m["BWL"], m["TWL"]))
        p_ps = (Hps - (m["header"] + 0.6)) / BAR
        p_k = (Hk - (zc - m["datum"])) / BAR
        rows.append([str(t).replace("T", " "), npump, "%.1f" % (1000 * Q * (1 + rng.normal(0, 0.004))),
                     "%.3f" % (p_ps + rng.normal(0, 0.008)), "%.3f" % (p_k + rng.normal(0, 0.008)),
                     "%.2f" % (level + rng.normal(0, 0.01))])
    with open(os.path.join(out, "scada.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "pumps_running", "FT201_flow_l_s", "PT201_pressure_bar", "%s_pressure_bar" % m["tag"],
                    "LT501_level_m"])
        w.writerows(rows)
