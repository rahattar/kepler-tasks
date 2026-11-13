"""What the checker does with programs that are not the reference.

    python3 verifier_checks.py > verifier_checks.txt        (as root, as the verifier runs)

Four groups, each judged by tests/grade_program.py or run through tests/test.sh itself:

  tables     programs that write a given OUT_CSV: the true results of a cut-down site in a form the task
             statement does not allow, in a form it leaves open, or moved to either side of a band's edge
  the limit  programs that are still running when the time is up, with the limit set to 3 s for the purpose
  the lab    orders placed through tests/lab/labsample as the user nobody while the laboratory is open
  the reward tests/test.sh with pytest replaced by a stand-in that exits and reports as it is told

Every program is built here at run time from the sealed results; none of them is a file of the bundle.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

import common
from common import grade_program

SITE = "south_yard"
unexpected = 0
cases = 0


def show(what, got, as_wanted):
    global unexpected, cases
    cases += 1
    unexpected += not as_wanted
    print("  %-78s %s%s" % (what, got, "" if as_wanted else "   UNEXPECTED"))


def program(body):
    handle, path = tempfile.mkstemp(prefix="case_", suffix=".py")
    with os.fdopen(handle, "w") as out:
        out.write("import os, sys, time\n" + body)
    os.chmod(path, 0o644)
    return path


def writes(payload, then="", status=0):
    return program("open(sys.argv[2], 'wb').write(%r)\n%ssys.exit(%d)\n" % (payload, then, status))


def judged(path, sites, truths, **more):
    outcome = common.assess(path, sites=sites, truths=truths, **more)
    os.unlink(path)
    return outcome


def nobodys_processes():
    count = 0
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            try:
                with open("/proc/%s/status" % entry) as handle:
                    text = handle.read()
                if "\nUid:\t%d\t" % grade_program.NOBODY in text and "\nState:\tZ" not in text:
                    count += 1
            except OSError:
                pass
    return count


def tables(sites, truths):
    truth = common.rows_of(os.path.join(truths, SITE + ".csv"))
    names = grade_program.COLUMNS
    head = ",".join(names)

    def sheet(rows=None, header=head, end="\n", cell=lambda name, text: text, join=","):
        rows = truth if rows is None else rows
        lines = [header] + [join.join(cell(name, row[name]) for name in names) for row in rows]
        return (end.join(lines) + end).encode()

    def moved(name, how):
        return sheet(cell=lambda n, text: ("%.6f" % how(float(text))) if n == name else text)

    print("\nTables. %s cut down to %d points; every table below is its true results, altered as described.\n"
          % (SITE, len(truth)))
    refused = [
        ("nothing written", program("sys.exit(0)\n")),
        ("OUT_CSV made as a directory", program("os.mkdir(sys.argv[2])\n")),
        ("OUT_CSV made as a symbolic link to another file holding the true table",
         program("open('other.csv', 'wb').write(%r)\nos.symlink(os.path.abspath('other.csv'), sys.argv[2])\n" % sheet())),
        ("an empty file", writes(b"")),
        ("the header and no rows", writes((head + "\n").encode())),
        ("no header", writes(sheet()[len(head) + 1:])),
        ("the header with h_min_um spelt hmin_um", writes(sheet(header=head.replace("h_min_um", "hmin_um")))),
        ("the header in capitals", writes(sheet(header=head.upper()))),
        ("the header with a blank after each comma", writes(sheet(header=head.replace(",", ", ")))),
        ("a seventh column", writes(("\n".join([head + ",regime"] + [",".join(row[n] for n in names) + ",L" for row in truth]) + "\n").encode())),
        ("the attitude column left out", writes(("\n".join([head.replace(",attitude_deg", "")] + [",".join(row[n] for n in names if n != "attitude_deg") for row in truth]) + "\n").encode())),
        ("one row of five fields", writes(sheet().replace(("," + truth[3]["p_max_MPa"] + "\n").encode(), b"\n", 1))),
        ("one point left out", writes(sheet(rows=truth[1:]))),
        ("one point given twice", writes(sheet(rows=truth + truth[:1]))),
        ("a row for a point the package does not have", writes(sheet(rows=truth + [dict(truth[0], point="X-000-DE-001")]))),
        ("the points in lower case", writes(sheet(cell=lambda n, t: t.lower() if n == "point" else t))),
        ("one value empty", writes(sheet().replace(("," + truth[2]["power_kW"] + ",").encode(), b",,", 1))),
        ("one value written n/a", writes(sheet().replace(("," + truth[2]["power_kW"] + ",").encode(), b",n/a,", 1))),
        ("one value nan", writes(sheet().replace(("," + truth[2]["power_kW"] + ",").encode(), b",nan,", 1))),
        ("one value inf", writes(sheet().replace(("," + truth[2]["power_kW"] + ",").encode(), b",inf,", 1))),
        ("one value with its unit, as 41.2 um", writes(sheet().replace(("," + truth[2]["h_min_um"] + ",").encode(), ("," + truth[2]["h_min_um"] + " um,").encode(), 1))),
        ("one value with a decimal comma", writes(sheet().replace(("," + truth[2]["t_eff_C"] + ",").encode(), ("," + truth[2]["t_eff_C"].replace(".", ",") + ",").encode(), 1))),
        ("one value with a digit separator, as 1_0", writes(sheet().replace(("," + truth[2]["t_eff_C"] + ",").encode(), b",5_0,", 1))),
        ("bytes that are not UTF-8", writes(sheet() + b"\xff\xfe\n")),
        ("a table padded to more than %d bytes" % grade_program.OUTPUT_CAP,
         writes(sheet(), then="open(sys.argv[2], 'ab').write(b'\\n' * %d)\n" % (grade_program.OUTPUT_CAP + 1))),
        ("the true table, then exit status 3", writes(sheet(), status=3)),
        ("minimum film thickness 1.6 per cent high at every point", writes(moved("h_min_um", lambda v: v * 1.016))),
        ("attitude angle 1.1 degrees high at every point", writes(moved("attitude_deg", lambda v: v + 1.1))),
        ("power loss 1.6 per cent low at every point", writes(moved("power_kW", lambda v: v * 0.984))),
        ("effective temperature 0.55 K high at every point", writes(moved("t_eff_C", lambda v: v + 0.55))),
        ("peak pressure 1.6 per cent high at every point", writes(moved("p_max_MPa", lambda v: v * 1.016))),
        ("one point of the site with its power loss 2 per cent high, the rest true",
         writes(sheet(rows=[dict(truth[0], power_kW="%.6f" % (float(truth[0]["power_kW"]) * 1.02))] + truth[1:]))),
    ]
    for what, path in refused:
        outcome = judged(path, sites, truths)
        show(what, "accepted" if outcome.accepted else "not accepted", not outcome.accepted)
    print()
    taken = [
        ("the true table as it stands", writes(sheet())),
        ("CRLF line ends", writes(sheet(end="\r\n"))),
        ("no terminator after the last row", writes(sheet()[:-1])),
        ("an empty line after every row", writes(sheet(end="\n\n"))),
        ("the rows in reverse order", writes(sheet(rows=truth[::-1]))),
        ("a blank either side of every field", writes(sheet(cell=lambda n, t: " " + t + " "))),
        ("every field in double quotes", writes(sheet(cell=lambda n, t: '"' + t + '"'))),
        ("a plus sign before every value", writes(sheet(cell=lambda n, t: t if n == "point" or t.startswith("-") else "+" + t))),
        ("every value in exponent form", writes(sheet(cell=lambda n, t: t if n == "point" else "%.8e" % float(t)))),
        ("minimum film thickness 1.4 per cent high at every point", writes(moved("h_min_um", lambda v: v * 1.014))),
        ("attitude angle 0.9 degrees high at every point", writes(moved("attitude_deg", lambda v: v + 0.9))),
        ("power loss 1.4 per cent low at every point", writes(moved("power_kW", lambda v: v * 0.986))),
        ("effective temperature 0.45 K high at every point", writes(moved("t_eff_C", lambda v: v + 0.45))),
        ("peak pressure 1.4 per cent high at every point", writes(moved("p_max_MPa", lambda v: v * 1.014))),
    ]
    for what, path in taken:
        outcome = judged(path, sites, truths)
        show(what, "accepted" if outcome.accepted else "not accepted", outcome.accepted)
    return sheet()


def the_limit(sites, truths, good, two_sites, two_truths):
    print("\nThe limit, set to 3 s for these runs. Every program first writes the true table.\n")
    slow = judged(writes(good, then="time.sleep(30)\n"), sites, truths, limit=3)
    entry = slow.sites[SITE]
    opened = "points_out_of_band" in entry or "refused" in entry
    show("then sleeps for 30 s", "%s; table %s; %s" % (entry["run"], "opened" if opened else "not opened",
         "accepted" if slow.accepted else "not accepted"), entry["run"] == "over the limit" and not opened and not slow.accepted)
    deaf = judged(writes(good, then="import signal\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nwhile True:\n    pass\n"),
                  sites, truths, limit=3)
    show("then ignores SIGTERM and spins", "%s after %.1f s; %s" % (deaf.sites[SITE]["run"], deaf.sites[SITE]["seconds"],
         "accepted" if deaf.accepted else "not accepted"),
         deaf.sites[SITE]["run"] == "over the limit" and deaf.sites[SITE]["seconds"] < 4.0 and not deaf.accepted)
    both = judged(writes(good, then="time.sleep(30)\n"), two_sites, two_truths, limit=3)
    show("then sleeps for 30 s, with two sites to run", "%d of 2 sites run; stopped: %s" % (len(both.sites), both.stopped),
         len(both.sites) == 1 and not both.accepted and bool(both.stopped))
    child = judged(writes(good, then="if os.fork() == 0:\n    os.setsid()\n    time.sleep(600)\n    os._exit(0)\n"), sites, truths, limit=3)
    left = nobodys_processes()
    show("then leaves a child in a session of its own asleep for 600 s and exits 0",
         "%s; %d processes of nobody left" % ("accepted" if child.accepted else "not accepted", left),
         child.accepted and left == 0)


def the_lab(sites):
    print("\nThe laboratory, open for %s as it is during that site's run; orders placed as nobody through "
          "tests/lab/labsample.\n" % SITE)
    package = os.path.join(sites, SITE)
    book = grade_program.lab.book_of(common.BOOKS, SITE)
    tags = list(book["analyses"])
    wrapper = os.path.join(common.TOOLS, "labsample")
    other = tempfile.mkdtemp(prefix="other_")
    os.chmod(other, 0o755)
    with open(os.path.join(other, "site.json"), "w") as handle:
        json.dump({"site": "quay_site", "lab_samples": 7}, handle)
    os.chmod(os.path.join(other, "site.json"), 0o644)

    def order(*args):
        command = ([] if os.geteuid() else grade_program.AS_NOBODY) + [sys.executable, wrapper] + list(args)
        done = subprocess.run(command, capture_output=True, text=True)
        return done.returncode, done.stdout.strip().splitlines()

    with grade_program.Desk(SITE, book) as desk:
        status, said = order(package, *tags[:book["budget"] + 1])
        show("an order of one bearing more than the allowance of %d" % book["budget"],
             "status %d: %s" % (status, said[0]), status == 1 and desk.order is None)
        status, said = order(package, tags[0], "Q-999-DE")
        show("an order naming a bearing the site does not have", "status %d: %s" % (status, said[0]),
             status == 1 and desk.order is None)
        status, said = order(other, "B-133-DE")
        show("an order through a package that names another site", "status %d: %s" % (status, said[0]),
             status == 1 and desk.order is None)
        status, said = order(package, *tags[:2])
        show("after those three, an order of two bearings", "status %d: %s and %d rows" % (status, said[0], len(said) - 1),
             status == 0 and said[0] == grade_program.lab.HEADER and len(said) == 3 and desk.order == tags[:2])
        status, said = order(package, tags[2])
        show("a second order in the same run", "status %d: %s" % (status, said[0]),
             status == 1 and said[0] == grade_program.lab.TAKEN and desk.order == tags[:2])
    status, said = order(package, tags[0])
    show("an order when no run is under way", "status %d: %s" % (status, said[0]), status == 1)
    shutil.rmtree(other)


def the_reward():
    print("\nThe reward. tests/test.sh run as it stands, with `python -m pytest` replaced by a stand-in.\n")
    script = os.path.join(common.TESTS, "test.sh")
    passed = dict(tests=1, passed=1, failed=0, skipped=0, pending=0, other=0)
    told = [
        ("pytest exits 0; the report counts one test, passed", 0, passed, "1"),
        ("pytest exits 0; the report counts one test, failed", 0, dict(passed, passed=0, failed=1), "0"),
        ("pytest exits 0; the report counts two tests, both passed", 0, dict(passed, tests=2, passed=2), "0"),
        ("pytest exits 0; the report counts one test, skipped", 0, dict(passed, passed=0, skipped=1), "0"),
        ("pytest exits 1; the report counts one test, passed", 1, passed, "0"),
        ("pytest exits 0 and leaves no report", 0, None, "0"),
        ("pytest exits 0; the report is not JSON", 0, "not a report", "0"),
        ("pytest exits 5, no test collected, no report", 5, None, "0"),
        ("no bearing.py delivered; pytest, were it run, would exit 0 and report one test, passed", 0, passed, "0"),
    ]
    os.makedirs("/logs/verifier", exist_ok=True)
    delivered = "/app/output/bearing.py"
    placed = not os.path.exists(delivered)
    if placed:                                         # test.sh looks for the delivered program first
        os.makedirs(os.path.dirname(delivered), exist_ok=True)
        shutil.copy(common.REFERENCE, delivered)
    aside = delivered + ".aside"
    for what, status, summary, want in told:
        if what.startswith("no bearing.py"):
            os.rename(delivered, aside)
        box = tempfile.mkdtemp(prefix="reward_")
        report = os.path.join(box, "report")
        if summary is not None:
            with open(report, "w") as handle:
                handle.write(summary if isinstance(summary, str) else json.dumps({"results": {"summary": summary}}))
        fake = os.path.join(box, "python")
        with open(fake, "w") as handle:
            handle.write("#!/bin/bash\n"
                         "if [ \"$1\" = \"-m\" ]; then\n"
                         "  %s\n"
                         "  exit %d\n"
                         "fi\n"
                         "exec %s \"$@\"\n" % ("cp %s /logs/verifier/ctrf.json" % report if summary is not None else "true",
                                               status, sys.executable))
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
        # what an earlier run or the program might have left: a reward of 1 and a report of a pass
        with open("/logs/verifier/reward.txt", "w") as handle:
            handle.write("1")
        with open("/logs/verifier/ctrf.json", "w") as handle:
            json.dump({"results": {"summary": passed}}, handle)
        subprocess.run(["bash", script], env=dict(os.environ, PATH=box + os.pathsep + os.environ["PATH"]),
                       capture_output=True)
        try:
            with open("/logs/verifier/reward.txt") as handle:
                got = handle.read()
        except OSError:
            got = "no file"
        shutil.rmtree(box)
        if what.startswith("no bearing.py"):
            os.rename(aside, delivered)
        show(what, "reward %s" % got, got == want)
    if placed:
        os.unlink(delivered)
    for name in ("reward.txt", "ctrf.json"):
        if os.path.exists(os.path.join("/logs/verifier", name)):
            os.unlink(os.path.join("/logs/verifier", name))


def main():
    print("Checks of the verifier, run as %s." % ("root: programs run as nobody" if os.geteuid() == 0 else "an ordinary user"))
    root, sites, truths = common.staged([SITE], every=40)
    root2, sites2, truths2 = common.staged(["canal_works", SITE], every=40)
    try:
        good = tables(sites, truths)
        the_limit(sites, truths, good, sites2, truths2)
        the_lab(sites)
    finally:
        shutil.rmtree(root)
        shutil.rmtree(root2)
    the_reward()
    print("\n%d cases, %d unexpected" % (cases, unexpected))
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
