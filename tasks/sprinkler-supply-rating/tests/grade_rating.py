"""Scores a rating sheet against the sealed rating.

The sheet is `riser,limit,p_base_psi,q_avail_gpm` with one row for each of SR01 to SR10. A row is right when its
limit is the sealed one, its pressure is within P_BAND of the sealed pressure and its flow within Q_BAND of the
sealed flow. The sheet is accepted only when every row is right.
"""
import json
import math
import os

HEADER = "riser,limit,p_base_psi,q_avail_gpm"
LIMITS = ("city-main", "backflow", "lead-in", "valve", "check")
P_BAND = 0.04            # of the sealed pressure
Q_BAND = 0.04            # of the sealed flow
MAX_BYTES = 100000
SEALED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sealed", "rating.json")


class Refused(Exception):
    """The sheet is not in the form the instruction states."""


def sealed():
    with open(SEALED) as f:
        return json.load(f)


def number(text, what, rid):
    try:
        v = float(text)
    except ValueError:
        raise Refused("%s: %s is not a number: %r" % (rid, what, text))
    if not math.isfinite(v):
        raise Refused("%s: %s is not finite" % (rid, what))
    return v


def read_sheet(path, risers):
    if not os.path.isfile(path) or os.path.islink(path):
        raise Refused("no regular file at %s" % path)
    raw = open(path, "rb").read()
    if len(raw) > MAX_BYTES:
        raise Refused("sheet larger than %d bytes" % MAX_BYTES)
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise Refused("sheet is not ASCII text")
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n")]
    lines = [ln for ln in lines if ln]
    if not lines or lines[0] != HEADER:
        raise Refused("first line is not the header %r" % HEADER)
    rows = {}
    for ln in lines[1:]:
        cells = [c.strip() for c in ln.split(",")]
        if len(cells) != 4:
            raise Refused("row does not have four fields: %r" % ln)
        rid, limit, p, q = cells
        if rid not in risers:
            raise Refused("unknown riser %r" % rid)
        if rid in rows:
            raise Refused("riser %s is given twice" % rid)
        if limit not in LIMITS:
            raise Refused("%s: limit %r is not one of %s" % (rid, limit, ", ".join(LIMITS)))
        rows[rid] = (limit, number(p, "p_base_psi", rid), number(q, "q_avail_gpm", rid))
    missing = sorted(set(risers) - set(rows))
    if missing:
        raise Refused("no row for %s" % ", ".join(missing))
    return rows


def score(path, truth=None):
    """(accepted, per-riser detail). Raises Refused for a sheet that is not in form."""
    truth = truth or sealed()
    rows = read_sheet(path, truth)
    detail = {}
    for rid, t in truth.items():
        limit, p, q = rows[rid]
        ok_l = limit == t["limit"]
        ok_p = abs(p - t["p_base_psi"]) <= P_BAND * t["p_base_psi"]
        ok_q = abs(q - t["q_avail_gpm"]) <= Q_BAND * t["q_avail_gpm"]
        detail[rid] = dict(limit=ok_l, p=ok_p, q=ok_q, ok=ok_l and ok_p and ok_q,
                           dp=p / t["p_base_psi"] - 1, dq=q / t["q_avail_gpm"] - 1)
    return all(d["ok"] for d in detail.values()), detail
