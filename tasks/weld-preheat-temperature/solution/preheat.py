"""Reference program: python3 preheat.py JOB_DIR OUT_JSON

Writes the MS-PH minimum preheat of a butt-welded joint (min_preheat_c):
- reads the joint sheet (number, station, arc monitor, the two plates, the consumable batch of each kind of run) and
  the shop log of the joint's station: a plate rejected and replaced, the arc monitor's current reading found high or low at a
  check (the runs before the check corrected), a wire spool of another batch fitted (the runs after it welded with
  that batch);
- each plate's heat is the heat whose certificate lists the plate's mark; its composition is its own product analysis
  when the certificate gives one, else its heat's cast analysis;
- the runs are the monitor's records of the joint (the monitor records every run at its station);
- each run's heat input is k P / v from the monitor's record: P the mean current times the mean arc voltage, or the
  mean of the instantaneous arc power of its waveform record for a pulsed run; v the length over the arc time; where
  the monitor senses voltage at the power source, the arc voltage is that voltage less the drop I R in the welding
  and return cables (per sample for a waveform record);
- each run's diffusible hydrogen is its batch's certificate value, plus for covered electrodes in an unheated quiver
  the pick-up s E, E the integral of the vapor pressure of the station's bay (its climate logger's hourly readings,
  linear between readings) from the last issue at the station to the start of the run, s fitted to the shop's
  exposure tests; the covered electrodes are of the batch the oven issued to the station;
- per plate, the hydrogen preheat (clause 2) is the highest over the runs, and the hardness preheat (clause 3) the
  lowest T0 at which every capping run's t8/5 (the larger of t2 and t3) reaches the t8/5 at which the HAZ hardness is
  380 HV10; the joint's minimum preheat is the highest over the plates and both clauses.
"""
import csv, json, math, os, re, sys
import numpy as np
from scipy.optimize import brentq

DATA = "/app/data/docs/welding_data.md"
K = {"111": 0.8, "135": 0.8, "136": 0.8, "141": 0.6}


def minutes(ts):
    h, m = ts.split()[1].split(":")
    return int(h) * 60 + int(m)


def vapor(T, RH):
    return RH / 100 * 0.61094 * math.exp(17.625 * T / (T + 243.04))


def loops():
    out = {}
    for ln in open(DATA):
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) == 4 and re.fullmatch(r"M\d+", c[0]):
            out[c[0]] = float(c[3]) / 1000 if re.fullmatch(r"[\d.]+", c[3]) else 0.0
    return out


def bays():
    out = {}
    for ln in open(DATA):
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) == 3 and re.fullmatch(r"WS-\d+", c[0]):
            out[c[0]] = c[2]
    return out


def pickup_rates():
    rows = {}
    for ln in open(DATA):
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) == 6 and re.fullmatch(r"[\d.]+", c[2]):
            rows.setdefault(c[0], []).append((float(c[2]) * vapor(float(c[3]), float(c[4])), float(c[5])))
    s = {}
    for desig, pts in rows.items():
        E, H = np.array(pts).T
        s[desig] = np.polyfit(E, H, 1)[0]
    return s


def parse_analysis(txt):
    return {e: float(v) for e, v in re.findall(r"([A-Z][a-z]?) ([\d.]+)", txt)}


def assess(d, skip=()):
    js = open(os.path.join(d, "joint_sheet.md")).read()
    station, monitor = re.search(r"welded at (\S+) \(arc monitor (\S+)\)", js).groups()
    jno = re.search(r"- Joint: (\S+),", js).group(1)
    plates = [dict(mark=m, heat=h, d=float(t)) for m, h, t in
              re.findall(r"- Plate [AB]: (\S+), \S+, heat (\S+), (\d+) mm", js)]
    sheet = {}
    for kind, proc, desig, batch in re.findall(r"- (Root run|Fill runs|Capping runs): process (\d+)(?: \(pulsed\))?, "
                                               r"(.+?), batch (\S+);", js):
        sheet[{"Root run": "root", "Fill runs": "fill", "Capping runs": "cap"}[kind]] = (proc, desig, batch)
    nominal = {}
    for kind, I, U, v in re.findall(r"- (Root run|Fill runs|Capping runs): .*nominal (\d+) A, ([\d.]+) V, (\d+) mm/min", js):
        nominal[{"Root run": "root", "Fill runs": "fill", "Capping runs": "cap"}[kind]] = (float(I), float(U), float(v))
    log = [r for r in csv.DictReader(open(os.path.join(d, "shop_log.csv"))) if r["station"] == station]
    calib, spools = [], []
    for r in sorted(log, key=lambda r: r["time"]):
        e = r["entry"]
        m = re.search(r"%s: plate (\S+) \(heat \S+\) rejected .*replaced by plate (\S+), heat (\S+), (\d+) mm" % re.escape(jno), e)
        if m and "plates" not in skip:
            for p in plates:
                if p["mark"] == m.group(1):
                    p.update(mark=m.group(2), heat=m.group(3), d=float(m.group(4)))
        m = re.search(r"Arc monitor %s checked .*current reading ([\d.]+) percent (high|low)" % re.escape(monitor), e)
        if m and "calib" not in skip:
            calib.append((r["time"], 1 + float(m.group(1)) / 100 * (1 if m.group(2) == "high" else -1)))
        m = re.search(r"Wire spool changed: batch (\S+) used up, .* batch (\S+) fitted", e)
        if m and "spool" not in skip:
            spools.append((r["time"], m.group(1), m.group(2)))
    # compositions
    mc = open(os.path.join(d, "mill_certificates.md")).read()
    cast, product = {}, {}
    any_product, heat_of = {}, {}
    for sec in mc.split("\n## ")[1:]:
        heat = re.match(r"Heat (\S+),", sec).group(1)
        for m in re.findall(r"(P-\d+) \(\d+ mm\)", re.search(r"- Plates: (.*)", sec).group(1)):
            heat_of[m] = heat
        cast[heat] = parse_analysis(re.search(r"Cast analysis \(mass percent\): (.*)\.", sec).group(1))
        for m, txt in re.findall(r"Product analysis of plate (\S+) \(mass percent\): (.*)\.", sec):
            product[m] = parse_analysis(txt)
            any_product.setdefault(heat, product[m])
    for p in plates:
        if "sheet_heat" not in skip:
            p["heat"] = heat_of.get(p["mark"], p["heat"])
        if p["mark"] in product and "product" not in skip:
            p["c"] = product[p["mark"]]
        elif "sister" in skip and p["heat"] in any_product:
            p["c"] = any_product[p["heat"]]
        else:
            p["c"] = cast[p["heat"]]
    # consumables
    hd0, desig_of = {}, {}
    for b, desig, proc, hd in re.findall(r"- Batch (\S+): (.+?) \(process (\d+)\); diffusible hydrogen ([\d.]+)",
                                        open(os.path.join(d, "consumables.md")).read()):
        hd0[b] = float(hd); desig_of[b] = desig
    s_rate = pickup_rates()
    logger = "B1" if "logger" in skip else bays()[station]
    clim = [r for r in csv.DictReader(open(os.path.join(d, "climate_log.csv"))) if r["logger"] == logger]
    ct = np.array([minutes(r["time"]) for r in clim], float)
    cp = np.array([vapor(float(r["temp_c"]), float(r["rh_pct"])) for r in clim])

    def exposure(t0, t1):
        if t1 <= t0:
            return 0.0
        x = np.linspace(t0, t1, 600)
        return float(np.trapezoid(np.interp(x, ct, cp), x) / 60)
    elog = sorted((r for r in csv.DictReader(open(os.path.join(d, "electrode_log.csv"))) if r["station"] == station),
                  key=lambda r: r["time"])
    runs = []
    for r in csv.DictReader(open(os.path.join(d, "monitor_runs.csv"))):
        if r["joint"] != jno and "foreign" not in skip:
            continue
        kind, proc = r["kind"], r["process"]
        t_run = r["start"]
        fac = 1.0
        for tc, f in calib:
            if t_run < tc:
                fac = f
                break
        R = 0.0 if "cable" in skip else loops().get(monitor, 0.0)
        if "nominal" in skip:
            I, U, vmin = nominal[kind]
            P, v = I * U, vmin / 60
        else:
            if r["waveform"] and "pulse" not in skip:
                w = np.loadtxt(os.path.join(d, r["waveform"]), delimiter=",", skiprows=1)
                I = w[:, 1] / fac
                if "cable_mean" in skip:
                    P = float(np.mean(I * w[:, 2]) - R * np.mean(I) ** 2)
                else:
                    P = float(np.mean(I * (w[:, 2] - R * I)))
            elif r["waveform"]:
                w = np.loadtxt(os.path.join(d, r["waveform"]), delimiter=",", skiprows=1)
                I = float(np.mean(w[:, 1] / fac))
                P = I * (float(np.mean(w[:, 2])) - R * I)
            else:
                I = float(r["mean_current_a"]) / fac
                P = I * (float(r["mean_voltage_v"]) - R * I)
            v = float(r["length_mm"]) / float(r["arc_time_s"])
        Q = K[proc] * P / v / 1000
        batch = sheet[kind][2]
        for ts, old, new in spools:
            if old == batch and t_run >= ts:
                batch = new
        if proc == "111" and "issued" not in skip:      # covered electrodes: the batch in the station's quiver
            issued = [e for e in elog if e["time"] <= t_run and e["event"].startswith("issued")
                      and desig_of.get(e["batch"]) == desig_of[batch]]
            if issued:
                batch = issued[-1]["batch"]
        HD = hd0[batch]
        if desig_of[batch] in s_rate and "exposure" not in skip:
            issue = [e for e in elog if e["batch"] == batch and e["time"] <= t_run and e["event"].startswith("issued")]
            if issue:
                last = issue[0] if "reissue" in skip else issue[-1]
                if "unheated" in last["event"]:
                    HD += s_rate[desig_of[batch]] * exposure(minutes(last["time"]), minutes(t_run))
        runs.append((kind, Q, HD))
    best = -273.0
    for p in plates:
        c = p["c"]
        CET = c["C"] + (c["Mn"] + c["Mo"]) / 10 + (c["Cr"] + c["Cu"]) / 20 + c["Ni"] / 40
        CE = c["C"] + c["Si"] / 11 + c["Mn"] / 8 + c["Cu"] / 9 + c["Cr"] / 5 + c["Ni"] / 17 + c["Mo"] / 6 + c["V"] / 3
        dd = p["d"]
        if "no_hydrogen" not in skip:
            for _, Q, HD in runs:
                best = max(best, 697 * CET + 160 * math.tanh(dd / 35) + 62 * HD ** 0.35 + (53 * CET - 32) * Q - 328)
        if "no_hardness" in skip:
            continue
        C = c["C"]
        tmin = 10 ** ((2019 * (C + 0.3 * (CE - C)) + 66 - 380) / (2019 * 0.5 * C + 66 * 0.8))
        for kind, Q, _ in runs:
            if kind != "cap" and "hard_all" not in skip:
                continue

            def t85(T0):
                t3 = (6700 - 5 * T0) * Q * (1 / (500 - T0) - 1 / (800 - T0)) * 0.9
                t2 = (4300 - 4.3 * T0) * 1e5 * (Q / dd) ** 2 * (1 / (500 - T0) ** 2 - 1 / (800 - T0) ** 2) * 1.0
                return t3 if "3d" in skip else t2 if "2d" in skip else max(t2, t3)
            if t85(-100) >= tmin:
                continue
            best = max(best, brentq(lambda T: t85(T) - tmin, -100, 450, xtol=1e-9))
    return {"min_preheat_c": round(best, 3)}


def main(pkg, out):
    with open(out, "w") as f:
        json.dump(assess(pkg), f)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
