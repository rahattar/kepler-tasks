"""Grades the submitted audit sheet against the sealed definition.

The submission is /app/output/diagnosis.csv with the header `chamber,cause,q_total_mbarl_s,s_eff_l_s` and one row
for each chamber of the fleet: the limiting cause MS-BP clause 6 names, the total gas load at the reference
condition in mbar L/s, and the actual effective pumping speed there in L/s.

A chamber is right when all three are right: the cause matches exactly, the gas load is within Q_TOL of the truth
and the speed within S_TOL. The sheet is accepted when at least GATE of the chambers are right.

The truth is computed from the sealed fleet (`sealed/fleet.py`, `sealed/bpphys.py`) at grading time, never from
running the reference solution.

The result must be a regular file (not a symlink) of at most 100 kB of ASCII text: the header line exactly, then
one row of four fields per chamber with none repeated, missing or unknown; the cause one of MS-BP's five names;
the two quantities finite positive numbers in the ranges below. Anything else is rejected, and no submission can
crash the grader.
"""
import csv
import io
import os
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "sealed"))
import bpphys as P                                                      # noqa: E402
import fleet as F                                                       # noqa: E402

HEADER = ["chamber", "cause", "q_total_mbarl_s", "s_eff_l_s"]
IDS = list(F.CHAMBER_IDS)
GATE = len(IDS)                     # every chamber must be right

# The allowance of one wrong chamber that earlier tasks carried is not used here, and the reason is measured in
# `authoring/evidence/plan_sweep.txt`: with an allowance of one, the audit test order is not load-bearing, because
# the reference passes with no order placed at all. Requiring every chamber makes the chamber whose own records
# cannot settle its cause decide the sheet, which is what the order is for. The gate is not a knife edge either:
# every sound method in `method_spread.txt` gets all ten chambers right, with 1.7x margin on the gas load and
# 2.1x on the speed, and every defective route in `route_study.txt` misses at least two chambers.
Q_TOL = 0.040                       # relative, on the total gas load
S_TOL = 0.030                       # relative, on the effective pumping speed
Q_RANGE = (1e-10, 1e-1)
S_RANGE = (1.0, 1e5)
MAX_BYTES = 100_000


class Reject(Exception):
    pass


def _num(text, what):
    try:
        v = float(text)
    except ValueError:
        raise Reject("%s is not a number: %r" % (what, text))
    if v != v or v in (float("inf"), float("-inf")):
        raise Reject("%s must be finite" % what)
    return v


def read_sheet(path):
    try:
        st = os.lstat(path)
    except OSError:
        raise Reject("no audit sheet at %s" % path)
    if not stat.S_ISREG(st.st_mode):
        raise Reject("the audit sheet is not a regular file")
    if st.st_size > MAX_BYTES:
        raise Reject("the audit sheet is too large")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        raw = f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise Reject("the audit sheet is too large")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise Reject("the audit sheet is not ASCII text")
    try:
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    except csv.Error as ex:
        raise Reject("the audit sheet is not valid CSV: %s" % ex)
    if not rows or rows[0] != HEADER:
        raise Reject("the first line must be exactly: %s" % ",".join(HEADER))
    out = {}
    for r in rows[1:]:
        if len(r) != 4:
            raise Reject("every row must have four fields: %r" % r)
        cid, cause, q, s = r
        if cid not in IDS:
            raise Reject("unknown chamber %r" % cid)
        if cid in out:
            raise Reject("chamber %s appears twice" % cid)
        if cause not in P.CAUSES:
            raise Reject("%s: cause %r is not one of %s" % (cid, cause, ", ".join(P.CAUSES)))
        qv = _num(q, "%s q_total_mbarl_s" % cid)
        sv = _num(s, "%s s_eff_l_s" % cid)
        if not Q_RANGE[0] <= qv <= Q_RANGE[1]:
            raise Reject("%s q_total_mbarl_s must be from %.0e to %.0e" % (cid, Q_RANGE[0], Q_RANGE[1]))
        if not S_RANGE[0] <= sv <= S_RANGE[1]:
            raise Reject("%s s_eff_l_s must be from %.0f to %.0e" % (cid, S_RANGE[0], S_RANGE[1]))
        out[cid] = (cause, qv, sv)
    if set(out) != set(IDS):
        raise Reject("the sheet must have one row for each of %s" % ", ".join(IDS))
    return out


def truth():
    return {cid: F.truth(F.BY[cid]) for cid in IDS}


def score(path):
    try:
        sub = read_sheet(path)
    except Reject as ex:
        return {"accepted": False, "npass": 0, "gate": GATE, "error": str(ex), "chambers": {}}
    tr = truth()
    out = {}
    for cid in IDS:
        cause, q, s = sub[cid]
        t = tr[cid]
        qdev = (q - t["q_total"]) / t["q_total"]
        sdev = (s - t["s_eff"]) / t["s_eff"]
        ok_cause = cause == t["cause"]
        ok_q = abs(qdev) <= Q_TOL
        ok_s = abs(sdev) <= S_TOL
        out[cid] = {"cause": cause, "cause_true": t["cause"], "ok_cause": ok_cause,
                    "q_total": q, "q_true": t["q_total"], "q_dev": round(qdev, 5), "ok_q": ok_q,
                    "s_eff": s, "s_true": t["s_eff"], "s_dev": round(sdev, 5), "ok_s": ok_s,
                    "ok": bool(ok_cause and ok_q and ok_s)}
    n = sum(v["ok"] for v in out.values())
    return {"accepted": n >= GATE, "npass": n, "gate": GATE, "chambers": out}


if __name__ == "__main__":
    r = score(sys.argv[1] if len(sys.argv) > 1 else "/app/output/diagnosis.csv")
    if "error" in r:
        print("rejected:", r["error"])
    for cid, v in r.get("chambers", {}).items():
        print("%s %s %-16s (%-16s) q %+7.2f%% %s  s %+7.2f%% %s" % (
            cid, "ok " if v["ok"] else "BAD", v["cause"], v["cause_true"],
            100 * v["q_dev"], "ok " if v["ok_q"] else "BAD",
            100 * v["s_dev"], "ok " if v["ok_s"] else "BAD"))
    print("%d of %d right (gate %d): %s" % (
        r["npass"], len(IDS), r["gate"], "accepted" if r["accepted"] else "rejected"))
