"""Wrong side of the 3 pp bound: the reference with one record trap fallen into at a time.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import methods as M

TRAPS = [
    ("reference", {}),
    ("dry bulb taken as the wet bulb", dict(db_as_wb=True)),
    ("standard sea-level pressure instead of the site's", dict(std_pressure=True)),
    ("windy hours kept", dict(no_wind_filter=True)),
    ("C1-C4 riser flows left in US gpm", dict(no_gpm=True)),
    ("met station time taken as plant time", dict(utc=0)),
    ("met station shifted by 6 h (standard time)", dict(utc=6)),
    ("C3 riser meter zero not removed", dict(no_c3_zero=True)),
    ("C6 riser meter trusted", dict(c6_trusted=True)),
    ("C6 flow taken as header minus the other risers", dict(c6_by_subtraction=True)),
    ("C1 bypass ignored (no bypass flow anywhere)", dict(no_bypass=True)),
    ("C1 weir temperature not unmixed", dict(no_unmix=True)),
    ("C2 replacement thermocouple trusted", dict(c2_trusted=True)),
    ("C4 replacement motor's power trusted", dict(c4_trusted=True)),
    ("C8 recirculation kept after its stack was extended", dict(recirc_always=True)),
    ("C5 flume reading taken as C5's basin", dict(flume_trusted=True)),
    ("C3 hours before the new fill kept", dict(keep_old_fill=True)),
    ("median of the whole record instead of the end of it", dict(end="median")),
]

if __name__ == "__main__":
    print("Miss per cell, percentage points (reported - true); the bound is 3 pp.\n")
    worst_trap = []
    for name, o in TRAPS:
        d = M.misses(o)
        bad = [c for c in M.CELLS if d[c] != d[c]]
        if bad:
            print("%-52s no valid hours left for %s" % (name, " ".join(bad)))
            continue
        w = max(d.values(), key=abs)
        cell = max(d, key=lambda c: abs(d[c]))
        print("%-52s worst %+7.1f (%s)  %s" % (name, w, cell, " ".join("%s %+.1f" % (c, d[c]) for c in M.CELLS)))
        if o:
            worst_trap.append(abs(w))
    print("\nNearest trap: %.1f pp" % min(worst_trap))
    d = M.misses(dict(no_recirc=True))
    print("\nNot a trap: leaving out C8's recirculation altogether (the survey's 2.0 K before the stack too) moves C8 by "
          "%+.1f pp, since the end of the record falls after the stack was extended." % d["C8"])
