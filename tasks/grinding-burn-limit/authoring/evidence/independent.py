"""A second MS-GB program, written separately from solution/burn.py and sharing no code with it:

    python3 independent.py JOB_DIR OUT_JSON

- Idle power: the median of each session's air passes (the reference takes the mean).
- Power model: fitted per unit width, P / b = p0 + p1 V + u ae vw, by ordinary least squares (the reference fits P
  itself, which weights wide passes more).
- Depth: stepping down from 1 mm in factors of 0.98 until the surface temperature is at or below the burn limit, then
  bisection (the reference brackets on a logarithmic grid and uses Brent's method).
- Records: the job sheet's fields read line by line, the machine log and the certificates read independently.
"""
import csv, json, math, os, re, statistics, sys

DATA_FILE = "/app/data/docs/grinding_data.md"


def item(text, key):
    for ln in text.splitlines():
        if ln.startswith("- %s:" % key):
            return ln.split(":", 1)[1].strip().rstrip(".")
    raise KeyError(key)


def read_job(d):
    t = open(os.path.join(d, "job_sheet.md")).read()
    wheel = item(t, "Wheel").split(",")[0].strip()
    part = item(t, "Part")
    material = part.split(",")[0].strip()
    lot = re.search(r"lot ([A-Za-z0-9]+)", part).group(1)
    lands = re.search(r"two lands of (\d+(?:\.\d+)?) mm", part)
    width = 2 * float(lands.group(1)) if lands else float(re.search(r"ground width (\d+(?:\.\d+)?) mm", part).group(1))
    op = item(t, "Operation")
    speed = float(re.search(r"work speed (\d+(?:\.\d+)?) m/min", op).group(1)) / 60.0 * 1000.0
    cool = re.search(r"(emulsion|grinding oil) at (\d+(?:\.\d+)?) C", op)
    coolant = "emulsion" if cool.group(1) == "emulsion" else "oil"
    temp = float(cool.group(2))
    per = re.search(r"dressing every (\d+) parts \(stock (\d+(?:\.\d+)?) mm over a (\d+(?:\.\d+)?) mm long face\)", op)
    interval = (float(per.group(1)) * float(per.group(2)) * float(per.group(3)) if per else
                float(re.search(r"dressing interval (\d+(?:\.\d+)?) mm3/mm", op).group(1)))
    return dict(wheel=wheel, material=material, lot=lot, b=width, vw=speed, coolant=coolant, T0=temp, interval=interval)


def burn_limit(d, lot):
    for ln in open(os.path.join(d, "heat_treatment.md")):
        if ln.startswith("- Lot %s " % lot) or ln.startswith("- Lot %s(" % lot):
            return max(float(x) for x in re.findall(r"at (\d+(?:\.\d+)?) C", ln)) + 200.0
    raise KeyError(lot)


def machine_state(d, job):
    with open(os.path.join(d, "machine_log.csv")) as fh:
        log = sorted(csv.DictReader(fh), key=lambda r: r["date"])
    since, diameter = "", 400.0
    for r in log:
        txt = r["description"]
        if "new wheel" in txt or txt.startswith("Coolant changed"):
            since = r["date"]
        m = re.search(r"diameter (\d+(?:\.\d+)?) mm", txt)
        if m:
            diameter = float(m.group(1))
        m = re.search(r"table speed limited to (\d+(?:\.\d+)?) m/min", txt)
        if m:
            job["vw"] = min(job["vw"], float(m.group(1)) / 60.0 * 1000.0)
        m = re.search(r"chiller out of service.*running at (\d+(?:\.\d+)?) C", txt)
        if m:
            job["T0"] = float(m.group(1))
    return since, diameter


def fit_power(d, since):
    with open(os.path.join(d, "power_log.csv")) as fh:
        rows = list(csv.DictReader(fh))
    idle = {}
    for r in rows:
        if r["pass"] == "air":
            idle.setdefault(r["date"], []).append(float(r["spindle_power_w"]))
    idle = {k: statistics.median(v) for k, v in idle.items()}
    A, y = [], []
    for r in rows:
        if r["pass"] != "grind" or r["date"] < since:
            continue
        b = float(r["width_mm"])
        per_width = (float(r["spindle_power_w"]) - idle[r["date"]]) / b
        A.append([1.0, float(r["volume_since_dressing_mm3_mm"]), float(r["depth_um"]) / 1000.0 * float(r["work_speed_mm_s"])])
        y.append(per_width)
    # normal equations, 3 x 3
    n = 3
    M = [[sum(a[i] * a[j] for a in A) for j in range(n)] for i in range(n)]
    v = [sum(a[i] * yy for a, yy in zip(A, y)) for i in range(n)]
    for i in range(n):                                   # Gauss-Jordan
        p = max(range(i, n), key=lambda r: abs(M[r][i]))
        M[i], M[p] = M[p], M[i]; v[i], v[p] = v[p], v[i]
        for r in range(n):
            if r != i:
                f = M[r][i] / M[i][i]
                M[r] = [a - f * c for a, c in zip(M[r], M[i])]; v[r] -= f * v[i]
    return [v[i] / M[i][i] for i in range(n)]


def tables(wheel, coolant, material):
    rw = beta = None
    for ln in open(DATA_FILE):
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) == 3 and c[0] == wheel and c[1] == coolant:
            rw = float(c[2])
        if len(c) == 4 and c[0] == material:
            k, rho, cp = (float(x) for x in c[1:])
            beta = math.sqrt(k * rho * cp)
    return rw, beta


def run(d, out):
    job = read_job(d)
    since, ds = machine_state(d, job)
    p0, p1, u = fit_power(d, since)
    Rw, beta = tables(job["wheel"], job["coolant"], job["material"])
    allowed = burn_limit(d, job["lot"]) - job["T0"]
    sliding = p0 + p1 * job["interval"]

    def rise(a_um):
        a = a_um / 1000.0
        lc = math.sqrt(a * ds)                                    # mm
        flux = (sliding + u * a * job["vw"]) / lc * 1e6           # W/m2 (power per width over contact length)
        return 1.13 * Rw * flux * math.sqrt(lc / job["vw"]) / beta

    hi = 1000.0
    lo = hi
    while rise(lo) > allowed:
        hi, lo = lo, lo * 0.98
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if rise(mid) > allowed:
            hi = mid
        else:
            lo = mid
    with open(out, "w") as fh:
        json.dump({"max_depth_um": round(lo, 4)}, fh)


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
