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


WRONGLY = [
    ("the form tester's own error motion charged to the parts", dict(spindle="keep")),
    ("one error motion pooled over the tester's whole inspection", dict(spindle="pooled")),
    ("only the line every record agrees on taken off (order 23)", dict(spindle="lines")),
    ("each campaign's mean vector taken off at the machine's orders", dict(spindle="epoch")),
    ("the machine's orders struck out of the tester's records", dict(spindle="delete")),
    ("the whole average of each campaign's records taken off each part", dict(spindle="mean")),
    ("a least-squares zone in place of the minimum zone", dict(how="ls")),
    ("the Gaussian 50 UPR taper left off (feed waviness kept in)", dict(filt="order1")),
    ("the deviations taken as measured (eccentricity kept in too)", dict(filt="none")),
    ("mean diameter in place of the mating cylinder", dict(size="mean")),
    ("the mating size alone, no two-point local size", dict(local=False)),
    ("no temperature correction to 20 C", dict(tcorr=False)),
    ("roundness computed where the drawing calls cylindricity", dict(kindover="roundness")),
]
OTHERWISE = [
    ("no scans at all: every record taken as it stands", dict(plan=[])),
    ("scans ordered but the setup not used to carry a twin", dict(plan=P, transfer=False)),
    ("one scan for each sparse feature (the re-honed bore left out)", dict(plan=["CB-24", "CB-25", "RJ-42", "RJ-43"])),
    ("the honed bore's twin scanned in its place", dict(plan=["RJ-44", "CB-24", "RJ-42", "RJ-45"])),
    ("the re-honed bore scanned, a sparse pair left on its own records", dict(plan=["CB-22", "CB-24", "CB-25", "RJ-42"])),
    ("the booking spent on four features whose records are sound", dict(plan=["CB-21", "CB-23", "CB-26", "GB-31"])),
    ("the first four features of the register scanned", dict(plan=["CB-21", "CB-22", "CB-23", "CB-24"])),
    ("only the re-honed bore scanned, three scans left unused", dict(plan=["CB-22"])),
]


def main():
    print("band on a reported form error %.1f um; the sentence must match exactly; the gate is all %d features\n"
          % (C.TOL_FORM, len(C.ORDER)))
    print("the booking the records call for: %s" % " ".join(P))
    show("reference", C.sentence(plan=P))
    show("reference, the other twin of each pair scanned", C.sentence(plan=ALT))

    # One list drives both what is shown and what is counted, so the count cannot fall out of step with the
    # table (it once did: a route was counted that the table no longer showed, and had been silently inert).
    tally = {f: 0 for f in C.ORDER}
    print("\nthe reference booking, assessed wrongly")
    for name, kw in WRONGLY:
        ans = C.sentence(plan=P, **kw)
        show(name, ans)
        for f in C.grade(ans)[2]:
            tally[f] += 1
    print("\nthe booking spent otherwise")
    for name, kw in OTHERWISE:
        ans = C.sentence(**kw)
        show(name, ans)
        for f in C.grade(ans)[2]:
            tally[f] += 1

    print("\n%d defective routes. How many of them lose each feature:" % (len(WRONGLY) + len(OTHERWISE)))
    print("  " + "  ".join("%s %d" % (f, n) for f, n in tally.items()))
    print("  fewest: %s" % min(tally.values()))


if __name__ == "__main__":
    main()
