"""Grades a submitted flare load study of unit 400 against the sealed definition.

One row per contingency: the relief devices that discharge under it, the total mass flow that reaches the flare
header, and the pressure that flow raises at the header's inlet. A row stands only if all three agree with the
sealed definition - the devices exactly, the load inside isim.TOL relative, the pressure inside isim.TOL
relative or, where the sealed pressure is under isim.BACK_FLOOR, under that floor as well - and the study is
taken only when every contingency's row stands.

The reader is built from a table of column specs, one parser to a column, so that what will be accepted is
stated once in CELLS rather than spread through the code. A cell that cannot be parsed raises Rejected, which
carries the line, the column and the reason; the first such fault stops the sheet being read, because a study
that cannot be read whole is not graded at all. Nothing a submission can contain escapes to the caller.

What is accepted: a regular file, not a link, of at most SIZE_CAP bytes of ASCII; the four column names in order
on the first line; then one row for each contingency the standard names, in any order, none twice and none
unknown. Devices may be separated by semicolons, spaces or commas and given in any order; the word none, a dash,
an empty cell or a cell of separators alone all mean that nothing discharges, which is graded as that claim
rather than treated as a fault. The two numbers may carry as many figures as the submitter likes, plain or in
exponent form, so long as they are finite, not negative and within their ceilings. Blank lines are skipped and
surrounding space ignored.
"""
import collections
import csv
import io
import math
import os
import re
import stat
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sealed"))
import isim as sealed  # noqa: E402

COLUMNS = ("contingency", "devices", "load_kg_per_h", "header_inlet_barg")
SIZE_CAP = 100_000
LOAD_CEILING = 1.0e7
PRESSURE_CEILING = 1.0e3
EMPTY = ("none", "-", "")
SEPARATORS = re.compile(r"[;,\s]+")

Row = collections.namedtuple("Row", "contingency devices load back")
Fault = collections.namedtuple("Fault", "line column reason")
Report = collections.namedtuple("Report", "taken standing total fault rows")


class Rejected(Exception):
    """A fault that stops the sheet being read. Carries where it was and what was wrong with it."""

    def __init__(self, line, column, reason):
        Exception.__init__(self, reason)
        self.fault = Fault(line, column, reason)


# --------------------------------------------------------------------------- what each column accepts
def parse_contingency(written, seen):
    if written not in sealed.CONTINGENCIES:
        raise Rejected(0, "contingency", "%r is not a contingency of the standard" % written)
    if written in seen:
        raise Rejected(0, "contingency", "%s has a second line" % written)
    return written


def parse_devices(written, seen):
    if written.strip().lower() in EMPTY:
        return ()
    named = [part for part in SEPARATORS.split(written.strip()) if part]
    if not named:
        return ()
    unknown = [part for part in named if part not in sealed.IDS]
    if unknown:
        raise Rejected(0, "devices", "%r is not a relief device of this unit" % unknown[0])
    if len(set(named)) != len(named):
        raise Rejected(0, "devices", "%r names a device twice" % written)
    return tuple(sorted(named))


def bounded_number(column, ceiling, units):
    def parse(written, seen):
        try:
            value = float(written)
        except ValueError:
            raise Rejected(0, column, "%r is not a number" % written)
        if not math.isfinite(value) or value < 0.0 or value > ceiling:
            raise Rejected(0, column, "%r is not a %s from 0 to %g" % (written, units, ceiling))
        return value
    return parse


CELLS = (("contingency", parse_contingency),
         ("devices", parse_devices),
         ("load_kg_per_h", bounded_number("load_kg_per_h", LOAD_CEILING, "load in kg/h")),
         ("header_inlet_barg", bounded_number("header_inlet_barg", PRESSURE_CEILING, "pressure in barg")))


# --------------------------------------------------------------------------- reading
def ascii_text(path):
    """The study's text. Anything that is not a plain readable ASCII file of its own is a fault."""
    try:
        mode = os.lstat(path).st_mode
    except OSError:
        raise Rejected(0, "", "there is no study at %s" % path)
    if stat.S_ISLNK(mode):
        raise Rejected(0, "", "the study is a symbolic link")
    if not stat.S_ISREG(mode):
        raise Rejected(0, "", "the study is not a regular file")
    try:
        with open(path, "rb", opener=lambda name, flags: os.open(name, flags | os.O_NOFOLLOW)) as handle:
            raw = handle.read(SIZE_CAP + 1)
    except OSError as exc:
        raise Rejected(0, "", "the study cannot be read: %s" % (exc.strerror or exc))
    if len(raw) > SIZE_CAP:
        raise Rejected(0, "", "the study is larger than %d bytes" % SIZE_CAP)
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError:
        raise Rejected(0, "", "the study is not ASCII text")


def body_lines(text):
    """Every line that carries something, the column names checked off the first of them."""
    try:
        lines = [[cell.strip() for cell in row] for row in csv.reader(io.StringIO(text))
                 if any(cell.strip() for cell in row)]
    except csv.Error as exc:
        raise Rejected(0, "", "the study is not valid CSV: %s" % exc)
    if not lines:
        raise Rejected(0, "", "the study is empty")
    if tuple(lines[0]) != COLUMNS:
        raise Rejected(1, "", "the first line must name exactly %s" % ", ".join(COLUMNS))
    return lines[1:]


def read_sheet(path):
    """The rows the study carries. Raises Rejected on the first thing in it that cannot be read."""
    rows, seen = [], set()
    for number, cells in enumerate(body_lines(ascii_text(path)), start=2):
        if len(cells) != len(COLUMNS):
            raise Rejected(number, "", "this line carries %d fields, not %d" % (len(cells), len(COLUMNS)))
        values = []
        for written, (name, parse) in zip(cells, CELLS):
            try:
                values.append(parse(written, seen))
            except Rejected as bad:
                raise Rejected(number, bad.fault.column, bad.fault.reason)
        seen.add(values[0])
        rows.append(Row(*values))
    missing = set(sealed.CONTINGENCIES) - seen
    if missing:
        raise Rejected(0, "contingency", "no line for %s" % ", ".join(sorted(missing)))
    return rows


# --------------------------------------------------------------------------- judging
def assess(path):
    """Read the study and judge it. Never raises, whatever the file holds."""
    total = len(sealed.CONTINGENCIES)
    try:
        rows = read_sheet(path)
    except Rejected as bad:
        return Report(False, 0, total, bad.fault, {})
    except Exception as exc:                        # nothing a submission contains may escape
        return Report(False, 0, total, Fault(0, "", "the study could not be read: %r" % exc), {})
    judged = {}
    for row in rows:
        stands, margins = sealed.row_ok(row.contingency, row.devices, row.load, row.back)
        judged[row.contingency] = {
            "devices": list(row.devices), "load_kg_per_h": row.load, "header_inlet_barg": row.back,
            "stands": bool(stands),
            "margins": {name: round(float(value), 6) for name, value in margins.items()}}
    standing = sum(1 for shown in judged.values() if shown["stands"])
    return Report(standing == total, standing, total, None, judged)


def explain(report):
    """One line per contingency, then the outcome, for the authoring scripts and the command line."""
    out = []
    if report.fault is not None:
        where = (" line %d" % report.fault.line) if report.fault.line else ""
        column = (" column %s" % report.fault.column) if report.fault.column else ""
        out.append("not read:%s%s: %s" % (where, column, report.fault.reason))
    for name in sorted(report.rows):
        shown = report.rows[name]
        margins = shown["margins"]
        out.append("%-24s %-3s %-34s %11.1f kg/h %8.4f barg | devices %s load %+.4f pressure %+.4f" % (
            name, "ok" if shown["stands"] else "no", " ".join(shown["devices"]) or "none",
            shown["load_kg_per_h"], shown["header_inlet_barg"],
            "ok" if margins["valves"] else "no", margins["load"], margins["back"]))
    out.append("%d of %d contingencies stand: the study is %s"
               % (report.standing, report.total, "taken" if report.taken else "not taken"))
    return "\n".join(out)


if __name__ == "__main__":
    print(explain(assess(sys.argv[1] if len(sys.argv) > 1 else "/app/output/flare_load.csv")))
