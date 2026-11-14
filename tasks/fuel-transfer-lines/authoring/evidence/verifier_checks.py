"""verifier_checks.py: what the checker and the reward script do with outputs that are not a plain right answer.
Writes verifier_checks.txt; every case says what is expected and prints UNEXPECTED if it turns out otherwise.

Every program is written here, at run time, around the sealed result of one small site (SITE): it writes
that table, or a variation of it, and may then misbehave. Programs go through tests/rerun.judge like any
other. The reward script, tests/test.sh, is run for real with pytest replaced by a stand-in that exits and
reports as told.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import common

SITE = "kiln_road"                 # a small site
OTHER = "tank_row"                 # another small site, for runs of two
out = common.Sheet(__file__)
tally = {"cases": 0, "unexpected": 0}

with open(os.path.join(common.SMALL, "results", SITE + ".csv"), newline="") as handle:
    SEALED = handle.read()
ROWS = [line.split(",") for line in SEALED.strip().split("\n")]
HEAD, BODY = ROWS[0], ROWS[1:]
with open(os.path.join(common.SMALL, "books", SITE + ".json")) as handle:
    BOOK = json.load(handle)
PIPES = sorted(BOOK["readings"])
ALLOWED = int(BOOK["allowance"])

WRITER = '''import os, subprocess, sys, time
package, out_csv = sys.argv[1], sys.argv[2]
TABLE = %r
def write(text=TABLE):
    with open(out_csv, "wb") as handle:
        handle.write(text if isinstance(text, bytes) else text.encode())
def order(*pipes, where=package):
    said = subprocess.run(["heatsurvey", where] + list(pipes), capture_output=True, text=True)
    return said.returncode, said.stdout.strip().splitlines()
%s
'''


def text_of(rows, head=None, end="\n", last=True):
    lines = [",".join(head or HEAD)] + [",".join(row) for row in rows]
    return end.join(lines) + (end if last else "")


def program(body, table=None):
    return common.written(WRITER % (SEALED if table is None else table, body), "lines.py")


def case(title, expect, path, limit=None, only=None, also=None):
    """Runs a program on the small site and compares the verdict with what is expected ("accepted" or "refused")."""
    verdict = common.run(path, "small", limit=limit, only=only or [SITE])
    got = "accepted" if verdict["accepted"] else "refused"
    good = got == expect and (also is None or also(verdict))
    note = verdict["sites"].get(SITE, {})
    why = verdict["stopped"] or note.get("not_the_table") or (note.get("run") if note.get("run") != "in time" else "") or \
        ("%s records out of band" % note.get("records_out_of_band") if note.get("records_out_of_band") else "")
    tally["cases"] += 1
    tally["unexpected"] += 0 if good else 1
    out.say("%-10s %s: %s%s" % ("ok" if good else "UNEXPECTED", title, got, " (%s)" % why if why else ""))
    return verdict


def scaled(dp=1.0, dt=0.0, rows=None):
    return [[r[0], repr(float(r[1]) * dp), repr(float(r[2]) + dt)] for r in (rows or BODY)]


out.say("tables that are the sealed result in another dress: accepted")
case("the sealed table as it is", "accepted", program("write()"))
case("CRLF line ends", "accepted", program("write()", text_of(BODY, end="\r\n")))
case("no line end after the last row", "accepted", program("write()", text_of(BODY, last=False)))
case("an empty line after every row", "accepted", program("write()", text_of(BODY, end="\n\n")))
case("rows in the opposite order", "accepted", program("write()", text_of(BODY[::-1])))
case("spaces around the values of a row", "accepted", program("write()", text_of([[" %s " % v for v in r] for r in BODY])))
case("every field of a row in quotes", "accepted", program("write()", text_of([['"%s"' % v for v in r] for r in BODY])))
case("a plus sign on every number", "accepted", program("write()", text_of([[r[0], "+" + r[1], "+" + r[2]] for r in BODY])))
case("exponent form", "accepted", program("write()", text_of([[r[0], "%.9e" % float(r[1]), "%.9E" % float(r[2])] for r in BODY])))
case("fifteen decimals", "accepted", program("write()", text_of([[r[0], "%.15f" % float(r[1]), "%.15f" % float(r[2])] for r in BODY])))

out.say()
out.say("tables the task statement does not describe: refused")
case("no OUT_CSV written", "refused", program("pass"))
case("a directory where OUT_CSV should be", "refused", program("os.mkdir(out_csv)"))
case("a symbolic link to a file holding the sealed table", "refused",
     program("out_csv, real = out_csv + '.real', out_csv\nwrite()\nos.symlink(out_csv, real)"))
case("bytes that are not text", "refused", program("write(TABLE.encode() + bytes([255, 254, 0, 200]))"))
case("the sealed table followed by padding to more than %d bytes" % common.rerun.MOST_BYTES, "refused",
     program("write(TABLE + '\\n' * %d)" % common.rerun.MOST_BYTES))
case("no header", "refused", program("write()", "\n".join(",".join(r) for r in BODY) + "\n"))
case("a header with one name misspelt", "refused", program("write()", text_of(BODY, head=["record", "dp_kpa", "t_out_C"])))
case("the header in capitals", "refused", program("write()", text_of(BODY, head=[h.upper() for h in HEAD])))
case("the header with spaces around its names", "refused", program("write()", text_of(BODY, head=[" %s " % h for h in HEAD])))
case("a fourth column", "refused", program("write()", text_of([r + ["0.5"] for r in BODY], head=HEAD + ["share"])))
case("the temperature column left out", "refused", program("write()", text_of([r[:2] for r in BODY], head=HEAD[:2])))
case("one record left out", "refused", program("write()", text_of(BODY[:-1])))
case("one record given twice", "refused", program("write()", text_of(BODY + [BODY[0]])))
case("a record that is not of the package", "refused", program("write()", text_of(BODY + [["FL-999/00", "1.0", "50.0"]])))
for what, bad in (("empty", ""), ("a word", "low"), ("nan", "nan"), ("inf", "inf"), ("followed by its unit", BODY[3][1] + " kPa"),
                  ("with a decimal comma", '"%s"' % BODY[3][1].replace(".", ",")), ("with a digit separator", "1_0.5"),
                  ("in hexadecimal", "0x1F")):
    rows = [list(r) for r in BODY]
    rows[3][1] = bad
    case("one pressure drop %s" % what, "refused", program("write()", text_of(rows)))
case("the sealed table, then exit status 3", "refused", program("write()\nsys.exit(3)"))

out.say()
out.say("the band: 2.5 per cent of the pressure drop, 0.5 K of the outlet temperature")
case("every pressure drop 2.4 per cent high", "accepted", program("write()", text_of(scaled(dp=1.024))))
case("every pressure drop 2.4 per cent low", "accepted", program("write()", text_of(scaled(dp=0.976))))
case("every pressure drop 2.6 per cent high", "refused", program("write()", text_of(scaled(dp=1.026))))
case("every pressure drop 2.6 per cent low", "refused", program("write()", text_of(scaled(dp=0.974))))
case("every outlet temperature 0.45 K high", "accepted", program("write()", text_of(scaled(dt=0.45))))
case("every outlet temperature 0.45 K low", "accepted", program("write()", text_of(scaled(dt=-0.45))))
case("every outlet temperature 0.55 K high", "refused", program("write()", text_of(scaled(dt=0.55))))
case("every outlet temperature 0.55 K low", "refused", program("write()", text_of(scaled(dt=-0.55))))
one = [list(r) for r in BODY]
one[7][1] = repr(float(one[7][1]) * 1.03)
case("one pressure drop 3 per cent high among true ones", "refused", program("write()", text_of(one)))
one = [list(r) for r in BODY]
one[7][2] = repr(float(one[7][2]) - 0.6)
case("one outlet temperature 0.6 K low among true ones", "refused", program("write()", text_of(one)))

out.say()
out.say("the limit, set to 3 s for these cases")
stopped = lambda v: "used up" in v["stopped"]
case("writes the sealed table, sleeps 1 s and exits", "accepted", program("write()\ntime.sleep(1)"), limit=3)
case("writes the sealed table and sleeps on: over the limit, the table not opened", "refused",
     program("write()\ntime.sleep(60)"), limit=3, also=lambda v: stopped(v) and "not_the_table" not in v["sites"][SITE])
case("writes the sealed table, ignores SIGTERM and spins", "refused",
     program("import signal\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nwrite()\nwhile True: pass"), limit=3, also=stopped)
case("over the limit on the first of two sites: the second is never started", "refused",
     program("write()\ntime.sleep(60)"), limit=3, only=[SITE, OTHER], also=lambda v: stopped(v) and list(v["sites"]) == [SITE])
burn = ("def busy(seconds):\n    import time\n    end = time.process_time() + seconds\n    while time.process_time() < end: pass\n"
        "import multiprocessing as mp\n")
counted = burn + ("kids = [mp.Process(target=busy, args=(1.2,)) for _ in range(2)]\n[k.start() for k in kids]\n[k.join() for k in kids]\nwrite()")
case("two processes it starts each burn 1.2 s of CPU and end before it writes the table, limit 10 s: accepted, and their CPU time is counted", "accepted",
     program(counted), limit=10, also=lambda v: v["sites"][SITE]["cpu_seconds"] >= 2.4)
spin = burn + ("write()\nkids = [mp.Process(target=busy, args=(60,)) for _ in range(2)]\n[k.start() for k in kids]\n[k.join() for k in kids]")
case("writes the sealed table and keeps two processes it starts busy, limit 3 s: over the limit", "refused", program(spin), limit=3, also=stopped)
left = ("write()\nsubprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'], start_new_session=True,\n"
        "                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)")
before = subprocess.run(["pgrep", "-f", "time.sleep(300)"], capture_output=True, text=True).stdout.split()
case("writes the sealed table and leaves a process behind in a session of its own", "accepted", program(left), limit=3)
after = subprocess.run(["pgrep", "-f", "time.sleep(300)"], capture_output=True, text=True).stdout.split()
gone = set(after) <= set(before) or os.geteuid() != 0
tally["cases"] += 1
tally["unexpected"] += 0 if gone else 1
out.say("%-10s the process left behind is gone after the run%s" % ("ok" if gone else "UNEXPECTED", "" if os.geteuid() == 0 else " (not checked: the study is not root)"))

out.say()
out.say("the survey crew during a run (each program writes the sealed table only if the crew behaved as stated)")
full = ", ".join(repr(p) for p in PIPES[:ALLOWED])
more = ", ".join(repr(p) for p in PIPES[:ALLOWED + 1])
head = "pipe,line_flow_t_h,flow_t_h,t_in_C,t_out_C,t_amb_C"
case("an order of the whole allowance is answered: status 0, the header and one row a pipe, in the order asked", "accepted",
     program("status, rows = order(%s)\nif status == 0 and rows[0] == %r and [r.split(',')[0] for r in rows[1:]] == [%s] and all(len(r.split(',')) == 6 for r in rows): write()"
             % (full, head, full)),
     also=lambda v: v["sites"][SITE]["survey_order"] == PIPES[:ALLOWED])
case("an order of one pipe over the allowance is refused whole, and the order after it is still taken", "accepted",
     program("first = order(%s)\nsecond = order(%s)\nif first[0] == 1 and len(first[1]) == 1 and second[0] == 0: write()" % (more, full)))
case("an order naming a pipe twice is refused", "accepted",
     program("status, rows = order(%r, %r)\nif status == 1 and len(rows) == 1: write()" % (PIPES[0], PIPES[0])))
case("an order naming a pipe the site does not have is refused", "accepted",
     program("status, rows = order(%r, 'FL-999-A')\nif status == 1 and len(rows) == 1: write()" % PIPES[0]))
case("a second order in the same run is refused, the first having been answered", "accepted",
     program("first = order(%r)\nsecond = order(%r)\nif first[0] == 0 and second[0] == 1 and len(second[1]) == 1: write()" % (PIPES[0], PIPES[1])),
     also=lambda v: v["sites"][SITE]["survey_order"] == [PIPES[0]])
copy = ("import json, shutil\nmine = os.path.join(os.getcwd(), 'mine')\nshutil.copytree(package, mine)\n"
        "os.chmod(os.path.join(mine, 'site.json'), 0o644)\n"
        "with open(os.path.join(mine, 'site.json')) as h: facts = json.load(h)\nfacts['site'] = %r\n"
        "with open(os.path.join(mine, 'site.json'), 'w') as h: json.dump(facts, h)\n"
        "status, rows = order(%r, where=mine)\nif status == 1 and len(rows) == 1: write()" % (OTHER, PIPES[0]))
case("an order through a copy of the package that names another site is refused", "accepted", program(copy),
     also=lambda v: v["sites"][SITE]["survey_order"] is None)
case("heatsurvey with no pipe prints its usage and ends with status 2", "accepted",
     program("said = subprocess.run(['heatsurvey', package], capture_output=True, text=True)\n"
             "if said.returncode == 2 and said.stdout.startswith('usage: heatsurvey'): write()"))
case("the package cannot be written to by the program", "accepted",
     program("try:\n    open(os.path.join(package, 'records.csv'), 'a').close()\nexcept OSError:\n    write()"))

out.say()
out.say("tests/test.sh, run for real with pytest replaced by a stand-in")
STAND_IN = '''import json, os, sys
target = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--ctrf=")][0]
report = os.environ["STAND_IN_REPORT"]
if report != "none":
    with open(target, "w") as handle:
        handle.write(report)
sys.exit(int(os.environ["STAND_IN_STATUS"]))
'''


def report(tests, passed, failed=0, skipped=0, status="passed"):
    return json.dumps({"results": {"summary": {"tests": tests, "passed": passed, "failed": failed, "skipped": skipped, "pending": 0, "other": 0},
                                   "tests": [{"name": "t%d" % i, "status": status} for i in range(tests)]}})


def reward(title, expect, exit_status, text, delivered=True):
    stand = tempfile.mkdtemp(prefix="stand_in_")
    os.mkdir(os.path.join(stand, "pytest"))
    open(os.path.join(stand, "pytest", "__init__.py"), "w").close()     # a regular package, found before the real one
    with open(os.path.join(stand, "pytest", "__main__.py"), "w") as handle:
        handle.write(STAND_IN)
    os.symlink(sys.executable, os.path.join(stand, "python"))
    kept = None
    if os.path.lexists("/app/output/lines.py"):
        kept = tempfile.mkdtemp(prefix="kept_")
        shutil.move("/app/output/lines.py", kept)
    try:
        os.makedirs("/app/output", exist_ok=True)
        if delivered:
            shutil.copy(common.REFERENCE, "/app/output/lines.py")
        env = dict(os.environ, PYTHONPATH=stand, PATH=stand + os.pathsep + os.environ["PATH"], STAND_IN_STATUS=str(exit_status), STAND_IN_REPORT=text)
        done = subprocess.run(["bash", os.path.join(common.TESTS, "test.sh")], env=env, capture_output=True, text=True)
        with open("/logs/verifier/reward.txt") as handle:
            got = handle.read()
    finally:
        if os.path.lexists("/app/output/lines.py"):
            os.unlink("/app/output/lines.py")
        if kept:
            shutil.move(os.path.join(kept, "lines.py"), "/app/output/lines.py")
        shutil.rmtree(stand, ignore_errors=True)
    good = got == expect and done.returncode == 0
    tally["cases"] += 1
    tally["unexpected"] += 0 if good else 1
    out.say("%-10s %s: reward %s" % ("ok" if good else "UNEXPECTED", title, got))


if os.geteuid() == 0:
    reward("pytest exits 0 and the report is one test, passed", "1", 0, report(1, 1))
    reward("pytest exits 0 and the report is two tests, both passed", "0", 0, report(2, 2))
    reward("pytest exits 1 with a report of one test, passed", "0", 1, report(1, 1))
    reward("pytest exits 0 and the report is one test, failed", "0", 0, report(1, 0, failed=1, status="failed"))
    reward("pytest exits 0 and the report is one test, skipped", "0", 0, report(1, 0, skipped=1, status="skipped"))
    reward("pytest exits 0 and leaves no report", "0", 0, "none")
    reward("pytest exits 0 and the report is not JSON", "0", 0, "one test, passed")
    reward("no lines.py was delivered", "0", 0, report(1, 1), delivered=False)
else:
    out.say("not run: the reward script writes under /logs/verifier, and this study is not root")

out.say()
out.say("%d cases, %d UNEXPECTED" % (tally["cases"], tally["unexpected"]))
out.close()
