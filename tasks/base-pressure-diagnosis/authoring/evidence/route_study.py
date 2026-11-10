"""Defective routes: each is the reference audit with one check left out or done the obvious way.

Every route is scored through the task's own grader, exactly as the verifier scores a submission. For each route
this reports how many chambers it gets wrong and, for each chamber, what it got wrong there: the cause, the gas
load, the speed, or more than one.

Two things must hold, and the script fails if either does not:
- every route is rejected, that is it gets more chambers wrong than the gate allows;
- every route either misses at least two chambers, or misses one of them by at least BIG_MISS times the
  tolerance on the quantity it gets wrong, so no route is rejected by a chamber that merely grazes a band;
- every chamber is got wrong by at least MIN_ROUTES routes, so no chamber is carried by a single check;
- every chamber is got wrong by at least one route on the cause alone. A cause is right or wrong whatever the
  tolerances are, so a chamber that only ever fails on a quantity would rest on where the band is drawn.

Each route is run on the same test order the reference places, so the routes differ from the reference only in
their defect and not in what they measured.

    python3 -I route_study.py  > route_study.txt
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C                                                      # noqa: E402
import routes as R                                                      # noqa: E402

MIN_ROUTES = 3
BIG_MISS = 2.0                      # a route that misses only one chamber must miss it by this much


def what_wrong(v):
    bad = []
    if not v["ok_cause"]:
        bad.append("cause")
    if not v["ok_q"]:
        bad.append("q")
    if not v["ok_s"]:
        bad.append("s")
    return "+".join(bad) if bad else ""


def main():
    vac = C.place_order(C.REFERENCE_PLAN)
    tr = C.truth()
    missed = {cid: 0 for cid in C.IDS}
    by_cause = {cid: 0 for cid in C.IDS}
    nearest_misses = []
    rows = []
    detail = []
    fails = []

    for name in R.ROUTES:
        answers = R.run(C.DATA, vac, name)
        r = C.score(answers)
        if "error" in r:
            fails.append("route %s produced a sheet the grader rejected: %s" % (name, r["error"]))
            continue
        wrong = [cid for cid in C.IDS if not r["chambers"][cid]["ok"]]
        for cid in wrong:
            missed[cid] += 1
            if not r["chambers"][cid]["ok_cause"]:
                by_cause[cid] += 1
        if r["accepted"]:
            fails.append("route %s was accepted: only %d chambers wrong" % (name, len(wrong)))
        if len(wrong) == 1:
            v = r["chambers"][wrong[0]]
            margin = max(abs(v["q_dev"]) / C.G.Q_TOL if not v["ok_q"] else 0.0,
                         abs(v["s_dev"]) / C.G.S_TOL if not v["ok_s"] else 0.0,
                         BIG_MISS if not v["ok_cause"] else 0.0)
            if margin < BIG_MISS:
                fails.append("route %s misses only %s, and only by %.2fx the tolerance"
                             % (name, wrong[0], margin))
        rows.append([name, len(wrong), "accepted" if r["accepted"] else "rejected",
                     " ".join(wrong) or "-"])
        for cid in wrong:
            v = r["chambers"][cid]
            if not v["ok_q"]:
                nearest_misses.append(v["q_dev"])
            detail.append([name, cid, what_wrong(v), v["cause"],
                           "%+.1f%%" % (100 * v["q_dev"]), "%+.1f%%" % (100 * v["s_dev"])])

    for cid, n in missed.items():
        if n < MIN_ROUTES:
            fails.append("chamber %s is got wrong by only %d route(s), want %d" % (cid, n, MIN_ROUTES))
    for cid, n in by_cause.items():
        if n < 1:
            fails.append("chamber %s is not got wrong by any route on the cause alone" % cid)

    print(C.report("Defective routes, each scored through the task's grader",
                   rows, ["route", "wrong", "verdict", "chambers wrong"]))
    print(C.report("What each route got wrong, chamber by chamber",
                   detail, ["route", "chamber", "wrong", "cause given", "q deviation", "s deviation"]))
    print(C.report("How many routes each chamber defeats",
                   [[cid, missed[cid], by_cause[cid], tr[cid]["cause"]] for cid in C.IDS],
                   ["chamber", "routes that miss it", "of those, on the cause", "cause"]))

    print("gate: at least %d of %d chambers right; a route is rejected when more than %d are wrong"
          % (C.G.GATE, len(C.IDS), len(C.IDS) - C.G.GATE))
    print("tolerances: gas load %.1f%%, speed %.1f%%" % (100 * C.G.Q_TOL, 100 * C.G.S_TOL))
    nearest = min([abs(v) for v in nearest_misses] or [0.0])
    print("nearest defective miss on a quantity: %.2f%% (%.2fx the gas-load tolerance)"
          % (100 * nearest, nearest / C.G.Q_TOL if C.G.Q_TOL else 0))
    print("")
    if fails:
        print("%d PROBLEM(S)" % len(fails))
        for f in fails:
            print("  " + f)
    else:
        print("all %d routes rejected; every chamber defeats at least %d routes" % (len(rows), MIN_ROUTES))
    C.cleanup()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
