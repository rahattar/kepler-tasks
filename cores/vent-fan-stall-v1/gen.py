"""gen.py: the districts of bare core v1 (a tenth of v0's size): two examples with results, one pending, four hidden.

    python3 gen.py [district ...]

What a package has on record: pressure-quantity surveys of its airways (three campaigns), the resistance each
stopping was built to, a work log, the fans, and the log of regulator and door settings. What is sealed: the
resistance of everything as it is, and the survey crew's book of what a survey would read now.

The shift (SITES): `breach` - one stopping that the register books at its built resistance passes ten or so
m3/s, and every campaign's quantities at its two ends miss balance by that much; `close` - the last bulkhead
closure of the record takes the district to the stall point within the accuracy of the surveys, so the
resistances on record put it on one side and the district as it is on the other. The crew's allowance is the
number of airways worked on since their last survey, plus one for each of the two.
"""
import csv, json, os, sys, zlib, datetime as dt
import numpy as np
import truth as T

HERE = os.path.dirname(os.path.abspath(__file__))
FULL = os.environ.get("VF_SCALE") == "full"        # the districts at ten times the size, for the bundle
OUT = os.path.join(HERE, "full") if FULL else HERE
DATA = os.path.join(OUT, "core", "environment", "data")
RIG = os.path.join(OUT, "core", "environment", "rig", "sealed")
HIDDEN = os.path.join(OUT, "hidden")
HLAB = os.path.join(OUT, "hidden_lab", "sealed")

PHI = [0, .06, .12, .18, .24, .30, .36, .40, .44, .48, .52, .56, .60, .65, .70, .75, .80, .85, .90, .95, 1.0]
SHAPES = {
    "VA-2500": [1.2, 1.138, 1.062, .98, .894, .805, .713, .65, .726, .825, .916, .978, 1.0, .98, .93, .85, .73, .58, .40, .21, 0.0],
    "VA-2800": [1.25, 1.174, 1.082, .983, .878, .769, .656, .58, .671, .79, .899, .973, 1.0, .98, .93, .85, .73, .58, .40, .21, 0.0],
    "VA-3150": [1.28, 1.19, 1.08, .962, .838, .709, .60, .668, .762, .855, .931, .982, 1.0, .985, .94, .86, .75, .60, .42, .22, 0.0],
}
BASE = {"VA-2500": (240.0, 2900.0), "VA-2800": (270.0, 3200.0), "VA-3150": (300.0, 3400.0)}
ACC = 0.003          # a survey reads the pressure difference and the quantity each within 0.3 per cent
CAMPAIGNS = [dt.date(2025, 2, 10), dt.date(2025, 8, 18), dt.date(2026, 1, 12)]

SITES = {
    "north_field":  dict(role="example", seed=31, panels=4, cross=8, model="VA-2500", blades=(4, 4), breach=False, close=None),
    "east_decline": dict(role="example", seed=32, panels=5, cross=8, model="VA-2800", blades=(4, 3), breach=False, close=None),
    "west_reef":    dict(role="pending", seed=33, panels=4, cross=9, model="VA-2500", blades=(4, 4), breach=True, close="any"),
    "deep_south":   dict(role="hidden", seed=41, panels=5, cross=8, model="VA-2800", blades=(4, 4), breach=True, close="any"),
    "old_shaft":    dict(role="hidden", seed=42, panels=4, cross=9, model="VA-2500", blades=(5, 4), breach=True, close=None),
    "far_east":     dict(role="hidden", seed=43, panels=4, cross=8, model="VA-3150", blades=(3, 3), breach=False, close="any"),
    "new_incline":  dict(role="hidden", seed=44, panels=5, cross=9, model="VA-2500", blades=(4, 4), breach=False, close=None),
}
if FULL:
    # close: what the district as it is does at the last closure - "stalls" (the records say it holds) or "holds"
    SITES = {
        "north_field":  dict(role="example", seed=51, panels=9, cross=56, model="VA-2500", blades=(4, 4), breach=False, close=None),
        "east_decline": dict(role="example", seed=52, panels=10, cross=60, model="VA-2800", blades=(4, 3), breach=False, close=None),
        "west_reef":    dict(role="pending", seed=53, panels=10, cross=56, model="VA-2500", blades=(4, 4), breach=True, close="stalls"),
        "deep_south":   dict(role="hidden", seed=61, panels=10, cross=60, model="VA-2800", blades=(4, 4), breach=True, close="holds"),
        "old_shaft":    dict(role="hidden", seed=62, panels=9, cross=60, model="VA-2500", blades=(5, 4), breach=True, close=None),
        "far_east":     dict(role="hidden", seed=63, panels=10, cross=58, model="VA-3150", blades=(3, 3), breach=False, close="stalls"),
        "lower_levels": dict(role="hidden", seed=64, panels=10, cross=60, model="VA-3150", blades=(4, 4), breach=True, close="stalls"),
        "river_block":  dict(role="hidden", seed=65, panels=9, cross=56, model="VA-2800", blades=(5, 5), breach=False, close="holds"),
        "new_incline":  dict(role="hidden", seed=66, panels=10, cross=60, model="VA-2500", blades=(4, 4), breach=False, close=None),
    }
DAYS = 21 if FULL else 7

def sig(x, n=4): return float("%.*g" % (n, x))
def unit(*key): return (zlib.crc32("|".join(map(str, key)).encode()) % 100000) / 100000.0      # a fixed draw in [0, 1)
SALT = [0]
def err(*key): return 1.0 + ACC * (2.0 * unit(SALT[0], *key) - 1.0)

def fan_curve(model, blade, size):
    q0, p0 = BASE[model]
    qm = q0 * size * (0.80 + 0.05 * blade); pp = p0 * (0.84 + 0.04 * blade)
    return [round(f * qm, 1) for f in PHI], [float(round(s * pp)) for s in SHAPES[model]]

def reg_table(r10): return {s: float("%.4g" % (r10 * 1.7 ** (10 - s))) for s in range(0, 11)}

def build(name, spec, size=1.0, sd2_r=0.006, sd1_r=0.018):
    rng = np.random.default_rng(spec["seed"])
    K, n = spec["panels"], spec["cross"]
    br = []; regs, doors, fans, curves = {}, {}, {}, {}
    Rnow = {}                          # the resistance of every airway, stopping and fan duct as it is
    def add(b, f, t, kind, R=None, item=""):
        br.append(dict(branch=b, frm=f, to=t, kind=kind, R=R, item=item))
        if kind == "airway": Rnow[b] = R; br[-1]["R"] = None
        if kind in ("stopping", "fan"): Rnow[b] = R
    add("DS", "ATM", "IM0", "airway", sig(rng.uniform(0.0035, 0.0045)))
    for k in range(1, K + 1):
        for e in "AB":
            ri = sig(rng.uniform(0.004, 0.008)); rr = sig(rng.uniform(0.004, 0.008))
            if k == 1 and e == "B":
                doors["SD-1"] = (sig(rng.uniform(6, 10)), sig(sd1_r)); add("IM-1-B", "IM0", "IM1", "door", None, "SD-1")
                doors["SD-2"] = (sig(rng.uniform(6, 10)), sig(sd2_r)); add("RM-1-B", "RM1", "RM0", "door", None, "SD-2")
            else:
                if k == 1: ri, rr = sig(sd1_r), float("%.7g" % sd2_r)
                add("IM-%d-%s" % (k, e), "IM%d" % (k - 1), "IM%d" % k, "airway", ri)
                add("RM-%d-%s" % (k, e), "RM%d" % k, "RM%d" % (k - 1), "airway", rr)
    doors["AL-1"] = (sig(rng.uniform(30, 50)), sig(rng.uniform(0.015, 0.025))); add("AL", "IM0", "RM0", "door", None, "AL-1")
    stops = []
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
            if rng.random() < 0.15:
                d = "D-%d-%02d" % (k, j); doors[d] = (sig(rng.uniform(300, 900)), sig(rng.uniform(0.8, 3.0)))
                add("P%d-X-%02d" % (k, j), a(j), b(j), "door", None, d)
            else:
                add("P%d-X-%02d" % (k, j), a(j), b(j), "stopping", sig(rng.uniform(1200, 4000)))
                stops.append((k, j, "P%d-X-%02d" % (k, j)))
        add("P%d-F" % k, a(n), b(n), "airway", sig(rng.uniform(0.25, 0.6)))
    add("US", "RM0", "FH", "airway", sig(rng.uniform(0.004, 0.0055)))
    leg = sig(rng.uniform(0.0035, 0.0045))
    for f, bl, lg in zip("AB", spec["blades"], (leg, sig(leg * rng.uniform(1.25, 1.4)))):
        fans["MF-%s" % f] = dict(branch="FAN-%s" % f, model=spec["model"], blade=bl)
        add("FAN-%s" % f, "FH", "ATM", "fan", lg, "MF-%s" % f)
    for bl in range(1, 6): curves[(spec["model"], bl)] = fan_curve(spec["model"], bl, size)
    # work on the airways: three or four gate roads altered since the last campaign, two between campaigns
    gates = [x["branch"] for x in br if x["kind"] == "airway" and x["branch"][0] == "P" and "-F" not in x["branch"]]
    ndec, nins = (4, 10) if FULL else (2, 4)
    pick = list(rng.choice(len(gates), size=int(rng.integers(6, 10) if FULL else rng.integers(3, 5)) + ndec + nins, replace=False))
    Rold = {}; work = []
    nalt = len(pick) - ndec - nins
    for i, gi in enumerate(pick):
        g = gates[gi]
        if i < nalt + ndec:
            Rold[g] = Rnow[g]; Rnow[g] = sig(Rnow[g] * rng.uniform(0.5, 0.75))
            kind = "RESUPPORTED" if rng.random() < 0.5 else "ENLARGED"
            when = dt.date(2026, 2, 2) + dt.timedelta(days=int(rng.integers(0, 20))) if i < nalt else dt.date(2025, 10, 6) + dt.timedelta(days=int(rng.integers(0, 60)))
        else:
            kind = "INSPECTED"; when = dt.date(2026, 1, 20) + dt.timedelta(days=int(rng.integers(0, 35)))
        work.append((when, g, kind))
    breach = None
    if spec["breach"]:
        cand = [s for s in stops if max(2, n // 8) <= s[1] <= max(2, n // 3 if FULL else n // 2)]
        k, j, breach = cand[int(rng.integers(len(cand)))]
        Rnow[breach] = sig(rng.uniform(4.0, 9.0))
    return dict(name=name, branches=br, regs=regs, doors=doors, fans=fans, curves=curves, log=[], points=[],
                Rnow=Rnow, Rold=Rold, work=sorted(work), breach=breach, altered=sorted(g for w, g, kd in work if kd != "INSPECTED" and w > CAMPAIGNS[-1]))

def working(d, rng):
    s = {r: int(rng.integers(6, 10)) for r in d["regs"]}
    for x in d["doors"]: s[x] = "open" if x.startswith("SD") else "closed"
    return s

def thresholds(d, settings):
    net, Rof, fanb, nodes = T.network(d, d["Rnow"])
    R0 = Rof(settings)
    y, it, ok = net.start(R0 * 0.25)
    ks = np.concatenate([np.geomspace(0.25, 4.0, 160), np.geomspace(4.0, 0.25, 160)])
    last = net.limbs(net.Z @ y); out = []
    for k in ks:
        y, it, ok = net.settle(y, R0 * k)
        lb = net.limbs(net.Z @ y)
        if lb != last: out.append((float(k), last, lb)); last = lb
    return out

def stamp(t): return t.strftime("%Y-%m-%d %H:%M")

def history(d, spec, rng, days=DAYS):
    t0 = dt.datetime(2026, 3, 2, 5, 0)
    s = working(d, rng)
    log = [(t0, x, ("open" if x == "AL-1" else v)) for x, v in sorted(s.items())]
    cur = dict(s); cur["AL-1"] = "open"
    ev = [(t0 + dt.timedelta(minutes=40), "AL-1", "closed")]
    rounds = [t0 + dt.timedelta(days=dd, hours=h, minutes=30) for dd in range(days) for h in (2, 14)]
    nslots = len(rounds) - 1
    long = ["shut", "relief", "shut", "shut", "relief", "throttle", "relief", "shut", "relief", "shut", "throttle", "relief"]
    if spec["close"]:
        kinds = long if FULL else ["shut", "relief", "shut", "throttle", "relief"]
        tail = 5 if FULL else 4
        slots = sorted(rng.choice(np.arange(1, nslots - tail), size=len(kinds), replace=False)) + [nslots - tail]; kinds = kinds + ["close"]
    else:
        kinds = long + ["shut", "relief"] if FULL else ["shut", "relief", "shut", "throttle", "relief", "shut"]
        slots = sorted(rng.choice(np.arange(1, nslots), size=len(kinds), replace=False))
    plan = {int(sl): kd for sl, kd in zip(slots, kinds)}
    regs = sorted(d["regs"]); pdoors = sorted(x for x in d["doors"] if x.startswith("D-"))
    close_at = None
    for sl in range(nslots):
        a = rounds[sl] + dt.timedelta(minutes=30); b = rounds[sl + 1] - dt.timedelta(minutes=30)
        span = (b - a).total_seconds() / 60.0
        kd = plan.get(sl); used = set()
        def slot_time():
            for _ in range(400):
                m = int(rng.uniform(0, 1) * span / 5) * 5
                if all(abs(m - u) >= 10 for u in used): used.add(m); return a + dt.timedelta(minutes=m)
            raise RuntimeError("no room in slot")
        if kd is not None:
            start = int(rng.uniform(0.1, 0.5) * span / 5) * 5; dur = int(rng.uniform(45, 200) / 5) * 5
            used.update((start, start + dur))
            ta, tb = a + dt.timedelta(minutes=start), a + dt.timedelta(minutes=start + dur)
            if kd == "shut": ev += [(ta, "SD-1", "closed"), (tb, "SD-1", "open")]
            elif kd == "close": ev += [(ta, "SD-2", "closed"), (tb, "SD-2", "open")]; close_at = stamp(ta)
            elif kd == "relief": ev += [(ta, "AL-1", "open"), (tb, "AL-1", "closed")]
            else:
                x = regs[int(rng.integers(len(regs)))]; ev += [(ta, x, 1), (tb, x, "restore")]
        for _ in range(int(rng.integers(3, 8)) if (not FULL or rng.random() < 0.12) else int(rng.integers(24, 40))):
            t = slot_time()
            if rng.random() < 0.6 or not pdoors:
                ev.append((t, regs[int(rng.integers(len(regs)))], "step"))
            else:
                ev.append((t, pdoors[int(rng.integers(len(pdoors)))], "toggle"))
    ev.sort(key=lambda e: e[0])
    hold = {}
    for t, x, v in ev:
        if v == "step":
            v = int(np.clip(cur[x] + (1 if rng.random() < 0.5 else -1), 5, 9))
            if v == cur[x]: v = cur[x] + (1 if cur[x] <= 6 else -1)
            if x in hold: hold[x] = v; continue
        elif v == "toggle": v = "open" if cur[x] == "closed" else "closed"
        elif v == "restore": v = hold.pop(x)
        elif v == 1: hold[x] = cur[x]
        if v == cur[x]: continue
        cur[x] = v; log.append((t, x, v))
    d["log"] = [(stamp(t), x, v) for t, x, v in log]; d["close_at"] = close_at
    st = ["DS", "US", "FAN-A", "FAN-B"] + [b["branch"] for b in d["branches"] if b["branch"].startswith(("IM-", "RM-"))]
    K, n = spec["panels"], spec["cross"]
    for k in range(1, K + 1):
        st += ["P%d-REG" % k, "P%d-F" % k, "P%d-I-01" % k, "P%d-I-%02d" % (k, n // 2 + 1), "P%d-R-%02d" % (k, max(2, n // 3))]
    pts = []; i = 0
    for t in rounds:
        for b in st:
            i += 1; pts.append(("S%05d" % i, stamp(t), b))
    d["points"] = pts
    return d

def campaigns(d, spec):
    """Three campaigns: the district solved as it stood (airways as they then were), every airway read with its errors."""
    rows = []
    for c, day in enumerate(CAMPAIGNS):
        Rfix = dict(d["Rnow"])
        for w, g, kd in d["work"]:
            if kd != "INSPECTED" and w > day: Rfix[g] = d["Rold"][g]
        net, Rof, fanb, nodes = T.network(d, Rfix)
        for trial in range(20):                                  # the district as it stood, both fans healthy
            s = working(d, np.random.default_rng(spec["seed"] * 100 + c + 1000 * trial))
            R = Rof(s); y, it, ok = net.start(R * 0.5)
            for k in range(1, 13): y, it, ok = net.settle(y, R * 0.5 ** (1 - k / 12))
            q = net.Z @ y
            if net.limbs(q) == "RR" and ok: break
        else: raise RuntimeError("campaign %d not in the healthy state" % c)
        for i, b in enumerate(d["branches"]):
            if b["kind"] != "airway": continue
            nm = b["branch"]
            grp = int(nm[1]) if nm[0] == "P" else 0                      # the mains on the first day, each panel on its own
            dp = Rfix[nm] * q[i] * abs(q[i]) * err("dp", d["name"], c, nm); qq = q[i] * err("q", d["name"], c, nm)
            rows.append(((day + dt.timedelta(days=grp)).isoformat(), nm, float("%.5g" % dp), float("%.5g" % qq)))
    return rows

def book_of(d, now, allowance):
    rd = {}
    for b in d["branches"]:
        h, q = now[b["branch"]]
        rd[b["branch"]] = [float("%.5g" % (h * err("dpnow", d["name"], b["branch"]))), float("%.5g" % (q * err("qnow", d["name"], b["branch"])))]
    return dict(allowance=allowance, readings=rd)

def on_record(d, surveys, book):
    """The resistances a program that does everything the records allow would hold."""
    R = {}
    latest = {}
    for day, nm, dp, q in surveys:
        if nm not in latest or day > latest[nm][0]: latest[nm] = (day, dp / (q * abs(q)))
    for b in d["branches"]:
        nm = b["branch"]
        if b["kind"] == "airway":
            if nm in d["altered"]: dp, q = book["readings"][nm]; R[nm] = dp / (q * abs(q))
            else: R[nm] = latest[nm][1]
        elif b["kind"] == "stopping":
            if nm == d["breach"]: dp, q = book["readings"][nm]; R[nm] = dp / (q * abs(q))
            else: R[nm] = b["R"]
        elif b["kind"] == "fan": R[nm] = b["R"]
    return R

def write(d, folder, surveys, allowance):
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder): os.remove(os.path.join(folder, f))
    def w(name, header, rows):
        with open(os.path.join(folder, name), "w", newline="") as f:
            c = csv.writer(f, lineterminator="\n"); c.writerow(header); c.writerows(rows)
    json.dump({"district": d["name"], "survey_allowance": allowance}, open(os.path.join(folder, "district.json"), "w"), indent=1)
    w("branches.csv", ["branch", "from_node", "to_node", "kind", "resistance_Ns2_m8", "item"],
      [[b["branch"], b["frm"], b["to"], b["kind"], "" if b["R"] is None else repr(b["R"]), b["item"]] for b in d["branches"]])
    w("regulators.csv", ["regulator", "setting", "resistance_Ns2_m8"], [[r, s, repr(v)] for r in sorted(d["regs"]) for s, v in sorted(d["regs"][r].items())])
    w("doors.csv", ["door", "resistance_closed_Ns2_m8", "resistance_open_Ns2_m8"], [[x, repr(v[0]), repr(v[1])] for x, v in sorted(d["doors"].items())])
    w("fans.csv", ["fan", "branch", "model", "blade_setting"], [[f, v["branch"], v["model"], v["blade"]] for f, v in sorted(d["fans"].items())])
    w("fan_curves.csv", ["model", "blade_setting", "flow_m3_s", "pressure_Pa"],
      [[m, bl, repr(q), repr(p)] for (m, bl), (qs, ps) in sorted(d["curves"].items()) for q, p in zip(qs, ps)])
    w("surveys.csv", ["date", "branch", "dp_Pa", "q_m3_s"], [[a, b, repr(c), repr(e)] for a, b, c, e in sorted(surveys)])
    w("work_log.csv", ["date", "branch", "work"], [[a.isoformat(), b, c] for a, b, c in d["work"]])
    w("log.csv", ["time", "item", "setting"], d["log"])
    w("points.csv", ["point", "time", "branch"], d["points"])

def rr_holds(d, Rfix, settings):
    """Does the state with both fans healthy exist at these settings? Approached from half the resistance."""
    net, Rof, fanb, nodes = T.network(d, Rfix)
    R = Rof(settings); y, it, ok = net.start(R * 0.5)
    for s in range(1, 13): y, it, ok = net.settle(y, R * 0.5 ** (1 - s / 12))
    return net.limbs(net.Z @ y) == "RR"

def settings_at(d, when):
    t0 = d["log"][0][0]; s = {}
    for t, x, v in d["log"]:
        if t <= when: s[x] = v
    return s

def size_for(name, spec, sd2_r, sd1_r):
    d = build(name, spec, sd2_r=sd2_r, sd1_r=sd1_r)
    th = thresholds(d, working(d, np.random.default_rng(spec["seed"] + 1000)))
    up = [k for k, a, b in th if a == "RR"][0]; dn = [k for k, a, b in th if b == "RR"][-1]
    return ((up * dn) ** 0.5) ** 0.5, dn, up        # the working district in the middle of the band

def edge(name, spec, size, which, other, settings, view):
    """The resistance of a main's first entry at which, with these settings, the healthy state just ceases."""
    lo, hi = 0.002, 0.2
    for _ in range(26):
        x = (lo * hi) ** 0.5
        dd = build(name, spec, size=size, **({"sd1_r": x, "sd2_r": other} if which == 1 else {"sd2_r": x, "sd1_r": other}))
        if rr_holds(dd, view(dd), settings): lo = x
        else: hi = x
    return (lo * hi) ** 0.5

def as_recorded(dd):
    """The district as its records have it: every airway's resistance times the errors of the reading it is taken from."""
    name = dd["name"]; R = dict(dd["Rnow"]); kind = {b["branch"]: b["kind"] for b in dd["branches"]}
    for nm in R:
        if kind[nm] == "airway":
            if nm in dd["altered"]: R[nm] *= err("dpnow", name, nm) / err("qnow", name, nm) ** 2
            else: R[nm] *= err("dp", name, len(CAMPAIGNS) - 1, nm) / err("q", name, len(CAMPAIGNS) - 1, nm) ** 2
        elif nm == dd["breach"]: R[nm] *= err("dpnow", name, nm) / err("qnow", name, nm) ** 2
    return R

def make(name):
    spec = SITES[name]
    true = lambda dd: dd["Rnow"]
    # the intake's bulkhead door: shut, it takes the working district 1.8 times as far as the stall point needs
    sd1, sd2 = 0.018, 0.006
    for _ in range(3):
        size, dn, up = size_for(name, spec, sd2, sd1)
        d = build(name, spec, size=size, sd2_r=sd2, sd1_r=sd1)
        s = working(d, np.random.default_rng(spec["seed"] + 1000)); s["SD-1"] = "closed"
        sd1 = sig(1.8 * edge(name, spec, size, 1, sd2, s, true))
        if spec["close"]: sd2 = sd1 / 1.8
    role_dir = {"example": os.path.join(DATA, "examples", name), "pending": os.path.join(DATA, "pending", name), "hidden": os.path.join(HIDDEN, name)}[spec["role"]]
    for attempt in range(60):
        seed = spec["seed"] + 1000 + 77 * attempt; SALT[0] = seed
        d = build(name, spec, size=size, sd2_r=sd2, sd1_r=sd1); history(d, spec, np.random.default_rng(seed))
        gap = None
        if spec["close"]:
            # the last closure, of the return's bulkhead door: the resistance of the return's first entry at which the
            # healthy state just ceases, for the district as it is and as its records have it; built between the two
            s = settings_at(d, d["close_at"])
            e_true = edge(name, spec, size, 2, sd1, s, true); e_rec = edge(name, spec, size, 2, sd1, s, as_recorded)
            gap = abs(np.log(e_true / e_rec))
            if spec["close"] != "any" and (spec["close"] == "stalls") != (e_rec > e_true):
                print("%-13s attempt %d refused: the last closure goes the other way" % (name, attempt), flush=True); continue
            if gap < 0.004:
                print("%-13s attempt %d refused: the two edges are %.4f per cent apart at %.4f" % (name, attempt, 100 * gap, e_true), flush=True); continue
            d = build(name, spec, size=size, sd2_r=(e_true * e_rec) ** 0.5, sd1_r=sd1); history(d, spec, np.random.default_rng(seed))
        allowance = len(d["altered"]) + (1 if spec["breach"] else 0) + (1 if spec["close"] else 0)
        sv = campaigns(d, spec)
        write(d, role_dir, sv, allowance)
        tf = os.path.join(HIDDEN, "_true_%s.json" % name)
        json.dump(dict(R=d["Rnow"], breach=d["breach"], close_at=d["close_at"], altered=d["altered"]), open(tf, "w"), indent=1)
        rep = T.audit(role_dir, tf, d["close_at"])
        if not rep["ok"]:
            print("%-13s attempt %d refused: %s" % (name, attempt, rep["why"]), flush=True); continue
        base = rep["base"]; dd = rep["d"]
        book = book_of(d, base["now"], allowance)
        rec_sim = T.simulate(dd, on_record(d, sv, book))
        nb = len(base["rounds"]) if d["close_at"] is None else sum(1 for t in base["rounds"] if t < d["close_at"])
        if rec_sim["rd_limbs"][:nb] != base["rd_limbs"][:nb]:
            print("%-13s attempt %d refused: the records give another state before the last closure" % (name, attempt), flush=True); continue
        if spec["close"] and all(a == b for a, b in zip(rec_sim["rd_limbs"][nb:], base["rd_limbs"][nb:])):
            print("%-13s attempt %d refused: the records and the district agree after the last closure" % (name, attempt), flush=True); continue
        if not spec["close"] and rec_sim["rd_limbs"] != base["rd_limbs"]:
            print("%-13s attempt %d refused: records and district differ" % (name, attempt), flush=True); continue
        folder = RIG if spec["role"] != "hidden" else HLAB
        json.dump(book, open(os.path.join(folder, name + ".json"), "w"))
        out = os.path.join(role_dir, "expected.csv" if spec["role"] == "example" else "truth.csv")
        if spec["role"] == "pending": out = os.path.join(HIDDEN, "_pending_" + name + "_truth.csv")
        with open(out, "w", newline="") as f:
            c = csv.writer(f, lineterminator="\n"); c.writerow(["point", "flow_m3_s"])
            for p, t, b in dd["points"]: c.writerow([p, "%.4f" % base["flows"][p]])
        facts = dict(rep["facts"]); facts.update(size=size, band=[dn, up], altered=d["altered"], breach=d["breach"], close_at=d["close_at"],
                                                edge_gap_per_cent=None if gap is None else 100 * gap,
                                                limbs_on_record="".join("s" if l != "RR" else "." for l in rec_sim["rd_limbs"]))
        if d["breach"]:
            br = next(b for b in d["branches"] if b["branch"] == d["breach"]); leak = []       # what the campaigns show at its intake end
            ends = {b["branch"]: (b["frm"], b["to"]) for b in d["branches"]}
            for day in sorted({r[0] for r in sv if r[1].startswith(d["breach"][:2])}):
                qin = sum(q for dy, nm, dp, q in sv if dy == day and ends[nm][1] == br["frm"])
                qout = sum(q for dy, nm, dp, q in sv if dy == day and ends[nm][0] == br["frm"])
                leak.append(round(qin - qout, 2))
            facts["breach_leak_in_campaigns_m3_s"] = leak; facts["breach_resistance_booked_and_real"] = [br["R"], d["Rnow"][d["breach"]]]
        json.dump(facts, open(os.path.join(HIDDEN, "_facts_%s.json" % name), "w"), indent=1)
        print("%-13s %-7s attempt %d  allowance %d  altered %d  breach %s  close %s  district %s  records %s" % (
            name, spec["role"], attempt, allowance, len(d["altered"]), d["breach"], d["close_at"], facts["limbs"], facts["limbs_on_record"]), flush=True)
        return
    raise SystemExit("no acceptable record for " + name)

if __name__ == "__main__":
    for p in (HIDDEN, HLAB, RIG): os.makedirs(p, exist_ok=True)
    for nm in (sys.argv[1:] or list(SITES)): make(nm)
