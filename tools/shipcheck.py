"""Check a bundle zip the way intake will meet it, before it goes to Alex.

    python3 tools/shipcheck.py <bundle.zip> [<previous.zip>]

It unzips into a scratch directory and works only on what is in the zip:
  1. the files at the root are the bundle's and nothing else, with no caches or dotfiles anywhere;
  2. task.toml has the same sections, keys and value types as a task that has passed intake
     (tasks/cooler-fouling-assessment), category "Science", a subcategory, the three explanations,
     the 28800 s agent timeout, and the instruction closes with the required sentence;
  3. the task's own preflight passes when run inside the unzipped tree;
  4. if a previous zip is given, which files differ from it.
Every rule here is one that has bounced a bundle. Add to it whenever intake teaches a new one.
"""
import os
import subprocess
import sys
import tempfile
import tomllib
import zipfile

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
    d = tempfile.mkdtemp(prefix="shipcheck-")
    with zipfile.ZipFile(path) as z:
        z.extractall(d)
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
chk(p.returncode == 0 and "clean" in last, last)

if len(sys.argv) > 2:
    print("\n4. against %s" % os.path.basename(sys.argv[2]))
    o = unzip(sys.argv[2])
    r = subprocess.run(["diff", "-rq", "-x", "__pycache__", o, d], capture_output=True, text=True).stdout
    for line in r.replace(o + "/", "").replace(d + "/", "").replace(o, "previous").replace(d, "this").strip().splitlines() or ["identical"]:
        print("  " + line)

print("\n%s" % ("ship check clean: unzipped at %s" % d if not bad else "DO NOT SHIP: %d problem(s)" % len(bad)))
sys.exit(1 if bad else 0)
