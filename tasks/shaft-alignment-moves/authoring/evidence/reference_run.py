#!/usr/bin/env python3
"""The reference run end to end: solution/solve.py against the contractor's real program, then the verifier.

    python3 reference_run.py

A copy of the contractor's directory is set up as the image sets it up (sealed/ and state/ closed, the reports
directory open to read), solve.py is run as a program with the `laservisit` command pointing at it, a second
order is tried, and the sheet it wrote is given to pytest. The tables show what the reference had to find.
"""
import os
import shutil
import subprocess
import sys
import tempfile

import common


def main():
    box = tempfile.mkdtemp(prefix="sam_rr_")
    try:
        lab = os.path.join(box, "contractor")
        shutil.copytree(os.path.join(common.ROOT, "environment", "rig"), lab)
        os.makedirs(os.path.join(lab, "state"))
        os.chmod(os.path.join(lab, "sealed"), 0o700)
        os.chmod(os.path.join(lab, "state"), 0o700)
        out_reports = os.path.join(box, "laser_reports")
        os.makedirs(out_reports)
        os.chmod(out_reports, 0o755)
        visit = os.path.join(box, "laservisit")
        with open(visit, "w") as handle:
            handle.write('#!/bin/bash\nLAB_DIR=%s REPORT_DIR=%s exec %s -B %s/lab.py laservisit "$@"\n'
                         % (lab, out_reports, sys.executable, lab))
        os.chmod(visit, 0o755)
        sheet_path = os.path.join(box, "output", "moves.csv")
        env = dict(os.environ, DATA_DIR=common.DATA, REPORT_DIR=out_reports, OUTPUT=sheet_path, LASERVISIT=visit,
                   PYTHONDONTWRITEBYTECODE="1")
        done = subprocess.run([sys.executable, "-B", os.path.join(common.ROOT, "solution", "solve.py")],
                              env=env, capture_output=True, text=True)
        print("solution/solve.py on the shipped records (seed %d), through environment/rig/lab.py.\n" % common.SHIPPED)
        print("\n".join(line for line in done.stdout.splitlines() if line.startswith("laser programme")))
        again = subprocess.run([visit, "K-201A", "K-201B", "K-201C", "P-331", "P-302", "P-312"],
                               capture_output=True, text=True)
        print("a second order: %s" % again.stdout.strip())
        test = subprocess.run([sys.executable, "-B", "-m", "pytest", "test_moves.py", "-p", "no:cacheprovider", "-q"],
                              cwd=os.path.join(common.ROOT, "tests"), capture_output=True, text=True,
                              env=dict(os.environ, MOVES_FILE=sheet_path, PYTHONDONTWRITEBYTECODE="1"))
        print("pytest on the sheet it wrote: %s" % test.stdout.strip().splitlines()[-1])

        unit = common.solve.Turnaround(common.records())
        programme = unit.programme()
        unit.take(common.solve.read_reports(out_reports, programme))
        outcome = common.grade_moves.assess(sheet_path)
    finally:
        shutil.rmtree(box, ignore_errors=True)
        try:
            os.remove("/logs/verifier/alignment.json")
        except OSError:
            pass

    print("\nThe groups of changed pumps, and what one measurement of each gave:\n")
    print("| group | models | their 2019 ratios | measured on | ratio now |")
    print("|---|---|---|---|---|")
    for number, group in enumerate(unit.groups()):
        models = sorted({unit.stationary(tag)[1] for tag in group})
        print("| %s | %s | %s | %s | %.3f |" % (" ".join(group), ", ".join(models),
                                              ", ".join("%.3f" % unit.model_ratio(m) for m in models),
                                              [t for t in group if t in unit.visited][0], unit.measured_ratio[number]))
    print("\nThe other models, on their 2019 ratios at today's pumped temperatures:\n")
    print("| model | 2019 ratio |")
    print("|---|---|")
    grouped = {unit.stationary(tag)[1] for group in unit.groups() for tag in group}
    for model in sorted(unit.construction):
        if model not in grouped:
            print("| %s | %.3f |" % (model, unit.model_ratio(model)))
    print("\nThe turbines:\n")
    print("| turbine | 2023 hot check, rise / lateral | measured now, rise / lateral |")
    print("|---|---|---|")
    for check in unit.rec["hot_checks"]:
        seen = unit.visited[check["tag"]]
        print("| %s | %s / %s | %.3f / %.3f |" % (check["tag"], check["rise_mm"], check["lateral_mm"],
                                                  seen["movable_rise"], seen["movable_lateral"]))
    print("\nThe dial sheets against the laser, on the six trains visited (cold position, mm):\n")
    print("| train | kit | bar set | mandrel | largest difference at either plane |")
    print("|---|---|---|---|---|")
    for tag in programme:
        dial = unit.dial_position(tag)
        laser = unit.cold_position(tag)
        gap = max(abs(a - b) for p, q in zip(dial, laser) for a, b in zip(p, q))
        print("| %s | %s | %d | %.2f | %.3f |" % (tag, unit.kit(tag), unit.bar_set(tag), unit.mandrel(tag), gap))
    print("\nThe sheet, as the verifier found each train (running, mm):\n")
    print("| train | shim front | shim rear | lateral front | lateral rear | worst left | where |")
    print("|---|---|---|---|---|---|---|")
    sheet = unit.sheet()
    for tag in unit.tags:
        row = outcome.detail[tag]
        print("| %s | %.3f | %.3f | %.3f | %.3f | %+.4f | %s |" % ((tag,) + sheet[tag] + (row["worst_mm"], row["at"])))
    worst = max(abs(row["worst_mm"]) for row in outcome.detail.values())
    print("\n%d of %d trains aligned; worst left %.4f mm against an acceptance of %.2f"
          % (outcome.aligned, outcome.trains, worst, common.unit3.TOL))
    return 0 if outcome.accepted and test.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
