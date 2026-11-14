"""Cases put to the verifier itself: sheets it must refuse, sheets it must take, the band, the limit, the run.

    python3 verifier_checks.py > verifier_checks.txt        as root

Two small works are made by the generator for the purpose (coil_yard and die_store with a hundredth of the
lifts), with their own sealed results. Every case is a complete program, written here at run time round those
sealed results, and run by tests/rope_bench.py as the verifier runs a delivered ropes.py. Each case says what
the bench should do with it; a case that goes the other way is printed as UNEXPECTED and the script ends 1.

The last group runs tests/test.sh itself, with `python -m pytest` stood in for by a script that leaves a chosen
report and exit status, to see what the reward file holds for each combination.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import common

bench = common.rope_bench
WHERE = common.made_again(0.01, which=("coil_yard", "die_store"))
ONE = None                # (works dir, sealed dir) holding coil_yard alone, set in main
TRUE = {}                 # works -> {row: damage}
unexpected, cases = 0, 0


def writer(body):
    """A program that writes `body` (a Python expression giving the sheet's text for a works) to OUT_CSV."""
    return common.as_file('''import os, sys, time
# which works this is, by the name of its first crane
tag = open(os.path.join(sys.argv[1], "cranes.csv")).read().splitlines()[1].split("-")[0]
SHEETS = %r
text = SHEETS[tag]
%s
''' % ({sorted(rows)[0].split("-")[0]: sheet_text(rows) for rows in TRUE.values()}, body))


def sheet_text(rows, form="%.6f"):
    return "row,damage\n" + "".join("%s,%s\n" % (row, form % value) for row, value in rows.items())


def case(label, program, expect, where=None, limit=common.LIMIT, check=None):
    """expect: True (accepted), False (refused), or a string that must appear in the first trial's outcome."""
    global unexpected, cases
    cases += 1
    verdict = bench.judge(program, works_dir=(where or ONE)[0], sealed_dir=(where or ONE)[1], limit=limit)
    first = verdict["trials"][0]["outcome"] if verdict["trials"] else verdict["halted"]
    good = (verdict["accepted"] is True) if expect is True else (verdict["accepted"] is False)
    if isinstance(expect, str):
        good = good and expect in first
    if check is not None:
        good = good and check(verdict)
    print("%-11s %-58s %s%s" % ("ok" if good else "UNEXPECTED", label, "accepted" if verdict["accepted"] else "refused: " + first,
                               "" if not verdict["halted"] or verdict["halted"] in first else " | " + verdict["halted"]))
    unexpected += not good
    return verdict


def sheet_case(label, transform, expect):
    """transform: Python source turning `text`, the true sheet, into what is written."""
    return case(label, writer(transform + "\nopen(sys.argv[2], 'w', newline='').write(text)"), expect)


def main():
    global ONE
    if os.geteuid() != 0:
        print("this study is run as root, as the verifier is; nothing was run")
        return 1
    for name in sorted(os.listdir(WHERE[0])):
        TRUE[name] = bench.sealed_sheet(os.path.join(WHERE[1], name + ".csv"))
    one = common.temporary("one-")
    shutil.copytree(os.path.join(WHERE[0], "coil_yard"), os.path.join(one, "works", "coil_yard"))
    os.makedirs(os.path.join(one, "sealed"))
    shutil.copyfile(os.path.join(WHERE[1], "coil_yard.csv"), os.path.join(one, "sealed", "coil_yard.csv"))
    os.chmod(os.path.join(one, "sealed"), 0o700)          # as /tests is in the verifier's image: root's alone
    ONE = (os.path.join(one, "works"), os.path.join(one, "sealed"))
    first_row = sorted(TRUE["coil_yard"])[0]

    print("sheets that are not the sheet of the statement\n")
    case("nothing written", writer("pass"), "no sheet")
    case("a directory at OUT_CSV", writer("os.mkdir(sys.argv[2])"), "not an ordinary file")
    case("a link to the true sheet at OUT_CSV",
         writer("real = sys.argv[2] + '.real'\nopen(real, 'w').write(text)\nos.symlink(real, sys.argv[2])"), "no sheet")
    case("a named pipe at OUT_CSV", writer("os.mkfifo(sys.argv[2])"), "not an ordinary file")
    sheet_case("an empty file", "text = ''", "empty")
    sheet_case("the header alone", "text = 'row,damage\\n'", "have no row")
    sheet_case("no header", "text = text.split('\\n', 1)[1]", "first line")
    sheet_case("header Row,Damage", "text = text.replace('row,damage', 'Row,Damage', 1)", "first line")
    sheet_case("header with a blank before it", "text = ' ' + text", "first line")
    sheet_case("header in quotes", "text = text.replace('row,damage', '\"row\",\"damage\"', 1)", "first line")
    sheet_case("header row,damage,note and a third field", "text = '\\n'.join(l + ',x' for l in text.splitlines()).replace('damage,x', 'damage,note', 1)", "first line")
    sheet_case("a third field in one row", "text = text.replace('\\n', ',0.1\\n', 2).replace('damage,0.1', 'damage', 1)", "fields, not 2")
    sheet_case("a row of one field", "text = text + '%s\\n'" % first_row, "fields, not 2")
    sheet_case("a row left out", "text = '\\n'.join(text.splitlines()[:-1]) + '\\n'", "have no row")
    sheet_case("a row given twice", "text = text + text.splitlines()[1] + '\\n'", "a second time")
    sheet_case("a row for a station the rope has not", "text = text + 'CY-1-999,0.01\\n'", "not a station")
    sheet_case("row names in lower case", "text = 'row,damage\\n' + text.split('\\n', 1)[1].lower()", "not a station")
    sheet_case("station numbers without their zeros", "import re\ntext = re.sub(r'-0+(\\d+),', r'-\\1,', text)", "not a station")
    for label, value in (("a damage left empty", ""), ("a damage of n/a", "n/a"), ("a damage of nan", "nan"), ("a damage of inf", "inf"),
                         ("a damage with a per cent sign", "12%"), ("a damage with a decimal comma, quoted", '"0,12"'),
                         ("a damage in hexadecimal", "0x1p-3"), ("a damage of 1e999", "1e999"), ("a damage of --0.1", "--0.1")):
        sheet_case(label, "lines = text.splitlines()\nlines[1] = lines[1].split(',')[0] + ',' + %r\ntext = '\\n'.join(lines) + '\\n'" % value,
                   "not finite" if value == "1e999" else "not a decimal number")
    sheet_case("a sheet of more than 1 MiB", "text = text + '\\n' * (1024 * 1024)", "larger than")
    case("a sheet in UTF-16", writer("open(sys.argv[2], 'wb').write(text.encode('utf-16'))"), "not plain text")
    case("the true sheet, exit status 3", writer("open(sys.argv[2], 'w').write(text)\nsys.exit(3)"), "status 3")
    case("the true sheet, killed by its own signal", writer("open(sys.argv[2], 'w').write(text)\nos.kill(os.getpid(), 9)"), "status -9")

    print("\nthe true sheet written in ways the statement leaves open\n")
    sheet_case("as it is", "pass", True)
    sheet_case("CRLF line ends", "text = text.replace('\\n', '\\r\\n')", True)
    sheet_case("no line end after the last row", "text = text.rstrip('\\n')", True)
    sheet_case("empty lines between rows", "text = text.replace('\\n', '\\n\\n')", True)
    sheet_case("rows in reverse order", "lines = text.splitlines()\ntext = '\\n'.join(lines[:1] + lines[:0:-1]) + '\\n'", True)
    sheet_case("every field in quotes", "lines = text.splitlines()\ntext = '\\n'.join(lines[:1] + ['\"%s\",\"%s\"' % tuple(l.split(',')) for l in lines[1:]]) + '\\n'", True)
    sheet_case("blanks round the fields", "lines = text.splitlines()\ntext = '\\n'.join(lines[:1] + [' %s , %s ' % tuple(l.split(',')) for l in lines[1:]]) + '\\n'", True)
    sheet_case("a plus sign before each damage", "lines = text.splitlines()\ntext = '\\n'.join(lines[:1] + [l.replace(',', ',+') for l in lines[1:]]) + '\\n'", True)
    sheet_case("exponent form", "lines = text.splitlines()\ntext = '\\n'.join(lines[:1] + ['%s,%.6e' % (l.split(',')[0], float(l.split(',')[1])) for l in lines[1:]]) + '\\n'", True)
    sheet_case("twelve decimals", "lines = text.splitlines()\ntext = '\\n'.join(lines[:1] + ['%s,%.12f' % (l.split(',')[0], float(l.split(',')[1])) for l in lines[1:]]) + '\\n'", True)

    print("\nthe band: %g of the greatest damage of the rope\n" % bench.SHARE)
    top = {}
    for row, value in TRUE["coil_yard"].items():
        top[bench.rope_of(row)] = max(top.get(bench.rope_of(row), 0.0), value)
    shift = "TOP = %r\nlines = text.splitlines()\ntext = '\\n'.join(lines[:1] + ['%%s,%%.9f' %% (l.split(',')[0], float(l.split(',')[1]) + SIGN * %g * TOP[l.split(',')[0].rsplit('-', 1)[0]]) for l in lines[1:]]) + '\\n'" % (top, bench.SHARE)
    sheet_case("every row 0.9 of the band high", shift.replace("SIGN", "0.9"), True)
    sheet_case("every row 0.9 of the band low", shift.replace("SIGN", "-0.9"), True)
    sheet_case("every row 1.1 of the band high", shift.replace("SIGN", "1.1"), "rows out")
    sheet_case("every row 1.1 of the band low", shift.replace("SIGN", "-1.1"), "rows out")
    sheet_case("one row of one rope 1.2 of the band high",
               "lines = text.splitlines()\nlines[7] = '%%s,%%.9f' %% (lines[7].split(',')[0], float(lines[7].split(',')[1]) + 1.2 * %g * %r)\ntext = '\\n'.join(lines) + '\\n'"
               % (bench.SHARE, top[bench.rope_of(sorted(TRUE["coil_yard"])[6])]), "1 of")

    print("\nthe limit, set to 3 s for the purpose; two works, coil_yard first\n")
    late = lambda v: len(v["trials"]) == 1 and "nothing after it was tried" in v["halted"]
    case("the true sheet, then asleep for 30 s", writer("open(sys.argv[2], 'w').write(text)\ntime.sleep(30)"), "over the limit", WHERE, 3, late)
    case("the true sheet, then spinning with SIGTERM ignored",
         writer("import signal\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nopen(sys.argv[2], 'w').write(text)\nwhile True: pass"), "over the limit", WHERE, 3, late)
    case("four processes spinning 1.5 s each, done in 1.5 s",
         writer("open(sys.argv[2], 'w').write(text)\nkids = []\nfor _ in range(4):\n    pid = os.fork()\n    if pid == 0:\n        end = time.process_time() + 1.5\n        while time.process_time() < end: pass\n        os._exit(0)\n    kids.append(pid)\nfor pid in kids: os.waitpid(pid, 0)"),
         "over the limit", WHERE, 3, lambda v: late(v) and v["trials"][0]["seconds"] < 3)
    case("four processes spinning 1.5 s each, never waited for",
         writer("open(sys.argv[2], 'w').write(text)\nfor _ in range(4):\n    if os.fork() == 0:\n        os.setsid()\n        end = time.process_time() + 1.5\n        while time.process_time() < end: pass\n        os._exit(0)\ntime.sleep(2.0)"),
         "over the limit", WHERE, 3, late)
    case("done in time, a child left asleep in a session of its own",
         writer("open(sys.argv[2], 'w').write(text)\nif os.fork() == 0:\n    os.setsid()\n    time.sleep(600)"), True, WHERE, 3,
         lambda v: not bench.processes(0, True))
    case("one process, 1 s of work on each works", writer("end = time.process_time() + 1.0\nwhile time.process_time() < end: pass\nopen(sys.argv[2], 'w').write(text)"),
         True, WHERE, 3, lambda v: all(0.9 < n["cpu_seconds"] < 2.0 for n in v["trials"]))

    print("\nthe run: each program writes the true sheet only if what it tests is so\n")
    only_if = lambda test: writer("if %s:\n    open(sys.argv[2], 'w').write(text)" % test)
    case("the working directory holds ropes.py and nothing else", only_if("os.listdir('.') == ['ropes.py']"), True)
    case("the user is nobody", only_if("os.getuid() == 65534 and os.geteuid() == 65534 and os.getgroups() in ([], [65534])"), True)
    case("the package cannot be written to", only_if("not os.access(sys.argv[1], os.W_OK) and not os.access(os.path.join(sys.argv[1], 'surveys.csv'), os.W_OK)"), True)
    case("the package holds its four files", only_if("sorted(os.listdir(sys.argv[1])) == ['cranes.csv', 'movements.csv', 'sheaves.csv', 'surveys.csv']"), True)
    case("one thread to a numerical library", only_if("os.environ.get('OMP_NUM_THREADS') == '1' and os.environ.get('OPENBLAS_NUM_THREADS') == '1'"), True)
    case("the sealed results cannot be read", only_if("not os.access(%r, os.R_OK)" % os.path.join(ONE[1], "coil_yard.csv")), True)
    case("no affinity is set: every CPU of the machine may be used", only_if("len(os.sched_getaffinity(0)) == os.cpu_count()"), True)
    case("a program that is a link to a program", link_to(writer("open(sys.argv[2], 'w').write(text)")), False)

    print("\nthe reward script: tests/test.sh as it stands, `python -m pytest` stood in for\n")
    reward_cases()
    print("\n%d cases, %d unexpected" % (cases, unexpected))
    return 1 if unexpected else 0


def link_to(program):
    link = os.path.join(common.temporary("link-"), "ropes.py")
    os.symlink(program, link)
    return link


def reward_cases():
    global unexpected, cases
    made = [d for d in ("/app", "/logs") if not os.path.exists(d)]
    os.makedirs("/app/output", exist_ok=True)
    os.makedirs("/logs/verifier", exist_ok=True)
    kept = None
    if os.path.exists("/app/output/ropes.py"):
        kept = tempfile.mkdtemp(prefix="kept-")
        shutil.move("/app/output/ropes.py", os.path.join(kept, "ropes.py"))
    stand = common.temporary("stand-")
    real = shutil.which("python3")
    with open(os.path.join(stand, "python"), "w") as handle:
        handle.write('''#!/bin/bash
# stands in for python: `python -m pytest ...` leaves the report and the status this case asks for
if [ "$1" = "-m" ] && [ "$2" = "pytest" ]; then
    [ -n "$STAND_REPORT" ] && printf '%%s' "$STAND_REPORT" > /logs/verifier/ctrf.json
    exit "$STAND_STATUS"
fi
exec %s "$@"
''' % real)
    os.chmod(os.path.join(stand, "python"), 0o755)
    summary = lambda **counts: json.dumps({"results": {"summary": dict({"tests": 0, "passed": 0, "failed": 0, "skipped": 0, "pending": 0, "other": 0}, **counts)}})
    table = [
        ("pytest ends 0, the report counts one test, passed", True, 0, summary(tests=1, passed=1), "1"),
        ("pytest ends 0, the report counts two tests, both passed", True, 0, summary(tests=2, passed=2), "0"),
        ("pytest ends 0, one test, failed", True, 0, summary(tests=1, failed=1), "0"),
        ("pytest ends 0, one test, skipped", True, 0, summary(tests=1, skipped=1), "0"),
        ("pytest ends 0, no test at all", True, 0, summary(), "0"),
        ("pytest ends 1, the report counts one test, passed", True, 1, summary(tests=1, passed=1), "0"),
        ("pytest ends 0, no report", True, 0, "", "0"),
        ("pytest ends 0, the report is not JSON", True, 0, "{tests: 1", "0"),
        ("pytest ends 0, the report has no summary", True, 0, json.dumps({"results": {}}), "0"),
        ("no ropes.py delivered, pytest would end 0 with one test passed", False, 0, summary(tests=1, passed=1), "0"),
    ]
    try:
        for label, delivered, status, report, expect in table:
            cases += 1
            if delivered:
                with open("/app/output/ropes.py", "w") as handle:
                    handle.write("pass\n")
            elif os.path.exists("/app/output/ropes.py"):
                os.remove("/app/output/ropes.py")
            env = dict(os.environ, PATH=stand + os.pathsep + os.environ["PATH"], STAND_STATUS=str(status), STAND_REPORT=report)
            done = subprocess.run(["bash", os.path.join(common.TESTS, "test.sh")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                with open("/logs/verifier/reward.txt") as handle:
                    reward = handle.read()
            except OSError:
                reward = "no file"
            good = reward == expect and done.returncode == 0
            unexpected += not good
            print("%-11s %-58s reward %s" % ("ok" if good else "UNEXPECTED", label, reward))
    finally:
        if os.path.exists("/app/output/ropes.py"):
            os.remove("/app/output/ropes.py")
        if kept:
            shutil.move(os.path.join(kept, "ropes.py"), "/app/output/ropes.py")
            shutil.rmtree(kept, ignore_errors=True)
        for folder in made:
            shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
