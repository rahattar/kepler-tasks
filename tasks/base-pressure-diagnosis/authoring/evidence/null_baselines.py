"""Method-free answers: sheets a program could write without doing the audit at all. Every one must be rejected.

Each is a complete audit sheet scored through the task's own grader. The answers are:

- the example chamber's audited result copied onto every chamber;
- one cause for all ten, for each of the five causes, with the example's quantities;
- the chamber's latest base-pressure reading taken as if it were the whole answer, with the gas load as the
  reading times the latest speed test and the cause the commonest one in the fleet;
- the register's specified base pressure times the latest speed test, with the commonest cause;
- the rated speed from the register and the pump curve, with the gas load that rated speed and the specified base
  pressure imply;
- three shortcuts that use the reference's own front end (the chamber as it stands, its corrected readings and its
  speed) but read the gas load off a single entry instead of fitting a budget, which is what the design rule of
  authoring/provenance/identify.py forbids from working: the latest entry's gas load taken as the reference
  condition's; the latest entry with the table's wall load and the rest put down to a leak; and the latest entry
  with the permeation computed and the rest put down to the wall, scaled to the reference condition.

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
    """The example chamber's own audited truth, copied onto all ten.

    The documents do not publish it - about_this_chamber.md says outright that no audited result is given - so
    this is not an answer an agent could read off. It is here as the strongest form of the constant answer: if
    even the true result of a real chamber of the same shop, applied to the whole fleet, gets nothing right,
    then no single answer does."""
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


def single_entry(how):
    """A shortcut through the reference's front end that reads the budget off the latest entry alone."""
    data = D.load_data(C.DATA)
    certs = data["certs"]
    fix = D.crossed_serials(data, certs)
    vac = C.place_order(C.REFERENCE_PLAN)
    out = {}
    for cid in C.IDS:
        cfg, obs, s_now, _rng = D.front_end(cid, data, certs, fix, vac)
        if s_now is None:
            s_now = latest_speed(cid, data)
        o = max((x for x in obs if x["kind"] == "entry"), key=lambda x: x["date"])
        s = s_now if o["speed"] == "now" else o["speed"]
        q = o["value"] * s
        perm = D.perm_of(cfg, o)
        mat, cm = D.seal_at(cfg, D.AUDIT)
        perm_ref = D.q_perm(mat, cm, D.T_REF)
        w_ref = D.q_wall_nominal(cfg["surfaces"], D.REF_H, "air", D.T_REF)
        if how == "as is":
            parts = {"wall-outgassing": q}
        elif how == "rest as leak":
            parts = {"wall-outgassing": w_ref, "permeation": perm_ref,
                     "air-leak": max(q - D.nominal_wall(cfg, o) - perm, 0.0)}
        else:
            c_w = max(q - perm, 0.0) / D.nominal_wall(cfg, o)
            parts = {"wall-outgassing": c_w * w_ref, "permeation": perm_ref}
        rated = D.rated_at(cfg) or s_now
        cause = "pump-speed" if s_now < D.PUMP_GATE * rated else max(parts, key=lambda k: parts[k])
        out[cid] = (cause, sum(parts.values()), s_now)
    return out


def main():
    C.header(__file__)
    C.require_baseline(C.reference_answers())
    data = D.load_data(C.DATA)
    ex_cause, ex_q, ex_s = example_result()
    answers = {}

    answers["one real chamber's result for all ten"] = {cid: (ex_cause, ex_q, ex_s) for cid in C.IDS}
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

    answers["the latest entry's gas load, as it stands"] = single_entry("as is")
    answers["the latest entry, the table's wall and the rest a leak"] = single_entry("rest as leak")
    answers["the latest entry, the rest put down to the wall"] = single_entry("rest as wall")

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
