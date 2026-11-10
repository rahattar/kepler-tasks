"""Grade a calibration file (path argument, or CALIBRATION_PATH, default /app/output/calibration.csv) on the floor's
sealed definition (vav.py, seed 31). For every box, the controller is configured with the file's K and offset and
holds its reported airflow at design minimum and at design maximum; the airflow the box actually delivers at each
setpoint is computed from the box's true inlet multiplier and transducer zero error. A box passes when both are
within TOL of the setpoint. The file passes when every box passes.

File rules: a header with the columns tag, k_factor and vp_offset_inwc (any order, other columns ignored), one row
for each of the 40 boxes and no other tags, finite numbers, k_factor above zero.
"""
import csv, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vav

TOL = vav.TOL          # 0.10, the owner's acceptance band at design minimum and design maximum


def _num(s):
    x = float(str(s).strip())
    if not math.isfinite(x):
        raise ValueError("non-finite value %r" % s)
    return x


def read(path):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise ValueError("empty file")
    head = [h.strip().lower() for h in rows[0]]
    for col in ("tag", "k_factor", "vp_offset_inwc"):
        if col not in head:
            raise ValueError("header has no column %r" % col)
    it, ik, io_ = head.index("tag"), head.index("k_factor"), head.index("vp_offset_inwc")
    cal = {}
    for r in rows[1:]:
        tag = r[it].strip().upper()
        if tag in cal:
            raise ValueError("box %s appears twice" % tag)
        k, off = _num(r[ik]), _num(r[io_])
        if k <= 0:
            raise ValueError("box %s: k_factor must be above zero" % tag)
        cal[tag] = (k, off)
    return cal


def grade(path):
    floor = vav.make_floor(31)
    tags = [b["tag"] for b in floor]
    cal = read(path)
    unknown = sorted(set(cal) - set(tags))
    if unknown:
        raise ValueError("unknown boxes %s" % unknown)
    out = dict(passed=True, boxes={}, missing=sorted(set(tags) - set(cal)))
    for b in floor:
        t = b["tag"]
        if t not in cal:
            out["boxes"][t] = dict(passed=False, reason="no row")
            out["passed"] = False
            continue
        K, off = cal[t]
        rec = dict(k_factor=K, vp_offset_inwc=off)
        for name, q in (("design_min", b["qmin"]), ("design_max", b["qmax"])):
            d = vav.true_flow(b, K, off, q)
            rec[name + "_setpoint_cfm"] = q
            rec[name + "_delivered_cfm"] = round(d, 1)
            rec[name + "_error"] = round(d / q - 1.0, 4)
        rec["passed"] = max(abs(rec["design_min_error"]), abs(rec["design_max_error"])) <= TOL
        out["boxes"][t] = rec
        out["passed"] &= rec["passed"]
    return out


if __name__ == "__main__":
    r = grade(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CALIBRATION_PATH", "/app/output/calibration.csv"))
    worst = sorted(((max(abs(v.get("design_min_error", 9)), abs(v.get("design_max_error", 9))), t)
                    for t, v in r["boxes"].items()), reverse=True)
    print("passed" if r["passed"] else "failed", "| worst %.1f %% at %s" % (100 * worst[0][0], worst[0][1]),
          "| failing:", [t for e, t in worst if e > TOL])
