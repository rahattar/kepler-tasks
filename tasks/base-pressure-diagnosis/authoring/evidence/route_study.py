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
their defect and not in what they measured. A route is counted against a chamber only where the reference itself
is right there: the study stops if the reference is not accepted.

The laboratory's scatter on the ordered test is drawn from a fixed seed in vacwork. The routes are also run on the
playbook's laboratory seeds (C.LAB_SEEDS), each a copy of vacwork with only that seed changed, so a route's
rejection does not rest on one draw of the scatter. Only the ordered chamber reads the order, so on each seed only
that chamber is re-audited; the others are the same on every seed. On every seed where the reference is right on
the ordered chamber, it must be missed by at least MIN_ROUTES routes, and a route that is rejected by the ordered
chamber alone must miss it on every such seed. A route that also misses other chambers is rejected whatever the
seed; how often it misses the ordered chamber is reported, not required.

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


def seed_study(base, base_routes, alone, fails):
    """The ordered chamber on each laboratory seed: is the reference right there, and do the routes that miss it
    on the shipped seed still miss it?"""
    ordered = sorted({t["chamber"] for t in C.REFERENCE_PLAN})
    rows = []
    for cid in ordered:
        hits = {name: 0 for name in base_routes}
        ref_ok = 0
        fewest = None
        for seed in C.LAB_SEEDS:
            vac = C.place_order(C.REFERENCE_PLAN, tag="seed", lab_seed=seed)
            ref = R.run(C.DATA, vac, only=[cid])
            if not C.chamber_ok(base, cid, ref[cid]):
                continue
            ref_ok += 1
            n = 0
            for name in base_routes:
                got = R.run(C.DATA, vac, name, only=[cid])
                if got[cid] is R.NO_ANSWER or not C.chamber_ok(base, cid, got[cid]):
                    hits[name] += 1
                    n += 1
            if n < MIN_ROUTES:
                fails.append("on laboratory seed %d only %d route(s) miss %s, want %d" % (seed, n, cid, MIN_ROUTES))
            fewest = n if fewest is None else min(fewest, n)
        if ref_ok < len(C.LAB_SEEDS):
            fails.append("the reference is right on %s on only %d of %d laboratory seeds"
                         % (cid, ref_ok, len(C.LAB_SEEDS)))
        for name in base_routes:
            if name in alone and hits[name] < ref_ok:
                fails.append("route %s is rejected by %s alone on the shipped seed, but misses it on only %d of the"
                             " %d laboratory seeds where the reference is right" % (name, cid, hits[name], ref_ok))
            rows.append([cid, name, "%d/%d" % (hits[name], ref_ok),
                         "yes" if name in alone else "no, misses others too"])
        rows.append([cid, "(reference right)", "%d/%d" % (ref_ok, len(C.LAB_SEEDS)), ""])
        rows.append([cid, "(fewest routes missing it on one seed)", str(fewest), ""])
    return rows


def main():
    C.header(__file__)
    C.require_baseline(C.reference_answers())
    vac = C.place_order(C.REFERENCE_PLAN)
    base = R.run(C.DATA, vac)
    if not C.score(base)["accepted"]:
        print("BASELINE NOT ACCEPTED: the routes' unpatched reference is not accepted")
        C.cleanup()
        return 1
    tr = C.truth()
    ordered = {t["chamber"] for t in C.REFERENCE_PLAN}
    misses_ordered = []
    alone = set()
    missed = {cid: 0 for cid in C.IDS}
    by_cause = {cid: 0 for cid in C.IDS}
    nearest_misses = []
    rows = []
    detail = []
    fails = []

    for name in R.ROUTES:
        answers = R.run(C.DATA, vac, name)
        blank = [cid for cid in C.IDS if answers[cid] is R.NO_ANSWER]
        if blank:
            # whoever follows the route has no row to write for these chambers; the grader rejects such a sheet
            # outright, which is checked here, and the other chambers are graded with the blanks filled from the
            # baseline so that what the route gets wrong elsewhere is still seen
            whole = C.score(answers)
            if "error" not in whole:
                fails.append("route %s left %s blank and the grader still read the sheet" % (name, blank))
            answers = dict(answers, **{cid: base[cid] for cid in blank})
        r = C.score(answers)
        if "error" in r:
            fails.append("route %s produced a sheet the grader rejected: %s" % (name, r["error"]))
            continue
        for cid in blank:
            r["chambers"][cid] = dict(r["chambers"][cid], ok=False, ok_cause=False, ok_q=False, ok_s=False,
                                      cause="(none)", q_dev=float("nan"), s_dev=float("nan"))
        if blank:
            r["accepted"] = False
        wrong = [cid for cid in C.IDS if not r["chambers"][cid]["ok"]]
        if wrong and set(wrong) & ordered:
            misses_ordered.append(name)
            if set(wrong) <= ordered:
                alone.add(name)
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
            if not v["ok_q"] and v["q_dev"] == v["q_dev"]:
                nearest_misses.append(v["q_dev"])
            detail.append([name, cid, what_wrong(v), v["cause"],
                           "%+.1f%%" % (100 * v["q_dev"]), "%+.1f%%" % (100 * v["s_dev"])])

    for cid, n in missed.items():
        if n < MIN_ROUTES:
            fails.append("chamber %s is got wrong by only %d route(s), want %d" % (cid, n, MIN_ROUTES))
    for cid, n in by_cause.items():
        if n < 1:
            fails.append("chamber %s is not got wrong by any route on the cause alone" % cid)

    seed_rows = seed_study(base, misses_ordered, alone, fails)

    print(C.report("Defective routes, each scored through the task's grader",
                   rows, ["route", "wrong", "verdict", "chambers wrong"]))
    print(C.report("What each route got wrong, chamber by chamber",
                   detail, ["route", "chamber", "wrong", "cause given", "q deviation", "s deviation"]))
    print(C.report("How many routes each chamber defeats",
                   [[cid, missed[cid], by_cause[cid], tr[cid]["cause"]] for cid in C.IDS],
                   ["chamber", "routes that miss it", "of those, on the cause", "cause"]))

    print(C.report("The ordered chamber on the laboratory seeds %d-%d: seeds where the route still misses it, of"
                   " those where the reference is right" % (C.LAB_SEEDS[0], C.LAB_SEEDS[-1]),
                   seed_rows, ["chamber", "route", "misses", "rejected by this chamber alone"]))

    print("gate: at least %d of %d chambers right; a route is rejected when more than %d are wrong"
          % (C.G.GATE, len(C.IDS), len(C.IDS) - C.G.GATE))
    print("tolerances: gas load %.1f%%, speed %.1f%%" % (100 * C.G.Q_TOL, 100 * C.G.S_TOL))
    nearest = min([abs(v) for v in nearest_misses] or [0.0])
    print("nearest defective miss on a quantity: %.2f%% (%.2fx the gas-load tolerance)"
          % (100 * nearest, nearest / C.G.Q_TOL if C.G.Q_TOL else 0))
    single = [name for name, n, _v, _w in [(r[0], r[1], r[2], r[3]) for r in rows] if n == 1]
    print("routes rejected by one chamber alone: %d (%s), each required to miss it by at least %.2fx the"
          " tolerance or on the cause" % (len(single), " ".join(single) or "-", BIG_MISS))
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
