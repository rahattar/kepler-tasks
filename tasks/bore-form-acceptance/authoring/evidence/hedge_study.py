"""Hedging. The sentence is one of four words, so it cannot be split between two readings at all: a sheet must
commit. The form error is a number, so this checks, for every choice a solver faces, whether one number could sit
inside the band under both readings of it (the two readings differ by less than 2 x the band).

    python3 hedge_study.py > hedge_study.txt
"""
import common as C

P = C.plan_reference()
CHOICES = (("the tester's error motion removed or charged to the parts", dict(), dict(spindle="keep")),
           ("minimum zone or least-squares zone", dict(), dict(how="ls")),
           ("the 50 UPR band or the profile unfiltered", dict(), dict(filt="order1")),
           ("cylindricity or roundness where the drawing calls cylindricity", dict(), dict(kindover="roundness")),
           ("a scan carried to the twin of its setup, or the sparse record used", dict(), dict(transfer=False)))


def main():
    print("band %.1f um on the form error; two readings can both be satisfied only if they differ by %.1f um or\n"
          "less. The sentence admits no hedge: it is one of four words and the gate is all %d features.\n"
          % (C.TOL_FORM, 2 * C.TOL_FORM, len(C.ORDER)))
    for name, a, b in CHOICES:
        A, B = C.sentence(plan=P, **a), C.sentence(plan=P, **b)
        both, verdict_differs = 0, 0
        worst = 0.0
        for f in C.ORDER:
            d = abs(A[f][0] - B[f][0])
            worst = max(worst, d)
            if d <= 2 * C.TOL_FORM:
                both += 1
            if A[f][1] != B[f][1]:
                verdict_differs += 1
        print("  %-58s features where one number fits both: %2d of %d" % (name, both, len(C.ORDER)))
        print("  %-58s widest gap %5.2f um; the sentence itself differs on %d" % ("", worst, verdict_differs))
    print("\nSo a solver who will not choose has nothing to fall back on: on the choices that matter the two\n"
          "readings are further apart than the band on most features, and where they are not, the sentence still\n"
          "differs and no word satisfies both.")


if __name__ == "__main__":
    main()
