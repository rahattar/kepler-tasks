"""Recomputes the sealed life fractions from the sealed definition and compares them with tests/superheater.py.
Writes calibration.txt."""
import methods as M


def main():
    d = M.T.truth()
    lines = ["%s recomputed %.6f  sealed %.6f  ratio %.6f" % (e, d[e], M.TRUTH.DAMAGE[e], d[e] / M.TRUTH.DAMAGE[e]) for e in M.S.E]
    lines.append("largest relative difference %.1e" % max(abs(d[e] / M.TRUTH.DAMAGE[e] - 1) for e in M.S.E))
    print("\n".join(lines))
    open("calibration.txt", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
