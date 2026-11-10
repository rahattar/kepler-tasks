"""All 120 ways to spend the three clean-and-test slots (three distinct units), each with the fallbacks for what it
leaves open: a ribbed unit with no standby given the bay's median RTD offset or none; ribbed units left untested
taken through their friction gain or given the measured gain as it is; a C-310 of the new pair left untested taken
through the factor measured on its tested twin or left on the shared vendor datasheet; E9 left untested taken from
its open 2025 sheet with the glycol- or water-side duty as recorded, their mean, or any one temperature rebuilt
from the other side's duty, or with the sheet set aside for the design split or the sister units' median factor; E5
left untested from its 2025 test with the shell film scaled for the wider baffle spacing or as it stands. An
allocation passes if any combination does.

    python3 campaign_study.py > campaign_study.txt
"""
import itertools, methods as M, hx
ok, best_fail, n = [], 9, 0
for plan in itertools.combinations(hx.UNITS, 3):
    n += 1
    e = min(M.grade(M.estimate(list(plan), **kw)[0])[0] for kw in
            [dict(liner=l, e8_bias=b, e9=n, e5=f, newfill=w) for l in ("proxy", "same") for b in ("bay_median", "zero")
             for n in ("glycol", "water", "mean", "fix_tho", "fix_tco", "fix_thi", "fix_tci", "design", "fleet")
             for f in ("baffle", "2025") for w in ("twin", "vendor")])
    if e <= M.TOL: ok.append((plan, round(e, 3)))
    else: best_fail = min(best_fail, e)
print("allocations of three slots over ten units: %d; passing: %s; best failing allocation: %.3f m2K/kW" % (n, ok, best_fail))
