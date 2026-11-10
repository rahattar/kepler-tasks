"""Malformed and edge-case sheets against tests/grade_limits.py: each must be rejected (or graded) without a crash.
Every case is built from the current reference sheet at run time, so this file cannot go stale.

    python3 authoring/evidence/verifier_checks.py > authoring/evidence/verifier_checks.txt
"""
import os
import sys
import tempfile

import common as C

sys.path.insert(0, os.path.join(C.ROOT, "tests"))
import grade_limits as G  # noqa: E402

SHEET, _ = C.route()                       # the reference sheet on the shipped seed
REF = {cid: ["%.2f" % SHEET[cid][0], SHEET[cid][1]] for cid in C.IDS}
HEADER = ",".join(G.HEADER)
TOTAL = G.GATE


def sheet(rows=None, header=HEADER, sep="\n", extra=""):
    rows = rows if rows is not None else ["%s,%s" % (cid, ",".join(REF[cid])) for cid in C.IDS]
    return header + sep + sep.join(rows) + sep + extra


def with_cell(cid_, col, value):
    rows = []
    for cid in C.IDS:
        v = list(REF[cid])
        if cid == cid_:
            v[col] = value
        rows.append("%s,%s" % (cid, ",".join(v)))
    return sheet(rows)


def shifted(cid, rel):
    """the pressure set to the definition's own, moved by rel of it, so that the edge of the band is exact"""
    return with_cell(cid, 0, "%.6f" % (C.S.ps_min(cid)[0] * (1.0 + rel)))


def cases():
    yield "reference sheet", sheet(), True
    yield "reference sheet, CRLF line ends and a blank line", sheet(sep="\r\n").replace("2A", "\r\n2A"), True
    yield "reference sheet, spaces around the fields", "\n".join(
        " , ".join(p.strip() for p in line.split(",")) for line in sheet().splitlines()) + "\n", True
    yield "rows in another order", sheet(list(reversed(sheet().splitlines()[1:]))), True
    yield "pressures with four decimals", sheet(
        ["%s,%.4f,%s" % (cid, SHEET[cid][0], SHEET[cid][1]) for cid in C.IDS]), True
    yield "a pressure in exponent notation", with_cell("1A", 0, "%.5e" % SHEET["1A"][0]), True
    yield "a pressure %+.1f per cent out, at the edge of the band" % (100.0 * C.S.TOL), shifted("1A", C.S.TOL), True
    yield "a pressure %+.2f per cent out, just past the edge" % (100.0 * (C.S.TOL + 0.0005)), shifted(
        "1A", C.S.TOL + 0.0005), "graded"
    yield "3A's pressure 5 per cent out", shifted("3A", 0.05), "graded"
    yield "2B's governing requirement the runner-up", with_cell("2B", 1, "discharge_temperature"), "graded"
    yield "empty file", "", False
    yield "header only", HEADER + "\n", False
    yield "header misspelt", sheet(header=HEADER.replace("suction_pressure_bar", "suction_pressure")), False
    yield "header with an extra column", sheet(header=HEADER + ",note"), False
    yield "no header", "\n".join(sheet().splitlines()[1:]), False
    yield "a cylinder missing", "\n".join(sheet().splitlines()[:-1]), False
    yield "a cylinder twice", sheet() + "1A,%s\n" % ",".join(REF["1A"]), False
    yield "an unknown cylinder", sheet() + "4C,%s\n" % ",".join(REF["1A"]), False
    yield "a cylinder in lower case", sheet().replace("2A,", "2a,"), False
    yield "a row with an extra field", sheet().replace("2A,%s" % ",".join(REF["2A"]),
                                                       "2A,%s,0" % ",".join(REF["2A"])), False
    yield "a row with a field missing", sheet().replace("2A,%s" % ",".join(REF["2A"]), "2A,%s" % REF["2A"][0]), False
    # a no-break space after 1A, written as chr(0xa0) so that this file itself stays ASCII
    yield "a non-ASCII character", sheet().replace("1A,", "1A" + chr(0xa0) + ","), False
    for name, v in (("NaN", "NaN"), ("Infinity", "Infinity"), ("empty", ""), ("text", "abc"),
                    ("negative", "-20.75"), ("0.9", "0.9"), ("500.1", "500.1")):
        yield "1A's pressure %s" % name, with_cell("1A", 0, v), False
    yield "1A's requirement not one of the standard's names", with_cell("1A", 1, "rod_load"), False
    yield "1A's requirement in upper case", with_cell("1A", 1, "ROD_LOAD_TENSION"), False
    yield "1A's requirement empty", with_cell("1A", 1, ""), False


def main():
    tmp = tempfile.mkdtemp()
    n = bad = 0
    for name, text, expect in cases():
        p = os.path.join(tmp, "cylinder_limits.csv")
        with open(p, "w", newline="", encoding="utf-8") as f:
            f.write(text)
        r = G.score(p)
        n += 1
        if expect is True:
            ok = r["accepted"] and r["npass"] == TOTAL
            print("%-62s accepted %d of %d  %s" % (name, r["npass"], TOTAL, "as expected" if ok else "UNEXPECTED"))
        elif expect == "graded":
            ok = "error" not in r and not r["accepted"] and r["npass"] == TOTAL - 1
            print("%-62s graded, %d of %d right  %s" % (name, r["npass"], TOTAL,
                                                        "as expected" if ok else "UNEXPECTED"))
        else:
            ok = "error" in r and not r["accepted"]
            print("%-62s rejected: %s  %s" % (name, r.get("error"), "" if ok else "UNEXPECTED"))
        bad += not ok
        os.remove(p)
    target = os.path.join(tmp, "real.csv")
    with open(target, "w") as f:
        f.write(sheet())
    link = os.path.join(tmp, "cylinder_limits.csv")
    os.symlink(target, link)
    n += 1
    r = G.score(link)
    bad += "error" not in r
    print("%-62s rejected: %s" % ("the sheet a symlink to a correct sheet", r.get("error")))
    n += 1
    r = G.score(os.path.join(tmp, "absent.csv"))
    bad += "error" not in r
    print("%-62s rejected: %s" % ("no sheet", r.get("error")))
    print()
    print("%d cases run, none crashed the grader%s" % (n, "" if not bad else ", %d UNEXPECTED" % bad))
    return bad


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
