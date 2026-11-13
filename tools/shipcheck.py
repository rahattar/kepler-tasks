"""Check a bundle zip the way intake will meet it, before it goes to Alex.

    python3 tools/shipcheck.py <bundle.zip> [<previous.zip>]

It unzips into a scratch directory and works only on what is in the zip:
  1. the files at the root are the bundle's and nothing else, with no caches or dotfiles anywhere;
  2. task.toml has the same sections, keys and value types as a task that has passed intake
     (tasks/cooler-fouling-assessment), category "Science", a subcategory, the three explanations,
     the 28800 s agent timeout, and the instruction closes with the required sentence;
  3. the task's own preflight passes when run inside the unzipped tree;
  4. the literals intake's structure check reads as text, and the verifier timeout; 4b. the limits on the live
     spec page (compose, cheat/, marker word, platform pins, unpinned installs, timeouts, network modes, sizes,
     instruction ending, headings and grading words);
  5. hygiene the reviews have refused: encoded strings or decoder calls in code, non-ASCII text, all-uppercase
     names, evidence that reports a failure, and evidence older than the code it describes;
  6. every agent-visible document is named in the instruction by its absolute path;
  7. if a previous zip is given, which files differ from it.
Every rule here has bounced a bundle or is stated on the live spec page. Add to it whenever intake teaches a new one.
"""
import ast
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PASSED = os.path.join(HERE, "..", "tasks", "cooler-fouling-assessment", "task.toml")
ROOT = {"README.md", "instruction.md", "task.toml", "authoring", "environment", "solution", "tests"}
CLOSE = ("You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints "
         "specific to this task.")
bad = []


def chk(c, msg):
    print("  %s %s" % ("ok  " if c else "FAIL", msg))
    if not c:
        bad.append(msg)


def unzip(path):
    # into a folder named after the task: several preflights check that the bundle folder carries the task's name
    task = re.sub(r"-\d{8}[a-z]?$", "", os.path.basename(path)[:-len(".zip")])
    d = os.path.join(tempfile.mkdtemp(prefix="shipcheck-"), task)
    os.makedirs(d)
    with zipfile.ZipFile(path) as z:
        z.extractall(d)
        for i in z.infolist():                          # extractall drops the mode bits; the exec bit matters
            mode = (i.external_attr >> 16) & 0o777
            if mode:
                os.chmod(os.path.join(d, i.filename), mode)
    return d


z = sys.argv[1]
d = unzip(z)
names = zipfile.ZipFile(z).namelist()
print("%s\n\n1. contents" % os.path.basename(z))
chk(set(os.listdir(d)) == ROOT, "root holds exactly %s" % ", ".join(sorted(ROOT)))
junk = [n for n in names if "__pycache__" in n or n.endswith(".pyc") or any(p.startswith(".") for p in n.split("/"))]
chk(not junk, "no caches or dotfiles%s" % ("" if not junk else ": %s" % junk[:3]))

chk(not [n for n in names if n.lower().endswith(".zip")], "no zip inside the bundle")
# The programme's name is allowed in one place, task.toml's own name field, and nowhere else in a bundle. It is
# read from that field here rather than written down, so this file never has to spell it.
name = tomllib.load(open(os.path.join(d, "task.toml"), "rb")).get("task", {}).get("name", "")
parts = name.split("/")
chk(len(parts) == 2 and all(parts), "task name has the shape <prefix>/<task-name>")
if len(parts) == 2 and parts[0]:
    hits = []
    for base, _, fs in os.walk(d):
        for f in fs:
            path = os.path.join(base, f)
            try:
                lines = open(path, errors="replace").read().splitlines()
            except OSError:
                continue
            for k, line in enumerate(lines, 1):
                if parts[0].lower() in line.lower() and not (f == "task.toml" and line.strip().startswith("name =")):
                    hits.append("%s:%d" % (os.path.relpath(path, d), k))
    chk(not hits, "the name's prefix appears nowhere but task.toml's name field%s" % ("" if not hits else ": %s" % hits[:4]))

print("\n2. task.toml against a task that passed intake")
a = tomllib.load(open(os.path.join(d, "task.toml"), "rb"))
b = tomllib.load(open(PASSED, "rb"))
chk(list(a) == list(b), "same sections in the same order")
for sec in b:
    if isinstance(b[sec], dict):
        diff = set(a.get(sec, {})) ^ set(b[sec])
        chk(not diff, "[%s] same keys%s" % (sec, "" if not diff else " - differs: %s" % sorted(diff)))
        for k in b[sec]:
            if k in a.get(sec, {}) and type(a[sec][k]) is not type(b[sec][k]):
                chk(False, "[%s] %s has type %s, the passing task has %s"
                    % (sec, k, type(a[sec][k]).__name__, type(b[sec][k]).__name__))
m = a.get("metadata", {})
chk(m.get("category") == "Science", 'category is "Science"')
chk(bool(str(m.get("subcategory", "")).strip()), "subcategory is not empty")
readme = open(os.path.join(d, "README.md")).read()
for k in ("difficulty_explanation", "solution_explanation", "verification_explanation"):
    v = str(m.get(k, "")).strip()
    chk(len(v) > 400 and v in readme, "%s present and word for word in the README" % k)
chk(a.get("agent", {}).get("timeout_sec") == 28800.0, "agent timeout_sec is 28800.0")
chk(open(os.path.join(d, "instruction.md")).read().rstrip().endswith(CLOSE), "instruction closes with the required sentence")

print("\n3. the task's own preflight, inside the unzipped bundle")
p = subprocess.run([sys.executable, "-B", "authoring/evidence/preflight.py"], cwd=d, capture_output=True, text=True,
                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
last = (p.stdout.strip().splitlines() or ["no output"])[-1]
chk(p.returncode == 0 and ("clean" in last or re.search(r"\b0 failed\b", last)), last)

task = parts[-1] if parts else ""
print("\n4. literals the structure check reads as text")
tdock = open(os.path.join(d, "tests", "Dockerfile")).read()
tsh = open(os.path.join(d, "tests", "test.sh")).read()
dock_lines = [ln.strip() for ln in tdock.splitlines()]
for art in a.get("artifacts", []):
    parent = os.path.dirname(art)
    # artifact-parent-not-created: a line of its own, not folded into a combined RUN
    chk("RUN mkdir -p %s" % parent in dock_lines, "tests/Dockerfile has `RUN mkdir -p %s` on a line of its own" % parent)
for v in ("0", "1"):
    # reward-txt-missing: the path written out, not built from shell variables
    chk('echo -n "%s" > /logs/verifier/reward.txt' % v in tsh, 'tests/test.sh writes `echo -n "%s" > /logs/verifier/reward.txt`' % v)
# reward-not-literal (shaft-alignment-moves 20261111): every write site is read as text and must be the literal
# write on a line of its own; a write inside a case arm (`0:0) echo -n "1" > ...`) is refused
sites = [ln.strip() for ln in tsh.splitlines() if "reward.txt" in ln and re.search(r"\b(echo|printf)\b|>", ln)
         and not ln.strip().startswith(("#", "rm "))]
chk(sites and all(ln in ('echo -n "0" > /logs/verifier/reward.txt', 'echo -n "1" > /logs/verifier/reward.txt') for ln in sites),
    "every reward write in tests/test.sh is the literal write on a line of its own%s"
    % ("" if all(ln in ('echo -n "0" > /logs/verifier/reward.txt', 'echo -n "1" > /logs/verifier/reward.txt') for ln in sites) else ": %s" % sites[:3]))
pins = tdock + "".join(open(os.path.join(dp, f)).read() for dp, _, fs in os.walk(os.path.join(d, "tests"))
                       for f in fs if f == "requirements.txt")
# pytest and the ctrf plugin are always needed; the libraries only if installed, and then at the standard version
for pkg, ver in (("pytest", "8.4.1"), ("pytest-json-ctrf", "0.3.5")):
    chk("%s==%s" % (pkg, ver) in pins, "verifier pins %s==%s" % (pkg, ver))
for pkg, ver in (("numpy", "2.1.3"), ("scipy", "1.14.1"), ("pandas", "2.2.3")):
    if re.search(r"(?<![\w-])%s\b" % pkg, pins):
        chk("%s==%s" % (pkg, ver) in pins, "verifier pins %s==%s" % (pkg, ver))
chk(a.get("verifier", {}).get("timeout_sec") == 600.0, "verifier timeout_sec is 600.0")

print("\n4b. limits from the live spec page (digest: project doc claude/kepler-spec.md)")
names_l = [n.rstrip("/") for n in names]
chk(not [n for n in names_l if re.search(r"(^|/)(docker-)?compose\.ya?ml$", n)], "no compose file (compose-not-supported)")
chk(not [n for n in names_l if n == "cheat" or n.startswith("cheat/") or "/cheat/" in n], "no cheat/ folder")
marker = "can" + "ary"                                  # the eval-set marker word, matched literally anywhere
hit = [n for n in names_l if not n.endswith("/") and os.path.isfile(os.path.join(d, n))
       and marker in open(os.path.join(d, n), errors="ignore").read().lower()]
chk(not hit, "the eval-set marker word appears nowhere%s" % ("" if not hit else ": %s" % hit[:4]))
dockers = [n for n in names_l if os.path.basename(n) == "Dockerfile"]
plat = [n for n in dockers if re.search(r"^\s*FROM\s+--platform", open(os.path.join(d, n)).read(), re.M | re.I)]
chk(not plat, "no FROM --platform pin%s" % ("" if not plat else ": %s" % plat))
edock = [ln.strip() for ln in open(os.path.join(d, "environment", "Dockerfile")).read().splitlines()
         if ln.strip() and not ln.strip().startswith("#")]
chk(not (edock and edock[-1].upper().startswith("USER ")), "environment/Dockerfile ends as root (no final USER line)")
unpinned = []
for n in dockers:
    txt = re.sub(r"\\\n", " ", open(os.path.join(d, n)).read())
    for ln in txt.splitlines():
        m_ = re.search(r"\b(?:pip3?|uv pip)\s+install\b(.*)", ln)
        if m_:
            for tok in m_.group(1).split("&&")[0].split():
                if not tok.startswith("-") and "==" not in tok and not tok.startswith(("/", ".")) and tok != "install":
                    unpinned.append("%s: %s" % (n, tok))
        if re.search(r"apt-get\s+install", ln) and re.search(r"\s[\w.+-]+=\S", ln.split("apt-get")[-1]):
            unpinned.append("%s: apt version pin" % n)
chk(not unpinned, "every pip install pinned with ==, no apt pins%s" % ("" if not unpinned else ": %s" % unpinned[:4]))
ag, ve, en = a.get("agent", {}), a.get("verifier", {}), a.get("environment", {})
chk(9000 <= ag.get("timeout_sec", 0) <= 28800, "agent timeout within 9000-28800")
chk(ve.get("timeout_sec", 0) <= 13500, "verifier timeout at most 13500")
chk(ve.get("environment_mode") == "separate", 'verifier environment_mode = "separate"')
chk(en.get("network_mode", "public") == "public", 'environment network_mode = "public"')
chk(ve.get("environment", {}).get("network_mode") == "no-network", 'verifier.environment network_mode = "no-network"')
chk("allow_internet" not in open(os.path.join(d, "task.toml")).read(), "no deprecated allow_internet key")
chk(en.get("cpus", 1) in (1, 2, 4, 8, 16) and en.get("memory_mb", 1024) in (1024, 2048, 4096, 8192, 16384)
    and en.get("storage_mb", 0) <= 40960, "cpus, memory_mb and storage_mb inside the allowed sets")
chk(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+){0,2}", task or "") is not None, "task name lowercase kebab-case")
kw, tags = a.get("task", {}).get("keywords"), m.get("tags")
if kw is not None:
    chk(kw == tags, "[task].keywords identical to [metadata].tags")
coi = str(m.get("conflicts_of_interest", "")).strip()
chk(coi and not re.search(r"TODO|TBD|placeholder|xxx|<", coi, re.I), "conflicts_of_interest filled in")
ins_raw = open(os.path.join(d, "instruction.md")).read()
n_sec = int(ag.get("timeout_sec", 0))
chk(re.search(r"\n\n" + re.escape(CLOSE.replace("28800", str(n_sec))) + r"\n?$", ins_raw) is not None,
    "instruction ends with a blank line, the closing sentence, at most one newline")
chk(not re.search(r"^\s{0,3}#", ins_raw, re.M), "instruction has no Markdown heading")
# instruction clarity (shaft-alignment-moves 20261111b): "You are the ... engineer" is roleplay, not contract
chk(not re.search(r"\b(you are|as an? [a-z ]*engineer|imagine|pretend)\b", ins_raw.replace(CLOSE, ""), re.I),
    "instruction assigns no role")
gw = re.findall(r"\b(grader|graded|grading|verifier|reward|score[sd]?|scoring|partial credit|tested|pass(?:es|ed)?|fail(?:s|ed)?)\b",
                ins_raw.replace(CLOSE, ""), re.I)
chk(not gw, "instruction has no grading words%s" % ("" if not gw else ": %s" % sorted(set(w.lower() for w in gw))))

print("\n5. hygiene the reviews have refused")
# Security review, impeller-shrink-fits 20261109b: strings held encoded, decoded at run time, are obfuscation even
# when what they hide is harmless. Look for the code doing it, not for the words: a preflight may list the names
# of decoders as plain strings in order to forbid them, and that is allowed.
DECODE_MODULES = {"base64", "binascii", "codecs", "zlib", "marshal", "bz2", "lzma"}
DECODE_CALLS = {"b64decode", "b32decode", "b16decode", "a85decode", "b85decode", "urlsafe_b64decode", "unhexlify",
                "a2b_base64", "a2b_hex", "fromhex", "decompress"}
enc, dyn = [], []
for base, _, fs in os.walk(d):
    for f in fs:
        if not f.endswith(".py"):
            continue
        path = os.path.join(base, f); rel = os.path.relpath(path, d)
        try:
            tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
        except SyntaxError:
            enc.append(rel + " (does not parse)"); continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                if any(m.split(".")[0] in DECODE_MODULES for m in mods):
                    enc.append("%s:%d import" % (rel, node.lineno))
            elif isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
                if name in DECODE_CALLS:
                    enc.append("%s:%d %s()" % (rel, node.lineno, name))
                if name == "decode" and any(isinstance(x, ast.Constant) and str(x.value).lower().startswith("rot")
                                            for x in node.args):
                    enc.append("%s:%d decode(rot)" % (rel, node.lineno))
                if name in ("exec", "eval", "__import__"):
                    dyn.append("%s:%d %s()" % (rel, node.lineno, name))
chk(not enc, "no encoding or decoding in code%s" % ("" if not enc else ": %s" % enc[:4]))
if dyn:
    # not seen refused yet; reported so that it is a decision rather than an accident
    print("  note dynamic execution, refused by no review so far but close to what security reviews look for: %s" % dyn[:4])
nonascii, upper = [], []
for base, dirs, fs in os.walk(d):
    for n in dirs + fs:
        stem = n.split(".")[0]
        if n not in ("README.md", "Dockerfile") and stem.isupper() and any(c.isalpha() for c in stem):
            upper.append(os.path.relpath(os.path.join(base, n), d))
    for f in fs:
        path = os.path.join(base, f)
        raw = open(path, "rb").read()
        if b"\0" in raw[:4096]:
            continue                                    # binary
        try:
            raw.decode("ascii")
        except UnicodeDecodeError:
            nonascii.append(os.path.relpath(path, d))
chk(not nonascii, "every text file is ASCII%s" % ("" if not nonascii else ": %s" % nonascii[:4]))
chk(not upper, "no all-uppercase file or folder names%s" % ("" if not upper else ": %s" % upper[:4]))
chk(0 < len(task.split("-")) <= 3, "the task name has at most three hyphenated words")
# Verification-explanation review, impeller-shrink-fits 20261109b: a committed study showing UNEXPECTED next to a
# README claiming the opposite. And the same review class on bore-form: a committed figure from an older round.
ev = os.path.join(d, "authoring", "evidence")
failing, stale = [], []
info = {i.filename: datetime(*i.date_time).timestamp() for i in zipfile.ZipFile(z).infolist()}
code = [t for n, t in info.items() if n.endswith(".py") and n.startswith(("authoring/provenance/", "solution/", "tests/"))]
newest = max(code) if code else 0
for f in sorted(os.listdir(ev)) if os.path.isdir(ev) else []:
    if f.endswith(".txt"):
        t = open(os.path.join(ev, f), errors="replace").read()
        unexpected = [m for m in re.findall(r"(\d+)?\s*UNEXPECTED", t) if m != "0"]   # "0 UNEXPECTED" is a pass
        if unexpected or re.search(r"Traceback \(most recent call last\)|\bPROBLEM", t):
            failing.append(f)
        # zip times are the working tree's modification times; a study last written well before the newest change
        # to the definition, the solution or the verifier has not been re-run since that change
        if info.get("authoring/evidence/" + f, newest) < newest - 120:
            stale.append(f)
chk(not failing, "no committed study reports a failure%s" % ("" if not failing else ": %s" % failing))
# Structure rejection, lube-oil-survey 20261113: [metadata] subfield over 120 characters.
import tomllib as _toml
_sub = _toml.load(open(os.path.join(d, "task.toml"), "rb")).get("metadata", {}).get("subfield", "")
chk(0 < len(_sub) <= 120, "[metadata] subfield is at most 120 characters (%d)" % len(_sub))
# Oracle failure, journal-bearing-survey 20261113: the verifier ran the program as another user, and test.sh's
# umask 077 made the scratch package unreadable to it. Every local run had called pytest directly, under the
# shell's umask. Where a verifier changes user, a committed study has to run tests/test.sh itself.
changes_user = [f for f in os.listdir(os.path.join(d, "tests")) if f.endswith(".py")
                and re.search(r"setpriv|os\.setuid|setresuid", open(os.path.join(d, "tests", f)).read())]
if changes_user:
    ran = [f for f in sorted(os.listdir(ev)) if f.endswith(".txt")
           and re.search(r"bash tests/test\.sh", open(os.path.join(ev, f), errors="replace").read())
           and re.search(r"reward 1\b", open(os.path.join(ev, f), errors="replace").read())] if os.path.isdir(ev) else []
    chk(bool(ran), "the verifier changes user (%s), and a committed study runs tests/test.sh itself to reward 1%s"
        % (", ".join(changes_user), "" if ran else ": none does"))
chk(not stale, "no committed study is older than the code it describes%s" % ("" if not stale else ": %s" % stale[:6]))

print("\n6. the instruction names every agent-visible document by its absolute path")
ins = open(os.path.join(d, "instruction.md")).read()
missing = []
data = os.path.join(d, "environment", "data")
for base, dirs, fs in os.walk(data):
    rel = os.path.relpath(base, data)
    depth = 0 if rel == "." else rel.count(os.sep) + 1
    if depth > 1:
        continue
    for f in fs:
        if f.endswith((".csv", ".md", ".json", ".txt")):
            p = "/app/data/" + (f if rel == "." else rel + "/" + f)
            if p not in ins and ("/app/data/" + rel) not in ins:
                missing.append(p)
if missing and re.search(r"/app/data/?(?![\w.-])", ins):
    # cooler-fouling 20261108 named only the folder and still reached the easiness screen; the playbook asks for
    # every file, so this is reported, not failed
    print("  note the instruction names /app/data but not: %s" % missing[:5])
else:
    chk(not missing, "every document is named%s" % ("" if not missing else ": %s" % missing[:5]))

if len(sys.argv) > 2:
    print("\n7. against %s" % os.path.basename(sys.argv[2]))
    o = unzip(sys.argv[2])
    r = subprocess.run(["diff", "-rq", "-x", "__pycache__", o, d], capture_output=True, text=True).stdout
    for line in r.replace(o + "/", "").replace(d + "/", "").replace(o, "previous").replace(d, "this").strip().splitlines() or ["identical"]:
        print("  " + line)

print("\n%s" % ("ship check clean: unzipped at %s" % d if not bad else "DO NOT SHIP: %d problem(s)" % len(bad)))
sys.exit(1 if bad else 0)
