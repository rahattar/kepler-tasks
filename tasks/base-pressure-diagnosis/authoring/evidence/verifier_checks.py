"""Malformed sheets and edge cases, every one built from the current reference solution at run time.

Nothing here is hard-coded from an earlier run: the reference is executed, its sheet is read, and each case is that
sheet corrupted in one named way. So if the reference or the grader changes, these cases change with them and
cannot quietly disagree with what the README claims.

Each case is scored by `grade_audit.score()`, which is what the verifier calls, and its outcome is compared with
what the rules say should happen. Any case whose outcome differs is printed as UNEXPECTED, and preflight fails if
the word appears in this file's output.

    python3 -I verifier_checks.py  > verifier_checks.txt
"""
import math
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C                                                      # noqa: E402

HEADER = "chamber,cause,q_total_mbarl_s,s_eff_l_s"


def sheet_lines(answers):
    return [HEADER] + ["%s,%s,%.4e,%.1f" % (cid, answers[cid][0], answers[cid][1], answers[cid][2])
                       for cid in C.IDS]


def case_accepted(name, text):
    return name, text, True


def case_rejected(name, text):
    return name, text, False


def build(answers):
    """Every case, as (name, sheet text or a callable that writes the file, expected acceptance)."""
    base = sheet_lines(answers)
    good = "\n".join(base) + "\n"
    cases = [case_accepted("the reference sheet as it stands", good)]

    # tolerated shapes
    cases.append(case_accepted("blank lines and surrounding spaces",
                               "\n".join([""] + ["  " + base[0] + " "] + [""] +
                                         ["  " + line + "  " for line in base[1:]] + [""]) + "\n"))
    cases.append(case_accepted("no trailing newline", "\n".join(base)))
    cases.append(case_accepted("the rows out of order",
                               "\n".join([base[0]] + list(reversed(base[1:]))) + "\n"))

    # One chamber nudged just inside and just outside each band, on both sides of the truth. Both bands get the
    # same four cases: a band tested on one side only is a band whose other edge is not known to be where the
    # instruction says it is.
    tr = C.truth()
    for field, tol, key, idx in (("gas-load", C.G.Q_TOL, "q_total", 0), ("speed", C.G.S_TOL, "s_eff", 1)):
        for frac, inside in ((0.9, True), (1.1, False)):
            for sign in (+1, -1):
                cid = C.IDS[idx]
                alt = dict(answers)
                value = tr[cid][key] * (1 + sign * frac * tol)
                alt[cid] = ((answers[cid][0], value, answers[cid][2]) if key == "q_total"
                            else (answers[cid][0], answers[cid][1], value))
                cases.append((("one chamber %+.1f%% on the %s band (%s it)"
                               % (100 * sign * frac * tol, field, "inside" if inside else "outside")),
                              "\n".join(sheet_lines(alt)) + "\n", inside))
    alt = dict(answers)
    other = [c for c in ("air-leak", "permeation") if c != answers[C.IDS[2]][0]][0]
    alt[C.IDS[2]] = (other, answers[C.IDS[2]][1], answers[C.IDS[2]][2])
    cases.append(case_rejected("one chamber with the wrong cause", "\n".join(sheet_lines(alt)) + "\n"))

    # malformed sheets
    cases += [
        case_rejected("no header", "\n".join(base[1:]) + "\n"),
        case_rejected("a renamed column", good.replace("q_total_mbarl_s", "gas_load")),
        case_rejected("the columns in another order",
                      "chamber,q_total_mbarl_s,cause,s_eff_l_s\n" + "\n".join(base[1:]) + "\n"),
        case_rejected("an extra column", "\n".join([base[0] + ",note"] + [b + ",x" for b in base[1:]]) + "\n"),
        case_rejected("a row missing", "\n".join(base[:-1]) + "\n"),
        case_rejected("a row repeated", "\n".join(base + [base[-1]]) + "\n"),
        case_rejected("an unknown chamber", good.replace(C.IDS[0], "VC99", 1)),
        case_rejected("a cause not in the list", good.replace(answers[C.IDS[0]][0], "leak", 1)),
        case_rejected("a cause in the wrong case",
                      good.replace(answers[C.IDS[0]][0], answers[C.IDS[0]][0].upper(), 1)),
        case_rejected("a gas load that is not a number",
                      "\n".join([base[0], "%s,%s,none,%.1f" % (C.IDS[0], answers[C.IDS[0]][0],
                                                               answers[C.IDS[0]][2])] + base[2:]) + "\n"),
        case_rejected("a gas load of NaN", _swap_q(base, answers, C.IDS[0], "nan")),
        case_rejected("a gas load of infinity", _swap_q(base, answers, C.IDS[0], "inf")),
        case_rejected("a negative gas load", _swap_q(base, answers, C.IDS[0], "-1.0e-04")),
        case_rejected("a gas load of zero", _swap_q(base, answers, C.IDS[0], "0.0")),
        case_rejected("a gas load far above the range", _swap_q(base, answers, C.IDS[0], "1.0e+03")),
        case_rejected("a speed of zero", _swap_s(base, answers, C.IDS[0], "0.0")),
        case_rejected("a speed far above the range", _swap_s(base, answers, C.IDS[0], "1.0e+07")),
        case_rejected("a speed that is a boolean", _swap_s(base, answers, C.IDS[0], "True")),
        case_rejected("an empty file", ""),
        case_rejected("only the header", base[0] + "\n"),
        case_rejected("padded past the size limit", good + "#" + "x" * 120_000 + "\n"),
        case_rejected("bytes that are not ASCII", good.replace(C.IDS[0], "VC\u00d61", 1)),
    ]
    return cases


def _swap_q(base, answers, cid, text):
    rows = [base[0]]
    for line in base[1:]:
        if line.startswith(cid + ","):
            rows.append("%s,%s,%s,%.1f" % (cid, answers[cid][0], text, answers[cid][2]))
        else:
            rows.append(line)
    return "\n".join(rows) + "\n"


def _swap_s(base, answers, cid, text):
    rows = [base[0]]
    for line in base[1:]:
        if line.startswith(cid + ","):
            rows.append("%s,%s,%.4e,%s" % (cid, answers[cid][0], answers[cid][1], text))
        else:
            rows.append(line)
    return "\n".join(rows) + "\n"


def score_file(path):
    return C.G.score(path)


def main():
    answers = C.reference_answers()
    work = tempfile.mkdtemp(prefix="bpd-verifier-")
    rows = []
    unexpected = 0

    for name, text, expect_ok in build(answers):
        path = os.path.join(work, "diagnosis.csv")
        if os.path.lexists(path):
            os.remove(path)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except UnicodeEncodeError:
            with open(path, "wb") as f:
                f.write(text.encode("utf-8"))
        r = score_file(path)
        ok = bool(r.get("accepted"))
        agrees = ok == expect_ok
        unexpected += 0 if agrees else 1
        rows.append([name, "accepted" if ok else "rejected", "accepted" if expect_ok else "rejected",
                     "%d/%d" % (r.get("npass", 0), len(C.IDS)),
                     (r.get("error") or "-")[:46], "" if agrees else "UNEXPECTED"])

    # a sheet that is a symlink to a good sheet, which the grader must refuse to read
    good = os.path.join(work, "real.csv")
    with open(good, "w") as f:
        f.write("\n".join(sheet_lines(answers)) + "\n")
    link = os.path.join(work, "diagnosis.csv")
    if os.path.lexists(link):
        os.remove(link)
    os.symlink(good, link)
    r = score_file(link)
    agrees = not r.get("accepted")
    unexpected += 0 if agrees else 1
    rows.append(["a sheet that is a symlink", "accepted" if r.get("accepted") else "rejected", "rejected",
                 "%d/%d" % (r.get("npass", 0), len(C.IDS)), (r.get("error") or "-")[:46],
                 "" if agrees else "UNEXPECTED"])
    os.remove(link)

    # a sheet that is a directory, and a sheet that is not there at all
    os.mkdir(link)
    r = score_file(link)
    agrees = not r.get("accepted")
    unexpected += 0 if agrees else 1
    rows.append(["a sheet that is a directory", "accepted" if r.get("accepted") else "rejected", "rejected",
                 "%d/%d" % (r.get("npass", 0), len(C.IDS)), (r.get("error") or "-")[:46],
                 "" if agrees else "UNEXPECTED"])
    os.rmdir(link)
    r = score_file(link)
    agrees = not r.get("accepted")
    unexpected += 0 if agrees else 1
    rows.append(["no sheet at all", "accepted" if r.get("accepted") else "rejected", "rejected",
                 "%d/%d" % (r.get("npass", 0), len(C.IDS)), (r.get("error") or "-")[:46],
                 "" if agrees else "UNEXPECTED"])

    print(C.report("Malformed sheets and edge cases, each scored by the grader the verifier calls", rows,
                   ["case", "outcome", "expected", "right", "grader's reason", ""]))
    print("tolerances: gas load %.1f%%, speed %.1f%%; gate %d of %d chambers; size limit %d bytes"
          % (100 * C.G.Q_TOL, 100 * C.G.S_TOL, C.G.GATE, len(C.IDS), C.G.MAX_BYTES))
    print("")
    if unexpected:
        print("%d case(s) did not behave as the rules say" % unexpected)
    else:
        print("all %d cases behaved as the rules say; the grader raised nothing it could not name" % len(rows))
    C.cleanup()
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
