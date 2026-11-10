"""Grade a corrections file (path argument, or CORRECTIONS_PATH, default /app/output/corrections.csv) on the bay's
sealed definition (tc.py, seed 7). For every zone of every furnace, the controller is loaded with the file's
corrections at 850 C and 1050 C and holds the corrected profile reading at the setpoint; the wafer temperature is
computed from the zone's true thermocouple drift and wafer-to-junction offset, both at the junction's actual
temperature. A zone passes when the wafer is within TOL of the setpoint at 850 C and at 1050 C. The file passes
when all 40 zones pass.

File rules: a header with the columns furnace, zone, correction_850_c and correction_1050_c (any order, other
columns ignored), one row for each of the 40 zones (F1-F8, Z1-Z5) and no others, finite numbers.
"""
import csv, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tc

TOL = tc.TOL          # 2.0 K, process engineering's requirement at 850 C and 1050 C


def _num(s):
    x = float(str(s).strip())
    if not math.isfinite(x):
        raise ValueError("non-finite value %r" % s)
    return x


def read(path):
    with open(path, newline="") as f:
        rows = [r for r in csv.reader(f) if any(c.strip() for c in r)]
    if not rows:
        raise ValueError("empty file")
    head = [h.strip().lower() for h in rows[0]]
    for col in ("furnace", "zone", "correction_850_c", "correction_1050_c"):
        if col not in head:
            raise ValueError("header has no column %r" % col)
    i_f, i_z, i_lo, i_hi = (head.index(c) for c in ("furnace", "zone", "correction_850_c", "correction_1050_c"))
    cal = {}
    for r in rows[1:]:
        key = (r[i_f].strip().upper(), r[i_z].strip().upper())
        if key in cal:
            raise ValueError("zone %s %s appears twice" % key)
        cal[key] = (_num(r[i_lo]), _num(r[i_hi]))
    return cal


def grade(path):
    bay = tc.make_bay(7)
    keys = [(f, z) for f in tc.FURN for z in tc.ZONES]
    cal = read(path)
    unknown = sorted(set(cal) - set(keys))
    if unknown:
        raise ValueError("unknown zones %s" % unknown)
    out = dict(passed=True, zones={}, missing=["%s %s" % k for k in keys if k not in cal])
    for f in tc.FURN:
        b = bay[f]
        for i, z in enumerate(tc.ZONES):
            name = "%s %s" % (f, z)
            if (f, z) not in cal:
                out["zones"][name] = dict(passed=False, reason="no row")
                out["passed"] = False
                continue
            lo, hi = cal[(f, z)]
            rec = dict(correction_850_c=lo, correction_1050_c=hi)
            for T in (tc.T_LO, tc.T_HI):
                e = float(tc.wafer_error(b, [lo] * 5, [hi] * 5, T)[i])
                rec["wafer_minus_setpoint_%d_k" % T] = round(e, 3)
            rec["passed"] = max(abs(rec["wafer_minus_setpoint_850_k"]), abs(rec["wafer_minus_setpoint_1050_k"])) <= TOL
            out["zones"][name] = rec
            out["passed"] &= rec["passed"]
    return out


if __name__ == "__main__":
    r = grade(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CORRECTIONS_PATH", "/app/output/corrections.csv"))
    worst = sorted(((max(abs(v.get("wafer_minus_setpoint_850_k", 99)), abs(v.get("wafer_minus_setpoint_1050_k", 99))), k)
                    for k, v in r["zones"].items()), reverse=True)
    print("passed" if r["passed"] else "failed", "| worst %.2f K at %s" % worst[0],
          "| failing:", [k for e, k in worst if e > TOL])
