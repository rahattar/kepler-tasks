"""Does the verifier refuse what it should and accept what it should?

    python3 verifier_checks.py > verifier_checks.txt

Every case is a complete program judged by tests/check_program.py, or a run of tests/test.sh itself. The
programs are written here at run time around the sealed results of one cell made by the generator with 4
cycles a point, so no table in this file can go stale. Five groups:

  tables    programs that write a table, or something else, where the table belongs
  bands     the true table with one quantity moved to just inside or just outside its band
  limit     programs that are still running when the time is up (the limit is set to 2 s for these)
  runs      what a run can see and do: its directory, its user, the package
  reward    tests/test.sh as it stands, with pytest replaced by a stand-in that ends and reports as told
"""
import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile

import common

CELL = "cell_09"
unexpected = 0
cases = 0


def show(what, got, good):
    global unexpected, cases
    cases += 1
    unexpected += not good
    print("  %-78s %-34s %s" % (what, got, "as expected" if good else "UNEXPECTED"))


WRITER = '''import os, sys, time, signal, subprocess
out = sys.argv[2]
payload = %(payload)r
%(before)s
if payload is not None:
    with open(out, "wb") as handle:
        handle.write(payload)
%(after)s
sys.exit(%(status)d)
'''


def writer(payload, before="", after="", status=0):
    return common.program(WRITER % dict(payload=payload, before=before, after=after, status=status))


def verdict(path, cells_dir, results_dir, **more):
    report = common.assess(path, cells_dir=cells_dir, results_dir=results_dir, **more)
    return report, ("accepted" if report["accepted"] else "not accepted")


def the_tables(cells_dir, results_dir, truth_text):
    rows = list(csv.reader(io.StringIO(truth_text)))
    head, body = rows[0], rows[1:]

    def text(new_head=None, new_body=None, end="\n"):
        return end.join(",".join(r) for r in [new_head or head] + (new_body if new_body is not None else body)) + end

    def with_value(value, column=2):
        changed = [list(r) for r in body]
        changed[3][column] = value
        return text(new_body=changed)

    print("\nTables that must be refused.\n")
    other = os.path.join(common.scratch("true_"), "true.csv")
    with open(other, "w") as handle:
        handle.write(truth_text)
    os.chmod(os.path.dirname(other), 0o755)
    os.chmod(other, 0o644)
    refused = [
        ("nothing written", writer(None)),
        ("a directory where the table belongs", writer(None, before="os.mkdir(out)")),
        ("a symbolic link to a file holding the true table", writer(None, before="os.symlink(%r, out)" % other)),
        ("an empty file", writer(b"")),
        ("the header alone", writer(text(new_body=[]).encode())),
        ("the true rows without the header", writer(text()[len(",".join(head)) + 1:].encode())),
        ("header misspelt (imep_Bar)", writer(text(new_head=[h.replace("imep_bar", "imep_Bar") for h in head]).encode())),
        ("header with a blank after a comma", writer(text().replace("point,cylinder", "point, cylinder", 1).encode())),
        ("header in quotes", writer(text().replace(",".join(head), ",".join('"%s"' % h for h in head), 1).encode())),
        ("a column added", writer(text(new_head=head + ["note"], new_body=[r + ["ok"] for r in body]).encode())),
        ("the column q_gross_J left out", writer(text(new_head=head[:-1], new_body=[r[:-1] for r in body]).encode())),
        ("one row of seven fields", writer(text(new_body=[body[0][:-1]] + body[1:]).encode())),
        ("one row left out", writer(text(new_body=body[1:]).encode())),
        ("one row given twice", writer(text(new_body=body + [body[0]]).encode())),
        ("a row for a point the package does not have", writer(text(new_body=body + [["P99"] + body[0][1:]]).encode())),
        ("a point's name in lower case", writer(text(new_body=[[body[0][0].lower()] + body[0][1:]] + body[1:]).encode())),
        ("cylinder 0", writer(text(new_body=[[body[0][0], "0"] + body[0][2:]] + body[1:]).encode())),
        ("cylinder written 1.0", writer(text(new_body=[[body[0][0], "1.0"] + body[0][2:]] + body[1:]).encode())),
        ("a value left empty", writer(with_value("").encode())),
        ("a value n/a", writer(with_value("n/a").encode())),
        ("a value nan", writer(with_value("nan").encode())),
        ("a value inf", writer(with_value("inf").encode())),
        ("a value with its unit (bar)", writer(with_value(body[3][2] + " bar").encode())),
        ("a value with a decimal comma", writer(with_value(body[3][2].replace(".", ",")).encode())),
        ("a value with a digit separator", writer(with_value("1_0.5").encode())),
        ("a value in hexadecimal", writer(with_value("0x1p3").encode())),
        ("bytes that are not text", writer(truth_text.encode() + b"\xff\xfe\n")),
        ("a table over the size cap", writer(truth_text.encode() + b"\n" * (common.check_program.TABLE_BYTES + 10))),
        ("the true table, then exit status 3", writer(truth_text.encode(), status=3)),
    ]
    for what, path in refused:
        report, said = verdict(path, cells_dir, results_dir)
        show(what, "%s: %s" % (said, report["cells"][CELL]["finding"][:22]), not report["accepted"])

    print("\nThe true table written in ways the task statement leaves open: all must be accepted.\n")
    accepted = [
        ("as the sealed results have it", truth_text),
        ("CRLF line ends", text(end="\r\n")),
        ("no line end after the last row", truth_text.rstrip("\n")),
        ("empty lines between rows and at the top", "\n" + text().replace("\n", "\n\n")),
        ("the rows in reverse order", text(new_body=body[::-1])),
        ("blanks round every field of the rows", text(new_body=[[" %s " % f for f in r] for r in body])),
        ("every field of the rows in quotes", text(new_body=[['"%s"' % f for f in r] for r in body])),
        ("a plus sign on positive values", text(new_body=[r[:2] + [f if f.startswith("-") else "+" + f for f in r[2:]] for r in body])),
        ("exponent form", text(new_body=[r[:2] + ["%.6e" % float(f) for f in r[2:]] for r in body])),
        ("ten decimals", text(new_body=[r[:2] + ["%.10f" % float(f) for f in r[2:]] for r in body])),
        ("cylinders written 01, 02, 03", text(new_body=[[r[0], "0" + r[1]] + r[2:] for r in body])),
    ]
    for what, table in accepted:
        report, said = verdict(writer(table.encode()), cells_dir, results_dir)
        show(what, said, report["accepted"])
    return head, body, text


def the_bands(cells_dir, results_dir, head, body, text):
    print("\nBands. One quantity moved at every row, then at one row only.\n")
    for column, name in enumerate(head[2:], start=2):
        kind, size = common.check_program.BANDS[name]
        for share, want in ((0.9, True), (1.1, False)):
            moved = []
            for r in body:
                value = float(r[column])
                step = share * (size * abs(value) if kind == "share" else size)
                moved.append(r[:column] + ["%.9f" % (value + step)] + r[column + 1:])
            report, said = verdict(writer(text(new_body=moved).encode()), cells_dir, results_dir)
            show("%s moved by %.1f of its band at every row" % (name, share), said, report["accepted"] == want)
    one = [list(r) for r in body]
    one[5][2] = "%.9f" % (float(one[5][2]) * 1.03)
    report, said = verdict(writer(text(new_body=one).encode()), cells_dir, results_dir)
    show("imep_bar 3 per cent high at one row of one cell", said, not report["accepted"])


def the_limit(cells_dir, results_dir, truth_text):
    print("\nThe limit, set to 2 s for these cases.\n")
    two = common.scratch("two_")
    for name in ("a_first", "b_second"):
        shutil.copytree(os.path.join(cells_dir, CELL), os.path.join(two, "cells", name))
        os.makedirs(os.path.join(two, "results"), exist_ok=True)
        shutil.copy(os.path.join(results_dir, CELL + ".csv"), os.path.join(two, "results", name + ".csv"))
    payload = truth_text.encode()
    late = writer(payload, after="time.sleep(30)")
    report, said = verdict(late, cells_dir, results_dir, limit=2)
    show("writes the true table, then sleeps", "%s; %s" % (said, report["cells"][CELL]["finding"]), not report["accepted"]
         and "rows" not in report["cells"][CELL])
    deaf = writer(payload, after="signal.signal(signal.SIGTERM, signal.SIG_IGN)\nwhile True:\n    pass")
    report, said = verdict(deaf, cells_dir, results_dir, limit=2)
    show("writes the true table, ignores SIGTERM and spins", "%s; %s" % (said, report["cells"][CELL]["finding"]),
         not report["accepted"] and "rows" not in report["cells"][CELL])
    report, said = verdict(late, os.path.join(two, "cells"), os.path.join(two, "results"), limit=2)
    show("two cells to run, over the limit on the first", "%s; cells run: %d" % (said, len(report["cells"])),
         not report["accepted"] and len(report["cells"]) == 1)
    marker = os.path.join(common.scratch("marker_"), "alive")
    os.chmod(os.path.dirname(marker), 0o777)
    lingering = "import time\ntime.sleep(4)\nopen(%r, 'w').close()" % marker
    child = "subprocess.Popen([sys.executable, '-c', %r], start_new_session=True)" % lingering
    report, said = verdict(writer(payload, after=child), cells_dir, results_dir, limit=2)
    import time
    time.sleep(6)
    survived = os.path.exists(marker)
    as_nobody = os.geteuid() == 0 and shutil.which("setpriv") is not None
    show("exits in time, leaves a child in a session of its own", "%s; child %s" % (said, "lived on" if survived else "killed"),
         report["accepted"] and (not survived or not as_nobody))


def the_runs(cells_dir, results_dir, truth_text):
    print("\nWhat a run can see and do.\n")
    payload = truth_text.encode()
    alone = writer(payload, before="if sorted(os.listdir('.')) != ['indicate.py']:\n    sys.exit(7)")
    report, said = verdict(alone, cells_dir, results_dir)
    show("the run's directory holds indicate.py and nothing else", said, report["accepted"])
    if os.geteuid() == 0 and shutil.which("setpriv") is not None:
        who = writer(payload, before="if os.getuid() != 65534 or os.geteuid() != 65534:\n    sys.exit(7)")
        report, said = verdict(who, cells_dir, results_dir)
        show("the program runs as the user nobody", said, report["accepted"])
        tests = writer(payload, before="try:\n    os.listdir(%r)\n    sys.exit(7)\nexcept PermissionError:\n    pass" % common.scratch("sealed_"))
        report, said = verdict(tests, cells_dir, results_dir)
        show("a directory of root's with mode 700 cannot be listed by the program", said, report["accepted"])
    spoil = writer(payload, before="try:\n    open(os.path.join(sys.argv[1], 'points.csv'), 'a').write('x')\n    sys.exit(7)\nexcept OSError:\n    pass")
    report, said = verdict(spoil, cells_dir, results_dir)
    show("the package cannot be written to", said, report["accepted"])
    threads = writer(payload, before="if os.environ.get('OMP_NUM_THREADS') != '1' or os.environ.get('OPENBLAS_NUM_THREADS') != '1':\n    sys.exit(7)")
    report, said = verdict(threads, cells_dir, results_dir)
    show("OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1 in the run's environment", said, report["accepted"])


STAND_IN = '''#!/bin/bash
# stands in for `python`: a pytest run ends as told, anything else goes to the real interpreter
if [ "$1" = "-m" ] && [ "$2" = "pytest" ]; then
    for word in "$@"; do
        case "$word" in --ctrf=*) report="${word#--ctrf=}";; esac
    done
    if [ -n "$STAND_IN_REPORT" ]; then cp "$STAND_IN_REPORT" "$report"; fi
    exit "$STAND_IN_STATUS"
fi
exec %s "$@"
'''


def the_reward():
    print("\nThe reward: tests/test.sh as it stands, `python -m pytest` replaced by a stand-in.\n")
    if os.geteuid() != 0:
        print("  not root here: /logs/verifier and /app/output cannot be made, group skipped")
        return
    script = os.path.join(common.TESTS, "test.sh")
    box = common.scratch("reward_")
    with open(os.path.join(box, "python"), "w") as handle:
        handle.write(STAND_IN % sys.executable)
    os.chmod(os.path.join(box, "python"), 0o755)
    made_app = not os.path.exists("/app/output")
    os.makedirs("/app/output", exist_ok=True)
    os.makedirs("/logs/verifier", exist_ok=True)

    def report_file(summary):
        if summary is None:
            return ""
        path = os.path.join(box, "report.json")
        with open(path, "w") as handle:
            handle.write(summary)
        return path

    one = '{"results": {"summary": {"tests": 1, "passed": 1, "failed": 0, "skipped": 0, "pending": 0, "other": 0}}}'
    cases_ = [
        ("pytest ends 0, the report counts one test, passed", True, 0, one, "1"),
        ("pytest ends 1, the report counts one test, failed", True, 1, one.replace('"passed": 1, "failed": 0', '"passed": 0, "failed": 1'), "0"),
        ("pytest ends 1 with a report of a pass", True, 1, one, "0"),
        ("pytest ends 0, the report counts two tests, both passed", True, 0, one.replace('"tests": 1, "passed": 1', '"tests": 2, "passed": 2'), "0"),
        ("pytest ends 0, the one test skipped", True, 0, one.replace('"passed": 1', '"passed": 0').replace('"skipped": 0', '"skipped": 1'), "0"),
        ("pytest ends 0 and leaves no report", True, 0, None, "0"),
        ("pytest ends 0 and the report is not JSON", True, 0, "one test passed", "0"),
        ("no indicate.py delivered, pytest would end 0 with a pass", False, 0, one, "0"),
    ]
    for what, delivered, status, summary, want in cases_:
        if delivered:
            shutil.copy(common.SOLUTION, "/app/output/indicate.py")
        elif os.path.exists("/app/output/indicate.py"):
            os.unlink("/app/output/indicate.py")
        with open("/logs/verifier/reward.txt", "w") as handle:      # what an earlier run might have left
            handle.write("1")
        env = dict(os.environ, PATH=box + os.pathsep + os.environ["PATH"], STAND_IN_STATUS=str(status),
                   STAND_IN_REPORT=report_file(summary))
        subprocess.run(["bash", script], env=env, capture_output=True, text=True)
        try:
            with open("/logs/verifier/reward.txt") as handle:
                got = handle.read()
        except OSError:
            got = "(no file)"
        show(what, "reward %s" % got, got == want)
    for name in ("reward.txt", "ctrf.json", "cells.json"):
        if os.path.exists(os.path.join("/logs/verifier", name)):
            os.unlink(os.path.join("/logs/verifier", name))
    if os.path.exists("/app/output/indicate.py"):
        os.unlink("/app/output/indicate.py")
    if made_app:
        shutil.rmtree("/app", ignore_errors=True)


def main():
    cells_dir, results_dir = common.cut_down(4, which=(CELL,))
    with open(os.path.join(results_dir, CELL + ".csv")) as handle:
        truth_text = handle.read()
    print("Programs judged by tests/check_program.py on %s made with 4 cycles a point (%d rows)." % (
        CELL, truth_text.count("\n") - 1))
    head, body, text = the_tables(cells_dir, results_dir, truth_text)
    the_bands(cells_dir, results_dir, head, body, text)
    the_limit(cells_dir, results_dir, truth_text)
    the_runs(cells_dir, results_dir, truth_text)
    the_reward()
    print("\n%d cases, %d unexpected" % (cases, unexpected))
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
