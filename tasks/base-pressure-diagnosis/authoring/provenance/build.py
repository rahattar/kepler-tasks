"""Writes the audit records, the documents, the worked example and the sealed truth from the sealed fleet.

    python3 -I build.py DEST [--truth PATH]

DEST gets the agent's `/app/data` tree: the register, the base-pressure log, the speed tests, the controller rows,
the maintenance log, the climate record, the gauge certificates, `docs/` and `example/`. With --truth the audit
truth is written as JSON for the verifier.

Everything is a deterministic function of the sealed definition and SEED, so the same call always writes the same
bytes. The records carry instrument noise; the truth never does.
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpphys as P                                                      # noqa: E402
import docs_bp                                                          # noqa: E402
import fleet as F                                                        # noqa: E402

SEED = 20261109

READ_NOISE = F.REPEAT["reading"]               # gauge readings, relative
SPEED_NOISE = F.REPEAT["speed_pressure"]       # speed-test pressures, relative
CLIMATE_NOISE = 1.4                 # shop air temperature, C


def rng_for(*parts):
    key = [SEED]
    for p in parts:
        key.append(sum((i + 1) * ord(c) for i, c in enumerate(str(p))) % 100003)
    return np.random.default_rng(key)


def days(a, b):
    import datetime
    fa = datetime.date(*map(int, a.split("-")))
    fb = datetime.date(*map(int, b.split("-")))
    return (fb - fa).days


def sig(x, n=3):
    """x to n significant figures, as a plain decimal string in exponent form."""
    if x == 0:
        return "0"
    return "%.*e" % (n - 1, x)


def primary_gauge(ch):
    for s in sorted(ch["certs"]):
        if s.startswith("CC"):
            return s
    return sorted(ch["certs"])[0]


# ----------------------------------------------------------------------------------------------------------------
def register_rows():
    rows = [["chamber", "volume_l", "turbo", "c_port_l_s", "seal_material", "seal_length_cm",
             "surface_area_m2", "surface", "p_spec_mbar"]]
    for cid in F.CHAMBER_IDS:
        r = F.BY[cid]["reg"]
        for area, mat in r["surfaces"]:
            rows.append([cid, "%d" % r["volume"], r["turbo"], "%d" % r["c_port"], r["seal"],
                         "%d" % r["seal_cm"], "%.2f" % area, mat, sig(r["p_spec"], 2)])
    return rows


def log_rows(ids):
    rows = [["date", "chamber", "pumpdown", "vent_gas", "pumpdown_h", "wall_temp_c", "gauge", "reading_mbar",
             "load", "note"]]
    out = []
    for cid in ids:
        ch = F.BY[cid]
        for n, entry in enumerate(ch["log"]):
            date, pid, vent, hours, temp_c, serial, load = entry[:7]
            true = F.log_reading(ch, entry)
            g = rng_for(cid, "log", n, serial)
            reading = true * float(math.exp(g.normal(0, READ_NOISE)))
            note = entry[8] if len(entry) > 8 else ""
            out.append([date, cid, pid, vent, "%.1f" % hours, "%.1f" % temp_c, serial, sig(reading),
                        load or "", note])
    out.sort(key=lambda r: (r[0], r[1], r[6]))
    return rows + out


def speed_rows(ids):
    rows = [["date", "chamber", "pumping_time_h", "wall_temp_c", "flow_mbarl_s", "p_with_flow_mbar",
             "p_without_flow_mbar", "gauge", "s_eff_l_s"]]
    out = []
    for cid in ids:
        ch = F.BY[cid]
        for n, entry in enumerate(ch["speed"]):
            date, hours, temp_c = entry[:3]
            serial = entry[3] if len(entry) > 3 else primary_gauge(ch)
            c = F.config(ch, date)
            s = P.s_eff(c, P.p_base(c, P.q_total(c, hours, "air", temp_c + 273.15)))
            # the chamber's own gas, as the gauge indicates it, and the nitrogen the test admits on top of it
            base_ind = P.indicated(c, hours, "air", temp_c + 273.15)
            flow = float("%.3g" % (s * 4.0e-5))
            rise_ind = flow / s                        # admitted nitrogen, K = 1.00, so indicated = partial
            cert = F.cert_factor(serial, date) * F.drift_factor(ch, serial, date)
            real = cert * F.cert_wrong_factor(ch, serial)
            g = rng_for(cid, "speed", n)
            p_wo = base_ind / real * float(math.exp(g.normal(0, SPEED_NOISE)))
            p_w = (base_ind + rise_ind) / real * float(math.exp(g.normal(0, SPEED_NOISE)))
            reported = flow / ((p_w - p_wo) * cert)
            out.append([date, cid, "%.1f" % hours, "%.1f" % temp_c, "%.4g" % flow, sig(p_w, 4), sig(p_wo, 4), serial,
                        "%.1f" % reported])
    out.sort(key=lambda r: (r[0], r[1]))
    return rows + out


def controller_rows(ids):
    rows = [["date", "chamber", "rotor_hz", "drive_power_w", "bearing_temp_c"]]
    out = []
    for cid in ids:
        ch = F.BY[cid]
        for n, date in enumerate(ch["ctrl"]):
            c = F.config(ch, date)
            f = c["f_pump"]
            hz0, pw0, tb0 = P.PUMP_CONTROLLER[c["turbo"]]
            g = rng_for(cid, "ctrl", n)
            hz = hz0 * (0.93 + 0.07 * f) * (1 + g.normal(0, 0.003))
            pw = pw0 * (1 + 1.10 * (1 - f)) * (1 + g.normal(0, 0.02))
            tb = tb0 + 26.0 * (1 - f) + g.normal(0, 0.5)
            out.append([date, cid, "%.0f" % hz, "%.0f" % pw, "%.1f" % tb])
    out.sort(key=lambda r: (r[0], r[1]))
    return rows + out


def maintenance_rows(ids):
    rows = [["date", "chamber", "entry"]]
    out = []
    for cid in ids:
        ch = F.BY[cid]
        for date, kind, args in ch["events"]:
            if kind == "note":
                text = args
            elif kind == "internals":
                text = "%s Internal surfaces after the work: %s." % (
                    args[1], "; ".join("%.2f m2 %s" % (a, m) for a, m in args[0]))
            elif kind == "trap":
                text = "%s Port conductance after the work: %d L/s." % (args[1], args[0])
            elif kind == "seal":
                text = "%s Seal material after the work: %s." % (args[1], args[0])
            elif kind == "seal_len":
                text = "%s Seal length after the work: %d cm." % (args[1], args[0])
            elif kind == "trapped":
                continue                              # a trapped volume is not an entry anybody writes
            elif kind == "pump":
                continue                              # nor is a pump quietly losing speed
            elif kind == "leak":
                continue
            else:
                continue
            out.append([date, cid, text])
    out.sort(key=lambda r: (r[0], r[1]))
    return rows + out


def climate_rows(first="2025-02-01", last="2026-11-01"):
    """A seasonal shop air temperature with a daily draw, and the relative humidity that goes with it."""
    rows = [["date", "air_temp_c", "relative_humidity_pct"]]
    import datetime
    d0 = datetime.date(*map(int, first.split("-")))
    d1 = datetime.date(*map(int, last.split("-")))
    g = rng_for("climate")
    d = d0
    while d <= d1:
        doy = d.timetuple().tm_yday
        base = 16.0 + 9.0 * math.sin(2 * math.pi * (doy - 112) / 365.25)
        t = base + float(g.normal(0, CLIMATE_NOISE))
        rh = 54.0 + 1.9 * (t - 16.0) + float(g.normal(0, 7.0))
        rows.append([d.isoformat(), "%.1f" % t, "%.0f" % max(18.0, min(94.0, rh))])
        d += datetime.timedelta(days=1)
    return rows


# ----------------------------------------------------------------------------------------------------------------
def truth():
    out = {}
    for cid in F.CHAMBER_IDS:
        t = F.truth(F.BY[cid])
        out[cid] = dict(cause=t["cause"], q_total_mbarl_s=t["q_total"], s_eff_l_s=t["s_eff"],
                        s_rated_l_s=t["s_rated"], p_base_mbar=t["p_base"])
    return out


def example_result():
    """The example chamber is there to show the format of the records and that they can be sound. MS-BP defines
    what the audit reports, so no result is given for it: a worked answer would be an end-to-end check of a whole
    audit rather than a worked example of the records."""
    return """# The example chamber, %(ex)s

%(ex)s belongs to the same shop and was audited in an earlier quarter. Its records are in this folder, in the same
format as the fleet's, so that the format and the units are plain.

Its records are sound throughout: one gauge, a speed test that still described its pump, no work in the
maintenance log over the period of its log, and nothing in the chamber on any of its pumpdowns.

MS-BP defines what the audit reports and how each quantity is reached, so no audited result is given here.

The register gives %(ex)s a specified base pressure of %(spec).0e mbar, and it was on that quarter's list because
it was not reaching it.
""" % dict(ex=F.EXAMPLE, spec=F.EX["reg"]["p_spec"])


def example_register_rows():
    rows = [["chamber", "volume_l", "turbo", "c_port_l_s", "seal_material", "seal_length_cm",
             "surface_area_m2", "surface", "p_spec_mbar"]]
    r = F.EX["reg"]
    for area, mat in r["surfaces"]:
        rows.append([F.EXAMPLE, "%d" % r["volume"], r["turbo"], "%d" % r["c_port"], r["seal"],
                     "%d" % r["seal_cm"], "%.2f" % area, mat, sig(r["p_spec"], 2)])
    return rows


# ----------------------------------------------------------------------------------------------------------------
def quote(field):
    """Minimal CSV quoting: a field holding a comma or a quote is quoted, inner quotes doubled."""
    if "," in field or '"' in field or "\n" in field:
        return '"' + field.replace('"', '""') + '"'
    return field


def write_csv(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(",".join(quote(c) for c in r) + "\n")


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text if text.endswith("\n") else text + "\n")


def build(dest):
    ids = F.CHAMBER_IDS
    write_csv(os.path.join(dest, "chamber_register.csv"), register_rows())
    write_csv(os.path.join(dest, "base_pressure_log.csv"), log_rows(ids))
    write_csv(os.path.join(dest, "speed_tests.csv"), speed_rows(ids))
    write_csv(os.path.join(dest, "turbo_controller.csv"), controller_rows(ids))
    write_csv(os.path.join(dest, "maintenance_log.csv"), maintenance_rows(ids))
    write_csv(os.path.join(dest, "shop_climate.csv"), climate_rows())
    for rel, text in docs_bp.docs().items():
        write_text(os.path.join(dest, rel), text)

    ex = [F.EXAMPLE]
    write_csv(os.path.join(dest, "example", "chamber_register.csv"), example_register_rows())
    write_csv(os.path.join(dest, "example", "base_pressure_log.csv"), log_rows(ex))
    write_csv(os.path.join(dest, "example", "speed_tests.csv"), speed_rows(ex))
    write_csv(os.path.join(dest, "example", "turbo_controller.csv"), controller_rows(ex))
    write_csv(os.path.join(dest, "example", "maintenance_log.csv"), maintenance_rows(ex))
    write_text(os.path.join(dest, "example", "about_this_chamber.md"), example_result())


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    dest = argv[0]
    build(dest)
    if "--truth" in argv:
        tp = argv[argv.index("--truth") + 1]
        os.makedirs(os.path.dirname(tp), exist_ok=True)
        with open(tp, "w") as f:
            json.dump(truth(), f, indent=1, sort_keys=True)
        print("truth written to %s" % tp)
    n = sum(len(fs) for _r, _d, fs in os.walk(dest))
    print("%d files written to %s" % (n, dest))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
