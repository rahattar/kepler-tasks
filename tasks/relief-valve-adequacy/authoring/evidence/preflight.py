#!/usr/bin/env python3
"""Every rule the bundle must meet, checked mechanically.

    python3 preflight.py

Exit status is 0 only when every check passes. Run it after any change, together with the evidence scripts.
"""
import filecmp
import hashlib
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True          # so this run cannot create the caches it is about to look for
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
EV = os.path.join(ROOT, "authoring", "evidence")
PROV = os.path.join(ROOT, "authoring", "provenance")
sys.path.insert(0, PROV)
sys.path.insert(0, os.path.join(ROOT, "solution"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

TOP = {"README.md", "instruction.md", "task.toml", "authoring", "environment", "solution", "tests"}
# .source_zip records which zip this directory was unpacked from. It is the repository's marker, not bundle
# content: the zip is built from the seven entries above by name, so it is never in the delivered bundle.
REPO_ONLY = {".source_zip"}
GRADING_WORDS = ("grader", "verifier", "reward", "score", "scored", "pass", "fail", "tested", "graded",
                 "partial credit", "tolerance", "within", "per cent of the true")
LAST_PARA = ("You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints "
             "specific to this task.")
PINS = {"numpy": "2.1.3", "scipy": "1.14.1", "pandas": "2.2.3", "pytest": "8.4.1",
        "pytest-json-ctrf": "0.3.5"}
EVIDENCE = ("route_study", "method_spread", "independent", "null_baselines", "hedge_study",
            "verifier_checks", "reference_run", "seed_screen")

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))


def read(path):
    with open(path, "rb") as f:
        return f.read()


def text(path):
    return read(path).decode("utf-8", "replace")


def main():
    # ---- bundle shape
    top = set(os.listdir(ROOT)) - REPO_ONLY
    check("the bundle holds exactly the seven required entries", top == TOP,
          "extra: %s; missing: %s" % (sorted(top - TOP) or "none", sorted(TOP - top) or "none"))

    # no caches or compiled modules: a .pyc of the sealed definition would carry it into the bundle
    caches = []
    for base, dirs, files in os.walk(ROOT):
        for n in dirs:
            if n == "__pycache__":
                caches.append(os.path.relpath(os.path.join(base, n), ROOT))
        for n in files:
            if n.endswith((".pyc", ".pyo")):
                caches.append(os.path.relpath(os.path.join(base, n), ROOT))
    check("no bytecode caches anywhere in the bundle", not caches, ", ".join(caches) or "none")

    bad_names, non_ascii, encoded = [], [], []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for n in dirs + files:
            if n in ("README.md", "Dockerfile"):
                continue
            if n.upper() == n and re.search(r"[A-Z]", n):
                bad_names.append(os.path.relpath(os.path.join(base, n), ROOT))
        for n in files:
            p = os.path.join(base, n)
            raw = read(p)
            try:
                raw.decode("ascii")
            except UnicodeDecodeError:
                non_ascii.append(os.path.relpath(p, ROOT))
            if n.endswith((".py", ".md", ".sh", ".toml", ".csv", ".json")):
                t = raw.decode("utf-8", "replace")
                for m in re.finditer(r"[A-Za-z0-9+/]{32,}={0,2}", t):
                    s = m.group(0)
                    if re.search(r"[A-Z]", s) and re.search(r"[a-z]", s) and re.search(r"\d", s):
                        encoded.append("%s: %s" % (os.path.relpath(p, ROOT), s[:24]))
                # the names of the decoders are looked for everywhere but in this file, which has to
                # name them to look for them
                if os.path.abspath(p) != os.path.abspath(__file__):
                    for needle in ("b64decode", "rot13", "codecs.decode", "base64"):
                        if needle in t:
                            encoded.append("%s: %s" % (os.path.relpath(p, ROOT), needle))
    check("no all-uppercase file or folder names", not bad_names, ", ".join(bad_names) or "none")
    check("every file is ASCII", not non_ascii, ", ".join(non_ascii) or "none")
    check("nothing encoded or obfuscated anywhere", not encoded, "; ".join(encoded) or "none")

    # ---- instruction.md
    ins = text(os.path.join(ROOT, "instruction.md"))
    check("instruction.md has no heading", not re.search(r"(?m)^\s*#", ins))
    found = [w for w in GRADING_WORDS if re.search(r"\b%s\b" % re.escape(w), ins, re.I)]
    check("instruction.md uses no grading words", not found, ", ".join(found) or "none")
    paras = [p.strip() for p in ins.strip().split("\n\n") if p.strip()]
    check("instruction.md ends with the required paragraph",
          paras and " ".join(paras[-1].split()) == LAST_PARA, repr(paras[-1][:60]) if paras else "empty")
    data = os.path.join(ROOT, "environment", "data")
    inputs = []
    for base, dirs, files in os.walk(data):
        for n in files:
            inputs.append("/app/data/" + os.path.relpath(os.path.join(base, n), data))
    missing = [p for p in inputs if p not in ins]
    check("instruction.md names every input file by absolute path", not missing,
          ", ".join(sorted(missing)) or "none")
    check("instruction.md names the output path and header",
          "/app/output/relief.csv" in ins and "valve,governing_case,required_area_mm2,verdict" in ins)
    import isim as S
    check("instruction.md does not print the accuracy band",
          not re.search(r"\b1\s*(per cent|%)", ins) and ("%.2f" % S.TOL) not in ins
          and ("%g" % S.TOL) not in ins)

    # ---- task.toml and README.md
    toml = text(os.path.join(ROOT, "task.toml"))
    readme = text(os.path.join(ROOT, "README.md"))
    for key, want in (("timeout_sec", "28800"), ("user", "agent")):
        check("task.toml sets %s" % key, re.search(r"%s\s*=\s*\"?%s" % (key, want), toml) is not None)
    check("task.toml gives the verifier 600 s in a separate environment with no network",
          'timeout_sec = 600.0' in toml and 'environment_mode = "separate"' in toml
          and 'network_mode = "no-network"' in toml)
    check("task.toml declares the domain and field",
          'domain = "engineering-sciences"' in toml and 'field = "mechanical-engineering"' in toml)
    check("task.toml declares the artifact", '/app/output/relief.csv' in toml)
    m = re.search(r'(?m)^name = "([^"]+)"', toml)
    check("task.toml name carries the prefix used so far", m and m.group(1).startswith("afterquery/"),
          m.group(1) if m else "absent")
    expl = {}
    for field in ("difficulty_explanation", "solution_explanation", "verification_explanation"):
        mm = re.search(r'%s = """(.*?)"""' % field, toml, re.S)
        expl[field] = mm.group(1) if mm else ""
        check("task.toml carries %s" % field, bool(expl[field]))
    check("the difficulty explanation says the data is synthetic and realistic",
          "synthetic" in expl["difficulty_explanation"] and "realistic" in expl["difficulty_explanation"])
    check("the difficulty explanation names who does the work",
          re.search(r"engineer", expl["difficulty_explanation"], re.I) is not None)
    check("the difficulty explanation names the research analogue",
          "research analogue" in expl["difficulty_explanation"])
    nums = re.findall(r"\b\d+ of \d+ (?:runs|trials|attempts)\b", expl["difficulty_explanation"])
    check("the difficulty explanation carries no agent-performance numbers", not nums, ", ".join(nums))
    for head, field in (("## Difficulty", "difficulty_explanation"),
                        ("## Reference solution", "solution_explanation"),
                        ("## Verification", "verification_explanation")):
        i = readme.find(head)
        check("README.md carries %s" % head, i >= 0)
        if i >= 0:
            body = readme[i + len(head):]
            nxt = body.find("\n## ")
            body = body[:nxt] if nxt >= 0 else body
            check("README.md %s matches task.toml" % head,
                  " ".join(body.split()) == " ".join(expl[field].split()))

    # ---- the verifier
    vdock = text(os.path.join(ROOT, "tests", "Dockerfile"))
    for pkg, ver in PINS.items():
        check("the verifier pins %s %s" % (pkg, ver), "%s==%s" % (pkg, ver) in vdock)
    check("the verifier image has no network use", "pip install" in vdock)
    sh = text(os.path.join(ROOT, "tests", "test.sh"))
    check("test.sh writes 0 before grading", re.search(r'echo -n "0" > /logs/verifier/reward.txt', sh) is not None)
    check("test.sh writes 1 only on a clean pytest run and one passing test",
          'if [ "$RC" -eq 0 ] && [ "$COUNTS_OK" = "yes" ]' in sh
          and 's.get("tests") == 1 and s.get("passed") == 1' in sh)
    check("test.sh locks the log directory before writing the reward",
          sh.index("chmod 700 /logs/verifier") < sh.index('echo -n "1"'))

    # ---- the sealed definition
    a = os.path.join(PROV, "isim.py")
    b = os.path.join(ROOT, "tests", "sealed", "isim.py")
    check("the sealed definition is byte-identical in provenance and tests",
          read(a) == read(b), hashlib.sha256(read(a)).hexdigest()[:16])
    check("the seed is byte-identical in provenance and tests",
          read(os.path.join(PROV, "seed.json")) == read(os.path.join(ROOT, "tests", "sealed", "seed.json")))
    env_files = []
    for base, dirs, files in os.walk(os.path.join(ROOT, "environment")):
        env_files += [os.path.join(base, n) for n in files]
    leaked = [os.path.relpath(p, ROOT) for p in env_files
              if "isim" in os.path.basename(p) or b"TOL = " in read(p)]
    check("the sealed definition is nowhere in the agent's environment", not leaked,
          ", ".join(leaked) or "none")
    cmp_ = filecmp.dircmp(os.path.join(ROOT, "environment", "data"),
                          os.path.join(ROOT, "tests", "app_data"))

    def diff(c):
        out = list(c.left_only) + list(c.right_only) + list(c.diff_files)
        for s in c.subdirs.values():
            out += diff(s)
        return out
    check("tests/app_data is the agent's data exactly", not diff(cmp_), ", ".join(diff(cmp_)) or "none")

    # ---- the records reproduce from the generator
    import importlib
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="rv_pf_")
    try:
        os.environ["GEN_QUIET"] = "1"
        gen = importlib.import_module("gen")
        out = os.path.join(tmp, "data")
        os.makedirs(os.path.join(out, "docs"))
        gen.main(out)
        c2 = filecmp.dircmp(os.path.join(ROOT, "environment", "data"), out)
        check("the generator reproduces the shipped records from the seed", not diff(c2),
              ", ".join(diff(c2)) or "none")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- the reference is accepted
    import grade_relief
    import solve
    os.environ["DATA_DIR"] = os.path.join(ROOT, "environment", "data")
    m = solve.Model(solve.load(os.environ["DATA_DIR"]))
    tmp = tempfile.mkdtemp(prefix="rv_ref_")
    ref = os.path.join(tmp, "relief.csv")
    try:
        with open(ref, "w") as f:
            f.write("valve,governing_case,required_area_mm2,verdict\n")
            for vid, case, need, verd in m.sheet():
                f.write("%s,%s,%.4f,%s\n" % (vid, case, need, verd))
        r = grade_relief.score(ref)
        check("the grader accepts the reference solution", r.get("accepted"),
              "%d of %d" % (r.get("npass", 0), r.get("gate", 0)))
        worst = max(abs(v["margins"]["area"]) for v in r["valves"].values())
        check("the reference sits well inside the area band", worst <= 0.5 * S.TOL,
              "worst %.4f against %.4f" % (worst, S.TOL))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- the design rules and the evidence
    rc = subprocess.run([sys.executable, os.path.join(PROV, "tune.py")], capture_output=True, text=True)
    check("the design rules hold (tune.py)", rc.returncode == 0, rc.stdout.strip().splitlines()[-1:][0]
          if rc.stdout.strip() else "")
    for name in EVIDENCE:
        p = os.path.join(EV, name + ".txt")
        check("authoring/evidence/%s.txt is present" % name, os.path.exists(p))
    vc = os.path.join(EV, "verifier_checks.txt")
    if os.path.exists(vc):
        check("verifier_checks.txt reports no unexpected case",
              not re.search(r"(?m)^UNEXPECTED", text(vc))
              and re.search(r"(?m)^\d+ cases, 0 UNEXPECTED", text(vc)) is not None)
    rs = os.path.join(EV, "route_study.txt")
    if os.path.exists(rs):
        t = text(rs)
        check("every defective route fails on the shipped records",
              "routes that pass on the shipped records: none" in t)
        check("every valve is failed by at least three routes",
              "valves failed by fewer than 3 routes: none" in t)
    ms = os.path.join(EV, "method_spread.txt")
    if os.path.exists(ms):
        check("every sound method gets all nine", "methods that do not get all nine: none" in text(ms))
    ind = os.path.join(EV, "independent.txt")
    if os.path.exists(ind):
        t = text(ind)
        check("the independent assessment gets all nine on the shipped records",
              "9 of 9 right on the shipped records" in t)
        check("the independent assessment gets all nine on every laboratory seed",
              "all nine right on 20 of 20 laboratory seeds" in t)

    # ---- report
    width = max(len(n) for n, _, _ in results)
    nfail = 0
    for name, ok, detail in results:
        if not ok:
            nfail += 1
        print("%s %-*s %s" % ("pass" if ok else "FAIL", width, name, detail))
    print("\n%d checks, %d failed" % (len(results), nfail))
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
