"""Documents of each joint's package, and the standard, the welding data and the package format the joints share."""
import csv, os
import numpy as np
import jobs as Jm
import weld as W

STANDARD = """# MS-PH Minimum preheat of butt welds in structural steel (owner's standard, revision 2)

1. The minimum preheat temperature of a joint is the highest of the requirements of clauses 2 and 3, over both plates
   of the joint, each plate taken with its own composition and thickness. It is also the joint's minimum interpass
   temperature.
2. Hydrogen cracking (EN 1011-2, Annex C, method B). For each run of the joint,
   Tp = 697 CET + 160 tanh(d / 35) + 62 HD^0.35 + (53 CET - 32) Q - 328 (C), where:
   - CET = C + (Mn + Mo) / 10 + (Cr + Cu) / 20 + Ni / 40, in mass percent;
   - d is the plate thickness (mm);
   - HD is the diffusible hydrogen of the run's weld metal (ml per 100 g of deposited metal), clause 5;
   - Q is the run's heat input (kJ/mm), clause 4.
3. HAZ hardness. The hardness of the plate's heat affected zone under each capping run (no later run tempers it) must
   not exceed 380 HV10:
   - HV = 2019 [C (1 - 0.5 log t) + 0.3 (CE - C)] + 66 (1 - 0.8 log t), with t the run's cooling time t8/5 (s),
     log to base 10, and CE = C + Si / 11 + Mn / 8 + Cu / 9 + Cr / 5 + Ni / 17 + Mo / 6 + V / 3;
   - t8/5 at the preheat temperature T0 (C) is the larger of
     t3 = (6700 - 5 T0) Q [1 / (500 - T0) - 1 / (800 - T0)] F3 and
     t2 = (4300 - 4.3 T0) 10^5 (Q / d)^2 [1 / (500 - T0)^2 - 1 / (800 - T0)^2] F2,
     with F2 = 1.0 and F3 = 0.9 for a capping run of a butt weld (EN 1011-2, Annex D).
4. Heat input. Q = k P / v / 1000 for each run as welded, from the arc monitor's record of the run, where:
   - k is the thermal efficiency of the process: 0.8 for processes 111, 135 and 136, and 0.6 for process 141;
   - P (W) is the arc power: the mean current times the mean arc voltage, or, for a waveform-controlled (pulsed) run,
     the mean of the instantaneous arc power over the run's waveform record;
   - v (mm/s) is the travel speed: the run's length divided by its arc time.
5. Diffusible hydrogen. HD is the certificate value of the consumable batch the run was welded with (ISO 3690). Covered
   electrodes in an unheated quiver also pick up moisture from the shop air: HD = HD0 + s E, where:
   - HD0 is the batch's certificate value;
   - E (kPa h) is the time integral of the water vapor partial pressure of the shop air, from the time the electrodes
     were issued to the quiver until the start of the run;
   - s is the pick-up rate of the electrode type, from the shop's exposure tests (`welding_data.md`).
   Electrodes in a heated quiver pick up no moisture. Electrodes returned to the oven and issued again count from the
   new issue. The vapor pressure is p = RH / 100 x 0.61094 exp(17.625 T / (T + 243.04)) kPa, with T the air
   temperature (C) and RH its relative humidity (percent).
"""

# the shop's exposure tests: (designation, batch, batch's certificate HD, [(hours, T C, RH percent)])
TESTS = [("E 42 4 B 42 H5", "E-7690", 3.5, [(0, 20, 50), (2, 25, 60), (4, 25, 60), (4, 30, 80), (8, 20, 70), (8, 30, 80)]),
         ("E 46 5 1Ni B 32 H5", "N-2190", 3.2, [(0, 20, 50), (2, 25, 60), (4, 30, 80), (6, 20, 70), (8, 25, 75), (8, 30, 80)])]


def tests_table():
    rng = np.random.default_rng(77)
    rows = []
    for desig, batch, hd0, plan in TESTS:
        for h, T, RH in plan:
            hd = hd0 + Jm.PICKUP[desig] * W.vapor_kpa(T, RH) * h + 0.12 * rng.standard_normal()
            rows.append("| %s | %s | %d | %d | %d | %.1f |" % (desig, batch, h, T, RH, hd))
    return "\n".join(rows)


DATA = ("# Welding data (shop tables)\n\n## Exposure tests of covered electrodes\n\n"
        "Electrodes of one batch taken from the holding oven, exposed in the climate chamber, then welded and tested\n"
        "to ISO 3690. Diffusible hydrogen in ml per 100 g of deposited metal.\n\n"
        "| designation | batch | exposure (h) | air temperature (C) | relative humidity (percent) | diffusible hydrogen |\n"
        "|---|---|---|---|---|---|\n" + tests_table() + "\n\n"
        "## Processes\n\n| process | name |\n|---|---|\n| 111 | manual metal arc (covered electrode) |\n"
        "| 135 | metal active gas, solid wire |\n| 136 | metal active gas, flux cored wire |\n| 141 | tungsten inert gas |\n\n"
        "## Arc monitors\n\n| monitor | station | voltage sensed at | loop resistance of the welding and return cables (mOhm) |\n"
        "|---|---|---|---|\n| M1 | WS-1 | the arc (sensing leads at the torch and the work) | - |\n"
        "| M2 | WS-2 | the arc (sensing leads at the torch and the work) | - |\n"
        "| M3 | WS-3 | the power source terminals | %.0f |\n| M4 | WS-4 | the power source terminals | %.0f |\n\n"
        % (1000 * Jm.LOOP["M3"], 1000 * Jm.LOOP["M4"]) +
        "## Shop bays\n\n| station | bay | climate logger |\n|---|---|---|\n| WS-1 | 1 | B1 |\n| WS-2 | 1 | B1 |\n"
        "| WS-3 | 2 | B2 |\n| WS-4 | 2 | B2 |\n")

FORMAT = """# Joint package format

Each joint's package holds:
- `joint_sheet.md`: the joint (number, type, length, station and arc monitor, date), its two plates (mark, grade, heat,
  thickness) and the welding procedure: for the root, fill and capping runs, the process, the consumable (designation
  and batch) and the nominal current, voltage and travel speed. A process may be marked `pulsed`.
- `mill_certificates.md`: the inspection certificates of the plate heats in the shop's stock for the job: for each
  heat, the grade, the plates of the heat, the cast analysis and the CEV; for some plates, a product analysis of the
  plate itself, `Product analysis of plate <mark>`.
- `consumables.md`: the inspection certificates of the consumable batches for the job, with the diffusible hydrogen.
- `monitor_runs.csv`: the station's arc monitor's record of each run it recorded that day: `joint`, `run` (numbered
  within the joint), `kind` (`root`, `fill` or `cap`), `start` (date and time), `process`, `arc_time_s`, `length_mm`,
  `mean_current_a`, `mean_voltage_v` (at the monitor's voltage sensing point), and `waveform`, the file of the run's
  waveform record when one was taken.
- `waveforms/`: waveform records, `t_ms`, `current_a`, `voltage_v`, sampled at 10 kHz.
- `electrode_log.csv`: the electrode oven log of the shop: `time`, `station`, `batch`, `event` (`issued to heated
  quiver`, `issued to unheated quiver`, `returned to oven`).
- `climate_log.csv`: the shop air, hourly, from the climate loggers of the shop's bays: `time`, `logger`, `temp_c`,
  `rh_pct`.
- `shop_log.csv`: the shop's work log: `time`, `station`, `entry`. Besides routine entries (fit-up, inspection,
  gas, grinding discs), entries use the shop's standard texts:
  - `<joint>: plate <mark> (heat <heat>) rejected at UT for a lamination; replaced by plate <mark>, heat <heat>,
    <thickness> mm.`
  - `Arc monitor <monitor> checked against the reference shunt: current reading <x> percent high; recalibrated
    (last check <date>).` (or `low`)
  - `Wire spool changed: batch <batch> used up, <designation> batch <batch> fitted.`
"""

JNO = {"joint-ex": "J-1043", "girder-flange": "J-2114", "tank-course": "J-2172", "boom-chord": "J-2231",
       "column-splice": "J-2290", "hopper-wall": "J-2318", "frame-web": "J-2365", "deck-plate": "J-2402"}
KIND = {"root": "Root run", "fill": "Fill runs", "cap": "Capping runs"}


def tstr(j, minutes):
    return "%s %02d:%02d" % (j["date"], int(minutes) // 60, int(minutes) % 60)


def joint_sheet(j):
    out = ["# Joint sheet - %s" % j["name"], "",
           "- Joint: %s, single-V butt weld, %d mm long, welded at %s (arc monitor %s) on %s." % (
               JNO[j["name"]], j["length"], j["station"], j["monitor"], j["date"])]
    for lab, p in zip("AB", j["sheet_plates"]):
        out.append("- Plate %s: %s, %s, heat %s, %d mm." % (lab, p["mark"], p["grade"], p["heat"], p["d"]))
    out.append("- WPS: WPS-%d rev 2." % (100 + j["seed"]))
    for kind in ("root", "fill", "cap"):
        r = next(r for r in j["runs"] if r["kind"] == kind)
        proc, I, U, v = j["nominal"][kind]
        desig = Jm.DESIG[Jm.BATCHES[r["sheet_batch"]][0]][1]
        pulsed = " (pulsed)" if r["pulse"] else ""
        out.append("- %s: process %s%s, %s, batch %s; nominal %d A, %.1f V, %d mm/min." % (
            KIND[kind], proc, pulsed, desig, r["sheet_batch"], I, U, v))
    return "\n".join(out) + "\n"


def cev(c):
    return c["C"] + c["Mn"] / 6 + (c["Cr"] + c["Mo"] + c["V"]) / 5 + (c["Ni"] + c["Cu"]) / 15


def analysis(c):
    return ", ".join("%s %s" % (e, ("%.3f" % c[e]) if e in ("C", "P", "S", "Nb", "Ti", "V") else "%.2f" % c[e])
                     for e in Jm.E0)


def heats_of(j):
    hs = []
    for p in j["plates"] + j["sheet_plates"]:
        if p["heat"] not in hs:
            hs.append(p["heat"])
    extra = {"joint-ex": ["92031"], "girder-flange": ["84477"], "tank-course": ["84390"], "boom-chord": ["71588"],
             "column-splice": ["65110"], "hopper-wall": ["84213"], "frame-web": ["84520"], "deck-plate": ["84213"]}
    return hs + [h for h in extra[j["name"]] if h not in hs]


def certs(j):
    out = ["# Plate inspection certificates (EN 10204 3.1)", ""]
    plates = {}
    listed = list(j["plates"])
    if j["replaced"]:
        listed.append(j["sheet_plates"][j["replaced"][0]])
    for p in listed:
        plates.setdefault(p["heat"], {})[p["mark"]] = p
    for k, h in enumerate(heats_of(j)):
        grade, c = Jm.HEATS[h]
        ps = plates.get(h, {})
        marks = ", ".join("%s (%d mm)" % (m, p["d"]) for m, p in ps.items()) or "stock plates of the heat"
        out += ["## Heat %s, %s" % (h, grade), "", "- Plates: %s." % marks,
                "- Cast analysis (mass percent): %s." % analysis(c), "- CEV (IIW): %.2f." % cev(c)]
        sis = j["sister"] if j["sister"] and j["sister"][0] == h else None
        if sis:
            marks = marks.rstrip(".") + ", %s (%d mm)" % (sis[1], next(iter(ps.values()))["d"])
            out[-3] = "- Plates: %s." % marks
        for m, p in ps.items():
            if p["product"]:
                out.append("- Product analysis of plate %s (mass percent): %s." % (m, analysis(p["product"])))
        if sis:
            sc = dict(c); sc.update(sis[2])
            out.append("- Product analysis of plate %s (mass percent): %s." % (sis[1], analysis(sc)))
        out.append("")
    return "\n".join(out)


def consumables(j):
    out = ["# Consumable inspection certificates (EN 10204 3.1)", ""]
    batches = []
    for r in j["runs"]:
        for b in (r["sheet_batch"], r["batch"]):
            if b not in batches:
                batches.append(b)
    for b in batches:
        kind, hd = Jm.BATCHES[b]
        proc, desig = Jm.DESIG[kind]
        out.append("- Batch %s: %s (process %s); diffusible hydrogen %.1f ml/100 g (ISO 3690)." % (b, desig, proc, hd))
    return "\n".join(out) + "\n"


def write(j, d):
    os.makedirs(os.path.join(d, "waveforms"), exist_ok=True)
    rng = np.random.default_rng(1000 + j["seed"])
    open(os.path.join(d, "joint_sheet.md"), "w").write(joint_sheet(j))
    open(os.path.join(d, "mill_certificates.md"), "w").write(certs(j))
    open(os.path.join(d, "consumables.md"), "w").write(consumables(j))
    rows = []
    for r in j["runs"]:
        fac = j["calib"][1] if j["calib"] and r["start"] < Jm.hm(j["calib"][0]) else 1.0
        wf = ""
        if r["pulse"]:
            wf = "waveforms/run_{:02d}.csv".format(r["no"])
            t = np.arange(10000) / 10.0                                   # ms, 10 kHz over 1 s
            period = 1000.0 / (148 + 6 * rng.random())                    # ms
            ph = (t / period + rng.random()) % 1.0
            I, U = Jm.pulse_shape(ph, r["pulse"])
            U = U + Jm.LOOP.get(j["monitor"], 0.0) * I
            I = I * fac * (1 + 0.01 * rng.standard_normal(t.size))
            U = U * (1 + 0.008 * rng.standard_normal(t.size))
            with open(os.path.join(d, wf), "w", newline="") as fh:
                w = csv.writer(fh); w.writerow(["t_ms", "current_a", "voltage_v"])
                for a, b, c in zip(t, I, U):
                    w.writerow(["%.1f" % a, "%.1f" % b, "%.2f" % c])
            Im, Um = float(np.mean(I)), float(np.mean(U))
        else:
            Im = r["I"] * fac * (1 + 0.003 * rng.standard_normal())
            Um = (r["U"] + Jm.LOOP.get(j["monitor"], 0.0) * r["I"]) * (1 + 0.003 * rng.standard_normal())
        rows.append([r["start"], JNO[j["name"]], r["no"], r["kind"], tstr(j, r["start"]), r["process"],
                     "%.1f" % (r["arc"] + 0.1 * rng.standard_normal()), j["length"], "%.1f" % Im, "%.2f" % Um, wf])
    for r in j["foreign"]:
        fac = j["calib"][1] if j["calib"] and r["start"] < Jm.hm(j["calib"][0]) else 1.0
        rows.append([r["start"], r["joint"], r["no"], r["kind"], tstr(j, r["start"]), r["process"],
                     "%.1f" % (r["arc"] + 0.1 * rng.standard_normal()), r["L"],
                     "%.1f" % (r["I"] * fac * (1 + 0.003 * rng.standard_normal())),
                     "%.2f" % ((r["U"] + Jm.LOOP.get(j["monitor"], 0.0) * r["I"]) * (1 + 0.003 * rng.standard_normal())), ""])
    rows.sort(key=lambda x: x[0])
    with open(os.path.join(d, "monitor_runs.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["joint", "run", "kind", "start", "process", "arc_time_s", "length_mm", "mean_current_a", "mean_voltage_v",
                    "waveform"])
        w.writerows([x[1:] for x in rows])
    if not any(r["pulse"] for r in j["runs"]):
        os.rmdir(os.path.join(d, "waveforms"))
    # electrode oven log: this joint's events and other stations' events of the day
    ev = []
    for b, (t, heated) in j["issue"].items():
        ev.append((Jm.hm(t), j["station"], b, "issued to %s quiver" % ("heated" if heated else "unheated")))
    if j["rebake"]:
        b, t1, t2 = j["rebake"]
        ev.append((Jm.hm(t1), j["station"], b, "returned to oven"))
        ev.append((Jm.hm(t2), j["station"], b, "issued to unheated quiver"))
    others = [s for s in ("WS-1", "WS-2", "WS-3", "WS-4") if s != j["station"]
              and s not in [o[0] for o in (j["others"] or [])]]
    for k, s in enumerate(others[:2 - len(j["others"] or [])]):
        b = ["E-7690", "N-2190", "E-7781", "E-7802"][(j["seed"] + k) % 4]
        t0 = 380 + 25 * k + int(30 * rng.random())
        ev.append((t0, s, b, "issued to %s quiver" % ("heated" if (j["seed"] + k) % 2 else "unheated")))
        ev.append((t0 + 200 + int(60 * rng.random()), s, b, "returned to oven"))
    for s, b, t1, heated, t2 in (j["others"] or []):
        ev.append((Jm.hm(t1), s, b, "issued to %s quiver" % ("heated" if heated else "unheated")))
        ev.append((Jm.hm(t2), s, b, "returned to oven"))
    ev.sort()
    with open(os.path.join(d, "electrode_log.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["time", "station", "batch", "event"])
        for t, s, b, e in ev:
            w.writerow([tstr(j, t), s, b, e])
    with open(os.path.join(d, "climate_log.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["time", "logger", "temp_c", "rh_pct"])
        mine = Jm.BAY[j["station"]]
        for h in range(5, 19):
            for lg in ("B1", "B2"):
                T, RH = Jm.climate_at(j, 60 * h, None if lg == mine else Jm.other_bay(j))
                w.writerow([tstr(j, 60 * h), lg, "%.1f" % (T + 0.15 * rng.standard_normal()),
                            "%.0f" % (RH + 0.8 * rng.standard_normal())])
    log = shop_log(j, rng)
    with open(os.path.join(d, "shop_log.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["time", "station", "entry"])
        for t, s, e in sorted(log):
            w.writerow([tstr(j, t), s, e])


def shop_log(j, rng):
    st, jn = j["station"], JNO[j["name"]]
    first = j["runs"][0]["start"]
    marks = "; ".join("%s heat %s" % (p["mark"], p["heat"]) for p in j["plates"])
    log = [(first - 25, st, "Fit-up of %s checked: root gap and root face within the WPS; plate marks verified (%s)." % (jn, marks)),
           (first - 12, st, "Shielding gas cylinder checked on %s." % st),
           (j["runs"][0]["start"] + j["runs"][0]["arc"] / 60 + 3, st, "%s: root run inspected (visual): accepted." % jn),
           (j["runs"][-1]["start"] + j["runs"][-1]["arc"] / 60 + 20, st, "%s: visual inspection of the cap: accepted; released for NDT." % jn),
           (first + 95, [s for s in ("WS-1", "WS-2", "WS-3", "WS-4") if s != st][j["seed"] % 3],
            "Grinder disc changed.")]
    for jno in sorted({r["joint"] for r in j["foreign"]}):
        f0 = min(r["start"] for r in j["foreign"] if r["joint"] == jno)
        log.append((f0 - 20, st, "Fit-up of %s checked: root gap and root face within the WPS." % jno))
    if j["replaced"]:
        i, newp, t = j["replaced"]
        old = j["sheet_plates"][i]
        log.append((Jm.hm(t), st, "%s: plate %s (heat %s) rejected at UT for a lamination; replaced by plate %s, heat %s, %d mm."
                    % (jn, old["mark"], old["heat"], newp["mark"], newp["heat"], newp["d"])))
    if j["calib"]:
        t, f = j["calib"]
        log.append((Jm.hm(t), st, "Arc monitor %s checked against the reference shunt: current reading %.1f percent %s; "
                    "recalibrated (last check 2026-01-12)." % (j["monitor"], abs(f - 1) * 100, "high" if f > 1 else "low")))
    if j["spool"]:
        t, b = j["spool"]
        old = next(r["sheet_batch"] for r in j["runs"] if Jm.DESIG[Jm.BATCHES[r["sheet_batch"]][0]][0] ==
                   Jm.DESIG[Jm.BATCHES[b][0]][0])
        log.append((Jm.hm(t), st, "Wire spool changed: batch %s used up, %s batch %s fitted."
                    % (old, Jm.DESIG[Jm.BATCHES[b][0]][1], b)))
    return log
