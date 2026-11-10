"""Method-free answers: sheets a program could write without doing the audit at all. Every one must be rejected.

Each is a complete audit sheet scored through the task's own grader. The answers are:

- the example chamber's audited result copied onto every chamber;
- one cause for all ten, for each of the five causes, with the example's quantities;
- the chamber's latest base-pressure reading taken as if it were the whole answer, with the gas load as the
  reading times the latest speed test and the cause the commonest one in the fleet;
- the register's specified base pressure times the latest speed test, with the commonest cause;
- the rated speed from the register and the pump curve, with the gas load that rated speed and the specified base
  pressure imply;
- the per-chamber median of the sound methods' answers, which is not method-free but shows what a sheet assembled
  from the fleet's own spread is worth.

For each the script reports how many chambers it gets right and which, so a free pass is visible.

    python3 -I null_baselines.py  > null_baselines.txt
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C                                                      # noqa: E402

sys.path.insert(0, os.path.join(C.TASK, "solution"))
import diagnose as D                                                    # noqa: E402

CAUSES = ("air-leak", "virtual-leak", "wall-outgassing", "permeation", "pump-speed")


def example_result():
    """The audit result the worked example carries, which an agent can read straight out of the documents."""
    ex = C.F.truth(C.F.EX)
    return ex["cause"], ex["q_total"], ex["s_eff"]


def commonest_cause(data):
    return "wall-outgassing"


def latest_reading(cid, data):
    rows = sorted([r for r in data["log"] if r["chamber"] == cid], key=lambda r: r["date"])
    return float(rows[-1]["reading_mbar"])


def latest_speed(cid, data):
    rows = sorted([r for r in data["speed"] if r["chamber"] == cid], key=lambda r: r["date"])
    return float(rows[-1]["s_eff_l_s"])


def rated_speed(cid, data):
    reg = [r for r in data["register"] if r["chamber"] == cid][0]
    port = float(reg["c_port_l_s"])
    pump = D.curve(D.TURBO[reg["turbo"]], 1e-6)
    return pump * port / (pump + port)


def spec_pressure(cid, data):
    return float([r for r in data["register"] if r["chamber"] == cid][0]["p_spec_mbar"])


def main():
    data = D.load_data(C.DATA)
    ex_cause, ex_q, ex_s = example_result()
    answers = {}

    answers["the example's result for every chamber"] = {cid: (ex_cause, ex_q, ex_s) for cid in C.IDS}
    for cause in CAUSES:
        answers["%s for every chamber" % cause] = {cid: (cause, ex_q, ex_s) for cid in C.IDS}
    answers["the latest reading times the latest speed test"] = {
        cid: (commonest_cause(data), latest_reading(cid, data) * latest_speed(cid, data), latest_speed(cid, data))
        for cid in C.IDS}
    answers["the specified base pressure times the latest speed test"] = {
        cid: (commonest_cause(data), spec_pressure(cid, data) * latest_speed(cid, data), latest_speed(cid, data))
        for cid in C.IDS}
    answers["the register's rated speed and the specified base pressure"] = {
        cid: (commonest_cause(data), spec_pressure(cid, data) * rated_speed(cid, data), rated_speed(cid, data))
        for cid in C.IDS}

    rows = []
    fails = []
    free = {cid: [] for cid in C.IDS}
    for name, ans in answers.items():
        r = C.score(ans)
        if "error" in r:
            rows.append([name, "rejected by the grader", "-", r["error"][:40]])
            continue
        right = [cid for cid in C.IDS if r["chambers"][cid]["ok"]]
        for cid in right:
            free[cid].append(name)
        if r["accepted"]:
            fails.append("the method-free answer %r was accepted" % name)
        rows.append([name, "%d/%d" % (r["npass"], len(C.IDS)),
                     "accepted" if r["accepted"] else "rejected", " ".join(right) or "-"])

    print(C.report("Method-free answers, each scored through the task's grader", rows,
                   ["answer", "right", "verdict", "chambers it happens to get right"]))
    print(C.report("Free passes, chamber by chamber",
                   [[cid, len(free[cid]), "; ".join(free[cid]) or "none"] for cid in C.IDS],
                   ["chamber", "answers it is free to", "which"]))
    print("gate: at least %d of %d chambers right" % (C.G.GATE, len(C.IDS)))
    print("")
    if fails:
        print("%d PROBLEM(S)" % len(fails))
        for f in fails:
            print("  " + f)
    else:
        print("every method-free answer rejected; the most any gets right is %d of %d"
              % (max(int(r[1].split("/")[0]) for r in rows if "/" in r[1]), len(C.IDS)))
    C.cleanup()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
