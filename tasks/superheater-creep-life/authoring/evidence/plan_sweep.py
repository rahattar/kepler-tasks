"""Every inspection order of up to two measurements (20 single tests, 190 pairs, and none). The reference method uses
an oxide result only on E3 (to fix its flux after the burner modification) and a wall result only on E9 (its
unrecorded spare); any other result leaves the method unchanged, so a plan's outcome is that of the class
(E3 oxide in it?, E9 wall in it?). Each class is computed, then every plan is listed under its class. Writes
plan_sweep.txt."""
import itertools
import methods as M

OPTS = [(e, t) for e in M.S.E for t in M.TESTS]


def main():
    cls = {}
    for a in (False, True):
        for b in (False, True):
            plan = tuple(x for x, on in ((("E3", "oxide-ut"), a), (("E9", "wall-ut"), b)) if on)
            r = M.misses(M.damage(plan))
            cls[(a, b)] = {e: v for e, v in r.items() if abs(v) > 0.25}
    plans = [()] + [(x,) for x in OPTS] + list(itertools.combinations(OPTS, 2))
    lines = []
    for (a, b), out in cls.items():
        n = [p for p in plans if (("E3", "oxide-ut") in p) == a and (("E9", "wall-ut") in p) == b]
        lines.append("E3 oxide %-5s E9 wall %-5s: %3d plans, outside 25%%: %s" % (a, b, len(n), ", ".join("%s %+.0f%%" % kv for kv in [(e, 100 * v) for e, v in out.items()]) or "none (pass)"))
    passing = [p for p in plans if ("E3", "oxide-ut") in p and ("E9", "wall-ut") in p]
    lines.append("plans considered: %d; passing: %d (%s)" % (len(plans), len(passing), "; ".join(" + ".join("%s %s" % x for x in p) for p in passing)))
    print("\n".join(lines))
    open("plan_sweep.txt", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
