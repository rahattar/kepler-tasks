"""Every route that gets a feature wrong, on the shipped records: what it costs and which features it loses.
Figures are the worst error on a reported form error (um) and the features sentenced wrong of 14.

    python3 route_study.py > route_study.txt
"""
import common as C

P = C.plan_reference()
ALT = ["CB-22", "CB-25", "RJ-43", "RJ-45"]       # the other twin of each pair


def show(name, ans):
    w, where, wrong, _ = C.grade(ans)
    print("  %-62s worst dform %6.2f (%-5s) wrong %2d  %s"
          % (name, w, where, len(wrong), " ".join(wrong)))


def main():
    print("band on a reported form error %.1f um; the sentence must match exactly; the gate is all %d features\n"
          % (C.TOL_FORM, len(C.ORDER)))
    print("the booking the records call for: %s" % " ".join(P))
    show("reference", C.sentence(plan=P))
    show("reference, the other twin of each pair scanned", C.sentence(plan=ALT))

    print("\nthe reference booking, assessed wrongly")
    show("the form tester's own error motion charged to the parts", C.sentence(plan=P, spindle="keep"))
    show("one error motion pooled over the tester's whole campaign", C.sentence(plan=P, spindle="pooled"))
    show("the whole average of each campaign's records taken off each part", C.sentence(plan=P, spindle="mean"))
    show("the Gaussian 50 UPR taper left off (feed waviness kept in)", C.sentence(plan=P, filt="order1"))
    show("the deviations taken as measured (eccentricity kept in too)", C.sentence(plan=P, filt="none"))
    show("mean diameter in place of the mating cylinder", C.sentence(plan=P, size="mean"))
    show("the mating size alone, no two-point local size", C.sentence(plan=P, local=False))
    show("no temperature correction to 20 C", C.sentence(plan=P, tcorr=False))
    show("roundness computed where the drawing calls cylindricity", C.sentence(plan=P, kindover="roundness"))

    print("\nthe booking spent otherwise")
    show("no scans at all: every record taken as it stands", C.sentence(plan=[]))
    show("scans ordered but the setup not used to carry a twin", C.sentence(plan=P, transfer=False))
    show("one scan for each sparse feature (the re-honed bore left out)",
         C.sentence(plan=["CB-24", "CB-25", "RJ-42", "RJ-43"]))
    show("the re-honed bore scanned, a sparse pair left on its own records",
         C.sentence(plan=["CB-22", "CB-24", "CB-25", "RJ-42"]))
    show("the booking spent on four features whose records are sound",
         C.sentence(plan=["CB-21", "CB-23", "CB-26", "GB-31"]))
    show("the first four features of the register scanned",
         C.sentence(plan=["CB-21", "CB-22", "CB-23", "CB-24"]))
    show("only the re-honed bore scanned, three scans left unused", C.sentence(plan=["CB-22"]))

    print("\nsound choices, for the record (these pass)")
    print("\nwhich features each defective route loses (count of the routes above that lose it)")
    tally = {f: 0 for f in C.ORDER}
    for kw in (dict(plan=P, spindle="keep"), dict(plan=P, spindle="pooled"), dict(plan=P, spindle="mean"),
               dict(plan=P, how="ls"), dict(plan=P, filt="order1"), dict(plan=P, filt="none"),
               dict(plan=P, size="mean"), dict(plan=P, tcorr=False), dict(plan=P, kindover="roundness"),
               dict(plan=[]), dict(plan=P, transfer=False),
               dict(plan=["CB-24", "CB-25", "RJ-42", "RJ-43"]), dict(plan=["CB-22", "CB-24", "CB-25", "RJ-42"]),
               dict(plan=["CB-21", "CB-23", "CB-26", "GB-31"]), dict(plan=["CB-21", "CB-22", "CB-23", "CB-24"]),
               dict(plan=["CB-22"])):
        for f in C.grade(C.sentence(**kw))[2]:
            tally[f] += 1
    print("  " + "  ".join("%s %d" % (f, n) for f, n in tally.items()))
    print("  fewest: %s" % min(tally.values()))


if __name__ == "__main__":
    main()
