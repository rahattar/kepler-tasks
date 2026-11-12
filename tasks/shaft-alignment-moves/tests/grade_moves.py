"""Puts a submitted sheet of foot moves onto the sealed unit and says which trains it leaves aligned.

A train is aligned when, with the submitted moves made cold and both machines then brought to their running
position, the movable shaft's centreline lies within the sealed tolerance of the stationary shaft's at both
hubs' reading planes, in height and sideways. That is AP-12 section 7, worked from the sealed definition in
./sealed and from nothing the engineer wrote except the sheet itself. No reference answer is involved: the
moves are applied to the train and the result is measured.

The sheet is read as the task statement describes it and no more loosely: the header as given, one row for
every train of the unit and for no other, four moves a row, each written as a plain decimal with exactly three
places. What the statement does not settle is left alone: the order of the rows, the line ending, empty lines
after the header, quoting, and blanks around a field.
"""
import csv
import io
import json
import os
import re
import stat
import sys
from dataclasses import dataclass, field

sys.dont_write_bytecode = True
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "sealed"))
import unit3  # noqa: E402

HEADER = ("tag", "v_front_mm", "v_rear_mm", "h_front_mm", "h_rear_mm")
MOVES = HEADER[1:]
PLACES = 3
LARGEST_SHEET = 200000                       # bytes; an honest sheet is under two thousand
_THREE_PLACES = re.compile(r"[+-]?\d*\.\d{%d}" % PLACES)
_WHERE = ("height at the stationary hub", "height at the movable hub",
          "sideways at the stationary hub", "sideways at the movable hub")


class Unreadable(Exception):
    """The sheet is not the document the task statement describes."""


@dataclass
class Outcome:
    accepted: bool = False
    aligned: int = 0
    trains: int = 0
    unreadable: str = ""
    detail: dict = field(default_factory=dict)


def sealed_trains():
    with open(os.path.join(_HERE, "sealed", "seed.json")) as handle:
        return unit3.build(json.load(handle)["seed"])


def _text(path):
    try:
        found = os.lstat(path)
    except OSError:
        raise Unreadable("there is no sheet at %s" % os.path.basename(path))
    if stat.S_ISLNK(found.st_mode):
        raise Unreadable("the sheet is a symbolic link")
    if not stat.S_ISREG(found.st_mode):
        raise Unreadable("the sheet is not a regular file")
    if found.st_size > LARGEST_SHEET:
        raise Unreadable("the sheet is larger than %d bytes" % LARGEST_SHEET)
    with open(path, "rb") as handle:
        raw = handle.read(LARGEST_SHEET + 1)
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError:
        raise Unreadable("the sheet is not ASCII text")


def _move(written, tag, column):
    figure = written.strip()
    if not _THREE_PLACES.fullmatch(figure):
        raise Unreadable("%s %s: %r is not a move written to %d decimal places" % (tag, column, written, PLACES))
    return float(figure)


def read_sheet(path, tags):
    """The submitted moves as {tag: (v_front, v_rear, h_front, h_rear)}, or Unreadable."""
    text = _text(path)
    if not text.strip():
        raise Unreadable("the sheet is empty")
    try:
        records = list(csv.reader(io.StringIO(text, newline="")))
    except csv.Error as problem:
        raise Unreadable("the sheet is not CSV: %s" % problem)
    if tuple(records[0]) != HEADER:
        raise Unreadable("the first line must be exactly %s" % ",".join(HEADER))
    moves = {}
    for record in records[1:]:
        if not record:
            continue
        if len(record) != len(HEADER):
            raise Unreadable("a row carries %d fields, not %d" % (len(record), len(HEADER)))
        tag = record[0].strip()
        if tag not in tags:
            raise Unreadable("%r is not a train of the unit" % record[0])
        if tag in moves:
            raise Unreadable("%s has a second row" % tag)
        moves[tag] = tuple(_move(written, tag, column) for written, column in zip(record[1:], MOVES))
    absent = sorted(set(tags) - set(moves))
    if absent:
        raise Unreadable("no row for %s" % ", ".join(absent))
    return moves


def assess(path):
    trains = sealed_trains()
    outcome = Outcome(trains=len(trains))
    try:
        sheet = read_sheet(path, trains)
    except Unreadable as problem:
        outcome.unreadable = str(problem)
        return outcome
    for tag in sorted(trains):
        left = unit3.residual(trains[tag], sheet[tag])
        worst = max(range(len(left)), key=lambda i: abs(left[i]))
        good = abs(left[worst]) <= unit3.TOL
        outcome.aligned += good
        outcome.detail[tag] = {"aligned": bool(good), "worst_mm": round(left[worst], 4), "at": _WHERE[worst]}
    outcome.accepted = outcome.aligned == outcome.trains
    return outcome


def explain(outcome):
    if outcome.unreadable:
        return "the sheet was not read: %s" % outcome.unreadable
    lines = ["%d of %d trains are left aligned" % (outcome.aligned, outcome.trains)]
    for tag, row in outcome.detail.items():
        if not row["aligned"]:
            lines.append("  %-8s %+.3f mm in %s, against %.2f" % (tag, row["worst_mm"], row["at"], unit3.TOL))
    return "\n".join(lines)


if __name__ == "__main__":
    result = assess(sys.argv[1] if len(sys.argv) > 1 else "/app/output/moves.csv")
    print(explain(result))
    sys.exit(0 if result.accepted else 1)
