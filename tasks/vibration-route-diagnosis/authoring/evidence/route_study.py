"""Wrong side of the bound (at most 2 of the 60 hidden machines wrong): the reference program with one of its checks
or one engineering step left out at a time, graded on the hidden route packages.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import common as C

VARIANTS = {
    "tach taken as one pulse per turn (no check for a second bright mark)": (
        "k = max(1, int(round(ft / (0.985 * sync_hz(r)))))", "k = 1"),
    "high capture taken at the route file's planned sample rate": (
        "    best, score = fs_planned, 0\n", "    return fs_planned\n"),
    "captures taken as labelled (no check for crossed-over points)": (
        "        if not vtp and crossed(m, r, caps, f1, drive_hz):", "        if False:"),
    "no sensor channel check, and half orders read by amplitude only": (
        ("    return np.median(vel(f, X)[(f > 0.7) & (f < 4)]) < 0.5        # mm/s; no machine line lies below 4 Hz",
         "    return True"),
        ("amp(f, v, h * fs_) if prominent(f, v, h * fs_, 5) else 0.0", "amp(f, v, h * fs_)")),
    "bearings as in the register (maintenance log not read)": (
        'if e["machine"] == m and "bearing replaced"', 'if False and "bearing replaced"'),
    "fan bearings and fan rotor at motor speed (sheave ratio ignored)": (
        'shaft = {p: (f1 * ratio if p == "FAN" else f1) for p in pts}', 'shaft = {p: f1 for p in pts}'),
    "1x read as the largest line within 3 bins (a neighbour's line taken as the machine's own)": (
        "fe = dict(f=f, v=v, X=X, one=amp(f, v, fs_)", "fe = dict(f=f, v=v, X=X, one=amp(f, v, fs_, 3)"),
    "VFD machines at nameplate speed": (
        '    if "VFD" in r["drive"]:\n        # motor 1x', '    if False:\n        # motor 1x'),
}

if __name__ == "__main__":
    base = open(C.SOLUTION).read()
    r = C.grade_text(base)
    print("Hidden machines misdiagnosed (of 60); the bound is 2.\n")
    print("%-92s %2d" % ("reference (solution/diagnose.py)", r["wrong"]))
    least = 99
    for name, edits in VARIANTS.items():
        if isinstance(edits[0], str):
            edits = (edits,)
        t = base
        for old, new in edits:
            assert t.count(old) == 1, name
            t = t.replace(old, new)
        r = C.grade_text(t)
        least = min(least, r["wrong"])
        print("%-92s %2d  %s" % (name, r["wrong"], "; ".join(C.misses(r))))
    print("\nEvery check or step left out misdiagnoses at least %d hidden machines." % least)
