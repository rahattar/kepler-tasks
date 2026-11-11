"""Every rule the bundle must satisfy, checked mechanically. Run it after any change, however small.

    python3 -I preflight.py

It checks the bundle's contents and names, the instruction, task.toml and README, the verifier's pins and reward
logic, how the truth is reached, the sealed definition's permissions, and that the evidence files are present and
report no problem. It also checks that every physical constant the solution and the independent audit carry their
own copy of still agrees with the sealed definition, which is the check that catches a table drifting apart from
the physics it is supposed to describe.

Exit status 0 when every check passes.
"""
import importlib.util
import os
import re
import sys
import subprocess
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
TASK = os.path.dirname(os.path.dirname(HERE))

ALLOWED_TOP = {"README.md", "instruction.md", "task.toml", "authoring", "environment", "solution", "tests"}
GRADING_WORDS = ["grader", "verifier", "reward", "score", "pass", "fail", "tested", "graded", "partial credit"]
LAST_PARAGRAPH = ("You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints "
                  "specific to this task.")
PINS = {"numpy": "2.1.3", "scipy": "1.14.1", "pandas": "2.2.3", "pytest": "8.4.1",
        "pytest-json-ctrf": "0.3.5"}
EVIDENCE = ["reference_run", "method_spread", "route_study", "null_baselines", "plan_sweep", "hedge_study",
            "verifier_checks"]

checks = []


def ok(name):
    checks.append((True, name, ""))


def bad(name, why):
    checks.append((False, name, why))


def check(cond, name, why=""):
    if cond:
        ok(name)
    else:
        bad(name, why)
    return cond


def read(rel):
    with open(os.path.join(TASK, rel)) as f:
        return f.read()


def run_py(path, args):
    """Run a bundle script in a child process and return (exit code, combined output)."""
    p = subprocess.run([sys.executable, "-I", path] + list(args), cwd=os.path.dirname(path),
                       capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------------------------- the bundle
def check_contents():
    top = set(os.listdir(TASK))
    extra = {t for t in top if not t.startswith(".")} - ALLOWED_TOP
    extra = {e for e in extra if e != "__pycache__"}
    check(not extra, "the bundle holds nothing but the seven allowed entries",
          "also found: " + ", ".join(sorted(extra)))
    for want in ALLOWED_TOP:
        check(os.path.exists(os.path.join(TASK, want)), "the bundle holds %s" % want, "missing")

    bad_names, non_ascii = [], []
    for root, dirs, files in os.walk(TASK):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        if ".git" in root:
            continue
        for n in list(dirs) + files:
            if n in ("README.md", "Dockerfile"):
                continue
            if n.isupper() or (n.upper() == n and any(c.isalpha() for c in n)):
                bad_names.append(os.path.relpath(os.path.join(root, n), TASK))
            try:
                n.encode("ascii")
            except UnicodeEncodeError:
                non_ascii.append(n)
    check(not bad_names, "no all-uppercase names except README.md and Dockerfile", ", ".join(bad_names))
    check(not non_ascii, "every file and folder name is ASCII", ", ".join(non_ascii))

    offenders = []
    for root, _dirs, files in os.walk(TASK):
        if ".git" in root or "__pycache__" in root:
            continue
        for n in files:
            p = os.path.join(root, n)
            try:
                with open(p, "rb") as f:
                    raw = f.read()
            except OSError:
                continue
            try:
                raw.decode("ascii")
            except UnicodeDecodeError:
                offenders.append(os.path.relpath(p, TASK))
    check(not offenders, "every shipped file is ASCII throughout", ", ".join(offenders))

    name = re.search(r'^name\s*=\s*"([^"]+)"', read("task.toml"), re.M)
    slug = name.group(1).split("/")[-1] if name else ""
    check(1 <= len(slug.split("-")) <= 3, "the task name has at most three hyphenated words", slug)
    check(slug == os.path.basename(TASK), "the task name matches the bundle's folder",
          "%s vs %s" % (slug, os.path.basename(TASK)))


def check_no_obfuscation():
    """No encoded strings anywhere, and nothing that decodes one at run time. A security review rejected a bundle
    that held programme names base64-encoded for a self-check, so what is looked for is an import of a decoding
    module, a call to a decoding function, and any literal that looks like encoded data.

    The check reads each file's syntax rather than its text, so a module name written here as a plain string does
    not itself count as an occurrence, and no file is exempt from the check."""
    import ast

    modules = {"base64", "binascii", "quopri", "uu", "codecs"}
    funcs = {"decodebytes", "encodebytes", "unhexlify", "hexlify", "fromhex", "decompress"}
    b64ish = re.compile(r"^[A-Za-z0-9+/]{24,}={0,2}$")
    hexish = re.compile(r"^[0-9a-fA-F]{32,}$")

    def looks_encoded(text):
        if " " in text or "\n" in text or "/" not in text and "." in text:
            pass
        if b64ish.match(text) and any(c.isdigit() for c in text) and any(c.isupper() for c in text) \
                and any(c.islower() for c in text):
            return True
        return bool(hexish.match(text))

    hits = []
    for root, _dirs, files in os.walk(TASK):
        if ".git" in root or "__pycache__" in root:
            continue
        for n in files:
            path = os.path.join(root, n)
            rel = os.path.relpath(path, TASK)
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if n.endswith(".py"):
                try:
                    tree = ast.parse(text)
                except SyntaxError:
                    hits.append("%s: will not parse" % rel)
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for a in node.names:
                            if a.name.split(".")[0] in modules:
                                hits.append("%s: imports %s" % (rel, a.name))
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module.split(".")[0] in modules:
                            hits.append("%s: imports from %s" % (rel, node.module))
                    elif isinstance(node, ast.Attribute):
                        if node.attr in funcs or node.attr.startswith(("b64", "b32", "b16", "a85", "b85")):
                            hits.append("%s: calls %s" % (rel, node.attr))
                    elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                        if looks_encoded(node.value):
                            hits.append("%s: holds a literal that looks encoded" % rel)
            else:
                for token in re.findall(r"[A-Za-z0-9+/=]{24,}", text):
                    if looks_encoded(token.rstrip("=") + "=" * (len(token) - len(token.rstrip("=")))):
                        hits.append("%s: holds a token that looks encoded" % rel)
    check(not hits, "nothing in the bundle encodes or decodes a string", "; ".join(sorted(set(hits))[:6]))


# ---------------------------------------------------------------------------------------------- instruction
def check_instruction():
    text = read("instruction.md")
    check(not any(line.lstrip().startswith("#") for line in text.splitlines()),
          "the instruction has no heading")
    low = text.lower()
    found = [w for w in GRADING_WORDS if re.search(r"\b%s\b" % re.escape(w), low)]
    check(not found, "the instruction uses no grading word", ", ".join(found))
    paras = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    check(paras and " ".join(paras[-1].split()) == LAST_PARAGRAPH,
          "the instruction's last paragraph is exactly the required sentence",
          repr(paras[-1][:70]) if paras else "no paragraphs")

    wanted = ["/app/data/docs/ms_bp_audit.md", "/app/data/docs/vacuum_data.md",
              "/app/data/chamber_register.csv", "/app/data/base_pressure_log.csv",
              "/app/data/speed_tests.csv", "/app/data/turbo_controller.csv",
              "/app/data/maintenance_log.csv", "/app/data/gauge_certificates.md",
              "/app/output/diagnosis.csv"]
    missing = [w for w in wanted if w not in text]
    check(not missing, "the instruction names every load-bearing path in full", ", ".join(missing))

    header = "chamber,cause,q_total_mbarl_s,s_eff_l_s"
    check(header in text, "the instruction gives the sheet's header exactly", header)

    sys.path.insert(0, os.path.join(TASK, "tests"))
    sys.path.insert(0, os.path.join(TASK, "tests", "sealed"))
    import grade_audit as G
    import fleet as F
    for cause in ["air-leak", "virtual-leak", "wall-outgassing", "permeation", "pump-speed"]:
        check(cause in text, "the instruction names the cause %r" % cause)
    check("%.0f" % (100 * G.Q_TOL) in text or "%.1f" % (100 * G.Q_TOL) in text,
          "the instruction states the gas-load tolerance", "%.1f%%" % (100 * G.Q_TOL))
    check("%.0f" % (100 * G.S_TOL) in text or "%.1f" % (100 * G.S_TOL) in text,
          "the instruction states the speed tolerance", "%.1f%%" % (100 * G.S_TOL))
    check(str(G.MAX_BYTES) in text, "the instruction states the size limit", str(G.MAX_BYTES))
    check("%.1f" % F.REF_H in text or str(int(F.REF_H)) in text,
          "the instruction or the standard fixes the reference condition")

    # the instruction must not hint at any trap
    hints = ["drift", "crossed", "swapped", "misfiled", "trap ", "baffle", "degraded", "contaminated",
             "trapped volume", "thin", "beware", "careful", "note that", "do not forget", "remember to"]
    leaked = [h for h in hints if re.search(r"\b%s\b" % re.escape(h.strip()), low)]
    check(not leaked, "the instruction hints at no trap or mechanism", ", ".join(leaked))

    words = {1: "one", 2: "two", 3: "three", 4: "four"}
    check(str(F.BUDGET) in text or re.search(r"\b%s test\b" % words.get(F.BUDGET, "x"), low),
          "the instruction states the test budget", str(F.BUDGET))
    check("vacwork" in low, "the instruction names the command that places the order")

    # The instruction must agree with the documents the agent will read. It once said /app/data/example/ held
    # the chamber's audit result while about_this_chamber.md and records_format.md both said no result is given,
    # which is a contradiction the agent cannot resolve.
    example_docs = (read("environment/data/example/about_this_chamber.md")
                    + read("environment/data/docs/records_format.md")).lower()
    says_none = "no audited result is given" in example_docs
    check(says_none, "the example's own documents say whether a result is given")
    if says_none:
        claims = re.search(r"example/[^.]*\b(audit result|audited result|result MS-BP gives)", text, re.I)
        check(claims is None,
              "the instruction does not claim the example carries an audited result",
              claims.group(0) if claims else "")
        check("no audited result is given" in low,
              "the instruction says outright that the example has no audited result")

    # Nothing the agent can discover in one command belongs in the instruction: it is not part of the contract
    # and it dates the moment the image changes.
    # Only the image's own furniture counts. "One test is available across the fleet" is the task contract, so
    # a bare "is available" must not trip this; what must trip it is a package, an interpreter or an install.
    runtime = r"(?:numpy|scipy|pandas|matplotlib|sklearn|pytest|python\s*3|pip|interpreter|packages?|libraries|" \
              r"modules?|pre-?installed|installed)"
    narration = [m.group(0) for m in re.finditer(
        r"[^.]*\b%s\b[^.]*(?:is|are)\s+(?:available|installed|provided|present)|"
        r"(?:is|are)\s+(?:available|installed|provided|present)[^.]*\b%s\b[^.]*|"
        r"\bpip\s+install\b|\bimport\s+(?:numpy|scipy|pandas)\b" % (runtime, runtime), low)]
    check(not narration, "the instruction narrates no discoverable detail of the image",
          "; ".join(n.strip()[:60] for n in narration))


# ---------------------------------------------------------------------------------------------- task.toml
def check_task_toml():
    text = read("task.toml")

    def field(name):
        m = re.search(r'^\s*%s\s*=\s*(.+)$' % re.escape(name), text, re.M)
        return m.group(1).strip() if m else None

    check(field("domain") == '"engineering-sciences"', "task.toml domain is engineering-sciences",
          str(field("domain")))
    check(field("field") == '"mechanical-engineering"', "task.toml field is mechanical-engineering",
          str(field("field")))
    check('"/app/output/diagnosis.csv"' in text, "task.toml declares the artifact")

    # Parsed rather than matched: harbor reads the file as TOML, and the keys below decide which
    # container the verifier runs in and whether either side has egress. A regex over the text once
    # let `network = false` pass here, which harbor does not read at all.
    try:
        t = tomllib.loads(text)
    except Exception as exc:
        bad("task.toml parses as TOML", str(exc))
        t = None
    if t is not None:
        check(t.get("agent", {}).get("timeout_sec") == 28800.0, "task.toml gives the agent 28800 s",
              repr(t.get("agent", {}).get("timeout_sec")))
        check(t.get("agent", {}).get("user") == "agent", "task.toml runs the agent as user agent",
              repr(t.get("agent", {}).get("user")))
        check(t.get("verifier", {}).get("timeout_sec") == 600.0, "task.toml gives the verifier 600 s",
              repr(t.get("verifier", {}).get("timeout_sec")))
        check(t.get("verifier", {}).get("environment_mode") == "separate",
              "task.toml runs the verifier in its own container",
              repr(t.get("verifier", {}).get("environment_mode")))
        check(t.get("verifier", {}).get("environment", {}).get("network_mode") == "no-network",
              "task.toml leaves the verifier without network",
              repr(t.get("verifier", {}).get("environment", {}).get("network_mode")))
        check(t.get("environment", {}).get("network_mode") == "public",
              "task.toml gives the agent the open internet",
              repr(t.get("environment", {}).get("network_mode")))
        for key in ("build_timeout_sec", "cpus", "memory_mb", "storage_mb", "gpus"):
            check(key in t.get("environment", {}), "task.toml declares environment.%s" % key)
        check("network" not in t.get("verifier", {}),
              "task.toml carries no bare verifier network key, which harbor ignores")

    # The difficulty explanation lives in README.md, not task.toml: the benchmark does not read it from there.
    readme = read("README.md")
    diff = re.search(r"^## Difficulty\s*\n([\s\S]*?)(?=^## )", readme, re.M)
    check(diff is not None, "README.md carries a difficulty explanation")
    if diff:
        body = diff.group(1)
        check("synthetic" in body, "the difficulty explanation says the data is synthetic")
        check("vacuum" in body.lower() and ("engineer" in body.lower() or "practitioner" in body.lower()),
              "the difficulty explanation names who does the work")
        check("research analogue" in body.lower() or "analogue" in body.lower(),
              "the difficulty explanation names the research analogue")
        agentish = re.findall(r"\b(?:xhigh|low effort|probe|agent|subagent|trial|run of 8|8 of 8)\b",
                              body, re.I)
        check(not agentish, "the difficulty explanation carries no agent-performance claim",
              ", ".join(sorted(set(agentish))))


def check_readme_matches_toml():
    readme = read("README.md")
    for head in ("## Difficulty", "## Reference solution", "## Verification"):
        check(head in readme, "README.md carries %s" % head)

    # The three explanations live in README.md alone; the benchmark does not read them from task.toml.
    t = tomllib.loads(read("task.toml"))
    for fieldname in ("difficulty_explanation", "solution_explanation", "verification_explanation",
                      "category", "subcategory"):
        check(fieldname not in t.get("metadata", {}),
              "task.toml metadata does not carry the unsupported field %s" % fieldname)

    # The documents are generated from the evidence, so regenerating them must be a no-op. This is the check
    # that catches a study re-run without a rewrite - the staleness this bundle was rejected for.
    code, out = run_py(os.path.join(TASK, "authoring", "provenance", "meta.py"), ["--check"])
    check(code == 0, "README.md and task.toml are current with the evidence", out.strip().splitlines()[-1:])


def check_evidence_is_sound():
    """No study may quote an exception as a finding.

    hedge_study.txt once reported 32 of 32 cases as "not reachable: TypeError", because a blanket except turned
    its own bug into a row of the table, and the verification explanation drew conclusions from it."""
    ev = os.path.join(TASK, "authoring", "evidence")
    for n in sorted(os.listdir(ev)):
        if not n.endswith(".txt"):
            continue
        body = read(os.path.join("authoring", "evidence", n))
        for word in ("Traceback", "TypeError", "ValueError", "KeyError", "IndexError", "AttributeError",
                     "not reachable", "UNEXPECTED"):
            check(word not in body, "%s reports no %s" % (n, word))
        check(body.strip() != "", "%s is not empty" % n)


def check_no_unused_runtime_files():
    """Every file shipped in a container is read by something.

    Three generation records - two seed.json and a truth.json - rode along in the sealed directories, read by
    nothing, and the bundle was rejected for carrying them."""
    # the names that are structural: the container reads them by convention, not by being mentioned
    structural = {"Dockerfile", "requirements.txt", "test.sh", "solve.sh", "run.sh", "entrypoint.sh",
                  "conftest.py", "pytest.ini", "vacwork-cmd"}
    # everything in the bundle that could name a file
    corpus = []
    for root, dirs, files in os.walk(TASK):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for n in files:
            if n.endswith((".py", ".md", ".sh", ".toml", ".txt", ".json", ".cmd")) or n in structural:
                try:
                    corpus.append(open(os.path.join(root, n), errors="replace").read())
                except OSError:
                    pass
    corpus = "\n".join(corpus)
    for tree in ("environment", "tests"):
        for root, dirs, files in os.walk(os.path.join(TASK, tree)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for n in sorted(files):
                rel = os.path.relpath(os.path.join(root, n), TASK)
                if n in structural or n.endswith(".csv"):
                    continue           # csv records are named in records_format.md and the instruction
                # the file's own text does not count as a mention of it
                others = corpus.replace(open(os.path.join(root, n), errors="replace").read(), "")
                check(n in others, "something reads %s" % rel,
                      "nothing in the bundle names it; generation records belong in authoring/provenance")
    for tree in ("environment", "tests"):
        for root, _dirs, files in os.walk(os.path.join(TASK, tree)):
            for n in files:
                if n in ("truth.json", "seed.json"):
                    bad("no generation record ships in %s" % tree, os.path.join(root, n))
    ok("no generation record ships in a container")


# ---------------------------------------------------------------------------------------------- verifier
def check_verifier():
    dockerfile = read("tests/Dockerfile")
    for pkg, ver in PINS.items():
        check("%s==%s" % (pkg, ver) in dockerfile, "the verifier pins %s at %s" % (pkg, ver))
    check("chmod 700 /tests" in dockerfile, "the verifier keeps /tests at 700")
    check("chmod -R go-rwx /tests" in dockerfile, "the verifier keeps /tests unreadable to others")

    test_sh = read("tests/test.sh")
    first = test_sh.index('echo -n "0"')
    pytest_at = test_sh.index("python -m pytest")
    check(first < pytest_at, "test.sh writes reward 0 before grading runs")
    check('s.get("tests") == 1' in test_sh and 's.get("passed") == 1' in test_sh,
          "test.sh requires exactly one test, passed, in the ctrf report")
    for key in ("failed", "skipped", "pending", "other"):
        check('"%s"' % key in test_sh, "test.sh requires no %s test" % key)
    last = test_sh.rindex('echo -n "1"')
    check(test_sh.rindex("COUNTS_OK") < last, "test.sh writes reward 1 only after the counts are checked")
    check("chown root:root /logs/verifier" in test_sh, "test.sh locks the log directory to root")

    env = read("environment/Dockerfile")
    check("chmod 700 /opt/vacwork/sealed" in env, "the agent's image keeps the sealed definition at 700")
    check("useradd" in env and "contractor" in env, "the agent's image gives the contractor its own user")
    check("visudo -cf" in env, "the agent's image validates its sudoers file")
    check(re.search(r"agent ALL=\(contractor\) NOPASSWD: /opt/vacwork/run status, /opt/vacwork/run submit", env),
          "the only privileged commands are the order's status and submit")
    check("/app/output" in env and "chown agent:agent /app/output" in env,
          "the agent may write only to /app/output")


def check_truth_is_sealed():
    grade = read("tests/grade_audit.py")
    check("import fleet as F" in grade and "F.truth" in grade,
          "the grader reaches the truth through the sealed fleet")
    import ast
    tree = ast.parse(grade)
    reaches = []
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d = ast.get_docstring(node, clean=False)
            if d:
                docstrings.add(d)
        if isinstance(node, ast.Import):
            reaches += [a.name for a in node.names if "diagnose" in a.name or "solution" in a.name]
        elif isinstance(node, ast.ImportFrom):
            if node.module and ("diagnose" in node.module or "solution" in node.module):
                reaches.append(node.module)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value not in docstrings:
            if "solution" in node.value or "diagnose" in node.value:
                reaches.append(node.value[:40])
    check(not reaches, "the grader does not reach for the reference solution", ", ".join(reaches))
    for f in ("bpphys.py", "fleet.py"):
        check(os.path.exists(os.path.join(TASK, "tests", "sealed", f)),
              "the verifier carries the sealed %s" % f)
    sealed = open(os.path.join(TASK, "tests", "sealed", "fleet.py")).read()
    prov = open(os.path.join(TASK, "authoring", "provenance", "fleet.py")).read()
    check(sealed == prov, "the verifier's sealed fleet is the provenance fleet, byte for byte")
    sealed_p = open(os.path.join(TASK, "tests", "sealed", "bpphys.py")).read()
    prov_p = open(os.path.join(TASK, "authoring", "provenance", "bpphys.py")).read()
    check(sealed_p == prov_p, "the verifier's sealed physics is the provenance physics, byte for byte")
    rig = open(os.path.join(TASK, "environment", "rig", "sealed", "fleet.py")).read()
    check(rig == prov, "the contractor's sealed fleet is the provenance fleet, byte for byte")


# ---------------------------------------------------------------------------------------------- constants
def check_constants_do_not_drift():
    """Every table the solution and the independent audit carry their own copy of must still agree with the
    sealed definition. A copy that drifts is how a reference comes to disagree with the physics it is grading
    against, which is exactly the fault a validation round rejected a bundle for."""
    P = load(os.path.join(TASK, "tests", "sealed", "bpphys.py"), "pf_bpphys")
    F = load(os.path.join(TASK, "tests", "sealed", "fleet.py"), "pf_fleet")
    D = load(os.path.join(TASK, "solution", "diagnose.py"), "pf_diagnose")
    I = load(os.path.join(TASK, "authoring", "evidence", "independent.py"), "pf_independent")

    def same(a, b, tol=1e-12):
        if isinstance(a, dict) and isinstance(b, dict):
            return set(a) == set(b) and all(same(a[k], b[k], tol) for k in a)
        if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            return len(a) == len(b) and all(same(x, y, tol) for x, y in zip(a, b))
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
        return a == b

    for label, a, b in [
        ("turbo curves", P.TURBO, D.TURBO),
        ("outgassing table", P.OUTGAS, D.OUTGAS),
        ("dry air", P.AIR, D.AIR),
        ("gauge sensitivities", P.GAS_FACTOR, D.GAS_FACTOR),
        ("the gas each mechanism admits", P.SPECIES, D.SPECIES),
        ("the wall water activation energy", P.E_W, D.E_W),
        ("the permeation activation energy", P.E_P, D.E_P),
        ("the nitrogen vent factor", P.N2_FACTOR, D.N2_FACTOR),
        ("the reference temperature", P.T_REF, D.T_REF),
        ("the pump gate", P.PUMP_GATE, D.PUMP_GATE),
        ("the reference pumping time", F.REF_H, D.REF_H),
        ("the audit date", F.AUDIT, D.AUDIT),
        ("the shop's fixtures", F.FIXTURES, D.FIXTURES),
    ]:
        check(same(a, b), "the solution's %s agrees with the sealed definition" % label,
              "%r vs %r" % (a, b))

    check(same({k: (v["K20"], tuple(v["rel"][s] for s in ("n2", "o2", "ar", "co2")))
                for k, v in P.SEALS.items()},
               {k: (v[0], tuple(v[1][s] for s in ("n2", "o2", "ar", "co2"))) for k, v in D.SEALS.items()}),
          "the solution's seal table agrees with the sealed definition")

    for label, a, b in [
        ("turbo curves", P.TURBO, {k: list(v) for k, v in I.PUMPS.items()}),
        ("outgassing table", P.OUTGAS, I.SURF),
        ("gauge sensitivities", P.GAS_FACTOR, I.SENS),
        ("the wall gas composition", P.SPECIES["wall-outgassing"], I.WALL_GAS),
        ("the wall water activation energy", P.E_W, I.EW),
        ("the permeation activation energy", P.E_P, I.EP),
        ("the nitrogen vent factor", P.N2_FACTOR, I.VENT_N2),
        ("the pump gate", P.PUMP_GATE, I.GATE),
        ("the reference pumping time", F.REF_H, I.REF_HOURS),
        ("the shop's fixtures", F.FIXTURES, I.KIT),
        ("dry air", tuple(P.AIR[k] for k in ("n2", "o2", "ar", "co2")), I.DRY_AIR),
    ]:
        check(same(a, b), "the independent audit's %s agrees with the sealed definition" % label,
              "%r vs %r" % (a, b))

    check(same({k: (v["K20"], tuple(v["rel"][s] for s in ("n2", "o2", "ar", "co2")))
                for k, v in P.SEALS.items()},
               {k: (v[0], v[1]) for k, v in I.ELAST.items()}),
          "the independent audit's seal table agrees with the sealed definition")

    # the documents are written from the sealed constants, so they cannot drift; check they were rebuilt
    sys.path.insert(0, os.path.join(TASK, "authoring", "provenance"))
    docs = load(os.path.join(TASK, "authoring", "provenance", "docs_bp.py"), "pf_docs")
    for rel, text in docs.docs().items():
        for where in ("environment/data", "tests/app_data"):
            path = os.path.join(TASK, where, rel)
            if not check(os.path.exists(path), "%s/%s is present" % (where, rel), "missing"):
                continue
            on_disk = open(path).read()
            check(" ".join(on_disk.split()) == " ".join(text.split()),
                  "%s/%s is what the generator writes now" % (where, rel),
                  "the shipped document is out of date; rerun build.py")


# ---------------------------------------------------------------------------------------------- evidence
def check_evidence():
    ed = os.path.join(TASK, "authoring", "evidence")
    for name in EVIDENCE:
        py = os.path.join(ed, name + ".py")
        txt = os.path.join(ed, name + ".txt")
        check(os.path.exists(py), "the evidence script %s.py is present" % name, "missing")
        if not check(os.path.exists(txt), "the evidence record %s.txt is present" % name, "missing"):
            continue
        body = open(txt).read()
        check("Traceback" not in body, "%s.txt records no crash" % name)
        check("PROBLEM" not in body, "%s.txt reports no problem" % name,
              "it does; read the file")
        if name == "verifier_checks":
            check("UNEXPECTED" not in body, "verifier_checks.txt holds no UNEXPECTED case",
                  "a case did not behave as the rules say")
    prov = os.path.join(TASK, "authoring", "provenance")
    for f in ("bpphys.py", "fleet.py", "docs_bp.py", "build.py", "tune.py"):
        check(os.path.exists(os.path.join(prov, f)), "the provenance holds %s" % f, "missing")


def check_data_tree():
    for where in ("environment/data", "tests/app_data"):
        for f in ("chamber_register.csv", "base_pressure_log.csv", "speed_tests.csv", "turbo_controller.csv",
                  "maintenance_log.csv", "shop_climate.csv", "gauge_certificates.md"):
            check(os.path.exists(os.path.join(TASK, where, f)), "%s/%s is present" % (where, f), "missing")
        check(os.path.isdir(os.path.join(TASK, where, "example")), "%s/example is present" % where, "missing")
    a = sorted(os.path.relpath(os.path.join(r, n), os.path.join(TASK, "environment/data"))
               for r, _d, fs in os.walk(os.path.join(TASK, "environment/data"))
               if "__pycache__" not in r for n in fs)
    b = sorted(os.path.relpath(os.path.join(r, n), os.path.join(TASK, "tests/app_data"))
               for r, _d, fs in os.walk(os.path.join(TASK, "tests/app_data"))
               if "__pycache__" not in r for n in fs)
    check(a == b, "the verifier's copy of the data holds the same files as the agent's")
    for rel in a:
        p1 = os.path.join(TASK, "environment/data", rel)
        p2 = os.path.join(TASK, "tests/app_data", rel)
        if os.path.exists(p2):
            check(open(p1, "rb").read() == open(p2, "rb").read(),
                  "the two copies of %s are identical" % rel, "they differ")
    # the sealed truth must not be reachable from the agent's data
    for root, _dirs, files in os.walk(os.path.join(TASK, "environment")):
        if "__pycache__" in root:
            continue
        for n in files:
            if n == "truth.json":
                bad("the agent's image carries no truth file", os.path.join(root, n))
    ok("the agent's image carries no truth file")


def main():
    check_contents()
    check_no_obfuscation()
    check_instruction()
    check_task_toml()
    check_readme_matches_toml()
    check_evidence_is_sound()
    check_no_unused_runtime_files()
    check_verifier()
    check_truth_is_sealed()
    check_constants_do_not_drift()
    check_evidence()
    check_data_tree()

    failed = [c for c in checks if not c[0]]
    for good, name, why in checks:
        if not good:
            print("FAIL  %s%s" % (name, (": " + why) if why else ""))
    print("")
    print("%d checks, %d failed" % (len(checks), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
