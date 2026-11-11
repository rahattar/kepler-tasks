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


def main():
    C.header(__file__)
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
    return 0 if r["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
