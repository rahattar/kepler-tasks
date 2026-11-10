"""Mechanical checks on a hand-written instruction.md. Prose is never touched.

    python3 authoring/evidence/check_instruction.py [path]

Verifies that every quantity the brief states agrees with the sealed spec and the
grader, that the mandated closing sentence is byte exact and agrees with the agent
timeout, that the JSON schema shown is what the grader actually parses, that the file
is prose rather than a procedure, and that nothing giving the task away appears.
"""
import json
import os
import re
import sys
import tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", ".."))
FAILS, WARNS, PASSED = [], [], 0

CLOSING = ("You have {t} seconds to complete this task. Do not cheat by using online "
           "solutions or hints specific to this task.")

# terms that would hand over the physics, the structure, or the campaign
FORBIDDEN = [
    "rarefa", "temperature jump", "knudsen", "mean free path", "accommodation",
    "slip regime", "slip flow", "continuum", "k/d", "conductance",
    "roughness correlat", "lot-to-lot", "lot to lot", "varies between stations",
    "varies from station", "differ thermally", "per-station coefficient",
    "not isothermal", "plate rises", "plate heats", "plate droop", "chiller capacity",
    "extrapolat", "interpolat", "regression", "covariate", "predict the remaining",
    "which stations to", "choose stations that", "span the", "make sure to",
    "you should", "you may want", "start by", "first,", "step 1", "step one",
]
# words that are fine in the file list but must not be editorialised
NEUTRAL_ONLY = ["plate_roughness_Ra_um", "passivation_lot"]

WORD_MIN, WORD_MAX = 400, 600


def check(ok, msg):
    global PASSED
    if ok:
        PASSED += 1
    else:
        FAILS.append(msg)


def main(path):
    global PASSED
    if not os.path.exists(path):
        print(f"no instruction file at {path} -- Alex writes it, by hand")
        return 1
    raw = open(path).read()
    body = raw.lower()

    with open(os.path.join(ROOT, "task.toml"), "rb") as f:
        toml = tomllib.load(f)
    timeout = int(toml["agent"]["timeout_sec"])
    spec = json.load(open(os.path.join(ROOT, "environment", "data", "spec.json")))
    truth = json.load(open(os.path.join(ROOT, "tests", "truth.json")))
    stations = [s["station"] for s in truth["stations"]]

    # --- the mandated closing sentence, byte exact
    want = CLOSING.format(t=timeout)
    check(raw.rstrip("\n").endswith(want),
          f"the file must end with exactly:\n    {want}")
    check(raw.endswith("\n") and not raw.endswith("\n\n\n"),
          "at most one trailing newline after the closing sentence")
    check("\n\n" + want in raw, "a blank line must precede the closing sentence")
    check(str(timeout) in raw, f"the closing sentence must name {timeout} seconds")

    # --- every number agrees with the sealed spec
    for val, label in ((spec["target_mean_temperature_C"], "target temperature"),
                       (spec["max_zone_difference_K"], "zone difference limit"),
                       (spec["he_pressure_min_torr"], "minimum pressure"),
                       (spec["he_pressure_max_torr"], "maximum pressure")):
        check(f"{val:g}" in raw or f"{val:.1f}" in raw,
              f"{label} {val} does not appear in the brief")
    pct = int(round(100 * spec["dwell_budget_fraction"]))
    check(f"{pct}%" in raw or f"{pct} percent" in body,
          f"the dwell budget of {pct}% does not appear")
    check("per station" in body or "each station" in body or "that station" in body,
          "the brief must make clear the dwell budget is PER STATION, not a fleet total")

    # The fleet-level gate is a count, and the agent cannot infer the number. It has to
    # be stated or the task is graded on a rule the solver was never given.
    need = None
    try:
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import grade as _g
        with open(os.path.join(ROOT, "tests", "truth.json")) as f:
            _sealed = json.load(f)["spec"]
        with open(os.path.join(ROOT, "environment", "data", "spec.json")) as f:
            _public = json.load(f)
        need = _sealed.get("min_stations_commissioned", _g.MIN_STATIONS)
        # Three places now carry the count: the public spec the agent reads, the sealed
        # spec the grader reads, and the grader's own fallback. Drift between them would
        # grade on a rule nobody was told, so check they agree before checking the prose.
        check(_public.get("min_stations_commissioned") == need,
              f"public spec.json says min_stations_commissioned="
              f"{_public.get('min_stations_commissioned')}, sealed truth says {need}")
        check(_g.MIN_STATIONS == need,
              f"grade.MIN_STATIONS is {_g.MIN_STATIONS}, the spec says {need}")
    except Exception as e:
        check(False, f"could not cross-check the station count: {e}")
    WORDS = {8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
             13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen",
             18: "eighteen", 20: "twenty", 24: "twenty-four"}
    n_fleet = None
    try:
        with open(os.path.join(ROOT, "tests", "truth.json")) as f:
            _t = json.load(f)
        n_fleet = len(_t["stations"])
        n_budget = int(_t["budget_runs"])
    except Exception as e:
        check(False, f"could not read the fleet size from tests/truth.json: {e}")
    if need is not None:
        spelled = WORDS.get(need, str(need))
        # word boundaries: "14" must not be satisfied by the 14400 in the timeout line
        check(re.search(r"\b%s\b|\b%d\b" % (spelled, need), body) is not None,
              f"the brief must state how many of the stations have to meet the limits "
              f"({spelled}); the agent cannot infer a count gate")
        check(re.search(r"(at least|minimum of|no fewer than)", body) is not None,
              "the brief must say the station requirement is a minimum, not that every "
              "station must pass")
    if n_fleet is not None:
        spelled = WORDS.get(n_fleet, str(n_fleet))
        check(re.search(r"\b%s\b|\b%d\b" % (spelled, n_fleet), body) is not None,
              f"the station count ({spelled}) must be stated")
        check(("S%02d" % n_fleet) in raw,
              f"the brief must name the last station, S{n_fleet:02d}, so the required "
              f"set is unambiguous")
        for stale in [k for k in WORDS if k not in (need, n_fleet, n_budget)]:
            # a count from an earlier fleet size left behind in the prose
            pat = r"\b(%s)\b" % WORDS[stale]
            if re.search(pat + r" (of the |stations|runs)", body):
                check(False, f"'{WORDS[stale]}' appears next to stations/runs but matches "
                             f"neither the fleet ({n_fleet}), the gate ({need}) nor the "
                             f"budget ({n_budget}) -- stale number")
        bspell = WORDS.get(n_budget, str(n_budget))
        check(re.search(r"\b%s\b|\b%d\b" % (bspell, n_budget), body) is not None,
              f"the run budget ({bspell}) must be stated")
    check(not re.search(r"total dwell|summed across|sum of the dwell|across all "
                        r"(twelve|12|sixteen|16)", body),
          "the brief appears to describe the dwell budget as a fleet total")

    # --- paths and the bench surface
    for s in ("/data", "/app/recipe.json", "/app/bench.py", "75 mm", "10 hz"):
        check(s in body, f"the literal '{s}' must appear")
    check("bench.py status" in body, "the brief must show 'bench.py status'")
    check(re.search(r"bench\.py run\s+--station\s+\S+\s+--pressure\s+\S+\s+"
                    r"--seconds\s+\S+", body) is not None,
          "the brief must show a complete 'bench.py run' command with all three flags")

    # --- the premise: no thermal data anywhere
    no_data = re.search(r"(no|none|never|without|nothing|any)[^.]{0,80}"
                        r"(thermal data|thermal runs|thermal measurement|"
                        r"been run|had a wafer|run a wafer)", body)
    check(no_data is not None,
          "the brief must say plainly that no thermal data is provided -- a sentence "
          "containing a negation near 'thermal data' or 'thermal runs'")

    # --- the schema the grader actually parses
    blocks = re.findall(r"```json\s*(.*?)```", raw, re.S)
    check(len(blocks) == 1, f"expected exactly one json block, found {len(blocks)}")
    if blocks:
        try:
            doc = json.loads(blocks[0])
            check("stations" in doc and isinstance(doc["stations"], list),
                  "the example must be an object with a 'stations' array")
            keys = set(doc["stations"][0]) if doc.get("stations") else set()
            check(keys == {"station", "he_pressure_torr", "dwell_s"},
                  f"the example keys {sorted(keys)} are not what the grader parses: "
                  "station, he_pressure_torr, dwell_s")
            sys.path.insert(0, os.path.join(ROOT, "tests"))
            import grade
            tmp = "/tmp/_instr_schema.json"
            full = {"stations": [{"station": n, "he_pressure_torr": 10.0,
                                  "dwell_s": 9.0} for n in stations]}
            with open(tmp, "w") as f:
                json.dump(full, f)
            try:
                grade.parse_recipe(tmp)
                PASSED += 1
            except ValueError as e:
                FAILS.append(f"the grader rejects the brief's own schema: {e}")
        except json.JSONDecodeError as e:
            check(False, f"the json block does not parse: {e}")

    # --- every station named, and the range reads right
    check(stations[0] in raw and stations[-1] in raw,
          f"the brief must name the station range, {stations[0]} through {stations[-1]}")

    # --- prose, not a procedure
    check(not re.search(r"^\s{0,3}#{1,6}\s", raw, re.M),
          "no markdown headings")
    outside = re.sub(r"```.*?```", "", raw, flags=re.S)
    check(not re.search(r"^\s*\d+[.)]\s+\S", outside, re.M),
          "no numbered steps outside the fenced blocks")
    check(not re.search(r"^\s*[-*]\s+\S", outside, re.M) or
          len(re.findall(r"^\s*[-*]\s+\S", outside, re.M)) <= 8,
          "too many bullets outside the fenced blocks; this should read as prose")
    check(">>>" not in raw, "a '>>>' skeleton line was left in the file")
    check("FILL" not in raw, "a FILL placeholder was left in the file")
    check(not re.search(r"\b(\w+)\s+\1\b", outside),
          "a word appears doubled, which usually means an editing slip")
    # Truncation is a property of a PARAGRAPH, not of a hard-wrapped line: prose that
    # wraps mid-sentence is normal and must not be flagged.
    for para in re.split(r"\n\s*\n", outside):
        s = " ".join(para.split())
        if not s or s.startswith(("-", "|", "#")) or len(s) < 60:
            continue
        if re.search(r"(^|\s)(/\S*/)?\w+\.(py|sh)\s", s + " "):
            # Bare command lines. Markdown joins them into one run-on line, which is
            # worse than a style nit: the reader is shown a command that does not exist.
            check(False, "these command lines are not in a fenced block, so markdown "
                         f"renders them as one run-on line: {s[:90]}")
            continue
        check(s[-1] in ".:;!?\"')", f"this paragraph ends mid-sentence: ...{s[-56:]}")

    # --- word count
    words = len(re.sub(r"```.*?```", " ", raw, flags=re.S).split())
    check(WORD_MIN <= words <= WORD_MAX,
          f"word count {words} is outside {WORD_MIN}-{WORD_MAX} (prose only, "
          "fenced blocks excluded)")

    # --- nothing that gives the task away
    for term in FORBIDDEN:
        if term in body:
            ctx = body[max(0, body.index(term) - 40):body.index(term) + 40]
            FAILS.append(f"forbidden term '{term}' appears: ...{ctx.strip()}...")
        else:
            PASSED += 1
    for term in NEUTRAL_ONLY:
        n = body.count(term.lower())
        if n > 1:
            WARNS.append(f"'{term}' appears {n} times; naming it once in the file "
                         "list is enough, more starts to look like a hint")

    print(f"instruction: {path}  ({words} words of prose)")
    for w in WARNS:
        print("  WARN  " + w)
    if FAILS:
        print(f"\n{len(FAILS)} FAILED of {PASSED + len(FAILS)} checks:")
        for f in FAILS:
            print("  FAIL  " + f)
        return 1
    print(f"\nclean: {PASSED} checks passed, {len(WARNS)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1
                  else os.path.join(ROOT, "instruction.md")))
