"""What the audit test order is worth: both audits under every order the budget allows.

The budget is one test across ten chambers, placed once before any result is known, and a gas-load test is taken
after a pumping time the plan chooses. The space of orders is therefore: each gas-load test (rga, rate-of-rise,
speed-test) on each chamber at each pumping time in TIMES, a helium test on each chamber (it does not depend on
the pumping time), and placing no order. The sweep covers all of it, and counts how many orders carry each audit
to a pass. Do not restate that count elsewhere; read it off plan_sweep.txt, which is where README.md gets it.

Only the ordered chamber reads the order. So for each order the ordered chamber is re-audited and the other nine
are taken from the audit with no order at all. That shortcut is checked, not assumed: on a sample of orders the
whole audit is run as well, and the two sheets must be identical.

Every order goes through the real `vacwork` program and every sheet through the task's grader.

    python3 -I plan_sweep.py  > plan_sweep.txt
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C                                                      # noqa: E402
import independent as I                                                 # noqa: E402
import routes as R                                                      # noqa: E402

TIMES = [16.0, 20.0, 24.0, 30.0, 36.0, 42.0, 48.0]
GAS_TESTS = ["rga", "rate-of-rise", "speed-test"]
CHECK_WHOLE = [("VC08", "rga", 36.0), ("VC03", "rate-of-rise", 24.0), ("VC09", "speed-test", 16.0),
               ("VC05", "helium", None)]


def plans():
    out = [("no order", None, [])]
    for cid in C.IDS:
        for k in GAS_TESTS:
            for h in TIMES:
                out.append(("%s %s at %g h" % (cid, k, h), cid, [dict(chamber=cid, test=k, pumping_time_h=h)]))
        out.append(("%s helium" % cid, cid, [dict(chamber=cid, test="helium")]))
    return out


def main():
    C.header(__file__)
    assert C.F.BUDGET == 1, "this sweep enumerates single-test orders; the budget is %d" % C.F.BUDGET
    C.require_baseline(C.reference_answers())
    none_vac = os.path.join(C._work, "no-such-vacwork")
    base = {"reference": R.run(C.DATA, none_vac), "independent": I.audit_all(C.DATA, None)}
    data_i = I.shop(C.DATA)
    fails = []

    # the shortcut, checked
    for cid, k, h in CHECK_WHOLE:
        plan = [dict(chamber=cid, test=k, **({"pumping_time_h": h} if h else {}))]
        vac = C.place_order(plan, "check")
        whole = {"reference": R.run(C.DATA, vac), "independent": I.audit_all(C.DATA, vac)}
        for who in whole:
            part = dict(base[who])
            part[cid] = (R.run(C.DATA, vac, only=[cid])[cid] if who == "reference"
                         else I.audit_one(cid, data_i, vac))
            if C.sheet(part) != C.sheet(whole[who]):
                fails.append("the %s's whole sheet on %s differs from the ordered chamber's re-audit" % (who, plan))

    rows = []
    good = {"reference": [], "independent": []}
    for name, cid, plan in plans():
        verdicts = []
        for who in ("reference", "independent"):
            answers = dict(base[who])
            if plan:
                vac = C.place_order(plan, "sweep")
                answers[cid] = (R.run(C.DATA, vac, only=[cid])[cid] if who == "reference"
                                else I.audit_one(cid, data_i, vac))
            r = C.score(answers)
            wrong = [c for c in C.IDS if not r["chambers"][c]["ok"]]
            verdicts.append("accepted" if r["accepted"] else "rejected (%s)" % " ".join(wrong))
            if r["accepted"]:
                good[who].append(name)
        rows.append([name] + verdicts)

    print(C.report("Both audits under every order the budget allows", rows, ["order", "reference", "independent"]))
    print("budget: %d test across %d chambers, placed once; pumping times tried: %s h"
          % (C.F.BUDGET, len(C.IDS), " ".join("%g" % h for h in TIMES)))
    print("gate: at least %d of %d chambers right" % (C.G.GATE, len(C.IDS)))
    print("orders tried: %d" % len(rows))
    print("")
    # counted from the sweep rather than stated, so the number in the README cannot drift from the number here
    for who in ("reference", "independent"):
        print("ORDERS THAT WORK FOR THE %s: %d of %d" % (who.upper(), len(good[who]), len(rows)))
        for name in good[who]:
            print("  %s" % name)
    if set(good["reference"]) != set(good["independent"]):
        fails.append("the two audits are carried by different orders: %s"
                     % sorted(set(good["reference"]) ^ set(good["independent"])))
    if "VC08 rga at %g h" % C.F.DEFAULT_TEST_H in good["reference"]:
        fails.append("the default pumping time works; the order would not need choosing")
    print("")
    if fails:
        print("%d PROBLEM(S)" % len(fails))
        for f in fails:
            print("  " + f)
    else:
        print("the shortcut matches the whole audit on every sampled order; both audits are carried by the same"
              " orders")
    C.cleanup()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
