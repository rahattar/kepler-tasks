"""Malformed and edge-case bore sheets against tests/grade_bores.py: each must be rejected (or graded) without a crash.

    python3 authoring/evidence/verifier_checks.py > authoring/evidence/verifier_checks.txt
"""
import os
import sys
import tempfile

import common as C

sys.path.insert(0, os.path.join(C.ROOT, "tests"))
import grade_bores as G  # noqa: E402

SHEET, _ = C.solve_route()             # the reference sheet on the shipped seed: {part: (bore_mm, oven_C)}
REF = {k: ("%.3f" % SHEET[k][0], "%d" % SHEET[k][1]) for k in C.IDS}
S1_OVEN = REF["S1"][1]
S2_ROW = "S2,%s,%s" % REF["S2"]
S5_OVER = "%d" % (C.S.PARTS["S5"]["Tlim"] + 1)                      # one degree above S5's heating limit
S1_TIGHT = "%.3f" % (float(REF["S1"][0]) - 0.008)                  # 8 um more interference than the reference


def sheet(rows=None, header="part,bore_mm,oven_C", sep="\n", extra=""):
    rows = rows if rows is not None else ["%s,%s,%s" % (k, b, t) for k, (b, t) in REF.items()]
    return header + sep + sep.join(rows) + sep + extra


def with_cell(part, col, value):
    rows = []
    for k, (b, t) in REF.items():
        if k == part:
            b, t = (value, t) if col == "bore" else (b, value)
        rows.append("%s,%s,%s" % (k, b, t))
    return sheet(rows)


def cases():
    yield "reference sheet", sheet(), True
    yield "reference sheet, CRLF line ends and blank lines", sheet(sep="\r\n").replace("S4", "\r\nS4"), True
    yield "reference sheet, spaces around fields, S1 oven as %s.0" % S1_OVEN, sheet().replace(",", " , ").replace(
        "S1 , %s , %s" % (REF["S1"][0], S1_OVEN), "S1 , %s , %s.0" % (REF["S1"][0], S1_OVEN)).replace(
        "part , bore_mm , oven_C", "part,bore_mm,oven_C"), True
    yield "rows in another order", sheet(list(reversed(sheet().splitlines()[1:]))), True
    yield "empty file", "", False
    yield "header only", "part,bore_mm,oven_C\n", False
    yield "header misspelt", sheet(header="part,bore,oven_C"), False
    yield "header with an extra column", sheet(header="part,bore_mm,oven_C,note"), False
    yield "no header", "\n".join(sheet().splitlines()[1:]), False
    yield "a part missing", "\n".join(sheet().splitlines()[:-1]), False
    yield "a part twice", sheet() + "S1,%s,%s\n" % REF["S1"], False
    yield "an unknown part", sheet() + "S7,115.000,%s\n" % S1_OVEN, False
    yield "a part in lower case", sheet().replace("S3,", "s3,"), False
    yield "a row with four fields", sheet().replace(S2_ROW, S2_ROW + ",x"), False
    yield "a row with two fields", sheet().replace(S2_ROW, S2_ROW.rsplit(",", 1)[0]), False
    # a no-break space after S1, written as chr(0xa0) so that this file itself stays ASCII
    yield "a non-ASCII character", sheet().replace("S1,", "S1" + chr(0xa0) + ","), False
    for name, v in (("four decimals", "125.1000"), ("NaN", "NaN"), ("Infinity", "Infinity"), ("empty", ""),
                    ("text", "abc"), ("1e2 (100.0)", "1e2"), ("49.999", "49.999"), ("200.001", "200.001"),
                    ("negative", "-125.100")):
        yield "S4 bore %s" % name, with_cell("S4", "bore", v), name == "1e2 (100.0)" and "graded" or False
    for name, v in (("280.5", "280.5"), ("19", "19"), ("1001", "1001"), ("empty", ""), ("NaN", "NaN")):
        yield "S1 oven %s" % name, with_cell("S1", "oven", v), False
    yield "S5 oven above its heating limit (%s C): graded, S5 wrong" % S5_OVER, with_cell("S5", "oven", S5_OVER), "graded"
    yield "S1 bore at %s (above its stress limit at trip): graded, S1 wrong" % S1_TIGHT, with_cell("S1", "bore", S1_TIGHT), "graded"


def main():
    tmp = tempfile.mkdtemp()
    n = 0
    for name, text, expect in cases():
        p = os.path.join(tmp, "bore_sheet.csv")
        with open(p, "w", newline="", encoding="utf-8") as f:
            f.write(text)
        r = G.score(p)
        n += 1
        if expect is True:
            ok = r["accepted"] and r["npass"] == 8
            print("%-66s accepted %d of 8  %s" % (name, r["npass"], "as expected" if ok else "UNEXPECTED"))
        elif expect == "graded":
            ok = "error" not in r and not r["accepted"] and r["npass"] == 7
            print("%-66s graded, %d of 8 right  %s" % (name, r["npass"], "as expected" if ok else "UNEXPECTED"))
        else:
            ok = "error" in r and not r["accepted"]
            print("%-66s rejected: %s  %s" % (name, r.get("error"), "" if ok else "UNEXPECTED"))
        os.remove(p)
    target = os.path.join(tmp, "real.csv")
    with open(target, "w") as f:
        f.write(sheet())
    link = os.path.join(tmp, "bore_sheet.csv")
    os.symlink(target, link)
    r = G.score(link)
    n += 1
    print("%-66s rejected: %s" % ("the sheet a symlink to a correct sheet", r.get("error")))
    r = G.score(os.path.join(tmp, "absent.csv"))
    n += 1
    print("%-66s rejected: %s" % ("no sheet", r.get("error")))
    print()
    print("%d cases run, none crashed the grader" % n)


if __name__ == "__main__":
    main()
