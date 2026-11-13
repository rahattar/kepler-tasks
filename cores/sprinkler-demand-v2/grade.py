"""Grades a demand program on the hidden packages: every package within the limit and within tolerance.

    python3 grade.py PROGRAM [SEED]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness                                               # noqa: E402

P_TOL = 0.03
Q_TOL = 0.03
CPU_LIMIT_S = 20.0      # the brief: 20 s on 1 CPU, judged by CPU time
WALL_GUARD_S = 120.0    # generous wall-clock safeguard for a shared machine


def main(argv):
    program = argv[1]
    seed = int(argv[2]) if len(argv) > 2 else 1
    hid = os.path.join(HERE, "core", "hidden")
    ok_all = True
    for tag in sorted(os.listdir(hid)):
        with open(os.path.join(hid, tag, "truth.json")) as f:
            truth = json.load(f)
        r = harness.run(program, os.path.join(hid, tag), truth, seed=seed,
                        limit=WALL_GUARD_S, cpu_limit=CPU_LIMIT_S)
        tr = truth["result"]
        line = "%-5s %-8s cpu %5.1f s wall %5.1f s" % (tag, r["status"], r["cpu_s"], r["wall_s"])
        ok = False
        if r["status"] == "done":
            res = r["result"]
            try:
                dp = res["pressure_psi"] / tr["pressure_psi"] - 1
                dq = res["flow_gpm"] / tr["flow_gpm"] - 1
                ok = abs(dp) <= P_TOL and abs(dq) <= Q_TOL
                line += "  P %+6.2f%%  Q %+6.2f%%" % (100 * dp, 100 * dq)
            except (KeyError, TypeError, ZeroDivisionError):
                line += "  result lacks pressure_psi or flow_gpm"
        test = r["tests"][0] if r["tests"] else None
        rep = r["reports"][0] if r["reports"] else None
        line += "  test %s%s" % (json.dumps(test), " REFUSED" if rep and "refused" in rep else "")
        print(("ok    " if ok else "FAIL  ") + line, flush=True)
        ok_all &= ok
    print("ACCEPTED" if ok_all else "REJECTED")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
