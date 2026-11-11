"""Grades a submitted relief assessment of unit 400 against the sealed definition.

The submission is a finding sheet: one row per relief valve, carrying the contingency that governs the valve, the
effective orifice area that contingency requires in mm2, and whether the valve as installed is adequate. A finding
stands only if all three agree with the sealed definition - the contingency named exactly, the area inside
isim.TOL relative, the word adequate or inadequate exactly - and the sheet is taken only when every valve's
finding stands.

Reading the sheet is kept apart from judging it. `read_sheet` turns the file into Finding records or, where it
cannot, into Fault records that say which row and which column were wrong; `assess` judges the findings it got.
Faults are collected rather than raised, so a sheet with several problems reports the first and counts the rest. A
sheet that cannot be read whole yields no findings and is never taken.

What the reader accepts: a regular file, not a link, of at most 100 kB of ASCII; the four column names in order on
the first line; then one row for each valve of unit 400, in any order, no valve twice and none unknown. The area
may be written with as many figures as the submitter likes, plain or in exponent form, so long as it is finite and
lies between AREA_FLOOR and AREA_CEILING mm2. Blank lines are skipped and surrounding spaces ignored. Anything
else is a fault, and nothing a submission can contain escapes this module.
"""
import collections
import csv
import io
import math
import os
import stat
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sealed"))
import isim as sealed  # noqa: E402

COLUMNS = ("valve", "governing_case", "required_area_mm2", "verdict")
VALVES = frozenset(sealed.IDS)
AREA_FLOOR, AREA_CEILING = 1.0e-3, 1.0e5
SIZE_CAP = 100_000

Finding = collections.namedtuple("Finding", "valve case area verdict")
Fault = collections.namedtuple("Fault", "row column reason")
Report = collections.namedtuple("Report", "taken standing total fault findings")


# --------------------------------------------------------------------------- reading
def _without_following(path, flags):
    return os.open(path, flags | os.O_NOFOLLOW)


def _ascii_body(path):
    """The file's text, or a Fault saying why there is none."""
    try:
        mode = os.lstat(path).st_mode
    except OSError:
        return Fault(0, "", "there is no assessment at %s" % path)
    if stat.S_ISLNK(mode):
        return Fault(0, "", "the assessment is a symbolic link")
    if not stat.S_ISREG(mode):
        return Fault(0, "", "the assessment is not a regular file")
    try:
        with open(path, "rb", opener=_without_following) as handle:
            raw = handle.read(SIZE_CAP + 1)
    except OSError as exc:
        return Fault(0, "", "the assessment cannot be read: %s" % (exc.strerror or exc))
    if len(raw) > SIZE_CAP:
        return Fault(0, "", "the assessment is larger than %d bytes" % SIZE_CAP)
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError:
        return Fault(0, "", "the assessment is not ASCII text")


def _area_of(written):
    """The area a cell carries, or None where the cell carries no usable one."""
    try:
        value = float(written)
    except ValueError:
        return None
    if not math.isfinite(value) or not AREA_FLOOR <= value <= AREA_CEILING:
        return None
    return value


def read_sheet(path):
    """(findings, faults). Findings come back only for a sheet with no fault anywhere in it."""
    body = _ascii_body(path)
    if isinstance(body, Fault):
        return [], [body]
    try:
        lines = [[cell.strip() for cell in row]
                 for row in csv.reader(io.StringIO(body)) if any(cell.strip() for cell in row)]
    except csv.Error as exc:
        return [], [Fault(0, "", "the assessment is not valid CSV: %s" % exc)]
    if not lines:
        return [], [Fault(0, "", "the assessment is empty")]
    if tuple(lines[0]) != COLUMNS:
        return [], [Fault(1, "", "the first line must name exactly %s" % ", ".join(COLUMNS))]

    findings, faults, seen = [], [], set()
    for number, cells in enumerate(lines[1:], start=2):
        if len(cells) != len(COLUMNS):
            faults.append(Fault(number, "", "this row carries %d fields, not %d"
                                % (len(cells), len(COLUMNS))))
            continue
        valve, case, written, verdict = cells
        if valve not in VALVES:
            faults.append(Fault(number, "valve", "%r is not a valve of unit 400" % valve))
            continue
        if valve in seen:
            faults.append(Fault(number, "valve", "%s has a second row" % valve))
            continue
        seen.add(valve)
        if case not in sealed.CASES:
            faults.append(Fault(number, "governing_case", "%r names no contingency of the standard" % case))
            continue
        if verdict not in sealed.VERDICTS:
            faults.append(Fault(number, "verdict",
                                "%r is neither %s" % (verdict, " nor ".join(sealed.VERDICTS))))
            continue
        area = _area_of(written)
        if area is None:
            faults.append(Fault(number, "required_area_mm2",
                                "%r is not a finite area between %g and %g mm2"
                                % (written, AREA_FLOOR, AREA_CEILING)))
            continue
        findings.append(Finding(valve, case, area, verdict))

    missing = VALVES - seen
    if missing:
        faults.append(Fault(0, "valve", "no row for %s" % ", ".join(sorted(missing))))
    return ([] if faults else findings), faults


# --------------------------------------------------------------------------- judging
def assess(path):
    """Read the sheet and judge it. Never raises, whatever the file holds."""
    try:
        findings, faults = read_sheet(path)
    except Exception as exc:                        # nothing a submission contains may escape
        findings, faults = [], [Fault(0, "", "the assessment could not be read: %r" % exc)]
    total = len(sealed.IDS)
    if faults:
        return Report(False, 0, total, faults[0], {})
    judged = {}
    for found in findings:
        stands, margins = sealed.row_ok(found.valve, found.case, found.area, found.verdict)
        judged[found.valve] = {"governing_case": found.case, "required_area_mm2": found.area,
                               "verdict": found.verdict, "stands": bool(stands),
                               "margins": {name: round(float(value), 6) for name, value in margins.items()}}
    standing = sum(1 for shown in judged.values() if shown["stands"])
    return Report(standing == total, standing, total, None, judged)


def explain(report):
    """One line per valve, then the outcome, for the authoring scripts and the command line."""
    out = []
    if report.fault is not None:
        where = (" row %d" % report.fault.row) if report.fault.row else ""
        column = (" column %s" % report.fault.column) if report.fault.column else ""
        out.append("not read:%s%s: %s" % (where, column, report.fault.reason))
    for valve in sorted(report.findings):
        shown = report.findings[valve]
        margins = shown["margins"]
        out.append("%s %-3s %-22s %12.4f mm2 %-11s | contingency %s area %+.4f finding %s" % (
            valve, "ok" if shown["stands"] else "no", shown["governing_case"],
            shown["required_area_mm2"], shown["verdict"],
            "ok" if margins["case"] else "no", margins["area"],
            "ok" if margins["verdict"] else "no"))
    out.append("%d of %d findings stand: the sheet is %s"
               % (report.standing, report.total, "taken" if report.taken else "not taken"))
    return "\n".join(out)


if __name__ == "__main__":
    print(explain(assess(sys.argv[1] if len(sys.argv) > 1 else "/app/output/relief.csv")))
