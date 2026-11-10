"""Documents of each job's package, and the standard, the cutting coefficients and the package format."""
import csv, os, random
import numpy as np
import chat as C
import jobs as Jm

STANDARD = """# MS-CH Milling stability limits (owner's standard, revision 1)

1. The stability limit of a milling operation is the axial depth of cut at which regenerative chatter starts at the
   spindle speed of the operation.
2. Method: the zero-order (average tooth angle) solution of Altintas and Budak (1995) for a cylindrical cutter of
   uniform pitch, helix and runout neglected:
   - x along the feed direction, y normal to it in the plane of the cut; the immersion angle measured from y in the
     direction of rotation; up (conventional) milling: entry 0, exit acos(1 - 2 ae/D); down (climb) milling: entry
     acos(2 ae/D - 1), exit pi, with ae the radial depth of cut and D the tool diameter;
   - the tool-tip receptances along x and y only (cross receptances neglected), N the number of cutting teeth,
     tangential cutting coefficient Kt and radial-to-tangential ratio Kr from `cutting_coefficients.md`;
   - the limit at a speed is the lowest positive limiting depth over the chatter frequencies whose stability lobe
     passes through that speed.
3. The tool-tip receptances are those of the tool assembly as it will cut, from tap tests at the tool tip along the
   machine's X and Y axes.
"""

COEFFS = """# Cutting coefficients (shop data, carbide tools)

| material | Kt (N/mm2) | Kr |
|---|---|---|
""" + "\n".join("| %s | %d | %.2f |" % (m, round(k / 1e6), r) for m, (k, r) in Jm.MAT.items()) + "\n"

FORMAT = """# Job package format

Each job's package holds:
- `setup_sheet.md`: the machine, the tool assembly (tool, teeth, holder, stickout), the material and the operation
  (milling direction, feed axis, radial depth of cut in mm or as a stepover percentage of the tool diameter,
  programmed spindle speed);
- `tap_tests/`: the tap test files of tool assemblies on the job's machine, one file per test and axis. Each file
  starts with `#` lines giving the machine, the assembly, its stickout, the date, the axis, where the hammer and the
  accelerometer were, the accelerometer's mass and whether the data are corrected for it, and the quantity measured
  (receptance in m/N, mobility in (m/s)/N or accelerance in (m/s^2)/N), then the columns `freq_hz`, `real`, `imag`
  and `coherence`;
- `machine_log.csv`: work on the machine: `date`, `work_order`, `description`.
"""


def setup_sheet(j):
    if j["inserts"]:
        tool = ("%s: %d mm face mill body with %d insert pockets; %d inserts fitted, in evenly spaced pockets; on a "
                "shell mill arbor" % (j["assembly"], round(j["D"] * 1000), j["teeth"], j["inserts"], ))
    else:
        tool = ("%s: %d mm solid carbide end mill, %d flutes, in a shrink-fit holder, stickout %d mm"
                % (j["assembly"], round(j["D"] * 1000), j["teeth"], j["stickout"]))
    ae = ("radial depth of cut %.1f mm" % (j["ae"] * 1000) if j["ae_form"] == "mm" else
          "stepover %d percent of the tool diameter" % round(100 * j["ae"] / j["D"]))
    mode = "climb milling" if j["milling"] == "climb" else "conventional milling"
    return ("# Setup sheet - %s\n\n- Machine: %s.\n- Tool assembly: %s.\n- Material: %s.\n- Operation: %s, feed along "
            "the machine %s axis, %s.\n- Programmed spindle speed: S%d rpm.\n"
            % (j["name"], j["machine"], tool, j["material"], mode, j["feed"], ae, j["S"]))


UNITS = {"receptance": "receptance, m/N", "mobility": "mobility, (m/s)/N", "accelerance": "accelerance, (m/s^2)/N"}


def tap_file(j, t, axis, rnd):
    f = np.arange(100.0, 5000.0 + 0.25, 0.5)
    G = C.frf(f, t["modes"][axis])
    w = 2 * np.pi * f
    m = t["mass_g"] / 1000
    if not t["corrected"]:                      # the accelerometer's mass loads the tool tip
        G = G / (1 - m * w ** 2 * G)
    if axis in t["opposite"]:                   # accelerometer on the opposite flank: response along -axis
        G = -G
    H = {"receptance": G, "mobility": 1j * w * G, "accelerance": -(w ** 2) * G}[t["units"]]
    nr = np.random.default_rng(j["seed"] * 100 + (0 if axis == "X" else 1) + 10 * len(t["date"]) + int(t["date"][-2:]))
    H = H * (1 + 0.003 * (nr.standard_normal(len(f)) + 1j * nr.standard_normal(len(f))))
    coh = np.clip(0.995 - 0.004 * np.abs(nr.standard_normal(len(f))), 0.9, 1.0)
    head = ["# Tap test, machine %s, assembly %s, stickout %s, %s" % (j["machine"], t["assembly"],
            "%d mm" % t["stickout"] if t["stickout"] else "not applicable (face mill on arbor)", t["date"]),
            ("# Axis: %s (hammer at the tool tip along +%s; accelerometer on the opposite flank of the tool, measuring "
             "along -%s; data as recorded)" % (axis, axis, axis)) if axis in t["opposite"] else
            "# Axis: %s (hammer at the tool tip along +%s; accelerometer on the struck flank, measuring along +%s)" % (axis, axis, axis),
            "# Accelerometer: %.1f g at the tool tip; data %s" % (t["mass_g"], "corrected for the accelerometer mass" if t["corrected"]
                                                                  else "not corrected for the accelerometer mass"),
            "# Quantity: %s" % UNITS[t["units"]], "freq_hz,real,imag,coherence"]
    rows = ["%.1f,%.6e,%.6e,%.3f" % (a, b.real, b.imag, c) for a, b, c in zip(f, H, coh)]
    return "\n".join(head + rows) + "\n"


NOISE = ["Way lube refilled", "Coolant concentration adjusted to 7 percent", "Chip conveyor serviced",
         "Probe battery replaced", "Axis backlash check, within tolerance", "Tool changer gripper adjusted",
         "Spindle warm-up cycle run, vibration normal", "Coolant filter replaced"]


def write(j, out):
    os.makedirs(os.path.join(out, "tap_tests"), exist_ok=True)
    rnd = random.Random(j["seed"])
    open(os.path.join(out, "setup_sheet.md"), "w").write(setup_sheet(j))
    for t in j["tests"]:
        for axis in ("X", "Y"):
            fn = "%s_%s_%s.csv" % (t["date"], t["assembly"], axis.lower())
            open(os.path.join(out, "tap_tests", fn), "w").write(tap_file(j, t, axis, rnd))
    log = [[d, "WO-%s-%04d" % (d[:4], rnd.randint(100, 9999)), txt] for d, kind, txt in j["log"]]
    for k in range(8):
        d = "%d-%02d-%02d" % (rnd.choice([2025, 2026]), rnd.randint(1, 12), rnd.randint(1, 28))
        if d > "2026-04-30": d = "2026-04-%02d" % rnd.randint(1, 28)
        log.append([d, "WO-%s-%04d" % (d[:4], rnd.randint(100, 9999)), rnd.choice(NOISE) + "."])
    log.sort()
    with open(os.path.join(out, "machine_log.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "work_order", "description"]); w.writerows(log)
