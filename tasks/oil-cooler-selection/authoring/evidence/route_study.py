"""Wrong side of the bound (at most 1 of the 8 hidden cases wrong): the reference program with one data check or
one step of the procedure left out at a time, graded on the hidden case packages.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import common as C

VARIANTS = {
    "calibration as-found errors not applied": (
        '        if c["adjusted"].strip().lower() != "yes" or c["tag"] not in col:', '        if True:'),
    "instrument glitches kept": (
        '    x = x.copy()\n    for i in range(1, len(x) - 1):', '    x = x.copy()\n    for i in range(0):'),
    "inlet water transmitter trusted as recorded": (
        "    cwin = np.where(bad, ch + offset, ci)", "    cwin = ci"),
    "frozen transmitter caught, but not one that stops tracking the water": (
        "    bad |= roll > 0.8\n", ""),
    "oil grade change after the latest analysis ignored": (
        '        if e["date"] > an["sample_date"] and "refilled with" in e["text"]:', '        if False:'),
    "design values from the highest 10-minute value, not the one-hour mean": (
        "        if s[i] - s[j] >= 50.0 - 1e-9:", "        if True:\n            j = i"),
}

if __name__ == "__main__":
    base = open(C.SOLUTION).read()
    r = C.grade_text(base)
    print("Hidden cases wrong (of 8); the bound is 1.\n")
    print("%-75s %d" % ("reference (solution/design.py)", r["wrong"]))
    least = 9
    for name, (old, new) in VARIANTS.items():
        assert base.count(old) == 1, name
        r = C.grade_text(base.replace(old, new))
        least = min(least, r["wrong"])
        print("%-75s %d  %s" % (name, r["wrong"], "; ".join(C.misses(r))))
    print("\nEvery check or step left out gets at least %d hidden cases wrong." % least)
