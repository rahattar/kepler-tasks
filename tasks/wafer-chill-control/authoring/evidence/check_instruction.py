"""Mechanical checks on a hand-written instruction.md. Prose is never touched.

    python3 authoring/evidence/check_instruction.py [path]

Verifies that every quantity and name the brief states agrees with the public data, the
verifier and task.toml, that the mandated closing sentence is byte exact, that any
interface example is what the verifier actually calls, that the file reads as prose
rather than a procedure, and that nothing giving the method away appears.
"""
import ast
import json
import os
import re
import sys
from types import SimpleNamespace

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
FAILS, WARNS, PASSED = [], [], 0


# Standard library only, Python 3.8+: the sealed modules are read with ast, never imported,
# so the checker runs on a bare host interpreter without numpy.
def module_constants(path):
    """Module-level constants of a source file, evaluated in order where they are plain
    literals or arithmetic on earlier constants."""
    ns = {}
    for node in ast.parse(open(path).read()).body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            val = eval(compile(ast.Expression(node.value), path, "eval"), {"__builtins__": {}}, ns)
        except Exception:
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name):
                ns[tgt.id] = val
            elif isinstance(tgt, ast.Tuple) and isinstance(val, tuple) and len(val) == len(tgt.elts):
                for e, v in zip(tgt.elts, val):
                    if isinstance(e, ast.Name):
                        ns[e.id] = v
    return SimpleNamespace(**ns)


def dict_keys_in(path, func, cls=None):
    """String keys of the first dict literal inside a function (or method of cls)."""
    tree = ast.parse(open(path).read())
    scope = tree.body
    if cls:
        scope = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls).body
    fn = next(n for n in scope if isinstance(n, ast.FunctionDef) and n.name == func)
    d = next(n for n in ast.walk(fn) if isinstance(n, ast.Dict))
    return [k.value for k in d.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]


def agent_timeout(path):
    try:
        import tomllib
        with open(path, "rb") as f:
            return int(tomllib.load(f)["agent"]["timeout_sec"])
    except ImportError:
        m = re.search(r"^\[agent\][^\[]*?^timeout_sec\s*=\s*([\d.]+)", open(path).read(), re.M | re.S)
        return int(float(m.group(1)))

CLOSING = ("You have {t} seconds to complete this task. Do not cheat by using online "
           "solutions or hints specific to this task.")

# terms that would hand over the physics or the method
FORBIDDEN = [
    "rarefa", "temperature jump", "temperature-jump", "knudsen", "mean free path",
    "accommodation", "kennard", "slip regime", "continuum", "conductance", "k/d",
    "kalman", "observer", "estimator", "particle filter", "bayes", "likelihood",
    "hypothes", "model predictive", "mpc", "receding horizon", "lookahead", "look ahead",
    "look-ahead", "ride the", "riding", "bang-bang", "estimate the sag", "infer the sag",
    "identify the", "system identification", "fit a model", "first-order", "time constant",
    "plate warms", "plate heats", "plate rises", "heat capacity of the plate",
    "chiller conductance", "spot difference", "overstate", "lumped",
    "you should", "you may want", "make sure", "start by", "first,", "step 1", "step one",
]
# whole words only (these are substrings of innocent words)
FORBIDDEN_WORDS = ["lag", "lags", "lagged", "delay", "filter"]

WORD_MIN, WORD_MAX = 350, 650
WORDS = {2: "two", 3: "three", 9: "nine", 12: "twelve", 18: "eighteen",
         24: "twenty-four"}


def check(ok, msg):
    global PASSED
    if ok:
        PASSED += 1
    else:
        FAILS.append(msg)


def has_number(body, n, unit_re=""):
    """n as digits or as a word, followed by an optional unit pattern."""
    word = WORDS.get(int(n), None) if float(n).is_integer() else None
    num = ("%g" % n).replace(".", r"\.")
    alts = [r"(?<![\d.])%s(?:\.0)?(?![\d])" % num]
    if word:
        alts.append(r"\b%s\b" % word)
    pat = "(?:%s)%s" % ("|".join(alts), unit_re)
    return re.search(pat, body) is not None


def main(path):
    global PASSED
    if not os.path.exists(path):
        print("no instruction file at %s -- Alex writes it, by hand" % path)
        return 1
    raw = open(path).read()
    body = raw.lower()
    outside = re.sub(r"```.*?```", " ", raw, flags=re.S)
    prose = outside.lower()

    timeout = agent_timeout(os.path.join(ROOT, "task.toml"))
    data = os.path.join(ROOT, "environment", "data")
    prod = json.load(open(os.path.join(data, "production.json")))
    stations = json.load(open(os.path.join(data, "stations.json")))
    truth = json.load(open(os.path.join(ROOT, "tests", "truth.json")))
    plant = module_constants(os.path.join(ROOT, "tests", "plant.py"))
    grade = module_constants(os.path.join(ROOT, "tests", "grade.py"))

    # --- the mandated closing sentence, byte exact
    want = CLOSING.format(t=timeout)
    check(raw.rstrip("\n").endswith(want), "the file must end with exactly:\n    " + want)
    check(raw.endswith("\n") and not raw.endswith("\n\n\n"),
          "at most one trailing newline after the closing sentence")
    check("\n\n" + want in raw, "a blank line must precede the closing sentence")

    # --- the public spec, the sealed plant and the verifier agree with each other
    pairs = [("release_mass_mean_max_C", plant.T_TARGET), ("zone_difference_max_K", plant.ZONE_CAP),
             ("cycle_max_s", plant.T_CYCLE_MAX), ("control_period_s", plant.CTRL_DT),
             ("pressure_command_min_torr", plant.P_MIN),
             ("pressure_command_max_torr", plant.P_MAX),
             ("chamber_pressure_at_landing_torr", plant.P_IDLE),
             ("cycle_allowance_fraction", truth["allowance"])]
    for key, sealed in pairs:
        check(abs(prod[key] - sealed) < 1e-12,
              "production.json %s = %r but the verifier uses %r" % (key, prod[key], sealed))
    n_hidden = len(truth["wafers"])
    per_station = {s: sum(w["station"] == s for w in truth["wafers"]) for s in prod["stations"]}
    check(set(per_station.values()) == {prod["hidden_wafers_per_station"]},
          "hidden set per station %s disagrees with production.json" % per_station)
    sags = [w["_sag_um"] for w in truth["wafers"]]
    lo, hi = prod["center_sag_range_um"]
    check(lo <= min(sags) and max(sags) <= hi, "a hidden wafer's sag is outside the stated range")
    t0s = [w["_T0_C"] for w in truth["wafers"]]
    lo_t, hi_t = prod["incoming_temperature_range_C"]
    check(lo_t <= min(t0s) and max(t0s) <= hi_t,
          "a hidden wafer's incoming temperature is outside the stated range")

    # --- every number the brief must state
    need = [
        (plant.ZONE_CAP, r"\s*k\b", "the zone limit, 25.0 K"),
        (plant.T_TARGET, r"\s*(°\s*)?c\b", "the release limit, 50.0 C"),
        (plant.T_CYCLE_MAX, r"\s*(s\b|sec)", "the 30 s cycle limit"),
        (plant.CTRL_DT, r"\s*(s\b|sec)", "the 0.1 s control period"),
        (plant.P_MIN, r"", "the minimum pressure, 3.0 Torr"),
        (plant.P_MAX, r"\s*torr", "the maximum pressure, 60.0 Torr"),
        (plant.R_SPLIT * 1e3, r"\s*mm", "the zone split at r = 75 mm"),
        (plant.R_WAFER * 1e3, r"\s*mm", "the 150 mm radius in the sag profile"),
        (plant.SPOT_CENTER[1] * 1e3, r"\s*mm", "the centre spot's 10 mm outer radius"),
        (plant.SPOT_EDGE[0] * 1e3, r"", "the edge spot's 135 mm inner radius"),
        (plant.SPOT_EDGE[1] * 1e3, r"\s*mm", "the edge spot's 145 mm outer radius"),
        (hi, r"", "the sag range, -50 to +50 um"),
        (n_hidden, r"", "the number of hidden wafers, 24"),
        (prod["hidden_wafers_per_station"], r"", "12 hidden wafers per station"),
        (grade.INIT_TIMEOUT_S, r"\s*(s\b|sec)", "the 20 s constructor limit"),
        (grade.WAFER_BUDGET_S, r"\s*(s\b|sec)", "the 60 s per-wafer limit"),
    ]
    for val, unit, label in need:
        check(has_number(body, val, unit), "the brief must state %s" % label)
    check(re.search(r"(?<![\d.])1(\.0)?\s*(s\b|sec)|\bone second\b", body) is not None,
          "the brief must state the 1 s limit per step() call")
    pct = int(round(100 * truth["allowance"]))
    check(re.search(r"\b%d\s*(%%|percent|per cent)" % pct, body) is not None,
          "the cycle allowance of %d%% must appear" % pct)
    check(re.search(r"(-|−|minus |±|\+/-|\+-)\s*50\b", body) is not None,
          "the sag range must show its negative end (-50 um), not only 50")
    check(re.search(r"(perfect|complete|full|exact)[^.]{0,40}knowledge|knows? each wafer|"
                    r"knew each wafer|knows? the wafer|knew the wafer", body) is not None,
          "the brief must say what the cycle allowance is measured against: a controller "
          "with perfect knowledge of each wafer")
    check(re.search(r"\b(every|all|each)\b[^.]{0,60}\bwafers?\b", body) is not None,
          "the brief must say every hidden wafer has to meet the limits")
    check(re.search(r"\btotal\b", body) is not None,
          "the allowance is on the TOTAL cycle over all hidden wafers; say so")

    # --- names and paths
    for s in ("/app/controller.py", "/data", "/app/check_controller.py", "stations.json",
              "production.json", "characterization"):
        check(s in raw, "the literal '%s' must appear" % s)
    for s in ("controller", "step", "pressure_torr", "release", "film"):
        check(s in raw, "the literal '%s' must appear" % s)
    for k in dict_keys_in(os.path.join(ROOT, "tests", "plant.py"), "reading", cls="Wafer"):
        check(k in raw, "the reading key '%s' must appear (it is what step() receives)" % k)
    rec = dict_keys_in(os.path.join(ROOT, "tests", "grade.py"), "station_record")
    check("stations.json" in raw,
          "the brief must say the station argument is that station's record in stations.json "
          "(keys %s)" % sorted(rec))
    for f in prod["backside_films"]:
        check(f in body, "the film '%s' must be named" % f)
    for s in prod["stations"]:
        check(re.search(r"\b%s\b" % s, raw) is not None, "station %s must be named" % s)
    check(re.search(r"area[- ]mean", body) is not None, "zones and spots are AREA means; say so")
    check(re.search(r"mass[- ]mean", body) is not None, "the release limit is on the MASS mean")
    check(re.search(r"\bsag\b", body) is not None, "the sag must be named")
    check(re.search(r"(unknown|not known|not told|not measured|never told|not given|"
                    r"isn't known|does not know|doesn't know|neither measured|nor given|"
                    r"never given|never measured)", body) is not None,
          "the brief must say the controller is not told each wafer's sag")
    check("numpy" in body and "scipy" in body and "standard library" in body,
          "the brief must say only the standard library, numpy and scipy are available")
    check(re.search(r"self[- ]contained|single file|one file", body) is not None,
          "the brief must say the controller is one self-contained file")
    check(re.search(r"(new|fresh|separate)[^.]{0,50}(process|instance)", body) is not None,
          "the brief must say each wafer gets a fresh process, so nothing carries over")
    check(re.search(r"/data[^.]{0,80}(not|no longer|isn't|is not|unavailable|absent)|"
                    r"(not|no|without)[^.]{0,80}/data", body) is not None,
          "the brief must say /data is not available when the controller is graded")

    # --- any fenced example must match the interface the verifier calls
    blocks = re.findall(r"```(\w*)\s*\n(.*?)```", raw, re.S)
    check(len(blocks) <= 2, "at most two fenced blocks; found %d" % len(blocks))
    for lang, code in blocks:
        if lang.lower() in ("python", "py") or "class Controller" in code:
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                check(False, "the python example does not parse: %s" % e)
                continue
            cls = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Controller"]
            check(len(cls) == 1, "the python example must define class Controller")
            if cls:
                meths = {n.name: [a.arg for a in n.args.args] for n in cls[0].body
                         if isinstance(n, ast.FunctionDef)}
                check(meths.get("__init__", [None])[1:] == ["station", "wafer"],
                      "__init__ must take (self, station, wafer) as the verifier calls it")
                check(meths.get("step", [None])[1:] == ["t", "reading"],
                      "step must take (self, t, reading) as the verifier calls it")
            for d in [n for n in ast.walk(tree) if isinstance(n, ast.Dict)]:
                keys = {k.value for k in d.keys if isinstance(k, ast.Constant)}
                if keys & {"pressure_torr", "release"}:
                    check(keys <= {"pressure_torr", "release"},
                          "the example command has keys %s; the verifier reads only "
                          "pressure_torr and release" % sorted(keys))
        elif lang.lower() == "json":
            try:
                json.loads(code)
                PASSED += 1
            except ValueError as e:
                check(False, "the json example does not parse: %s" % e)

    # --- prose, not a procedure
    check(not re.search(r"^\s{0,3}#{1,6}\s", raw, re.M), "no markdown headings")
    check(not re.search(r"^\s*\d+[.)]\s+\S", outside, re.M),
          "no numbered steps outside the fenced blocks")
    check(len(re.findall(r"^\s*[-*]\s+\S", outside, re.M)) <= 8,
          "too many bullets outside the fenced blocks; this should read as prose")
    check(">>>" not in raw, "a '>>>' skeleton line was left in the file")
    check("FILL" not in raw, "a FILL placeholder was left in the file")
    check(not re.search(r"\b(\w+)\s+\1\b", prose), "a word appears doubled (editing slip?)")
    check(not re.search(r"\b(we|our|us)\b", prose),
          "first person ('we', 'our', 'us'); the last quality review failed a brief on this")
    if re.search(r",\s+not\s+(just|only|merely)\b", prose):
        WARNS.append("a 'not just/only ...' contrastive; the last review called these "
                     "removable")
    for para in re.split(r"\n\s*\n", outside):
        s = " ".join(para.split())
        if not s or s.startswith(("-", "|", "#")) or len(s) < 60:
            continue
        check(s[-1] in ".:;!?\"')", "this paragraph ends mid-sentence: ...%s" % s[-56:])
    if not raw.isascii():
        WARNS.append("non-ASCII characters present: %s"
                     % sorted({c for c in raw if ord(c) > 127}))

    # --- length
    words = len(outside.split())
    check(WORD_MIN <= words <= WORD_MAX,
          "word count %d is outside %d-%d (prose only, fenced blocks excluded)"
          % (words, WORD_MIN, WORD_MAX))

    # --- nothing that gives the method away
    for term in FORBIDDEN:
        if term in body:
            i = body.index(term)
            FAILS.append("forbidden term '%s': ...%s..." % (term, body[max(0, i - 40):i + 40]
                                                          .replace("\n", " ").strip()))
        else:
            PASSED += 1
    for term in FORBIDDEN_WORDS:
        m = re.search(r"\b%s\b" % term, body)
        if m:
            i = m.start()
            FAILS.append("forbidden word '%s': ...%s..." % (term, body[max(0, i - 40):i + 40]
                                                          .replace("\n", " ").strip()))
        else:
            PASSED += 1

    print("instruction: %s  (%d words of prose)" % (path, words))
    for w in WARNS:
        print("  WARN  " + w)
    if FAILS:
        print("\n%d FAILED of %d checks:" % (len(FAILS), PASSED + len(FAILS)))
        for f in FAILS:
            print("  FAIL  " + f)
        return 1
    print("\nclean: %d checks passed, %d warning(s)" % (PASSED, len(WARNS)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "instruction.md")))
