#!/usr/bin/env python3
"""Every rule the bundle must meet, checked mechanically.

    python3 preflight.py

Exit status is 0 only when every check passes. Run it after any change, together with the evidence scripts.
"""
import filecmp
import hashlib
import json
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
TASK = "flare-load-study"
# the bundle is these seven entries. A hidden entry beside them is never packaged, so it is not bundle content.
OUTSIDE_PATHS = ("/home/", "/Users/", "/mnt/", "/tmp/")
DATA_MUST_NOT_SAY = ("sealed", "isim", "grader", "verifier", "synthetic", "authoring", "provenance")
GRADING_WORDS = ("grader", "verifier", "reward", "score", "scored", "pass", "fail", "tested", "graded",
                 "partial credit", "tolerance", "within", "per cent of the true")
LAST_PARA = ("You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints "
             "specific to this task.")
PINS = {"numpy": "2.1.3", "scipy": "1.14.1", "pandas": "2.2.3", "pytest": "8.4.1",
        "pytest-json-ctrf": "0.3.5"}
EVIDENCE = ("route_study", "method_spread", "independent", "null_baselines", "hedge_study",
            "verifier_checks", "reference_run", "seed_screen", "booking_study")

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
    top = {n for n in os.listdir(ROOT) if not n.startswith(".")}
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

    strays, links = [], []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for n in dirs + files:
            if os.path.islink(os.path.join(base, n)):
                links.append(os.path.relpath(os.path.join(base, n), ROOT))
        for n in files:
            fp = os.path.join(base, n)
            # the prefixes are looked for everywhere but in this file, which has to write them down to
            # look for them
            if os.path.abspath(fp) == os.path.abspath(__file__):
                continue
            for i, line in enumerate(text(fp).splitlines(), 1):
                if any(q in line for q in OUTSIDE_PATHS):
                    strays.append("%s:%d" % (os.path.relpath(fp, ROOT), i))
    check("no path from outside the bundle in any file", not strays, ", ".join(strays) or "none")
    check("no symbolic links in the bundle", not links, ", ".join(links) or "none")

    said = []
    for base, dirs, files in os.walk(os.path.join(ROOT, "environment", "data")):
        for n in files:
            fp = os.path.join(base, n)
            low = text(fp).lower()
            said += ["%s: %s" % (os.path.relpath(fp, ROOT), w) for w in DATA_MUST_NOT_SAY if w in low]
    check("the agent's records use no authoring vocabulary", not said, ", ".join(said) or "none")

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
    named = set(re.findall(r"/app/data/[\w/.-]+", ins))
    check("every path instruction.md names is a file that exists",
          not [p for p in named if not os.path.exists(p.replace("/app/data", data))],
          ", ".join(sorted(p for p in named if not os.path.exists(p.replace("/app/data", data)))) or "none")
    check("instruction.md names the output path and header",
          "/app/output/flare_load.csv" in ins
          and "contingency,devices,load_kg_per_h,header_inlet_barg" in ins)
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
    check("task.toml declares both artifacts", '/app/output/flare_load.csv' in toml
          and '/app/output/tip_sizing.csv' in toml)
    m = re.search(r'(?m)^name = "([^"]+)"', toml)
    parts = m.group(1).split("/") if m else []
    check("task.toml name is one prefix followed by this task's own name",
          len(parts) == 2 and parts[0] and parts[1] == TASK,
          ("<prefix>/%s" % parts[1]) if len(parts) == 2 else (m.group(1) if m else "absent"))
    # the prefix belongs to that name and nowhere else: anywhere else it is provenance, and a submission
    # carrying it is refused
    if len(parts) == 2:
        stray = []
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for n in files:
                fp = os.path.join(base, n)
                for i, line in enumerate(text(fp).splitlines(), 1):
                    if parts[0] not in line:
                        continue
                    if n == "task.toml" and line.strip().startswith("name ="):
                        continue
                    stray.append("%s:%d" % (os.path.relpath(fp, ROOT), i))
        check("the name's prefix appears nowhere but that one line", not stray, ", ".join(stray) or "none")
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
    check("the verifier image installs its stack", "pip install --no-cache-dir" in vdock)
    # the validator looks for this line verbatim: without it harbor has nowhere to upload the artifact
    check("the verifier image creates the artifact's parent directory",
          "RUN mkdir -p /app/output" in vdock)
    sh = text(os.path.join(ROOT, "tests", "test.sh"))
    zero = 'echo -n "0" > /logs/verifier/reward.txt'
    one = 'echo -n "1" > /logs/verifier/reward.txt'
    check("test.sh writes the reward to the one path the harness reads", zero in sh and one in sh)
    check("test.sh writes a zero reward before it grades anything",
          "python -m pytest" in sh and sh.index(zero) < sh.index("python -m pytest"))
    check("test.sh requires the report to hold exactly one passing test",
          all(k in sh for k in ('"tests": 1', '"passed": 1', '"failed": 0', '"skipped": 0')))
    check("test.sh writes a reward of one only on a clean run and a counted report",
          re.search(r'\[ "\$\w+" -eq 0 \] && \[ "\$\w+" -eq 0 \]', sh) is not None)
    # the locking step is found by what it does, not by what it is called
    locker = re.search(r"(?m)^(\w+)\(\)\s*\{[^}]*chmod 700 /logs/verifier", sh)
    after = sh[sh.index("python -m pytest"):sh.index(one)]
    check("test.sh re-locks the log directory after grading and before the reward is written",
          locker is not None and re.search(r"(?m)^\s*%s\b" % locker.group(1), after) is not None)
    check("test.sh clears the old reward after grading and before writing the new one",
          sh.index("python -m pytest") < sh.rindex("rm -f /logs/verifier/reward.txt") < sh.index(one))
    check("test.sh names the report it reads, and reads only that one",
          sh.count("/logs/verifier/ctrf.json") == 2)
    check("test.sh takes no path for the reward from outside",
          not re.search(r"reward\.txt[\"']?\s*=|\$\{?\w*REWARD", sh))

    # ---- the sealed definition
    a = os.path.join(PROV, "isim.py")
    b = os.path.join(ROOT, "tests", "sealed", "isim.py")
    check("the sealed definition is byte-identical in provenance and tests",
          read(a) == read(b), hashlib.sha256(read(a)).hexdigest()[:16])
    check("the seed is byte-identical in provenance and tests",
          read(os.path.join(PROV, "seed.json")) == read(os.path.join(ROOT, "tests", "sealed", "seed.json")))
    rig = os.path.join(ROOT, "environment", "rig")
    c = os.path.join(rig, "sealed", "isim.py")
    check("the sealed definition is byte-identical in the crew's copy too", read(a) == read(c),
          hashlib.sha256(read(c)).hexdigest()[:16])
    env_files = []
    for base, dirs, files in os.walk(os.path.join(ROOT, "environment")):
        env_files += [os.path.join(base, n) for n in files]
    # the crew's own directory is the one place in the agent's image the definition may sit, and the image
    # closes it to the agent; anywhere else it would be readable
    leaked = [os.path.relpath(p, ROOT) for p in env_files
              if (os.path.basename(p).startswith("isim") or b"TOL = " in read(p))
              and os.path.dirname(p) != os.path.join(rig, "sealed")]
    check("the sealed definition is nowhere in the agent's environment but the crew's own directory",
          not leaked, ", ".join(leaked) or "none")
    seed = json.loads(read(os.path.join(rig, "sealed", "seed.json")).decode())
    check("the crew's seed carries a seed of its own for the tests",
          "test_seed" in seed and seed["test_seed"] != seed.get("seed"), str(seed))

    # ---- the crew, as the agent's image installs it
    env_docker = text(os.path.join(ROOT, "environment", "Dockerfile"))
    lab = text(os.path.join(rig, "lab.py"))
    import isim as S_
    check("the standard sets the re-rating limit the design rules use",
          ("%.0f per cent" % (100.0 * S_.BACK_LIMIT)) in text(os.path.join(ROOT, "environment", "data", "docs", "standard.md")))
    check("the flare note lists the bores the sizing searches",
          all(("%.1f" % b) in text(os.path.join(ROOT, "environment", "data", "docs", "flare_system.md")) for b in S_.TIP_BORES))
    check("the image gives the crew a user of its own, with no shell",
          "useradd" in env_docker and "crew" in env_docker and "nologin" in env_docker)
    check("the image closes the crew's sealed definition and records to everyone else",
          "chmod 700 /opt/crew/sealed /opt/crew/state" in env_docker
          and "chmod 600 /opt/crew/sealed/*" in env_docker)
    check("the agent may run one program as the crew, with no environment carried across",
          "agent ALL=(crew) NOPASSWD: /opt/crew/lab.py" in env_docker
          and "env_reset" in env_docker and "visudo -cf" in env_docker)
    check("the only way in is the fieldtest wrapper",
          "/usr/local/bin/fieldtest" in env_docker and 'lab.py fieldtest "$@"' in env_docker)
    check("the crew writes where the agent can read and the agent cannot write",
          "install -d -o crew -g crew -m 755 /app/field_reports" in env_docker)
    check("the crew charges the booking before it runs a test",
          lab.index("O_EXCL") < lab.index("run_test"))
    check("the crew refuses a test it has already run", "a second order for it" in lab)
    check("the crew will not start if its directories are not as installed",
          "as_installed(SEALED)" in lab and "as_installed(STATE)" in lab)
    check("the crew's records cannot be a link", "O_NOFOLLOW" in lab)
    check("instruction.md states the booking the crew's document gives",
          ("booking is two tests" in ins) and S_.BUDGET == 2)
    check("instruction.md names where the crew reports", "/app/field_reports" in ins)
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
    import grade_flare
    import solve
    os.environ["DATA_DIR"] = os.path.join(ROOT, "environment", "data")
    import common
    m = solve.Study(solve.load(os.environ["DATA_DIR"]), common.crew_reports(S))
    tmp = tempfile.mkdtemp(prefix="fl_ref_")
    ref = os.path.join(tmp, "flare_load.csv")
    try:
        with open(ref, "w") as f:
            f.write("contingency,devices,load_kg_per_h,header_inlet_barg\n")
            for name, devices, total, back in m.sheet():
                f.write("%s,%s,%.1f,%.4f\n" % (name, ";".join(devices), total, back))
        bore, who, share, _w = m.sizing()
        size_ref = os.path.join(tmp, "tip_sizing.csv")
        with open(size_ref, "w") as f:
            f.write("tip_bore_mm,binding_device,back_pressure_pct\n%.1f,%s,%.3f\n"
                    % (bore, who, 100.0 * share))
        r = grade_flare.assess(ref, size_ref)
        check("the grader takes the reference solution", r.taken, "%d of %d" % (r.standing, r.total))
        worst = max([max(abs(v["margins"]["load"]), abs(v["margins"]["back"])) for v in r.rows.values()]
                    + [abs(r.sizing["margins"]["share"])])
        check("the reference sits well inside the band", worst <= 0.5 * S.TOL,
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
        check("every part is failed by at least three routes",
              "parts failed by fewer than 3 routes: none" in t)
        check("the coupling cannot be skipped",
              "the system never brought together, rates at no back pressure" in t)
        check("the bonnet column cannot be ignored", "every device taken as conventional" in t)
    ms = os.path.join(EV, "method_spread.txt")
    if os.path.exists(ms):
        check("every sound method gets all seven", "methods that miss a contingency: none" in text(ms))
    bs = os.path.join(EV, "booking_study.txt")
    if os.path.exists(bs):
        t = text(bs)
        check("only the two tests that reach a row are worth ordering",
              "tests worth ordering: `tip-backpressure`, `pump-shutoff`" in t)
        check("only one way of spending the booking gets every row",
              "bookings that get all 7: tip-backpressure, pump-shutoff" in t
              and "nothing ordered: 1 of 7" in t)
    ind = os.path.join(EV, "independent.txt")
    if os.path.exists(ind):
        t = text(ind)
        check("the second study agrees on the shipped records", "7 of 7 parts agree" in t)
        check("the second study agrees on every laboratory seed",
              "worst agreement over 20 laboratory seeds: 7 of 7" in t)

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
