"""A second audit, written from the documents alone and sharing no code with the reference solution.

It is meant to fail where the reference is wrong, so wherever the reference makes a decision this one makes it a
different way:

- **The gas budget** is one nonlinear least squares in the logarithm of every parameter at once - the wall
  coefficient, the leak, a trapped volume and its time constant, and the speed now where no test gives it - with
  MS-BP clause 5's correction evaluated inside the residual. The reference searches the time constant on a grid,
  solves the rest linearly and iterates the correction outside.
- **Which budget** is chosen by the Bayesian information criterion, where the reference uses Akaike's.
- **The seal** is tested with a free permeation scale, fitted continuously and adopted as another table material
  only where it is well determined and lies near one. The reference tries each material with a fixed penalty.
- **A changed turbo** is found by a changepoint in the bearing temperature, judged against the series' own scatter;
  the reference uses fixed steps in drive power and temperature.
- **The pump fitted** is the model nearest the median of every controller row before any change, where the
  reference averages the first four rows and applies an acceptance bound.
- **A gauge certificate** is called out only when the throughput tests sit above the rated speed by more than three
  standard errors of their stated repeatability, where the reference uses a fixed slack.
- **A fouling cold cathode** is corrected by its fitted ratio to the ionization gauge whenever both were read, with
  no threshold on the size of the trend.

    audit_all(data_dir, vacwork_dir) -> {chamber: (cause, q_total, s_eff)}
"""
import csv
import math
import os

import numpy as np
from scipy.optimize import least_squares, nnls

REF_HOURS = 36.0
T0 = 293.15
RGAS = 8.3145
EW = 30.0e3
EP = 42.0e3
VENT_N2 = 0.25
GATE = 0.75
AUDIT_DATE = "2026-11-02"

PUMPS = {
    "TMP-400": ((1e-9, 360.0), (1e-3, 360.0), (1e-2, 250.0), (5e-2, 100.0), (2e-1, 28.0)),
    "TMP-700": ((1e-9, 640.0), (1e-3, 640.0), (1e-2, 420.0), (5e-2, 160.0), (2e-1, 40.0)),
    "TMP-1100": ((1e-9, 1010.0), (1e-3, 1010.0), (1e-2, 640.0), (5e-2, 230.0), (2e-1, 55.0)),
    "TMP-1600": ((1e-9, 1480.0), (1e-3, 1480.0), (1e-2, 900.0), (5e-2, 310.0), (2e-1, 70.0)),
}
SURF = {
    "stainless steel, electropolished": (7.0e-9, 1.00),
    "stainless steel, as machined": (2.6e-8, 1.00),
    "stainless steel, bead blasted": (6.5e-8, 0.95),
    "aluminum, bare": (1.4e-8, 1.00),
    "aluminum, anodized": (5.5e-7, 0.85),
    "copper, bare": (2.2e-8, 1.00),
    "PEEK": (3.5e-7, 0.60),
    "graphite felt": (9.0e-7, 0.70),
}
ELAST = {
    "fluoroelastomer": (1.15e-7, (1.00, 3.00, 0.35, 12.0)),
    "nitrile": (3.40e-7, (1.00, 2.60, 0.40, 10.0)),
    "perfluoroelastomer": (4.20e-8, (1.00, 2.80, 0.30, 11.0)),
}
CTRL = {
    "TMP-400": (1000.0, 60.0, 38.0),
    "TMP-700": (820.0, 95.0, 42.0),
    "TMP-1100": (700.0, 130.0, 45.0),
    "TMP-1600": (600.0, 170.0, 48.0),
}
DRY_AIR = (0.7808, 0.2095, 0.00934, 0.00042)            # n2, o2, ar, co2
# vacuum_data.md: each gauge type's sensitivity, by its serial's prefix
SENS = {"IG": dict(h2=0.42, h2o=1.12, n2=1.00, o2=1.01, ar=1.29, co2=1.42),
        "CC": dict(h2=0.46, h2o=0.80, n2=1.00, o2=0.94, ar=1.12, co2=1.30)}
WALL_GAS = dict(h2o=0.960, h2=0.015, n2=0.025)
KIT = {
    "carrier set A": (2.4, "stainless steel, as machined"),
    "carrier set B": (1.6, "stainless steel, bead blasted"),
    "lens rack": (0.55, "aluminum, anodized"),
    "braze fixture": (2.1, "stainless steel, bead blasted"),
    "shield set": (1.8, "aluminum, bare"),
    "harness tray": (0.30, "PEEK"),
}
ORDER = ["h2", "h2o", "n2", "o2", "ar", "co2"]


def rows_of(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def speed_curve(pump, p):
    pts = PUMPS[pump]
    lx = [math.log10(a) for a, _ in pts]
    ly = [b for _, b in pts]
    return float(np.interp(math.log10(max(p, 1e-12)), lx, ly))


def arrhenius(energy, t_c):
    return math.exp(energy / RGAS * (1.0 / T0 - 1.0 / (t_c + 273.15)))


def wall_shape(surfaces, hours, vent, t_c):
    """The outgassing table's nominal gas load for these surfaces at this condition."""
    acc = 0.0
    for area, kind in surfaces:
        q1, alpha = SURF[kind]
        acc += area * 1e4 * q1 * max(hours, 0.05) ** -alpha
    return acc * (VENT_N2 if vent != "air" else 1.0) * arrhenius(EW, t_c)


def perm_load(seal, cm, t_c):
    return ELAST[seal][0] * cm * arrhenius(EP, t_c)


def perm_species(seal):
    rel = ELAST[seal][1]
    raw = [a * r for a, r in zip(DRY_AIR, rel)]
    tot = sum(raw)
    return dict(zip(("n2", "o2", "ar", "co2"), [v / tot for v in raw]))


def mixture(wall, perm, channel, seal, kind="IG"):
    """Species fractions of a gas made of the three sources, and the pressure a gauge of the given type would
    indicate for one unit of true pressure."""
    acc = {k: 0.0 for k in ORDER}
    total = wall + perm + channel
    if total <= 0:
        return acc, 1.0
    for k, v in WALL_GAS.items():
        acc[k] += wall / total * v
    for k, v in perm_species(seal).items():
        acc[k] += perm / total * v
    for k, v in zip(("n2", "o2", "ar", "co2"), DRY_AIR):
        acc[k] += channel / total * v
    shown = sum(x * SENS[kind][k] for k, x in acc.items())      # a gauge reads sum K_i p_i, K its type's
    return acc, shown


def shop(data_dir):
    d = dict(reg=rows_of(os.path.join(data_dir, "chamber_register.csv")),
             log=rows_of(os.path.join(data_dir, "base_pressure_log.csv")),
             spd=rows_of(os.path.join(data_dir, "speed_tests.csv")),
             ctl=rows_of(os.path.join(data_dir, "turbo_controller.csv")),
             mnt=rows_of(os.path.join(data_dir, "maintenance_log.csv")))
    d["cert"] = certificates(os.path.join(data_dir, "gauge_certificates.md"))
    d["leak_std"] = leak_standard(d)
    if d["leak_std"]:
        since, factor = d["leak_std"]
        d["spd"] = [dict(r, s_eff_l_s=str(float(r["s_eff_l_s"]) / factor)) if r["date"] >= since else r
                    for r in d["spd"]]
    return d


def certificates(path):
    out, tag = {}, None
    for line in open(path):
        line = line.strip()
        if line.startswith("## "):
            tag = line[3:]
            out[tag] = dict(owner=None, points=[])
        elif tag and "installed on chamber" in line:
            out[tag]["owner"] = line.rstrip(".").split()[-1]
        elif tag and line.startswith("| 20"):
            bits = [c.strip() for c in line.strip("|").split("|")]
            if len(bits) == 2:
                try:
                    out[tag]["points"].append((bits[0], float(bits[1])))
                except ValueError:
                    pass
    for v in out.values():
        v["points"].sort()
    return {k: v for k, v in out.items() if v["points"]}


def factor_on(cert, tag, date):
    pts = cert[tag]["points"]
    val = pts[0][1]
    for d, f in pts:
        if d <= date:
            val = f
    return val


def state_on(cid, data, date):
    """The chamber as the register and the maintenance log leave it on a date."""
    mine = [r for r in data["reg"] if r["chamber"] == cid]
    head = mine[0]
    st = dict(volume=float(head["volume_l"]), pump=head["turbo"], port=float(head["c_port_l_s"]),
              seal=head["seal_material"], seal_cm=float(head["seal_length_cm"]),
              surfaces=[(float(r["surface_area_m2"]), r["surface"]) for r in mine],
              spec=float(head["p_spec_mbar"]), relined=None, ported=None, seal_register=head["seal_material"],
              seal_logged=None, port_register=float(head["c_port_l_s"]))
    fitted = pump_fitted(cid, data)
    if fitted:
        st["pump"] = fitted
    for row in sorted([r for r in data["mnt"] if r["chamber"] == cid], key=lambda r: r["date"]):
        if row["date"] > date:
            continue
        txt = row["entry"]
        if "Internal surfaces after the work:" in txt:
            spec = txt.split("Internal surfaces after the work:", 1)[1].strip().rstrip(".")
            st["surfaces"] = []
            for piece in spec.split(";"):
                area, kind = piece.strip().split(" m2 ", 1)
                st["surfaces"].append((float(area), kind.strip()))
            st["relined"] = row["date"]
        if "Port conductance after the work:" in txt:
            st["port"] = float(txt.split("Port conductance after the work:", 1)[1].strip().split()[0])
            st["ported"] = row["date"]
        elif "fitted in the high-vacuum port" in txt:
            st["port"] = None                 # nobody recorded its conductance: the port has to be measured
            st["ported"] = row["date"]
        if "Seal material after the work:" in txt:
            st["seal"] = txt.split("Seal material after the work:", 1)[1].strip().rstrip(".")
            st["seal_logged"] = st["seal_logged"] or row["date"]
        if "Seal length after the work:" in txt:
            st["seal_cm"] = float(txt.split("Seal length after the work:", 1)[1].strip().split()[0])
    return st


READ_REPEAT = 0.006                 # records_format.md: the shop's gauge readings repeat to 0.6 per cent
SPEED_REPEAT = 0.007                # and a throughput test's speed, from two pressures each repeating to 0.5
ORDER_REPEAT = {"rga": 0.010, "rate-of-rise": 0.005, "speed-test": 0.005}
TAU_LONGEST = 48.0                  # MS-BP clause 3.3


def _ctrl(cid, data):
    return sorted([r for r in data["ctl"] if r["chamber"] == cid], key=lambda r: r["date"])


def turbo_altered(cid, data):
    """The date the controller shows the turbo became another pump: the split of the bearing temperature series
    with the largest step, accepted where that step is more than ten standard errors of the series' own scatter."""
    seq = _ctrl(cid, data)
    t = np.array([float(r["bearing_temp_c"]) for r in seq])
    best = None
    for i in range(2, len(t) - 1):
        a, b = t[:i], t[i:]
        sd = math.sqrt((np.var(a, ddof=1) * (len(a) - 1) + np.var(b, ddof=1) * (len(b) - 1)) / (len(t) - 2))
        z = abs(b.mean() - a.mean()) / (max(sd, 1e-9) * math.sqrt(1.0 / len(a) + 1.0 / len(b)))
        if best is None or z > best[0]:
            best = (z, seq[i]["date"])
    return best[1] if best and best[0] > 10.0 else None


def pump_fitted(cid, data):
    """The pump the controller's figures say is turning, which a register can get wrong: the model nearest the
    median of every row before the turbo changed."""
    seq = _ctrl(cid, data)
    if not seq:
        return None
    alt = turbo_altered(cid, data)
    seq = [r for r in seq if not alt or r["date"] < alt] or seq
    got = [float(np.median([float(r[k]) for r in seq])) for k in ("rotor_hz", "drive_power_w", "bearing_temp_c")]
    return min(CTRL, key=lambda m: sum(((g - n) / n) ** 2 for g, n in zip(got, CTRL[m])))


def swapped_tags(data):
    """Pumpdowns whose gauge tag belongs to another chamber while that chamber's log carries this chamber's tag:
    the certificates are right, so the two are read back the right way round."""
    seen, owned = {}, {}
    for r in data["log"]:
        seen.setdefault(r["chamber"], set()).add(r["gauge"])
    for tag, v in data["cert"].items():
        owned.setdefault(v["owner"], set()).add(tag)
    out = {}
    for cid, tags in seen.items():
        for tag in tags:
            holder = data["cert"].get(tag, {}).get("owner")
            if holder in (None, cid):
                continue
            shared = owned.get(cid, set()) & seen.get(holder, set())
            if shared:
                right = sorted(shared)[0]
                for r in data["log"]:
                    if r["chamber"] == cid and r["gauge"] == tag:
                        out[(cid, r["date"], r["pumpdown"])] = right
    return out


def _ord(date):
    import datetime
    return datetime.date(*map(int, date.split("-"))).toordinal()


def _cc_line(cid, data, comp):
    """The cold cathode's ratio to the ionization gauge on the pumpdowns both read, as a line in days, with each
    ratio's share that comes from the gas's composition divided out (`comp`, by pumpdown; one where unknown)."""
    pairs = {}
    for r in [x for x in data["log"] if x["chamber"] == cid]:
        pairs.setdefault((r["date"], r["pumpdown"]), {})[r["gauge"][:2]] = float(r["reading_mbar"])
    both = [(_ord(d), v["CC"] / v["IG"] / comp.get((d, p_), 1.0)) for (d, p_), v in sorted(pairs.items())
            if "CC" in v and "IG" in v]
    line = np.polyfit([x for x, _ in both], [y for _, y in both], 1) if len(both) >= 2 else None
    return both, line


def readings(cid, data, st, swaps, comp=None, every=False):
    """The readings since the chamber was last relined. With `every` false, one per pumpdown, preferring the
    ionization gauge, which audit_note.md makes the reference instrument; with it true, every reading on a
    pumpdown read with both types too, which is what lets the fit see the gas's composition. A cold cathode
    reading on a pumpdown without the ionization gauge is corrected by the fitted line of its ratio to that gauge,
    composition divided out, wherever both were ever read."""
    mine = [r for r in data["log"] if r["chamber"] == cid and r["date"] <= AUDIT_DATE]
    if st["relined"]:
        mine = [r for r in mine if r["date"] >= st["relined"]]
    groups = {}
    for r in mine:
        groups.setdefault((r["date"], r["pumpdown"]), []).append(r)
    _both, line = _cc_line(cid, data, comp or {})
    out = []
    for (date, pd), group in sorted(groups.items()):
        hot = [r for r in group if r["gauge"].startswith("IG")]
        picks = group if (every and hot) else [hot[0] if hot else sorted(group, key=lambda r: r["gauge"])[0]]
        for pick in picks:
            tag = swaps.get((cid, date, pd), pick["gauge"]) if pick["gauge"].startswith("CC") else pick["gauge"]
            if tag not in data["cert"]:
                continue
            shown = float(pick["reading_mbar"]) * factor_on(data["cert"], tag, date)
            if not hot and line is not None and tag.startswith("CC"):
                shown /= float(np.polyval(line, _ord(date)))
            out.append(dict(date=date, hours=float(pick["pumpdown_h"]), t_c=float(pick["wall_temp_c"]),
                            vent=pick["vent_gas"], load=pick["load"].strip(), shown=shown, tag=tag, pd=pd,
                            paired=bool(hot) and len(group) > 1))
    return out


def test_readings(cid, data, st, comp=None):
    """Each shop speed test's no-flow pressure as one more reading: the empty chamber after an air vent, at the
    test's pumping time and wall temperature, with the speed that test measured. A cold cathode that has drifted is
    corrected as in readings(); before the first pumpdown both gauges were read on, it is taken as it was then."""
    both, line = _cc_line(cid, data, comp or {})
    out = []
    for r in data["spd"]:
        if r["chamber"] != cid or r["date"] > AUDIT_DATE or (st["relined"] and r["date"] < st["relined"]):
            continue
        tag = r["gauge"]
        if tag not in data["cert"]:
            continue
        shown = float(r["p_without_flow_mbar"]) * factor_on(data["cert"], tag, r["date"])
        if line is not None and tag.startswith("CC"):
            shown /= float(np.polyval(line, max(_ord(r["date"]), both[0][0])))
        out.append(dict(date=r["date"], hours=float(r["pumping_time_h"]), t_c=float(r["wall_temp_c"]),
                        vent="air", load="", shown=shown, tag=tag, s_test=float(r["s_eff_l_s"])))
    return out


def surfaces_of(st, load):
    out = list(st["surfaces"])
    if load and load in KIT:
        out.append(KIT[load])
    return out


def rated_of(st, p=1e-6, date=None):
    """The rated speed, on the audit date or on another; None where the port's conductance is not recorded."""
    port = st["port_register"] if (date and st["ported"] and date < st["ported"]) else st["port"]
    if port is None:
        return None
    pump = speed_curve(st["pump"], p)
    return pump * port / (pump + port)


def leak_standard(data):
    """Whether the shop's calibrated leak, which every shop speed test admits, has changed: (from, factor) or None.

    Every test on a chamber whose rated speed is on record, with its pump in order that day, measures the leak's
    real flow against its stated one (a pump in order delivers its rated speed). The change is put where a split of
    those tests in date order gives the largest separation of the two sides' trimmed means, in units of their
    scatter, and the factor is the ratio of those trimmed means. Trimming drops a side's extreme fifth, so a chamber
    whose own certificate is out does not move it."""
    pts = []
    for cid in sorted({r["chamber"] for r in data["reg"]}):
        st = state_on(cid, data, AUDIT_DATE)
        altered = turbo_altered(cid, data)
        for r in data["spd"]:
            if r["chamber"] != cid or (altered and r["date"] >= altered):
                continue
            rated = rated_of(st, date=r["date"])
            if rated:
                pts.append((r["date"], float(r["s_eff_l_s"]) / rated))
    pts.sort()

    def trimmed(v):
        v = sorted(v)
        cut = len(v) // 5
        v = v[cut:len(v) - cut] if len(v) - 2 * cut >= 2 else v
        return float(np.mean(v)), float(np.std(v)) + SPEED_REPEAT

    best = None
    for i in range(3, len(pts) - 2):
        if pts[i][0] == pts[i - 1][0]:
            continue
        (m1, s1), (m2, s2) = trimmed([v for _d, v in pts[:i]]), trimmed([v for _d, v in pts[i:]])
        z = abs(m2 - m1) / math.hypot(s1, s2)
        if best is None or z > best[0]:
            best = (z, pts[i][0], m2 / m1)
    if best is None or best[0] < 5.0:
        return None
    return best[1], best[2]


def cert_out_by(cid, data, st):
    """{gauge tag: how far its certificate is out}. A chamber's throughput tests cannot report a speed its pump in
    series with its port does not deliver (MS-BP clause 4; a pump in order delivers its rated speed, vacuum data).
    Grouped by the gauge each test was read on, where the mean ratio to rated sits off 1 by more than three standard
    errors of the stated repeatability, that ratio is how far the gauge's certificate is out. A test after a trap
    was fitted, or after the turbo changed, measured another configuration and is set aside."""
    rated = rated_of(st)
    if rated is None:
        return {}
    altered = turbo_altered(cid, data)
    by = {}
    for r in data["spd"]:
        if r["chamber"] != cid or (st["ported"] and r["date"] < st["ported"]):
            continue
        if altered and r["date"] >= altered:
            continue
        by.setdefault(r["gauge"], []).append(float(r["s_eff_l_s"]) / rated)
    out = {}
    for tag, vals in by.items():
        k = float(np.mean(vals))
        if abs(k - 1.0) > 3.0 * SPEED_REPEAT / math.sqrt(len(vals)):
            out[tag] = k
    return out


def _cuts(st, altered):
    return sorted(d for d in (st["ported"], altered) if d)


def _period(date, cuts):
    return sum(1 for c in cuts if date >= c)


def shop_speed(cid, data, cuts, period, k):
    """The mean of the shop's speed tests in a period, each read back through its own gauge's certificate."""
    vals = [float(r["s_eff_l_s"]) / k.get(r["gauge"], 1.0) for r in data["spd"]
            if r["chamber"] == cid and _period(r["date"], cuts) == period]
    return float(np.mean(vals)) if vals else None


def _report_head(path):
    hours, t_c, factor = REF_HOURS, 20.0, 1.0
    for line in open(path):
        if not line.startswith("#"):
            break
        if "pumping time" in line:
            hours = float(line.rsplit(":", 1)[1].split()[0])
        elif "wall temperature" in line:
            t_c = float(line.rsplit(":", 1)[1].split()[0])
        elif "factor" in line:
            factor = float(line.rsplit("factor", 1)[1].split()[0])
    return hours, t_c, factor


def _table(path, skip):
    return [l.strip().split(",") for l in open(path) if not l.startswith("#") and not l.startswith(skip)]


def order_observations(cid, st, vac):
    """What an ordered test says about the gas load, and the speed it gives where it gives one. The contractor reads
    on its own gauge, whose factor the report states; nothing of the chamber's certificate enters."""
    obs, s_now, leak = [], None, None
    if not vac:
        return obs, s_now, leak
    f = os.path.join(vac, "speed_test_%s.csv" % cid.lower())
    if os.path.exists(f):
        hours, t_c, factor = _report_head(f)
        flow, p_w, p_wo, s = (float(x) for x in _table(f, "flow")[-1])
        s_now = s
        obs.append(dict(hours=hours, t_c=t_c, vent="air", load="", shown=p_wo * factor, gauge=True,
                        speed=s, sd=ORDER_REPEAT["speed-test"], date=AUDIT_DATE))
    f = os.path.join(vac, "rate_of_rise_%s.csv" % cid.lower())
    if os.path.exists(f):
        hours, t_c, _ = _report_head(f)
        pts = [(float(a), float(b)) for a, b in _table(f, "seconds")]
        win = [q for q in pts if q[0] <= 600.0] or pts
        slope, _intercept = np.polyfit([x for x, _ in win], [y for _, y in win], 1)
        q = slope * st["volume"]
        # the base pressure is the trace's own reading at valve closure, not the line's intercept: the pressure
        # climbs a hundredfold over the window, so the intercept is a long extrapolation of a steep line and is
        # several per cent out on the read noise alone
        s_now = q / pts[0][1]
        obs.append(dict(hours=hours, t_c=t_c, vent="air", load="", shown=q, gauge=False, speed=1.0,
                        sd=ORDER_REPEAT["rate-of-rise"], date=AUDIT_DATE))
    f = os.path.join(vac, "rga_%s.csv" % cid.lower())
    if os.path.exists(f):
        hours, t_c, _ = _report_head(f)
        total = sum(float(v) for _n, _m, v in _table(f, "species"))
        obs.append(dict(hours=hours, t_c=t_c, vent="air", load="", shown=total, gauge=False, speed="now",
                        sd=ORDER_REPEAT["rga"], date=AUDIT_DATE))
    f = os.path.join(vac, "helium_%s.csv" % cid.lower())
    if os.path.exists(f):
        by = {}
        for region, sec, val in _table(f, "region"):
            by.setdefault(region, []).append((float(sec), float(val)))
        step = 0.0
        for pts in by.values():
            pts.sort()
            v = np.array([x for _t, x in pts])
            tt = np.array([t for t, _x in pts])
            # a channel answers in seconds and a seal over minutes. From forty seconds on a channel's step has
            # settled, so the trace there is a constant plus a seal's ramp; that constant, less the reading before
            # the hood went on, is the step, whatever ramp lies over it
            late = tt >= 40.0
            fit = None
            for tb in np.geomspace(40.0, 2000.0, 60):
                X = np.column_stack([np.ones(late.sum()), 1.0 - np.exp(-tt[late] / tb)])
                coef, *_ = np.linalg.lstsq(X, v[late], rcond=None)
                if coef[1] < 0:
                    coef = np.array([v[late].mean(), 0.0])
                r = float(np.sum(((X @ coef) - v[late]) ** 2 / np.maximum(v[late], 1e-14) ** 2))
                if fit is None or r < fit[0]:
                    fit = (r, coef)
            step = max(step, float(fit[1][0] - v[0]))
        leak = max(step, 0.0) / 2.69
    return obs, s_now, leak


def _seal_series(st, date, scale):
    """The seal on a date, and its permeation per unit of the table's figure. Before the log first records a
    material the register's applies, scaled where the fit is testing it."""
    seal, cm = st["seal"], st["seal_cm"]
    before = st["seal_logged"] is None or date < st["seal_logged"]
    if before:
        seal = st["seal_register"]
    return seal, cm, (scale if before else 1.0)


def solve(cid, data, st, obs, s_now, trapped_from, free_perm, speed_range, leak=None, fixed_tau=None):
    """One nonlinear least squares in the logarithm of every parameter. Returns (chi2, parameters, n, k).
    With fixed_tau the time constant is held, and the rest is fitted around it."""
    hist = {}
    for o in obs:
        hist[o["date"]] = state_on(cid, data, o["date"])
    shapes = [wall_shape(surfaces_of(st, o["load"]), o["hours"], o["vent"], o["t_c"]) for o in obs]
    seals = [_seal_series(dict(st, seal=hist[o["date"]]["seal"], seal_cm=hist[o["date"]]["seal_cm"]),
                          o["date"], 1.0) for o in obs]
    base_perm = [perm_load(m, cm, o["t_c"]) for (m, cm, _x), o in zip(seals, obs)]
    in_register = [x != 1.0 or (st["seal_logged"] is None or o["date"] < st["seal_logged"])
                   for (_m, _c, x), o in zip(seals, obs)]
    trapped = [trapped_from is not None and o["date"] >= trapped_from for o in obs]
    names = ["c_w", "leak"] + (["qv0"] if trapped_from else []) + \
            (["tau"] if trapped_from and fixed_tau is None else []) + (["perm"] if free_perm else []) + \
            (["s_now"] if s_now is None else [])

    def unpack(th):
        p = dict(zip(names, [math.exp(x) for x in th]))
        p.setdefault("qv0", 0.0)
        p.setdefault("tau", fixed_tau if trapped_from else None)
        p.setdefault("perm", 1.0)
        p.setdefault("s_now", s_now)
        return p

    def residual(th):
        p = unpack(th)
        res = []
        for i, o in enumerate(obs):
            wall = p["c_w"] * shapes[i]
            pm = base_perm[i] * (p["perm"] if in_register[i] else 1.0)
            chan = p["leak"] + (p["qv0"] * math.exp(-o["hours"] / p["tau"]) if trapped[i] else 0.0)
            true = wall + pm + chan
            speed = p["s_now"] if o["speed"] == "now" else o["speed"]
            if o["gauge"]:
                _mix, shown_per_true = mixture(wall, pm, chan, seals[i][0], (o.get("tag") or "IG")[:2])
                model = true * shown_per_true / speed
            else:
                model = true / speed
            res.append((math.log(max(model, 1e-30)) - math.log(max(o["shown"], 1e-30))) / o["sd"])
        if leak is not None:
            res.append((p["leak"] - leak) / max(0.03 * leak, 2e-9))
        return res

    lo = {"c_w": 1e-3, "leak": 1e-11, "qv0": 1e-10, "tau": 1.0, "perm": 1e-2, "s_now": speed_range[0]}
    # bounds wide enough never to bind inside the range MS-BP allows: a bound that binds makes a flat profile look
    # informative, which is exactly what tau_is_measured must not be fooled by
    hi = {"c_w": 1e2, "leak": 1e-1, "qv0": 1e1, "tau": TAU_LONGEST, "perm": 1e2, "s_now": speed_range[1]}
    best = None
    for tau0 in ((4.0, 12.0, 30.0) if trapped_from and fixed_tau is None else (None,)):
        x0 = {"c_w": 1.0, "leak": 1e-5, "qv0": 1e-4, "tau": tau0 or 1.0, "perm": 1.0,
              "s_now": math.sqrt(speed_range[0] * speed_range[1])}
        th0 = [math.log(x0[n]) for n in names]
        fit = least_squares(residual, th0, bounds=([math.log(lo[n]) for n in names],
                                                   [math.log(hi[n]) for n in names]),
                            method="trf", xtol=1e-12, ftol=1e-12, max_nfev=4000)
        chi2 = float(np.sum(np.array(fit.fun) ** 2))
        if best is None or chi2 < best[0]:
            best = (chi2, fit)
    chi2, fit = best
    p = unpack(fit.x)
    # the uncertainty of the permeation scale, from the curvature of the fit, decides whether it is believed
    if free_perm:
        J = fit.jac
        try:
            cov = np.linalg.inv(J.T @ J)
            p["perm_sd"] = float(math.sqrt(max(cov[names.index("perm"), names.index("perm")], 0.0)))
        except np.linalg.LinAlgError:
            p["perm_sd"] = float("inf")
    n = len(obs) + (1 if leak is not None else 0)
    k = len(names) + (1 if trapped_from and fixed_tau is not None else 0)
    return chi2, p, n, k


def tau_is_measured(cid, data, st, obs, s_now, trapped_from, free_perm, speed_range, leak):
    """Whether the records say anything about how fast the trapped volume empties: the fit is profiled over the
    time constant, everything else refitted at each value, and a profile that varies by less than one unit of chi2
    across the whole range MS-BP allows means the time constant is not measured at all. An optimiser stopping
    somewhere in such a valley reports where it happened to stop, which is no answer."""
    prof = [solve(cid, data, st, obs, s_now, trapped_from, free_perm, speed_range, leak, fixed_tau=t)[0]
            for t in (2.0, 5.0, 10.0, 20.0, 35.0, TAU_LONGEST)]
    return max(prof) - min(prof) >= 1.0


CHI2_1PC = {1: 6.63, 2: 9.21, 3: 11.34}      # the chi-square a one per cent significance asks, by added parameters


def audit_one(cid, data, vac):
    st = state_on(cid, data, AUDIT_DATE)
    altered = turbo_altered(cid, data)
    k = cert_out_by(cid, data, st)
    cuts = _cuts(st, altered)
    now = _period(AUDIT_DATE, cuts)
    ordered, s_now, leak = order_observations(cid, st, vac)
    if s_now is None:
        s_now = shop_speed(cid, data, cuts, now, k)

    swaps = swapped_tags(data)

    def gather(st_, comp, every, before=None):
        out = []
        rs = readings(cid, data, st_, swaps, comp, every)
        if before:
            rs = [r for r in rs if r["date"] < before]
        for r in rs:
            shown = r["shown"] * k.get(r["tag"], 1.0)
            per = _period(r["date"], cuts)
            speed = "now" if per == now else shop_speed(cid, data, cuts, per, k)
            if speed is None:
                continue
            out.append(dict(r, shown=shown, gauge=True, speed=speed, sd=READ_REPEAT))
        if before is None:
            for r in test_readings(cid, data, st_, comp):
                f = k.get(r["tag"], 1.0)
                out.append(dict(r, shown=r["shown"] * f, gauge=True, speed=r["s_test"] / f,
                                sd=math.hypot(SPEED_REPEAT, SPEED_REPEAT * 1.5)))
        return out

    rated = rated_of(st) or s_now        # a pump in order behind an unrecorded port: its measured speed is rated
    paired = any(r["paired"] for r in readings(cid, data, st, swaps, None, True))
    comp, every = {}, False
    if paired or {x["gauge"][:2] for x in data["log"] if x["chamber"] == cid} >= {"CC", "IG"}:
        # The two gauge types read the same gas differently (vacuum_data.md), so their ratio on a pumpdown is the
        # gas's composition as well as the cold cathode's own calibration. A plain budget on one reading per
        # pumpdown gives each paired pumpdown's composition; what is left of the ratio is the cold cathode; if it
        # holds still, every reading is kept and the fit reads the composition from the pairs itself.
        def note(st_, p, rs):
            for r in rs:
                if not r["paired"] or not r["tag"].startswith("IG"):
                    continue
                here = state_on(cid, data, r["date"])
                wall = p["c_w"] * wall_shape(surfaces_of(st_, r["load"]), r["hours"], r["vent"], r["t_c"])
                pm = perm_load(here["seal"] if here["seal_logged"] else st_["seal_register"], here["seal_cm"],
                               r["t_c"])
                cc = mixture(wall, pm, p["leak"], here["seal"], "CC")[1]
                ig = mixture(wall, pm, p["leak"], here["seal"], "IG")[1]
                comp[(r["date"], r["pd"])] = cc / ig
        if st["relined"]:
            old = state_on(cid, data, "0000-00-00")
            old = dict(old, relined=None)
            pre = gather(old, {}, False, before=st["relined"])
            if len(pre) >= 2:
                try:
                    _c0, p0, _n0, _k0 = solve(cid, data, old, pre, s_now or rated, None, False,
                                              (0.05 * rated, 1.2 * rated))
                    note(old, p0, [r for r in readings(cid, data, old, swaps, None, True)
                                   if r["date"] < st["relined"]])
                except Exception:
                    pass
        # the composition of the pumpdowns since: the budget on one reading per pumpdown, its cold cathode
        # readings corrected by the line as the composition last estimated leaves it, a few times over
        for _round in range(4):
            first = gather(st, dict(comp), False) + ordered
            try:
                _c1, p1, _n1, _k1 = solve(cid, data, st, first, s_now, None, False, (0.05 * rated, 1.2 * rated),
                                          leak)
                note(st, p1, readings(cid, data, st, swaps, None, True))
            except Exception:
                break
        both, line = _cc_line(cid, data, comp)
        if line is not None and len(both) >= 2:
            span = both[-1][0] - both[0][0]
            every = abs(line[0] * span) <= 0.04      # within what two readings' scatter and the composition
            # estimate's own error leave in a ratio; a fouling cathode loses far more
    obs = gather(st, comp, every) + ordered

    lo_d, hi_d = min(o["date"] for o in obs), max(o["date"] for o in obs)
    worked = sorted({r["date"] for r in data["mnt"] if r["chamber"] == cid and lo_d < r["date"] <= hi_d})
    best = None
    plain = solve(cid, data, st, obs, s_now, None, False, (0.05 * rated, 1.2 * rated), leak)
    for tf in [None, "0000-00-00"] + worked:
        for free in (False, True):
            chi2, p, n, kpar = solve(cid, data, st, obs, s_now, tf, free, (0.05 * rated, 1.2 * rated), leak)
            if n <= kpar:
                continue                    # a budget that passes through every observation is untested
            if (tf is not None or free) and n < kpar + 2:
                continue                    # an added mechanism has to leave two degrees of freedom to be tested
            # and it has to earn its place: the improvement over the plain budget must be significant at one per
            # cent for the parameters it adds (chi-square, two for a trapped volume, one for a seal's scale)
            added = (2 if tf is not None else 0) + (1 if free else 0)
            if added and plain[2] > plain[3] and plain[0] - chi2 < CHI2_1PC[added]:
                continue
            bic = chi2 + kpar * math.log(n)
            if best is None or bic < best[0]:
                best = (bic, p, tf, free)
    _bic, p, tf, free = best
    if tf is not None and not tau_is_measured(cid, data, st, obs, s_now, tf, free, (0.05 * rated, 1.2 * rated),
                                              leak):
        # Nothing measures it. The conservative reading is MS-BP clause 3.3's longest time constant, which leaves
        # the most trapped gas at the reference condition; it is a statement of what is not known, not an estimate.
        _chi2, p, _n, _k = solve(cid, data, st, obs, s_now, tf, free, (0.05 * rated, 1.2 * rated), leak,
                                 fixed_tau=TAU_LONGEST)

    seal_now = st["seal"] if st["seal_logged"] else st["seal_register"]
    if free:
        # adopt another table material only where the fitted scale is well determined and lands near it
        k_fit = p["perm"] * ELAST[st["seal_register"]][0]
        near = min(ELAST, key=lambda m: abs(math.log(ELAST[m][0] / k_fit)))
        if near != st["seal_register"] and p.get("perm_sd", 1.0) < 0.15 \
                and abs(math.log(ELAST[near][0] / k_fit)) < 3.0 * max(p["perm_sd"], 0.02):
            if not st["seal_logged"]:
                seal_now = near
            chi2, p, n, kpar = solve(cid, data, dict(st, seal_register=near), obs, s_now, tf, False,
                                     (0.05 * rated, 1.2 * rated), leak)
        else:
            chi2, p, n, kpar = solve(cid, data, st, obs, s_now, tf, False, (0.05 * rated, 1.2 * rated), leak)

    parts = {
        "wall-outgassing": p["c_w"] * wall_shape(st["surfaces"], REF_HOURS, "air", 20.0),
        "permeation": perm_load(seal_now, st["seal_cm"], 20.0),
        "air-leak": p["leak"],
        "virtual-leak": p["qv0"] * math.exp(-REF_HOURS / p["tau"]) if p["qv0"] and p["tau"] else 0.0,
    }
    whole = sum(parts.values())
    s_eff = p["s_now"]
    cause = "pump-speed" if s_eff < GATE * rated else max(parts, key=lambda q: parts[q])
    return cause, whole, s_eff


def audit_all(data_dir, vac=None):
    data = shop(data_dir)
    ids = sorted({r["chamber"] for r in data["reg"]})
    return {cid: audit_one(cid, data, vac) for cid in ids}


if __name__ == "__main__":
    import sys
    out = audit_all(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print("chamber,cause,q_total_mbarl_s,s_eff_l_s")
    for cid in sorted(out):
        cause, q, s = out[cid]
        print("%s,%s,%.4e,%.1f" % (cid, cause, q, s))
