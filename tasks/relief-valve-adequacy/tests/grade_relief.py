"""Grades the submitted relief assessment against the sealed definition.

The submission is /app/output/relief.csv with the header `valve,governing_case,required_area_mm2,verdict` and one
row for each of the nine valves: the contingency that requires the largest relieving capacity, the effective
orifice area it requires in mm2, and whether the installed valve is adequate under plant standard RP-7. A row is
right when all three agree with the sealed definition (isim.py): the contingency name exactly, the area within
isim.TOL relative, and the verdict exactly. The sheet is accepted only when all nine rows are right.

A value exactly at the edge of the area band is compared with a small allowance on the comparison itself, so that
the result is not decided by binary rounding.

The result must be a regular file (not a symlink) of at most 100 kB of ASCII text: the header line exactly, then
nine rows of four fields with no valve repeated, missing or unknown; governing_case one of the names the standard
defines; required_area_mm2 a decimal number from 0.001 to 100000, written with as many figures as the solver likes;
verdict either adequate or inadequate. Blank lines and surrounding spaces are ignored. Anything else is rejected and never
crashes the grader.
"""
import csv
import decimal
import io
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "sealed"))
import isim as S  # noqa: E402

IDS = list(S.IDS)
GATE = len(IDS)
HEADER = ["valve", "governing_case", "required_area_mm2", "verdict"]
AREA_MIN, AREA_MAX = decimal.Decimal("0.001"), decimal.Decimal("100000")


class Reject(Exception):
    pass


def read_sheet(path):
    try:
        st = os.lstat(path)
    except OSError:
        raise Reject("no assessment at %s" % path)
    if not stat.S_ISREG(st.st_mode):
        raise Reject("the assessment is not a regular file")
    if st.st_size > 100_000:
        raise Reject("the assessment is too large")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise Reject("the assessment is not ASCII text")
    try:
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    except csv.Error as ex:
        raise Reject("the assessment is not valid CSV: %s" % ex)
    if not rows or rows[0] != HEADER:
        raise Reject("the first line must be exactly: %s" % ",".join(HEADER))
    out = {}
    for r in rows[1:]:
        if len(r) != 4:
            raise Reject("every row must have four fields: %r" % r)
        vid, case, area, verd = r
        if vid not in IDS:
            raise Reject("unknown valve %r" % vid)
        if vid in out:
            raise Reject("valve %s appears twice" % vid)
        if case not in S.CASES:
            raise Reject("%s governing_case must be one of %s" % (vid, ", ".join(S.CASES)))
        if verd not in S.VERDICTS:
            raise Reject("%s verdict must be one of %s" % (vid, ", ".join(S.VERDICTS)))
        try:
            a = decimal.Decimal(area)
        except decimal.InvalidOperation:
            raise Reject("%s required_area_mm2 is not a number: %r" % (vid, area))
        if not a.is_finite():
            raise Reject("%s required_area_mm2 must be finite" % vid)
        if not AREA_MIN <= a <= AREA_MAX:
            raise Reject("%s required_area_mm2 must be from %s to %s" % (vid, AREA_MIN, AREA_MAX))
        out[vid] = (case, float(a), verd)
    if set(out) != set(IDS):
        raise Reject("the assessment must have one row for each of %s" % ", ".join(IDS))
    return out


def score(path):
    try:
        sel = read_sheet(path)
    except Reject as ex:
        return {"accepted": False, "npass": 0, "gate": GATE, "error": str(ex), "valves": {}}
    valves = {}
    for vid in IDS:
        case, area, verd = sel[vid]
        ok, m = S.row_ok(vid, case, area, verd)
        valves[vid] = {"governing_case": case, "required_area_mm2": area, "verdict": verd,
                       "ok": bool(ok), "margins": {k: round(float(v), 6) for k, v in m.items()}}
    n = sum(v["ok"] for v in valves.values())
    return {"accepted": n >= GATE, "npass": n, "gate": GATE, "valves": valves}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/relief.csv")
    if "error" in r:
        print("rejected:", r["error"])
    for k, v in r.get("valves", {}).items():
        m = v["margins"]
        print("%s %s %-22s %12.4f mm2 %-11s | case %s area %+.4f verdict %s" % (
            k, "ok " if v["ok"] else "BAD", v["governing_case"], v["required_area_mm2"], v["verdict"],
            "ok" if m["case"] else "no", m["area"], "ok" if m["verdict"] else "no"))
    print("%d of %d right (gate %d): %s" % (r["npass"], GATE, r["gate"],
                                            "accepted" if r["accepted"] else "rejected"))
