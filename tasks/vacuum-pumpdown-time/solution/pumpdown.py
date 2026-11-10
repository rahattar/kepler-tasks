"""Reference program: python3 pumpdown.py JOB_DIR OUT_JSON

Writes the MS-VP pump-down time of a chamber's job (pumpdown_min):
- the chamber as it is on the job's date: the chamber sheet, changed by the equipment log (a rerouted roughing line,
  spool pieces, rebuilt internals with their new volume, door seals, turbo exchanges), with the pumps and the
  crossover pressure as the controller reports them in the chamber's latest pump-down record;
- the walls' gas load Q_w1 (t / 1 h)^-alpha_w and the air leak Q_L fitted to the chamber's air-vent pump-down records
  since its internals were last rebuilt, each record taken with its own pumps, gauges and load (from its header) and
  the chamber's volume and line on its date: in high vacuum, the gas load is S_eff p + V dp/dt, less the outgassing
  of the record's load and of the spool pieces; one leak per door seal;
- pressures: indicated pressure times the gauge's calibration factor, times 1.12 for a cold cathode gauge in high
  vacuum (water vapor);
- the pump-down integrates V dp/dt = -S_eff p + Q(t) from 1013 mbar, roughing to the crossover and then the turbo
  pump, to the job's process pressure.
"""
import csv, glob, json, math, os, re, sys
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import least_squares

DATA = "/app/data/docs/vacuum_data.md"


def tables():
    rough, turbo, outgas, sec = {}, {}, {}, None
    for ln in open(DATA):
        if ln.startswith("## "):
            sec = ln
            continue
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) == 2 and "mbar" in c[1]:
            pts = [(float(a), float(b)) for a, b in re.findall(r"([\d.e+-]+) mbar ([\d.]+) L/s", c[1])]
            (rough if "Roughing" in sec else turbo)[c[0]] = pts
        if len(c) == 3 and "Outgassing" in sec and re.fullmatch(r"\d[\d.]*(e[+-]?\d+)?", c[1]):
            outgas[c[0]] = (float(c[1]), float(c[2]))
    return rough, turbo, outgas


def curve(pts, p):
    return float(np.interp(math.log10(max(p, 1e-12)), [math.log10(a) for a, _ in pts], [b for _, b in pts]))


def knudsen(D, L, p):
    return 135 * D ** 4 * p / L + 12.1 * D ** 3 / L * (1 + 192 * D * p) / (1 + 237 * D * p)


def parse_load(txt, outgas):
    if txt.strip() == "empty":
        return []
    out = []
    for item in txt.split("; "):
        m = re.match(r"(.+) \((.+), ([\d.]+) m2\)", item.strip().rstrip("."))
        mat = m.group(2)
        out.append((float(m.group(3)) * 1e4,) + outgas[mat])
    return out


def assess(d, skip=()):
    rough_t, turbo_t, outgas = tables()
    cs = open(os.path.join(d, "chamber_sheet.md")).read()
    sheet = dict(V=float(re.search(r"Volume: ([\d.]+) L", cs).group(1)),
                 rough=re.search(r"Roughing pump: (\S+)\.", cs).group(1),
                 D=float(re.search(r"Roughing line: (\d+) mm bore", cs).group(1)) / 10,
                 L=float(re.search(r"mm bore, ([\d.]+) m long", cs).group(1)) * 100,
                 turbo=re.search(r"Turbo pump: (\S+)\.", cs).group(1),
                 C_hv=float(re.search(r"port conductance: ([\d.]+) L/s", cs).group(1)),
                 p_x=float(re.search(r"Crossover pressure: ([\d.e+-]+) mbar", cs).group(1)))
    g = re.search(r"Gauges: Pirani (\S+), cold cathode (\S+)\.", cs)
    sheet_gauges = (g.group(1), g.group(2))
    js = open(os.path.join(d, "job_sheet.md")).read()
    jdate = re.search(r"Date: (\S+)\.", js).group(1)
    jload = parse_load(re.search(r"- Load: (.*)\.\n", js).group(1), outgas)
    p_target = float(re.search(r"Process pressure: ([\d.e+-]+) mbar", js).group(1))
    certs = {}
    for s_, dt, f in re.findall(r"gauge (\S+): calibrated (\S+), calibration factor (\d+\.\d+)",
                                open(os.path.join(d, "gauge_certificates.md")).read()):
        certs.setdefault(s_, []).append((dt, float(f)))

    def factor(serial, date):
        cs = sorted(certs[serial])
        if "cert_date" in skip:
            return cs[-1][1]
        return [f for dt, f in cs if dt <= date][-1]
    name = re.search(r"Chamber sheet - (\S+)", cs).group(1)
    log = sorted(csv.DictReader(open(os.path.join(d, "equipment_log.csv"))), key=lambda r: r["date"])
    ss = outgas["stainless steel, as machined"]

    def state(date):
        s = dict(V=sheet["V"], D=sheet["D"], L=sheet["L"], spools=[], spool_v=[], rebuilt="0", seal="0")
        for r in log:
            if r["date"] > date:
                continue
            e = r["entry"]
            m = re.match(r"Roughing line rerouted: (\d+) mm bore, ([\d.]+) m long", e)
            if m and "line" not in skip:
                s["D"], s["L"] = float(m.group(1)) / 10, float(m.group(2)) * 100
            m = re.match(r"Spool piece fitted .*: (\d+) mm bore, (\d+) mm long", e)
            if m and "spool" not in skip:
                Dm, Lm = float(m.group(1)) / 1000, float(m.group(2)) / 1000
                s["V"] += math.pi / 4 * Dm ** 2 * Lm * 1000
                s["spool_v"].append((r["date"], math.pi / 4 * Dm ** 2 * Lm * 1000))
                s["spools"].append((math.pi * Dm * Lm * 1e4,) + ss)
            m = re.match(r"Internals rebuilt: .*; chamber volume now ([\d.]+) L", e)
            if m and "internals" not in skip:
                s["V"], s["rebuilt"] = float(m.group(1)), r["date"]
            if e.startswith("Door seal replaced") and "seal" not in skip:
                s["seal"] = r["date"]
            if e.startswith("Load lock merged into the chamber") and "internals" not in skip:
                s["rebuilt"] = r["date"]
        return s

    def volume(r):
        """The chamber volume from a record's roughing: t(300 -> 3 mbar) = V x integral dp / (S_eff p)."""
        st = state(r["date"])
        fp = factor(r["gauges"][0], r["date"])
        pr = [(float(x["time_s"]), float(x["pirani_mbar"]) * fp) for x in r["rows"] if x["stage"] == "rough" and x["pirani_mbar"]]
        def t_at(pt):
            for (t1, p1), (t2, p2) in zip(pr, pr[1:]):
                if p1 >= pt >= p2:
                    return t1 + (t2 - t1) * math.log(p1 / pt) / math.log(p1 / p2)
        lp = np.linspace(math.log(3.0), math.log(300.0), 400)
        f = [1 / (1 / curve(rough_t[r["rough"]], math.exp(x)) + 1 / knudsen(st["D"], st["L"], math.exp(x))) for x in lp]
        return (t_at(3.0) - t_at(300.0)) / np.trapezoid(1 / np.array(f), lp)

    recs = []
    for f in sorted(glob.glob(os.path.join(d, "pumpdown_records", "*.csv"))):
        head = {}
        lines = open(f).read().splitlines()
        for ln in lines:
            if ln.startswith("# "):
                k, _, v = ln[2:].partition(": ")
                head[k.split(" - ")[0]] = v
        date = re.search(r"(\d{4}-\d\d-\d\d)", lines[0]).group(1)
        if re.search(r"Pump-down record - (\S+),", lines[0]).group(1) != name and "misfiled" not in skip:
            continue
        rows = list(csv.DictReader([ln for ln in lines if not ln.startswith("#")]))
        pm = re.search(r"roughing (\S+), turbo (\S+)", head["Pumps"])
        gm = re.search(r"Pirani (\S+), cold cathode (\S+)", head["Gauges"])
        recs.append(dict(date=date, vent=head["Vent"], load=parse_load(head["Load"], outgas),
                         rough=pm.group(1) if "header_pumps" not in skip else sheet["rough"],
                         turbo=pm.group(2) if "header_pumps" not in skip else sheet["turbo"],
                         gauges=(gm.group(1), gm.group(2)) if "header_gauges" not in skip else sheet_gauges,
                         p_x=float(re.search(r"crossover at ([\d.e+-]+) mbar", head["Controller"]).group(1)),
                         rows=rows))
    now = state(jdate)
    use = [r for r in recs if ("n2" in skip or r["vent"].startswith("air")) and r["date"] >= now["rebuilt"]]
    periods = sorted({state(r["date"])["seal"] for r in use})
    T, Y, PER, EXTRA = [], [], [], []
    for r in use:
        st = state(r["date"])
        fc = factor(r["gauges"][1], r["date"]) * (1.0 if "water" in skip else 1.12)
        hv = [(float(x["time_s"]), float(x["cold_cathode_mbar"]) * fc) for x in r["rows"]
              if x["stage"] == "high" and x["cold_cathode_mbar"]]
        t0 = hv[0][0] + 600
        hv = [h for h in hv if h[0] >= t0]
        ts = np.array([h[0] for h in hv]); ps = np.array([h[1] for h in hv])
        dpdt = np.gradient(ps, ts)
        S = np.array([1 / (1 / curve(turbo_t[r["turbo"]], p) + 1 / sheet["C_hv"]) for p in ps])
        Q = S * ps + (0.0 if "quasi" in skip else st["V"] * dpdt)
        th = ts / 3600
        extra = sum(A * q1 * th ** -a for A, q1, a in (r["load"] if "record_load" not in skip else []) + st["spools"])
        T += list(th); Y += list(Q); EXTRA += list(np.zeros_like(th) + extra)
        PER += [periods.index(st["seal"])] * len(th)
    T, Y, EXTRA, PER = map(np.array, (T, Y, EXTRA, PER))
    n = len(periods)

    def res(x):
        Qw1, a = math.exp(x[0]), x[1]
        QL = np.exp(np.array(x[2:]))[PER]
        return np.log(QL + Qw1 * T ** -a + EXTRA) - np.log(Y)
    x0 = [math.log(np.median(Y)), 1.0] + [math.log(np.median(Y) * 1e-3)] * n
    fit = least_squares(res, x0, method="lm")
    Qw1, a_w = math.exp(fit.x[0]), fit.x[1]
    QL = math.exp(fit.x[2 + periods.index(now["seal"])])       # the leak since the last door seal
    last = max(recs, key=lambda r: r["date"])
    if "volume" not in skip:
        vrec = [r for r in recs if r["date"] >= now["rebuilt"]]
        Vn = float(np.mean([volume(r) for r in vrec])) + sum(v for dt, v in now["spool_v"] if dt > vrec[-1]["date"])
    else:
        Vn = now["V"]
    rough = last["rough"]; turbo = last["turbo"]
    p_x = sheet["p_x"] if "header_crossover" in skip else last["p_x"]
    surf = [(1.0, Qw1, a_w)] + now["spools"] + ([] if "no_load" in skip else jload)

    def Qt(t_s):
        t = max(t_s / 3600, 0.05)
        return QL + sum(A * q1 * t ** -al for A, q1, al in surf)

    def Seff_r(p):
        S = curve(rough_t[rough], p)
        if "nominal" in skip:
            S = max(s for _, s in rough_t[rough])
        if "conductance" in skip:
            return S
        C = 12.1 * now["D"] ** 3 / now["L"] if "molecular" in skip else knudsen(now["D"], now["L"], p)
        return S * C / (S + C)

    def Seff_h(p):
        S = curve(turbo_t[turbo], p)
        if "nominal" in skip:
            S = max(s for _, s in turbo_t[turbo])
        return S * sheet["C_hv"] / (S + sheet["C_hv"])

    def ev(target):
        f = lambda t, y: y[0] - math.log(target)
        f.terminal, f.direction = True, -1
        return f
    r1 = solve_ivp(lambda t, y: [(-Seff_r(math.exp(y[0])) * math.exp(y[0]) + Qt(t)) / (Vn * math.exp(y[0]))],
                   (0, 12 * 3600), [math.log(1013.0)], events=ev(p_x), method="LSODA", rtol=1e-8, atol=1e-10,
                   max_step=5.0)
    tx = r1.t_events[0][0]
    r2 = solve_ivp(lambda t, y: [(-Seff_h(math.exp(y[0])) * math.exp(y[0]) + Qt(t)) / (Vn * math.exp(y[0]))],
                   (tx, 24 * 3600), [math.log(p_x)], events=ev(p_target), method="LSODA", rtol=1e-8, atol=1e-10,
                   max_step=20.0)
    return {"pumpdown_min": round(r2.t_events[0][0] / 60, 3)}


def main(pkg, out):
    with open(out, "w") as f:
        json.dump(assess(pkg), f)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
