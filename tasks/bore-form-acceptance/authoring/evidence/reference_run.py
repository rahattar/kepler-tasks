"""The shipped scenario, feature by feature: what the reference gets, and how much room it has.

    python3 reference_run.py > reference_run.txt
"""
import common as C


def main():
    P = C.plan_reference()
    ans = C.sentence(plan=P)
    w, where, wrong, det = C.grade(ans)
    print("scans ordered: %s   (booking %d)" % (" ".join(P), C.BUDGET))
    print("band on the form error %.1f um; the gate is all %d features\n" % (C.TOL_FORM, len(C.ORDER)))
    print("%-7s %-13s %7s %7s %7s | %-12s %-12s %s" % (
        "feature", "characteristic", "form", "true", "error", "sentence", "true", "room to the nearest limit"))
    for f in C.ORDER:
        t = C.TRUTH[f]
        form, v = ans[f]
        room = min(abs(t["form_margin"]), abs(t["size_margin"]), abs(t["local_margin"]))
        print("%-7s %-13s %7.2f %7.2f %+7.2f | %-12s %-12s %5.1f um (%s)" % (
            f, C.DRAW[f]["form_characteristic"], form, t["form"], form - t["form"], v, t["verdict"], room,
            "form" if abs(t["form_margin"]) == room else ("size" if abs(t["size_margin"]) == room else "local")))
    print("\nworst error on a form error %.2f um at %s, against the band of %.1f" % (w, where, C.TOL_FORM))
    print("features sentenced wrong: %d" % len(wrong))


if __name__ == "__main__":
    main()
