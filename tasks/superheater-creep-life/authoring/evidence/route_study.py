"""Each record trap or shortcut taken on its own (everything else as the reference); prints the elements outside 25 %.
Writes route_study.txt."""
import methods as M

ROUTES = [
    ("reference", {}),
    ("historian read as degC throughout", dict(no_unit_fix=True)),
    ("E7/E8 swap left in", dict(no_unswap=True)),
    ("E2's refitted pad trusted", dict(no_e2_fix=True)),
    ("E7's renewed pad trusted", dict(no_e7_fix=True)),
    ("E5's drifting pad trusted", dict(no_drift_fix=True)),
    ("oxide not reset at the 2023 clean", dict(no_clean=True)),
    ("2018 left out", dict(skip_2018=True)),
    ("nominal walls throughout", dict(nominal_walls=True)),
    ("E6 at its register wall", dict(e6_nominal=True)),
    ("E1 thinning linear from 2015", dict(e1_linear=True)),
    ("E3 without oxide: pre-modification ratio", dict(plan=(("E9", "wall-ut"),), e3="premod")),
    ("E3 without oxide: E4's rise carried over", dict(plan=(("E9", "wall-ut"),), e3="e4")),
    ("E9 without wall-ut: nominal wall", dict(plan=(("E3", "oxide-ut"),))),
]


def main():
    lines = []
    for name, o in ROUTES:
        o = dict(o)
        plan = o.pop("plan", (("E3", "oxide-ut"), ("E9", "wall-ut")))
        r = M.misses(M.damage(plan, **o))
        out = {e: v for e, v in r.items() if abs(v) > 0.25}
        worst = max(abs(v) for v in r.values())
        fmt = lambda v: ("%+.0f%%" % (100 * v)) if abs(v) < 100 else "more than 100x"
        fmtw = lambda v: ("%.0f%%" % (100 * v)) if v < 100 else "more than 100x"
        lines.append("%-44s worst %s   outside 25%%: %s" % (name, fmtw(worst), ", ".join("%s %s" % (e, fmt(v)) for e, v in out.items()) or "none"))
        print(lines[-1], flush=True)
    open("route_study.txt", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
