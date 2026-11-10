"""A second MS-PH program, written separately from solution/preheat.py and sharing no code with it:

    python3 independent.py JOB_DIR OUT_JSON

- Pick-up rate: fitted through the origin to each test's rise over the batch's unexposed test (the reference fits a
  straight line with an intercept).
- Exposure: each hourly climate reading held until the next one (the reference interpolates linearly).
- Pulsed power: the trapezoidal time mean of current x arc voltage (the reference averages the samples); the arc
  voltage is the sensed voltage less the cable drop where the monitor senses at the power source.
- Hardness: the cooling time at 380 HV10 found by bisection on the hardness relation, and the preheat by bisection on
  T0 (the reference solves the first in closed form and uses Brent's method).
- Records: the joint sheet, the certificates, the logs and the monitor records read line by line; the covered
  electrodes' batch is the oven's last issue to the station (the reference matches the designation too).
"""
import csv, json, math, os, sys

DOC = "/app/data/docs/welding_data.md"
EFF = {"111": 0.8, "135": 0.8, "136": 0.8, "141": 0.6}


def hours(stamp):
    hh, mm = stamp.strip().split(" ")[1].split(":")
    return int(hh) + int(mm) / 60.0


def p_vap(T, RH):
    return RH / 100.0 * 0.61094 * math.exp(17.625 * T / (T + 243.04))


def lines(path):
    with open(path) as fh:
        return [ln.rstrip("\n") for ln in fh]


def after(text, key):
    i = text.index(key) + len(key)
    return text[i:]


def number_after(text, key):
    t = after(text, key).strip()
    num = ""
    for ch in t:
        if ch.isdigit() or ch == ".":
            num += ch
        else:
            break
    return float(num.rstrip("."))


def elements(text):
    out = {}
    for part in text.split(","):
        bits = part.split()
        if len(bits) == 2:
            out[bits[0]] = float(bits[1].rstrip("."))
    return out


def loop_ohm(monitor):
    for ln in lines(DOC):
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0] == monitor:
            try:
                return float(cells[3]) / 1000.0
            except ValueError:
                return 0.0
    return 0.0


def bay_logger(station):
    for ln in lines(DOC):
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0] == station:
            return cells[2]
    raise KeyError(station)


def pickup():
    tests = {}
    for ln in lines(DOC):
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) != 6:
            continue
        try:
            h, T, RH, hd = (float(x) for x in cells[2:])
        except ValueError:
            continue
        tests.setdefault((cells[0], cells[1]), []).append((h * p_vap(T, RH), hd))
    rate = {}
    for (desig, _), pts in tests.items():
        base = [hd for e, hd in pts if e == 0][0]
        sxx = sum(e * e for e, _ in pts)
        sxy = sum(e * (hd - base) for e, hd in pts)
        rate[desig] = sxy / sxx
    return rate


def run(pkg, out):
    sheet = lines(os.path.join(pkg, "joint_sheet.md"))
    plates, procs = [], {}
    for ln in sheet:
        if ln.startswith("- Joint:"):
            jno = ln.split(":")[1].split(",")[0].strip()
            station = after(ln, "welded at ").split()[0]
            monitor = after(ln, "(arc monitor ").split(")")[0]
        elif ln.startswith("- Plate "):
            f = [x.strip() for x in ln.split(":", 1)[1].split(",")]
            plates.append(dict(mark=f[0], heat=f[2].split()[1], d=float(f[3].split()[0])))
        elif ln.startswith(("- Root run:", "- Fill runs:", "- Capping runs:")):
            kind = {"Root": "root", "Fill": "fill", "Capping": "cap"}[ln[2:].split()[0]]
            procs[kind] = after(ln, "batch ").split(";")[0].strip()
    # shop log of the joint's station
    with open(os.path.join(pkg, "shop_log.csv")) as fh:
        log = [r for r in csv.DictReader(fh) if r["station"] == station]
    checks, spools = [], []
    for r in log:
        e = r["entry"]
        if e.startswith(jno + ": plate") and "replaced by plate" in e:
            old = e.split("plate ")[1].split()[0]
            rest = after(e, "replaced by plate ").split(",")
            for p in plates:
                if p["mark"] == old:
                    p["mark"], p["heat"] = rest[0].strip(), rest[1].split()[1]
                    p["d"] = float(rest[2].split()[0])
        if e.startswith("Arc monitor %s checked" % monitor):
            pct = number_after(e, "current reading ")
            checks.append((r["time"], 1 + pct / 100 if "percent high" in e else 1 - pct / 100))
        if e.startswith("Wire spool changed"):
            spools.append((r["time"], after(e, "batch ").split()[0], e.rsplit("batch ", 1)[1].split()[0]))
    checks.sort()
    # compositions
    cast, prod, heat, listed = {}, {}, None, {}
    for ln in lines(os.path.join(pkg, "mill_certificates.md")):
        if ln.startswith("## Heat "):
            heat = ln.split()[2].rstrip(",")
        elif ln.startswith("- Plates:"):
            for part in ln.split(":", 1)[1].split(","):
                tok = part.strip().split()
                if tok and tok[0].startswith("P-"):
                    listed[tok[0]] = heat
        elif ln.startswith("- Cast analysis"):
            cast[heat] = elements(ln.split(":", 1)[1])
        elif ln.startswith("- Product analysis of plate "):
            prod[ln.split()[5]] = elements(ln.split(":", 1)[1])
    hd0, desig = {}, {}
    for ln in lines(os.path.join(pkg, "consumables.md")):
        if ln.startswith("- Batch "):
            b = ln.split()[2].rstrip(":")
            desig[b] = ln.split(":", 1)[1].split("(process")[0].strip()
            hd0[b] = number_after(ln, "diffusible hydrogen ")
    rate = pickup()
    with open(os.path.join(pkg, "climate_log.csv")) as fh:
        lg = bay_logger(station)
        clim = sorted((hours(r["time"]), p_vap(float(r["temp_c"]), float(r["rh_pct"])))
                      for r in csv.DictReader(fh) if r["logger"] == lg)

    def expo(h0, h1):
        tot = 0.0
        for k, (t, p) in enumerate(clim):
            t_next = clim[k + 1][0] if k + 1 < len(clim) else 99.0
            a, b = max(t, h0), min(t_next, h1)
            if b > a:
                tot += p * (b - a)
        if h0 < clim[0][0]:
            tot += clim[0][1] * (min(clim[0][0], h1) - h0)
        return tot
    with open(os.path.join(pkg, "electrode_log.csv")) as fh:
        elog = [r for r in csv.DictReader(fh) if r["station"] == station]
    runs = []
    with open(os.path.join(pkg, "monitor_runs.csv")) as fh:
        for r in csv.DictReader(fh):
            if r["joint"] != jno:
                continue
            corr = 1.0
            for t, f in checks:
                if r["start"] < t:
                    corr = f
                    break
            R = loop_ohm(monitor)
            if r["waveform"]:
                with open(os.path.join(pkg, r["waveform"])) as wf:
                    w = []
                    for a in csv.DictReader(wf):
                        i_true = float(a["current_a"]) / corr
                        w.append((float(a["t_ms"]), i_true * (float(a["voltage_v"]) - R * i_true)))
                area = sum((w[i + 1][0] - w[i][0]) * (w[i + 1][1] + w[i][1]) / 2 for i in range(len(w) - 1))
                power = area / (w[-1][0] - w[0][0])
            else:
                i_true = float(r["mean_current_a"]) / corr
                power = i_true * (float(r["mean_voltage_v"]) - R * i_true)
            speed = float(r["length_mm"]) / float(r["arc_time_s"])
            q = EFF[r["process"]] * power / speed / 1000.0
            b = procs[r["kind"]]
            for t, old, new in spools:
                if b == old and r["start"] >= t:
                    b = new
            if r["process"] == "111":
                out_ = [e for e in elog if e["event"].startswith("issued") and e["time"] <= r["start"]]
                if out_:
                    b = max(out_, key=lambda e: e["time"])["batch"]
            hd = hd0[b]
            if desig[b] in rate:
                issues = [e for e in elog if e["batch"] == b and e["event"].startswith("issued") and e["time"] <= r["start"]]
                if issues and max(issues, key=lambda e: e["time"])["event"] == "issued to unheated quiver":
                    t0 = max(e["time"] for e in issues)
                    hd += rate[desig[b]] * expo(hours(t0), hours(r["start"]))
            runs.append((r["kind"], q, hd))
    req = []
    for p in plates:
        c = prod.get(p["mark"], cast[listed.get(p["mark"], p["heat"])])
        cet = c["C"] + (c["Mn"] + c["Mo"]) / 10 + (c["Cr"] + c["Cu"]) / 20 + c["Ni"] / 40
        ce = c["C"] + c["Si"] / 11 + c["Mn"] / 8 + c["Cu"] / 9 + c["Cr"] / 5 + c["Ni"] / 17 + c["Mo"] / 6 + c["V"] / 3
        d = p["d"]
        req += [697 * cet + 160 * math.tanh(d / 35) + 62 * hd ** 0.35 + (53 * cet - 32) * q - 328 for _, q, hd in runs]

        def hardness(t):
            lg = math.log10(t)
            return 2019 * (c["C"] * (1 - 0.5 * lg) + 0.3 * (ce - c["C"])) + 66 * (1 - 0.8 * lg)
        lo, hi = 0.01, 1000.0                         # hardness falls with t
        for _ in range(200):
            mid = math.sqrt(lo * hi)
            lo, hi = (mid, hi) if hardness(mid) > 380 else (lo, mid)
        tneed = hi
        for kind, q, _ in runs:
            if kind != "cap":
                continue

            def cool(T0):
                a = (6700 - 5 * T0) * q * (1 / (500 - T0) - 1 / (800 - T0)) * 0.9
                b = (4300 - 4.3 * T0) * 1e5 * (q / d) ** 2 * (1 / (500 - T0) ** 2 - 1 / (800 - T0) ** 2)
                return max(a, b)
            lo, hi = -100.0, 450.0
            if cool(lo) >= tneed:
                continue
            for _ in range(200):
                mid = (lo + hi) / 2
                lo, hi = (lo, mid) if cool(mid) >= tneed else (mid, hi)
            req.append(hi)
    with open(out, "w") as fh:
        json.dump({"min_preheat_c": round(max(req), 4)}, fh)


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
