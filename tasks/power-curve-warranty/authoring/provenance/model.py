"""Sealed model of the owner's wind farms: turbine models and warranted curves, the farm-period packages (layout,
climate, true performance, and the record faults each package carries), the record generator and the truth.

The truth for a turbine is PP-12 applied to its true power curve: the annual energy ratio of the true curve, on the
procedure's grid and Rayleigh 7.5 m/s distribution, over the warranted curve of its model."""
import csv, math, os
import numpy as np

RHO0 = 1.225
G0, R0, RW = 9.80665, 287.05, 461.5

# ---------------------------------------------------------------- turbine models (supply agreement, appendix C)
MODELS = {"HW116-2.5": dict(D=116.0, hub=90.0, rated=2500.0, cp=0.47),
          "HW120-2.5": dict(D=120.0, hub=90.0, rated=2500.0, cp=0.47),
          "HW103-2.0": dict(D=103.0, hub=80.0, rated=2000.0, cp=0.46)}
GRID = np.arange(3.0, 25.01, 0.5)


def warranted(model):
    m = MODELS[model]
    v = GRID
    A = math.pi * m["D"] ** 2 / 4.0
    cp = m["cp"] * np.exp(-((v - 7.5) / 7.0) ** 2) ** 0.35 * np.clip((v - 2.6) / 2.0, 0.0, 1.0) ** 0.6
    p = 0.5 * RHO0 * A * cp * v ** 3 / 1000.0 * 0.95
    p = m["rated"] * np.tanh(p / m["rated"] * 1.02) / np.tanh(1.02)
    p = np.minimum(p, m["rated"])
    return v, np.round(p, 1)


def true_power(model, perf, vn):
    v, p = warranted(model)
    rated = MODELS[model]["rated"]
    base = np.interp(vn, v, p, left=0.0, right=0.0)
    short = (1.0 - perf) * base * np.clip((rated - base) / (0.12 * rated), 0.0, 1.0)
    out = base - short
    return np.where((vn < 3.0) | (vn > 25.0), 0.0, out)


def aep(v, p, vave=7.5):
    F = lambda x: 1.0 - np.exp(-math.pi / 4.0 * (x / vave) ** 2)
    return 8760.0 * float(np.sum((F(v[1:]) - F(v[:-1])) * 0.5 * (p[1:] + p[:-1]))) / 1000.0


def truth(pk):
    """True annual energy ratio and claim of each turbine, from its true power curve against the warranted curve of
    the model it runs as in the period (a rotor replaced at the start of the period counts as the new model)."""
    out = {}
    rot = {r["turbine"]: r for r in pk["faults"].get("rotor", [])}
    for t, model in pk["models"].items():
        if t in rot:
            model = rot[t]["model"]
        v, pw = warranted(model)
        r = aep(GRID, true_power(model, pk["perf"][t], GRID)) / aep(v, pw)
        out[t] = (round(r, 4), "yes" if r < 0.97 else "no")
    return out


# ---------------------------------------------------------------- layouts
def layout(n_front, n_back, bearing, spacing_d, back_d, stagger_d, D=116.0):
    """Front row from (0, 0) along `bearing` (deg) at spacing_d D; the back row back_d D to the left of the row
    (bearing - 90, downwind of the front row), staggered by stagger_d D along the row. Turbines numbered front row first."""
    b = math.radians(bearing); bn = math.radians(bearing - 90.0)
    ux, uy = math.sin(b), math.cos(b); nx, ny = math.sin(bn), math.cos(bn)
    xy = []
    for k in range(n_front):
        xy.append((k * spacing_d * D * ux, k * spacing_d * D * uy))
    for k in range(n_back):
        s = (k * spacing_d + stagger_d) * D
        xy.append((s * ux + back_d * D * nx, s * uy + back_d * D * ny))
    return xy


# ---------------------------------------------------------------- packages
def _pk(name, farm, start, days, elev, utc, n_front, n_back, bearing, spacing, back, stagger, models, perf, rose, A,
        T0, Tslope, faults, sound=None, ice=None, ntf_old=(1.080, 0.25), seed=1, prevailing=225.0, period=None):
    turbines = ["T%02d" % (i + 1) for i in range(n_front + n_back)]
    D = MODELS[models[0]]["D"]
    xy0 = layout(n_front, n_back, bearing, spacing, back, stagger, D)
    # the mast stands 2.5 rotor diameters upwind of T01 in the prevailing direction
    pr = math.radians(prevailing)
    mx, my = xy0[0][0] + 2.5 * D * math.sin(pr), xy0[0][1] + 2.5 * D * math.cos(pr)
    xy = {t: (round(x - mx, 0), round(y - my, 0)) for t, (x, y) in zip(turbines, xy0)}
    return dict(name=name, farm=farm, start=start, days=days, elev=elev, utc=utc, turbines=turbines, xy=xy,
                models=dict(zip(turbines, models)), perf=dict(zip(turbines, perf)), rose=rose, A=A, T0=T0, Tslope=Tslope,
                faults=faults, sound=sound or {}, ice=ice or [], ntf_old=ntf_old, seed=seed, prevailing=prevailing,
                cal_sector=(round(prevailing - 35), round(prevailing + 35)), period=period)


ROSE_SW = ([225.0, 305.0, 65.0, 160.0], [0.50, 0.20, 0.18, 0.12])
ROSE_W = ([265.0, 330.0, 120.0, 200.0], [0.45, 0.22, 0.15, 0.18])
ROSE_S = ([185.0, 250.0, 20.0, 110.0], [0.48, 0.20, 0.17, 0.15])

PACKAGES = [
    # the example given with the task: sound mode, a second rotor model, logged curtailments; no record faults
    _pk("ridgeback-2026h1", "Ridgeback Wind", "2026-01-01", 181, 640.0, -6, 5, 5, 135.0, 4.0, 7.0, 2.0,
        ["HW116-2.5"] * 8 + ["HW120-2.5"] * 2,
        [1.005, 0.995, 1.000, 0.990, 0.885, 1.000, 0.900, 0.995, 0.990, 0.895], ROSE_SW, 8.3, -6.0, 26.0,
        faults={}, sound={"T08": 1800.0, "T09": 1800.0, "T10": 1800.0}, ice=["T01", "T02", "T03", "T04", "T05"], seed=2611),
    # hidden
    _pk("ridgeback-2026h2", "Ridgeback Wind", "2026-07-01", 184, 640.0, -6, 5, 5, 135.0, 4.0, 7.0, 2.0,
        ["HW116-2.5"] * 8 + ["HW120-2.5"] * 2,
        [1.000, 0.885, 0.990, 0.995, 1.000, 0.895, 0.995, 0.990, 0.880, 1.005], ROSE_SW, 8.0, 22.0, -26.0,
        faults=dict(fw=dict(dates={"T%02d" % i: "2026-08-%02d 10:%02d" % (3 + i, 10 + i) for i in range(1, 11)}, logged=True),
                    scale=dict(turbine="T03", factor=0.955, at="2026-10-05 13:20", logged=False),
                    mclock=dict(at="2026-08-26 15:40", hours=6)),
        sound={"T08": 1800.0, "T09": 1800.0, "T10": 1800.0}, ice=["T01", "T02", "T03", "T04", "T05"], seed=3102),
    _pk("cedar-flats-2026h1", "Cedar Flats Wind", "2026-01-01", 181, 1450.0, -7, 8, 0, 160.0, 4.5, 0.0, 0.0,
        ["HW116-2.5"] * 8, [0.995, 1.005, 0.885, 1.000, 0.890, 0.995, 1.000, 0.895], ROSE_W, 8.6, -9.0, 24.0,
        faults=dict(qnh=dict(start="2026-02-25 08:00", end="2026-07-01 00:00"), utc=dict(turbine="T06"),
                    rotor=[dict(turbine="T05", model="HW120-2.5", at="2026-01-01 09:40"),
                           dict(turbine="T07", model="HW120-2.5", at="2026-01-01 14:10")]),
        sound={"T06": 1800.0, "T07": 1800.0, "T08": 1800.0}, ice=[], seed=4203, prevailing=265.0),
    _pk("hollins-ridge-2026h1", "Hollins Ridge Wind", "2026-01-01", 181, 380.0, -5, 6, 6, 120.0, 4.0, 7.5, 2.0,
        ["HW116-2.5"] * 12, [1.000, 0.995, 0.990, 0.885, 1.000, 0.995, 1.000, 1.000, 0.995, 0.995, 0.900, 0.990],
        ROSE_S, 7.9, -4.0, 25.0,
        faults=dict(fw=dict(dates={"T%02d" % i: "2026-04-%02d 09:%02d" % (6 + i, 20 + i) for i in range(1, 13)}, logged=False),
                    yaw=dict(turbine="T09", offset=-40.0, at="2026-02-11 10:30", logged=False),
                    vane=dict(at="2026-03-03 11:20", offset=28.0)),
        ice=["T01", "T02", "T03", "T04", "T05", "T06"], seed=5304, prevailing=185.0),
    _pk("tallow-creek-2026h1", "Tallow Creek Wind", "2026-01-01", 181, 910.0, -6, 9, 0, 150.0, 4.2, 0.0, 0.0,
        ["HW103-2.0"] * 9, [0.995, 0.880, 1.000, 1.005, 0.995, 1.000, 0.990, 0.890, 1.000], ROSE_SW, 8.1, -7.0, 25.0,
        faults=dict(scale=dict(turbine="T05", factor=0.950, at="2026-03-02 11:00", logged=True),
                    qnh=dict(start="2026-05-10 10:00", end="2026-07-01 00:00"),
                    fw=dict(dates={"T%02d" % i: "2025-12-%02d 10:%02d" % (1 + i, 10 + i) for i in range(1, 10)}, logged=False)),
        ice=[], seed=6405, ntf_old=(1.065, 0.30)),
    _pk("north-branch-2025h2", "North Branch Wind", "2025-07-01", 184, 520.0, -6, 5, 5, 140.0, 4.0, 7.0, 2.0,
        ["HW116-2.5"] * 10, [0.995, 1.000, 0.890, 1.005, 0.995, 1.000, 0.990, 0.995, 0.885, 1.000], ROSE_SW, 8.2, 21.0, -24.0,
        faults=dict(fw=dict(dates={"T%02d" % i: "2025-09-%02d 10:%02d" % (8 + i, 5 + i) for i in range(1, 11)}, logged=True),
                    cup=dict(at="2025-09-24 12:40", slope=0.09980, offset=0.3050),
                    utc=dict(turbine="T04")),
        sound={"T04": 1800.0, "T05": 1800.0}, ice=["T01", "T02", "T03", "T04", "T05"], seed=7506),
    _pk("pike-hollow-2026h1", "Pike Hollow Wind", "2026-01-01", 181, 760.0, -6, 5, 5, 145.0, 4.0, 7.0, 2.0,
        ["HW116-2.5"] * 6 + ["HW120-2.5"] * 4, [1.000, 0.995, 1.000, 0.885, 1.005, 0.995, 1.000, 0.990, 0.895, 1.000],
        ROSE_SW, 8.4, -5.0, 25.0,
        faults=dict(yaw=dict(turbine="T07", offset=-38.0, at="2026-02-20 14:00", logged=True),
                    drift=dict(start="2026-01-22 13:10", mag=0.08),
                    fw=dict(dates={"T%02d" % i: "2026-03-%02d 10:%02d" % (8 + i, 10 + i) for i in range(1, 11)}, logged=False)),
        sound={"T06": 1800.0, "T07": 1800.0}, ice=["T01", "T02", "T03"], seed=8607),
]
EXAMPLE = PACKAGES[0]["name"]
HIDDEN = [p["name"] for p in PACKAGES[1:]]
BY_NAME = {p["name"]: p for p in PACKAGES}
CERT = (0.04580, 0.2310)          # M1 cup certificate at the start of each period (every farm's mast uses the same type)
FW_BIAS = 1.005


# ---------------------------------------------------------------- generator
def _ar1(rng, n, phi, sd):
    e = rng.standard_normal(n) * sd
    z = np.empty(n); z[0] = e[0] / max(math.sqrt(1 - phi * phi), 1e-6) * 0.0
    for i in range(1, n): z[i] = phi * z[i - 1] + e[i]
    return z


def _weather(pk, rng):
    n = pk["days"] * 144
    t0 = np.datetime64(pk["start"] + "T00:00")
    ts = t0 + np.arange(n) * np.timedelta64(10, "m")
    hour = (np.arange(n) % 144) / 6.0; day = np.arange(n) / 144.0
    z = _ar1(rng, n, 0.985, math.sqrt(1 - 0.985 ** 2))
    from math import erf
    u = np.clip(0.5 * (1 + np.vectorize(erf)(z / math.sqrt(2))), 1e-6, 1 - 1e-6)
    A = pk["A"] * (1 + 0.05 * np.cos(2 * math.pi * (hour - 3) / 24))
    U = A * (-np.log(1 - u)) ** 0.5
    centres, weights = np.array(pk["rose"][0]), np.array(pk["rose"][1])
    reg = np.empty(n, int); i = 0
    while i < n:
        L = int(rng.integers(144, 576)); reg[i:i + L] = rng.choice(len(centres), p=weights); i += L
    w = _ar1(rng, n, 0.99, 1.2)
    wd = (centres[reg] + 2.5 * w + rng.standard_normal(n) * 5.0) % 360.0
    T = pk["T0"] + pk["Tslope"] * day / pk["days"] + 4.0 * np.sin(2 * math.pi * (hour - 9) / 24) + _ar1(rng, n, 0.995, 0.25)
    RH = np.clip(70.0 - 12.0 * np.sin(2 * math.pi * (hour - 9) / 24) + rng.standard_normal(n) * 5.0 + 6.0 * np.tanh(_ar1(rng, n, 0.99, 0.2)), 25.0, 100.0)
    p_sea = 1014.0 + 3.0 * _ar1(rng, n, 0.997, 0.35)
    hub = MODELS[pk["models"]["T01"]]["hub"]
    p_ground = p_sea * np.exp(-pk["elev"] * G0 / (R0 * (T + 273.15 + 3.0)))
    p_hub = p_ground * np.exp(-(hub - 2.0) * G0 / (R0 * (T + 273.15)))
    return dict(n=n, ts=ts, hour=hour, U=U, wd=wd, T=T, RH=RH, p_sea=p_sea, p_ground=p_ground, p_hub=p_hub)


def density(T, RH, p_hpa):
    Tk = T + 273.15
    Pw = 0.0000205 * np.exp(0.0631846 * Tk)
    return (1.0 / Tk) * (p_hpa * 100.0 / R0 - (RH / 100.0) * Pw * (1 / R0 - 1 / RW))


def _wakes(pk, U, wd, rng):
    rot, hub = {}, {}
    th = np.deg2rad(wd); dx, dy = -np.sin(th), -np.cos(th)
    ct = np.where(U < 10.0, 0.78, 0.78 * (10.0 / np.maximum(U, 10.0)) ** 3)
    beta = 0.5 * (1 + np.sqrt(1 - ct)) / np.sqrt(1 - ct)
    ang = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    pts = [(0.0, 0.0)] + [(0.5 * math.cos(a), 0.5 * math.sin(a)) for a in ang] + [(0.9 * math.cos(a + 0.39), 0.9 * math.sin(a + 0.39)) for a in ang]
    wts = np.array([0.1] + [0.4 / 8] * 8 + [0.5 / 8] * 8)
    srng = np.random.default_rng(pk["seed"] + 99)
    for t in pk["turbines"]:
        xt, yt = pk["xy"][t]; D = MODELS[pk["models"][t]]["D"]
        d_rot2 = np.zeros_like(U); d_hub2 = np.zeros_like(U)
        for s in pk["turbines"]:
            if s == t: continue
            xs, ys = pk["xy"][s]; Ds = MODELS[pk["models"][s]]["D"]
            rx, ry = xt - xs, yt - ys
            x = rx * dx + ry * dy; lat = rx * dy - ry * dx
            down = x > 2.0 * Ds
            sig = (0.04 * np.maximum(x, 1.0) / Ds + 0.2 * np.sqrt(beta)) * Ds
            C = 1 - np.sqrt(np.clip(1 - ct / (8 * (sig / Ds) ** 2), 0.0, 1.0))
            dh = C * np.exp(-lat ** 2 / (2 * sig ** 2))
            dr = np.zeros_like(U)
            for (py, pz), wgt in zip(pts, wts):
                dr += wgt * C * np.exp(-((lat + py * D / 2) ** 2 + (pz * D / 2) ** 2) / (2 * sig ** 2))
            d_rot2 += np.where(down, dr ** 2, 0.0); d_hub2 += np.where(down, dh ** 2, 0.0)
        f = 1.0 if t == "T01" else 1 + srng.normal(0, 0.008)
        sc = U * f * (1 + rng.standard_normal(len(U)) * 0.02)
        rot[t] = sc * (1 - np.sqrt(d_rot2)); hub[t] = sc * (1 - np.sqrt(d_hub2))
    return rot, hub


def _t(s):
    return np.datetime64(s.replace(" ", "T"))


def _fmt(ts):
    return np.datetime_as_string(ts, unit="m")


def generate(pk, outdir):
    """Write the package's records into outdir; returns the true energy per turbine (for the meters) and the truth."""
    rng = np.random.default_rng(pk["seed"])
    W = _weather(pk, rng); n = W["n"]; ts = W["ts"]
    rho = density(W["T"], W["RH"], W["p_hub"])
    Ui, Uh = _wakes(pk, W["U"], W["wd"], rng)
    F = pk["faults"]
    icing = (W["T"] < 1.0) & (W["RH"] > 88.0)
    icing = np.convolve(icing.astype(float), np.ones(12) / 12, mode="same") > 0.5
    curt = np.zeros(n, bool); events = []
    limits = {t: 0.5 * MODELS[m]["rated"] for t, m in pk["models"].items()}
    for k in range(int(rng.integers(5, 10))):
        a = int(rng.integers(0, n - 60)); L = int(rng.integers(12, 48)); curt[a:a + L] = True
        events.append((_fmt(ts[a]), _fmt(ts[a + L])))
    os.makedirs(os.path.join(outdir, "scada"), exist_ok=True)
    true_p = {}
    local_hour = W["hour"]
    for t in pk["turbines"]:
        model = pk["models"][t]; rated = MODELS[model]["rated"]
        U = Ui[t]
        vn = U * (rho / RHO0) ** (1 / 3)
        p = true_power(model, pk["perf"][t], vn)
        for r in F.get("rotor", []):   # rotor replaced: the new model's power from then on
            if t == r["turbine"]:
                p = np.where(ts >= _t(r["at"]), true_power(r["model"], pk["perf"][t], vn), p)
        p = p * (1 + rng.standard_normal(n) * 0.012) + rng.standard_normal(n) * 6.0
        p = np.where(icing, p * 0.65, p)
        status = np.zeros(n, int); status[U < 3.0] = 1
        down = np.zeros(n, bool)
        for k in range(int(rng.integers(3, 7))):
            a = int(rng.integers(0, n - 300)); L = int(rng.integers(6, 200)); down[a:a + L] = True
            status[a:a + L] = int(rng.choice([2, 3, 7]))
        cap = np.where(curt, limits[t], rated)
        status[curt & ~down] = 5
        if t in pk["sound"]:
            cap = np.where((local_hour >= 22) | (local_hour < 6), np.minimum(cap, pk["sound"][t]), cap)
        p = np.minimum(p, cap)
        p = np.where(down | (U < 3.0) | (U > 25.0), rng.standard_normal(n) * 2.0 - 4.0, p)
        p = np.maximum(p, -15.0)
        true_p[t] = p.copy()
        a_, b_ = pk["ntf_old"]
        Uhub = Uh[t]
        if "fw" in F:
            fw = ts >= _t(F["fw"]["dates"][t])
            nac = np.where(fw, Uhub * FW_BIAS, (Uhub - b_) / a_)
        else:
            nac = (Uhub - b_) / a_
        nac = nac + rng.standard_normal(n) * 0.08
        if "drift" in F and t == "T01":
            d0 = _t(F["drift"]["start"]); d1 = ts[-1] + np.timedelta64(10, "m")
            frac = np.clip((ts - d0) / (d1 - d0), 0.0, 1.0)
            nac = nac * (1 - F["drift"]["mag"] * frac)
        nac = np.maximum(nac, 0.0)
        pr = p.copy()
        if "scale" in F and t == F["scale"]["turbine"]:
            pr = np.where(ts >= _t(F["scale"]["at"]), pr * F["scale"]["factor"], pr)
        yaw = W["wd"] + rng.standard_normal(n) * 4.0
        if "yaw" in F and t == F["yaw"]["turbine"]:
            yaw = np.where(ts >= _t(F["yaw"]["at"]), yaw + F["yaw"]["offset"], yaw)
        yaw = yaw % 360.0
        shift = np.timedelta64(-pk["utc"], "h") if ("utc" in F and F["utc"]["turbine"] == t) else np.timedelta64(0, "h")
        stamp = ts + shift
        has_ice = t in pk["ice"]
        ice_alarm = (icing & has_ice).astype(int)
        tamb = W["T"] + 1.5 + rng.standard_normal(n) * 0.3
        with open(os.path.join(outdir, "scada", "turbine_%s.csv" % t), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "power_kw", "nacelle_ws_ms", "yaw_position_deg", "status", "ambient_temp_c",
                        "ambient_pressure_hpa"] + (["ice_alarm"] if has_ice else []))
            st_s = _fmt(stamp)
            for i in range(n):
                row = [st_s[i].replace("T", " "), "%.1f" % pr[i], "%.2f" % nac[i], "%.1f" % yaw[i], status[i],
                       "%.1f" % tamb[i], "%.1f" % W["p_sea"][i]]
                if has_ice: row.append(ice_alarm[i])
                w.writerow(row)
    # mast
    hz = (W["U"] * (1 + rng.standard_normal(n) * 0.005) - CERT[1]) / CERT[0]
    if "cup" in F:
        sp = ts >= _t(F["cup"]["at"])
        hz = np.where(sp, (W["U"] * (1 + rng.standard_normal(n) * 0.005) - F["cup"]["offset"]) / F["cup"]["slope"], hz)
    pg = W["p_ground"] + rng.standard_normal(n) * 0.2
    if "qnh" in F:
        pg = np.where((ts >= _t(F["qnh"]["start"])) & (ts < _t(F["qnh"]["end"])), 0.0, pg)
    os.makedirs(os.path.join(outdir, "mast"), exist_ok=True)
    wdm = (W["wd"] + rng.standard_normal(n) * 2) % 360; tm = W["T"] + rng.standard_normal(n) * 0.1
    if "vane" in F:   # replaced vane mounted with an orientation error
        wdm = np.where(ts >= _t(F["vane"]["at"]), wdm + F["vane"]["offset"], wdm) % 360
    mstamp = ts.copy(); keep = np.ones(n, bool)
    if "mclock" in F:  # replacement logger set to another time base: records stamped `hours` late from then on
        late = ts >= _t(F["mclock"]["at"])
        mstamp = np.where(late, ts + np.timedelta64(int(F["mclock"]["hours"]), "h"), ts)
        keep = mstamp <= ts[-1]
    with open(os.path.join(outdir, "mast", "m1_10min.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "ws_hub_hz", "wd_hub_deg", "temp_hub_c", "rh_hub_pct", "pressure_2m_hpa"])
        st_s = _fmt(mstamp)
        for i in np.nonzero(keep)[0]:
            w.writerow([st_s[i].replace("T", " "), "%.2f" % hz[i], "%.1f" % wdm[i], "%.2f" % tm[i], "%.1f" % W["RH"][i], "%.1f" % pg[i]])
    os.makedirs(os.path.join(outdir, "records"), exist_ok=True)
    months = ts.astype("datetime64[M]")
    with open(os.path.join(outdir, "records", "monthly_meter_energy.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["month"] + pk["turbines"])
        for m in np.unique(months):
            sel = months == m
            w.writerow([str(m)] + ["%.0f" % (np.maximum(true_p[t][sel], 0).sum() / 6.0 * 0.995) for t in pk["turbines"]])
    with open(os.path.join(outdir, "records", "curtailment_log.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["start_local", "end_local", "limit", "source"])
        for a, b in sorted(events): w.writerow([a.replace("T", " "), b.replace("T", " "), "50 percent of rated power", "grid operator dispatch instruction"])
    return truth(pk)
