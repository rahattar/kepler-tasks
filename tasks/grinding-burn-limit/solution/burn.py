"""Reference program: python3 burn.py JOB_DIR OUT_JSON

Writes the MS-GB burn-limited depth of cut of a plunge surface grinding job (max_depth_um):
- reads the job sheet: the wheel, the part's material and lot, the contact width (the ground width, or the two lands of
  a face with a relief groove), the programmed work speed, the coolant and its temperature, and the dressing interval
  (in mm3/mm, or in parts times the stock times the face length);
- reads the machine log: the work speed is the programmed one, or the table's speed limit when the log sets a lower
  one; the coolant temperature is the job sheet's, or the temperature the log gives while the chiller is out of
  service; the wheel diameter is the one after the last dressing; the power records used are those since the last
  wheel or coolant change (the operation's wheel specification and coolant);
- the burn limit is the highest temperature at which the part's lot was tempered (its certificate) plus 200 K;
- the net power of each grind pass is its spindle power less the idle power of the same session (the mean of that
  day's air passes); p0, p1 and u are fitted by least squares on P = b p0 + b V p1 + u b ae vw;
- the depth is the largest at which coolant temperature plus 1.13 Rw q sqrt(lc / vw) / beta stays at the burn limit,
  with the wheel at the end of its dressing interval (MS-GB clauses 1 to 4), Rw and beta from the grinding data.
"""
import csv, json, math, os, re, sys
import numpy as np
from scipy.optimize import brentq

DATA = "/app/data/docs/grinding_data.md"


def tables():
    rw, props = {}, {}
    for ln in open(DATA):
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) == 3 and re.fullmatch(r"[\d.]+", c[2]) and not c[0].startswith("-"):
            rw[(c[0], c[1])] = float(c[2])
        if len(c) == 4 and all(re.fullmatch(r"[\d.]+", x) for x in c[1:]):
            props[c[0]] = tuple(float(x) for x in c[1:])
    return rw, props


def assess(d, skip=()):
    s = open(os.path.join(d, "job_sheet.md")).read()
    wheel = re.search(r"Wheel: (\S+),", s).group(1)
    material, lot = re.search(r"Part: (\S+), lot ([^;]+);", s).groups()
    m = re.search(r"two lands of (\d+) mm", s)
    b = 2 * float(m.group(1)) if m else float(re.search(r"ground width (\d+) mm", s).group(1))
    v = float(re.search(r"work speed (\d+) m/min", s).group(1)) * 1000 / 60
    m = re.search(r"(5 percent emulsion|straight grinding oil) at (\d+) C", s)
    coolant_now = "emulsion" if "emulsion" in m.group(1) else "oil"; T0 = float(m.group(2))
    m = re.search(r"dressing interval (\d+) mm3/mm", s)
    if m:
        interval = float(m.group(1))
    else:
        n, stock, length = re.search(r"dressing every (\d+) parts \(stock ([\d.]+) mm over a (\d+) mm long face\)", s).groups()
        interval = float(n) * (1 if "parts" in skip else float(stock) * float(length))
    ht = open(os.path.join(d, "heat_treatment.md")).read()
    line = re.search(r"^- Lot %s .*$" % re.escape(lot), ht, re.M).group(0) if "lot" not in skip else ht.split("\n- ")[1]
    temps = [float(x) for x in re.findall(r"(\d+) C", line)]
    Tt = temps[0] if "retemper" in skip else max(temps)
    log = list(csv.DictReader(open(os.path.join(d, "machine_log.csv"))))
    for r in sorted(log, key=lambda r: r["date"]):
        m = re.search(r"table speed limited to (\d+) m/min", r["description"])
        if m and "speed" not in skip:
            v = min(v, float(m.group(1)) * 1000 / 60)
        m = re.search(r"chiller out of service.*coolant running at (\d+) C", r["description"])
        if m and "chiller" not in skip:
            T0 = float(m.group(1))
    coolant = "emulsion"
    start = "0"
    for r in sorted(log, key=lambda r: r["date"]):
        m = re.search(r"Coolant changed from .* to (5 percent emulsion|straight grinding oil)", r["description"])
        if m:
            coolant = "emulsion" if "emulsion" in m.group(1) else "oil"; start = max(start, r["date"])
        if re.search(r"new wheel (\S+) .*fitted", r["description"]):
            start = max(start, r["date"])
    dres = [float(x) for r in sorted(log, key=lambda r: r["date"]) for x in re.findall(r"Wheel dressed; diameter ([\d.]+) mm", r["description"])]
    ds = dres[-1] if dres else 400.0
    rows = list(csv.DictReader(open(os.path.join(d, "power_log.csv"))))
    if "period" in skip:
        start = "0"
    idle = {}
    for r in rows:
        if r["pass"] == "air":
            idle.setdefault(r["date"], []).append(float(r["spindle_power_w"]))
    gidle = np.mean([x for v_ in idle.values() for x in v_])
    X, y = [], []
    for r in rows:
        if r["pass"] != "grind" or r["date"] < start:
            continue
        bb, a, vv, V, P = (float(r[k]) for k in ("width_mm", "depth_um", "work_speed_mm_s", "volume_since_dressing_mm3_mm", "spindle_power_w"))
        Pn = P - (gidle if "idle" in skip else np.mean(idle[r["date"]]))
        X.append([bb, bb * V, bb * a / 1000 * vv]); y.append(Pn)
    (p0, p1, u), *_ = np.linalg.lstsq(np.array(X), np.array(y), rcond=None)
    rw_tab, props = tables()
    Rw = rw_tab[(wheel, coolant_now)]
    k, rho, c = props[material]
    beta = math.sqrt(k * rho * c)
    Vx = interval if "interval" not in skip else np.mean([r[1] / r[0] for r in X])
    dT = Tt + 200 - T0

    def theta(a_um):
        a = a_um / 1000
        lc = math.sqrt(a * ds)
        P = b * (p0 + p1 * Vx) + u * b * a * v
        q = P / (b * lc) * 1e6
        return 1.13 * Rw * q * math.sqrt((lc / 1000) / (v / 1000)) / beta
    grid = np.geomspace(0.1, 1000, 3000)
    vals = np.array([theta(a) - dT for a in grid])
    i = np.where(vals <= 0)[0][-1]
    a_max = brentq(lambda a: theta(a) - dT, grid[i], grid[i + 1], xtol=1e-10)
    return {"max_depth_um": round(a_max, 3)}


def main(pkg, out):
    with open(out, "w") as f:
        json.dump(assess(pkg), f)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
