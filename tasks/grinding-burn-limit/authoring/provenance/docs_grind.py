"""Documents of each grinding job's package, and the standard, the data tables and the package format the jobs
share."""
import csv, os, random
import numpy as np
import jobs as Jm

STANDARD = """# MS-GB Grinding burn limits for surface grinding (owner's standard, revision 1)

1. The burn-limited depth of cut of a surface grinding operation is the largest depth of cut per pass at which the
   ground surface temperature stays at or below the part's burn limit, at the operation's work speed and ground width,
   with the wheel at the end of its dressing interval.
2. Surface temperature: coolant temperature plus the maximum temperature rise of a uniform band heat source moving
   over a semi-infinite workpiece at high Peclet number, theta = 1.13 Rw q sqrt(lc / vw) / beta, with:
   - lc = sqrt(ae ds), the geometric contact length, ae the depth of cut and ds the wheel diameter;
   - q = P / (b lc), the heat flux of the net grinding power P over the contact area of ground width b;
   - Rw, the share of the heat entering the workpiece, and beta = sqrt(k rho c), the workpiece's thermal property,
     from `grinding_data.md`.
3. Net grinding power: the spindle power less the spindle's idle power with the wheel running and not in contact,
   P = b (p0 + p1 V) + u Q, with V the specific volume removed since the last dressing (mm3 per mm of width) and
   Q = b ae vw the removal rate. p0, p1 and u are identified by least squares from the machine's power records of
   passes made with the operation's wheel specification and coolant.
4. Burn limit: the highest temperature at which the part's lot was tempered, plus 200 K.
"""

DATA = ("# Grinding data (shop tables)\n\n## Share of the heat entering the workpiece, Rw\n\n| wheel | coolant | Rw |\n"
        "|---|---|---|\n" + "\n".join("| %s | %s | %.2f |" % (w, c, r) for (w, c), r in Jm.RW.items()) +
        "\n\n## Workpiece thermal properties\n\n| material | k (W/m K) | rho (kg/m3) | c (J/kg K) |\n|---|---|---|---|\n" +
        "\n".join("| %s | %d | %d | %d |" % (m, *p) for m, p in Jm.PROPS.items()) + "\n")

FORMAT = """# Job package format

Each job's package holds:
- `job_sheet.md`: the machine, the wheel (specification, size when new), the part (material, lot and the ground
  face, as `ground width W mm` or as `ground face W mm wide: two lands of L mm each side of a G mm relief groove`),
  the programmed work speed, the coolant and its temperature, and the dressing interval of the operation (as
  `dressing interval V mm3/mm` or as `dressing every N parts (stock S mm over a L mm long face)`);
- `heat_treatment.md`: the heat treatment certificates of the part lots on the job;
- `machine_log.csv`: work on the machine: `date`, `work_order`, `description` (wheel changes, dressing with the
  wheel diameter after it, coolant and chiller work, spindle and table work);
- `power_log.csv`: the machine's spindle power records: `date`, `pass` (`air` with the wheel running and not in
  contact, or `grind`), `width_mm`, `depth_um`, `work_speed_mm_s`, `volume_since_dressing_mm3_mm`, `spindle_power_w`.
"""


def job_sheet(j):
    _, wheel, coolant, _ = Jm.current(j)
    width = ("ground face %d mm wide: two lands of %d mm each side of a %d mm relief groove" % (2 * j["lands"][0] + j["lands"][1],
             j["lands"][0], j["lands"][1]) if j["lands"] else "ground width %d mm" % j["b"])
    dress = ("dressing every %d parts (stock %.2f mm over a %d mm long face)" % j["parts"] if j["parts"] else
             "dressing interval %d mm3/mm" % j["interval"])
    return ("# Job sheet - %s\n\n- Machine: %s.\n- Wheel: %s, 400 x %d x 127 mm (diameter x width x bore) when new.\n"
            "- Part: %s, lot %s; %s.\n- Operation: plunge surface grinding, work speed %d m/min, %s at %d C; %s.\n"
            % (j["name"], j["machine"], wheel, j["wheel_width"], j["material"], j["lot"], width, j["v_m_min"],
               {"emulsion": "5 percent emulsion", "oil": "straight grinding oil"}[coolant], j["T_job"], dress))


def certs(j):
    out = ["# Heat treatment certificates", ""]
    for lot, temps in sorted(j["certs"].items()):
        line = "- Lot %s (%s): hardened, oil quenched; tempered 2 h at %d C" % (lot, j["material"], temps[0])
        for t in temps[1:]:
            line += "; re-tempered 2 h at %d C after a hardness check" % t
        out.append(line + ".")
    return "\n".join(out) + "\n"


def records(j, rnd, nr):
    """Power records from the first history period to the job: sessions of 2 air passes and 12 grind passes; the
    wheel is dressed when the specific volume reaches 35 to 60 percent of the job's dressing interval (the shop's
    other work dresses earlier), and each dressing takes the diameter down a little; the current wheel's last
    dressing gives the diameter on the job sheet."""
    rows, events = [], []
    hist = j["history"]
    dates = []
    d0 = np.datetime64(hist[0][0])
    for k in range(int((np.datetime64("2026-04-20") - d0) / np.timedelta64(1, "D"))):
        day = d0 + np.timedelta64(k, "D")
        if day.astype("datetime64[D]").item().weekday() < 5 and rnd.random() < 0.35:
            dates.append(str(day))
    V = 0.0
    cur = None
    target = j["interval"] * rnd.uniform(0.35, 0.6)
    for date in dates:
        per = [h for h in hist if h[0] <= date][-1]
        if per is not cur:
            if cur is not None and per[1] != cur[1]:
                events.append([per[0], "wheel", "Wheel %s removed; new wheel %s 400 x %d x 127 fitted and dressed." % (cur[1], per[1], j["wheel_width"])])
                V = 0.0
            if cur is not None and per[2] != cur[2]:
                events.append([per[0], "note", "Coolant changed from %s to %s; system flushed." % (
                    {"emulsion": "5 percent emulsion", "oil": "straight grinding oil"}[cur[2]],
                    {"emulsion": "5 percent emulsion", "oil": "straight grinding oil"}[per[2]])])
            if cur is not None and per[1] == cur[1] and per[2] == cur[2]:
                events.append([per[0], "note", "Spindle bearings replaced; spindle run in."])
            cur = per
        _, wheel, coolant, idle = per
        p0, p1, u = Jm.PM[(wheel, coolant)]
        idle_s = idle * (1 + 0.02 * nr.standard_normal())
        for _ in range(2):
            rows.append([date, "air", 0, 0, 0, round(V, 1), round(idle_s * (1 + 0.004 * nr.standard_normal()))])
        for _ in range(12):
            b = rnd.choice([10, 12, 14, 16, 18, 20, 22, 25, 30])
            a = rnd.choice([3, 4, 5, 6, 8, 10, 12, 15])
            v = rnd.choice([100, 133, 150, 200, 250, 300, 333])
            P = b * (p0 + p1 * V) + u * b * (a / 1000) * v
            rows.append([date, "grind", b, a, v, round(V, 1), round(idle_s + P * (1 + 0.012 * nr.standard_normal()))])
            V += a / 1000 * 100 * 30          # mm3/mm per pass: 100 mm stroke, 30 strokes
            if V >= target:
                events.append([date, "dress", None])
                V = 0.0
                target = j["interval"] * rnd.uniform(0.35, 0.6)
    events.append(["2026-04-21", "dress", None])
    # diameters: each wheel goes down evenly from 400 mm at fitting; the current wheel ends at the job sheet's diameter
    log, seg = [], []
    def flush(seg, end):
        n = len(seg)
        for k, e in enumerate(seg):
            log.append([e[0], "Wheel dressed; diameter %.1f mm." % (400 - (400 - end) * (k + 1) / n)])
    for e in events:
        if e[1] == "dress":
            seg.append(e)
        else:
            if e[1] == "wheel":
                flush(seg, 400 - (400 - j["d_now"]) * 0.8); seg = []
            log.append([e[0], e[2]])
    flush(seg, j["d_now"])
    if j["chiller"]:
        log.append([j["chiller"][0], "Coolant chiller compressor failed; chiller out of service awaiting parts, coolant "
                    "running at %d C." % j["chiller"][1]])
    if j["table_limit"]:
        log.append([j["table_limit"][0], "Table hydraulic valve replaced; table speed limited to %d m/min until the "
                    "servo valve is delivered." % j["table_limit"][1]])
    return rows, log


NOISE = ["Way lube refilled", "Coolant filter replaced", "Magnetic chuck ground true", "Guard interlock checked",
         "Dresser diamond indexed", "Coolant concentration checked", "Hydraulic oil level topped up"]


def write(j, out):
    os.makedirs(out, exist_ok=True)
    rnd = random.Random(j["seed"]); nr = np.random.default_rng(j["seed"])
    open(os.path.join(out, "job_sheet.md"), "w").write(job_sheet(j))
    open(os.path.join(out, "heat_treatment.md"), "w").write(certs(j))
    rows, log = records(j, rnd, nr)
    for k in range(6):
        d = "%d-%02d-%02d" % (rnd.choice([2025, 2026]), rnd.randint(1, 12), rnd.randint(1, 28))
        if "2025-11-01" <= d <= "2026-04-20":
            log.append([d, rnd.choice(NOISE) + "."])
    log.sort()
    with open(os.path.join(out, "machine_log.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "work_order", "description"])
        for d, t in log:
            w.writerow([d, "WO-%s-%04d" % (d[:4], rnd.randint(100, 9999)), t])
    with open(os.path.join(out, "power_log.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "pass", "width_mm", "depth_um", "work_speed_mm_s", "volume_since_dressing_mm3_mm", "spindle_power_w"])
        w.writerows(rows)
