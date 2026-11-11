"""Grades the submitted sentencing sheet against the sealed definition.

The submission is /app/output/form.csv with the header `feature,form_um,verdict` and one row for each of the 14
features: the feature's form error in micrometres, to the characteristic its drawing calls for, and its sentence.
For each feature the sealed definition (isim.py) holds the minimum-zone form error of the true surface and the
sentence that FM-7 gives it. A feature is right when the reported form error is within TOL micrometres of the
sealed one and the sentence matches exactly. The sheet is accepted only when all 14 features are right.

The result must be a regular file (not a symlink) of at most 100 kB of ASCII text: the header line exactly, then 14
rows of three fields with no feature repeated, missing or unknown; form_um a finite decimal number from 0 to 500
with at most two decimals; verdict one of accept, reject_size, reject_form, reject_both. Blank lines and
surrounding spaces are ignored. Anything else is rejected and never crashes the grader.
"""
import csv
import decimal
import io
import os
import re
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "sealed"))
import isim as S  # noqa: E402

IDS = list(S.ORDER)
GATE = len(IDS)
HEADER = ["feature", "form_um", "verdict"]
VERDICTS = ("accept", "reject_size", "reject_form", "reject_both")
TOL = 1.2          # um on the reported form error


class Reject(Exception):
    pass


TWO_DECIMALS = re.compile(r"[0-9]+\.[0-9]{2}")

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
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise Reject("the sheet is not ASCII text")
    # The instruction's contract, enforced as written and no further:
    #   "the exact header feature,form_um,verdict"   - the first line, character for character
    #   "one row for each of the 14 features"        - 14 rows, each feature once, and no other line
    #   "form_um ... to two decimal places"          - digits, a point, exactly two digits; nothing else
    #   "verdict must be one of ..."                 - one of the four words, exactly
    # No field is trimmed or coerced: a field with a space in it is not the field the instruction asks for.
    # What the instruction does not constrain is left alone: the order of the rows, whether lines end in LF or
    # CRLF (Python's csv module writes CRLF by default), whether the last line has a terminator, empty lines
    # after the header, and CSV quoting of a row's fields - a quoted 12.34 is still 12.34 to two decimal places.
    # The header gets none of that latitude, because "exact" is the instruction's own word for it.
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()                                   # the terminator of the last line, if it has one
    lines = [ln[:-1] if ln.endswith("\r") else ln for ln in lines]
    if not lines or lines[0] != ",".join(HEADER):
        raise Reject("the first line must be exactly: %s" % ",".join(HEADER))
    body = [ln for ln in lines[1:] if ln != ""]
    try:
        rows = list(csv.reader(io.StringIO("\n".join(body) + "\n"), strict=True)) if body else []
    except csv.Error as ex:
        raise Reject("the sheet is not valid CSV: %s" % ex)
    out = {}
    for r in rows:
        if len(r) != 3:
            raise Reject("every row must have three fields: %r" % r)
        fid, form, verdict = r
        if fid not in IDS:
            raise Reject("unknown feature %r" % fid)
        if fid in out:
            raise Reject("feature %s appears twice" % fid)
        if not TWO_DECIMALS.fullmatch(form):
            raise Reject("%s form_um must be a number written to two decimal places, as in 12.34: %r"
                         % (fid, form))
        if verdict not in VERDICTS:
            raise Reject("%s verdict must be one of %s" % (fid, ", ".join(VERDICTS)))
        out[fid] = (float(form), verdict)
    if set(out) != set(IDS):
        raise Reject("the sheet must have one row for each of %s" % ", ".join(IDS))
    return out


def score(path):
    try:
        sel = read_sheet(path)
    except Reject as ex:
        return {"accepted": False, "npass": 0, "gate": GATE, "tol_um": TOL, "error": str(ex), "features": {}}
    out = {}
    for k in IDS:
        form, verdict = sel[k]
        t = S.truth(k)
        de = form - t["form"]
        form_ok = abs(de) <= TOL
        v_ok = verdict == t["verdict"]
        out[k] = {"form_um": form, "form_true_um": round(t["form"], 3), "form_error_um": round(de, 3),
                  "verdict": verdict, "verdict_true": t["verdict"], "form_ok": bool(form_ok),
                  "verdict_ok": bool(v_ok), "ok": bool(form_ok and v_ok)}
    n = sum(v["ok"] for v in out.values())
    return {"accepted": n >= GATE, "npass": n, "gate": GATE, "tol_um": TOL, "features": out}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/form.csv")
    if "error" in r:
        print("rejected:", r["error"])
    for k, v in r.get("features", {}).items():
        print("%-6s %s form %6.2f (true %6.2f, %+.2f) %-12s (true %-12s)" % (
            k, "ok " if v["ok"] else "BAD", v["form_um"], v["form_true_um"], v["form_error_um"],
            v["verdict"], v["verdict_true"]))
    print("%d of %d right (gate %d): %s" % (r["npass"], GATE, r["gate"], "accepted" if r["accepted"] else "rejected"))
