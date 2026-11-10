"""A second audit, written from the documents alone and sharing no code with the reference solution.

Where the reference identifies the gas budget by a linear least squares with the gauge correction iterated to a
fixed point outside it, this one solves the whole thing at once: a nonlinear least squares in the logarithm of the
gas load, over the wall coefficient, the leak, and a trapped volume with its time constant, with MS-BP clause 5's
correction evaluated inside the residual at every step. Where the reference reads the wall's share of a thin log
off the water line of a residual gas analysis, this one unmixes all six species against the three source
compositions by non-negative least squares. It also finds a changed turbo from the controller's rotor frequency
rather than its drive power, and averages every surviving speed test rather than taking the latest.

It reaches the same answers as the reference, which is what makes the audit well posed rather than a property of
one program.

    audit_all(data_dir, vacwork_dir) -> {chamber: (cause, q_total, s_eff)}
"""
import csv
import math
import os

import numpy as np
from scipy.optimize import least_squares, nnls

REF_HOURS = 16.0
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
SENS = dict(h2=0.42, h2o=1.12, n2=1.00, o2=1.01, ar=1.29, co2=1.42)
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


def mixture(wall, perm, channel, seal):
    """Species fractions of a gas made of the three sources, and the pressure the gauge would indicate for one
    unit of true pressure."""
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
    shown = sum(x / SENS[k] for k, x in acc.items())
    return acc, shown


def shop(data_dir):
    d = dict(reg=rows_of(os.path.join(data_dir, "chamber_register.csv")),
             log=rows_of(os.path.join(data_dir, "base_pressure_log.csv")),
             spd=rows_of(os.path.join(data_dir, "speed_tests.csv")),
             ctl=rows_of(os.path.join(data_dir, "turbo_controller.csv")),
             mnt=rows_of(os.path.join(data_dir, "maintenance_log.csv")))
    d["cert"] = certificates(os.path.join(data_dir, "gauge_certificates.md"))
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
              spec=float(head["p_spec_mbar"]), relined=None, ported=None)
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
        if "Seal material after the work:" in txt:
            st["seal"] = txt.split("Seal material after the work:", 1)[1].strip().rstrip(".")
        if "Seal length after the work:" in txt:
            st["seal_cm"] = float(txt.split("Seal length after the work:", 1)[1].strip().split()[0])
    return st


def pump_fitted(cid, data):
    """The pump the controller's figures say is turning, which a register can get wrong. Chosen by the smallest
    relative distance to each model's rated rotor frequency, drive power and bearing temperature over the
    chamber's earliest rows."""
    seq = sorted([r for r in data["ctl"] if r["chamber"] == cid], key=lambda r: r["date"])[:4]
    if not seq:
        return None
    got = (float(np.mean([float(r["rotor_hz"]) for r in seq])),
           float(np.mean([float(r["drive_power_w"]) for r in seq])),
           float(np.mean([float(r["bearing_temp_c"]) for r in seq])))
    scored = sorted((sum(((g - n) / n) ** 2 for g, n in zip(got, nom)), m) for m, nom in CTRL.items())
    return scored[0][1] if scored[0][0] < 0.02 else None


def turbo_altered(cid, data):
    """The first month the controller shows a turbo that is not the one it was: rotor frequency down by more than
    3 per cent, or bearing temperature up by more than 5 C."""
    seq = sorted([r for r in data["ctl"] if r["chamber"] == cid], key=lambda r: r["date"])
    if len(seq) < 2:
        return None
    hz0 = float(seq[0]["rotor_hz"])
    tb0 = float(seq[0]["bearing_temp_c"])
    for r in seq[1:]:
        if float(r["rotor_hz"]) < 0.97 * hz0 or float(r["bearing_temp_c"]) > tb0 + 5.0:
            return r["date"]
    return None


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


def readings(cid, data, st, swaps):
    """One reading per pumpdown since the chamber was last relined, preferring the hot-filament gauge and
    correcting a fouling cold cathode by the trend of its ratio to that gauge."""
    mine = [r for r in data["log"] if r["chamber"] == cid and r["date"] <= AUDIT_DATE]
    if st["relined"]:
        mine = [r for r in mine if r["date"] >= st["relined"]]
    groups = {}
    for r in mine:
        groups.setdefault((r["date"], r["pumpdown"]), []).append(r)

    pairs = {}
    for r in [x for x in data["log"] if x["chamber"] == cid]:
        pairs.setdefault((r["date"], r["pumpdown"]), {})[r["gauge"][:2]] = float(r["reading_mbar"])
    both = [(_ord(d), v["CC"] / v["IG"]) for (d, _p), v in sorted(pairs.items()) if "CC" in v and "IG" in v]
    slope = offset = None
    if len(both) >= 2 and abs(both[-1][1] - both[0][1]) > 0.02:
        xs = np.array([x for x, _ in both], float)
        ys = np.array([y for _, y in both], float)
        slope, offset = np.polyfit(xs, ys, 1)

    out = []
    for (date, pd), group in sorted(groups.items()):
        hot = [r for r in group if r["gauge"].startswith("IG")]
        pick = hot[0] if hot else sorted(group, key=lambda r: r["gauge"])[0]
        tag = swaps.get((cid, date, pd), pick["gauge"])
        if tag not in data["cert"]:
            continue
        shown = float(pick["reading_mbar"]) * factor_on(data["cert"], tag, date)
        if not hot and slope is not None:
            ratio = offset + slope * _ord(date)
            if 0.2 < ratio < 5.0:
                shown /= ratio
        out.append(dict(date=date, hours=float(pick["pumpdown_h"]), t_c=float(pick["wall_temp_c"]),
                        vent=pick["vent_gas"], load=pick["load"].strip(), shown=shown, tag=tag))
    return out


def _ord(date):
    import datetime
    return datetime.date(*map(int, date.split("-"))).toordinal()


def seal_on(cid, data, date):
    st = state_on(cid, data, date)
    return st["seal"], st["seal_cm"]


def surfaces_of(st, load):
    out = list(st["surfaces"])
    if load and load in KIT:
        out.append(KIT[load])
    return out


def solve_budget(cid, data, st, reads, s_eff, with_trap):
    """Nonlinear least squares in the logarithm of the gas load, with the gauge correction inside the residual."""
    shapes = [wall_shape(surfaces_of(st, r["load"]), r["hours"], r["vent"], r["t_c"]) for r in reads]
    perms = [perm_load(*seal_on(cid, data, r["date"]), t_c=r["t_c"]) for r in reads]
    seals = [seal_on(cid, data, r["date"])[0] for r in reads]

    def residual(theta):
        c_w = math.exp(theta[0])
        q_l = math.exp(theta[1])
        qv0 = math.exp(theta[2]) if with_trap else 0.0
        tau = math.exp(theta[3]) if with_trap else 1.0
        res = []
        for i, r in enumerate(reads):
            wall = c_w * shapes[i]
            chan = q_l + (qv0 * math.exp(-r["hours"] / tau) if with_trap else 0.0)
            _mix, shown_per_true = mixture(wall, perms[i], chan, seals[i])
            model_true = wall + perms[i] + chan
            model_shown = model_true * shown_per_true / s_eff
            res.append(math.log(max(model_shown, 1e-30)) - math.log(max(r["shown"], 1e-30)))
        return res

    start = [math.log(1.0), math.log(max(1e-6, 1e-5))]
    lo = [math.log(1e-3), math.log(1e-12)]
    hi = [math.log(1e3), math.log(1e-1)]
    if with_trap:
        start += [math.log(1e-4), math.log(8.0)]
        lo += [math.log(1e-9), math.log(2.0)]
        hi += [math.log(1e-1), math.log(48.0)]
    fit = least_squares(residual, start, bounds=(lo, hi), method="trf", xtol=1e-12, ftol=1e-12)
    c_w = math.exp(fit.x[0])
    q_l = math.exp(fit.x[1])
    qv0 = math.exp(fit.x[2]) if with_trap else 0.0
    tau = math.exp(fit.x[3]) if with_trap else None
    return c_w, q_l, qv0, tau, float(np.sum(np.array(fit.fun) ** 2))


def unmix(cid, data, vac, s_eff):
    """Splits the gas load into wall water, permeated air and air through a channel by fitting all six species the
    analyser resolves against the three source compositions."""
    path = os.path.join(vac, "rga_%s.csv" % cid.lower()) if vac else None
    if not path or not os.path.exists(path):
        return None
    partial, hours, t_c = {}, REF_HOURS, 20.0
    for line in open(path):
        if line.startswith("#"):
            if "pumping time" in line:
                hours = float(line.rsplit(":", 1)[1].split()[0])
            elif "wall temperature" in line:
                t_c = float(line.rsplit(":", 1)[1].split()[0])
            continue
        if line.startswith("species"):
            continue
        name, _mz, val = line.strip().split(",")
        partial[name] = float(val)
    seal, _cm = seal_on(cid, data, AUDIT_DATE)
    cols = []
    for src in (WALL_GAS, perm_species(seal), dict(zip(("n2", "o2", "ar", "co2"), DRY_AIR))):
        tot = sum(src.values())
        cols.append([src.get(k, 0.0) / tot for k in ORDER])
    A = np.array(cols, float).T
    y = np.array([partial.get(k, 0.0) * s_eff for k in ORDER], float)
    q, _rn = nnls(A, y)
    return dict(wall=float(q[0]), perm=float(q[1]), channel=float(q[2]), hours=hours, t_c=t_c)


def worked_on_since_sound(cid, data):
    tests = sorted([r for r in data["spd"] if r["chamber"] == cid], key=lambda r: r["date"])
    if not tests:
        return False
    first = tests[0]
    spec = float([r for r in data["reg"] if r["chamber"] == cid][0]["p_spec_mbar"])
    was_sound = float(first["p_without_flow_mbar"]) <= 2.0 * spec
    since = [r for r in data["mnt"] if r["chamber"] == cid and first["date"] < r["date"] <= AUDIT_DATE]
    return bool(was_sound and since)


def ordered_speed(cid, st, vac):
    if not vac:
        return None
    sp = os.path.join(vac, "speed_test_%s.csv" % cid.lower())
    if os.path.exists(sp):
        for line in open(sp):
            if line.startswith("#") or line.startswith("flow"):
                continue
            return float(line.strip().split(",")[3])
    rr = os.path.join(vac, "rate_of_rise_%s.csv" % cid.lower())
    if os.path.exists(rr):
        pts = []
        for line in open(rr):
            if line.startswith("#") or line.startswith("seconds"):
                continue
            a, b = line.strip().split(",")
            pts.append((float(a), float(b)))
        if len(pts) >= 10:
            # the first ten minutes only: over a whole hour the wall gas load has fallen measurably, and the
            # slope would be the average over the run rather than the load at the reported pumping time
            win = [q for q in pts if q[0] <= 600.0] or pts
            slope, intercept = np.polyfit([x for x, _ in win], [y for _, y in win], 1)
            return slope * st["volume"] / intercept
    return None


def cert_out_by(cid, data, st):
    """A chamber's throughput tests cannot report a speed above its pump in series with its port. Where they do,
    the ratio is how far its gauge certificate is out: its pressures are low by it and its reported speeds high by
    it, which is why the gas load looks right and only the speed does not."""
    rated = rated_of(st)
    good, tags = [], set()
    for r in data["spd"]:
        if r["chamber"] != cid or (st["ported"] and r["date"] < st["ported"]):
            continue
        good.append(float(r["s_eff_l_s"]) / rated)
        tags.add(r["gauge"])
    if not good:
        return 1.0, None
    k = float(np.mean(good))
    if k <= 1.02:
        return 1.0, None
    return k, (sorted(tags)[0] if len(tags) == 1 else None)


def speed_of(cid, data, st, vac, altered):
    s = ordered_speed(cid, st, vac)
    if s is not None:
        return s
    good = [r for r in sorted(data["spd"], key=lambda r: r["date"]) if r["chamber"] == cid
            and not (st["ported"] and r["date"] < st["ported"])
            and not (altered and r["date"] >= altered)]
    if good and not altered:
        return float(np.mean([float(r["s_eff_l_s"]) for r in good]))
    if good and altered:
        s_old = float(np.mean([float(r["s_eff_l_s"]) for r in good]))
        reads = readings(cid, data, st, swapped_tags(data))
        before = [r for r in reads if r["date"] < altered]
        after = [r for r in reads if r["date"] >= altered]
        if before and after:
            c_w, q_l, _qv, _tau, _ss = solve_budget(cid, data, st, before, s_old, False)
            est = []
            for r in after:
                wall = c_w * wall_shape(surfaces_of(st, r["load"]), r["hours"], r["vent"], r["t_c"])
                pm = perm_load(*seal_on(cid, data, r["date"]), t_c=r["t_c"])
                _mix, shown_per_true = mixture(wall, pm, q_l, seal_on(cid, data, r["date"])[0])
                est.append((wall + pm + q_l) * shown_per_true / r["shown"])
            return float(np.mean(est))
    return st["port"] * speed_curve(st["pump"], 1e-6) / (st["port"] + speed_curve(st["pump"], 1e-6))


def rated_of(st, p=1e-6):
    pump = speed_curve(st["pump"], p)
    return pump * st["port"] / (pump + st["port"])


def audit_one(cid, data, vac):
    st = state_on(cid, data, AUDIT_DATE)
    altered = turbo_altered(cid, data)
    k, k_tag = cert_out_by(cid, data, st)
    s_eff = speed_of(cid, data, st, vac, altered)
    if k != 1.0 and ordered_speed(cid, st, vac) is None:
        s_eff = s_eff / k                             # a shop speed test was read with the same certificate
    elif k != 1.0 and os.path.exists(os.path.join(vac or "", "speed_test_%s.csv" % cid.lower())):
        s_eff = s_eff / k
    reads = readings(cid, data, st, swapped_tags(data))
    if k != 1.0:
        reads = [dict(r, shown=r["shown"] * k) if (k_tag is None or r["tag"] == k_tag) else r for r in reads]
    if altered:
        reads = [r for r in reads if r["date"] >= altered] or reads
    spans = sorted({round(r["hours"], 2) for r in reads})
    seal, seal_cm = seal_on(cid, data, AUDIT_DATE)
    split = unmix(cid, data, vac, s_eff)

    if len(spans) >= 2:
        c_w, q_l, qv0, tau, ss_flat = solve_budget(cid, data, st, reads, s_eff, False)
        trap = solve_budget(cid, data, st, reads, s_eff, True) if len(reads) >= 3 else None
        take_trap = False
        if trap:
            at_ref = trap[2] * math.exp(-REF_HOURS / trap[3])
            whole = (trap[0] * wall_shape(st["surfaces"], REF_HOURS, "air", 20.0)
                     + perm_load(seal, seal_cm, 20.0) + trap[1] + at_ref)
            worth = at_ref / whole if whole > 0 else 0.0
            if split is not None:
                airy = split["channel"] + split["perm"] > split["wall"]
                take_trap = airy and trap[4] < 0.60 * ss_flat and worth > 0.08
            else:
                take_trap = trap[4] < 0.25 * ss_flat and worth > 0.08
        if take_trap:
            c_w, q_l, qv0, tau = trap[0], trap[1], trap[2], trap[3]
        else:
            qv0, tau = 0.0, None
    elif split is not None:
        nominal = wall_shape(st["surfaces"], split["hours"], "air", split["t_c"])
        c_w = split["wall"] / nominal if nominal > 0 else 1.0
        channel = split["channel"]
        if worked_on_since_sound(cid, data):
            tau = 9.0
            qv0, q_l = channel * math.exp(split["hours"] / tau), 0.0
        else:
            qv0, tau, q_l = 0.0, None, channel
    else:
        c_w, q_l, qv0, tau, _ss = solve_budget(cid, data, st, reads, s_eff, False)

    parts = {
        "wall-outgassing": c_w * wall_shape(st["surfaces"], REF_HOURS, "air", 20.0),
        "permeation": perm_load(seal, seal_cm, 20.0),
        "air-leak": max(q_l, 0.0),
        "virtual-leak": qv0 * math.exp(-REF_HOURS / tau) if qv0 and tau else 0.0,
    }
    whole = sum(parts.values())
    rated_pump = speed_curve(st["pump"], whole / max(s_eff, 1.0))
    rated = rated_pump * st["port"] / (rated_pump + st["port"])
    cause = "pump-speed" if s_eff < GATE * rated else max(parts, key=lambda k: parts[k])
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
