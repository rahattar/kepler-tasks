"""Each defective route's sheet, scored by the verifier's grading module on the shipped data.

    python3 route_study.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TASK = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(TASK, "tests"))
sys.path.insert(0, HERE)
import grade_rating as G  # noqa: E402
import routes  # noqa: E402

DATA = os.path.join(TASK, "environment", "data")


sys.path.insert(0, os.path.join(TASK, "authoring", "provenance"))
import supply_site  # noqa: E402

_MAIN = supply_site.Main()


def run(cls):
    order = cls.order(DATA) if hasattr(cls, "order") else routes.reference_order(DATA)
    report = supply_site.flow_test(order["riser"], order["flow_gpm"], supply_site.SEED, _MAIN) if order else None
    res = cls(DATA, report).rate()
    path = os.path.join(tempfile.mkdtemp(), "rating.csv")
    routes.R.write(res, path)
    return G.score(path)


def main():
    truth = G.sealed()
    failed_by = {rid: 0 for rid in truth}
    for cls in [routes.R.Audit] + routes.ROUTES:
        try:
            ok, detail = run(cls)
        except (G.Refused, ValueError, ZeroDivisionError) as e:
            for rid in failed_by:
                failed_by[rid] += 1
            print("%-22s %-8s no sheet in form (%s)" % (cls.__name__, "refused", e))
            continue
        bad = [rid for rid in sorted(detail) if not detail[rid]["ok"]]
        for rid in bad:
            failed_by[rid] += 1
        worst = max(detail.values(), key=lambda d: abs(d["dp"]))
        print("%-22s %-8s rows wrong %2d  worst p %+6.1f%%  %s" % (
            cls.__name__, "accepted" if ok else "refused", len(bad), 100 * worst["dp"],
            " ".join("%s%s" % (rid[2:], "".join(c for c, k in (("L", "limit"), ("p", "p"), ("q", "q"))
                                             if not detail[rid][k])) for rid in bad)))
    print("routes failing each riser:", " ".join("%s:%d" % (rid, n) for rid, n in sorted(failed_by.items())))


if __name__ == "__main__":
    main()
