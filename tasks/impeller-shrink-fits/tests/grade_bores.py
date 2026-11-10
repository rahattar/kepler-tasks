"""Grades the submitted bore sheet against the sealed definition.

The submission is /app/output/bore_sheet.csv with the header `part,bore_mm,oven_C` and one row for each of S1 to S6,
BD and TC: the bore diameter to which the part is finish-honed (mm at 20 C, at most three decimals) and its oven
temperature (a whole degree C). For each part the sealed model (isim.py) checks plant standard RS-3 as the rotor is
now: retention at the least interference and hub stress at the greatest, both at rest and at trip speed in running,
and the assembly clearance at the oven temperature, which must not exceed the part's heating limit. The sheet is
accepted only when all 8 parts are right.

The result must be a regular file (not a symlink) of at most 100 kB of ASCII text: the header line exactly, then 8
rows of three fields with no part repeated, missing or unknown; bore_mm a decimal number from 50 to 200 with at most
three decimals; oven_C a whole number from 20 to 1000 (an integral value such as 250.0 is accepted). Blank lines and
surrounding spaces are ignored. Anything else is rejected and never crashes the grader.
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

IDS = list(S.PARTS)
GATE = len(IDS)
HEADER = ["part", "bore_mm", "oven_C"]


class Reject(Exception):
    pass


def _dec(text, what):
    try:
        v = decimal.Decimal(text)
    except decimal.InvalidOperation:
        raise Reject("%s is not a number: %r" % (what, text))
    if not v.is_finite():
        raise Reject("%s must be finite" % what)
    return v


def read_sheet(path):
    try:
        st = os.lstat(path)
    except OSError:
        raise Reject("no bore sheet at %s" % path)
    if not stat.S_ISREG(st.st_mode):
        raise Reject("the bore sheet is not a regular file")
    if st.st_size > 100_000:
        raise Reject("the bore sheet is too large")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise Reject("the bore sheet is not ASCII text")
    try:
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    except csv.Error as ex:
        raise Reject("the bore sheet is not valid CSV: %s" % ex)
    if not rows or rows[0] != HEADER:
        raise Reject("the first line must be exactly: %s" % ",".join(HEADER))
    out = {}
    for r in rows[1:]:
        if len(r) != 3:
            raise Reject("every row must have three fields: %r" % r)
        pid, b, t = r
        if pid not in IDS:
            raise Reject("unknown part %r" % pid)
        if pid in out:
            raise Reject("part %s appears twice" % pid)
        bd = _dec(b, "%s bore_mm" % pid)
        if bd.as_tuple().exponent < -3:
            raise Reject("%s bore_mm has more than three decimals" % pid)
        if not decimal.Decimal(50) <= bd <= decimal.Decimal(200):
            raise Reject("%s bore_mm must be from 50 to 200" % pid)
        td = _dec(t, "%s oven_C" % pid)
        if td != td.to_integral_value():
            raise Reject("%s oven_C must be a whole number" % pid)
        if not 20 <= td <= 1000:
            raise Reject("%s oven_C must be from 20 to 1000" % pid)
        out[pid] = (float(bd), int(td))
    if set(out) != set(IDS):
        raise Reject("the sheet must have one row for each of %s" % ", ".join(IDS))
    return out


def score(path):
    try:
        sel = read_sheet(path)
    except Reject as ex:
        return {"accepted": False, "npass": 0, "gate": GATE, "error": str(ex), "parts": {}}
    parts = {}
    for k in IDS:
        b, T = sel[k]
        ok, m = S.part_ok(k, b, T)
        parts[k] = {"bore_mm": b, "oven_C": T, "ok": bool(ok), "margins": {q: round(float(v), 4) for q, v in m.items()}}
    n = sum(v["ok"] for v in parts.values())
    return {"accepted": n >= GATE, "npass": n, "gate": GATE, "parts": parts}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/bore_sheet.csv")
    if "error" in r:
        print("rejected:", r["error"])
    for k, v in r.get("parts", {}).items():
        m = v["margins"]
        print("%s %s %8.3f mm %3d C | retention %+.3f stress %+.3f clearance %+.3f limit %+.2f" % (
            k, "ok " if v["ok"] else "BAD", v["bore_mm"], v["oven_C"], m["ret"], m["stress"], m["clear"], m["limit"]))
    print("%d of %d right (gate %d): %s" % (r["npass"], GATE, r["gate"], "accepted" if r["accepted"] else "rejected"))
