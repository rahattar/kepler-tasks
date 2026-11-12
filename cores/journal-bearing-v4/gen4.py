"""Bare core v4: site packages. A site's bearings draw oil from shared systems; after a changeover the new
charges are unknown and the laboratory analyses a fixed number of samples, ordered once.
usage: gen4.py OUT NAME...   (writes OUT/data/examples/NAME or OUT/hidden/NAME, and OUT/lab/NAME.json)"""
import csv, datetime, json, math, os, random, sys
import solver as rb

rb.GRIDS = ((240, 24), (240, 24))          # the truth grid
NOMINAL = {32: (32.0, 5.4, 865.0), 46: (46.0, 6.8, 870.0), 68: (68.0, 8.7, 875.0)}
MODELS = {"JB-90": (90.0, 72.0, 60, 3.0, (1480, 3560), (0.6, 2.2)), "JB-125": (125.0, 110.0, 85, 6.0, (1480, 2960), (0.6, 2.4)),
          "JB-160": (160.0, 130.0, 110, 9.0, (900, 1780), (0.5, 2.0)), "JB-200": (200.0, 180.0, 140, 14.0, (600, 1480), (0.6, 2.2))}
ROUNDS = ["2024-03-11", "2024-09-09", "2025-03-10", "2025-09-08"]
CHANGE = "2026-01-19"; FIRST = "2025-10-06"; LAST = "2026-09-25"

# name: (seed, examples?, split system or None, consoles [(system, grade, renewed, [machines])], self-contained machines)
SITES = {
 "north_works": (11, True, None, 3, 1), "east_works": (12, True, None, 4, 2),
 "quay_site": (21, False, 1, 5, 2), "ridge_plant": (22, False, 2, 4, 2), "canal_works": (23, False, 0, 5, 1),
 "upper_mill": (24, False, 3, 5, 2), "south_yard": (25, False, None, 4, 2), "tank_farm": (26, False, 1, 4, 3),
}

def day(rng, a, b):
    A, B = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    return (A + datetime.timedelta(days=rng.randrange(1, (B - A).days))).isoformat()

def scaled(nom, f):
    return (round(nom[0] * f, 1), round(nom[1] * (1 + 0.6 * (f - 1)), 2), round(nom[2] + 30 * (f - 1)))

def build(out, name):
    seed, example, split, n_cons, n_self = SITES[name]
    rng = random.Random(seed)
    kinds = ["P", "K", "C", "B", "G", "M"]
    systems, machines, bearings = [], [], []
    mno = 100 + 10 * rng.randrange(1, 9)
    for s in range(n_cons):
        sysname = "LO-%d" % (s + 1); grade = rng.choice([46, 46, 68, 32])
        nm = 3 if s == split else rng.choice([2, 3])
        ms = []
        for _ in range(nm):
            mno += rng.randrange(1, 6); ms.append("%s-%d" % (rng.choice(kinds), mno))
        # charges: one for the system, or two where the listed system is really two consoles
        groups = [ms[:2], ms[2:]] if s == split else [ms]
        renewed = not (s == n_cons - 1 and split != s)          # the last console keeps its old charge
        systems.append(dict(system=sysname, kind="console", grade=grade, renewed=renewed, groups=groups))
    for _ in range(n_self):
        mno += rng.randrange(1, 6); m = "%s-%d" % (rng.choice(kinds), mno)
        systems.append(dict(system="SC-" + m, kind="self-contained", grade=rng.choice([46, 68]), renewed=True, groups=[[m]]))
    lab, charges = {}, {}
    samples = []
    for sy in systems:
        base = rng.uniform(0.94, 1.06)
        for g, ms in enumerate(sy["groups"]):
            off = 0.0 if g == 0 else rng.choice([-1, 1]) * rng.uniform(0.085, 0.11)
            old = [scaled(NOMINAL[sy["grade"]], (base + off) * (1 + 0.004 * r)) for r in range(len(ROUNDS))]
            new = scaled(NOMINAL[sy["grade"]], (rng.uniform(0.9, 0.97) if rng.random() < 0.5 else rng.uniform(1.04, 1.12))
                         + (0.0 if g == 0 else -off)) if sy["renewed"] else None
            for m in ms:
                charges[m] = dict(old=old, new=new, system=sy["system"], group=g)
        for m in [m for ms in sy["groups"] for m in ms]:
            model = rng.choice(list(MODELS))
            for pos in (["DE", "NDE"] if rng.random() < 0.6 else ["DE"]):
                bearings.append(dict(tag="%s-%s" % (m, pos), machine=m, oil_system=sy["system"], model=model))
        # two samples a round at two different machines where there are two; every machine sampled over the rounds
        allm = [m for ms in sy["groups"] for m in ms]
        for r, date in enumerate(ROUNDS):
            if len(sy["groups"]) == 2:
                picks = [sy["groups"][0][r % 2], sy["groups"][1][0]]
            elif len(allm) >= 2:
                picks = [allm[r % len(allm)], allm[(r + 1) % len(allm)]]
            else:
                picks = [allm[0]]
            for m in picks:
                tag = [b["tag"] for b in bearings if b["machine"] == m][r % len([b for b in bearings if b["machine"] == m])]
                v = charges[m]["old"][r]
                jit = rng.choice([-0.1, 0.0, 0.1])
                samples.append((date, tag, "%.1f" % (v[0] + jit), "%.2f" % v[1], "%d" % v[2]))
    samples.sort()
    # what each machine's oil is taken to be, by the standard: the latest analysis of the charge
    def latest_old(m):
        sy = charges[m]["system"]; grp = charges[m]["group"]
        mine = {mm for mm in charges if charges[mm]["system"] == sy and charges[mm]["group"] == grp}
        last = max(s[0] for s in samples if s[1].rsplit("-", 1)[0] in mine)
        vals = [(float(s[2]), float(s[3]), float(s[4])) for s in samples if s[0] == last and s[1].rsplit("-", 1)[0] in mine]
        return tuple(sum(v[i] for v in vals) / len(vals) for i in range(3))
    for b in bearings:
        c = charges[b["machine"]]
        if c["new"] is not None:
            lab[b["tag"]] = c["new"]
    budget = sum(len(sy["groups"]) for sy in systems if sy["renewed"])
    d = os.path.join(out, "data/examples" if example else "hidden", name); os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(out, "lab"), exist_ok=True)
    json.dump(dict(budget=budget, analyses=lab), open(os.path.join(out, "lab", name + ".json"), "w"))
    json.dump(dict(site=name, lab_samples=budget), open(d + "/site.json", "w"), indent=1)
    with open(d + "/bearings.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["tag", "machine", "oil_system", "journal_diameter_mm", "length_mm", "radial_clearance_um", "groove_angles_deg", "oil_flow_L_min"])
        for b in bearings:
            D, L, c, q, _, _ = MODELS[b["model"]]
            w.writerow([b["tag"], b["machine"], b["oil_system"], D, L, c, "90;270", q])
    with open(d + "/oil_systems.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["oil_system", "kind", "oil_grade"])
        for sy in systems: w.writerow([sy["system"], sy["kind"], "ISO VG %d" % sy["grade"]])
    with open(d + "/oil_log.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "oil_system", "work", "remarks"])
        for sy in systems:
            if sy["renewed"]: w.writerow([CHANGE, sy["system"], "CHARGE_RENEWED", "drained, flushed and refilled, new supplier"])
    with open(d + "/oil_samples.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["date", "sampled_at", "nu40_cSt", "nu100_cSt", "rho15_kg_m3"]); w.writerows(samples)
    # operating points and their results
    rows, truth = [], []
    for b in bearings:
        D, L, c, q, sp, sl = MODELS[b["model"]]
        ch = charges[b["machine"]]
        states = {"old": (D, L, c / 1000.0, (90.0, 270.0), latest_old(b["machine"]), q)}
        if ch["new"] is not None:
            states["new"] = (D, L, c / 1000.0, (90.0, 270.0), ch["new"], q)
        brgs = {k: rb.Bearing(v) for k, v in states.items()}
        n = 0; tries = 0
        while n < 110 and tries < 400:
            tries += 1
            date = day(rng, FIRST, CHANGE) if rng.random() < 0.35 else day(rng, CHANGE, LAST)
            which = "new" if (date > CHANGE and "new" in brgs) else "old"
            brg = brgs[which]
            rpm = round(rng.uniform(*sp) / 10) * 10
            load = round(rng.uniform(*sl) * D * L / 100) * 100
            t = round(rng.uniform(38, 52), 1)
            w_ = rpm * 2 * math.pi / 60.0
            brg.lands = brg.grids[0]
            xs, aux = brg.solve_regime(w_, load, math.pi, t, False, (0.0, 0.9, t + 8.0))
            eps, psi, T, power, pmax, Rec = aux
            if not (abs(brg.residual(xs, w_, load, math.pi, t, False)[0]).max() < 1e-7 and Rec < 0.7 * brg.Ret and 0.1 < eps < 0.93):
                continue
            n += 1
            pt = "%s-%03d" % (b["tag"], n)
            rows.append(dict(point=pt, tag=b["tag"], date=date, speed_rpm=rpm, load_N=load, load_angle_deg=0, inlet_C=t))
            truth.append((date, pt, ["%.3f" % (brg.c * (1 - eps) * 1e6), "%.2f" % math.degrees(psi - math.pi), "%.4f" % (power / 1e3), "%.2f" % T, "%.4f" % (pmax / 1e6)]))
    order = sorted(range(len(rows)), key=lambda i: (rows[i]["date"], rows[i]["point"]))
    with open(d + "/points.csv", "w", newline="") as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows[i] for i in order)
    with open(os.path.join(d, "expected.csv" if example else "truth.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["point", "h_min_um", "attitude_deg", "power_kW", "t_eff_C", "p_max_MPa"])
        for i in order: w.writerow([truth[i][1]] + truth[i][2])
    print(name, "bearings", len(bearings), "points", len(rows), "budget", budget, "systems renewed as listed",
          sum(1 for sy in systems if sy["renewed"]), flush=True)

if __name__ == "__main__":
    for name in sys.argv[2:]:
        build(sys.argv[1], name)
