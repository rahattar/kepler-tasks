"""Second, independent MS-SV sizing program (method-spread evidence); shares no code with solution/surge.py.

    python3 authoring/evidence/independent.py MAIN_DIR OUT_JSON

Differs from the reference wherever MS-SV leaves the method open:
- MOC on a fixed 20 m reach grid (the time step follows), pump rundown by a two-stage Runge-Kutta step, and the
  vessel's gas law solved for the gas volume by Newton's method;
- the tapping elevation and the downstream friction fitted together by least squares on the running periods (the
  intercept of the head-loss line), not from the static readings;
- the roughness from the whole main (PT201 to the reservoir) outside the throttled periods the log names;
- a diverted stretch taken as the drawing's shape shifted to the crown found at the chamber, tapering to zero at the
  ends of the stretch and never above the chamber;
- five reservoir levels; the least gas found by a secant search, 3 percent above it; the vessel 4 percent above the
  volume the gas expands to at 85 percent.
"""
import json, math, re, sys
import numpy as np
import pandas as pd

g = 9.81; Hatm = 10.2; mbar = 10.197; nu = 1.0e-6


def txt(d, f):
    return open("%s/%s" % (d, f)).read()


def num(s):
    return float(s.replace(",", ""))


def read(d):
    t = txt(d, "system_description.md"); p = txt(d, "pump_datasheets.md")
    m = {}
    m["L"] = num(re.search(r"; ([\d,]+) m from PS-2", t).group(1))
    m["D"] = num(re.search(r"internal diameter ([\d,]+) mm", t).group(1)) / 1e3
    m["a"] = num(re.search(r"Wave speed ([\d,]+) m/s", t).group(1))
    m["kd"] = num(re.search(r"roughness ([\d.]+) mm", t).group(1)) / 1e3
    tab = re.findall(r"^\| ([\d,]+) \| (-?[\d.]+) \|$", t, re.M)
    m["x"] = np.array([num(a) for a, _ in tab]); m["z"] = np.array([float(b) for _, b in tab])
    m["ww"] = float(re.search(r"Wet well water level ([\d.]+)", t).group(1))
    m["hdr"] = float(re.search(r"Header centreline ([\d.]+)", t).group(1))
    m["zpt"] = float(re.search(r"PT201 on the header, ([\d.]+)", t).group(1))
    m["lv"] = (float(re.search(r"bottom water level ([\d.]+)", t).group(1)), float(re.search(r"top water level ([\d.]+)", t).group(1)))
    g1 = re.search(r"chamber (\S+) at chainage ([\d,]+) m", t); m["xc"] = num(g1.group(2))
    m["tag"] = re.search(r"Pressure transmitter (PT\d+) \(installed", t).group(1)
    g2 = re.search(r"([\d.]+) m below the crown tapping", t); m["below"] = float(g2.group(1)) if g2 else 0.0
    g3 = re.search(r"Chainage ([\d,]+) to ([\d,]+) m was diverted", t); m["div"] = (num(g3.group(1)), num(g3.group(2))) if g3 else None
    words = dict(one=1, two=2, three=3, four=4)
    m["np"] = words[re.search(r"(\w+) sets running together", t).group(1)]
    q, h = re.search(r"([\d.]+) L/s at ([\d.]+) m; efficiency (\d+) percent", p).groups()[:2]
    m["Q1"], m["H1"] = float(q) / 1e3, float(h)
    m["eff"] = float(re.search(r"efficiency (\d+) percent", p).group(1)) / 100
    m["J"] = sum(float(v) for v in re.findall(r"([\d.]+) kg m2", p))
    log = pd.read_csv("%s/records/maintenance_log.csv" % d)
    m["shut"] = []
    for _, r in log.iterrows():
        u = re.search(r"until (\d{4}-\d\d-\d\d \d\d:\d\d)", str(r["description"]))
        if "throttled" in str(r["description"]) and u:
            m["shut"].append((pd.Timestamp(r["date_local"]), pd.Timestamp(u.group(1))))
    return m


def lam(k, D, v):
    """Colebrook-White friction factor by fixed-point iteration on 1/sqrt(lambda)."""
    Re = max(v, 0.02) * D / nu; y = 7.0
    for _ in range(80):
        y = -2 * math.log10(k / (3.71 * D) + 2.51 * y / Re)
    return 1 / y ** 2


def k_of(lmb, D, v):
    lo, hi = math.log(1e-8), math.log(3e-2)
    for _ in range(70):
        c = 0.5 * (lo + hi)
        if lam(math.exp(c), D, v) < lmb: lo = c
        else: hi = c
    return math.exp(0.5 * (lo + hi))


def calibrate(d, m):
    s = pd.read_csv("%s/scada.csv" % d, parse_dates=["timestamp"])
    A = math.pi * m["D"] ** 2 / 4
    ok = (s["pumps_running"] > 0) & (s["FT201_flow_l_s"] > 50)
    for a, b in m["shut"]:
        ok &= ~((s["timestamp"] >= a) & (s["timestamp"] < b))
    v = s["FT201_flow_l_s"][ok].values / 1e3 / A
    hres = s["LT501_level_m"][ok].values
    # tapping elevation and downstream loss coefficient: p_k - H_res = -z_tap + c v^2 (least squares)
    pk = s["%s_pressure_bar" % m["tag"]][ok].values * mbar
    X = np.c_[np.ones(len(v)), v ** 2]
    (c0, c1), *_ = np.linalg.lstsq(X, pk - hres, rcond=None)
    z_tap = -c0
    # roughness of the whole main from the header transmitter
    dh = s["PT201_pressure_bar"][ok].values * mbar + m["zpt"] - hres
    lm = dh / (m["L"] / m["D"] * v ** 2 / (2 * g))
    k = float(np.median([k_of(l, m["D"], vv) for l, vv in zip(lm, v)]))
    z = m["z"].copy(); x = m["x"].copy()
    if m["div"] and m["div"][0] < m["xc"] < m["div"][1]:
        zc = z_tap + m["below"] - m["D"] / 2
        if not np.any(np.isclose(x, m["xc"])):
            x = np.append(x, m["xc"]); z = np.append(z, np.interp(m["xc"], m["x"], m["z"])); o = np.argsort(x); x, z = x[o], z[o]
        dz = zc - float(np.interp(m["xc"], x, z))
        c0d, c1d = m["div"]
        for i in range(len(x)):
            if c0d < x[i] < c1d:
                w = 1 - abs(x[i] - m["xc"]) / (c1d - m["xc"] if x[i] > m["xc"] else m["xc"] - c0d)
                z[i] = min(z[i] + dz * w, zc)
    return k, x, z


def transient(m, k, x, z, Hres, gas0, T=120.0):
    """Lowest crown pressure, highest pressure and largest gas volume after the trip of all running sets."""
    D, A = m["D"], math.pi * m["D"] ** 2 / 4
    N = int(round(m["L"] / 20.0)); dx = m["L"] / N; dt = dx / m["a"]
    Bc = m["a"] / (g * A)
    # steady state with the friction of the steady flow
    lmb = lam(k, D, 1.5)
    for _ in range(10):
        r = lmb * m["L"] / (D * 2 * g * A ** 2)
        c2 = 0.30 * m["H1"] / (m["np"] * m["Q1"]) ** 2
        Q0 = math.sqrt(max(m["ww"] + 1.30 * m["H1"] - Hres, 0) / (r + c2))
        lmb = lam(k, D, Q0 / A)
    Rc = lmb * dx / (2 * g * D * A ** 2)
    xs = np.linspace(0, m["L"], N + 1); zs = np.interp(xs, x, z)
    zcrit = np.interp(np.union1d(xs, x), x, z)
    H = m["ww"] + 1.30 * m["H1"] - c2 * Q0 ** 2 - r * Q0 ** 2 * xs / m["L"]
    Q = np.full(N + 1, Q0)
    w0 = 1480 * math.pi / 30; Tq = 1000 * g * m["Q1"] * m["H1"] / (m["eff"] * w0)
    al = 1.0; qp = Q0 / m["np"]; nrv = True
    zw = m["hdr"] + 1.0; Kgas = (H[0] + Hatm - zw) * gas0 ** 1.2; Vg = gas0; qv = 0.0
    lowest = H - zs; highest = H - zs; vmax = gas0
    tor = lambda a, q: 0.45 * a * a + 0.55 * a * q / m["Q1"]
    for _ in range(int(T / dt)):
        Cp = H[:-2] + Bc * Q[:-2] - Rc * Q[:-2] * np.abs(Q[:-2])
        Cm = H[2:] - Bc * Q[2:] + Rc * Q[2:] * np.abs(Q[2:])
        Hn = np.empty_like(H); Qn = np.empty_like(Q)
        Hn[1:-1] = (Cp + Cm) / 2; Qn[1:-1] = (Cp - Cm) / (2 * Bc)
        Hn[-1] = Hres; Qn[-1] = (H[-2] + Bc * Q[-2] - Rc * Q[-2] * abs(Q[-2]) - Hres) / Bc
        cm0 = H[1] - Bc * Q[1] + Rc * Q[1] * abs(Q[1])
        if nrv:   # two-stage Runge-Kutta for the speed
            k1 = -tor(al, qp) * Tq / (m["J"] * w0)
            k2 = -tor(max(al + dt * k1, 0), qp) * Tq / (m["J"] * w0)
            al = max(al + 0.5 * dt * (k1 + k2), 0.0)
        cq = 0.30 * m["H1"] / m["Q1"] ** 2
        def pumpq(qvv):
            c = m["ww"] + 1.30 * m["H1"] * al * al - cm0 - Bc * qvv
            if not nrv or c <= 0: return 0.0
            b = Bc * m["np"]
            return (-b + math.sqrt(b * b + 4 * cq * c)) / (2 * cq)
        # unknown: new gas volume V; outflow qv = 2 (V - Vg)/dt - qv_old
        def resid(V):
            q = 2 * (V - Vg) / dt - qv
            loss = (10.0 if q >= 0 else 25.0) * q * abs(q)
            Hn0 = cm0 + Bc * (m["np"] * pumpq(q) + q)
            return Kgas / V ** 1.2 - Hatm + zw - loss - Hn0
        V = Vg
        for _ in range(60):
            f0 = resid(V); h = 1e-6 * max(V, 1.0); f1 = resid(V + h)
            step = -f0 * h / (f1 - f0)
            V = max(V + step, 1e-6)
            if abs(step) < 1e-11: break
        qn = 2 * (V - Vg) / dt - qv
        qpn = pumpq(qn)
        if nrv and qpn <= 0: nrv = False; qpn = 0.0
        Vg, qv = V, qn
        Hn[0] = cm0 + Bc * (m["np"] * qpn + qv); Qn[0] = m["np"] * qpn + qv
        qp = qpn
        H, Q = Hn, Qn
        lowest = np.minimum(lowest, H - zs); highest = np.maximum(highest, H - zs); vmax = max(vmax, Vg)
    # crown pressure at every node and every profile vertex
    Hl = lowest + zs
    crit = (np.interp(np.union1d(xs, x), xs, Hl) - zcrit - D / 2).min()
    return crit, highest.max(), vmax


def size(d):
    m = read(d)
    k, x, z = calibrate(d, m)
    levels = np.linspace(m["lv"][0], m["lv"][1], 5)
    def worst(gas):
        res = [transient(m, k, x, z, h, gas) for h in levels]
        return min(r[0] for r in res), max(r[1] for r in res), max(r[2] for r in res)
    # secant search for the least gas holding -3 m, bracketed
    a, b = 2.0, 40.0
    while worst(b)[0] < -3.0: b *= 2
    fa, fb = worst(a)[0] + 3.0, worst(b)[0] + 3.0
    for _ in range(40):
        c = b - fb * (b - a) / (fb - fa) if fb != fa else 0.5 * (a + b)
        if not (min(a, b) < c < max(a, b)): c = 0.5 * (a + b)
        fc = worst(c)[0] + 3.0
        if fc >= 0: b, fb = c, fc
        else: a, fa = c, fc
        if abs(b - a) < 1e-3 * b: break
    gas = 1.03 * b
    lo, hi, vmax = worst(gas)
    return {"vessel_volume_m3": round(1.04 * vmax / 0.85, 2), "gas_volume_m3": round(gas, 2)}


if __name__ == "__main__":
    json.dump(size(sys.argv[1]), open(sys.argv[2], "w"))
