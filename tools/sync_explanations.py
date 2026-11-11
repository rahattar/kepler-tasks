"""Copy the README's three sections into task.toml's explanation fields, word for word.

    python3 tools/sync_explanations.py tasks/<task>

Edit the README, then run this. The intake requires the fields in task.toml; preflight requires the two to agree.
The solution field stops before the README's closing line about solve.sh, and the verification field before the
README's paragraph listing the evidence files, as they always have.
"""
import re
import sys
import tomllib

root = sys.argv[1].rstrip("/")
readme = open(root + "/README.md").read()


def section(head, nxt):
    return readme.split(head, 1)[1].split(nxt, 1)[0].strip()


want = {
    "difficulty_explanation": section("## Difficulty", "\n## Reference solution"),
    "solution_explanation": section("## Reference solution", "\n## Verification").split("\n\n`solution/solve.sh` starts")[0].strip(),
    "verification_explanation": section("## Verification", "\nEvidence (`authoring/evidence/`)"),
}
src = open(root + "/task.toml").read()
for k, v in want.items():
    assert '"""' not in v and "\\" not in v, k
    m = re.search(r'^%s = """\n.*?\n"""\n' % k, src, flags=re.S | re.M)
    assert m, "task.toml has no %s field to replace" % k
    src = src[:m.start()] + '%s = """\n%s\n"""\n' % (k, v) + src[m.end():]
open(root + "/task.toml", "w").write(src)
got = tomllib.load(open(root + "/task.toml", "rb"))["metadata"]
for k, v in want.items():
    assert got[k].strip() == v, k
    print("%-26s %5d chars, as the README has it" % (k, len(v)))
