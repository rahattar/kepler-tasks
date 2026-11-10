"""Reference sizing program for MS-SV air vessels:

    python3 surge.py MAIN_DIR OUT_JSON

Reads one main's package, checks its records against each other before using them, and sizes the air vessel on the
pump station header by the method of characteristics (MS-SV clause 2). The checks:
- the elevation of the chamber transmitter's tapping from the static readings (pumps stopped: head = reservoir
  level), and from it the pipe crown, by where the transmitter sits (system description);
- the as-laid levels of a diverted stretch whose levels were not recorded: the chamber is the high point, so the
  stretch is taken through the crown found at the chamber, between the recorded levels at its ends;
- the Colebrook roughness of the main from the head loss between the chamber transmitter and the reservoir (downstream
  of anything at the pump station), over running periods outside any the maintenance log names as throttled.
Then the trip of all running sets at the bottom, middle and top water levels; the least gas volume that holds the
crown pressure limit (bisection), 2 percent above it; the vessel 3 percent above the volume the gas expands to at
85 percent.
"""
import csv, json, math, os, re, sys
import numpy as np
import pandas as pd
from scipy.optimize import brentq


G = 9.81
HB = 10.2      # atmospheric pressure head, m water


def build(sections, dt):
    """Each section gets an integer number of reaches at the common dt; its wave speed is adjusted to fit."""
    x, D, a, f = [], [], [], []
    xs = 0.0
    for s in sections:
        n = max(1, int(round(s["L"] / (s["a"] * dt))))
        for i in range(n):
            x.append(xs + i * s["L"] / n); D.append(s["D"]); a.append(s["L"] / (n * dt)); f.append(s["f"])
        xs += s["L"]
    x.append(xs); D.append(sections[-1]["D"]); a.append(a[-1]); f.append(f[-1])
    return np.array(x), np.array(D), np.array(a), np.array(f)


def pump_fns(pu):
    def head(alpha, q):
        v = q / pu["QR"]
        return pu["HR"] * (pu["a0"] * alpha ** 2 + pu["a1"] * alpha * v + pu["a2"] * v ** 2)
    def dhead_dq(alpha, q):
        return pu["HR"] * (pu["a1"] * alpha / pu["QR"] + 2 * pu["a2"] * q / pu["QR"] ** 2)
    def torque(alpha, q):
        v = q / pu["QR"]
        return pu["b0"] * alpha ** 2 + pu["b1"] * alpha * v + pu["b2"] * v ** 2
    return head, dhead_dq, torque


def steady(P):
    x, D, a, f = build(P["sections"], P["dt"])
    head, _, _ = pump_fns(P["pump"])
    npump = P["pump"]["n"]
    seg = np.diff(x); Dm = 0.5 * (D[:-1] + D[1:]); fm = 0.5 * (f[:-1] + f[1:]); Am = math.pi * Dm ** 2 / 4
    loss = lambda Q: np.sum(fm * seg / Dm * (Q / Am) ** 2 / (2 * G))
    lo, hi = 1e-5, 10.0
    for _ in range(100):
        Q = 0.5 * (lo + hi)
        if P["Hs"] + head(1.0, Q / npump) > P["Ht"] + loss(Q): lo = Q
        else: hi = Q
    Q0 = 0.5 * (lo + hi)
    H = np.empty(len(x)); H[0] = P["Hs"] + head(1.0, Q0 / npump)
    H[1:] = H[0] - np.cumsum(fm * seg / Dm * (Q0 / Am) ** 2 / (2 * G))
    return x, D, a, f, Q0, H


def run_moc(P, T=150.0, record=()):
    dt = P["dt"]
    x, D, a, f, Q0, H = steady(P)
    N = len(x) - 1
    A = math.pi * D ** 2 / 4
    B = a / (G * A)
    Rf = f * a * dt / (2 * G * D * A ** 2)
    zp = np.interp(x, P["profile"][0], P["profile"][1])
    pu = P["pump"]; npump = pu["n"]
    head, dhead, torque = pump_fns(pu)
    omegaR = pu["NR"] * 2 * math.pi / 60.0
    TR = 1000 * G * pu["QR"] * pu["HR"] / (pu["eta"] * omegaR)
    Q = np.full(N + 1, Q0)
    ves = P.get("vessel")
    if ves:
        Vg = ves["Vg0"]; Cg = (H[0] + HB - ves["zw"]) * Vg ** ves["n"]
    alpha, qp, nrv, qv_prev = 1.0, Q0 / npump, True, 0.0
    Hmin, Hmax = H.copy(), H.copy(); Vgmax = Vg if ves else 0.0
    rec = {k: [] for k in record}; ts = []
    for step in range(int(T / dt)):
        Hn = np.empty_like(H); Qn = np.empty_like(Q)
        CP = H[:-2] + B[1:-1] * Q[:-2] - Rf[1:-1] * Q[:-2] * np.abs(Q[:-2])
        CM = H[2:] - B[1:-1] * Q[2:] + Rf[1:-1] * Q[2:] * np.abs(Q[2:])
        Hn[1:-1] = 0.5 * (CP + CM); Qn[1:-1] = (CP - CM) / (2 * B[1:-1])
        CPd = H[-2] + B[-1] * Q[-2] - Rf[-1] * Q[-2] * abs(Q[-2])
        Hn[-1] = P["Ht"]; Qn[-1] = (CPd - P["Ht"]) / B[-1]
        CM0 = H[1] - B[0] * Q[1] + Rf[0] * Q[1] * abs(Q[1])
        if nrv:
            alpha = max(alpha - torque(alpha, qp) * TR / (pu["I"] * omegaR) * dt, 0.0)
        c2 = -pu["HR"] * pu["a2"] / pu["QR"] ** 2      # > 0; pump head = Hs + HR a0 alpha^2 - c2 qp^2 (a1 = 0)
        def qpump(qv):
            c0 = P["Hs"] + pu["HR"] * pu["a0"] * alpha ** 2 - CM0 - B[0] * qv
            if c0 <= 0: return 0.0
            bn = B[0] * npump
            return (-bn + math.sqrt(bn * bn + 4 * c2 * c0)) / (2 * c2)
        def g(qv, with_pump):
            qpp = qpump(qv) if with_pump else 0.0
            H0 = CM0 + B[0] * (npump * qpp + qv)
            Vn = Vg + 0.5 * dt * (qv + qv_prev)
            if Vn <= 1e-9: return 1e9, qpp
            Rv = ves["R_out"] if qv >= 0 else ves["R_in"]
            return (Cg / Vn ** ves["n"] - HB + ves["zw"]) - H0 - Rv * qv * abs(qv), qpp
        def solve(with_pump):
            # g is strictly decreasing in the vessel outflow: bracket around the last value, then Brent
            w = 0.05
            lo, hi = qv_prev - w, qv_prev + w
            while g(lo, with_pump)[0] < 0: lo -= w; w *= 2
            w = 0.05
            while g(hi, with_pump)[0] > 0: hi += w; w *= 2
            return brentq(lambda q: g(q, with_pump)[0], lo, hi, xtol=1e-12, rtol=1e-12)
        if ves:
            qv = solve(nrv)
            qp = qpump(qv) if nrv else 0.0
            if nrv and qp <= 0.0:
                nrv = False; qp = 0.0; qv = solve(False)
            Vg = Vg + 0.5 * dt * (qv + qv_prev); qv_prev = qv; Vgmax = max(Vgmax, Vg)
        else:
            qv = 0.0
            qp = qpump(0.0) if nrv else 0.0
            if nrv and qp <= 0.0: nrv = False; qp = 0.0
        Hn[0] = CM0 + B[0] * (npump * qp + qv); Qn[0] = npump * qp + qv
        H, Q = Hn, Qn
        np.minimum(Hmin, H, out=Hmin); np.maximum(Hmax, H, out=Hmax)
        if record:
            for k in record: rec[k].append(H[k])
            ts.append((step + 1) * dt)
    return dict(x=x, z=zp, Q0=Q0, Hss=None, Hmin=Hmin, Hmax=Hmax, pmin=Hmin - zp, pmax=Hmax - zp, Vgmax=Vgmax,
                rec={k: np.array(v) for k, v in rec.items()}, t=np.array(ts))


BAR = 10.197      # m of water per bar
PMIN, PMAX, GASMAX = -3.0, 160.0, 0.85


def parse(d, skip=()):
    t = open(os.path.join(d, "system_description.md")).read()
    S = {}
    S["L"] = float(re.search(r"([\d,]+) m from PS", t).group(1).replace(",", ""))
    S["D"] = float(re.search(r"internal diameter (\d+) mm", t).group(1)) / 1000.0
    S["a"] = float(re.search(r"Wave speed ([\d,]+) m/s", t).group(1).replace(",", ""))
    S["k"] = float(re.search(r"roughness ([\d.]+) mm", t).group(1)) / 1000.0
    rows = re.findall(r"^\| ([\d,]+) \| (-?[\d.]+) \|$", t, re.M)
    S["ch"] = np.array([float(a.replace(",", "")) for a, b in rows]); S["z"] = np.array([float(b) for a, b in rows])
    S["ww"] = float(re.search(r"Wet well water level ([\d.]+) m AOD", t).group(1))
    S["header"] = float(re.search(r"Header centreline ([\d.]+) m AOD", t).group(1))
    S["pt201"] = float(re.search(r"Pressure transmitter PT201 on the header, ([\d.]+) m AOD", t).group(1))
    S["BWL"] = float(re.search(r"bottom water level ([\d.]+) m AOD", t).group(1))
    S["TWL"] = float(re.search(r"top water level ([\d.]+) m AOD", t).group(1))
    m = re.search(r"Chainage ([\d,]+) to ([\d,]+) m was diverted", t)
    S["div"] = (float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))) if m and "div" not in skip else None
    m = re.search(r"chamber \S+ at chainage ([\d,]+) m[^.]*\. Pressure transmitter (\w+)", t)
    S["kx"], S["tag"] = float(m.group(1).replace(",", "")), m.group(2)
    m = re.search(r"%s[^.]*?([\d.]+) m below the crown" % S["tag"], t)
    S["datum"] = float(m.group(1)) if m and "datum" not in skip else 0.0
    p = open(os.path.join(d, "pump_datasheets.md")).read()
    S["n"] = int(re.search(r"(\w+) sets running together", t).group(1).replace("two", "2").replace("three", "3")
                 .replace("four", "4")) if re.search(r"(\w+) sets running together", t) else 2
    QR, HR = re.search(r"Rated point at 1480 rpm: ([\d.]+) L/s at ([\d.]+) m", p).groups()
    S["pump"] = dict(QR=float(QR) / 1000.0, HR=float(HR), eta=float(re.search(r"efficiency (\d+) percent", p).group(1)) / 100,
                     I=sum(float(x) for x in re.findall(r"([\d.]+) kg m2", p)), NR=1480.0)
    S["throttle"] = []
    for r in csv.DictReader(open(os.path.join(d, "records", "maintenance_log.csv"))):
        m = re.search(r"throttled.*?until (\d{4}-\d\d-\d\d \d\d:\d\d)", r["description"])
        if m and "throttle" not in skip:
            S["throttle"].append((pd.Timestamp(r["date_local"]), pd.Timestamp(m.group(1))))
    return S


def calibrate(d, S, skip=()):
    s = pd.read_csv(os.path.join(d, "scada.csv"), parse_dates=["timestamp"])
    pk = s["%s_pressure_bar" % S["tag"]] * BAR
    off = s["pumps_running"] == 0
    z_tap = float(np.median(s["LT501_level_m"][off] - pk[off]))       # static: head at the tapping = reservoir level
    z_crown = z_tap + S["datum"]
    run = (s["pumps_running"] > 0) & (s["FT201_flow_l_s"] > 50)
    for a, b in S["throttle"]:
        run &= ~((s["timestamp"] >= a) & (s["timestamp"] < b))
    A = math.pi * S["D"] ** 2 / 4
    if "friction" in skip:
        k = S["k"]
    else:
        if "segment" in skip:    # whole line from PT201, every running period
            r2 = (s["pumps_running"] > 0) & (s["FT201_flow_l_s"] > 50)
            Q = s["FT201_flow_l_s"][r2] / 1000.0
            dh = s["PT201_pressure_bar"][r2] * BAR + S["pt201"] - s["LT501_level_m"][r2]; Lseg = S["L"]
        else:
            Q = s["FT201_flow_l_s"][run] / 1000.0
            dh = (pk[run] + z_tap) - s["LT501_level_m"][run]; Lseg = S["L"] - S["kx"]
        v = (Q / A).values; fi = dh.values / (Lseg / S["D"] * v ** 2 / (2 * G))
        k = float(np.median([rough(fx, S["D"], vx) for fx, vx in zip(fi, v)]))
    z = S["z"].copy()
    if S["div"] is not None and S["div"][0] < S["kx"] < S["div"][1]:
        c0, c1 = S["div"]
        z0, z1 = np.interp(c0, S["ch"], S["z"]), np.interp(c1, S["ch"], S["z"])
        zc = z_crown - S["D"] / 2
        for i, c in enumerate(S["ch"]):
            if c0 < c < c1:
                z[i] = np.interp(c, [c0, S["kx"], c1], [z0, zc, z1])
        if not np.any(np.isclose(S["ch"], S["kx"])):
            S["ch"] = np.append(S["ch"], S["kx"]); z = np.append(z, zc); o = np.argsort(S["ch"]); S["ch"], z = S["ch"][o], z[o]
    return k, z


def rough(f, D, v):
    """Roughness for which Colebrook gives f at velocity v."""
    lo, hi = 1e-8, 2e-2
    for _ in range(60):
        k = (lo * hi) ** 0.5
        if colebrook(k, D, v) < f: lo = k
        else: hi = k
    return (lo * hi) ** 0.5


def colebrook(k, D, v=1.6):
    Re = v * D / 1e-6; f = 0.02
    for _ in range(60): f = (-2 * math.log10(k / (3.7 * D) + 2.51 / (Re * math.sqrt(f)))) ** -2
    return f


def assess(d, skip=()):
    """The design for one main. `skip` names checks to leave out (for authoring/evidence/route_study.py only): div,
    datum, throttle, friction (design roughness), segment (roughness from PT201 over every running period), levels
    (middle reservoir level only)."""
    S = parse(d, skip)
    k, z = calibrate(d, S, skip)
    pu = dict(S["pump"], n=S["n"], a0=1.30, a1=0.0, a2=-0.30, b0=0.45, b1=0.55, b2=0.0)
    ves = dict(n=1.2, R_out=10.0, R_in=25.0, zw=S["header"] + 1.0)
    levels = (S["BWL"], 0.5 * (S["BWL"] + S["TWL"]), S["TWL"])
    if "levels" in skip: levels = (0.5 * (S["BWL"] + S["TWL"]),)
    fsteady = {}
    A = math.pi * S["D"] ** 2 / 4
    for Ht in levels:       # Colebrook friction factor of the new duty's steady flow at this reservoir level
        f = colebrook(k, S["D"], 1.5)
        for _ in range(8):
            P = dict(dt=0.02, sections=[dict(L=S["L"], D=S["D"], a=S["a"], f=f)], profile=(S["ch"], z), Hs=S["ww"], Ht=Ht, pump=pu)
            f = colebrook(k, S["D"], steady(P)[4] / A)
        fsteady[Ht] = f
    def run(Vg):
        worst = (1e9, 0.0)
        for Ht in levels:
            f = fsteady[Ht]
            P = dict(dt=0.02, sections=[dict(L=S["L"], D=S["D"], a=S["a"], f=f)], profile=(S["ch"], z), Hs=S["ww"], Ht=Ht,
                     pump=pu, vessel=dict(ves, V=1e6, Vg0=Vg))
            r = run_moc(P, T=120.0)
            worst = (min(worst[0], (r["pmin"] - S["D"] / 2).min()), max(worst[1], r["Vgmax"]))
        return worst
    lo, hi = 0.5, 400.0
    while run(hi)[0] < PMIN: hi *= 2
    for _ in range(14):
        m = (lo * hi) ** 0.5
        if run(m)[0] >= PMIN: hi = m
        else: lo = m
    Vg = hi * 1.02
    V = run(Vg)[1] / GASMAX * 1.03
    return dict(vessel_volume_m3=round(V, 2), gas_volume_m3=round(Vg, 2))


def main(pkg, out):
    with open(out, "w") as f:
        json.dump(assess(pkg), f)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
