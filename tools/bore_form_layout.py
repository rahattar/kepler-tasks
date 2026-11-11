"""Lay bore-form-acceptance's form errors out again after the sealed definition's shapes change.

    python3 tools/bore_form_layout.py

tune.py solves each setup's lobing scale and each feature's mean; three features are then brought to their own
form targets by a shape of their own (RJ-41 and CB-22 by taper, RJ-46 by ovality), and the means are solved a
second time. Everything is written back into authoring/provenance/isim.py. Run tune.py afterwards to check.
"""
import os
import re
import subprocess
import sys

PROV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tasks", "bore-form-acceptance",
                    "authoring", "provenance")
ISIM = os.path.join(PROV, "isim.py")


def entry(t, f):
    i = t.index('"%s": dict(' % f)
    rest = t[i:]
    n = rest.index('\n    "') if '\n    "' in rest else len(rest)
    return i, rest[:n]


def set_mean(t, f, mean):
    i, seg = entry(t, f)
    return t[:i] + re.sub(r"mean=\([^)]*\)", "mean=%s" % mean, seg, count=1) + t[i + len(seg):]


def solve_and_apply():
    out = subprocess.run([sys.executable, "-B", "tune.py", "solve"], cwd=PROV, capture_output=True, text=True).stdout
    t = open(ISIM).read()
    blk = re.search(r'SETUP = \{\n(?:    "S\d".*\n)+\}', out).group(0)
    t = t.replace(re.search(r'SETUP = \{\n(?:    "S\d".*\n)+\}', t).group(0), blk, 1)
    n = 0
    for m in re.finditer(r'    "(\S+)": mean=(\([^)]*\)), tol=\("(\w+)", ([\d.]+)\),', out):
        f, mean, kind, tol = m.groups()
        pat = re.compile(r'("%s": dict\(kind="\w+", nom=[\d.]+, lim=\([^)]*\), tol=\(")(\w+)(", )([\d.]+)(\))' % f)
        assert pat.search(t), f
        t = pat.sub(lambda g: g.group(1) + kind + g.group(3) + tol + g.group(5), t, count=1)
        t = set_mean(t, f, mean)
        n += 1
    assert n == 14, n
    open(ISIM, "w").write(t)


SHAPES = r'''
import json, sys
sys.dont_write_bytecode = True
import isim as S, tune as T
def form(f): return T.form_of(f, *T.profiles(f))
def bisect(setter, f, lo, hi, want):
    setter(lo); a = form(f); setter(hi); b = form(f)
    assert a <= want <= b, "%s: target %.2f is outside what its shape can reach, %.2f to %.2f" % (f, want, a, b)
    for _ in range(24):
        mid = (lo + hi) / 2.0; setter(mid)
        if form(f) < want: lo = mid
        else: hi = mid
    setter((lo + hi) / 2.0); return (lo + hi) / 2.0, form(f)
def taper(f):
    base = list(S.FEATURES[f]["mean"]); bar = sum(base) / 3.0; patt = [m - bar for m in base]
    s = max(abs(q) for q in patt) or 1.0; unit = [q / s for q in patt]
    def set_k(k): S.FEATURES[f]["mean"] = tuple(round(bar + k * u, 2) for u in unit)
    return set_k
out = {"means": {}}
for f in ("RJ-41", "CB-22"):
    k, got = bisect(taper(f), f, 0.0, 40.0, T.FORM_WANT[f]); out["means"][f] = S.FEATURES[f]["mean"]
    print("%-6s taper half-spread %5.2f um -> form %.2f (want %.2f)" % (f, k, got, T.FORM_WANT[f]))
def set_oval(a):
    d = dict(S.FEATURES["RJ-46"]["own"]); d[2] = (round(a, 2), 1.20); S.FEATURES["RJ-46"]["own"] = d
a, got = bisect(set_oval, "RJ-46", 0.5, 14.0, T.FORM_WANT["RJ-46"]); out["oval"] = round(a, 2)
print("RJ-46  ovality %5.2f um -> form %.2f (want %.2f)" % (a, got, T.FORM_WANT["RJ-46"]))
print("JSON" + json.dumps(out))
'''


def shapes():
    r = subprocess.run([sys.executable, "-B", "-c", SHAPES], cwd=PROV, capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stderr[-600:])
    print("".join(ln + "\n" for ln in r.stdout.splitlines() if not ln.startswith("JSON")), end="")
    import json
    sh = json.loads([ln for ln in r.stdout.splitlines() if ln.startswith("JSON")][0][4:])
    t = open(ISIM).read()
    for f, mean in sh["means"].items():
        t = set_mean(t, f, "(%s)" % ", ".join(str(x) for x in mean))
    i, seg = entry(t, "RJ-46")
    new = re.sub(r"own=\{2: \([\d.]+, 1\.20\)", "own={2: (%.2f, 1.20)" % sh["oval"], seg, count=1)
    assert new != seg or ("2: (%.2f, 1.20)" % sh["oval"]) in seg
    open(ISIM, "w").write(t[:i] + new + t[i + len(seg):])


solve_and_apply()
shapes()
solve_and_apply()
print(subprocess.run([sys.executable, "-B", "tune.py"], cwd=PROV, capture_output=True, text=True).stdout)
