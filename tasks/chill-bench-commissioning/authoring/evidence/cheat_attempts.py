"""Adversarial shortcuts. Every one must score 0.

Each entry is a recipe an agent could produce without doing the commissioning work, or
a malformed submission that might slip past a careless parser. They are graded by the
shipped grader, in one process so the per-station optima are derived once.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "tests"))
import grade

TR = grade.load_truth(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "..", "..", "tests", "truth.json"))
NAMES = [s["station"] for s in TR["stations"]]
NEED = TR["spec"].get("min_stations_commissioned", grade.MIN_STATIONS)
TMP = "/tmp/cheat.json"

# The eight the reference's campaign actually measures (the seven hull vertices plus
# S16), so the eight it has to predict are the eight a "measure what you can, guess the
# rest" shortcut leaves guessed.
MEASURABLE = {"S07", "S15", "S11", "S05", "S09", "S04", "S16", "S06"}


def rec(rows):
    return {"stations": rows}


def flat(P, dw, names=None):
    return rec([{"station": n, "he_pressure_torr": P, "dwell_s": dw}
                for n in (names or NAMES)])


with open("/tmp/refrun/app/recipe.json") as f:
    ORACLE = json.load(f)

CHEATS = [
    ("nop: no recipe file at all", None),
    ("empty object", {}),
    ("empty station list", rec([])),
    ("not JSON at all", "THIS IS NOT JSON"),
    ("go slow: 3 Torr and a 30 s dwell everywhere", flat(3.0, 30.0)),
    ("go slow: 6 Torr and a 20 s dwell everywhere", flat(6.0, 20.0)),
    ("maximum pressure, generous dwell", flat(60.0, 12.0)),
    ("maximum pressure, minimum dwell", flat(60.0, 3.5)),
    ("one mid recipe copied to all sixteen", flat(11.0, 9.5)),
    ("zero dwell everywhere", flat(11.0, 0.0)),
    ("negative dwell", flat(11.0, -5.0)),
    ("pressure below the supply range", flat(1.0, 12.0)),
    ("pressure above the supply range", flat(120.0, 8.0)),
    ("only the first eight stations", flat(11.0, 9.5, NAMES[:8])),
    ("a station that does not exist", flat(11.0, 9.5, NAMES[:-1] + ["S99"])),
    ("one station listed twice, one omitted",
     rec([{"station": n, "he_pressure_torr": 11.0, "dwell_s": 9.5}
          for n in NAMES[:-1] + ["S01"]])),
    ("the oracle with every dwell padded 15%",
     rec([{**r, "dwell_s": round(r["dwell_s"] * 1.15, 3)} for r in ORACLE["stations"]])),
    ("the oracle with every dwell shaved 10%",
     rec([{**r, "dwell_s": round(r["dwell_s"] * 0.90, 3)} for r in ORACLE["stations"]])),
    # the other half of the shortcut space: right dwell, pressure pushed to the zone side
    ("the oracle with every pressure raised 15%",
     rec([{**r, "he_pressure_torr": round(r["he_pressure_torr"] * 1.15, 3)}
          for r in ORACLE["stations"]])),
    ("the oracle's pressures, all dwells set to the fleet mean",
     rec([{**r, "dwell_s": round(sum(x["dwell_s"] for x in ORACLE["stations"])
                                 / len(ORACLE["stations"]), 3)}
          for r in ORACLE["stations"]])),
    ("the oracle's dwells, all pressures set to the fleet mean",
     rec([{**r, "he_pressure_torr":
           round(sum(x["he_pressure_torr"] for x in ORACLE["stations"])
                 / len(ORACLE["stations"]), 3)} for r in ORACLE["stations"]])),
    # The one the count gate has to refuse: do the work on the eight you can measure
    # and put a plausible mid recipe on the eight you cannot. Allowing one station to
    # fail must not turn into allowing eight.
    ("the oracle on the eight measurable stations, one mid recipe on the other eight",
     rec([r if r["station"] in MEASURABLE
          else {"station": r["station"], "he_pressure_torr": 11.0, "dwell_s": 9.5}
          for r in ORACLE["stations"]])),
]


def constant_dwell_coverage():
    """With a count gate, a constant dwell only has to commission SOME stations.

    The impossibility argument under a conjunction was 'no single dwell satisfies
    temperature and budget together at any pressure'. Under a 15-of-16 count that is no
    longer the right question -- a cheat could sacrifice a station. So re-derive it: a
    station is commissionable at a constant dwell D only if D lies between its own
    optimum and (1 + delta) times it, since at its best pressure the time to target IS
    the optimum. Report the best coverage any single D achieves.
    """
    import numpy as np
    import physics as ph
    sp = TR["spec"]
    delta = sp["dwell_budget_fraction"]
    need = sp.get("min_stations_commissioned", grade.MIN_STATIONS)
    opts = []
    for s in grade._stations(TR):
        o = ph.fastest_feasible(s, sp["target_mean_temperature_C"],
                                sp["max_zone_difference_K"],
                                sp["he_pressure_min_torr"], sp["he_pressure_max_torr"])
        opts.append((s.name, o[1], (1 + delta) * o[1]))
    grid = np.arange(min(o for _, o, _ in opts), max(h for _, _, h in opts) + 0.01, 0.01)
    best, bestD = 0, None
    for D in grid:
        n = sum(1 for _, lo, hi in opts if lo - 1e-9 <= D <= hi + 1e-9)
        if n > best:
            best, bestD = n, float(D)
    print("\n  per-station commissionable dwell windows [optimum, +%.0f%%]:"
          % (100 * delta))
    for n, lo, hi in sorted(opts, key=lambda x: x[1]):
        print("    %-4s [%6.3f, %6.3f] s" % (n, lo, hi))
    print("  best single constant dwell: %.2f s commissions %d of %d stations"
          % (bestD, best, len(opts)))
    print("  gate requires %d, so a constant dwell %s"
          % (need, "PASSES -- HOLE" if best >= need else "still fails"))
    return best


if __name__ == "__main__":
    print("%-76s %7s %6s  %s"
          % ("shortcut", "reward", "comm", "why it fails"))
    print("-" * 120)
    worst = 0
    for label, body in CHEATS:
        if body is None:
            if os.path.exists(TMP):
                os.remove(TMP)
        elif isinstance(body, str):
            with open(TMP, "w") as f:
                f.write(body)
        else:
            with open(TMP, "w") as f:
                json.dump(body, f)
        r = grade.grade(TMP, TR)
        if r["error"]:
            why, comm = r["error"][:56], "-"
        else:
            why = ", ".join(t for k, t in (("meets_temperature", "temperature"),
                                           ("meets_uniformity", "uniformity"),
                                           ("meets_dwell_budget", "dwell budget"))
                            if any(not s[k] for s in r["stations"])) or "-"
            comm = "%2d/%d" % (r["commissioned"], len(NAMES))
        worst = max(worst, r["reward"])
        print("%-76s %7d  %5s  %s" % (label, r["reward"], comm, why), flush=True)
    print("-" * 120)
    print("gate requires %d of %d commissioned; highest reward any shortcut "
          "achieved: %d  %s"
          % (NEED, len(NAMES), worst, "PASS" if worst == 0 else "*** A SHORTCUT SCORES 1 ***"))
    constant_dwell_coverage()
