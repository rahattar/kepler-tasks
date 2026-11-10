"""Grades the submitted sound power sheet against the sealed definition.

The submission is /app/output/sound_power.csv with the header `machine,lw_63,lw_125,lw_250,lw_500,lw_1k,lw_2k,lw_4k,
lw_8k,lwa` and one row for each of C1, C2 and C3: the sound power level of the machine as it stands now in each of the
eight octave bands from 63 Hz to 8 kHz, and its A-weighted sound power level, in dB. Each of the 27 values is right
when it is within isim.TOL of the sealed definition, and the sheet is accepted only when all 27 are.

The result must be a regular file (not a symlink) of at most 100 kB of ASCII text: the header line exactly, then three
rows of ten fields with no machine repeated, missing or unknown, every level a finite decimal number from 40 to 160.
Blank lines and surrounding spaces are ignored. Anything else is rejected and never crashes the grader.
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

IDS = list(S.MACHINES)
KEYS = [S.LABEL[b] for b in S.BANDS] + ["A"]
HEADER = ["machine"] + ["lw_%s" % S.LABEL[b] for b in S.BANDS] + ["lwa"]
GATE = len(IDS) * len(KEYS)
LO, HI = decimal.Decimal(40), decimal.Decimal(160)


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
        raise Reject("%s must be from 40 to 160 dB" % what)
    return float(v)


def read_sheet(path):
    try:
        st = os.lstat(path)
    except OSError:
        raise Reject("no sound power sheet at %s" % path)
    if not stat.S_ISREG(st.st_mode):
        raise Reject("the sound power sheet is not a regular file")
    if st.st_size > 100_000:
        raise Reject("the sound power sheet is too large")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        raw = f.read()
    try:
        body = raw.decode("ascii")
    except UnicodeDecodeError:
        raise Reject("the sound power sheet is not ASCII text")
    try:
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(body)) if any(c.strip() for c in r)]
    except csv.Error as ex:
        raise Reject("the sound power sheet is not valid CSV: %s" % ex)
    if not rows or rows[0] != HEADER:
        raise Reject("the first line must be exactly: %s" % ",".join(HEADER))
    out = {}
    for r in rows[1:]:
        if len(r) != len(HEADER):
            raise Reject("every row must have %d fields: %r" % (len(HEADER), r))
        mid = r[0]
        if mid not in IDS:
            raise Reject("unknown machine %r" % mid)
        if mid in out:
            raise Reject("machine %s appears twice" % mid)
        out[mid] = {k: _dec(v, "%s %s" % (mid, h)) for k, v, h in zip(KEYS, r[1:], HEADER[1:])}
    if set(out) != set(IDS):
        raise Reject("the sheet must have one row for each of %s" % ", ".join(IDS))
    return out


def score(path):
    try:
        sel = read_sheet(path)
    except Reject as ex:
        return {"accepted": False, "npass": 0, "gate": GATE, "error": str(ex), "machines": {}}
    truth, out, n = S.truth(), {}, 0
    for m in IDS:
        d = {k: sel[m][k] - truth[m][k] for k in KEYS}
        ok = {k: abs(d[k]) <= S.TOL for k in KEYS}
        n += sum(ok.values())
        out[m] = {"values": {k: sel[m][k] for k in KEYS}, "errors": {k: round(d[k], 3) for k in KEYS},
                  "ok": {k: bool(ok[k]) for k in KEYS}, "right": sum(ok.values()), "worst": round(
                      max(abs(v) for v in d.values()), 3)}
    return {"accepted": n >= GATE, "npass": n, "gate": GATE, "tol": S.TOL, "machines": out}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/sound_power.csv")
    if "error" in r:
        print("rejected:", r["error"])
    for m, v in r.get("machines", {}).items():
        print("%s %s %2d of %d right, worst %+.2f dB | %s" % (
            m, "ok " if v["right"] == len(KEYS) else "BAD", v["right"], len(KEYS), v["worst"],
            " ".join("%s %+.2f%s" % (k, v["errors"][k], "" if v["ok"][k] else "*") for k in KEYS)))
    print("%d of %d values right (tolerance %.1f dB, gate %d): %s" % (
        r["npass"], GATE, r.get("tol", S.TOL), r["gate"], "accepted" if r["accepted"] else "rejected"))
