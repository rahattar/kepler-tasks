"""Shortcuts and incomplete plans against the reference, on the shipped floor.

    python3 route_study.py > route_study.txt
"""
import methods as M

P = M.REFERENCE_PLAN                                     # 36, 37, 38 (labs on 2.4), 28 (vertical drop), 31 (long run)


def show(name, cal):
    e, worst, fails = M.grade(cal)
    print("  %-66s worst %5.1f %% (%s)  fails %2d  %s" % (name, 100 * e, worst[-2:], len(fails),
                                                       " ".join(f[-2:] for f in fails[:10])))


def main():
    print("acceptance: delivered airflow within 10 % of setpoint at design minimum and maximum, every box\n")
    show("factory K and offset 0 (as shipped)", {t: (M.KF[t], 0.0) for t in M.TAGS})
    show("reference: visits 36 37 38 28 31, class transfer", M.calibrate(P))
    print("\nshortcuts on the reference plan")
    show("offsets only on firmware 2.4 (failed auto-zero on a 3.1 box missed)", M.calibrate(P, az_check=False))
    show("no closed-damper offsets", M.calibrate(P, night_offsets=False))
    show("2024 report used for the east wing too", M.calibrate(P, use_stale=True))
    show("one elbow model for both orientations", M.calibrate(P, vertical="pool"))
    show("punch-list connectors taken at their surveyed L/D", M.calibrate(P, kinks="survey"))
    show("visits fitted for K only, at design maximum, offset 0", M.calibrate(P, one_point=True))
    print("\nincomplete plans (each with its most forgiving fallback where several are defensible)")
    alts = [
        ("no vertical-drop visit (34 instead), drops at factory K",
         M.calibrate(M.LABS24 + ["VAV-3-34", "VAV-3-31"], vertical="factory")),
        ("no vertical-drop visit (34 instead), drops on the horizontal model",
         M.calibrate(M.LABS24 + ["VAV-3-34", "VAV-3-31"], vertical="horizontal")),
        ("no long-run visit (34 instead), long runs as ordinary flex",
         M.calibrate(M.LABS24 + ["VAV-3-28", "VAV-3-34"], sag="flex")),
        ("no long-run visit (34 instead), long runs at the kinked factor",
         M.calibrate(M.LABS24 + ["VAV-3-28", "VAV-3-34"], sag="kinked")),
    ]
    for name, cal in alts:
        show(name, cal)
    for skip in M.LABS24:
        rest = [x for x in M.LABS24 if x != skip]
        extra = "VAV-3-34" if skip == "VAV-3-38" else "VAV-3-30"
        for lz in ("fleet", "labs"):
            show("lab %s not visited (%s instead), zero = %s" % (skip[-2:], extra[-2:],
                 "median of the 2.4 zeros" if lz == "fleet" else "mean of the visited labs"),
                 M.calibrate(rest + [extra, "VAV-3-28", "VAV-3-31"], lab_zero=lz))
    print("\nnot a method, shown for completeness: an unvisited 2.4 lab given offset 0")
    for skip in M.LABS24:
        rest = [x for x in M.LABS24 if x != skip]
        extra = "VAV-3-34" if skip == "VAV-3-38" else "VAV-3-30"
        show("lab %s not visited, offset 0" % skip[-2:], M.calibrate(rest + [extra, "VAV-3-28", "VAV-3-31"], lab_zero="zero"))


if __name__ == "__main__":
    main()
