"""Reference solution for the base-pressure audit.

    python3 -I diagnose.py DATA_DIR OUT_CSV [VACWORK_DIR]

For each chamber of the register it writes the cause, the total gas load and the effective pumping speed at MS-BP's
reference condition.

Method, per chamber:

1. **The chamber as it stands.** The register entry, changed by every maintenance log row on or before the audit
   date: internal surfaces replaced, seal material or length changed, a trap or baffle fitted in the high-vacuum
   port. The pump is the one the turbo controller's own figures identify, which need not be the register's.

2. **The instruments.** Where a gauge's serial in the log is owned by another chamber's certificate and that
   chamber's log carries this chamber's serial on the same dates, the two are read back the right way round. A
   cold cathode is checked against the ionization gauge wherever both were read, and a drift in their ratio is
   carried to the pumpdowns the reference instrument did not see. A certificate is out when the throughput
   tests read on that gauge report a speed the pump and port cannot have: above rated, which clause 4 rules out,
   or below it while the controller shows the pump in order, which by the vacuum data delivers its rated speed.
   The readings of that gauge, and the speeds of those tests, are put right by the same factor.

3. **The speed.** The pump curves are flat at base pressure, so the speed is one constant between the dates on
   which it can change: a trap fitted in the port, and the turbo becoming another pump. The speed now is the
   ordered test's, or the latest shop test since the last such date; a contractor's test is read on its own gauge,
   whose factor its report states, and owes nothing to the chamber's certificate. Where neither exists, the speed
   now is found with the gas budget, below.

4. **The observations.** Every kept base-pressure entry is an observation of the gas load, whichever pump or port
   it was taken with, at the speed in force on its date: the gas load does not depend on the pump. Entries are kept
   from the last change of internals onwards; a seal change does not void them, since the seal in place on each
   date is known. An ordered analysis or rate-of-rise test is one more observation at its own pumping time and wall
   temperature, and a helium test is an observation of the leak.

5. **The gas budget.** Fitted over the observations as clause 3 gives it:

       Q_i = C_w W_i + Q_L + Q_v0 exp(-t_i / tau) [on and after the trapped volume's date] + Q_perm,i

   with W_i the outgassing table's nominal wall load for the entry's surfaces, fixtures, vent gas and wall
   temperature, and Q_perm,i the seal's permeation at its wall temperature. A gauge reading needs clause 5's
   correction for composition, which depends on the split, so it is iterated to a fixed point. Each observation is
   weighted by its own repeatability.

6. **Which budget.** Every structure the records leave open is fitted: no trapped volume, or one present from the
   start, or one that appeared on a date the maintenance log records work on the chamber; and the register's seal
   material, or another in its place. The fit with the least AIC is kept, with the small-sample correction (AICc)
   wherever the sample allows it: a chamber with few observations since its last change would otherwise take a
   trapped volume on a single degree of freedom. Setting the register's seal aside costs
   OVERRIDE_CHI2, so it happens only where the records plainly contradict it. A structure is admissible only where
   it leaves at least one observation over its parameters: a budget that fits every observation exactly has not
   been tested by any of them.

7. **Referring to the audit condition.** The fitted budget is evaluated at %s h, 20 C, an air vent and no load,
   and the cause is named by MS-BP clause 6 against the rated speed of the chamber as it is now.
"""
import csv
import json
import math
import os
import sys

REF_H = 36.0
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
    denom = sum(x * GAS_FACTOR[k] for k, x in mix.items())      # the gauge reads sum_i K_i p_i
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
               turbo_register=r0["turbo"], seal_register=r0["seal_material"], seal_logged_from=None)
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
            if cfg["seal_logged_from"] is None:
                cfg["seal_logged_from"] = row["date"]
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


def speed_test_points(cid, cfg, data, certs):
    """Each shop speed test's no-flow pressure, as a base-pressure reading: the empty chamber at the end of a
    pumpdown after an air vent, at the test's own pumping time and wall temperature, read on the test's gauge. The
    test's own reported speed goes with it, since the two were measured together."""
    pts = []
    for r in data["speed"]:
        if r["chamber"] != cid or r["date"] > AUDIT:
            continue
        if cfg["internals_from"] and r["date"] < cfg["internals_from"]:
            continue
        serial = r["gauge"]
        if serial not in certs:
            continue
        pts.append(dict(date=r["date"], pd="speed test", vent="air", t_h=float(r["pumping_time_h"]),
                        t_k=float(r["wall_temp_c"]) + 273.15,
                        p_n2=float(r["p_without_flow_mbar"]) * cert_factor(certs, serial, r["date"]),
                        load="", serial=serial, reference=False, s_test=float(r["s_eff_l_s"])))
    return pts


def _day_number(date):
    import datetime
    y, m, d = map(int, date.split("-"))
    return datetime.date(y, m, d).toordinal()


def correct_drift(pts, cid, data):
    """Where a chamber carries both gauge types, the cold cathode is checked against the reference instrument on
    every pumpdown both were read on. A cold cathode that fouls reads progressively low, so the ratio is fitted as
    a straight line in days and carried forward to the pumpdowns the reference instrument did not see, whose
    cold cathode readings are corrected by it; a reading from before the first pairing (a speed test's, say) is
    taken at the first pairing's ratio. Where the two agree, nothing is changed."""
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
        # the line is carried forward, never back: before the first pumpdown both gauges were read on there is no
        # evidence of drift, so a reading from then is taken at the ratio of that first pairing
        ratio = a + b * max(_day_number(p["date"]), obs[0][0])
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


READ_SD = 0.006                     # the shop's gauge readings repeat to 0.6 per cent (records_format.md)
SPEED_OB_SD = 0.009                 # a speed test's no-flow pressure times its own speed: the pressure's 0.5 per
                                    # cent and the speed's, which shares that pressure, together
TEST_SD = {"rga": 0.010, "rate-of-rise": 0.005, "speed-test": 0.005}
HELIUM_SD = 0.03                    # a helium test's leak, relative
TAU_MAX = 48.0                      # MS-BP clause 3.3: no trapped volume of the shop takes longer to empty
TAUS = [math.exp(i * math.log(TAU_MAX) / 47.0) for i in range(48)]     # 1 h to TAU_MAX, log-spaced
OVERRIDE_CHI2 = 10.0                # how much better a seal other than the register's must fit to be believed


def _seal_for(cfg, date, register_seal):
    """The seal on a date. Where the maintenance log records a change of material, that is what was fitted. Before
    any such record the material is the register's, unless the fit is testing another in its place."""
    mat, cm = seal_at(cfg, date)
    logged = cfg.get("seal_logged_from")
    if register_seal and (logged is None or date < logged):
        mat = register_seal
    return mat, cm


def fit_budget(cfg, obs, structure, s_now, helium=None):
    """The gas budget of MS-BP clause 3, fitted to the observations for one structure:

        Q_i = C_w W_i + Q_L + Q_v0 exp(-t_i / tau) [on and after the trapped volume's date] + Q_perm,i

    W_i is the outgassing table's nominal wall load for the entry's surfaces, fixtures, vent and temperature, and
    Q_perm,i the seal's permeation at its temperature. Every coefficient is non-negative; tau is searched on a grid
    and settled between its neighbours, and the rest is linear. Each observation is weighted by its own repeatability, relative to its size. A gauge
    reading needs clause 5's correction for composition, which depends on the split, so the correction is iterated
    to a fixed point. A helium test, where there is one, measures Q_L and enters as one more observation of it.

    Returns (chi2, number of parameters, the parameters, the observations' gas loads)."""
    import numpy as np
    from scipy.optimize import nnls
    seal = structure.get("seal")
    trap_from = structure.get("trapped_from")
    n = len(obs)
    W = np.array([nominal_wall(cfg, o) for o in obs])
    mats = [_seal_for(cfg, o["date"], seal) for o in obs]
    PM = np.array([q_perm(m, cm, o["t_k"]) for (m, cm), o in zip(mats, obs)])
    H = np.array([o["t_h"] for o in obs])
    TR = np.array([1.0 if trap_from is not None and o["date"] >= trap_from else 0.0 for o in obs])
    SD = np.array([o["sd"] for o in obs])
    S = np.array([s_now if o["speed"] == "now" else o["speed"] for o in obs], dtype=float)
    G = np.array([1.0 if o["gauge"] else 0.0 for o in obs])
    taus = TAUS if trap_from is not None else [None]
    corr = np.ones(n)
    best = None
    for _ in range(40):
        q = np.array([o["value"] for o in obs]) * np.where(G > 0, corr, 1.0) * S
        w = 1.0 / (q * SD)
        best = None
        profile = []
        for tau in taus:
            cols = [W, np.ones(n)] + ([TR * np.exp(-H / tau)] if tau is not None else [])
            A = np.column_stack(cols) * w[:, None]
            b = (q - PM) * w
            if helium is not None:
                sd_l = max(HELIUM_SD * helium, 2e-9)
                row = np.zeros(A.shape[1])
                row[1] = 1.0 / sd_l
                A = np.vstack([A, row])
                b = np.append(b, helium / sd_l)
            x, rn = nnls(A, b)
            profile.append((rn, x, tau))
            if best is None or rn < best[0]:
                best = (rn, x, tau)
        if tau_flat(profile):
            # nothing in the observations measures how fast the trapped volume empties: every time constant fits
            # as well as every other, and the grid's minimum is a draw of the noise. Clause 3.3's bound is taken
            # instead, a statement of what is not known rather than an estimate
            best = profile[-1]
        elif best[2] is not None:
            # the grid finds the valley; the time constant is then settled inside it, between the grid points on
            # either side, since a few per cent in tau is a few per cent in the trapped load at the reference
            i = [t for _r, _x, t in profile].index(best[2])
            lo, hi = profile[max(i - 1, 0)][2], profile[min(i + 1, len(profile) - 1)][2]

            def solve_at(tau):
                cols = [W, np.ones(n), TR * np.exp(-H / tau)]
                A = np.column_stack(cols) * w[:, None]
                b = (q - PM) * w
                if helium is not None:
                    sd_l = max(HELIUM_SD * helium, 2e-9)
                    row = np.zeros(A.shape[1])
                    row[1] = 1.0 / sd_l
                    A = np.vstack([A, row])
                    b = np.append(b, helium / sd_l)
                return nnls(A, b)

            lt, _ = _golden(lambda lt: solve_at(math.exp(lt))[1], math.log(lo), math.log(hi))
            x_r, rn_r = solve_at(math.exp(lt))
            if rn_r <= best[0]:
                best = (rn_r, x_r, math.exp(lt))
        rn, x, tau = best
        new = np.ones(n)
        for i in range(n):
            if not G[i]:
                continue
            parts = {"wall-outgassing": x[0] * W[i], "air-leak": x[1], "permeation": PM[i]}
            if tau is not None:
                parts["virtual-leak"] = x[2] * TR[i] * math.exp(-H[i] / tau)
            new[i] = gas_correction(parts, mats[i][0])
        done = float(np.max(np.abs(new - corr))) < 1e-9
        corr = new
        if done:
            break
    rn, x, tau = best
    params = dict(c_w=float(x[0]), leak=float(x[1]), qv0=float(x[2]) if tau is not None else 0.0, tau=tau,
                  seal=seal, trapped_from=trap_from, s_now=s_now)
    k = 2 + (2 if trap_from is not None else 0)
    return float(rn * rn), k, params, q


def tau_flat(profile):
    """Whether a fit's misfit over the grid of time constants is flat: within one unit of chi-square everywhere,
    which is the width of a one-sigma interval on a single parameter."""
    if len(profile) < 2:
        return False
    c = [rn * rn for rn, _x, _t in profile]
    return max(c) - min(c) < 1.0


def _golden(f, lo, hi, iters=40):
    """Minimises f over [lo, hi] by golden section."""
    g = (math.sqrt(5.0) - 1.0) / 2.0
    a, b = lo, hi
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = f(d)
    return (c, fc) if fc < fd else (d, fd)


def candidate_structures(cid, cfg, data, obs):
    """Every structure the records leave open. The seal is the documents' unless another material is tried in the
    register's place; a trapped volume is absent, or present from the start, or appeared on a date the maintenance
    log records work on this chamber within the span of the records."""
    seals = [None] + [m for m in sorted(SEALS) if m != cfg["seal_register"]]
    lo, hi = min(o["date"] for o in obs), max(o["date"] for o in obs)
    worked = sorted({r["date"] for r in data["maint"] if r["chamber"] == cid and lo < r["date"] <= hi})
    traps = [None, "0000-00-00"] + worked
    return [dict(seal=sm, trapped_from=tf) for sm in seals for tf in traps]


class Underdetermined(Exception):
    """The records leave fewer observations than the simplest budget has parameters."""


def choose_budget(cid, cfg, data, obs, s_now, s_range=None, helium=None):
    """Fits every candidate structure and keeps the one with the least AICc, falling back to AIC only where no
    structure leaves the two degrees of freedom AICc needs. A structure is admissible only where
    there are more observations than parameters: a budget that passes through every observation exactly has not
    been tested by any of them. Overturning the register's seal costs OVERRIDE_CHI2:
    an engineer does not set the register aside on a marginal fit, but does when the records plainly contradict it.
    Where the pump has changed since its last speed test, the speed now is one more parameter, found with the rest."""
    n = len(obs) + (1 if helium is not None else 0)
    best = None
    for st in candidate_structures(cid, cfg, data, obs):
        k = 2 + (2 if st["trapped_from"] is not None else 0) + (1 if s_now is None else 0)
        if n <= k:
            continue
        if s_now is None:
            lo, hi = s_range

            def f(ls):
                return fit_budget(cfg, obs, st, math.exp(ls), helium)[0]
            ls, _ = _golden(f, math.log(lo), math.log(hi))
            chi2, kk, params, q = fit_budget(cfg, obs, st, math.exp(ls), helium)
        else:
            chi2, kk, params, q = fit_budget(cfg, obs, st, s_now, helium)
        aic = chi2 + 2 * k + (OVERRIDE_CHI2 if st["seal"] else 0.0)
        # the small-sample correction, where the sample allows it; a structure that leaves a single degree of
        # freedom has none, and is weighed against the others only where every structure is in the same case
        aicc = aic + 2.0 * k * (k + 1) / (n - k - 1) if n - k - 1 > 0 else math.inf
        key = (aicc, aic)
        if best is None or key < best[0]:
            best = (key, params, chi2, k)
    if best is None:
        raise Underdetermined("%s: %d observations, too few for any budget" % (cid, n))
    return best[1], best[2], best[3]


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
    permeation answers over minutes, so its signal is a ramp that is still climbing when the hood comes off. A
    region with both shows the step under the ramp, so each trace is split into a background, a fast rise and a
    slow one, and the real leak is the largest fast rise any region shows, converted from the helium rate the detector reads to an air
    rate by HE_AIR. What the test cannot show is a trapped volume, which vents into the chamber and never reaches
    a hood at all: that is why a helium test tells a leak from permeation but leaves the rest of a constant gas
    load unexplained."""
    path = os.path.join(vac, "helium_%s.csv" % cid.lower()) if vac else None
    if not path or not os.path.exists(path):
        return None
    import numpy as np
    from scipy.optimize import nnls
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
        t = np.array([a for a, _ in pts])
        v = np.array([b for _, b in pts])
        # a hooded region can show both at once, a channel's step under a seal's ramp, so the trace is split into
        # the two: a background, a rise that settles in seconds and one that takes minutes, each fitted
        fit = None
        for ta in (2.0, 4.0, 6.0, 8.0, 10.0, 14.0, 20.0):
            for tb in (60.0, 90.0, 120.0, 180.0, 240.0, 360.0, 600.0, 900.0):
                A = np.column_stack([np.ones_like(t), 1.0 - np.exp(-t / ta), 1.0 - np.exp(-t / tb)])
                sc = np.maximum(v, 1e-14)
                x, rn = nnls(A / sc[:, None], v / sc)
                if fit is None or rn < fit[0]:
                    fit = (rn, x)
        best = max(best, float(fit[1][1]))
    return dict(leak=best / HE_AIR)


def ordered_speed(cid, cfg, vac):
    """The effective speed from an ordered test, with the gas-load observation it carries. The contractor brings
    its own gauge, calibrated against nitrogen, and the report states its factor; its readings owe nothing to the
    chamber's own certificate. A rate-of-rise test is read with a spinning rotor gauge and needs no correction at
    all."""
    if not vac:
        return None, None
    sp = os.path.join(vac, "speed_test_%s.csv" % cid.lower())
    if os.path.exists(sp):
        factor = 1.0
        with open(sp) as f:
            lines = f.readlines()
        for line in lines:
            if line.startswith("#") and "factor" in line:
                factor = float(line.rsplit("factor", 1)[1].strip().split()[0])
        rows = [l for l in lines if not l.startswith("#") and not l.startswith("flow")]
        if rows:
            flow, p_w, p_wo, s = (float(x) for x in rows[-1].strip().split(","))
            t_h, t_k = _header_values(sp)
            ob = dict(kind="speed-test", date=AUDIT, t_h=t_h, t_k=t_k, vent="air", load="",
                      value=p_wo * factor, gauge=True, speed=s, sd=TEST_SD["speed-test"])
            return s, ob
    ror = rate_of_rise_says(cid, cfg, vac)
    if ror and ror["p_base"] > 0:
        ob = dict(kind="rate-of-rise", date=AUDIT, t_h=ror["t_h"], t_k=ror["t_k"], vent="air", load="",
                  value=ror["q_total"], gauge=False, speed=1.0, sd=TEST_SD["rate-of-rise"])
        return ror["q_total"] / ror["p_base"], ob
    return None, None


def speed_periods(cid, cfg, data, changed):
    """The dates on which the chamber's speed changed: a trap or baffle fitted in the port, and the turbo becoming
    another pump. Between two of them the speed is one constant (MS-BP clause 4: the pump curves are flat at base
    pressure)."""
    return sorted(d for d in (cfg["trap_from"], changed) if d)


def period_of(date, cuts):
    return sum(1 for c in cuts if date >= c)


def shop_speed_in(cid, data, cuts, period, k):
    """The latest of the shop's own speed tests taken in a period, read back through the certificate of the gauge
    it was read on (k: {serial: the factor that certificate is out by})."""
    rows = [r for r in sorted(data["speed"], key=lambda r: r["date"])
            if r["chamber"] == cid and period_of(r["date"], cuts) == period]
    return float(rows[-1]["s_eff_l_s"]) / k.get(rows[-1]["gauge"], 1.0) if rows else None


# ---------------------------------------------------------------------------------------------------- audit
CERT_SLACK = 0.02                   # a measured speed may sit this far from rated on the test's own scatter


def rated_at(cfg, p=1e-6):
    return series(curve(TURBO[cfg["turbo"]], p), cfg["c_port"])


def with_controller_pump(cid, cfg, data):
    """The configuration with the pump the controller reports, where that is not the pump the register names."""
    model = pump_from_controller(cid, data)
    if model and model != cfg["turbo"]:
        return dict(cfg, turbo=model)
    return cfg


def certificate_error(cid, cfg, data):
    """How far each of a chamber's gauge certificates is out, where one is: {serial: factor}.

    A wrong calibration factor cancels in the gas load: every pressure the certificate yields is off by the same
    factor and every speed it yields is off by its inverse, so Q = p S_eff comes out right and the gas budget fits
    as well as ever. What it cannot do is hide in the speed. MS-BP clause 4 has the chamber's effective speed as
    its pump in series with its port, and the vacuum data say a pump in order delivers its rated speed. So a
    throughput test read on a gauge whose certificate is out reports a speed the pump and port cannot have: above
    rated, which no pump delivers, or below it while the pump is in order. The ratio of the reported speed to the
    rated speed is the factor that gauge's certificate is out by.

    Tests are grouped by the gauge they were read on, since a chamber whose gauge was replaced has a certificate
    for each. A test taken before a trap was fitted measured a larger port, and one taken after the turbo changed
    measured another pump; neither is evidence about a certificate."""
    rated = rated_at(cfg)
    changed = pump_changed_on(cid, data)
    by = {}
    for r in data["speed"]:
        if r["chamber"] != cid:
            continue
        if cfg["trap_from"] and r["date"] < cfg["trap_from"]:
            continue
        if changed and r["date"] >= changed:
            continue
        by.setdefault(r["gauge"], []).append(float(r["s_eff_l_s"]) / rated)
    out = {}
    for serial, ratios in by.items():
        k = sum(ratios) / len(ratios)
        if abs(k - 1.0) > CERT_SLACK:
            out[serial] = k
    return out


def front_end(cid, data, certs, fix, vac):
    """The chamber as it stands, the observations of its gas load and the speed in force on each: everything the
    audit settles before it attributes the gas load to a mechanism.

    This is a function rather than the first half of `audit_chamber` because the authoring studies need exactly
    the audit's own front end. A study that keeps its own copy measures the copy: when the copy falls behind, the
    study reports its own drift as a finding.

    Every kept entry is an observation, whichever pump or port it was taken with: the gas load does not depend on
    the pump. What does is the speed it is multiplied by, so each entry takes the speed in force on its date. The
    speed now is the ordered test's, or the latest shop test since the last change; failing both it is left to the
    fit (`None`), with the range it may lie in."""
    cfg = with_controller_pump(cid, chamber_config(cid, data), data)
    changed = pump_changed_on(cid, data)
    # the certificate is checked first, because every pressure and every reported speed of this chamber has to be
    # put right by the same factor before anything is fitted
    k = certificate_error(cid, cfg, data)
    cuts = speed_periods(cid, cfg, data, changed)
    now = period_of(AUDIT, cuts)
    s_now, order_ob = ordered_speed(cid, cfg, vac)
    if s_now is None:
        s_now = shop_speed_in(cid, data, cuts, now, k)

    pts = correct_drift(entry_points(cid, cfg, data, certs, fix), cid, data)
    if k:
        # only the readings taken with a gauge whose certificate is out need putting right; a chamber's other
        # gauges, the reference instrument of clause 5 among them, were never affected
        pts = [dict(q, p_n2=q["p_n2"] * k.get(q["serial"], 1.0)) for q in pts]
    obs = []
    for p in pts:
        per = period_of(p["date"], cuts)
        speed = "now" if per == now else shop_speed_in(cid, data, cuts, per, k)
        if speed is None:
            continue                                  # a period with no speed test describes nothing usable
        obs.append(dict(kind="entry", date=p["date"], t_h=p["t_h"], t_k=p["t_k"], vent=p["vent"],
                        load=p["load"], value=p["p_n2"], gauge=True, speed=speed, sd=READ_SD,
                        serial=p["serial"]))
    # a speed test is a base-pressure reading as well as a speed: its no-flow pressure, read at its own pumping
    # time, is often the only reading a chamber has at any but its usual pumping time
    for p in correct_drift(speed_test_points(cid, cfg, data, certs), cid, data):
        f = k.get(p["serial"], 1.0) if k else 1.0
        obs.append(dict(kind="speed-test", date=p["date"], t_h=p["t_h"], t_k=p["t_k"], vent="air", load="",
                        value=p["p_n2"] * f, gauge=True, speed=p["s_test"] / f, sd=SPEED_OB_SD,
                        serial=p["serial"]))
    if order_ob is not None:
        obs.append(order_ob)
    rga = rga_says(cid, vac)
    if rga:
        # an analyser's partial pressures are true pressures: their sum is the whole pressure at the test's own
        # pumping time and wall temperature, with no correction for composition, and times the speed now it is the
        # gas load there
        obs.append(dict(kind="rga", date=AUDIT, t_h=rga["t_h"], t_k=rga["t_k"], vent="air", load="",
                        value=sum(rga["pp"].values()), gauge=False, speed="now", sd=TEST_SD["rga"]))
    rated = rated_at(cfg)
    return cfg, obs, s_now, (0.05 * rated, 1.2 * rated)


def at_reference(cfg, params):
    """The gas budget evaluated at MS-BP's reference condition: REF_H hours after an air vent, 20 C, no load, with
    the chamber's internal surfaces and seal as they are on the audit date."""
    qw = params["c_w"] * q_wall_nominal(cfg["surfaces"], REF_H, "air", T_REF)
    mat, cm = _seal_for(cfg, AUDIT, params["seal"])
    qp = q_perm(mat, cm, T_REF)
    qv = params["qv0"] * math.exp(-REF_H / params["tau"]) if params["qv0"] and params["tau"] else 0.0
    parts = {"wall-outgassing": qw, "permeation": qp, "air-leak": params["leak"], "virtual-leak": qv}
    return parts, sum(parts.values())


def audit_chamber(cid, data, certs, fix, vac):
    cfg, obs, s_now, s_range = front_end(cid, data, certs, fix, vac)
    hel = helium_says(cid, vac)
    params, chi2, k = choose_budget(cid, cfg, data, obs, s_now, s_range, hel["leak"] if hel else None)
    parts, q_total = at_reference(cfg, params)
    s_eff = params["s_now"]
    s_rated = rated_at(cfg)
    cause = "pump-speed" if s_eff < PUMP_GATE * s_rated else max(parts, key=lambda k: parts[k])
    return dict(chamber=cid, cause=cause, q_total=q_total, s_eff=s_eff, parts=parts, s_rated=s_rated,
                params=params, chi2=chi2, n_obs=len(obs))


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
