import sys, json, collections, numpy as np, truth as T, gen as G
name = sys.argv[1]
spec = G.SITES[name]
folder = ("core/environment/data/%s/%s" % ("examples" if spec["role"] == "example" else "pending", name)) if spec["role"] != "hidden" else "hidden/" + name
pk = T.load(folder)
act = json.load(open("hidden/_actual_%s.json" % name))
truth = T.simulate(pk, None, act)
for label, a in (("records alone", {}), ("fouled only fixed", {"return_C": act["return_C"]}), ("throttle only fixed", {"resistance": act["resistance"]})):
    got = T.simulate(pk, None, a)
    out = collections.Counter(); worst = collections.defaultdict(float)
    for r in pk["points"]:
        e = abs(got[r["point"]] - truth[r["point"]]) / G.band(r["point"], truth[r["point"]])
        if e > 1: out[(r["item"], r["quantity"])] += 1
        worst[r["quantity"]] = max(worst[r["quantity"]], e)
    print(label, sum(out.values()), "out;", dict(worst), "; by item:", sorted(out.items(), key=lambda x: -x[1])[:8])
