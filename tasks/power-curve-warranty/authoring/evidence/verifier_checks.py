"""The verifier's handling of malformed output and misbehaving programs. Each case is the reference program with its
output corrupted after it is written (so only the corruption can make it wrong), run through tests/grade.py exactly as
the verifier runs it (as nobody when this script runs as root).

    python3 authoring/evidence/verifier_checks.py > authoring/evidence/verifier_checks.txt
"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
G = C.load(os.path.join(C.ROOT, "tests", "grade.py"), "grade")

REF = open(os.path.join(C.ROOT, "solution", "pp12.py")).read()
TAIL = 'if __name__ == "__main__":\n    main(sys.argv[1], sys.argv[2])\n'
assert REF.endswith(TAIL)
POST = {
    "reference, unchanged": "",
    "output is a symlink to a correct file": "os.rename(out, out + '.real'); os.symlink(out + '.real', out)",
    "no header": "L = open(out).read().splitlines(); open(out, 'w').write('\\n'.join(L[1:]) + '\\n')",
    "header in another order": "L = open(out).read().splitlines(); L[0] = 'turbine,warranty_claim,aep_ratio'; open(out, 'w').write('\\n'.join(L) + '\\n')",
    "an extra column": "L = open(out).read().splitlines(); open(out, 'w').write('\\n'.join(l + ',x' for l in L) + '\\n')",
    "a turbine twice": "L = open(out).read().splitlines(); open(out, 'w').write('\\n'.join(L + [L[1]]) + '\\n')",
    "a turbine missing": "L = open(out).read().splitlines(); open(out, 'w').write('\\n'.join(L[:-1]) + '\\n')",
    "an extra turbine": "L = open(out).read().splitlines(); open(out, 'w').write('\\n'.join(L + ['T99,1.0000,no']) + '\\n')",
    "a ratio NaN": "L = open(out).read().splitlines(); t = L[1].split(','); L[1] = t[0] + ',nan,' + t[2]; open(out, 'w').write('\\n'.join(L) + '\\n')",
    "a ratio infinite": "L = open(out).read().splitlines(); t = L[1].split(','); L[1] = t[0] + ',inf,' + t[2]; open(out, 'w').write('\\n'.join(L) + '\\n')",
    "a ratio not a number": "L = open(out).read().splitlines(); t = L[1].split(','); L[1] = t[0] + ',high,' + t[2]; open(out, 'w').write('\\n'.join(L) + '\\n')",
    "a claim 'Yes' (capitalised)": "s = open(out).read().replace(',yes', ',Yes').replace(',no', ',Yes'); open(out, 'w').write(s)",
    "empty file": "open(out, 'w').close()",
    "bytes that are not UTF-8": "open(out, 'ab').write(b'\\xff\\xfe\\n')",
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


def program(post):
    body = REF[:-len(TAIL)] + 'if __name__ == "__main__":\n    main(sys.argv[1], sys.argv[2])\n    out = sys.argv[2]\n'
    if post:
        body += "    " + post + "\n"
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False); f.write(body); f.close()
    os.chmod(f.name, 0o644)
    return f.name


as_nobody = os.geteuid() == 0
print("tests/grade.py on corrupted copies of the reference program, run as %s; 59 hidden turbines, accepted when at most %d is wrong.\n"
      % ("nobody" if as_nobody else "the current user", G.MAX_WRONG))
for name, post in POST.items():
    G.TIME_LIMIT_S = 20 if "time limit" in name else 600
    p = program(post)
    r = G.score(p, hidden=C.HIDDEN, as_nobody=as_nobody)
    left = live_nobody() if as_nobody else []
    errs = sorted({v.get("error", "")[:70] for v in r["packages"].values() if v.get("error")})
    print("%-72s wrong %2d  %s%s" % (name, r["wrong"], "accepted" if r["accepted"] else "rejected",
                                     "; nobody's processes left: %d" % len(left) if as_nobody else ""))
    if errs:
        print("    %s" % errs[0])
    os.unlink(p)
