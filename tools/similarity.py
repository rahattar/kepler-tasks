"""Nearest-neighbour similarity of one task's files against every other task in tasks/.

    python3 tools/similarity.py tasks/<task> [--exclude a,b] [--line 0.4]

For each file of the task that a similarity gate is likely to compare (instruction, Dockerfiles, test.sh, the
verifier's Python, the solution), finds the most similar file of the same role in any other task and prints
two measures:
  ratio    difflib SequenceMatcher ratio on whitespace-normalised text (the measure docs/rejection-patterns.md
           quotes);
  jaccard  token 5-gram Jaccard, which is less sensitive to reordering.
The platform's own measure is not published. These are proxies, calibrated only by the cases in
docs/rejection-patterns.md (relief-valve-adequacy cleared after its harness came down below about 0.4).
--exclude drops tasks known to be out of the pool, for example ones rejected at a later gate.
"""
import difflib
import glob
import os
import re
import sys

args = sys.argv[1:]
if not args:
    sys.exit(__doc__)
task = os.path.abspath(args[0])
exclude = set()
line = 0.4
if "--exclude" in args:
    exclude = set(args[args.index("--exclude") + 1].split(","))
if "--line" in args:
    line = float(args[args.index("--line") + 1])
tasks_dir = os.path.dirname(task)
others = sorted(p for p in glob.glob(os.path.join(tasks_dir, "*"))
                if os.path.isdir(p) and p != task and os.path.basename(p) not in exclude)


def role(rel):
    """Files compared with each other: same path, or for Python the same folder."""
    if rel in ("instruction.md", "environment/Dockerfile", "tests/Dockerfile", "tests/test.sh"):
        return rel
    top = rel.split("/")[0]
    if top in ("tests", "solution") and rel.endswith((".py", ".sh")):
        return top + "/*" + os.path.splitext(rel)[1]
    return None


def files(root):
    out = {}
    for base, _, fs in os.walk(root):
        for f in fs:
            rel = os.path.relpath(os.path.join(base, f), root).replace(os.sep, "/")
            r = role(rel)
            if r and "__pycache__" not in rel:
                out[rel] = r
    return out


def norm(path):
    return re.sub(r"\s+", " ", open(path, errors="replace").read()).strip()


def grams(text, n=5):
    t = re.findall(r"\w+|[^\w\s]", text)
    return {tuple(t[i:i + n]) for i in range(max(len(t) - n + 1, 0))}


mine = files(task)
pool = [(os.path.basename(o), rel, r, os.path.join(o, rel)) for o in others for rel, r in files(o).items()]
cache = {}
print("%-34s %6s %-30s %7s" % ("file", "ratio", "nearest", "jaccard"))
for rel, r in sorted(mine.items()):
    a = norm(os.path.join(task, rel)); ga = grams(a)
    best = (0.0, "-", 0.0)
    for name, orel, orole, path in pool:
        if orole != r:
            continue
        if path not in cache:
            b = norm(path); cache[path] = (b, grams(b))
        b, gb = cache[path]
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        if sm.real_quick_ratio() < best[0] or sm.quick_ratio() < best[0]:
            continue
        ratio = sm.ratio()
        if ratio > best[0]:
            jac = len(ga & gb) / len(ga | gb) if ga | gb else 0.0
            best = (ratio, "%s/%s" % (name, orel) if orel != rel else name, jac)
    flag = "  <- above %.2f" % line if best[0] > line else ""
    print("%-34s %6.3f %-30s %7.3f%s" % (rel, best[0], best[1][:30], best[2], flag))
