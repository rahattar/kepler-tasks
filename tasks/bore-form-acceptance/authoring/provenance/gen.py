"""Writes the agent-visible records of the press overhaul from the sealed definition (isim.py, seed SEED): the
feature register, the drawing requirements, the machining log, the measurement index, one file of measured points
per record, and the shop's own inspection report. The documents in data/docs are written by hand and copied as
they are.

    python3 gen.py OUTDIR
"""
import csv
import io
import os
import shutil
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isim as S  # noqa: E402

SEED = 7001
HERE = os.path.dirname(os.path.abspath(__file__))
COMPONENT = {"CB-21": "main ram cylinder, rod end", "CB-22": "main ram cylinder, cap end",
             "CB-23": "pull-back cylinder 1", "CB-24": "pull-back cylinder 2", "CB-25": "pull-back cylinder 3",
             "CB-26": "press cylinder, upper", "GB-31": "main ram gland", "GB-32": "pull-back gland",
             "RJ-41": "main ram, rod journal", "RJ-42": "pull-back ram 1", "RJ-43": "pull-back ram 2",
             "RJ-44": "press ram, upper journal", "RJ-45": "pull-back ram 3", "RJ-46": "tie rod journal"}
LENGTH = S.LENGTH
# the machining log: setup -> date, machine, fixture, the pass, and the features bored in that one setup
SETUP_LOG = {
    "S1": ("2026-09-14", "HBM-2 horizontal borer", "F-2 cradle", "finish bore, CBN insert, 0.08 mm/rev"),
    "S2": ("2026-09-16", "HBM-2 horizontal borer", "F-2 cradle", "finish bore, CBN insert, 0.08 mm/rev"),
    "S3": ("2026-09-18", "VTL-1 vertical lathe", "4-jaw, soft jaws", "finish turn, 0.10 mm/rev"),
    "S4": ("2026-09-21", "HBM-1 horizontal borer", "F-5 vee block", "finish bore, 0.06 mm/rev"),
    "S5": ("2026-09-22", "VTL-1 vertical lathe", "4-jaw, soft jaws", "finish turn, 0.10 mm/rev"),
    "S6": ("2026-09-24", "CG-3 cylindrical grinder", "between centres", "finish grind, 0.02 mm infeed"),
    "S7": ("2026-09-25", "HBM-2 horizontal borer", "F-2 cradle", "finish bore, CBN insert, 0.10 mm/rev"),
    "S8": ("2026-09-28", "CG-3 cylindrical grinder", "between centres", "finish grind, 0.02 mm infeed"),
}
MEAS_DATE = {"S1": "2026-09-29", "S2": "2026-09-29", "S3": "2026-09-30", "S4": "2026-10-01", "S5": "2026-09-30",
             "S6": "2026-10-02", "S7": "2026-10-01", "S8": "2026-10-02"}


def write(path, text):
    with open(path, "w", newline="") as f:
        f.write(text)


def table(path, header, rows):
    """A CSV with every field that needs it quoted, so a comma in a description cannot shift a column."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    write(path, buf.getvalue())


def records(out):
    """One file of measured points per feature, as the shop left it: the roundness tester at TESTER_PTS points a
    revolution, or the coordinate machine's bore program at CMM_PTS touch points."""
    os.makedirs(os.path.join(out, "measurements"), exist_ok=True)
    idx = []
    for f in S.ORDER:
        d = S.FEATURES[f]
        tester = d["src"] == "tester"
        pts = S.TESTER_PTS if tester else S.CMM_PTS
        inst = "form tester RT-1" if tester else "coordinate machine CMM-4, bore/journal program"
        rng = np.random.default_rng([SEED, S.ORDER.index(f)])
        psi = S.mount_phase(f, rng)
        rows = ["section_mm,angle_deg,radius_mm"]
        for j, frac in enumerate(S.SECTIONS):
            state = (("after" if MEAS_DATE[d["setup"]] > S.REGREASE else "before") if tester else False)
            th, r = S.measured(f, j, pts, rng, T=S.T_SHOP[f], pre=True, spindle=state, psi=psi)
            zmm = round(frac * LENGTH[f], 1)
            for a, rr in zip(th, r):
                rows.append("%.1f,%.3f,%.5f" % (zmm, np.degrees(a), rr))
        name = "measurements/%s.csv" % f.lower().replace("-", "")
        write(os.path.join(out, name), "\n".join(rows) + "\n")
        idx.append([f, inst, pts, len(S.SECTIONS), MEAS_DATE[d["setup"]], "%.1f" % S.T_SHOP[f], "data/" + name])
    table(os.path.join(out, "measurement_index.csv"),
          ["feature", "instrument", "points_per_rev", "sections", "measured_on", "room_c", "file"], idx)


def register(out):
    rows = [[f, COMPONENT[f], S.FEATURES[f]["kind"], "%.1f" % S.FEATURES[f]["nom"], "%.1f" % LENGTH[f], "42CrMo4"]
            for f in S.ORDER]
    table(os.path.join(out, "feature_register.csv"),
          ["feature", "component", "kind", "nominal_mm", "feature_length_mm", "material"], rows)


def drawings(out):
    rows = []
    for f in S.ORDER:
        lo, hi = S.FEATURES[f]["lim"]
        kind, tol = S.FEATURES[f]["tol"]
        rows.append([f, "%+d" % lo, "%+d" % hi, "yes", kind, "%.0f" % tol])
    table(os.path.join(out, "drawing_requirements.csv"),
          ["feature", "size_lower_um", "size_upper_um", "envelope_requirement", "form_characteristic",
           "form_tolerance_um"], rows)


def machining(out):
    rows = []
    for s, (date, machine, fixture, op) in SETUP_LOG.items():
        fs = [f for f in S.ORDER if S.FEATURES[f]["setup"] == s]
        note = "clamped once, every feature of this setup finished before unclamping" if len(fs) > 1 \
            else "single part in the setup"
        rows.append([date, s, machine, fixture, op, " ".join(fs), note])
    rows.append(["2026-09-30", "-", "RT-1 form tester", "-", "spindle bearings re-greased, preload reset", "-",
                 "planned maintenance, carried out in the evening after the day's inspection work"])
    rows.append(["2026-10-03", "-", "HON-1 honing machine", "-", "re-hone to clear a score", "CB-22",
                 "score found on strip, bore honed through; the inspection measurement of %s predates this"
                 % MEAS_DATE[S.FEATURES["CB-22"]["setup"]]])
    rows.append(["2026-10-04", "-", "-", "-", "metrology room booking opened", "-",
                 "press overhaul: dense form scans on request, booking of %d" % S.BUDGET])
    table(os.path.join(out, "machining_log.csv"),
          ["date", "setup", "machine", "fixture", "operation", "features_in_this_setup", "note"], rows)


def inspection_report(out, lines):
    text = ["# Inspection report, press overhaul (shop metrology, 2026-10-02)", "",
            "Measured on the machines and at the room temperatures in `measurement_index.csv`. Figures as the",
            "instrument software reports them; see `docs/instrument_notes.md` for what its defaults are.", "",
            "| feature | mean diameter (mm) | roundness (um) | points/rev |", "|---|---|---|---|"]
    text += lines
    text += ["", "Sentencing against the drawings is not done here: the overhaul engineer does it.", ""]
    write(os.path.join(out, "docs", "inspection_report.md"), "\n".join(text))


def shop_figures():
    """What the shop's software reports: a least-squares zone on the filtered profile, and the mean diameter.
    Both are its defaults, and both are the wrong reference for the drawings' requirements."""
    lines = []
    for f in S.ORDER:
        d = S.FEATURES[f]
        tester = d["src"] == "tester"
        pts = S.TESTER_PTS if tester else S.CMM_PTS
        rng = np.random.default_rng([SEED, S.ORDER.index(f)])
        psi = S.mount_phase(f, rng)
        zs, means, ls = [], [], []
        for j, frac in enumerate(S.SECTIONS):
            state = (("after" if MEAS_DATE[d["setup"]] > S.REGREASE else "before") if tester else False)
            th, r = S.measured(f, j, pts, rng, T=S.T_SHOP[f], pre=True, spindle=state, psi=psi)
            dev = (r - r.mean()) * 1000.0
            p = S.assess_profile(th, dev)
            means.append(r.mean() * 2.0)
            ls.append(p.max() - p.min())
            zs.append(frac)
        if d["tol"][0] == "cylindricity":
            v = max(ls)                     # the software reports roundness per section whatever the callout
        else:
            v = max(ls)
        lines.append("| %s | %.4f | %.1f | %d |" % (f, float(np.mean(means)), v, pts))
    return lines


def main(out):
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "docs"), exist_ok=True)
    register(out)
    drawings(out)
    machining(out)
    records(out)
    for name in sorted(os.listdir(os.path.join(HERE, "docs"))):
        shutil.copy(os.path.join(HERE, "docs", name), os.path.join(out, "docs", name))
    inspection_report(out, shop_figures())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "environment", "data"))
