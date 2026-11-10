"""Shortcuts and plans that spend the three steps differently, against the reference, on the shipped bay. Figures
are the worst zone's |wafer - setpoint| in K; acceptance 2 K.

    python3 route_study.py > route_study.txt
"""
import methods as M

P = M.REFERENCE_PLAN


def show(name, cal):
    e, z, fails = M.grade(cal)
    print("  %-78s worst %5.2f K (%s)  fails %2d  %s" % (name, e, z, len(fails), " ".join(fails[:8])))


def main():
    print("acceptance: wafer within 2 K of the setpoint at 850 C and 1050 C, every zone\n")
    show("corrections loaded now (2025 calibration; F8 factory values)",
         {(r.furnace, r.zone): (r.correction_850_c, r.correction_1050_c) for r in M.LOADED.itertuples()})
    show("reference: F3@1050 F5@1050 F8@1050", M.calibrate(P))
    print("\nshortcuts on the reference plan")
    show("drift at 600 C used at every temperature (not carried by T/600)", M.calibrate(P, scale="none"))
    show("drift carried in kelvin, (T+273)/873, against the stated 1.75 at 1050 C", M.calibrate(P, scale="K"))
    show("offset ratio taken as 850/1050 (offset not zero in the soak)", M.calibrate(P, rho="linear"))
    show("offset ratio from T^4 without the zero at 600 C", M.calibrate(P, rho="t4_no_reference"))
    show("liner change not applied to F2 and F7", M.calibrate(P, use_liner=False))
    show("F3's liner change carried over unchanged to F2 and F7 (liners shield differently)",
         M.calibrate(P, liner="same"))
    show("partial boats read as full boats in the process trends (F2, F7 run without fill dummies)",
         M.calibrate(P, boats="all"))
    show("partial boats kept, boat load as a regressor (passes)", M.calibrate(P, boats="regress"))
    show("F6 drift from its 2026-09-15 hold as read (growth since not carried)", M.calibrate(P, growth="none"))
    show("F6 'hold' rows not read: F6 drift from the bay median", M.calibrate(P, hold=False))
    show("F6 'hold' rows not read: F6 drift from F3", M.calibrate(P, hold=False, unknown="other"))
    show("F6 growth at 850 C added as if it were drift at 600 C (passes)", M.calibrate(P, growth="unscaled"))
    show("F3 split with the four-week mean of its 850 C trend (passes: F3 grows slowly)",
         M.calibrate(P, split_gap="mean"))
    print("\nplans that spend the steps differently (most forgiving fallback where several are defensible)")
    alts = [
        ("F3@1050 F5@1050 F6@1050 (F8 factory values)", [("F3", (1050,)), ("F5", (1050,)), ("F6", (1050,))], {}),
        ("F3@1050 F5@1050 F6@1050 (F8 from the 2025 T-200 offsets)", [("F3", (1050,)), ("F5", (1050,)), ("F6", (1050,))],
         dict(f8="fleet")),
        ("F3@1050 F6@600 F8@1050 (F5 at its 2025 offset)", [("F3", (1050,)), ("F6", (600,)), ("F8", (1050,))], {}),
        ("F3@1050 F6@600 F8@1050 (F5 from the 2025 T-200 offsets)", [("F3", (1050,)), ("F6", (600,)), ("F8", (1050,))],
         dict(f5="fleet")),
        ("F2@1050 F3@1050 F8@1050 (second liner measured; F5 at its 2025 offset)",
         [("F2", (1050,)), ("F3", (1050,)), ("F8", (1050,))], {}),
        ("F2@1050 F3@1050 F8@1050 (second liner measured; F5 from the 2025 T-200 offsets)",
         [("F2", (1050,)), ("F3", (1050,)), ("F8", (1050,))], dict(f5="fleet")),
        ("F7@1050 F3@1050 F5@1050 (second liner measured; F8 factory values)",
         [("F7", (1050,)), ("F3", (1050,)), ("F5", (1050,))], {}),
        ("F2@1050 F7@1050 F3@1050 (every liner measured; F5 2025, F8 factory values)",
         [("F2", (1050,)), ("F7", (1050,)), ("F3", (1050,))], {}),
        ("F3@600+1050 F5@1050 (F8 factory values)", [("F3", (600, 1050)), ("F5", (1050,))], {}),
        ("F3@600+1050 F8@1050 (F5 at its 2025 offset)", [("F3", (600, 1050)), ("F8", (1050,))], {}),
        ("F3@850+1050 F5@1050 (F8 factory values)", [("F3", (850, 1050)), ("F5", (1050,))], {}),
        ("F3@850 F5@1050 F8@1050 (850 C repeats the trend: no split; F3 drift from the bay median)",
         [("F3", (850,)), ("F5", (1050,)), ("F8", (1050,))], {}),
        ("F3@850 F5@1050 F8@1050 (F3 drift from F6)", [("F3", (850,)), ("F5", (1050,)), ("F8", (1050,))],
         dict(unknown="other")),
        ("F2@1050 F5@1050 F8@1050 (F3 not run, drift from the bay median)",
         [("F2", (1050,)), ("F5", (1050,)), ("F8", (1050,))], {}),
        ("F2@1050 F5@1050 F8@1050 (F3 not run, drift from F6)",
         [("F2", (1050,)), ("F5", (1050,)), ("F8", (1050,))], dict(unknown="other")),
    ]
    for name, plan, kw in alts:
        show(name, M.calibrate(plan, **kw))


if __name__ == "__main__":
    main()
