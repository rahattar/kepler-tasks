"""Wrong side of the 0.3 % bound: the correct program (solution/gtperf.py) with one of the shipped program's defects
put back at a time, and the shipped program itself, each graded on the eight hidden record sets.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import common as C

if __name__ == "__main__":
    print("Hidden record sets failed, and the misses (output/heat rate, percent) on the failed sets; the bound is 0.3 %.\n")
    n, w, s = C.summary(C.grade_text(open(C.SOLUTION).read()))
    print("%-62s %d of 8 fail  (largest miss %.2f %%)" % ("correct program (solution/gtperf.py)", n, w))
    least = []
    for b in C.bugs.ALL:
        r = C.grade_text(C.bugs.make([b]))
        n, w, s = C.summary(r)
        big = max([abs(100 * v["output_miss"]) for v in r["sets"].values() if not v["accepted"] and "output_miss" in v]
                  + [abs(100 * v["heat_rate_miss"]) for v in r["sets"].values() if not v["accepted"] and "heat_rate_miss" in v]
                  + [999.0 if any(v.get("error") for v in r["sets"].values()) else 0.0])
        least.append(big)
        print("%-62s %d of 8 fail  %s" % (C.bugs.BUGS[b][0][:62], n, s))
    n, w, s = C.summary(C.grade_text(C.bugs.make(C.bugs.ALL)))
    print("%-62s %d of 8 fail" % ("the shipped program (all of the above)", n))
    print("\nEvery defect alone fails at least one hidden set; the smallest largest-miss of a defect is %.2f %%."
          % min(least))
