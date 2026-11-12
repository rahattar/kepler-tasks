"""Sound methods: audits a competent vacuum engineer might do, all of which must pass.

The tolerances are set from this spread, not from the reference alone. Each method is a complete audit sheet
scored through the task's own grader, exactly as the verifier scores a submission.

The methods are:
- the reference, on the order solution/solve.sh places;
- the reference on other sound orders: a gas-load test on VC06, the one chamber whose records leave its gas load
  at the reference condition open (solution/diagnose.py --plan measures how far), at other pumping times inside
  the range where the answers differ
  (plan_sweep.txt measures every order, sound or not);
- a structurally independent second audit (independent.py), which shares no code with the reference and selects
  its budgets by a different criterion, on each of those orders;
- the reference with each sound variation in routes.VARIATIONS, on the reference order.

Every one of them must be accepted. The laboratory's scatter on the ordered test is drawn from a fixed seed in
vacwork, so the reference and the independent audit are also run on each of the playbook's laboratory seeds
(C.LAB_SEEDS) on the reference order; only the ordered chamber reads the order, so only it is re-audited there.
Each must be right on it on every seed.

The script reports the widest deviation any sound method reaches on any chamber, which is what the tolerances
must clear.

    python3 -I method_spread.py  > method_spread.txt
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C                                                      # noqa: E402
import independent as I                                                 # noqa: E402
import routes as R                                                      # noqa: E402

T = lambda c, k, h: dict(chamber=c, test=k, pumping_time_h=h)           # noqa: E731

ORDERS = {
    "VC06 rga at 36 h (solve.sh)": C.REFERENCE_PLAN,
    "VC06 rga at 30 h": [T("VC06", "rga", 30.0)],
    "VC06 rga at 48 h": [T("VC06", "rga", 48.0)],
    "VC06 rate-of-rise at 30 h": [T("VC06", "rate-of-rise", 30.0)],
    "VC06 rate-of-rise at 36 h": [T("VC06", "rate-of-rise", 36.0)],
    "VC06 speed-test at 42 h": [T("VC06", "speed-test", 42.0)],
}


def main():
    C.header(__file__)
    C.require_baseline(C.reference_answers())
    rows = []
    worst = []
    fails = []

    methods = []
    for name, plan in ORDERS.items():
        tag = "o%d" % len(methods)
        methods.append(("reference, " + name, lambda plan=plan, tag=tag: C.reference_answers(plan, tag)))
        methods.append(("independent, " + name, lambda plan=plan: I.audit_all(C.DATA, C.place_order(plan))))
    for v in R.VARIATIONS:
        methods.append(("reference + " + v.replace("_", " "),
                        lambda v=v: R.run(C.DATA, C.place_order(C.REFERENCE_PLAN), o=R.opts(**{v: True}))))

    base = None
    for name, make in methods:
        answers = make()
        if base is None:
            base = answers
        r = C.score(answers)
        if "error" in r:
            fails.append("method %r produced a sheet the grader rejected: %s" % (name, r["error"]))
            continue
        wrong = [cid for cid in C.IDS if not r["chambers"][cid]["ok"]]
        if not r["accepted"]:
            fails.append("sound method %r was rejected: %s wrong" % (name, " ".join(wrong)))
        wq = max(abs(r["chambers"][cid]["q_dev"]) for cid in C.IDS)
        ws = max(abs(r["chambers"][cid]["s_dev"]) for cid in C.IDS)
        at_q = max(C.IDS, key=lambda cid: abs(r["chambers"][cid]["q_dev"]))
        bad_cause = [cid for cid in C.IDS if not r["chambers"][cid]["ok_cause"]]
        worst.append((name, wq, ws))
        rows.append([name, "%d/%d" % (r["npass"], len(C.IDS)), "accepted" if r["accepted"] else "REJECTED",
                     "%.2f%% (%s)" % (100 * wq, at_q), "%.2f%%" % (100 * ws), " ".join(bad_cause) or "-"])

    # the laboratory seeds, on the ordered chamber
    tr = C.truth()
    seed_rows = []
    for cid in sorted({t["chamber"] for t in C.REFERENCE_PLAN}):
        for who in ("reference", "independent"):
            ok, dq = 0, []
            for seed in C.LAB_SEEDS:
                vac = C.place_order(C.REFERENCE_PLAN, tag="seed", lab_seed=seed)
                if who == "reference":
                    a = R.run(C.DATA, vac, only=[cid])[cid]
                else:
                    a = I.audit_all(C.DATA, vac)[cid]
                if C.chamber_ok(base, cid, a):
                    ok += 1
                dq.append(a[1] / tr[cid]["q_total"] - 1.0)
            worst.append(("%s on %s, seeds %d-%d" % (who, cid, C.LAB_SEEDS[0], C.LAB_SEEDS[-1]),
                          max(abs(x) for x in dq), 0.0))
            if ok < len(C.LAB_SEEDS):
                fails.append("the %s is right on %s on only %d of %d laboratory seeds"
                             % (who, cid, ok, len(C.LAB_SEEDS)))
            seed_rows.append([cid, who, "%d/%d" % (ok, len(C.LAB_SEEDS)), "%+.2f%%" % (100 * min(dq)),
                              "%+.2f%%" % (100 * max(dq))])

    print(C.report("Sound methods, each scored through the task's grader", rows,
                   ["method", "right", "verdict", "worst q deviation", "worst s deviation", "causes missed"]))
    print(C.report("The ordered chamber on the laboratory seeds, reference order", seed_rows,
                   ["chamber", "audit", "right", "lowest q deviation", "highest q deviation"]))

    wq = max(w[1] for w in worst)
    ws = max(w[2] for w in worst)
    print("widest deviation over every sound method and chamber: gas load %.2f%%, speed %.2f%%"
          % (100 * wq, 100 * ws))
    print("tolerances: gas load %.1f%%, speed %.1f%% (margin %.2fx and %.2fx)"
          % (100 * C.G.Q_TOL, 100 * C.G.S_TOL, C.G.Q_TOL / wq if wq else 0, C.G.S_TOL / ws if ws else 0))
    print("")
    if fails:
        print("%d PROBLEM(S)" % len(fails))
        for f in fails:
            print("  " + f)
    else:
        print("all %d sound methods accepted, and both audits right on every laboratory seed" % len(rows))
    C.cleanup()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
