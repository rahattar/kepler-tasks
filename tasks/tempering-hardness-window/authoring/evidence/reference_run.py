"""The reference solution on the shipped scenario (laboratory emulator = the real laboratory's readings).

    python3 authoring/evidence/reference_run.py     (writes reference_run.txt)
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402


def main():
    lines = []
    temps, tests, lab = C.run_reference(seed=C.SEED, quiet=True)
    import solve
    lines.append("seed %d; plan %s" % (C.SEED, ", ".join("%s@%s%s" % (h, b, " double" if d else "") for h, b, d in solve.PLAN)))
    for heat, Tl, D, loc, double, h, off in tests:
        lines.append("test %s %d C %d mm %s%s -> %.1f HRC (offset against the model %+.2f)" % (
            heat, Tl, D, loc, " double" if double else "", h, off))
    lines.append("tempers used %d of %d" % (lab.used, lab.budget))
    res, n = C.grade(temps)
    for b, T in temps.items():
        W = C.S.window(b)
        lines.append("%s %s %d C -> true %.2f HRC, margin %+.2f (window %d-%d C) %s" % (
            b, C.S.BATCHES[b][1], T, res[b][1], C.margin(b, T), W[0], W[-1], "ok" if res[b][0] else "BAD"))
    lines.append("reference: %d of 13 batches right; smallest true margin %+.2f HRC" % (
        n, min(C.margin(b, T) for b, T in temps.items())))
    return "\n".join(lines)


if __name__ == "__main__":
    txt = main()
    print(txt)
    open(os.path.join(HERE, "reference_run.txt"), "w").write(txt + "\n")
