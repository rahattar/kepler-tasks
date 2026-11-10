"""The verifier's handling of malformed output and misbehaving programs, measured through tests/grade.py exactly as
the verifier runs it (as nobody when this script runs as root). Each case is a complete program that writes the
reference's critical speeds for the fan (the values solution/fan.py wrote for the six hidden fans, in reference.txt,
looked up by the fan's name in the title of its datasheet, so that a case runs in seconds) and then corrupts its
output or misbehaves; the first case, uncorrupted, shows that the lookup is right on every fan, so only the
corruption can make a case wrong.

    python3 authoring/evidence/verifier_checks.py > authoring/evidence/verifier_checks.txt
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
G = C.G

REF = {m: (float(a), float(b)) for m, a, _, b in
       re.findall(r"^([a-z]+(?:-[a-z]+)+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s", open(os.path.join(C.ROOT, "authoring", "evidence", "reference.txt")).read(), re.M)}
assert set(REF) == set(C.truth()), REF
BASE = '''import json, os, sys
REF = %r
out = sys.argv[2]
name = open(os.path.join(sys.argv[1], "fan_datasheet.md")).readline()[2:].split(" - ")[0]
V, Vg = REF[name.lower().replace(" ", "-")]
d = {"first_critical_rpm": V, "second_critical_rpm": Vg}
json.dump(d, open(out, "w"))
'''
POST = {
    "reference values, unchanged": "",
    "output is a symlink to a correct file": "os.rename(out, out + '.real'); os.symlink(out + '.real', out)",
    "a key missing": "json.dump({'first_critical_rpm': V}, open(out, 'w'))",
    "an extra key": "json.dump(dict(d, note='ok'), open(out, 'w'))",
    "a key twice": "open(out, 'w').write('{\"first_critical_rpm\": %r, \"second_critical_rpm\": %r, \"second_critical_rpm\": %r}' % (V, Vg, Vg))",
    "keys in other words (first_rpm, second_rpm)": "json.dump({'first_rpm': V, 'second_rpm': Vg}, open(out, 'w'))",
    "a value NaN": "open(out, 'w').write('{\"first_critical_rpm\": NaN, \"second_critical_rpm\": %r}' % Vg)",
    "a value Infinity": "open(out, 'w').write('{\"first_critical_rpm\": Infinity, \"second_critical_rpm\": %r}' % Vg)",
    "a value as a string": "json.dump({'first_critical_rpm': str(V), 'second_critical_rpm': Vg}, open(out, 'w'))",
    "a value true": "json.dump({'first_critical_rpm': V, 'second_critical_rpm': True}, open(out, 'w'))",
    "a value negative": "json.dump({'first_critical_rpm': V, 'second_critical_rpm': -Vg}, open(out, 'w'))",
    "a value zero": "json.dump({'first_critical_rpm': 0, 'second_critical_rpm': Vg}, open(out, 'w'))",
    "a list, not an object": "json.dump([V, Vg], open(out, 'w'))",
    "empty file": "open(out, 'w').close()",
    "bytes that are not UTF-8": "open(out, 'ab').write(b'\\xff\\xfe')",
    "correct object padded to 70 kB": "open(out, 'w').write(json.dumps(d) + ' ' * 70000)",
    "correct output, exit status 1": "sys.exit(1)",
    "correct output, a background process left running": "import subprocess; subprocess.Popen(['setsid', 'sleep', '3000'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)",
    "correct output, then runs past the time limit (limit set to 20 s here)": "import time; time.sleep(60)",
}


def live_nobody():
    """nobody's processes that are still running (zombies awaiting their parent are dead and excluded)."""
    out = []
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                st = open("/proc/%s/status" % d).read().splitlines()
                uid = int(next(l for l in st if l.startswith("Uid:")).split()[1])
                state = next(l for l in st if l.startswith("State:")).split()[1]
                if uid == 65534 and state != "Z":
                    out.append(d)
            except (OSError, StopIteration, ValueError):
                pass
    return out


print("tests/grade.py on corrupted copies of the reference's values, run as %s; six hidden fans, accepted when at "
      "most %d is wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", G.MAX_WRONG))
for name, post in POST.items():
    G.TIME_LIMIT_S = 20 if "time limit" in name else 600
    r = C.verify(C.write_program(BASE % REF + post + "\n"))
    left = live_nobody() if C.AS_NOBODY else []
    errs = sorted({" ".join(v.get("error", "").split())[-110:] for v in r["packages"].values() if v.get("error")})
    print("%-72s wrong %d  %s%s" % (name, r["wrong"], "accepted" if r["accepted"] else "rejected",
                                    "; nobody's processes left: %d" % len(left) if C.AS_NOBODY else ""))
    if errs:
        print("    %s" % errs[0])
G.TIME_LIMIT_S = 600
