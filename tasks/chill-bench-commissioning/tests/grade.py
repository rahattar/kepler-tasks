"""Grader for the commissioning-bench design. Sealed; the agent never sees it.

Three criteria, all per station, all re-derived at grade time from the physics
module. Nothing is compared against a stored answer.

  C1  mass-mean wafer temperature at the end of dwell <= target
  C2  max |T_inner - T_outer| during the dwell <= cap
  C3  the station's dwell <= (1 + delta) x THAT STATION's optimal dwell

A station is commissioned when it meets all three. The recipe is accepted when at
least MIN_STATIONS of the fleet are commissioned.

Two deliberate choices:

C3 is per station, not summed. A summed budget pools slack across the fleet and lets
one station run several times its own optimum (measured at 2.7x on the previous
design); per station, the budget means what it says.

The fleet-level gate is a count, not a conjunction over the whole fleet. All-or-nothing
across every station and criterion means one slip on one station zeros an otherwise
correct commissioning run, and it made the verdict on an earlier fleet turn on a 0.08 K
excess at a single station while every other margin was healthy. Requiring all but one
keeps the discrimination that matters: wrong covariate models lose several of the
stations they had to predict, not one (authoring/evidence/baselines.txt).
"""
import functools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import physics as ph

HERE = os.path.dirname(os.path.abspath(__file__))

# How many of the fleet must be commissioned. The sealed spec carries the authoritative
# value (min_stations_commissioned); this is the fallback if a truth file predates it.
# Set from measurement, not taste: authoring/evidence/design_mc.txt and probe_runs.txt.
MIN_STATIONS = 15


@functools.lru_cache(maxsize=None)
def _optimum(key, T_tgt, cap, P_lo, P_hi):
    """Constrained optimum for one station. Memoised: same station, same answer."""
    name, d_in, d_out, T0, Tsp, a = key
    st = ph.Station(name, d_in, d_out, T0, Tsp, a, a)
    return ph.fastest_feasible(st, T_tgt, cap, P_lo, P_hi)


def load_truth(path=None):
    with open(path or os.path.join(HERE, "truth.json")) as f:
        return json.load(f)


def _stations(truth):
    out = []
    for s in truth["stations"]:
        a = s["_alpha"]
        out.append(ph.Station(s["station"], s["inner_standoff_um"] * 1e-6,
                              s["outer_standoff_um"] * 1e-6,
                              s["incoming_temperature_C"], s["plate_setpoint_C"], a, a))
    return out


def parse_recipe(path):
    if not os.path.exists(path):
        raise ValueError(f"{path} does not exist")
    with open(path) as f:
        try:
            doc = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path} is not valid JSON: {e}")
    if not isinstance(doc, dict) or "stations" not in doc:
        raise ValueError("top level must be an object with a 'stations' array")
    out = {}
    for i, row in enumerate(doc["stations"]):
        if not isinstance(row, dict):
            raise ValueError(f"stations[{i}] is not an object")
        for key in ("station", "he_pressure_torr", "dwell_s"):
            if key not in row:
                raise ValueError(f"stations[{i}] is missing '{key}'")
        name = str(row["station"])
        try:
            P, dw = float(row["he_pressure_torr"]), float(row["dwell_s"])
        except (TypeError, ValueError):
            raise ValueError(f"stations[{i}] has non-numeric pressure or dwell")
        if not (P == P and dw == dw):
            raise ValueError(f"stations[{i}] has NaN")
        if name in out:
            raise ValueError(f"station {name} appears more than once")
        out[name] = (P, dw)
    return out


def grade(recipe_path, truth=None, verbose=False):
    truth = truth or load_truth()
    spec = truth["spec"]
    T_tgt = spec["target_mean_temperature_C"]
    cap = spec["max_zone_difference_K"]
    delta = spec["dwell_budget_fraction"]
    P_lo, P_hi = spec["he_pressure_min_torr"], spec["he_pressure_max_torr"]
    stations = _stations(truth)

    res = {"reward": 0, "criteria": {}, "stations": [], "error": None}
    try:
        recipe = parse_recipe(recipe_path)
    except ValueError as e:
        res["error"] = str(e)
        return res

    missing = [s.name for s in stations if s.name not in recipe]
    if missing:
        res["error"] = f"recipe is missing stations: {', '.join(missing)}"
        return res

    commissioned = 0
    for st in stations:
        P, dw = recipe[st.name]
        if not (P_lo - 1e-9 <= P <= P_hi + 1e-9):
            res["error"] = (f"station {st.name}: pressure {P} Torr is outside the "
                            f"{P_lo}-{P_hi} Torr supply range")
            return res
        if dw < 0:
            res["error"] = f"station {st.name}: negative dwell"
            return res
        T_end, grad = ph.state_at(P, dw, st)
        o = _optimum((st.name, st.d_ctr, st.d_edge, st.T0_C, st.T_setpoint_C,
                      st.alpha_wafer), T_tgt, cap, P_lo, P_hi)
        if o is None:
            res["error"] = f"station {st.name} has no feasible recipe; task is broken"
            return res
        limit = (1.0 + delta) * o[1]
        ok1, ok2, ok3 = T_end <= T_tgt + 1e-9, grad <= cap + 1e-9, dw <= limit + 1e-9
        ok = ok1 and ok2 and ok3
        commissioned += int(ok)
        res["stations"].append({
            "station": st.name, "he_pressure_torr": P, "dwell_s": dw,
            "T_end_C": round(T_end, 4), "zone_diff_K": round(grad, 4),
            "optimal_dwell_s": round(o[1], 4), "dwell_limit_s": round(limit, 4),
            "dwell_ratio": round(dw / o[1], 4),
            "meets_temperature": bool(ok1), "meets_uniformity": bool(ok2),
            "meets_dwell_budget": bool(ok3), "commissioned": bool(ok)})

    need = spec.get("min_stations_commissioned",
                    truth.get("min_stations_commissioned", MIN_STATIONS))
    res["commissioned"] = commissioned
    res["stations_required"] = need
    res["criteria"] = {
        "temperature_failures": sum(1 for s in res["stations"]
                                    if not s["meets_temperature"]),
        "uniformity_failures": sum(1 for s in res["stations"]
                                   if not s["meets_uniformity"]),
        "dwell_budget_failures": sum(1 for s in res["stations"]
                                     if not s["meets_dwell_budget"]),
    }
    res["reward"] = int(commissioned >= need)
    if verbose:
        print("reward %d  -- %d of %d stations commissioned, %d required  %s"
              % (res["reward"], commissioned, len(stations), need, res["criteria"]))
        for s in res["stations"]:
            flags = "".join(["T" if not s["meets_temperature"] else ".",
                             "U" if not s["meets_uniformity"] else ".",
                             "B" if not s["meets_dwell_budget"] else "."])
            print("  %-4s P=%6.2f dw=%6.2f  T_end=%7.3f  dT=%6.2f  "
                  "dwell %.3fx  [%s]"
                  % (s["station"], s["he_pressure_torr"], s["dwell_s"], s["T_end_C"],
                     s["zone_diff_K"], s["dwell_ratio"], flags))
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("recipe")
    ap.add_argument("--truth", default=None)
    a = ap.parse_args()
    r = grade(a.recipe, load_truth(a.truth) if a.truth else None, verbose=True)
    sys.exit(0 if r["reward"] else 1)
