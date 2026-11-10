"""A second MS-VP program, written separately from solution/pumpdown.py and sharing no code with it:

    python3 independent.py JOB_DIR OUT_JSON

- Records: only those of the current door seal and internals, after an air vent (the reference fits one leak per
  door seal over all records since the internals were rebuilt).
- Fit: for each alpha on a grid, Q_L and Q_w1 by linear least squares on the gas load itself (the reference fits all
  three by nonlinear least squares on its logarithm), the high-vacuum gas load taken as S_eff p (quasi-static).
- Integration: fixed-step fourth-order Runge-Kutta on ln p (the reference uses LSODA).
- Volume: the time from 100 to 1 mbar of each record since the last change of the chamber's volume, against the
  roughing model's time per liter (the reference uses 300 to 3 mbar and the trapezoidal rule).
- Records and documents read line by line.
"""
import csv, json, math, os, sys

DOC = "/app/data/docs/vacuum_data.md"


def num(tok):
    return float(tok.strip().rstrip(".").rstrip(","))


def read_tables():
    rough, turbo, gas, part = {}, {}, {}, ""
    for ln in open(DOC):
        if ln.startswith("## "):
            part = ln.lower()
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if "pumps" in part and len(cells) == 2 and "L/s" in cells[1]:
            pts = []
            for seg in cells[1].split(";"):
                w = seg.split()
                pts.append((float(w[0]), float(w[2])))
            (rough if "roughing" in part else turbo)[cells[0]] = sorted(pts)
        if "outgassing" in part and len(cells) == 3:
            try:
                gas[cells[0]] = (float(cells[1]), float(cells[2]))
            except ValueError:
                pass
    return rough, turbo, gas


def speed(pts, p):
    x = math.log10(max(p, 1e-12))
    xs = [math.log10(a) for a, _ in pts]
    if x <= xs[0]:
        return pts[0][1]
    if x >= xs[-1]:
        return pts[-1][1]
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            f = (x - xs[i]) / (xs[i + 1] - xs[i])
            return pts[i][1] + f * (pts[i + 1][1] - pts[i][1])


def line_c(D, L, p):
    vis = 135.0 * D ** 4 * p / L
    mol = 12.1 * D ** 3 / L
    return vis + mol * (1 + 192.0 * D * p) / (1 + 237.0 * D * p)


def items(text, gas):
    text = text.strip().rstrip(".")
    if text == "empty":
        return []
    out = []
    for it in text.split(";"):
        inner = it[it.index("(") + 1:it.rindex(")")]
        mat, area = inner.rsplit(",", 1)
        out.append((float(area.split()[0]) * 1e4,) + gas[mat.strip()])
    return out


def solve(lin):
    """2 x 2 normal equations for y = a + b x."""
    n = len(lin)
    sx = sum(x for x, _ in lin); sy = sum(y for _, y in lin)
    sxx = sum(x * x for x, _ in lin); sxy = sum(x * y for x, y in lin)
    det = n * sxx - sx * sx
    return (sy * sxx - sx * sxy) / det, (n * sxy - sx * sy) / det


def run(pkg, out):
    rough_c, turbo_c, gas = read_tables()
    sheet = {}
    chamber = open(os.path.join(pkg, "chamber_sheet.md")).readline().split(" - ")[1].strip()
    for ln in open(os.path.join(pkg, "chamber_sheet.md")):
        if ln.startswith("- ") and ":" in ln:
            k, v = ln[2:].split(":", 1)
            sheet[k.strip()] = v.strip().rstrip(".")
    V0 = num(sheet["Volume"].split()[0])
    rl = sheet["Roughing line"].split()
    D, L = num(rl[0]) / 10, num(rl[3]) * 100
    Chv = num(sheet["High-vacuum port conductance"].split()[0])
    job = {}
    for ln in open(os.path.join(pkg, "job_sheet.md")):
        if ln.startswith("- ") and ":" in ln:
            k, v = ln[2:].split(":", 1)
            job[k.strip()] = v.strip()
    jdate = job["Date"].rstrip(".")
    ptarget = num(job["Process pressure"].split()[0])
    jload = items(job["Load"], gas)
    factor = {}
    for ln in open(os.path.join(pkg, "gauge_certificates.md")):
        if ln.startswith("- ") and "calibration factor" in ln:
            serial = ln.split("gauge ")[1].split(":")[0]
            when = ln.split("calibrated ")[1].split(",")[0]
            factor.setdefault(serial, []).append((when, num(ln.rsplit(" ", 1)[1])))

    def fac(serial, date):
        best = None
        for when, f in factor[serial]:
            if when <= date and (best is None or when > best[0]):
                best = (when, f)
        return best[1]
    with open(os.path.join(pkg, "equipment_log.csv")) as fh:
        log = sorted(csv.DictReader(fh), key=lambda r: r["date"])
    seal, rebuilt, spools, Vnow, spool_vol = "", "", [], V0, []
    D0, L0 = D, L
    for r in log:
        e = r["entry"]
        if r["date"] > jdate:
            continue
        if e.startswith("Roughing line rerouted"):
            w = e.split(":")[1].split()
            D, L = num(w[0]) / 10, num(w[3]) * 100
        elif e.startswith("Spool piece fitted"):
            w = e.split(":")[1].split()
            d_m, l_m = num(w[0]) / 1000, num(w[3]) / 1000
            Vnow += math.pi * d_m * d_m / 4 * l_m * 1000
            spool_vol.append((r["date"], math.pi * d_m * d_m / 4 * l_m * 1000))
            spools.append((math.pi * d_m * l_m * 1e4,) + gas["stainless steel, as machined"])
        elif e.startswith("Internals rebuilt"):
            Vnow = num(e.split("chamber volume now ")[1].split()[0])
            rebuilt = r["date"]
        elif e.startswith("Door seal replaced"):
            seal = r["date"]
        elif e.startswith("Load lock merged"):
            rebuilt = r["date"]
    recs = []
    folder = os.path.join(pkg, "pumpdown_records")
    for fn in sorted(os.listdir(folder)):
        h, rows = {}, []
        with open(os.path.join(folder, fn)) as fh:
            body = []
            for ln in fh:
                if ln.startswith("#"):
                    key, _, val = ln[1:].strip().partition(": ")
                    h[key] = val
                else:
                    body.append(ln)
        rows = list(csv.DictReader(body))
        date = fn[:10]
        title = [k for k in h if k.startswith("Pump-down record")][0]
        if title.split(" - ")[1].split(",")[0].strip() != chamber:
            continue                                         # another chamber's record, filed here by mistake
        recs.append(dict(date=date, h=h, rows=rows))
    vols = []
    for r in recs:
        if r["date"] < rebuilt:
            continue
        rm = r["h"]["Pumps"].split("roughing ")[1].split(",")[0]
        pg = r["h"]["Gauges"].split("Pirani ")[1].split(",")[0]
        Dr, Lr = D0, L0
        for e in log:
            if e["date"] <= r["date"] and e["entry"].startswith("Roughing line rerouted"):
                w = e["entry"].split(":")[1].split()
                Dr, Lr = num(w[0]) / 10, num(w[3]) * 100
        pr = [(float(x["time_s"]), float(x["pirani_mbar"]) * fac(pg, r["date"])) for x in r["rows"]
              if x["stage"] == "rough" and x["pirani_mbar"]]

        def cross(level):
            for (ta, pa), (tb, pb) in zip(pr, pr[1:]):
                if pa >= level >= pb:
                    return ta + (tb - ta) * (math.log(pa) - math.log(level)) / (math.log(pa) - math.log(pb))
        n = 2000
        acc = 0.0
        for k in range(n):                                  # midpoint rule in ln p from 1 to 100 mbar
            p = math.exp(math.log(100.0) * (k + 0.5) / n)
            S = speed(rough_c[rm], p); C = line_c(Dr, Lr, p)
            acc += (math.log(100.0) / n) / (S * C / (S + C))
        vols.append((cross(1.0) - cross(100.0)) / acc)
    if vols:
        Vnow = sum(vols) / len(vols) + sum(v for dt, v in spool_vol if dt > recs[-1]["date"])
    latest = recs[-1]["h"]
    rough_m = latest["Pumps"].split("roughing ")[1].split(",")[0]
    turbo_m = latest["Pumps"].split("turbo ")[1].strip()
    p_x = num(latest["Controller"].split("crossover at ")[1].split()[0])
    pts = []
    for r in recs:
        if r["date"] < max(seal, rebuilt) or not r["h"]["Vent"].startswith("air"):
            continue
        tm = r["h"]["Pumps"].split("turbo ")[1].strip()
        cc = r["h"]["Gauges"].split("cold cathode ")[1].strip()
        load = items(r["h"]["Load"], gas)
        rows = [x for x in r["rows"] if x["stage"] == "high" and x["cold_cathode_mbar"]]
        t_on = float(rows[0]["time_s"])
        for x in rows:
            t = float(x["time_s"])
            if t < t_on + 600:
                continue
            p = float(x["cold_cathode_mbar"]) * fac(cc, r["date"]) * 1.12
            S = 1 / (1 / speed(turbo_c[tm], p) + 1 / Chv)
            th = t / 3600
            q = S * p - sum(A * q1 * th ** -a for A, q1, a in load)
            pts.append((th, q))
    best = None
    for k in range(501):
        a = 0.5 + k * 0.002
        lin = [(th ** -a, q) for th, q in pts]
        QL, Qw = solve(lin)
        err = sum((QL + Qw * x - y) ** 2 / y ** 2 for x, y in lin)
        if best is None or err < best[0]:
            best = (err, a, QL, Qw)
    _, aw, QL, Qw = best
    surf = [(1.0, Qw, aw)] + spools + jload

    def load(t_s):
        th = max(t_s / 3600, 0.05)
        return QL + sum(A * q1 * th ** -a for A, q1, a in surf)

    def f_rough(t, y):
        p = math.exp(y)
        S = speed(rough_c[rough_m], p)
        C = line_c(D, L, p)
        return (-(S * C / (S + C)) * p + load(t)) / (Vnow * p)

    def f_high(t, y):
        p = math.exp(y)
        S = speed(turbo_c[turbo_m], p)
        return (-(S * Chv / (S + Chv)) * p + load(t)) / (Vnow * p)

    def rk4(f, t, y, h):
        k1 = f(t, y); k2 = f(t + h / 2, y + h / 2 * k1); k3 = f(t + h / 2, y + h / 2 * k2); k4 = f(t + h, y + h * k3)
        return y + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    t, y, h = 0.0, math.log(1013.0), 0.25
    while y > math.log(p_x):
        yn = rk4(f_rough, t, y, h)
        if yn <= math.log(p_x):
            h2 = h * (y - math.log(p_x)) / (y - yn)
            t, y = t + h2, math.log(p_x)
            break
        t, y = t + h, yn
    h = 0.5
    while True:
        yn = rk4(f_high, t, y, h)
        if yn <= math.log(ptarget):
            t += h * (y - math.log(ptarget)) / (y - yn)
            break
        t, y = t + h, yn
        h = min(h * 1.002, 1.0)
    with open(out, "w") as fh:
        json.dump({"pumpdown_min": round(t / 60, 4)}, fh)


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
