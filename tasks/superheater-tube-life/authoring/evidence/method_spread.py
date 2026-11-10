"""Sound variants of the reference (choices an engineer could defend); all must pass. Writes method_spread.txt."""
import methods as M

VARIANTS = [
    ("reference", {}),
    ("fills from E1 instead of E2", dict(sister_A="E1")),
    ("fills from E10 instead of E7 (E9)", dict(sister_B="E10")),
    ("fill ratios over 6 months", dict(window=0.5)),
    ("fill ratios over 2 years", dict(window=2.0)),
    ("2018 headers at their 2017 means", dict(hdr_2018="2017")),
]


def main():
    lines, worst_all = [], 0.0
    for name, o in VARIANTS:
        r = M.misses(M.damage(**o))
        w = max(r.items(), key=lambda kv: abs(kv[1]))
        worst_all = max(worst_all, abs(w[1]))
        lines.append("%-40s worst %s %+.1f%%   all: %s" % (name, w[0], 100 * w[1], " ".join("%s %+.1f" % (e, 100 * v) for e, v in r.items())))
        print(lines[-1], flush=True)
    lines.append("largest miss over the variants: %.1f%%" % (100 * worst_all))
    open("method_spread.txt", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
