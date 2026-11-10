"""Grade a fouling file (path argument, or FOULING_PATH, default /app/output/fouling.csv) on the bank's sealed
definition (hx.py, seed 11). Each unit's reported as-found fouling resistance is compared with its true value on
the test day (2026-10-26, before cleaning). A unit passes when the difference is within TOL m2K/kW; the file passes
when all ten units pass.

File rules: a header with the columns unit and fouling_m2k_per_kw (any order, other columns ignored), one row for
each of E1-E10 and no others, finite numbers.
"""
import csv, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hx

TOL = 0.04          # m2K/kW, process engineering's requirement


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
    for col in ("unit", "fouling_m2k_per_kw"):
        if col not in head:
            raise ValueError("header has no column %r" % col)
    i_u, i_r = head.index("unit"), head.index("fouling_m2k_per_kw")
    est = {}
    for r in rows[1:]:
        u = r[i_u].strip().upper()
        if u in est:
            raise ValueError("unit %s appears twice" % u)
        est[u] = _num(r[i_r])
    return est


def grade(path):
    fleet = hx.make_fleet(11)
    est = read(path)
    unknown = sorted(set(est) - set(hx.UNITS))
    if unknown:
        raise ValueError("unknown units %s" % unknown)
    out = dict(passed=True, units={}, missing=[u for u in hx.UNITS if u not in est])
    for u in hx.UNITS:
        if u not in est:
            out["units"][u] = dict(passed=False, reason="no row")
            out["passed"] = False
            continue
        true = hx.rf(fleet[u], hx.T_TEST)
        err = est[u] - true
        rec = dict(reported=est[u], error_m2k_per_kw=round(err, 4), passed=abs(err) <= TOL)
        out["units"][u] = rec
        out["passed"] &= rec["passed"]
    return out


if __name__ == "__main__":
    r = grade(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("FOULING_PATH", "/app/output/fouling.csv"))
    worst = sorted(((abs(v.get("error_m2k_per_kw", 99)), k) for k, v in r["units"].items()), reverse=True)
    print("passed" if r["passed"] else "failed", "| worst %.3f m2K/kW at %s" % worst[0],
          "| failing:", [k for e, k in worst if e > TOL])
