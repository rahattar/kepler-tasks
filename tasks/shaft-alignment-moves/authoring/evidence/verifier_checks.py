#!/usr/bin/env python3
"""Malformed and edge-case sheets put through the real grader, and the reward script run for real.

    python3 verifier_checks.py

Every sheet is built from the reference's own answer at run time, so nothing here goes stale when the answer
moves. Each line says what the grader did and whether that was what the task statement calls for. None may
come out UNEXPECTED.
"""
import csv
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

import common

G = common.grade_moves
HEAD = list(G.HEADER)


def rows():
    sheet, _ = common.run()
    return [[tag] + ["%.3f" % move for move in sheet[tag]] for tag in sorted(sheet)]


def render(body, head=HEAD, eol="\n", gap=False, pad=False, quote=csv.QUOTE_MINIMAL, final=True):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator=eol, quoting=quote)
    if head is not None:
        writer.writerow(head)
    for row in body:
        writer.writerow(["  %s " % cell for cell in row] if pad else row)
        if gap:
            out.write(eol)
    text = out.getvalue()
    return text if final else text.rstrip("\r\n")


def with_cell(body, row, column, value):
    changed = [list(r) for r in body]
    changed[row][column] = value
    return changed


def shifted(body, which, vertical=0.0, lateral=0.0):
    out = []
    for i, row in enumerate(body):
        if which == "all" or i == which:
            v = [float(x) for x in row[1:]]
            row = [row[0]] + ["%.3f" % x for x in (v[0] + vertical, v[1] + vertical, v[2] + lateral, v[3] + lateral)]
        out.append(row)
    return out


def main():
    base = rows()
    tol = common.unit3.TOL
    n = len(base)
    small = next((i, j) for i, row in enumerate(base) for j in range(1, 5) if row[j].lstrip("-").startswith("0."))
    cases = [
        # (what, text of the sheet, expected: "accepted", "refused" or the number of trains aligned)
        ("the reference sheet", render(base), "accepted"),
        ("CRLF line ends", render(base, eol="\r\n"), "accepted"),
        ("no terminator on the last line", render(base, final=False), "accepted"),
        ("an empty line after every row", render(base, gap=True), "accepted"),
        ("the rows in reverse order", render(base[::-1]), "accepted"),
        ("blanks around every field of every row", render(base, pad=True), "accepted"),
        ("every field quoted", render(base, quote=csv.QUOTE_ALL), "accepted"),
        ("a plus sign on a positive move", render(with_cell(base, 0, 1, "+" + base[0][1].lstrip("-"))),
         "accepted" if not base[0][1].startswith("-") else "graded"),
        ("no digit before the point", render(with_cell(base, small[0], small[1], base[small[0]][small[1]].replace("0.", ".", 1))),
         "accepted"),
        ("an empty file", "", "refused"),
        ("blanks and line ends only", " \n\n", "refused"),
        ("the header alone", render([]), "refused"),
        ("no header", render(base, head=None), "refused"),
        ("a misspelt header", render(base, head=["tag", "v_front", "v_rear_mm", "h_front_mm", "h_rear_mm"]), "refused"),
        ("blanks inside the header", render(base, head=[" tag"] + HEAD[1:]), "refused"),
        ("the header in capitals", render(base, head=[h.upper() for h in HEAD]), "refused"),
        ("an empty line above the header", "\n" + render(base), "refused"),
        ("a sixth column", render([r + ["0.000"] for r in base], head=HEAD + ["note"]), "refused"),
        ("a row with three moves", render(base[:-1] + [base[-1][:4]]), "refused"),
        ("a row with five moves", render(base[:-1] + [base[-1] + ["0.000"]]), "refused"),
        ("a train left out", render(base[1:]), "refused"),
        ("a train given twice", render(base + [base[0]]), "refused"),
        ("a train that is not on the unit", render(base + [["P-999", "0.000", "0.000", "0.000", "0.000"]]), "refused"),
        ("a tag in lower case", render(with_cell(base, 0, 0, base[0][0].lower())), "refused"),
        ("a move to two decimals", render(with_cell(base, 4, 2, base[4][2][:-1])), "refused"),
        ("a move to four decimals", render(with_cell(base, 4, 2, base[4][2] + "0")), "refused"),
        ("a move with no decimals", render(with_cell(base, 4, 2, "1")), "refused"),
        ("a move in exponent form", render(with_cell(base, 4, 2, "1.250e+00")), "refused"),
        ("a move with a decimal comma", render(with_cell(base, 4, 2, "1,250"), quote=csv.QUOTE_MINIMAL), "refused"),
        ("a move with its unit", render(with_cell(base, 4, 2, "1.250 mm")), "refused"),
        ("two figures for one move", render(with_cell(base, 4, 2, "1.250/1.300")), "refused"),
        ("an empty move", render(with_cell(base, 4, 2, "")), "refused"),
        ("a move of nan", render(with_cell(base, 4, 2, "nan")), "refused"),
        ("a move of inf", render(with_cell(base, 4, 2, "inf")), "refused"),
        ("text that is not ASCII", render(with_cell(base, 4, 2, "1.250" + chr(233))), "refused"),
        ("a sheet over the size cap", render(base) + "\n" * (G.LARGEST_SHEET + 1), "refused"),
        ("one train left %.3f mm high at both planes" % (0.8 * tol), render(shifted(base, 5, vertical=0.8 * tol)), "accepted"),
        ("one train left %.3f mm high at both planes" % (1.4 * tol), render(shifted(base, 5, vertical=1.4 * tol)), n - 1),
        ("one train left %.3f mm to one side at both planes" % (1.4 * tol), render(shifted(base, 9, lateral=-1.4 * tol)), n - 1),
        ("every train left %.3f mm high" % (1.4 * tol), render(shifted(base, "all", vertical=1.4 * tol)), 0),
        ("one train's four moves set to zero", render(with_cell(with_cell(with_cell(with_cell(base, 7, 1, "0.000"), 7, 2, "0.000"), 7, 3, "0.000"), 7, 4, "0.000")), n - 1),
    ]
    print("Sheets put through tests/grade_moves.py. Every sheet is built from the reference's answer.\n")
    wrong = 0
    box = tempfile.mkdtemp(prefix="sam_vc_")

    def line(what, did, good):
        nonlocal wrong
        wrong += 0 if good else 1
        print("%-10s %-52s -> %s" % ("ok" if good else "UNEXPECTED", what, did))

    def judge(outcome, expected):
        if outcome.unreadable:
            return "refused: %s" % outcome.unreadable[:110], expected == "refused"
        if outcome.accepted:
            return "accepted", expected in ("accepted", "graded")
        return "read, %d of %d aligned" % (outcome.aligned, outcome.trains), expected in ("graded", outcome.aligned)

    try:
        path = os.path.join(box, "moves.csv")
        for what, text, expected in cases:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                handle.write(text)
            try:
                did, good = judge(G.assess(path), expected)
            except Exception as crash:                      # the grader must never raise
                did, good = "CRASH %r" % crash, False
            line(what, did, good)
        os.remove(path)
        did, good = judge(G.assess(path), "refused")
        line("no file at all", did, good)
        os.mkdir(path)
        did, good = judge(G.assess(path), "refused")
        line("a directory in place of the sheet", did, good)
        os.rmdir(path)
        real = os.path.join(box, "real.csv")
        with open(real, "w", newline="") as handle:
            handle.write(render(base))
        os.symlink(real, path)
        did, good = judge(G.assess(path), "refused")
        line("a symbolic link to a good sheet", did, good)
    finally:
        shutil.rmtree(box, ignore_errors=True)
    count = len(cases) + 3

    print("\nThe reward script tests/test.sh, run for real with pytest replaced by a stand-in that exits and "
          "reports as told.\n")
    protocol = [
        ("pytest exits 0 and reports one test, passed", 0, dict(tests=1, passed=1, failed=0, skipped=0, pending=0, other=0), "1"),
        ("pytest exits 0 and reports two tests, both passed", 0, dict(tests=2, passed=2, failed=0, skipped=0, pending=0, other=0), "0"),
        ("pytest exits 0 and reports one test, skipped", 0, dict(tests=1, passed=0, failed=0, skipped=1, pending=0, other=0), "0"),
        ("pytest exits 1 though the report shows a pass", 1, dict(tests=1, passed=1, failed=0, skipped=0, pending=0, other=0), "0"),
        ("pytest exits 0 and writes no report", 0, None, "0"),
        ("pytest exits 0 and the report is not JSON", 0, "garbage", "0"),
    ]
    script = os.path.join(common.ROOT, "tests", "test.sh")
    for what, status, summary, want in protocol:
        box = tempfile.mkdtemp(prefix="sam_rp_")
        try:
            report = os.path.join(box, "report.json")
            if summary is not None:
                with open(report, "w") as handle:
                    handle.write(summary if isinstance(summary, str) else json.dumps({"results": {"summary": summary}}))
            stand_in = os.path.join(box, "python")
            with open(stand_in, "w") as handle:
                handle.write('#!/bin/bash\nif [ "$1" = "-m" ]; then\n  %s\n  exit %d\nfi\nexec %s "$@"\n'
                             % ("cp %s /logs/verifier/ctrf.json" % report if summary is not None else ":",
                                status, sys.executable))
            os.chmod(stand_in, os.stat(stand_in).st_mode | stat.S_IEXEC)
            os.makedirs("/logs/verifier", exist_ok=True)
            with open("/logs/verifier/reward.txt", "w") as handle:
                handle.write("1")                              # a reward left by something else must not survive
            with open("/logs/verifier/ctrf.json", "w") as handle:
                json.dump({"results": {"summary": dict(tests=1, passed=1, failed=0, skipped=0, pending=0, other=0)}}, handle)
            subprocess.run(["bash", script], env=dict(os.environ, PATH=box + os.pathsep + os.environ["PATH"]),
                           capture_output=True)
            got = open("/logs/verifier/reward.txt").read() if os.path.exists("/logs/verifier/reward.txt") else "none"
        finally:
            shutil.rmtree(box, ignore_errors=True)
        line(what, "reward %s" % got, got == want)
    count += len(protocol)
    for leftover in ("reward.txt", "ctrf.json"):
        try:
            os.remove(os.path.join("/logs/verifier", leftover))
        except OSError:
            pass
    print("\n%d cases, %d UNEXPECTED" % (count, wrong))
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
