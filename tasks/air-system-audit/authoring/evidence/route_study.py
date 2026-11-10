"""Wrong side of the bound (at most 1 of the 8 hidden sites wrong): the reference program with one check or step
left out at a time, graded on the hidden audit packages.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import common as C

VARIANTS = {
    "demand taken as supply (storage in the receiver and piping left out)": (
        "    demand = supply - V / patm * (p_end - p_start) / DT * 60.0", "    demand = supply"),
    "pressure log taken on its own clock (no clock check)": ("        if cc > best:", "        if lag == 0:"),
    "load/unload power logs taken as recorded (no one-CT check)": (
        "                if 0.25 < level < 0.45:", "                if False:"),
    "variable-speed power logs taken as recorded (no one-CT check)": (
        "                if run.size and np.percentile(run, 5) < 0.6 * min(w):", "                if False:"),
    "no one-CT check at all": (
        "                if 0.25 < level < 0.45:", "                if False:",
        "                if run.size and np.percentile(run, 5) < 0.6 * min(w):", "                if False:"),
    "an interval counted loaded when its power is above half of full load": (
        "                    if r >= 0.92:\n", "                    frac[i] = float(r > 0.5)\n                    continue\n"
        "                    if r >= 0.92:\n"),
}

if __name__ == "__main__":
    base = open(C.SOLUTION).read()
    r = C.grade_text(base)
    print("Hidden sites wrong (of 8); the bound is 1.\n")
    print("%-75s %d" % ("reference (solution/audit.py)", r["wrong"]))
    for name, pairs in VARIANTS.items():
        text = base
        for old, new in zip(pairs[::2], pairs[1::2]):
            assert base.count(old) == 1, name
            text = text.replace(old, new)
        r = C.grade_text(text)
        print("%-75s %d  %s" % (name, r["wrong"], "; ".join(C.misses(r))))
