"""Grades the submitted sheet of cylinder limits against the sealed definition.

The submission is /app/output/cylinder_limits.csv with the header `cylinder,field_pressure_bar,governing_limit`
and one row for each of the six cylinders: the lowest field pressure at which the cylinder may be run while the
unit holds its contract flow, in bar absolute, and the name of the requirement of RC-4 that governs it. The pressure is right when it is within isim.TOL
of the sealed definition, relatively; the requirement is right when it is the one the definition names. The sheet is
accepted only when all twelve values are right.

A pressure at the edge of the band is accepted: the comparison carries an allowance of 1e-12 relative so that the
edge does not turn on the binary representation of the printed number.

The result must be a regular file (not a symlink) of at most 100 kB of ASCII text: the header line exactly, then six
rows of three fields with no cylinder repeated, missing or unknown, every pressure a finite decimal number from 1 to
500 bar, and every requirement one of the six names the standard uses. Blank lines and surrounding spaces are
ignored. Anything else is rejected and never crashes the grader.
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

IDS = sorted(S.CYL)
HEADER = ["cylinder", "field_pressure_bar", "governing_limit"]
GATE = 2 * len(IDS)
LO, HI = decimal.Decimal(1), decimal.Decimal(500)


class Reject(Exception):
    pass


def _dec(t, what):
    try:
        v = decimal.Decimal(t)
    except decimal.InvalidOperation:
        raise Reject("%s is not a number: %r" % (what, t))
    if not v.is_finite():
        raise Reject("%s must be finite" % what)
    if not LO <= v <= HI:
        raise Reject("%s must be from 1 to 500 bar" % what)
    return float(v)


def read_sheet(path):
    try:
        st = os.lstat(path)
    except OSError:
        raise Reject("no sheet at %s" % path)
    if not stat.S_ISREG(st.st_mode):
        raise Reject("the sheet is not a regular file")
    if st.st_size > 100_000:
        raise Reject("the sheet is too large")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        raw = f.read()
    try:
        body = raw.decode("ascii")
    except UnicodeDecodeError:
        raise Reject("the sheet is not ASCII text")
    try:
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(body)) if any(c.strip() for c in r)]
    except csv.Error as ex:
        raise Reject("the sheet is not valid CSV: %s" % ex)
    if not rows or rows[0] != HEADER:
        raise Reject("the first line must be exactly: %s" % ",".join(HEADER))
    out = {}
    for r in rows[1:]:
        if len(r) != len(HEADER):
            raise Reject("every row must have %d fields: %r" % (len(HEADER), r))
        cid = r[0]
        if cid not in IDS:
            raise Reject("unknown cylinder %r" % cid)
        if cid in out:
            raise Reject("cylinder %s appears twice" % cid)
        if r[2] not in S.REQ:
            raise Reject("%s: the governing limit must be one of %s, not %r" % (cid, " ".join(S.REQ), r[2]))
        out[cid] = (_dec(r[1], "%s field pressure" % cid), r[2])
    if set(out) != set(IDS):
        raise Reject("the sheet must have one row for each of %s" % ", ".join(IDS))
    return out


def score(path):
    try:
        sel = read_sheet(path)
    except Reject as ex:
        return {"accepted": False, "npass": 0, "gate": GATE, "error": str(ex), "cylinders": {}}
    truth, out, n = S.truth(), {}, 0
    for cid in IDS:
        tp, tq = truth[cid]
        gp, gq = sel[cid]
        rel = (gp - tp) / tp
        ok_p = abs(rel) <= S.TOL + 1e-12
        ok_q = gq == tq
        n += int(ok_p) + int(ok_q)
        out[cid] = {"suction_pressure_bar": gp, "governing_limit": gq,
                    "error_relative": round(rel, 6), "error_bar": round(gp - tp, 4),
                    "pressure_ok": bool(ok_p), "limit_ok": bool(ok_q),
                    "right": int(ok_p) + int(ok_q)}
    return {"accepted": n >= GATE, "npass": n, "gate": GATE, "tol": S.TOL, "cylinders": out}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/cylinder_limits.csv")
    if "error" in r:
        print("rejected:", r["error"])
    for cid, v in r.get("cylinders", {}).items():
        print("%-3s %s %8.2f bar %+7.3f %% %-22s %s" % (
            cid, "ok " if v["right"] == 2 else "BAD", v["suction_pressure_bar"], 100.0 * v["error_relative"],
            v["governing_limit"], "" if v["right"] == 2 else
            "(%s%s)" % ("pressure " if not v["pressure_ok"] else "", "limit" if not v["limit_ok"] else "")))
    print("%d of %d values right (tolerance %.1f per cent, gate %d): %s" % (
        r["npass"], GATE, 100.0 * r.get("tol", S.TOL), r["gate"], "accepted" if r["accepted"] else "rejected"))
