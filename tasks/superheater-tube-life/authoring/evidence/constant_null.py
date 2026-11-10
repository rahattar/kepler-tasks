"""Answers that use no assessment: one constant for every element, and each element filled from its neighbours.
Writes constant_null.txt."""
import numpy as np
import methods as M

D = M.TRUTH.DAMAGE
E = M.S.E


def main():
    lines = []
    best = max(((sum(abs(c / D[e] - 1) <= 0.25 for e in E), c) for c in np.geomspace(0.01, 1.0, 2000)))
    lines.append("best single constant %.4f satisfies %d of 10" % (best[1], best[0]))
    for e in E:
        i = E.index(e)
        nb = [D[E[j]] for j in (i - 1, i + 1) if 0 <= j < len(E)]
        g = float(np.exp(np.mean(np.log(nb))))
        lines.append("%s from its neighbours' geometric mean: %+.0f%%" % (e, 100 * (g / D[e] - 1)))
    print("\n".join(lines))
    open("constant_null.txt", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
