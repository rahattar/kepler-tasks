"""Structural checks on the bundle. Run from the task directory:

    python3 authoring/evidence/preflight.py
"""
import filecmp
import os
import re
import subprocess
import sys
import tempfile
import tomllib

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ALLOWED_ROOT = {"instruction.md", "task.toml", "README.md", "environment", "solution", "tests", "authoring"}
BAND = re.compile(r"(?<![\d.])1\.2(?![\d])")        # the band the verifier allows on a reported form error
FAILS, PASSED = [], [0]


def check(ok, msg):
    PASSED[0] += 1
    if not ok:
        FAILS.append(msg)


def main():
    os.chdir(ROOT)
    # ---- structure
    roots = set(os.listdir("."))
    check(roots <= ALLOWED_ROOT | {".source_zip"}, "root has unexpected entries: %s" % sorted(roots - ALLOWED_ROOT))
    for p in ("instruction.md", "task.toml", "README.md", "environment/Dockerfile", "environment/rig/lab.py",
              "environment/rig/sealed/isim.py", "environment/rig/sealed/seed.json", "solution/solve.py",
              "solution/solve.sh", "tests/Dockerfile", "tests/test.sh", "tests/test_form.py", "tests/grade_form.py",
              "tests/sealed/isim.py", "tests/sealed/seed.json", "authoring/provenance/isim.py",
              "authoring/provenance/gen.py", "authoring/provenance/tune.py", "authoring/evidence/common.py",
              "authoring/evidence/route_study.py", "authoring/evidence/route_study.txt",
              "authoring/evidence/method_spread.py", "authoring/evidence/method_spread.txt",
              "authoring/evidence/campaign_study.py", "authoring/evidence/campaign_study.txt",
              "authoring/evidence/hedge_study.py", "authoring/evidence/hedge_study.txt",
              "authoring/evidence/null_baselines.py", "authoring/evidence/null_baselines.txt",
              "authoring/evidence/verifier_checks.py", "authoring/evidence/verifier_checks.txt",
              "authoring/evidence/independent.py", "authoring/evidence/independent.txt",
              "authoring/evidence/reference_run.py", "authoring/evidence/reference_run.txt",
              "authoring/evidence/preflight.py"):
        check(os.path.isfile(p), "missing %s" % p)
    junk = []
    for dp, dirs, files in os.walk("."):
        for name in files:
            p = os.path.join(dp, name)
            if p == "./.source_zip":
                continue    # the repository's marker of the last zip built; the zip itself leaves it out
            if name.startswith(".") or name.endswith((".pyc", ".orig", ".rej")) or "__pycache__" in p:
                junk.append(p)
                continue
            with open(p, "rb") as f:
                raw = f.read()
            try:
                raw.decode("ascii")
            except UnicodeDecodeError:
                check(False, "not ASCII: %s" % p)
        for d in list(dirs):
            if d in ("__pycache__", ".pytest_cache"):
                junk.append(os.path.join(dp, d))
                dirs.remove(d)
    check(not junk, "junk that must be removed: %s" % sorted(junk))

    # ---- the sealed definition, in its three places
    for other in ("environment/rig/sealed/isim.py", "tests/sealed/isim.py"):
        check(filecmp.cmp("authoring/provenance/isim.py", other, shallow=False),
              "%s differs from authoring/provenance/isim.py" % other)
    check(filecmp.cmp("environment/rig/sealed/seed.json", "tests/sealed/seed.json", shallow=False),
          "the two seed.json differ")

    # ---- the records regenerate byte for byte, and the verifier's copy matches the agent's
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "data")
    r = subprocess.run([sys.executable, "-I", "authoring/provenance/gen.py", out], capture_output=True, text=True)
    check(r.returncode == 0, "gen.py failed: %s" % r.stderr[-300:])
    if r.returncode == 0:
        cmp = filecmp.dircmp("environment/data", out)
        bad = []

        def walk(c, base=""):
            bad.extend(os.path.join(base, n) for n in c.left_only + c.right_only + c.diff_files)
            for name, sub in c.subdirs.items():
                walk(sub, os.path.join(base, name))
        walk(cmp)
        check(not bad, "gen.py does not reproduce environment/data: %s" % sorted(bad)[:6])
    cmp2 = filecmp.dircmp("environment/data", "tests/app_data")
    bad2 = []

    def walk2(c, base=""):
        bad2.extend(os.path.join(base, n) for n in c.left_only + c.right_only + c.diff_files)
        for name, sub in c.subdirs.items():
            walk2(sub, os.path.join(base, name))
    walk2(cmp2)
    check(not bad2, "tests/app_data differs from environment/data: %s" % sorted(bad2)[:6])

    # ---- the instruction
    ins = open("instruction.md").read()
    check(ins.rstrip().endswith("You have 28800 seconds to complete this task. Do not cheat by using online "
                                "solutions or hints specific to this task."), "instruction's closing line")
    for w in ("grader", "verifier", "reward", "score", "pass", "fail", "tested", "graded", "partial credit",
              "scoring", "test_", "tolerance"):
        check(w not in ins.lower(), "instruction mentions %r" % w)
    check(not ins.lstrip().startswith("#"), "the instruction must carry no heading")
    for f in ("feature_register.csv", "drawing_requirements.csv", "machining_log.csv", "measurement_index.csv",
              "docs/standard_fm7.md", "docs/instrument_notes.md", "docs/metrology_room.md",
              "docs/inspection_report.md", "measurements"):
        check("/app/data/" + f in ins, "the instruction must name /app/data/%s by its path" % f)
    for f in ("/app/scan_reports", "/app/output/form.csv"):
        check(f in ins, "the instruction must name %s" % f)
    for w in ("minimum zone", "least squares", "least-squares", "spindle", "error motion", "nyquist", "alias",
              "undulation", "taylor", "mating", "envelope", "re-hone", "rehone", "same setup", "transfer",
              "temperature", "filter", "harmonic"):
        check(w not in ins.lower(), "instruction gives away the mechanism: %r" % w)
    check("28800" in ins and "4 scans" in ins, "instruction must state the time and the booking")

    # ---- the band must be readable nowhere the agent can reach
    visible = ["instruction.md"] + sorted(os.path.join(dp, f) for dp, _, fs in os.walk("environment/data")
                                          for f in fs if not f.endswith(".csv") or "measurements" not in dp)
    for p in visible:
        txt = open(p, encoding="ascii", errors="ignore").read()
        check(not BAND.search(txt), "an agent-visible file states the band: %s" % p)
    check(BAND.search(open("tests/grade_form.py").read()) is not None, "the verifier lost its band")

    # ---- what the documents must say, and must not
    fm7 = open("environment/data/docs/standard_fm7.md").read()
    for phrase in ("exp(-pi (0.4697 n / 50)^2)", "minimum-zone", "largest cylinder", "smallest such cylinder",
                   "diametrically opposite", "11.7e-6", "reject_both"):
        check(phrase in fm7, "FM-7 lost %r" % phrase)
    notes = open("environment/data/docs/instrument_notes.md").read()
    for phrase in ("12 touch points", "least-squares", "spindle encoder's zero", "has not been renewed"):
        check(phrase in notes, "the instrument notes lost %r" % phrase)
    room = open("environment/data/docs/metrology_room.md").read()
    check("4 scans" in room and "does not refill" in room, "the metrology room note lost its booking")
    bore = " ".join(open("environment/data/docs/boring_practice.md").read().split())
    for phrase in ("property of the setup", "carry the same undulations per revolution", "angular position",
                   "The diameter", "The taper", "no longer carries that setup's lobing"):
        check(phrase in bore, "the boring practice note lost %r" % phrase)
    check("boring_practice.md" in ins, "the instruction must name the boring practice note")
    for name in sorted(os.listdir("authoring/provenance/docs")):
        check(os.path.exists(os.path.join("environment/data/docs", name)),
              "a written document is not shipped to the agent: %s" % name)

    # ---- the instruction's formatting contract is the verifier's, clause for clause. A correct sheet passes;
    # the same answers to one decimal, as whole numbers, or under a header that is not character for character
    # the one asked for, do not. (Bounced Nov 11: the reader trimmed the header and took any number of decimals
    # up to two, so sheets outside the stated format could pass.)
    for clause in ("exact header `feature,form_um,verdict`", "to two decimal places",
                   "one row for each of the 14 features",
                   "one of `accept`, `reject_size`, `reject_form`, or `reject_both`"):
        check(clause in ins, "the instruction lost a clause the verifier enforces: %r" % clause)
    import importlib.util as _il2
    import tempfile as _tf
    _gs = _il2.spec_from_file_location("grade_form_preflight", "tests/grade_form.py")
    _g = _il2.module_from_spec(_gs)
    _gs.loader.exec_module(_g)
    _right = [(f, _g.S.truth(f)["form"], _g.S.truth(f)["verdict"]) for f in _g.IDS]

    def _took(fmt="%.2f", head="feature,form_um,verdict", tail="", nl="\n"):
        with _tf.TemporaryDirectory() as d:
            path = os.path.join(d, "form.csv")
            with open(path, "w", newline="") as fh:
                fh.write(nl.join([head] + ["%s,%s,%s%s" % (f, fmt % v, w, tail) for f, v, w in _right]) + nl)
            return bool(_g.score(path).get("accepted"))

    check(_took(), "the verifier refuses a correct sheet in the stated format")
    check(_took(nl="\r\n"), "the verifier refuses a correct sheet with CRLF line ends")
    check(not _took(fmt="%.1f"), "the verifier takes form_um to one decimal place")
    check(not _took(fmt="%.0f"), "the verifier takes form_um as whole numbers")
    check(not _took(fmt="%.3f"), "the verifier takes form_um to three decimal places")
    check(not _took(fmt="%.2e"), "the verifier takes form_um in exponent form")
    check(not _took(head="feature, form_um, verdict"), "the verifier takes a header with spaces in it")
    check(not _took(head=" feature,form_um,verdict"), "the verifier takes a header with a leading space")
    check(not _took(head="FEATURE,FORM_UM,VERDICT"), "the verifier takes a header in capitals")
    check(not _took(tail=" "), "the verifier takes a sentence with a trailing space")
    # the clause says two decimal places and nothing about a leading digit, so .50 is read, as 0.50
    with _tf.TemporaryDirectory() as d:
        path = os.path.join(d, "form.csv")
        with open(path, "w", newline="") as fh:
            fh.write("\n".join(["feature,form_um,verdict"] + [
                "%s,%s,%s" % (f, ".50" if i == 0 else "%.2f" % v, w) for i, (f, v, w) in enumerate(_right)]) + "\n")
        try:
            check(_g.read_sheet(path)[_g.IDS[0]][0] == 0.5, "the reader misreads .50")
        except Exception as ex:
            check(False, "the reader refuses .50, which is written to two decimal places: %s" % ex)
    reader = open("tests/grade_form.py").read().split("def read_sheet", 1)[1].split("\ndef ", 1)[0]
    check(".strip()" not in reader and "Decimal" not in reader,
          "read_sheet trims or coerces a field again; the contract is literal")

    # ---- no graded feature may be winnable without the work. A sheet that names one form figure and one
    # sentence for all 14 features is right about a feature when the figure is within the band of that
    # feature's form error and the sentence is that feature's. One such hit is unavoidable; two would mean a
    # pair of features sharing a sentence lie within twice the band of each other, and neither of them would be
    # discriminating. null_baselines.py sweeps the constants; this keeps the spacing that makes the sweep come
    # out at one.
    import importlib.util as _il
    _s = _il.spec_from_file_location("isim_preflight", "tests/sealed/isim.py")
    _m = _il.module_from_spec(_s)
    _s.loader.exec_module(_m)
    band = float(re.search(r"^TOL = ([\d.]+)", open("tests/grade_form.py").read(), re.M).group(1))
    tru = {f: _m.truth(f) for f in _m.ORDER}
    byv = {}
    for f in _m.ORDER:
        byv.setdefault(tru[f]["verdict"], []).append(f)
    for v, fs in sorted(byv.items()):
        for i, a in enumerate(fs):
            for b in fs[i + 1:]:
                gap = abs(tru[a]["form"] - tru[b]["form"])
                check(gap > 2.0 * band,
                      "%s and %s are both %s and only %.2f um apart, inside twice the band of %.2f"
                      % (a, b, v, gap, band))
    for f in _m.ORDER:
        check(abs(tru[f]["form_margin"]) > 2.0 * band,
              "%s sits %.2f um from its form tolerance, inside twice the band" % (f, tru[f]["form_margin"]))
    for p in visible:
        txt = open(p, encoding="ascii", errors="ignore").read().lower()
        check("error motion rides" not in txt and " 23 upr" not in txt and "29 upr" not in txt,
              "a document gives away the machine's error motion: %s" % p)

    # ---- task.toml, and the three explanations shared with the README
    t = tomllib.load(open("task.toml", "rb"))
    check(t["task"]["name"].endswith("/bore-form-acceptance"), "task name")
    check(t["artifacts"] == ["/app/output/form.csv"], "artifacts")
    check(t["agent"]["timeout_sec"] == 28800.0, "agent timeout must be 28800 s")
    check(t["agent"]["user"] == "agent", "the agent must not run as root")
    check(t["verifier"]["environment_mode"] == "separate", "the verifier must run in its own container")
    check(t["verifier.environment"]["network_mode"] if "verifier.environment" in t
          else t["verifier"]["environment"]["network_mode"] == "no-network", "the verifier must have no network")
    # The intake's structure check wants the full metadata block in task.toml: every key below, category fixed
    # at "Science", subcategory non-empty, and the three explanations present. A review once called five of
    # these "not recognised metadata" as an advisory, they were taken out on the strength of it, and the bundle
    # bounced at intake. The structure check is the authority; an advisory note is not. Do not remove keys.
    REQUIRED = ("author_name", "author_email", "author_organization", "author_profile", "research_advisor",
                "referred_by", "conflicts_of_interest", "domain", "field", "subfield", "category", "subcategory",
                "tags", "expert_time_estimate_hours", "relevant_experience", "difficulty_explanation",
                "solution_explanation", "verification_explanation")
    for k in REQUIRED:
        check(k in t["metadata"], "task.toml [metadata] is missing %s" % k)
    check(t["metadata"].get("category") == "Science", "[metadata] category must be Science on this dataset")
    check(bool(str(t["metadata"].get("subcategory", "")).strip()), "[metadata] subcategory is missing or empty")
    readme = open("README.md").read()
    for k in ("difficulty_explanation", "solution_explanation", "verification_explanation"):
        v = str(t["metadata"].get(k, "")).strip()
        check(len(v) > 400, "task.toml's %s is missing or too thin" % k)
        check(v in readme, "README and task.toml disagree on %s" % k)
    for head in ("## Difficulty", "## Reference solution", "## Verification"):
        check(head in readme, "the README lost its %s section" % head)

    print("%d checks" % PASSED[0])
    if FAILS:
        print("%d FAILED:" % len(FAILS))
        for m in FAILS:
            print("  FAIL  %s" % m)
        sys.exit(1)
    print("pre-flight clean: %d checks passed" % PASSED[0])


if __name__ == "__main__":
    main()
