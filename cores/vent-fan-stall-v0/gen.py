"""gen.py: builds the districts of the bare core: two examples with results, one pending without, six hidden.

    python3 gen.py [site ...]

A district is written as a package first; the truth is then computed from the package as written (truth.py),
so what is graded is the physics of the shipped figures and nothing else.
"""
import csv, json, os, sys, datetime as dt
import numpy as np
from vnet import Net
import truth as T

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "core", "environment", "data")
HIDDEN = os.path.join(HERE, "hidden")

# ---- fan catalogue: characteristic shapes (flow fraction of free delivery, pressure fraction of peak) ----
PHI = [0, .06, .12, .18, .24, .30, .36, .40, .44, .48, .52, .56, .60, .65, .70, .75, .80, .85, .90, .95, 1.0]
SHAPES = {
    "VA-2500": [1.2, 1.138, 1.062, .98, .894, .805, .713, .65, .726, .825, .916, .978, 1.0, .98, .93, .85, .73, .58, .40, .21, 0.0],
    "VA-2800": [1.25, 1.174, 1.082, .983, .878, .769, .656, .58, .671, .79, .899, .973, 1.0, .98, .93, .85, .73, .58, .40, .21, 0.0],
    "VA-3150": [1.28, 1.19, 1.08, .962, .838, .709, .60, .668, .762, .855, .931, .982, 1.0, .985, .94, .86, .75, .60, .42, .22, 0.0],
}
BASE = {"VA-2500": (240.0, 2900.0), "VA-2800": (270.0, 3200.0), "VA-3150": (300.0, 3400.0)}

def fan_curve(model, blade, size):
    """Tabulated characteristic of a model at a blade setting (1..5); size scales the flow (the fan's diameter step)."""
    q0, p0 = BASE[model]
    qm = q0 * size * (0.80 + 0.05 * blade); pp = p0 * (0.84 + 0.04 * blade)
    return [round(f * qm, 1) for f in PHI], [float(round(s * pp)) for s in SHAPES[model]]

def reg_table(r10):
    return {s: float("%.4g" % (r10 * 1.7 ** (10 - s))) for s in range(0, 11)}

SITES = {
    # name: role, seed, panels, crosscuts, fan model, blades (A, B), regime
    "north_field":  dict(role="example", seed=11, panels=9, cross=56, model="VA-2500", blades=(4, 4), regime="clear"),
    "east_decline": dict(role="example", seed=12, panels=10, cross=60, model="VA-2800", blades=(4, 3), regime="clear"),
    "west_reef":    dict(role="pending", seed=13, panels=10, cross=56, model="VA-2500", blades=(4, 4), regime="band"),
    "deep_south":   dict(role="hidden", seed=21, panels=10, cross=60, model="VA-2800", blades=(4, 4), regime="band"),
    "old_shaft":    dict(role="hidden", seed=22, panels=9, cross=60, model="VA-2500", blades=(5, 4), regime="band"),
    "far_east":     dict(role="hidden", seed=23, panels=10, cross=58, model="VA-3150", blades=(3, 3), regime="band"),
    "lower_levels": dict(role="hidden", seed=24, panels=10, cross=60, model="VA-3150", blades=(4, 4), regime="band"),
    "river_block":  dict(role="hidden", seed=25, panels=9, cross=56, model="VA-2800", blades=(5, 5), regime="band"),
    "new_incline":  dict(role="hidden", seed=26, panels=10, cross=60, model="VA-2500", blades=(4, 4), regime="clear"),
}

def sig(x, n=4):
    return float("%.*g" % (n, x))

def build(name, spec, size=1.0, sd_r=0.018):
    """The district as built: nodes, branches, items, fans. No log yet."""
    rng = np.random.default_rng(spec["seed"])
    K, n = spec["panels"], spec["cross"]
    br = []      # dict(branch, frm, to, kind, R, item)
    regs, doors, fans, curves = {}, {}, {}, {}
    def add(b, f, t, kind, R=None, item=""):
        br.append(dict(branch=b, frm=f, to=t, kind=kind, R=R, item=item))
    add("DS", "ATM", "IM0", "airway", sig(rng.uniform(0.0035, 0.0045)))
    for k in range(1, K + 1):
        for e in "AB":
            ri = sig(rng.uniform(0.004, 0.008)); rr = sig(rng.uniform(0.004, 0.008))
            if k == 1 and e == "B":
                # a bulkhead door stands in entry B of the first intake segment and of the first return segment
                doors["SD-1"] = (sig(rng.uniform(6, 10)), sig(sd_r)); add("IM-1-B", "IM0", "IM1", "door", None, "SD-1")
                doors["SD-2"] = (sig(rng.uniform(6, 10)), sig(sd_r)); add("RM-1-B", "RM1", "RM0", "door", None, "SD-2")
            else:
                if k == 1: ri, rr = sig(sd_r), sig(sd_r)
                add("IM-%d-%s" % (k, e), "IM%d" % (k - 1), "IM%d" % k, "airway", ri)
                add("RM-%d-%s" % (k, e), "RM%d" % k, "RM%d" % (k - 1), "airway", rr)
    doors["AL-1"] = (sig(rng.uniform(30, 50)), sig(rng.uniform(0.015, 0.025))); add("AL", "IM0", "RM0", "door", None, "AL-1")
    for k in range(1, K + 1):
        a = lambda j: ("IM%d" % k) if j == 0 else "P%da%02d" % (k, j)
        b = lambda j: "P%db%02d" % (k, j)
        for j in range(1, n + 1):
            add("P%d-I-%02d" % (k, j), a(j - 1), a(j), "airway", sig(rng.uniform(0.004, 0.012)))
            if j >= 2: add("P%d-R-%02d" % (k, j), b(j), b(j - 1), "airway", sig(rng.uniform(0.004, 0.012)))
        reg = "REG-%d" % k; regs[reg] = reg_table(sig(rng.uniform(0.0015, 0.003)))
        add("P%d-R-01" % k, b(1), "P%dreg" % k, "airway", sig(rng.uniform(0.004, 0.012)))
        add("P%d-REG" % k, "P%dreg" % k, "RM%d" % k, "regulator", None, reg)
        for j in range(1, n):
            if rng.random() < 0.12:
                d = "D-%d-%02d" % (k, j); doors[d] = (sig(rng.uniform(300, 900)), sig(rng.uniform(0.8, 3.0)))
                add("P%d-X-%02d" % (k, j), a(j), b(j), "door", None, d)
            else:
                add("P%d-X-%02d" % (k, j), a(j), b(j), "airway", sig(rng.uniform(300, 3000)))
        add("P%d-F" % k, a(n), b(n), "airway", sig(rng.uniform(0.25, 0.6)))
    add("US", "RM0", "FH", "airway", sig(rng.uniform(0.004, 0.0055)))
    leg = sig(rng.uniform(0.0035, 0.0045))
    for i, (f, bl, lg) in enumerate(zip("AB", spec["blades"], (leg, sig(leg * rng.uniform(1.25, 1.4))))):
        fid = "MF-%s" % f; fans[fid] = dict(branch="FAN-%s" % f, model=spec["model"], blade=bl)
        add("FAN-%s" % f, "FH", "ATM", "fan", lg, fid)
        curves[(spec["model"], bl)] = fan_curve(spec["model"], bl, size)
    # the catalogue sheet of the model: every blade setting, whether fitted or not
    for bl in range(1, 6): curves.setdefault((spec["model"], bl), fan_curve(spec["model"], bl, size))
    return dict(name=name, branches=br, regs=regs, doors=doors, fans=fans, curves=curves, log=[], points=[])

def working(d, rng):
    """Working settings: regulators 6..9, panel doors closed, bulkhead doors open, airlock closed."""
    s = {r: int(rng.integers(6, 10)) for r in d["regs"]}
    for x in d["doors"]: s[x] = "open" if x.startswith("SD") else "closed"
    return s

def thresholds(d, settings):
    """Scale every resistance of the district up and then down: where do the fans change limb?"""
    net, Rof, fanb = T.network(d)
    R0 = Rof(settings)
    y, it, ok = net.start(R0 * 0.25)
    ks = np.concatenate([np.geomspace(0.25, 4.0, 220), np.geomspace(4.0, 0.25, 220)])
    last = net.limbs(net.Z @ y); out = []
    for k in ks:
        y, it, ok = net.settle(y, R0 * k)
        lb = net.limbs(net.Z @ y)
        if lb != last: out.append((float(k), last, lb)); last = lb
    return out

def stamp(t):
    return t.strftime("%Y-%m-%d %H:%M")

def history(d, spec, rng, days=21):
    """The log and the survey points. Excursions lie between survey rounds and are never surveyed."""
    t0 = dt.datetime(2026, 3, 2, 5, 0)
    s = working(d, rng)
    log = [(t0, x, ("open" if x == "AL-1" else v)) for x, v in sorted(s.items())]   # the record opens with the airlock open
    cur = dict(s); cur["AL-1"] = "open"
    ev = [(t0 + dt.timedelta(minutes=40), "AL-1", "closed")]
    rounds = [t0 + dt.timedelta(days=dd, hours=h, minutes=30) for dd in range(days) for h in (2, 14)]   # 07:30, 19:30
    nslots = len(rounds) - 1
    # which slots carry which excursion
    plan = {}
    kinds = ["shut", "relief", "shut", "shut", "relief", "throttle", "relief", "shut", "relief", "shut", "throttle", "relief", "shut", "relief"]
    slots = sorted(rng.choice(np.arange(1, nslots), size=len(kinds), replace=False))
    for sl, kd in zip(slots, kinds): plan[int(sl)] = kd
    regs = sorted(d["regs"]); pdoors = sorted(x for x in d["doors"] if x.startswith("D-"))
    for sl in range(nslots):
        a = rounds[sl] + dt.timedelta(minutes=30); b = rounds[sl + 1] - dt.timedelta(minutes=30)
        span = (b - a).total_seconds() / 60.0
        times = []
        kd = plan.get(sl)
        quiet = rng.random() < 0.12
        nord = int(rng.integers(3, 9)) if quiet else int(rng.integers(24, 40))
        used = set()
        def slot_time(lo=0.0, hi=1.0):
            for _ in range(200):
                m = int(rng.uniform(lo, hi) * span / 5) * 5
                if all(abs(m - u) >= 10 for u in used): used.add(m); return a + dt.timedelta(minutes=m)
            raise RuntimeError("no room in slot")
        if kd is not None:
            start = int(rng.uniform(0.1, 0.5) * span / 5) * 5; dur = int(rng.uniform(45, 200) / 5) * 5
            used.update((start, start + dur))
            ta, tb = a + dt.timedelta(minutes=start), a + dt.timedelta(minutes=start + dur)
            if kd == "shut":
                x = "SD-1" if rng.random() < 0.5 else "SD-2"; ev += [(ta, x, "closed"), (tb, x, "open")]
            elif kd == "relief":
                ev += [(ta, "AL-1", "open"), (tb, "AL-1", "closed")]
            else:   # a panel throttled right down for a while
                x = regs[int(rng.integers(len(regs)))]; ev += [(ta, x, 1), (tb, x, "restore")]
        for _ in range(nord):
            t = slot_time()
            if rng.random() < 0.45:
                x = regs[int(rng.integers(len(regs)))]; ev.append((t, x, "step"))
            elif pdoors:
                x = pdoors[int(rng.integers(len(pdoors)))]; ev.append((t, x, "toggle"))
    ev.sort(key=lambda e: e[0])
    hold = {}
    for t, x, v in ev:
        if v == "step":
            v = int(np.clip(cur[x] + (1 if rng.random() < 0.5 else -1), 5, 9))
            if v == cur[x]: v = cur[x] + (1 if cur[x] <= 6 else -1)
            if x in hold: hold[x] = v; continue          # the regulator is throttled just now: the step applies on restore
        elif v == "toggle":
            v = "open" if cur[x] == "closed" else "closed"
        elif v == "restore":
            v = hold.pop(x)
        elif v == 1:
            hold[x] = cur[x]
        if v == cur[x]: continue
        cur[x] = v; log.append((t, x, v))
    d["log"] = [(stamp(t), x, v) for t, x, v in log]
    # survey stations: the same branches at every round
    st = ["DS", "US", "FAN-A", "FAN-B"] + [b["branch"] for b in d["branches"] if b["branch"].startswith(("IM-", "RM-"))]
    K, n = spec["panels"], spec["cross"]
    for k in range(1, K + 1):
        st += ["P%d-REG" % k, "P%d-F" % k, "P%d-I-01" % k, "P%d-I-%02d" % (k, n // 2), "P%d-R-%02d" % (k, max(2, n // 3))]
    pts = []; i = 0
    for t in rounds:
        for b in st:
            i += 1; pts.append(("S%05d" % i, stamp(t), b))
    d["points"] = pts
    return d

def write(d, folder):
    os.makedirs(folder, exist_ok=True)
    def w(name, header, rows):
        with open(os.path.join(folder, name), "w", newline="") as f:
            c = csv.writer(f, lineterminator="\n"); c.writerow(header); c.writerows(rows)
    json.dump({"district": d["name"]}, open(os.path.join(folder, "district.json"), "w"), indent=1)
    w("branches.csv", ["branch", "from_node", "to_node", "kind", "resistance_Ns2_m8", "item"],
      [[b["branch"], b["frm"], b["to"], b["kind"], "" if b["R"] is None else repr(b["R"]), b["item"]] for b in d["branches"]])
    w("regulators.csv", ["regulator", "setting", "resistance_Ns2_m8"],
      [[r, s, repr(v)] for r in sorted(d["regs"]) for s, v in sorted(d["regs"][r].items())])
    w("doors.csv", ["door", "resistance_closed_Ns2_m8", "resistance_open_Ns2_m8"],
      [[x, repr(v[0]), repr(v[1])] for x, v in sorted(d["doors"].items())])
    w("fans.csv", ["fan", "branch", "model", "blade_setting"],
      [[f, v["branch"], v["model"], v["blade"]] for f, v in sorted(d["fans"].items())])
    w("fan_curves.csv", ["model", "blade_setting", "flow_m3_s", "pressure_Pa"],
      [[m, bl, repr(q), repr(p)] for (m, bl), (qs, ps) in sorted(d["curves"].items()) for q, p in zip(qs, ps)])
    w("log.csv", ["time", "item", "setting"], d["log"])
    w("points.csv", ["point", "time", "branch"], d["points"])

def make(name):
    spec = SITES[name]
    rng = np.random.default_rng(spec["seed"] + 1000)
    # size the fans for the mine: where on the stall band does the working district sit?
    d = build(name, spec)
    s0 = working(d, np.random.default_rng(spec["seed"] + 1000))
    th = thresholds(d, s0)
    up = [k for k, a, b in th if a == "RR"][0]; dn = [k for k, a, b in th if b == "RR"][-1]
    kstar = (up * dn) ** 0.5 if spec["regime"] == "band" else 0.70 * dn
    size = kstar ** 0.5          # scaling every resistance by k is scaling the fans' flow by sqrt(k)
    for attempt in range(40):
        d = build(name, spec, size=size)
        rng = np.random.default_rng(spec["seed"] + 1000 + 77 * attempt)
        history(d, spec, rng)
        folder = os.path.join(DATA, {"example": "examples", "pending": "pending"}[spec["role"]], name) if spec["role"] != "hidden" \
            else os.path.join(HIDDEN, name)
        if os.path.isdir(folder):
            for f in os.listdir(folder): os.remove(os.path.join(folder, f))
        write(d, folder)
        rep = T.audit(folder, spec["regime"])
        if rep["ok"]:
            res = rep["result"]
            out = os.path.join(folder, "expected.csv" if spec["role"] == "example" else "truth.csv")
            if spec["role"] == "pending": out = os.path.join(HIDDEN, "_pending_" + name + "_truth.csv")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "w", newline="") as f:
                c = csv.writer(f, lineterminator="\n"); c.writerow(["point", "flow_m3_s"])
                for p, q in res: c.writerow([p, "%.4f" % q])
            print("%-13s %-7s attempt %d  size %.3f  band %.3f..%.3f  %s" % (name, spec["role"], attempt, size, dn, up, rep["summary"]), flush=True)
            json.dump(rep["facts"], open(os.path.join(HIDDEN, "_facts_" + name + ".json"), "w"), indent=1)
            return rep
        print("%-13s attempt %d refused: %s" % (name, attempt, rep["why"]), flush=True)
    raise SystemExit("no acceptable history for " + name)

if __name__ == "__main__":
    os.makedirs(HIDDEN, exist_ok=True)
    for nm in (sys.argv[1:] or list(SITES)): make(nm)
