"""Reference solution for the base-pressure audit.

    python3 -I diagnose.py DATA_DIR OUT_CSV [VACWORK_DIR]

For each chamber of the register it writes the cause, the total gas load and the effective pumping speed at MS-BP's
reference condition.

Method, per chamber:

1. **The chamber as it stands.** The register entry, changed by every maintenance log row on or before the audit
   date: internal surfaces replaced, seal material or length changed, a trap or baffle fitted in the high-vacuum
   port.

2. **Which records still describe it.** Base-pressure entries are kept from the last change of internals onwards.
   A speed test is kept only if no trap was fitted after it and the turbo controller shows no step in drive power
   or bearing temperature after it; a step voids the test, because the pump it measured is not the pump now.
   Where a gauge's serial in the log is owned by another chamber's certificate and that chamber's log carries this
   chamber's serial on the same dates, the two are read back the right way round.

3. **The gas loads that can be computed.** Wall and internals outgassing follows from the current surfaces, the
   entry's pumping time, vent gas and wall temperature, and the outgassing table, plus the area of any fixture the
   entry names. Permeation follows from the current seal material and length and the wall temperature. Neither
   needs a measurement.

4. **The gas load that cannot.** For each kept entry the indicated pressure is the reading times the certificate
   factor in force, and the true total pressure follows from the composition by MS-BP clause 5; since the
   composition depends on the split, the correction is iterated to a fixed point. The total gas load of the entry
   is the true pressure times the effective speed. What remains after the computable loads are taken out is fitted
   over the kept entries as a constant leak, or as a constant leak plus a decaying trapped volume where the
   evidence supports one.

5. **Which model.** A trapped volume is accepted only on evidence: a residual gas analysis whose nitrogen and
   oxygen outweigh its water, or a clear improvement in fit over a constant leak with a time constant in a
   physical range. Otherwise the residual is a leak.

6. **Referring to the audit condition.** The fitted model is evaluated at %s h, 20 C, an air vent and no load, and
   the cause is named by MS-BP clause 6 against the rated speed of the chamber as it is now.

Where a chamber's speed is not available from a surviving test, it is taken from an ordered speed test or
rate-of-rise test, and failing that from the chamber's own records before the turbo changed.
"""
import csv
import json
import math
import os
import sys

REF_H = 16.0
T_REF = 293.15
R_GAS = 8.3145
E_W = 30.0e3
E_P = 42.0e3
N2_FACTOR = 0.25
PUMP_GATE = 0.75
AUDIT = "2026-11-02"
HE_AIR = 2.69                       # helium leak rate over air leak rate for a channel in molecular flow

PUMP_CONTROLLER = {
    "TMP-400": (1000.0, 60.0, 38.0),
    "TMP-700": (820.0, 95.0, 42.0),
    "TMP-1100": (700.0, 130.0, 45.0),
    "TMP-1600": (600.0, 170.0, 48.0),
}
TURBO = {
    "TMP-400": [(1e-9, 360.0), (1e-3, 360.0), (1e-2, 250.0), (5e-2, 100.0), (2e-1, 28.0)],
    "TMP-700": [(1e-9, 640.0), (1e-3, 640.0), (1e-2, 420.0), (5e-2, 160.0), (2e-1, 40.0)],
    "TMP-1100": [(1e-9, 1010.0), (1e-3, 1010.0), (1e-2, 640.0), (5e-2, 230.0), (2e-1, 55.0)],
    "TMP-1600": [(1e-9, 1480.0), (1e-3, 1480.0), (1e-2, 900.0), (5e-2, 310.0), (2e-1, 70.0)],
}
OUTGAS = {
    "stainless steel, electropolished": (7.0e-9, 1.00),
    "stainless steel, as machined": (2.6e-8, 1.00),
    "stainless steel, bead blasted": (6.5e-8, 0.95),
    "aluminum, bare": (1.4e-8, 1.00),
    "aluminum, anodized": (5.5e-7, 0.85),
    "copper, bare": (2.2e-8, 1.00),
    "PEEK": (3.5e-7, 0.60),
    "graphite felt": (9.0e-7, 0.70),
}
SEALS = {
    "fluoroelastomer": (1.15e-7, dict(n2=1.00, o2=3.00, ar=0.35, co2=12.0)),
    "nitrile": (3.40e-7, dict(n2=1.00, o2=2.60, ar=0.40, co2=10.0)),
    "perfluoroelastomer": (4.20e-8, dict(n2=1.00, o2=2.80, ar=0.30, co2=11.0)),
}
AIR = dict(n2=0.7808, o2=0.2095, ar=0.00934, co2=0.00042)
SPECIES = {
    "wall-outgassing": dict(h2o=0.960, h2=0.015, n2=0.025),
    "air-leak": dict(AIR),
    "virtual-leak": dict(AIR),
}
GAS_FACTOR = dict(h2o=1.12, h2=0.42, n2=1.00, o2=1.01, ar=1.29, co2=1.42)
FIXTURES = {
    "carrier set A": (2.4, "stainless steel, as machined"),
    "carrier set B": (1.6, "stainless steel, bead blasted"),
    "lens rack": (0.55, "aluminum, anodized"),
    "braze fixture": (2.1, "stainless steel, bead blasted"),
    "shield set": (1.8, "aluminum, bare"),
    "harness tray": (0.30, "PEEK"),
}


# ---------------------------------------------------------------------------------------------------- physics
def curve(table, p):
    lp = math.log10(max(p, 1e-12))
    xs = [math.log10(a) for a, _ in table]
    ys = [b for _, b in table]
    if lp <= xs[0]:
        return ys[0]
    if lp >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if lp <= xs[i]:
            f = (lp - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + f * (ys[i] - ys[i - 1])
    return ys[-1]


def series(s, c):
    return s * c / (s + c)


def theta(e, t_k):
    return math.exp(e / R_GAS * (1.0 / T_REF - 1.0 / t_k))


def q_wall_nominal(surfaces, t_h, vent, t_k):
    """What the outgassing table's nominal q1 gives for these surfaces: the shape of the wall gas load."""
    t = max(t_h, 0.05)
    f = 1.0 if vent == "air" else N2_FACTOR
    tot = 0.0
    for area_m2, mat in surfaces:
        q1, alpha = OUTGAS[mat]
        tot += area_m2 * 1e4 * q1 * t ** -alpha
    return tot * f * theta(E_W, t_k)


def q_wall(surfaces, t_h, vent, t_k, c_w=1.0):
    return c_w * q_wall_nominal(surfaces, t_h, vent, t_k)


def q_perm(seal, l_cm, t_k=None):
    return SEALS[seal][0] * l_cm * theta(E_P, t_k)


def perm_mix(seal):
    rel = SEALS[seal][1]
    w = {k: AIR[k] * rel[k] for k in AIR}
    tot = sum(w.values())
    return {k: v / tot for k, v in w.items()}


def gas_correction(parts, seal):
    """p_true / p_N2 for a gas made of the given mechanism loads."""
    tot = sum(parts.values())
    if tot <= 0:
        return 1.0
    mix = {}
    for mech, q in parts.items():
        if q <= 0:
            continue
        w = perm_mix(seal) if mech == "permeation" else SPECIES[mech]
        s = sum(w.values())
        for k, v in w.items():
            mix[k] = mix.get(k, 0.0) + q / tot * v / s
    denom = sum(x / GAS_FACTOR[k] for k, x in mix.items())
    return 1.0 / denom if denom > 0 else 1.0


# ---------------------------------------------------------------------------------------------------- reading
def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_data(d):
    return dict(
        register=read_csv(os.path.join(d, "chamber_register.csv")),
        log=read_csv(os.path.join(d, "base_pressure_log.csv")),
        speed=read_csv(os.path.join(d, "speed_tests.csv")),
        ctrl=read_csv(os.path.join(d, "turbo_controller.csv")),
        maint=read_csv(os.path.join(d, "maintenance_log.csv")),
        certs=parse_certs(os.path.join(d, "gauge_certificates.md")),
    )


def parse_certs(path):
    """{serial: (owning chamber, [(date, factor)])} from the certificates document."""
    out = {}
    serial = None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("## "):
                serial = line[3:].strip()
                out[serial] = [None, []]
            elif serial and "installed on chamber" in line:
                out[serial][0] = line.rstrip(".").split()[-1]
            elif serial and line.startswith("| 20"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) == 2:
                    try:
                        out[serial][1].append((cells[0], float(cells[1])))
                    except ValueError:
                        pass
    return {k: (v[0], sorted(v[1])) for k, v in out.items() if v[1]}


def cert_factor(certs, serial, date):
    f = certs[serial][1][0][1]
    for d, v in certs[serial][1]:
        if d <= date:
            f = v
    return f


# ---------------------------------------------------------------------------------------------------- chamber
def chamber_config(cid, data):
    reg = [r for r in data["register"] if r["chamber"] == cid]
    r0 = reg[0]
    cfg = dict(id=cid, volume=float(r0["volume_l"]), turbo=r0["turbo"], c_port=float(r0["c_port_l_s"]),
               seal=r0["seal_material"], seal_cm=float(r0["seal_length_cm"]),
               surfaces=[(float(r["surface_area_m2"]), r["surface"]) for r in reg],
               p_spec=float(r0["p_spec_mbar"]), internals_from=None, trap_from=None,
               turbo_register=r0["turbo"])
    # the seal is kept as a history, because a seal changed part way through the log means one permeation
    # constant will not serve every entry
    cfg["seal_hist"] = [("0000-00-00", cfg["seal"], cfg["seal_cm"])]
    for row in sorted(data["maint"], key=lambda r: r["date"]):
        if row["chamber"] != cid or row["date"] > AUDIT:
            continue
        e = row["entry"]
        if "Internal surfaces after the work:" in e:
            spec = e.split("Internal surfaces after the work:", 1)[1].strip().rstrip(".")
            surf = []
            for part in spec.split(";"):
                part = part.strip()
                a, mat = part.split(" m2 ", 1)
                surf.append((float(a), mat.strip()))
            cfg["surfaces"] = surf
            cfg["internals_from"] = row["date"]
        if "Port conductance after the work:" in e:
            v = e.split("Port conductance after the work:", 1)[1]
            cfg["c_port"] = float(v.strip().split()[0])
            cfg["trap_from"] = row["date"]
        if "Seal material after the work:" in e:
            cfg["seal"] = e.split("Seal material after the work:", 1)[1].strip().rstrip(".")
            cfg["seal_hist"].append((row["date"], cfg["seal"], cfg["seal_cm"]))
        if "Seal length after the work:" in e:
            cfg["seal_cm"] = float(e.split("Seal length after the work:", 1)[1].strip().split()[0])
            cfg["seal_hist"].append((row["date"], cfg["seal"], cfg["seal_cm"]))
    return cfg


def seal_at(cfg, date):
    """The seal material and length in place on a date."""
    mat, cm = cfg["seal_hist"][0][1], cfg["seal_hist"][0][2]
    for d, m, c in cfg["seal_hist"]:
        if d <= date:
            mat, cm = m, c
    return mat, cm


def pump_from_controller(cid, data):
    """The pump model the controller's own figures say is fitted.

    A register is a list of what was ordered and can name the wrong pump; a controller reports the rotor
    frequency, drive power and bearing temperature of the pump actually turning, and the shop's vacuum data give
    those three figures for each model at its rated speed. The model whose figures fit the chamber's earliest
    rows, before any change in them, is the pump that is there. Nothing about the gas budget depends on this, and
    nothing in a fit will show it: what depends on it is the rated speed, and so whether MS-BP clause 6 calls the
    pump the cause."""
    rows = sorted([r for r in data["ctrl"] if r["chamber"] == cid], key=lambda r: r["date"])[:4]
    if not rows:
        return None
    hz = sum(float(r["rotor_hz"]) for r in rows) / len(rows)
    pw = sum(float(r["drive_power_w"]) for r in rows) / len(rows)
    tb = sum(float(r["bearing_temp_c"]) for r in rows) / len(rows)
    best, score = None, None
    for model, (h, w, t) in PUMP_CONTROLLER.items():
        d = ((hz - h) / h) ** 2 + ((pw - w) / w) ** 2 + ((tb - t) / t) ** 2
        if score is None or d < score:
            best, score = model, d
    return best if score is not None and score < 0.02 else None


def pump_changed_on(cid, data):
    """The first date on which the controller shows the turbo is not the pump it was: a step of more than 15 per
    cent in drive power or more than 5 C in bearing temperature against the chamber's own first rows."""
    rows = sorted([r for r in data["ctrl"] if r["chamber"] == cid], key=lambda r: r["date"])
    if len(rows) < 2:
        return None
    pw0 = float(rows[0]["drive_power_w"])
    tb0 = float(rows[0]["bearing_temp_c"])
    for r in rows[1:]:
        if float(r["drive_power_w"]) > 1.15 * pw0 or float(r["bearing_temp_c"]) > tb0 + 5.0:
            return r["date"]
    return None


def crossed_serials(data, certs):
    """Serials that appear in a chamber's log but belong to another chamber's certificate, where that other
    chamber's log carries this chamber's serial on the same dates. Returns {(chamber, date): right serial}."""
    by = {}
    for r in data["log"]:
        by.setdefault(r["chamber"], set()).add(r["gauge"])
    own = {}
    for s, (owner, _f) in certs.items():
        own.setdefault(owner, set()).add(s)
    fix = {}
    for cid, used in by.items():
        foreign = {s for s in used if certs.get(s, (None,))[0] not in (cid, None)}
        for s in foreign:
            other = certs[s][0]
            mine = own.get(cid, set())
            if other and mine & by.get(other, set()):
                right = sorted(mine & by.get(other, set()))[0]
                for r in data["log"]:
                    if r["chamber"] == cid and r["gauge"] == s:
                        fix[(cid, r["date"], r["pumpdown"])] = right
    return fix


# ---------------------------------------------------------------------------------------------------- fitting
def entry_points(cid, cfg, data, certs, fix):
    """The kept base-pressure entries as dicts, one per pumpdown, preferring the reference instrument."""
    rows = [r for r in data["log"] if r["chamber"] == cid and r["date"] <= AUDIT]
    if cfg["internals_from"]:
        rows = [r for r in rows if r["date"] >= cfg["internals_from"]]
    by_pd = {}
    for r in rows:
        by_pd.setdefault((r["date"], r["pumpdown"]), []).append(r)
    pts = []
    for (date, pd), group in sorted(by_pd.items()):
        pick = None
        for r in group:                                      # the ionization gauge is the reference instrument
            if r["gauge"].startswith("IG"):
                pick = r
                break
        if pick is None:
            if len(group) == 1:
                pick = group[0]
            else:
                pick = sorted(group, key=lambda r: r["gauge"])[0]
            if any(g["gauge"].startswith("IG") for g in by_pd.get((date, pd), [])):
                pass
        serial = fix.get((cid, date, pd), pick["gauge"])
        if serial not in certs:
            continue
        load = pick["load"].strip()
        pts.append(dict(date=date, pd=pd, vent=pick["vent_gas"], t_h=float(pick["pumpdown_h"]),
                        t_k=float(pick["wall_temp_c"]) + 273.15,
                        p_n2=float(pick["reading_mbar"]) * cert_factor(certs, serial, date),
                        load=load, serial=serial, reference=pick["gauge"].startswith("IG")))
    return pts


def _day_number(date):
    import datetime
    y, m, d = map(int, date.split("-"))
    return datetime.date(y, m, d).toordinal()


def correct_drift(pts, cid, data):
    """Where a chamber carries both gauge types, the cold cathode is checked against the reference instrument on
    every pumpdown both were read on. A cold cathode that fouls reads progressively low, so the ratio is fitted as
    a straight line in days and carried forward to the pumpdowns the reference instrument did not see, whose
    cold cathode readings are corrected by it. Where the two agree, nothing is changed."""
    rows = [r for r in data["log"] if r["chamber"] == cid]
    if not {"CC", "IG"} <= {r["gauge"][:2] for r in rows}:
        return pts
    paired = {}
    for r in rows:
        paired.setdefault((r["date"], r["pumpdown"]), {})[r["gauge"][:2]] = float(r["reading_mbar"])
    obs = [(_day_number(d), v["CC"] / v["IG"]) for (d, _p), v in sorted(paired.items())
           if "CC" in v and "IG" in v]
    if len(obs) < 2 or abs(obs[-1][1] - obs[0][1]) <= 0.02:
        return pts
    n = len(obs)
    sx = sum(x for x, _ in obs)
    sy = sum(y for _, y in obs)
    sxx = sum(x * x for x, _ in obs)
    sxy = sum(x * y for x, y in obs)
    den = n * sxx - sx * sx
    if abs(den) < 1e-12:
        return pts
    b = (n * sxy - sx * sy) / den
    a = (sy - b * sx) / n
    out = []
    for p in pts:
        if p["reference"]:
            out.append(p)
            continue
        ratio = a + b * _day_number(p["date"])
        if 0.2 < ratio < 5.0:
            out.append(dict(p, p_n2=p["p_n2"] / ratio, drift_corrected=True))
        else:
            out.append(p)
    return out


def surfaces_with_load(cfg, load):
    surf = list(cfg["surfaces"])
    if load and load in FIXTURES:
        surf.append(FIXTURES[load])
    return surf


def nominal_wall(cfg, pt):
    """The nominal wall shape for one entry, including the area of any fixture it names."""
    return q_wall_nominal(surfaces_with_load(cfg, pt["load"]), pt["t_h"], pt["vent"], pt["t_k"])


def perm_of(cfg, pt):
    """The permeation gas load of one entry, with the seal that was in place on its date."""
    mat, cm = seal_at(cfg, pt["date"])
    return q_perm(mat, cm, pt["t_k"])


def _lstsq_nonneg(cols, y):
    """Least squares in the given columns with every coefficient at or above zero. With at most three columns the
    active set is found by trying each subset, which is exact and needs no iteration."""
    import itertools
    import numpy as np
    n = len(y)
    k = len(cols)
    A = np.array(cols, dtype=float).T
    yv = np.array(y, dtype=float)
    best = None
    for size in range(k, 0, -1):
        for sub in itertools.combinations(range(k), size):
            M = A[:, list(sub)]
            if M.shape[0] < M.shape[1]:
                continue
            try:
                c, *_ = np.linalg.lstsq(M, yv, rcond=None)
            except np.linalg.LinAlgError:
                continue
            if np.any(c < -1e-18):
                continue
            full = np.zeros(k)
            full[list(sub)] = np.maximum(c, 0.0)
            ss = float(np.sum((A @ full - yv) ** 2))
            if best is None or ss < best[1] - 1e-30:
                best = (full, ss)
    if best is None:
        return [0.0] * k, float(sum(v * v for v in y))
    return list(best[0]), best[1]


def fit_split(cfg, pts, s_eff, tau=None):
    """Identifies the chamber's gas budget from its entries.

    Each entry's true total pressure is its nitrogen-equivalent pressure times MS-BP clause 5's correction, and
    its total gas load is that times the effective speed. The loads are fitted to

        Q_i = C_w * W_i + Q_perm(T_i) + Q_L [ + Q_v0 exp(-t_i / tau) ]

    with W_i the nominal wall shape of the entry and Q_perm computable from the seal. Since the correction depends
    on the split and the split on the correction, the two are iterated to a fixed point. Returns
    (C_w, Q_L, Q_v0, residual sum of squares, the entries' total gas loads)."""
    n = len(pts)
    W = [nominal_wall(cfg, p) for p in pts]
    QP = [perm_of(cfg, p) for p in pts]
    corr = [1.0] * n
    coef = [1.0, 0.0, 0.0]
    ss = 0.0
    q = [0.0] * n
    for _ in range(20):
        q = [pts[i]["p_n2"] * corr[i] * s_eff for i in range(n)]
        y = [q[i] - QP[i] for i in range(n)]
        cols = [W, [1.0] * n]
        if tau:
            cols.append([math.exp(-pts[i]["t_h"] / tau) for i in range(n)])
        c, ss = _lstsq_nonneg(cols, y)
        coef = [c[0], c[1], c[2] if tau else 0.0]
        new = []
        for i in range(n):
            parts = {"wall-outgassing": coef[0] * W[i], "permeation": QP[i], "air-leak": coef[1]}
            if tau:
                parts["virtual-leak"] = coef[2] * math.exp(-pts[i]["t_h"] / tau)
            new.append(gas_correction(parts, seal_at(cfg, pts[i]["date"])[0]))
        if max(abs(a - b) for a, b in zip(new, corr)) < 1e-10:
            corr = new
            break
        corr = new
    return coef[0], coef[1], coef[2], ss, q


def durations(pts):
    return sorted({round(p["t_h"], 2) for p in pts})


TAU_RANGE = (2.0, 48.0)
TAU_SPREAD = 12.0                   # the exponential may not vary by more than this over the entries
MIN_TRAPPED_SHARE = 0.08            # a trapped volume that contributes less than this at the reference condition
                                    # is not what limits the chamber, whatever it does to the residual


def best_trapped(cfg, pts, s_eff):
    """The trapped-volume model over a grid of time constants, by residual sum of squares.

    A time constant short against the entries' pumping times makes the exponential column vanish at every entry
    but one, and such a fit will take up noise with an arbitrarily large coefficient. Only time constants whose
    exponential is comparable across the entries are considered, and only fits whose trapped volume still carries
    a real share of the gas load at the reference condition."""
    best = None
    for i in range(int(TAU_RANGE[0] * 2), int(TAU_RANGE[1] * 2) + 1):
        tau = 0.5 * i
        ex = [math.exp(-p["t_h"] / tau) for p in pts]
        if min(ex) <= 0 or max(ex) / min(ex) > TAU_SPREAD:
            continue
        c_w, q_l, qv0, ss, _q = fit_split(cfg, pts, s_eff, tau)
        if qv0 <= 0 or c_w <= 0:
            continue
        _parts, total = at_reference(cfg, c_w, q_l, qv0, tau)
        if total <= 0 or qv0 * math.exp(-REF_H / tau) / total < MIN_TRAPPED_SHARE:
            continue
        if best is None or ss < best[3]:
            best = (c_w, q_l, qv0, ss, tau)
    return best


def _header_values(path):
    """The pumping time in hours and the wall temperature in kelvin from a report's header comments."""
    t_h, t_k = REF_H, T_REF
    with open(path) as f:
        for line in f:
            if not line.startswith("#"):
                break
            if "pumping time" in line:
                t_h = float(line.rsplit(":", 1)[1].strip().split()[0])
            elif "wall temperature" in line:
                t_k = float(line.rsplit(":", 1)[1].strip().split()[0]) + 273.15
    return t_h, t_k


def rga_says(cid, vac):
    """From a residual gas analysis: 'air' when nitrogen and oxygen outweigh water, 'water' when they do not, and
    the oxygen-to-nitrogen ratio, which separates permeated air from a real leak, since an elastomer passes oxygen
    about three times as readily as nitrogen while a channel passes air in its own proportions."""
    path = os.path.join(vac, "rga_%s.csv" % cid.lower()) if vac else None
    if not path or not os.path.exists(path):
        return None
    pp = {}
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("species"):
                continue
            parts = line.strip().split(",")
            if len(parts) == 3:
                pp[parts[0]] = float(parts[2])
    air = pp.get("n2", 0) + pp.get("o2", 0) + pp.get("ar", 0)
    water = pp.get("h2o", 0)
    o2n2 = pp.get("o2", 0) / pp["n2"] if pp.get("n2") else 0.0
    t_h, t_k = _header_values(path)
    return dict(kind="air" if air > water else "water", o2_n2=o2n2, pp=pp, t_h=t_h, t_k=t_k)


ROR_WINDOW = 600.0                  # s, the part of a rate-of-rise run the slope is taken over


def rate_of_rise_says(cid, cfg, vac):
    """From a rate-of-rise test: the chamber's true base pressure, which needs no gas correction, and its total
    gas load, the volume times the slope of the rise.

    The slope is taken over the first ROR_WINDOW seconds only. The wall gas load falls as the pumping time grows,
    so a slope fitted over the whole hour is the gas load averaged over that hour and not the gas load at the
    pumping time the test reports; over ten minutes the fall is well under a per cent."""
    path = os.path.join(vac, "rate_of_rise_%s.csv" % cid.lower()) if vac else None
    if not path or not os.path.exists(path):
        return None
    pts = []
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("seconds"):
                continue
            a, b = line.strip().split(",")
            pts.append((float(a), float(b)))
    if len(pts) < 10:
        return None
    window = [q for q in pts if q[0] <= ROR_WINDOW] or pts
    n = len(window)
    sx = sum(x for x, _ in window)
    sy = sum(y for _, y in window)
    sxx = sum(x * x for x, _ in window)
    sxy = sum(x * y for x, y in window)
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    t_h, t_k = _header_values(path)
    base = _base_pressure(path)
    return dict(p_base=base if base else pts[0][1], q_total=slope * cfg["volume"], t_h=t_h, t_k=t_k)


def _base_pressure(path):
    """The base pressure the report gives for the ten minutes before the valve was closed. The trace's own first
    sample is a single reading, and the pressure rises a hundredfold across the window, so the averaged figure the
    report carries is the one to divide the gas load by."""
    with open(path) as f:
        for line in f:
            if not line.startswith("#"):
                return None
            if "base pressure before valve closure" in line:
                return float(line.rsplit(":", 1)[1].strip().split()[0])
    return None


def helium_says(cid, vac):
    """From a helium leak test: the chamber's real air leak, and nothing else.

    A channel in molecular flow answers within seconds, so its signal is a step; gas crossing an elastomer seal by
    permeation answers over minutes, so its signal is a ramp that is still climbing when the hood comes off. The
    real leak is the largest step any region shows, converted from the helium rate the detector reads to an air
    rate by HE_AIR. What the test cannot show is a trapped volume, which vents into the chamber and never reaches
    a hood at all: that is why a helium test tells a leak from permeation but leaves the rest of a constant gas
    load unexplained."""
    path = os.path.join(vac, "helium_%s.csv" % cid.lower()) if vac else None
    if not path or not os.path.exists(path):
        return None
    by_region = {}
    with open(path) as f:
        for line in f:
            if line.startswith("#") or line.startswith("region"):
                continue
            region, sec, val = line.strip().split(",")
            by_region.setdefault(region, []).append((float(sec), float(val)))
    best = 0.0
    for region, pts in by_region.items():
        pts.sort()
        early = [v for t, v in pts if t <= 30.0]
        late = [v for t, v in pts if t >= 240.0]
        if not early or not late:
            continue
        base = early[0]
        rise_early = max(early) - base
        rise_late = (sum(late) / len(late)) - base
        # a step has most of its rise in the first half minute; a ramp is still well short of its end value there
        if rise_late > 0 and rise_early > 0.5 * rise_late:
            best = max(best, rise_early)
    return dict(leak=best / HE_AIR) if best > 0 else dict(leak=0.0)


def ordered_speed(cid, cfg, vac):
    """The effective speed from an ordered test, and whether it came through a gauge certificate: a throughput
    test does, so a wrong certificate carries into it, while a rate-of-rise test is read with a spinning rotor
    gauge and does not."""
    if not vac:
        return None, True
    sp = os.path.join(vac, "speed_test_%s.csv" % cid.lower())
    if os.path.exists(sp):
        with open(sp) as f:
            rows = [l for l in f if not l.startswith("#") and not l.startswith("flow")]
        if rows:
            return float(rows[-1].strip().split(",")[3]), True
    ror = rate_of_rise_says(cid, cfg, vac)
    if ror and ror["p_base"] > 0:
        return ror["q_total"] / ror["p_base"], False
    return None, True


def surviving_speed(cid, cfg, data, changed):
    """The latest speed test that still describes the chamber: after any trap, and before any turbo change."""
    rows = sorted([r for r in data["speed"] if r["chamber"] == cid], key=lambda r: r["date"])
    ok = []
    for r in rows:
        if cfg["trap_from"] and r["date"] < cfg["trap_from"]:
            continue
        if changed and r["date"] >= changed:
            continue
        ok.append(r)
    if not ok:
        return None
    if changed:
        return None                                   # a test before the change does not describe the pump now
    return float(ok[-1]["s_eff_l_s"])


def baseline_speed(cid, cfg, data, certs, fix, changed, k=1.0):
    """Failing a test, the speed now from the chamber's own records. The gas budget is identified from the entries
    before the turbo changed, where the old speed test still described the pump; the same budget evaluated at a
    later entry's condition, divided by that entry's true pressure, gives the speed now."""
    old = [r for r in sorted(data["speed"], key=lambda r: r["date"])
           if r["chamber"] == cid and r["date"] < changed
           and not (cfg["trap_from"] and r["date"] < cfg["trap_from"])]
    if not old:
        return None
    s_old = float(old[-1]["s_eff_l_s"]) / k
    pts = correct_drift(entry_points(cid, cfg, data, certs, fix), cid, data)
    if k != 1.0:
        pts = [dict(q, p_n2=q["p_n2"] * k) for q in pts]
    before = [p for p in pts if p["date"] < changed]
    after = [p for p in pts if p["date"] >= changed]
    if not before or not after:
        return None
    c_w, q_l, _qv, _ss, _q = fit_split(cfg, before, s_old)
    est = []
    for p in after:
        qw = c_w * nominal_wall(cfg, p)
        qp = perm_of(cfg, p)
        parts = {"wall-outgassing": qw, "permeation": qp, "air-leak": q_l}
        est.append((qw + qp + q_l) / (p["p_n2"] * gas_correction(parts, seal_at(cfg, p["date"])[0])))
    return sum(est) / len(est)


# ---------------------------------------------------------------------------------------------------- audit
CERT_SLACK = 0.02                   # a measured speed may sit this far above rated on the test's own scatter


def rated_at(cfg, p=1e-6):
    return series(curve(TURBO[cfg["turbo"]], p), cfg["c_port"])


def with_controller_pump(cid, cfg, data):
    """The configuration with the pump the controller reports, where that is not the pump the register names."""
    model = pump_from_controller(cid, data)
    if model and model != cfg["turbo"]:
        return dict(cfg, turbo=model)
    return cfg


def certificate_error(cid, cfg, data):
    """How far a chamber's gauge certificate is out, if it is.

    A wrong calibration factor cancels in the gas load: every pressure the certificate yields is low by the same
    factor and every speed it yields is high by it, so Q = p S_eff comes out right and the gas budget fits as well
    as ever. What it cannot do is hide in the speed. MS-BP clause 4 has the chamber's effective speed as its pump
    in series with its port, and a pump delivers at most its curve, so a speed above the rated speed is not
    possible. The chamber's own throughput tests are where that shows, whatever the audit ends up taking its speed
    from, so they are what is checked here: the ratio of the speed they report to the rated speed is the factor
    the certificate is out by.

    A test taken before a trap was fitted measured a larger port and is left out; it is not evidence of anything
    about the certificate."""
    rated = rated_at(cfg)
    ratios, serials = [], set()
    for r in data["speed"]:
        if r["chamber"] != cid:
            continue
        if cfg["trap_from"] and r["date"] < cfg["trap_from"]:
            continue
        ratios.append(float(r["s_eff_l_s"]) / rated)
        serials.add(r["gauge"])
    if not ratios:
        return 1.0, None
    k = sum(ratios) / len(ratios)
    if k <= 1.0 + CERT_SLACK:
        return 1.0, None
    return k, (sorted(serials)[0] if len(serials) == 1 else None)


def front_end(cid, data, certs, fix, vac):
    """The chamber as it stands, the records that still describe it and the speed: everything the audit settles
    before it attributes the gas load to a mechanism.

    This is a function rather than the first half of `audit_chamber` because the authoring studies need exactly
    the audit's own front end. A study that keeps its own copy measures the copy: when the copy falls behind, the
    study reports its own drift as a finding."""
    cfg = with_controller_pump(cid, chamber_config(cid, data), data)
    changed = pump_changed_on(cid, data)
    # the certificate is checked first, because every pressure and every reported speed of this chamber has to be
    # put right by the same factor before anything is fitted
    k, k_serial = certificate_error(cid, cfg, data)
    s_eff, from_gauge = ordered_speed(cid, cfg, vac)
    if s_eff is None:
        s_eff, from_gauge = surviving_speed(cid, cfg, data, changed), True
    if s_eff is None and changed:
        s_eff, from_gauge = baseline_speed(cid, cfg, data, certs, fix, changed, k), False
    if s_eff is None:
        s_eff, from_gauge = rated_at(cfg), False
    if from_gauge:
        s_eff = s_eff / k                             # the contractor read it with the same certificate

    pts = correct_drift(entry_points(cid, cfg, data, certs, fix), cid, data)
    if changed:
        pts = [p for p in pts if p["date"] >= changed] or pts
    if k != 1.0:
        # only the readings taken with the gauge whose certificate is out need putting right; a chamber that also
        # carries the reference instrument of clause 5 has readings that were never affected
        pts = [dict(q, p_n2=q["p_n2"] * k) if (k_serial is None or q["serial"] == k_serial) else q
               for q in pts]
    return cfg, pts, s_eff


def audit_chamber(cid, data, certs, fix, vac):
    cfg, pts, s_eff = front_end(cid, data, certs, fix, vac)

    rga = rga_says(cid, vac)
    nd = len(durations(pts))
    if nd >= 2:
        parts, q_total = identify_from_log(cid, cfg, pts, s_eff, data, rga)
    else:
        parts, q_total = identify_from_rga(cid, cfg, pts, s_eff, data, rga, vac)

    s_rated = series(curve(TURBO[cfg["turbo"]], q_total / max(s_eff, 1.0)), cfg["c_port"])
    if s_eff < PUMP_GATE * s_rated:
        cause = "pump-speed"
    else:
        cause = max(parts, key=lambda k: parts[k])
    return dict(chamber=cid, cause=cause, q_total=q_total, s_eff=s_eff, parts=parts, s_rated=s_rated,
                durations=nd)


def at_reference(cfg, c_w, q_l, qv0, tau):
    """The gas budget evaluated at MS-BP's reference condition: 16 h, 20 C, an air vent and no load, with the
    chamber's internal surfaces and seal as they are on the audit date."""
    qw = c_w * q_wall_nominal(cfg["surfaces"], REF_H, "air", T_REF)
    mat, cm = seal_at(cfg, AUDIT)
    qp = q_perm(mat, cm, T_REF)
    qv = qv0 * math.exp(-REF_H / tau) if qv0 and tau else 0.0
    parts = {"wall-outgassing": qw, "permeation": qp, "air-leak": max(q_l, 0.0), "virtual-leak": qv}
    return parts, sum(parts.values())


def identify_from_log(cid, cfg, pts, s_eff, data, rga):
    """The ordinary case: the log spans more than one pumping time, so the wall coefficient and the constant part
    of the gas load separate. A trapped volume is admitted only on evidence."""
    c_w, q_l, _qv, ss_leak, _q = fit_split(cfg, pts, s_eff)
    trapped = best_trapped(cfg, pts, s_eff) if len(pts) >= 3 else None
    use_trapped = False
    if trapped:
        better = trapped[3] < 0.25 * ss_leak
        if rga is not None:
            # a gas of nitrogen and oxygen in air's proportions is a leak or a trapped volume; whether it decays
            # is what separates the two
            air_like = rga["kind"] == "air" and rga["o2_n2"] < 0.45
            use_trapped = air_like and trapped[3] < 0.60 * ss_leak
        else:
            use_trapped = better and 0.5 <= trapped[4] <= 48.0
    if use_trapped:
        c_w, q_l, qv0, _ss, tau = trapped
        return at_reference(cfg, c_w, q_l, qv0, tau)
    return at_reference(cfg, c_w, q_l, 0.0, None)


WALL_WATER = (SPECIES["wall-outgassing"]["h2o"] + SPECIES["wall-outgassing"]["h2"]) / sum(
    SPECIES["wall-outgassing"].values())


def identify_from_rga(cid, cfg, pts, s_eff, data, rga, vac=None):
    """A chamber whose log holds only one pumping time. The wall gas load cannot be separated from the constant
    part by the log alone, so the split comes from the composition instead.

    Of the mechanisms, only the wall admits water, so the water the analyser reads fixes the wall's gas load. The
    analyser's partial pressures are true pressures and need no gas correction, so their sum times the effective
    speed is the whole gas load at the test's condition. Permeation is computable from the seal, and what is left
    is air through a channel: a leak, or a trapped volume if the chamber was sound when it was first speed-tested
    and has been worked on since.

    Everything is done at the test's own pumping time and wall temperature, and only then referred to the
    reference condition, so the log's temperature never enters."""
    hel = helium_says(cid, vac)
    if rga is None and hel is not None:
        # The helium test gives the real leak and leaves everything else as it was. The gas load at the single
        # pumping time is p S_eff as before; permeation is computable; the leak is measured; and the wall and any
        # trapped volume share what remains. A trapped volume is what a chamber worked on since it was last sound
        # has, and the wall takes the rest at the table's nominal coefficient.
        q_meas = sum(q["p_n2"] for q in pts) / len(pts) * s_eff
        qp = q_perm(*seal_at(cfg, AUDIT), t_k=pts[-1]["t_k"])
        w_t = q_wall_nominal(cfg["surfaces"], pts[-1]["t_h"], "air", pts[-1]["t_k"])
        corr = 1.0
        for _ in range(20):
            total = q_meas * corr
            rest = max(total - qp - hel["leak"], 0.0)
            trapped = rest if was_sound_and_worked_on(cid, cfg, data) else 0.0
            wall = 0.0 if trapped else rest
            new = gas_correction({"wall-outgassing": wall, "permeation": qp, "air-leak": hel["leak"],
                                  "virtual-leak": trapped}, seal_at(cfg, pts[-1]["date"])[0])
            if abs(new - corr) < 1e-10:
                corr = new
                break
            corr = new
        total = q_meas * corr
        rest = max(total - qp - hel["leak"], 0.0)
        if was_sound_and_worked_on(cid, cfg, data):
            tau = 9.0
            c_w = 1.0 * 0.0
            return at_reference(cfg, c_w, hel["leak"], rest * math.exp(pts[-1]["t_h"] / tau), tau)
        c_w = rest / w_t if w_t > 0 else 1.0
        return at_reference(cfg, c_w, hel["leak"], 0.0, None)
    ror = rate_of_rise_says(cid, cfg, vac)
    if rga is None and ror is not None:
        # A rate-of-rise is read with a spinning rotor gauge, so it gives the whole gas load at its own condition
        # without any correction for composition. The split is then needed only to carry that total from the
        # test's wall temperature to 20 C, where it moves the answer by a fraction of what it would if it had to
        # fix the total as well: permeation is computable, and the wall takes the rest.
        qp_t = q_perm(*seal_at(cfg, AUDIT), t_k=ror["t_k"])
        w_t = q_wall_nominal(cfg["surfaces"], ror["t_h"], "air", ror["t_k"])
        c_w = max((ror["q_total"] - qp_t) / w_t, 0.0) if w_t > 0 else 1.0
        return at_reference(cfg, c_w, 0.0, 0.0, None)
    if rga is None:
        # Nothing to separate the wall coefficient from the constant part: a least squares lands anywhere along
        # the line that fits the single pumping time, and this is the chamber the audit order is for.
        c_w, q_l, _qv, _ss, _q = fit_split(cfg, pts, s_eff)
        return at_reference(cfg, c_w, q_l, 0.0, None)
    pp = rga["pp"]
    t_test, temp_test = rga["t_h"], rga["t_k"]
    q_total = sum(pp.values()) * s_eff
    q_wall_t = (pp.get("h2o", 0.0) + pp.get("h2", 0.0)) * s_eff / WALL_WATER
    q_perm_t = q_perm(*seal_at(cfg, AUDIT), t_k=temp_test)
    nominal = q_wall_nominal(cfg["surfaces"], t_test, "air", temp_test)
    c_w = q_wall_t / nominal if nominal > 0 else 1.0
    channel = max(q_total - q_wall_t - q_perm_t, 0.0)
    if was_sound_and_worked_on(cid, cfg, data):
        tau = 9.0
        return at_reference(cfg, c_w, 0.0, channel * math.exp(t_test / tau), tau)
    return at_reference(cfg, c_w, channel, 0.0, None)


def was_sound_and_worked_on(cid, cfg, data):
    """True when the chamber's own earliest speed test shows it was close to its specification then, and the
    maintenance log records work on it since the last base-pressure entry it had before that work."""
    tests = sorted([r for r in data["speed"] if r["chamber"] == cid], key=lambda r: r["date"])
    if not tests:
        return False
    first = tests[0]
    p_then = float(first["p_without_flow_mbar"])
    reg = [r for r in data["register"] if r["chamber"] == cid][0]
    sound_then = p_then <= 2.0 * float(reg["p_spec_mbar"])
    work = [r for r in data["maint"] if r["chamber"] == cid and r["date"] > first["date"]
            and r["date"] <= AUDIT]
    return bool(sound_then and work)


def _trapped_from_one(rows, cfg):
    r = rows[-1]
    return max(r["residual"], 0.0) * math.exp(r["t_h"] / 9.0)


def main(argv):
    if len(argv) < 2:
        print(__doc__ % REF_H)
        return 2
    data_dir, out_csv = argv[0], argv[1]
    vac = argv[2] if len(argv) > 2 else "/app/vacwork"
    if not os.path.isdir(vac):
        vac = None
    data = load_data(data_dir)
    certs = data["certs"]
    fix = crossed_serials(data, certs)
    ids = sorted({r["chamber"] for r in data["register"]})
    out = [audit_chamber(cid, data, certs, fix, vac) for cid in ids]
    with open(out_csv, "w") as f:
        f.write("chamber,cause,q_total_mbarl_s,s_eff_l_s\n")
        for r in out:
            f.write("%s,%s,%.4e,%.1f\n" % (r["chamber"], r["cause"], r["q_total"], r["s_eff"]))
    if os.environ.get("DIAGNOSE_VERBOSE"):
        for r in out:
            print("%s %-16s q=%.4e s=%7.1f rated=%7.1f  %s" % (
                r["chamber"], r["cause"], r["q_total"], r["s_eff"], r["s_rated"],
                " ".join("%s=%.2e" % (k[:4], v) for k, v in r["parts"].items() if v > 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
