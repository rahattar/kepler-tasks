"""Scores one sheet with the verifier's grading module and prints each row.  python3 grade_sheet.py SHEET"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "tests")))
import grade_rating as G  # noqa: E402

try:
    ok, detail = G.score(sys.argv[1])
except G.Refused as e:
    print("REFUSED: %s" % e)
    sys.exit(1)
for rid in sorted(detail):
    d = detail[rid]
    print("%s %-5s limit %-5s p %+6.1f%% %-4s q %+6.1f%% %s" % (
        rid, "ok" if d["ok"] else "WRONG", "ok" if d["limit"] else "WRONG", 100 * d["dp"], "" if d["p"] else "out",
        100 * d["dq"], "" if d["q"] else "out"))
print("ACCEPTED" if ok else "REFUSED: %d of %d rows wrong" % (sum(not d["ok"] for d in detail.values()), len(detail)))
