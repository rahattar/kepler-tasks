"""The reference solution run the way the task runs it, and scored the way the verifier scores it.

The audit test order is placed through the real `vacwork` program on a scratch state, the reference is run as
`solution/solve.sh` runs it, and the sheet it writes is read from disk by the task's own grader.

    python3 -I reference_run.py  > reference_run.txt
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C                                                      # noqa: E402


def planned_order():
    """The order solve.sh places, as `diagnose.py --plan` derives it from the agent's records, with the spread of
    each chamber's gas load at 36 h over the budgets its records cannot reject."""
    import json
    import subprocess
    p = subprocess.run([sys.executable, "-I", os.path.join(C.TASK, "solution", "diagnose.py"), "--plan", C.DATA],
                       capture_output=True, text=True, check=True)
    return json.loads(p.stdout)["tests"], [l[2:] for l in p.stderr.splitlines() if l.startswith("# ")]


def main():
    C.header(__file__)
    plan, rows_plan = planned_order()
    print("How far each chamber's records determine its gas load at 36 h (diagnose.py --plan), widest first:")
    for line in rows_plan:
        print("  " + line)
    spreads = [float(l.rsplit("(", 1)[1].split("%")[0]) for l in rows_plan]
    print("planned order: %s; its spread %.1f%%, the next chamber's %.1f%% (%.1fx)"
          % (", ".join("%s %s at %g h" % (t["chamber"], t["test"], t["pumping_time_h"]) for t in plan),
             spreads[0], spreads[1], spreads[0] / spreads[1]))
    same = [dict(t, pumping_time_h=float(t["pumping_time_h"])) for t in plan] == C.REFERENCE_PLAN
    print("the planned order is the reference order: %s" % ("yes" if same else "NO"))
    vc01 = [float(l.rsplit("(", 1)[1].split("%")[0]) for l in rows_plan if l.startswith("VC01")]
    print("VC01 read with both gauges: %.1f%% wide" % vc01[0])
    # the same step, profiled on the reference instrument alone wherever both gauges read a pumpdown
    import contextlib
    import io
    import routes as R
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        naive = R.own_plan("reference_gauge_only", C.DATA)
    lines = [l[2:] for l in buf.getvalue().splitlines() if l.startswith("# ")]
    print("")
    print("The same, profiled on the reference instrument alone (routes.reference_gauge_only), widest first:")
    for line in lines[:3]:
        print("  " + line)
    v01 = [float(l.rsplit("(", 1)[1].split("%")[0]) for l in lines if l.startswith("VC01")]
    print("VC01 on the reference instrument alone: %.1f%% wide; that profile orders %s"
          % (v01[0], ", ".join("%s %s" % (t["chamber"], t["test"]) for t in naive)))
    print("")
    answers = C.reference_answers()
    r = C.score(answers)
    tr = C.truth()
    rows = []
    for cid in C.IDS:
        v = r["chambers"][cid]
        rows.append([cid, v["cause"], v["cause_true"], "%.4e" % v["q_total"], "%.4e" % v["q_true"],
                     "%+.2f%%" % (100 * v["q_dev"]), "%.1f" % v["s_eff"], "%.1f" % v["s_true"],
                     "%+.2f%%" % (100 * v["s_dev"]), "ok" if v["ok"] else "BAD"])
    print(C.report("The reference solution against the sealed fleet", rows,
                   ["chamber", "cause", "true cause", "gas load", "true gas load", "deviation",
                    "speed", "true speed", "deviation", ""]))
    print("order placed: " + ", ".join("%s %s%s" % (t["chamber"], t["test"], " at %g h" % t["pumping_time_h"]
                                                     if "pumping_time_h" in t else "") for t in C.REFERENCE_PLAN))
    print("tolerances: gas load %.1f%%, speed %.1f%%; gate %d of %d chambers"
          % (100 * C.G.Q_TOL, 100 * C.G.S_TOL, C.G.GATE, len(C.IDS)))
    print("worst deviation: gas load %.2f%%, speed %.2f%%"
          % (100 * max(abs(r["chambers"][c]["q_dev"]) for c in C.IDS),
             100 * max(abs(r["chambers"][c]["s_dev"]) for c in C.IDS)))
    print("")
    print("%d of %d chambers right: %s" % (r["npass"], len(C.IDS),
                                           "accepted" if r["accepted"] else "REJECTED"))
    C.cleanup()
    return 0 if r["accepted"] and same else 1


if __name__ == "__main__":
    sys.exit(main())
