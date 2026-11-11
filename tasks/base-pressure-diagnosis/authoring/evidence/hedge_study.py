"""What a wrong attribution does to the quantities.

A sheet that names the wrong cause fails that chamber by definition: the cause is graded on its own. What this
study measures is the other thing a solver might hope for, that a wrong reading of a chamber still lands its gas
load inside the band, so that only the one field is lost. For every chamber and every cause but its own, the
reference audit is run with its reading forced to that cause, and the resulting sheet, naming that cause, is
scored through the task's grader:

- wall-outgassing: the gas budget with no trapped volume and the real leak held at zero (a helium result of zero,
  entered as the reference enters any helium test), so the wall takes every part of the gas load that decays;
- air-leak: no trapped volume, the register's seal;
- virtual-leak: a trapped volume present, from the start or from a date of logged work, and the real leak held at
  zero, so the constant part not explained by the seal goes to the trapped volume;
- permeation: the register's seal set aside for another material of the table, no trapped volume;
- pump-speed: the reference's own quantities, with only the cause changed.

Everything else is the reference's own code, patched in place and restored, so the deviations are the forced
reading's and not a copy's drift. The study reports how many forced readings keep the gas load in its band, and
fails if any of the sheets is accepted.

    python3 -I hedge_study.py  > hedge_study.txt
"""
import contextlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C                                                      # noqa: E402
import routes as R                                                      # noqa: E402

D = R.D
CAUSES = ("wall-outgassing", "air-leak", "virtual-leak", "permeation", "pump-speed")


def _keep(cause):
    """Which of the reference's candidate structures a forced reading admits, and whether the leak is held at 0."""
    if cause == "wall-outgassing":
        return (lambda st: st["trapped_from"] is None and st["seal"] is None), True
    if cause == "air-leak":
        return (lambda st: st["trapped_from"] is None and st["seal"] is None), False
    if cause == "virtual-leak":
        return (lambda st: st["trapped_from"] is not None and st["seal"] is None), True
    if cause == "permeation":
        return (lambda st: st["trapped_from"] is None and st["seal"] is not None), False
    raise ValueError(cause)


@contextlib.contextmanager
def forced(cause):
    keep, no_leak = _keep(cause)
    old_cs, old_he = D.candidate_structures, D.helium_says

    def cs(cid, cfg, data, obs):
        return [st for st in old_cs(cid, cfg, data, obs) if keep(st)]

    D.candidate_structures = cs
    if no_leak:
        D.helium_says = lambda cid, vac: dict(leak=0.0)
    try:
        yield
    finally:
        D.candidate_structures, D.helium_says = old_cs, old_he


def main():
    C.header(__file__)
    ref = C.reference_answers()
    C.require_baseline(ref)
    vac = C.place_order(C.REFERENCE_PLAN)
    tr = C.truth()

    rows = []
    inside = []
    unfit = []
    accepted = []
    for cid in C.IDS:
        true_cause = tr[cid]["cause"]
        for cause in CAUSES:
            if cause == true_cause:
                continue
            if cause == "pump-speed":
                q_alt, s_alt = ref[cid][1], ref[cid][2]
                named = ref[cid][0]
            else:
                with forced(cause):
                    got = R.run(C.DATA, vac, only=[cid])[cid]
                if got is R.NO_ANSWER:
                    # the records leave fewer observations than a budget of that form has parameters, so the
                    # reading cannot be fitted at all: there is no gas load to hedge with
                    unfit.append((cid, cause))
                    rows.append([cid, true_cause, cause, "-", "-", "-", "too few observations to fit", "-"])
                    continue
                named, q_alt, s_alt = got
            sheet = dict(ref)
            sheet[cid] = (cause, q_alt, s_alt)
            r = C.score(sheet)
            v = r["chambers"][cid]
            if v["ok_q"]:
                inside.append((cid, cause))
            if r["accepted"]:
                accepted.append((cid, cause))
            rows.append([cid, true_cause, cause, named, "%.3e" % q_alt, "%+.2f%%" % (100 * v["q_dev"]),
                         "yes" if v["ok_q"] else "no", "accepted" if r["accepted"] else "rejected"])

    print(C.report("Every chamber read as every cause but its own, each a whole sheet through the grader", rows,
                   ["chamber", "true cause", "forced reading", "largest load under it", "gas load", "deviation",
                    "quantity in band", "verdict"]))
    print("cases: %d (each of %d chambers against each of the other %d causes)" % (len(rows), len(C.IDS), 4))
    print("forced readings the records leave too few observations to fit: %d of %d" % (len(unfit), len(rows)))
    for cid, cause in unfit:
        print("  %s read as %s" % (cid, cause))
    print("forced readings that keep the gas load in its band: %d of %d" % (len(inside), len(rows)))
    for cid, cause in inside:
        print("  %s read as %s" % (cid, cause))
    print("")
    if accepted:
        print("%d PROBLEM(S): these sheets naming a wrong cause were accepted" % len(accepted))
        for cid, cause in accepted:
            print("  %s named %s and still passed" % (cid, cause))
    else:
        print("none of the %d sheets naming a wrong cause is accepted" % len(rows))
    C.cleanup()
    return 1 if accepted else 0


if __name__ == "__main__":
    sys.exit(main())
