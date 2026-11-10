"""Every outage programme of one to three tests (coast-down or strain survey, on any screen, none repeated: 1350
programmes), each assembled with the siblings' median, smallest or largest damage per event as the proxy for what
the records and tests leave open. Only programmes that leave no screen outside 20 % pass.

    python3 plan_sweep.py > plan_sweep.txt
"""
import itertools
import plans as P
import screens as S

o = P.opts()
comp = P.components(o)
opts_ = [(u, k) for u in S.UNITS for k in ("coast-down", "strain-survey")]
rows = []
for n in (1, 2, 3):
    for plan in itertools.combinations(opts_, n):
        for proxy in ("median", "min", "max"):
            w, u, f, _ = P.grade(P.assemble(comp, plan, o, proxy))
            rows.append((len(f), w, proxy, plan, f))
ok = [r for r in rows if r[0] == 0]
print("programmes x proxies scored: %d; passing: %d" % (len(rows), len(ok)))
for r in sorted(ok, key=lambda r: r[1]):
    print("  pass  worst %.3f  proxy %-6s  %s" % (r[1], r[2], " + ".join("%s %s" % p for p in r[3])))
bad = [r for r in rows if r[0] > 0]
m = min(bad, key=lambda r: r[1])
print("smallest worst-screen miss among failing programmes: %.3f (%s, proxy %s, outside: %s)" % (m[1], " + ".join("%s %s" % p for p in m[3]), m[2], " ".join(m[4])))
print("best failing programmes (fewest screens outside, then smallest worst miss):")
for r in sorted([r for r in rows if r[0] > 0], key=lambda r: (r[0], r[1]))[:10]:
    print("  fail  worst %.3f  proxy %-6s  %s  outside: %s" % (r[1], r[2], " + ".join("%s %s" % p for p in r[3]), " ".join(r[4])))
for label, plan in (("decoy S3 instead of S6", [("S5", "strain-survey"), ("S3", "coast-down"), ("S8", "coast-down")]),
                    ("decoy S4 instead of S6", [("S5", "strain-survey"), ("S4", "coast-down"), ("S8", "coast-down")]),
                    ("both large drives, no S6", [("S5", "strain-survey"), ("S8", "coast-down"), ("S10", "coast-down")]),
                    ("S5 coast-down instead of S6", [("S5", "strain-survey"), ("S5", "coast-down"), ("S8", "coast-down")]),
                    ("no large-drive test", [("S5", "strain-survey"), ("S6", "coast-down"), ("S4", "coast-down")]),
                    ("no survey", [("S6", "coast-down"), ("S8", "coast-down"), ("S5", "coast-down")])):
    w, u, f, _ = P.grade(P.assemble(comp, plan, o))
    print("  %-30s worst %.2f (%s) outside: %s" % (label, w, u, " ".join(f)))
