"""check.py: the evidence in every package: campaign misclosures at sound nodes and at the conditions."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ref_design as R  # noqa: E402

man = json.load(open(os.path.join(HERE, "core", "manifest.json")))
for name, m in sorted(man.items(), key=lambda kv: (kv[1]["where"], kv[0])):
    pkg = os.path.join(HERE, "core", "data", m["where"], name) if m["where"] != "hidden" else \
        os.path.join(HERE, "core", "hidden", name)
    pk = R.Package(pkg)
    bal = pk.balances()
    vnode = {v["node"]: v["valve"] for v in pk.valves}
    cnode = {c["node"]: c["meter"] for c in pk.custs}
    cond = {}
    worst_sound, nsound, big_sound = 0.0, 0, 0.0
    for node, seq in bal.items():
        tag = vnode.get(node) or cnode.get(node)
        if tag is not None and tag in (m["passing_valve"], m["low_meter"]):
            cond[tag] = ["%s %+.0f (bound %.0f)" % (d[5:], miss, b) for d, miss, b in sorted(seq)]
        else:
            for d, miss, b in seq:
                nsound += 1
                worst_sound = max(worst_sound, abs(miss) / b)
                big_sound = max(big_sound, abs(miss))
    print("%-8s %-8s worked-on %2d allowance %2d  sound balances %4d, worst |miss|/bound %.2f, largest miss %.0f m3/h"
          % (name, m["where"], len(pk.changed()), pk.info["survey_allowance"], nsound, worst_sound, big_sound))
    for tag, s in cond.items():
        print("          %-8s %s" % (tag, "; ".join(s)))
    print("          suspects found by the reference: %s" % R.suspects(pk))
