"""Malformed and edge-case sheets against tests/grade_power.py: each must be rejected (or graded) without a crash.
Every case is built from the current reference sheet at run time, so this file cannot go stale.

    python3 authoring/evidence/verifier_checks.py > authoring/evidence/verifier_checks.txt
"""
import os
import sys
import tempfile

import common as C

sys.path.insert(0, os.path.join(C.ROOT, "tests"))
import grade_power as G  # noqa: E402

SHEET, _ = C.solve_route()                 # the reference sheet on the shipped seed
REF = {m: ["%.1f" % SHEET[m][k] for k in C.KEYS] for m in C.IDS}
HEADER = ",".join(G.HEADER)
TOTAL = G.GATE


def sheet(rows=None, header=HEADER, sep="\n", extra=""):
    rows = rows if rows is not None else ["%s,%s" % (m, ",".join(REF[m])) for m in C.IDS]
    return header + sep + sep.join(rows) + sep + extra


def with_cell(machine, key, value):
    rows = []
    for m in C.IDS:
        v = list(REF[m])
        if m == machine:
            v[C.KEYS.index(key)] = value
        rows.append("%s,%s" % (m, ",".join(v)))
    return sheet(rows)


def shifted(machine, key, by):
    """the value set to the definition's own, moved by `by` dB, so that the edge of the band is exact"""
    return with_cell(machine, key, "%.2f" % (C.S.truth()[machine][key] + by))


def cases():
    yield "reference sheet", sheet(), True
    yield "reference sheet, CRLF line ends and a blank line", sheet(sep="\r\n").replace("C2", "\r\nC2"), True
    yield "reference sheet, spaces around the fields", sheet().replace(",", " , ").replace(
        "machine , ", "machine,").replace(" , lw", ",lw").replace("lw_8k , lwa", "lw_8k,lwa"), True
    yield "rows in another order", sheet(list(reversed(sheet().splitlines()[1:]))), True
    yield "levels with four decimals", sheet(
        ["%s,%s" % (m, ",".join("%.4f" % SHEET[m][k] for k in C.KEYS)) for m in C.IDS]), True
    yield "a level %+.1f dB out, at the edge of the band" % C.S.TOL, shifted("C1", "250", C.S.TOL), True
    yield "a level %+.2f dB out, just past the edge" % (C.S.TOL + 0.05), shifted(
        "C1", "250", C.S.TOL + 0.05), "graded"
    yield "C3's A-weighted level 2 dB out", shifted("C3", "A", 2.0), "graded"
    yield "empty file", "", False
    yield "header only", HEADER + "\n", False
    yield "header misspelt", sheet(header=HEADER.replace("lw_1k", "lw_1000")), False
    yield "header with an extra column", sheet(header=HEADER + ",note"), False
    yield "no header", "\n".join(sheet().splitlines()[1:]), False
    yield "a machine missing", "\n".join(sheet().splitlines()[:-1]), False
    yield "a machine twice", sheet() + "C1,%s\n" % ",".join(REF["C1"]), False
    yield "an unknown machine", sheet() + "C4,%s\n" % ",".join(REF["C1"]), False
    yield "a machine in lower case", sheet().replace("C2,", "c2,"), False
    yield "a row with an extra field", sheet().replace("C2,%s" % ",".join(REF["C2"]),
                                                       "C2,%s,0" % ",".join(REF["C2"])), False
    yield "a row with a field missing", sheet().replace("C2,%s" % ",".join(REF["C2"]),
                                                        "C2,%s" % ",".join(REF["C2"][:-1])), False
    # a no-break space after C1, written as chr(0xa0) so that this file itself stays ASCII
    yield "a non-ASCII character", sheet().replace("C1,", "C1" + chr(0xa0) + ","), False
    for name, v in (("NaN", "NaN"), ("Infinity", "Infinity"), ("empty", ""), ("text", "abc"),
                    ("negative", "-96.0"), ("39.9", "39.9"), ("160.1", "160.1")):
        yield "C1's 1 kHz level %s" % name, with_cell("C1", "1k", v), False
    yield "C2's A-weighted level as 1e2 (100.0)", with_cell("C2", "A", "1e2"), "graded"


def main():
    tmp = tempfile.mkdtemp()
    n = 0
    for name, text, expect in cases():
        p = os.path.join(tmp, "sound_power.csv")
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
        os.remove(p)
    target = os.path.join(tmp, "real.csv")
    with open(target, "w") as f:
        f.write(sheet())
    link = os.path.join(tmp, "sound_power.csv")
    os.symlink(target, link)
    n += 1
    print("%-62s rejected: %s" % ("the sheet a symlink to a correct sheet", G.score(link).get("error")))
    n += 1
    print("%-62s rejected: %s" % ("no sheet", G.score(os.path.join(tmp, "absent.csv")).get("error")))
    print()
    print("%d cases run, none crashed the grader" % n)


if __name__ == "__main__":
    main()
