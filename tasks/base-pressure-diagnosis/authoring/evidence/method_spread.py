"""Sound methods: variations a competent vacuum engineer might choose, all of which must pass.

The tolerances are set from this spread, not from the reference alone. Each method is a complete audit sheet
scored through the task's own grader, exactly as the verifier scores a submission.

The methods are:
- the reference, on the test order it places;
- the reference on the one order the fleet admits: an analysis on the single chamber whose own records cannot
  separate a trapped volume from wall gas. Every other order is a misallocation rather than another sound method,
  and `plan_sweep.txt` measures what each of them costs;
- a structurally independent second audit (`independent.py`), which shares no code with the reference;
- the reference with the oldest surviving entry left out, on each chamber that has four or more;
- the reference taking the constant part of each gas load as the median of the entries' residuals;
- the reference taking the next-to-latest surviving speed test rather than the latest.

Every one of them must be accepted, and the script reports the widest deviation any of them reaches on any
chamber, which is what the tolerances must clear.

    python3 -I method_spread.py  > method_spread.txt
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C                                                      # noqa: E402
import independent as I                                                 # noqa: E402
import routes as R                                                      # noqa: E402

PLANS = {
    "the reference order": C.REFERENCE_PLAN,
}


def main():
    tr = C.truth()
    rows = []
    worst = []
    fails = []

    methods = []
    for name, plan in PLANS.items():
        tag = name.replace(" ", "-")
        methods.append((name, lambda plan=plan, tag=tag: C.reference_answers(plan, tag)))
    methods.append(("independent audit",
                    lambda: I.audit_all(C.DATA, C.place_order(C.REFERENCE_PLAN))))
    for v in R.VARIATIONS:
        methods.append((v.replace("_", " "),
                        lambda v=v: R.run(C.DATA, C.place_order(C.REFERENCE_PLAN), o=R.opts(**{v: True}))))

    for name, make in methods:
        answers = make()
        r = C.score(answers)
        if "error" in r:
            fails.append("method %r produced a sheet the grader rejected: %s" % (name, r["error"]))
            continue
        wrong = [cid for cid in C.IDS if not r["chambers"][cid]["ok"]]
        if not r["accepted"]:
            fails.append("sound method %r was rejected: %s wrong" % (name, " ".join(wrong)))
        wq = max(abs(r["chambers"][cid]["q_dev"]) for cid in C.IDS)
        ws = max(abs(r["chambers"][cid]["s_dev"]) for cid in C.IDS)
        bad_cause = [cid for cid in C.IDS if not r["chambers"][cid]["ok_cause"]]
        worst.append((name, wq, ws))
        rows.append([name, "%d/%d" % (r["npass"], len(C.IDS)), "accepted" if r["accepted"] else "REJECTED",
                     "%+.2f%%" % (100 * wq), "%+.2f%%" % (100 * ws),
                     " ".join(bad_cause) or "-"])

    print(C.report("Sound methods, each scored through the task's grader", rows,
                   ["method", "right", "verdict", "worst q deviation", "worst s deviation",
                    "causes missed"]))

    wq = max(w[1] for w in worst)
    ws = max(w[2] for w in worst)
    print("widest deviation over every sound method and chamber: gas load %.2f%%, speed %.2f%%"
          % (100 * wq, 100 * ws))
    print("tolerances: gas load %.1f%%, speed %.1f%% (margin %.2fx and %.2fx)"
          % (100 * C.G.Q_TOL, 100 * C.G.S_TOL, C.G.Q_TOL / wq if wq else 0, C.G.S_TOL / ws if ws else 0))
    print("")
    for name, q, s in worst:
        print("  %-26s q %+6.2f%%  s %+6.2f%%" % (name, 100 * q, 100 * s))
    print("")
    if fails:
        print("%d PROBLEM(S)" % len(fails))
        for f in fails:
            print("  " + f)
    else:
        print("all %d sound methods accepted" % len(rows))
    C.cleanup()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
