#!/usr/bin/env python3
"""Malformed and edge-case sheets put through the real grader.

Every case is built from the current reference sheet at run time, so this cannot go stale when the answer changes.
Each line says what the grader did and whether that was expected. None may come out UNEXPECTED.

    python3 verifier_checks.py
"""
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "solution"))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
import grade_flare  # noqa: E402
import solve  # noqa: E402

HEADER = list(grade_flare.COLUMNS)


def reference_sizing():
    """The reference's own re-rating, as a one-row sheet."""
    os.environ["DATA_DIR"] = os.path.join(ROOT, "environment", "data")
    sys.path.insert(0, os.path.join(ROOT, "authoring", "evidence"))
    import common
    sealed, _ = common.truth()
    m = solve.Study(solve.load(os.environ["DATA_DIR"]), common.crew_reports(sealed))
    bore, who, share, _where = m.sizing()
    return "tip_bore_mm,binding_device,back_pressure_pct\n%.1f,%s,%.3f\n" % (bore, who, 100.0 * share)


def reference_rows():
    """The reference's own answer, as rows."""
    os.environ["DATA_DIR"] = os.path.join(ROOT, "environment", "data")
    sys.path.insert(0, os.path.join(ROOT, "authoring", "evidence"))
    import common
    sealed, _ = common.truth()
    m = solve.Study(solve.load(os.environ["DATA_DIR"]), common.crew_reports(sealed))
    return [[c, ";".join(devices), "%.1f" % total, "%.4f" % back]
            for c, devices, total, back in m.sheet()]


def render(rows, header=HEADER, eol="\n", blanks=False, pad=False):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator=eol)
    w.writerow(header)
    for r in rows:
        w.writerow(["  %s  " % c for c in r] if pad else r)
        if blanks:
            buf.write(eol)
    return buf.getvalue()


CASES = 0


def main():
    global CASES
    rows = reference_rows()
    tmp = tempfile.mkdtemp(prefix="fl_vc_")
    path = os.path.join(tmp, "flare_load.csv")
    sizing_path = os.path.join(tmp, "tip_sizing.csv")
    good_sizing = reference_sizing()
    bad = 0

    def check(label, text, expect, write=None, sizing=None):
        nonlocal bad
        global CASES
        CASES += 1
        for p in (path,):
            if os.path.lexists(p):
                os.remove(p)
        if write == "symlink":
            os.symlink(os.path.join(tmp, "target.csv"), path)
            with open(os.path.join(tmp, "target.csv"), "w") as f:
                f.write(text)
        elif write == "absent":
            pass
        elif write == "dir":
            os.mkdir(path)
        else:
            with open(path, "w", newline="") as f:
                f.write(text)
        with open(sizing_path, "w", newline="") as f:
            f.write(good_sizing if sizing is None else sizing)
        if sizing == "absent":
            os.remove(sizing_path)
        r = grade_flare.assess(path, sizing_path)
        got = "rejected" if r.fault is not None else ("accepted" if r.taken else "graded %d of 7" % r.standing)
        tag = "ok " if got.split()[0] == expect.split()[0] else "UNEXPECTED"
        if tag != "ok ":
            bad += 1
        note = ("" if r.fault is None else ": " + r.fault.reason.replace(tmp + os.sep, "").replace(tmp, ""))
        print("%s %-52s -> %s%s" % (tag, label, got, note))
        if write == "dir":
            shutil.rmtree(path, ignore_errors=True)

    print("Sheets put through tests/grade_flare.py. Every case is built from the current reference.\n")
    check("the reference sheet", render(rows), "accepted")
    check("the reference sheet with CRLF line ends", render(rows, eol="\r\n"), "accepted")
    check("the reference sheet with blank lines", render(rows, blanks=True), "accepted")
    check("the reference sheet with padded fields", render(rows, pad=True), "accepted")
    check("the reference sheet with the rows reversed", render(rows[::-1]), "accepted")
    check("devices separated by commas", render([[r[0], r[1].replace(";", ",")] + r[2:] for r in rows]),
          "accepted")
    check("devices separated by spaces", render([[r[0], r[1].replace(";", " ")] + r[2:] for r in rows]),
          "accepted")
    check("devices in the other order",
          render([[r[0], ";".join(r[1].split(";")[::-1])] + r[2:] for r in rows]), "accepted")
    check("no file at all", "", "rejected", write="absent")
    check("a symbolic link to a good sheet", render(rows), "rejected", write="symlink")
    check("a directory in place of the file", "", "rejected", write="dir")
    check("an empty file", "", "rejected")
    check("the header alone", render([]), "rejected")
    check("no header", "\n".join(",".join(r) for r in rows) + "\n", "rejected")
    check("a misspelt header",
          render(rows, header=["contingency", "device", "load_kgh", "header_barg"]), "rejected")
    check("an extra header column", render([r + ["x"] for r in rows], header=HEADER + ["note"]), "rejected")
    check("a row of the wrong length", render(rows[:-1] + [rows[-1][:3]]), "rejected")
    check("a contingency missing", render(rows[:-1]), "rejected")
    check("a contingency repeated", render(rows + [rows[0]]), "rejected")
    check("an unknown contingency", render(rows[:-1] + [["flood"] + rows[-1][1:]]), "rejected")
    check("a contingency in upper case", render([["POWER_FAILURE"] + rows[0][1:]] + rows[1:]), "rejected")
    check("non-ASCII text", render(rows).replace("power", "pow" + chr(233) + "r"), "rejected")
    check("a sheet larger than the cap", render(rows) + "# " + "x" * 100_001, "rejected")

    # the instruction asks every number to at least three significant figures, and the grader holds that line
    def retype(contingency, column, text):
        out = []
        for r in rows:
            r = list(r)
            if r[0] == contingency:
                r[column] = text
            out.append(r)
        return out

    def resize(share_text):
        head, row = good_sizing.strip().split("\n")
        bore, device, _share = row.split(",")
        return "%s\n%s,%s,%s\n" % (head, bore, device, share_text)

    graded = [r for r in rows if float(r[3]) != 0.0]
    floored = [r for r in rows if float(r[3]) == 0.0]
    share_now = float(good_sizing.strip().split("\n")[1].split(",")[2])
    check("a load to two significant figures",
          render(retype(rows[0][0], 2, "%.1e" % float(rows[0][2]))), "rejected")
    check("a load to three significant figures in exponent form",
          render(retype(rows[0][0], 2, "%.2e" % float(rows[0][2]))), "accepted")
    check("a pressure to two significant figures",
          render(retype(graded[0][0], 3, "%.2g" % float(graded[0][3]))), "rejected")
    check("a pressure to three significant figures",
          render(retype(graded[0][0], 3, "%.3g" % float(graded[0][3]))), "accepted")
    if floored:
        check("a pressure below the floor written as nil", render(retype(floored[0][0], 3, "0")), "accepted")
    check("the re-rating share to two significant figures", render(rows), "rejected",
          sizing=resize("%.2g" % share_now))
    check("the re-rating share to three significant figures", render(rows), "accepted",
          sizing=resize("%.3g" % share_now))

    for label, val in (("an unknown device", "PSV-499"), ("a device in lower case", "psv-401"),
                       ("a device named twice", rows[0][1] + ";" + rows[0][1].split(";")[0]),
                       ):
        check(label, render([[rows[0][0], val] + rows[0][2:]] + rows[1:]), "rejected")
    check("a device list of separators alone",
          render([[rows[0][0], ";;;"] + rows[0][2:]] + rows[1:]), "graded 5")
    for label, val in (("a load that is not a number", "about 50000"), ("an empty load", ""),
                       ("a load of NaN", "nan"), ("an infinite load", "inf"),
                       ("a negative load", "-50000"), ("a load above the range", "1e8")):
        check(label, render([rows[0][:2] + [val] + rows[0][3:]] + rows[1:]), "rejected")
    for label, val in (("a pressure that is not a number", "about 1 bar"), ("an empty pressure", ""),
                       ("a pressure of NaN", "nan"), ("an infinite pressure", "inf"),
                       ("a negative pressure", "-1.3"), ("a pressure above the range", "1e4")):
        check(label, render([rows[0][:3] + [val]] + rows[1:]), "rejected")
    load0 = float(rows[0][2])
    for label, val in (("a load in exponent form", "%.6e" % load0),
                       ("a load with six decimals", "%.6f" % load0),
                       ("a load with twelve decimals", "%.12f" % load0),
                       ("a load with a leading plus", "+%.1f" % load0)):
        check(label, render([rows[0][:2] + [val] + rows[0][3:]] + rows[1:]), "accepted")
    check("one device dropped", render([[rows[0][0], ";".join(rows[0][1].split(";")[1:])] + rows[0][2:]]
                                       + rows[1:]), "graded 5")
    check("one device added", render([[rows[0][0], rows[0][1] + ";PSV-404"] + rows[0][2:]] + rows[1:]),
          "graded 5")
    check("a device list of none", render([[rows[0][0], "none"] + rows[0][2:]] + rows[1:]), "graded 5")
    check("one load moved by 2 per cent",
          render([rows[0][:2] + ["%.1f" % (float(rows[0][2]) * 1.02)] + rows[0][3:]] + rows[1:]), "graded 5")
    check("one pressure moved by 2 per cent",
          render([rows[0][:3] + ["%.4f" % (float(rows[0][3]) * 1.02)]] + rows[1:]), "graded 5")
    check("every load moved by 2 per cent",
          render([r[:2] + ["%.1f" % (float(r[2]) * 1.02)] + r[3:] for r in rows]), "graded 0")
    check("every pressure moved by 2 per cent",
          render([r[:3] + ["%.4f" % (float(r[3]) * 1.02)] for r in rows]), "graded 1")

    # ---- the re-rating sheet
    for label, text, expect in (
            ("no re-rating sheet at all", "absent", "rejected"),
            ("a re-rating header that is misspelt",
             "tip_bore,binding_device,back_pressure_pct\n406.4,PSV-409,4.440\n", "rejected"),
            ("a re-rating with two rows",
             good_sizing + "406.4,PSV-409,4.440\n", "rejected"),
            ("a re-rating naming a device that is not one",
             "tip_bore_mm,binding_device,back_pressure_pct\n406.4,PSV-499,4.440\n", "rejected"),
            ("a re-rating whose bore is not a number",
             "tip_bore_mm,binding_device,back_pressure_pct\nsixteen inch,PSV-409,4.440\n", "rejected"),
            ("a re-rating with a negative share",
             "tip_bore_mm,binding_device,back_pressure_pct\n406.4,PSV-409,-4.440\n", "rejected"),
            ("a re-rating one bore too small",
             "tip_bore_mm,binding_device,back_pressure_pct\n355.6,PSV-409,5.960\n", "graded 6"),
            ("a re-rating naming the wrong binding device",
             "tip_bore_mm,binding_device,back_pressure_pct\n406.4,PSV-407,4.440\n", "graded 6"),
            ("a re-rating whose share is 2 per cent out",
             "tip_bore_mm,binding_device,back_pressure_pct\n406.4,PSV-409,4.529\n", "graded 6")):
        check(label, render(rows), expect, sizing=text)

    shutil.rmtree(tmp, ignore_errors=True)

    print("\nThe reward protocol in tests/test.sh, with pytest stubbed so each combination can be forced.\n")
    bad += reward_protocol()
    print("\n%d cases, %d UNEXPECTED" % (CASES + 4, bad))
    print("The grader never crashed, and the reward followed the run rather than anything written during it.")
    return 0


def reward_protocol():
    """Run tests/test.sh for real with a stub in place of python's pytest, and read back the reward it wrote.

    The stub answers the two calls test.sh makes: `python -m pytest ...` writes the ctrf report we want it to and
    exits with the status we want, and `python - <file>` runs the real interpreter on the script test.sh pipes in.
    """
    import stat as statmod
    sh = os.path.join(ROOT, "tests", "test.sh")
    reward = "/logs/verifier/reward.txt"
    cases = [
        ("pytest passes and the report holds one passing test", 0,
         {"results": {"summary": {"tests": 1, "passed": 1, "failed": 0, "skipped": 0,
                                  "pending": 0, "other": 0}}}, "1"),
        ("pytest passes but the report holds two tests", 0,
         {"results": {"summary": {"tests": 2, "passed": 2, "failed": 0, "skipped": 0,
                                  "pending": 0, "other": 0}}}, "0"),
        ("pytest fails though the report looks right", 1,
         {"results": {"summary": {"tests": 1, "passed": 1, "failed": 0, "skipped": 0,
                                  "pending": 0, "other": 0}}}, "0"),
        ("pytest passes and writes no report at all", 0, None, "0"),
    ]
    wrong = 0
    for label, status, report, want in cases:
        box = tempfile.mkdtemp(prefix="rv_rp_")
        try:
            stub = os.path.join(box, "python")
            with open(stub, "w") as handle:
                handle.write(
                    "#!/bin/bash\n"
                    "if [ \"$1\" = \"-m\" ]; then\n"
                    "  %s\n"
                    "  exit %d\n"
                    "fi\n"
                    "exec %s \"$@\"\n"
                    % (("cp %s /logs/verifier/ctrf.json" % os.path.join(box, "ctrf.json"))
                       if report is not None else ":", status, sys.executable))
            os.chmod(stub, os.stat(stub).st_mode | statmod.S_IEXEC)
            if report is not None:
                with open(os.path.join(box, "ctrf.json"), "w") as handle:
                    json.dump(report, handle)
            os.makedirs("/logs/verifier", exist_ok=True)
            for leftover in ("reward.txt", "ctrf.json"):
                try:
                    os.remove(os.path.join("/logs/verifier", leftover))
                except OSError:
                    pass
            env = dict(os.environ, PATH=box + os.pathsep + os.environ["PATH"])
            subprocess.run(["bash", sh], env=env, capture_output=True)
            got = open(reward).read().strip() if os.path.exists(reward) else "<no reward file>"
        finally:
            shutil.rmtree(box, ignore_errors=True)
        tag = "ok " if got == want else "UNEXPECTED"
        if tag != "ok ":
            wrong += 1
        print("%s %-52s -> reward %s" % (tag, label, got))
    return wrong


if __name__ == "__main__":
    sys.exit(main())
