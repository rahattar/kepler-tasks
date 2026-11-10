"""Route study: defective ways of doing the selection, each graded by the sealed definition.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt

Each route is the reference with one thing done wrong: a record misread, a test plan with a gap where a hoist's
linings run, a fit that assumes something away, or a requirement modelled loosely. Every route picks the settings by
the reference's rule (the largest smallest margin under its own model), so it fails only through what it got wrong.
The matrix at the end shows, hoist by hoist, which routes fail it.
"""
import common as C
from common import F, E

REF = C.REF_PLAN
O1_ONLY = [F(20), F(60), F(110), F(160), F(200), F(250), F(280), E("S16", 65, "AC")]
NO_O2_PEAK = [F(20), F(20, "O2"), F(160), F(160, "O2"), F(260, "O2"), F(60), E("S16", 80, "AC"), E("S18", 57, "DC")]
X3 = [F(20), F(150), F(20, "O2"), F(250, "O2"), F(175, "O2"), E("S16", 65, "DC"), E("S16", 72, "AC"), F(55)]
GAP_O1 = [F(20), F(160), F(20, "O2"), F(160, "O2"), F(200, "O2"), F(260, "O2"), E("S16", 65, "AC"), E("S16", 65, "DC")]
TWO_POINT = [F(20), F(60), F(160), F(20, "O2"), F(200, "O2"), F(260, "O2"), E("S16", 65, "AC"), E("S18", 55, "DC")]
X1 = [F(20), F(170), F(20, "O2"), F(190, "O2"), E("S16", 64, "AC"), F(280, "O2"), F(70, "O2"), F(70)]
GENERIC = [F(20), F(100), F(200), F(20, "O2"), F(100, "O2"), F(200, "O2"), F(300, "O2"), E("S16", 65, "AC")]

ROUTES = [
    # records
    ("maintenance log missed (register as is)", dict(H=C.hoists(miss=("log",)))),
    ("H05's re-reeving missed (4 falls, 20 t)", dict(H=C.hoists(miss=("reeve",)))),
    ("inverter retrofits missed (H04, H08, H12 as contactor hoists)", dict(H=C.hoists(miss=("inverter",)))),
    ("fast lowering missed (H04, H08)", dict(H=C.hoists(miss=("fast",)))),
    ("two-speed hoists' working stops from full speed", dict(H=C.hoists(miss=("twospeed",)))),
    ("contactor lowering at the motor's rated speed (below synchronous)", dict(H=C.hoists(miss=("lower_speed",)))),
    # friction plans and fits
    ("no tests: catalogue torque at every temperature, catalogue engagement", dict(M=C.catalogue_model(), reach=1e9)),
    ("O1 only (20-280 C), O2 taken to behave as O1", dict(plan=O1_ONLY, same_lining=True)),
    ("O2 without a test near 200 C (probe x2's tests)", dict(plan=NO_O2_PEAK)),
    ("O2 at 175 and 250 C, two engagement tests (probe x3's tests)", dict(plan=X3)),
    ("O1 without a test at the cool hoists' 50-65 C (DC engagement instead)", dict(plan=GAP_O1)),
    ("O2 without a test at H07's 160 C (DC engagement instead)", dict(plan=TWO_POINT)),
    ("O2 at 70, 190 and 280 C, none at H07's 160 C (probe x1's tests)", dict(plan=X1)),
    ("generic grid: each lining at 20, 100, 200 (O2 also 300) C", dict(plan=GENERIC)),
    ("reference tests, friction extrapolated beyond the tested range", dict(plan=REF, reach=1e9)),
    # engagement
    ("reference tests, engagement test ignored (catalogue times at every setting)", dict(plan=REF, engagement="catalogue")),
    # requirements
    ("holding with the gear's efficiency credited", dict(plan=REF, hold_eff=True)),
    ("deceleration checked with the empty hook only", dict(plan=REF, decel_case="empty")),
    ("deceleration checked lowering the rated load only", dict(plan=REF, decel_case="lower")),
    ("deceleration and gearbox at the duty temperature only", dict(plan=REF, decel_T="duty")),
    ("duty temperature as the time-average, not the peak after a stop", dict(plan=REF, duty_T="mean")),
    ("no engagement delay (brake acts when the power is cut)", dict(plan=REF, engage_phase=False)),
]


def main():
    print(__doc__.split("\n\n")[0].strip())
    print("Shipped scenario, laboratory seed %d. Reference: 12 of 12.\n" % C.SEED)
    matrix = {}
    for name, kw in ROUTES:
        picks, n, fails = C.run(**kw)
        matrix[name] = {f.split()[0] for f in fails}
        print("%-74s %2d/12  %s" % (name, n, " ".join(fails)), flush=True)
    print("\nFailed hoists by route (x = fails at least one requirement):")
    print("%-4s" % "" + " ".join("%2d" % (i + 1) for i in range(len(ROUTES))))
    for hid in C.IDS:
        print("%-4s" % hid + " ".join(" x" if hid in matrix[nm] else " ." for nm, _ in ROUTES)
              + "   failed by %d" % sum(hid in matrix[nm] for nm, _ in ROUTES))
    print("\nRoutes: " + "; ".join("%d %s" % (i + 1, nm) for i, (nm, _) in enumerate(ROUTES)))
    same = [nm for nm, _ in ROUTES if not matrix[nm]]
    print("\nDepartures that still get 12 of 12 on this scenario (the windows absorb them): " + "; ".join(same) + ".")


if __name__ == "__main__":
    main()
