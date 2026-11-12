#!/usr/bin/env python3
"""The design rules of the task, recomputed from the sealed definition and checked.

    python3 tune.py

Nothing here uses the reference solution. Each rule is a property the sealed unit must have for the task to
be what the README says it is; each line gives the figure and whether the rule holds. Exit status 0 only when
every rule holds.
"""
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import unit3 as U  # noqa: E402

held = []


def rule(text, ok):
    held.append(ok)
    print("%s %s" % ("holds" if ok else "FAILS", text))


def worth(t, ratio_error):
    """How far a pump's shaft is put out, running, by an error in its support's ratio (mm)."""
    return U.ALPHA * t["h_stat"] * abs(ratio_error) * (t["tpnow"] - U.T_REF)


def main():
    seed = json.load(open(os.path.join(HERE, "seed.json")))["seed"]
    T = U.build(seed)
    tol = U.TOL
    pumps = [t for t in T.values() if t.get("cons")]
    changed = [t for t in pumps if t["change"]]
    print("Design rules on the sealed unit (seed %d). The acceptance is %.2f mm.\n" % (seed, tol))

    # the scale of the physics against the acceptance
    hot = [t for t in pumps if t["tpnow"] > 100.0]
    grow = [U.growth(t["h_stat"], t["t_stat"], t["amb"]) for t in hot]
    rule("the supports of the %d hot pumps rise by %.2f to %.2f mm from cold to running, %d to %d times the "
         "acceptance" % (len(hot), min(grow), max(grow), int(min(grow) / tol), int(max(grow) / tol)), min(grow) > 10 * tol)
    kelvin = [tol / (U.ALPHA * t["h_stat"]) for t in hot]
    rule("the acceptance is worth %.1f to %.1f K of support temperature on a hot pump" % (min(kelvin), max(kelvin)),
         max(kelvin) < 10.0)
    share = [tol / (U.ALPHA * t["h_stat"] * (t["tpnow"] - U.T_REF)) for t in hot]
    rule("in the ratio of support rise to pumped rise above 25 C, the acceptance is worth %.3f to %.3f"
         % (min(share), max(share)), max(share) < abs(U.K_2019["Fc"] - U.K_2019["Fd"]) / 2)
    lever = max((t["span"] + t["a"] + t["b"]) / t["span"] for t in T.values())
    rule("the cold line is carried from the reading planes to feet up to %.1f spans away" % lever, lever > 3.0)

    # the programme
    turbines = [t for t in T.values() if t["kind"] == "turb"]
    by_behaviour = {(t["cons"], t["change"]) for t in changed}
    by_label = {(U.BUILD[t["cons"]], t["change"]) for t in changed}
    need = len(turbines) + len(by_behaviour)
    rule("measurements the records cannot replace: %d turbines and %d groups of changed pumps, %d in all, "
         "against %d visits" % (len(turbines), len(by_behaviour), need, U.BUDGET), need == U.BUDGET)
    rule("counted by the construction the pump data lists, the groups are %d and the count is %d, one short of "
         "the visits" % (len(by_label), len(turbines) + len(by_label)), len(turbines) + len(by_label) == U.BUDGET - 1)

    # each change is worth more than the acceptance on every pump it reaches
    low = min(worth(t, U.K_NOW[(t["cons"], t["change"])] - U.K_2019[t["cons"]]) for t in changed)
    rule("a changed pump left on its 2019 ratio is out by at least %.3f mm (every one of %d)" % (low, len(changed)),
         low > 2 * tol)
    split = [t for t in changed if t["cons"] in ("Fc", "Fd")]
    other = {"Fc": "Fd", "Fd": "Fc"}
    low = min(worth(t, U.K_NOW[(t["cons"], "dry")] - U.K_NOW[(other[t["cons"]], "dry")]) for t in split)
    rule("an HSC pump given the other HSC model's measured ratio is out by at least %.3f mm (every one of %d)"
         % (low, len(split)), low > 2 * tol)
    low = min(worth(t, U.K_2019["Fc"] - U.K_2019["Fd"]) for t in split)
    rule("the two HSC models' 2019 ratios, %.2f and %.2f, are worth at least %.3f mm on any of their pumps, so "
         "the survey tells them apart" % (U.K_2019["Fc"], U.K_2019["Fd"], low), low > 2 * tol)
    same = [models for cons in ("F", "Cc") for models in [sorted(m for m, c in U.MODELS.items() if c == cons)]]
    rule("the other two changed groups hold two models each with one ratio before and one after: %s"
         % "; ".join(" and ".join(m) for m in same), all(len(m) == 2 for m in same))
    plain = {"Fc": "F", "Fd": "F", "Cc": "C"}
    blanked = [t for t in changed if t["change"] == "dry"]
    low = min(worth(t, U.K_NOW[(t["cons"], "dry")] - U.K_2019[plain[t["cons"]]]) for t in blanked)
    rule("a drained pedestal taken as a plain one of the same casing support is out by at least %.3f mm "
         "(every one of %d)" % (low, len(blanked)), low > tol)

    # the revamp reaches the untouched pumps through their pumped temperature
    moved = [t for t in pumps if not t["change"] and t["tpnow"] != t["tp19"]]
    low = min(U.ALPHA * t["h_stat"] * U.K_2019[t["cons"]] * abs(t["tpnow"] - t["tp19"]) for t in moved)
    rule("an untouched pump whose pumped temperature moved, left on its survey temperature, is out by at least "
         "%.3f mm (every one of %d)" % (low, len(moved)), low > tol)
    high = max(U.ALPHA * t["h_stat"] * 1.5 * (t["tpnow"] - U.T_REF) / (t["tp19"] - U.T_REF) for t in pumps)
    rule("the survey's own scatter, 1.5 K at most on a support, is worth at most %.3f mm on any pump" % high,
         high < tol / 2)

    # the turbines
    low = min(max(abs(U.TURB_NOW[k][i] - U.TURB_2023[k][i]) for i in (0, 1)) for k in U.TURB_NOW)
    rule("each turbine's running position has moved from its 2023 hot check by at least %.2f mm" % low, low > 2 * tol)
    a, b = sorted(U.TURB_NOW)
    gap = max(abs(U.TURB_NOW[a][i] - U.TURB_NOW[b][i]) for i in (0, 1))
    rule("the two turbines differ from each other by %.2f mm, so one cannot stand for the other" % gap, gap > 2 * tol)

    # the compressors are settled: nothing in the sealed unit differs from what their records say
    gear = [t for t in T.values() if t["kind"] == "comp"]
    rule("the %d compressor trains run where the maker's gearbox figure and the survey put them: a visit to "
         "one returns what the records already give" % len(gear),
         all(U.running_change(t)[:2] == U.GEAR[t["gear"]] and t["t_stat"] == t["t_stat19"] for t in gear))

    # the sag
    over = [t for t in T.values() if U.SAG[(t["kit"], U.bar_for(t["span"]))] > tol]
    rule("%d of %d trains were read with a bracket whose sag is above the acceptance" % (len(over), len(T)),
         len(over) >= len(T) // 3)

    # every train is its own question
    cross = [(i, j) for i in T for j in T if i != j and U.passes(T[j], U.true_moves(T[i]))]
    rule("no train's sealed moves leave any other train aligned (%d pairs of %d do)" % (len(cross), len(T) * (len(T) - 1)),
         not cross)
    worst = max(max(abs(v) for v in U.residual(t, U.true_moves(t))) for t in T.values())
    rule("the sealed moves leave every train aligned to rounding error", worst < 1e-9)

    print("\ndesign rules: %d of %d hold" % (sum(held), len(held)))
    return 0 if all(held) else 1


if __name__ == "__main__":
    sys.exit(main())
