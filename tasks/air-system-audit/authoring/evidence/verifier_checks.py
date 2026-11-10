"""Checks that the verifier rejects malformed results and leaves no process behind. Each case is a small program
run through grade_audits.run_one on one hidden audit, as user nobody when run as root, as the verifier does; the
daemon case also checks that no process it started is left.

    python3 authoring/evidence/verifier_checks.py > authoring/evidence/verifier_checks.txt
"""
import os
import tempfile
import time

import common as C

GOOD = '{"avg_demand_m3_min": 1.0, "peak_demand_m3_min": 1.0, "leak_m3_min": 1.0, "specific_power_kw_per_m3_min": 1.0}'
CASES = {
    "well-formed result (judged on its values)": "open(sys.argv[2], 'w').write(%r)" % GOOD,
    "NaN value": "open(sys.argv[2], 'w').write(%r)" % GOOD.replace('"leak_m3_min": 1.0', '"leak_m3_min": NaN'),
    "infinite value": "open(sys.argv[2], 'w').write(%r)" % GOOD.replace('1.0}', 'Infinity}'),
    "boolean value": "open(sys.argv[2], 'w').write(%r)" % GOOD.replace('"leak_m3_min": 1.0', '"leak_m3_min": true'),
    "string value": "open(sys.argv[2], 'w').write(%r)" % GOOD.replace('"leak_m3_min": 1.0', '"leak_m3_min": "1.0"'),
    "array value": "open(sys.argv[2], 'w').write(%r)" % GOOD.replace('"leak_m3_min": 1.0', '"leak_m3_min": []'),
    "duplicate key": "open(sys.argv[2], 'w').write(%r)" % GOOD.replace('}', ', "leak_m3_min": 1.0}'),
    "missing key": "open(sys.argv[2], 'w').write(%r)" % GOOD.replace('"leak_m3_min": 1.0, ', ''),
    "extra key": "open(sys.argv[2], 'w').write(%r)" % GOOD.replace('}', ', "note": 1.0}'),
    "empty array instead of an object": "open(sys.argv[2], 'w').write('[]')",
    "symlink as the result": "os.symlink('/etc/hostname', sys.argv[2])",
    "no result written": "pass",
    "background process left running": ("if os.fork() == 0:\n    os.setsid()\n    if os.fork() == 0:\n"
                                        "        time.sleep(600)\n    os._exit(0)\n"
                                        "open(sys.argv[2], 'w').write(%r)" % GOOD),
}


def leftovers(tag):
    n = 0
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                cmd = open("/proc/%s/cmdline" % d, "rb").read()
                st = open("/proc/%s/status" % d).read()
            except OSError:
                continue
            if tag.encode() in cmd and "State:\tZ" not in st:
                n += 1
    return n


site = os.path.join(C.HIDDEN, "s-301")
truth = __import__("json").load(open(os.path.join(C.HIDDEN, "truth.json")))["s-301"]
print("Verifier robustness: each malformed result must count as wrong (not a crash), and nothing may outlive a run.\n")
for name, body in CASES.items():
    with tempfile.NamedTemporaryFile("w", suffix="_vcheck.py", delete=False) as f:
        f.write("import os, sys, time\n" + body + "\n")
        prog = f.name
    t0 = time.time()
    res, err = C.grade_audits.run_one(prog, site, as_nobody=os.geteuid() == 0)
    dt = time.time() - t0
    if err is None:
        ok, info = C.grade_audits.judge(res, truth)
        verdict = "right" if ok else "wrong: %s" % (info if isinstance(info, str) else "values off")
    else:
        verdict = "wrong: %s" % err.split(":")[0]
    left = leftovers(os.path.basename(prog))
    print("%-42s %-60s %.1f s, processes left %d" % (name, verdict[:60], dt, left))
    os.unlink(prog)
