"""The checker and the reward script, tried on outputs and programs made for the purpose.

    python3 verifier_checks.py > verifier_checks.txt        (as root: the reward script writes under /logs/verifier)

Every program here is built at run time from the sealed result of one small district, so nothing in this
file can go stale. Each case says what the checker should do and what it did; a case that does otherwise is
marked UNEXPECTED, and the last line counts them.
"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile

import common
from common import judge_airflow

DISTRICT = "new_incline"
unexpected = 0
cases = 0


def sealed():
    return judge_airflow.sealed_flows(os.path.join(common.SMALL, "results", DISTRICT + ".csv"))


def table(flows, header="point,flow_m3_s", end="\n", fmt="%.4f"):
    return (header + end + "".join("%s,%s%s" % (p, fmt % q, end) for p, q in flows.items())).encode()


def program(body):
    fd, path = tempfile.mkstemp(prefix="case_", suffix=".py")
    with os.fdopen(fd, "w") as out:
        out.write("import os, sys, time, signal, subprocess\n" + body)
    os.chmod(path, 0o644)
    return path


def writes(payload, then=""):
    return program("open(sys.argv[2], 'wb').write(%r)\n%s" % (payload, then))


def case(what, prog, want, limit=None, only=(DISTRICT,), check=None):
    global unexpected, cases
    cases += 1
    verdict = common.run(prog, "small", limit=limit, only=list(only))
    got = "accepted" if verdict["accepted"] else "refused"
    note = verdict["districts"].get(only[0], {})
    why = verdict["stopped"] or note.get("not_the_table") or (note.get("run") if note.get("run") != "in time" else "") or \
        ("%d points out of band" % note["points_out_of_band"] if note.get("points_out_of_band") else "")
    ok = got == want and (check is None or check(verdict))
    unexpected += not ok
    print("%-10s %s%s%s" % (got, what, "  [%s]" % why if why else "", "" if ok else "   UNEXPECTED"))
    os.unlink(prog)
    return verdict


def tables():
    true = sealed()
    points = list(true)
    good = table(true)
    print("OUT_CSV that is not the table the task statement describes: all refused")
    case("nothing written", program("pass\n"), "refused")
    case("OUT_CSV is a directory", program("os.mkdir(sys.argv[2])\n"), "refused")
    case("OUT_CSV is a symbolic link to a file holding the true table",
         program("open('real.csv','wb').write(%r)\nos.symlink(os.path.abspath('real.csv'), sys.argv[2])\n" % good), "refused")
    case("an empty file", writes(b""), "refused")
    case("the header alone", writes(b"point,flow_m3_s\n"), "refused")
    case("no header", writes(good.split(b"\n", 1)[1]), "refused")
    case("header misspelt (point,flow_m3s)", writes(table(true, "point,flow_m3s")), "refused")
    case("header in capitals", writes(table(true, "POINT,FLOW_M3_S")), "refused")
    case("header padded with a blank", writes(table(true, "point, flow_m3_s")), "refused")
    case("a third column", writes(("point,flow_m3_s,note\n" + "".join("%s,%.4f,x\n" % kv for kv in true.items())).encode()), "refused")
    case("one column", writes(("point\n" + "".join("%s\n" % p for p in true)).encode()), "refused")
    case("a row of three fields", writes(good + b"S99999,1.0,2.0\n"), "refused")
    short = dict(true); short.pop(points[7])
    case("a point left out", writes(table(short)), "refused")
    case("a point given twice", writes(good + ("%s,%.4f\n" % (points[3], true[points[3]])).encode()), "refused")
    case("a point the package does not have", writes(good + b"S99999,1.0\n"), "refused")
    case("a point in lower case", writes(good.replace(points[5].encode(), points[5].lower().encode(), 1)), "refused")
    for label, text in (("empty", ""), ("n/a", "n/a"), ("nan", "nan"), ("inf", "inf"), ("with its unit", "12.5 m3/s"),
                        ("with a decimal comma", '"12,5"'), ("with a digit separator", "1_2.5"), ("in hexadecimal", "0x1F")):
        bad = good.replace(("%s,%.4f" % (points[9], true[points[9]])).encode(), ("%s,%s" % (points[9], text)).encode(), 1)
        case("an airflow %s" % label, writes(bad), "refused")
    case("bytes that are not UTF-8", writes(good + b"\xff\xfe\n"), "refused")
    case("larger than %d bytes (the true table followed by empty lines)" % judge_airflow.MOST_BYTES,
         writes(good + b"\n" * (judge_airflow.MOST_BYTES + 10)), "refused")
    case("the true table, then exit status 3", writes(good, "sys.exit(3)\n"), "refused")
    print()
    print("the true table in ways the task statement leaves open: all accepted")
    case("as it is", writes(good), "accepted")
    case("CRLF line ends", writes(table(true, end="\r\n")), "accepted")
    case("no final line end", writes(good.rstrip(b"\n")), "accepted")
    case("empty lines between rows", writes(good.replace(b"\n", b"\n\n")), "accepted")
    case("the rows in reverse order", writes(table(dict(reversed(list(true.items()))))), "accepted")
    case("blanks round every field", writes(("point,flow_m3_s\n" + "".join(" %s , %.4f \n" % kv for kv in true.items())).encode()), "accepted")
    case("every field quoted", writes(('"point","flow_m3_s"\n' + "".join('"%s","%.4f"\n' % kv for kv in true.items())).encode()), "accepted")
    case("plus signs", writes(table(true, fmt="%+.4f")), "accepted")
    case("exponent form", writes(table(true, fmt="%.6e")), "accepted")
    case("fifteen decimals", writes(table(true, fmt="%.15f")), "accepted")
    print()
    print("the bands (%.1f per cent of the sealed airflow, or %.2f m3/s where that is more)" % (
        100 * judge_airflow.BAND_SHARE, judge_airflow.BAND_FLOOR))
    def moved(share):
        return {p: q + share * max(judge_airflow.BAND_SHARE * abs(q), judge_airflow.BAND_FLOOR) for p, q in true.items()}
    case("every airflow 0.95 of its band high", writes(table(moved(0.95), fmt="%.6f")), "accepted")
    case("every airflow 0.95 of its band low", writes(table(moved(-0.95), fmt="%.6f")), "accepted")
    case("every airflow 1.05 of its band high", writes(table(moved(1.05), fmt="%.6f")), "refused")
    one = dict(true); big = max(true, key=lambda p: abs(true[p])); one[big] = true[big] * 1.02
    case("one airflow 2 per cent high, the rest true", writes(table(one)), "refused",
         check=lambda v: v["districts"][DISTRICT]["points_out_of_band"] == 1)
    small = min(true, key=lambda p: abs(true[p])); two = dict(true); two[small] = true[small] + 0.9 * judge_airflow.BAND_FLOOR
    if judge_airflow.BAND_SHARE * abs(true[small]) < 0.9 * judge_airflow.BAND_FLOOR:
        case("the smallest airflow (%.3f m3/s) 0.027 m3/s high: inside the floor" % true[small], writes(table(two, fmt="%.6f")), "accepted")
    return good


def limits(good):
    print()
    print("the limit, set to 3 s for these cases")
    over = lambda v: v["stopped"].startswith("the run on") and "points_out_of_band" not in v["districts"][DISTRICT]
    case("writes the true table, then sleeps", writes(good, "time.sleep(30)\n"), "refused", limit=3, check=over)
    case("writes the true table, ignores SIGTERM and spins",
         writes(good, "signal.signal(signal.SIGTERM, signal.SIG_IGN)\nwhile True: pass\n"), "refused", limit=3, check=over)
    case("two districts to run, the first over the limit: the second is never started",
         writes(good, "time.sleep(30)\n"), "refused", limit=3, only=(DISTRICT, "old_shaft"),
         check=lambda v: list(v["districts"]) == [DISTRICT])
    case("exits in time and leaves a child running in a session of its own",
         writes(good, "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)\n"),
         "accepted", limit=20)
    if os.geteuid() == 0:
        import time
        time.sleep(0.5)
        seen = subprocess.run(["ps", "-u", "nobody", "-o", "pid=,stat="], capture_output=True, text=True).stdout.splitlines()
        left = [line for line in seen if line.split() and not line.split()[1].startswith("Z")]
        global unexpected
        unexpected += bool(left)
        print("           processes of nobody left after that run: %d%s" % (len(left), "   UNEXPECTED" if left else ""))


def crew(good):
    print()
    print("the survey crew during a run (each program checks the crew's replies itself and writes the true table only")
    print("if every reply is the one expected)")
    districts, results, books = common.sets("small")
    import json
    book = json.load(open(os.path.join(books, DISTRICT + ".json")))
    names = list(book["readings"]); n = book["allowance"]
    ask = ("def ask(*b):\n    r = subprocess.run(['pqsurvey', sys.argv[1]] + list(b), capture_output=True, text=True)\n"
           "    return r.returncode, r.stdout.strip()\n")
    done = "open(sys.argv[2], 'wb').write(%r)\n" % good

    def crew_case(what, body):
        case(what, program(ask + body + done), "accepted")

    crew_case("an order of the whole allowance (%d branches) is answered with one row a branch" % n,
              "c, t = ask(*%r)\nassert c == 0 and len(t.splitlines()) == %d and t.splitlines()[0] == 'branch,dp_Pa,q_m3_s', t\n" % (names[:n], n + 1))
    crew_case("an order of one more than the allowance is refused and is not the district's order: the next is taken",
              "c, t = ask(*%r)\nassert c == 1 and 'at most' in t, t\nc, t = ask(%r)\nassert c == 0, t\n" % (names[:n + 1], names[0]))
    crew_case("an order naming a branch the district does not have is refused, and the next is taken",
              "c, t = ask('NO-SUCH')\nassert c == 1 and 'no branch' in t, t\nc, t = ask(%r)\nassert c == 0, t\n" % names[1])
    crew_case("an order naming a branch twice is refused",
              "c, t = ask(%r, %r)\nassert c == 1 and 'twice' in t, t\n" % (names[0], names[0]))
    crew_case("a second order in the same run is refused",
              "c, t = ask(%r)\nassert c == 0, t\nc, t = ask(%r)\nassert c == 1 and 'already' in t, t\n" % (names[0], names[1]))
    crew_case("an order through a copy of the package that names another district is refused",
              "import shutil, json\nshutil.copytree(sys.argv[1], 'other')\njson.dump({'district': 'old_shaft', 'survey_allowance': 9}, open('other/district.json', 'w'))\n"
              "r = subprocess.run(['pqsurvey', 'other', %r], capture_output=True, text=True)\nassert r.returncode == 1 and 'nothing for a district' in r.stdout, r.stdout\n" % names[0])
    trio = [next(b for b in names if b.startswith("FAN-")), next(b for b in names if "-X-" in b),
            next(b for b in names if b.endswith("-REG"))]
    crew_case("a fan branch, a cut-through and a regulator can be named like any other branch",
              "c, t = ask(*%r)\nassert c == 0 and len(t.splitlines()) == 4, t\n" % (trio,))
    global unexpected, cases
    cases += 1
    alone = subprocess.run([sys.executable, os.path.join(common.TESTS, "crew", "pqsurvey"), os.path.join(districts, DISTRICT), names[0]],
                           capture_output=True, text=True, env={"PATH": os.environ["PATH"], "SURVEY_WINDOW": "/nonexistent/window"})
    ok = alone.returncode == 1 and "not available" in alone.stdout
    unexpected += not ok
    print("%-10s outside a run nothing answers: %r%s" % ("refused" if alone.returncode else "answered", alone.stdout.strip(), "" if ok else "   UNEXPECTED"))


def reward():
    print()
    print("tests/test.sh itself, run for real with `python -m pytest` replaced by a stand-in that leaves the report and")
    print("the exit status named; the reward is what /logs/verifier/reward.txt holds afterwards")
    global unexpected, cases
    if os.geteuid() != 0:
        print("not root: skipped")
        return
    room = tempfile.mkdtemp(prefix="reward_")
    for name in ("test.sh", "one_passed.py"):
        shutil.copy(os.path.join(common.TESTS, name), room)
    stand_in = os.path.join(room, "bin")
    os.mkdir(stand_in)
    with open(os.path.join(stand_in, "python"), "w") as out:
        out.write("#!/bin/bash\n"
                  'if [ "$1" = "-m" ] && [ "$2" = "pytest" ]; then\n'
                  '  for a in "$@"; do case "$a" in --ctrf=*) report="${a#--ctrf=}";; esac; done\n'
                  '  [ -n "$STAND_REPORT" ] && printf "%%s" "$STAND_REPORT" > "$report"\n'
                  '  exit "$STAND_EXIT"\n'
                  "fi\n"
                  'exec %s "$@"\n' % sys.executable)
    os.chmod(os.path.join(stand_in, "python"), 0o755)
    delivered = "/app/output/airflow.py"
    kept = None
    if os.path.exists(delivered):
        kept = delivered + ".kept"; os.rename(delivered, kept)
    os.makedirs("/app/output", exist_ok=True)
    summary = lambda **k: '{"results": {"summary": %s}}' % str(dict(dict(tests=1, passed=1, failed=0, skipped=0, pending=0, other=0), **k)).replace("'", '"')
    rows = (("pytest exits 0, the report counts one test, passed", True, 0, summary(), "1"),
            ("pytest exits 1, the report counts one test, failed", True, 1, summary(passed=0, failed=1), "0"),
            ("pytest exits 0, the report counts one test, skipped", True, 0, summary(passed=0, skipped=1), "0"),
            ("pytest exits 0, the report counts two tests, passed", True, 0, summary(tests=2, passed=2), "0"),
            ("pytest exits 1, the report counts one test, passed", True, 1, summary(), "0"),
            ("pytest exits 0 and leaves no report", True, 0, "", "0"),
            ("pytest exits 0, the report is not JSON", True, 0, "one passed", "0"),
            ("no airflow.py delivered", False, 0, summary(), "0"))
    try:
        for what, there, status, report, want in rows:
            cases += 1
            if there:
                open(delivered, "w").write("pass\n")
            elif os.path.exists(delivered):
                os.unlink(delivered)
            env = dict(os.environ, PATH=stand_in + os.pathsep + os.environ["PATH"], STAND_EXIT=str(status), STAND_REPORT=report)
            done = subprocess.run(["bash", os.path.join(room, "test.sh")], env=env, capture_output=True, text=True)
            try:
                got = open("/logs/verifier/reward.txt").read()
            except OSError:
                got = "no file"
            mode = stat.S_IMODE(os.stat("/logs/verifier").st_mode)
            ok = got == want and done.returncode == 0 and mode == 0o700
            unexpected += not ok
            print("reward %-3s %s%s" % (got, what, "" if ok else "   UNEXPECTED (exit %d, mode %o)" % (done.returncode, mode)))
    finally:
        if os.path.exists(delivered):
            os.unlink(delivered)
        if kept:
            os.rename(kept, delivered)
        shutil.rmtree(room, ignore_errors=True)


def main():
    print("tests/judge_airflow.py on the small district %s (%d points), the programs made here from its sealed result" % (
        DISTRICT, len(sealed())))
    print()
    good = tables()
    limits(good)
    crew(good)
    reward()
    print()
    print("%d cases, %d unexpected" % (cases, unexpected))


if __name__ == "__main__":
    main()
