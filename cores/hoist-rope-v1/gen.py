"""Builds the works of the hoist-rope core: visible (two with results, one without) and hidden with the shift.
Sealed physics is here too: every station's rope element is followed as material through the log, so a rope
turned end for end carries its damage with it. python3 gen.py [works ...]"""
import csv, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
G = 9.80665
ROPE = {"8x36": (-1.214, 0.887, 7.432, -2.103), "6x36": (-1.371, 0.934, 7.518, -2.146)}   # b0 b1 b2 b3
DAYS = 300.0
# turned: ropes turned end for end at a time the records do not give. wrong: ropes whose surveys, from one survey
# on, were taken from the dead end and written down as if from the drum. tall: cranes above the visible lifts.
WORKS = {
    "forge_bay":    dict(role="example", seed=51, tag="FB", cranes=5, turned=0, wrong=0, eight=1, tall=0),
    "plate_shop":   dict(role="example", seed=52, tag="PS", cranes=5, turned=0, wrong=0, eight=1, tall=0),
    "melt_hall":    dict(role="pending", seed=53, tag="MH", cranes=5, turned=1, wrong=1, eight=1, tall=0),
    "roll_store":   dict(role="hidden", seed=61, tag="RS", cranes=6, turned=1, wrong=1, eight=2, tall=2),
    "press_line":   dict(role="hidden", seed=62, tag="PL", cranes=6, turned=1, wrong=1, eight=2, tall=1),
    "coil_yard":    dict(role="hidden", seed=63, tag="CY", cranes=5, turned=0, wrong=0, eight=1, tall=2),
    "ladle_aisle":  dict(role="hidden", seed=64, tag="LA", cranes=6, turned=1, wrong=2, eight=3, tall=2),
    "die_store":    dict(role="hidden", seed=65, tag="DS", cranes=6, turned=0, wrong=1, eight=1, tall=1),
    "scrap_bay":    dict(role="hidden", seed=66, tag="SB", cranes=6, turned=2, wrong=1, eight=2, tall=3),
}


def endurance(S, D, d, cons):
    b0, b1, b2, b3 = ROPE[cons]
    r = np.log10(D / d)
    return 10.0 ** (b0 + (b1 + b3 * r) * np.log10(S / d ** 2) + b2 * r)


def make_crane(rng, name, eight, tall):
    n = 8 if eight else int(rng.choice([2, 4, 4, 6]))
    H = float(round(rng.uniform(29.3, 42.7) if tall else rng.uniform(11.4, 27.6), 1))
    d = float(rng.choice([16.0, 18.0, 20.0, 22.0, 24.0, 26.0]))
    cons = str(rng.choice(list(ROPE)))
    rated = float(round(0.118 * d * d * n * rng.uniform(0.82, 1.07) / G, 1))      # t, about a fifth of the rope's strength
    block = float(round(rated * rng.uniform(0.035, 0.06), 2))
    Ds = float(round(d * rng.uniform(20.3, 25.2), 0)); Dd = float(round(d * rng.uniform(18.2, 22.4), 0))
    a1 = float(round(rng.uniform(1.13, 1.87), 2)); step = float(round(rng.uniform(0.93, 1.38), 2))
    sheaves = [dict(name="S%d" % j, parts=j, offset=mm(a1 + step * (j - 1)), D=Ds, weight=1.0) for j in range(1, n)]
    sheaves.append(dict(name="drum", parts=n, offset=mm(a1 + step * (n - 1) + rng.uniform(3.7, 8.9)), D=Dd, weight=0.5))
    L = float(5 * np.ceil((sheaves[-1]["offset"] + n * (H - 0.4) + rng.uniform(9.0, 17.0)) / 5))
    return dict(crane=name, falls=n, H=H, d=d, cons=cons, rated=rated, block=block, eff=float(round(rng.uniform(0.93, 0.975), 3)),
                sheaves=sheaves, L=L)


def mm(v):
    """An offset as surveyed to the millimetre; never on the centimetre grid of the logged heights, so that no
    movement ends with a sheave exactly on a station."""
    k = int(round(v * 1000))
    if k % 10 == 0:
        k += 3
    return k / 1000.0


def make_log(rng, cr):
    H = cr["H"]
    pick = rng.uniform(0.6, 1.6); travel = H * rng.uniform(0.58, 0.83) - 1.0
    sets = np.sort(rng.uniform(0.8, max(2.0, 0.45 * H), 3))
    t = 0.0; h = travel; rows = []
    while True:
        t += 0.002 + rng.exponential(1.0 / rng.uniform(11, 17))
        if t >= DAYS:
            break
        load = cr["rated"] * (rng.uniform(0.28, 1.0) if rng.random() < 0.85 else rng.uniform(0.05, 0.3))
        top = travel + rng.normal(0, 0.35) if rng.random() < 0.9 else rng.uniform(travel, H - 2.1)
        seq = [(pick + abs(rng.normal(0, 0.12)), 0.0), (top, load), (float(rng.choice(sets)) + abs(rng.normal(0, 0.2)), load), (travel + rng.normal(0, 0.3), 0.0)]
        for k, (tgt, ld) in enumerate(seq):
            tgt = float(np.clip(tgt, 0.45, H - 2.05))
            if abs(tgt - h) > 0.05:
                rows.append((t + 0.0004 * k, h, tgt, ld)); h = tgt
    a = np.array(rows)
    a[:, 0] = np.round(a[:, 0], 4); a[:, 1:] = np.round(a[:, 1:], 2)      # as the log is written
    return a


def station_damage(cr, log, surveys_t, turn_t):
    """Damage of the element at each station (stations as the rope sits at the end), and the diameters every
    survey reads, station by station as the rope sat then."""
    L = cr["L"]; ns = int(L / 5); x_now = 2.5 + 5.0 * np.arange(ns)
    d0 = cr["d"]
    t, h1, h2, ld = log.T
    S = (ld + cr["block"]) * 1e3 * G / (cr["falls"] * cr["eff"])
    lo = np.minimum(h1, h2); hi = np.maximum(h1, h2)
    turned_now = turn_t is not None
    # position of each end-state station's element before the turn
    x_before = L - x_now if turned_now else x_now
    def pos(tt):
        return np.where(tt < turn_t, 1, 0) if turned_now else np.zeros_like(tt, int)
    before = pos(t).astype(bool)
    D = np.zeros(ns)
    # diameters are generated from damage, so march survey by survey
    diam = []                              # per survey: array by element (end-state station order)
    rng = np.random.default_rng(int(L * 1000 + cr["H"] * 10))
    # how a rope thins is its own affair: constants of the rope, and a gain that varies along it, element by element
    kappa = rng.uniform(0.034, 0.062); base = rng.uniform(0.007, 0.016); pw = rng.uniform(0.55, 0.9)
    z = rng.standard_normal(ns + 4); gain = np.exp(0.16 * (np.convolve(z, np.ones(3) / 3 ** 0.5, "same")[2:-2] * 0.7 + 0.7 * rng.standard_normal(ns)))
    d_el = np.full(ns, d0)
    edges = list(surveys_t) + [DAYS + 1]
    Dref = None
    acc = np.zeros(ns)
    hist = []
    for k in range(len(surveys_t)):
        # the survey at edges[k] reads the elements as they are
        hist.append(acc.copy())
        sel = (t >= edges[k]) & (t < edges[k + 1])
        if k == 0:
            d_el = np.round(d0 * (1 + 0.0004 * rng.standard_normal(ns)), 2)
        diam.append(d_el.copy())
        for s in cr["sheaves"]:
            for part_before in (True, False):
                m = sel & (before == part_before)
                if not m.any():
                    continue
                xp = x_before if part_before else x_now
                hc = cr["H"] - (L - s["offset"] - xp) / s["parts"]                     # hook height at which the sheave meets the element
                cross = (lo[m][:, None] < hc[None, :]) & (hc[None, :] <= hi[m][:, None])
                N = endurance(S[m][:, None], s["D"], d_el[None, :], cr["cons"])
                acc += s["weight"] * (cross / N).sum(0)
        if k + 1 < len(surveys_t):
            scale = max(acc.max(), 1e-9)
            d_el = np.round(d0 * (1 - base * edges[k + 1] / DAYS - kappa * gain * (acc / REF[cr["crane"]]) ** pw) + 0.012 * rng.standard_normal(ns), 2)
    return acc, diam


REF = {}


def build(name):
    spec = WORKS[name]; rng = np.random.default_rng(spec["seed"]); nc = spec["cranes"]
    kinds = [dict(eight=i < spec["eight"]) for i in rng.permutation(nc)]
    for i, k in enumerate(rng.permutation(nc)):
        kinds[int(k)]["tall"] = i < spec["tall"]
    perm = rng.permutation(nc)
    turned = set(int(k) for k in perm[:spec["turned"]]); wrong = set(int(k) for k in perm[spec["turned"]:spec["turned"] + spec["wrong"]])
    surveys_t = [0.0] + list(np.round(np.cumsum(rng.uniform(12.7, 17.9, 19)), 2))
    surveys_t = [s for s in surveys_t if s < DAYS - 5]
    cranes = []; out_rows = []; srows = []; lrows = []
    for i in range(nc):
        for attempt in range(50):
            cr = make_crane(rng, "%s-%d" % (spec["tag"], i + 1), kinds[i]["eight"], kinds[i]["tall"])
            log = make_log(rng, cr)
            turn_t = None; kw = None
            if i in turned:
                k = int(rng.integers(7, 13))
                turn_t = float(round(rng.uniform(surveys_t[k] + 2.3, surveys_t[k + 1] - 2.3), 2))
            if i in wrong:
                kw = int(rng.integers(8, 14))          # the first survey taken from the dead end
            # first pass for the wear scale, second with it
            REF[cr["crane"]] = 1.0
            acc0, _ = station_damage(cr, log, surveys_t, turn_t)
            REF[cr["crane"]] = float(acc0.max())
            acc, diam = station_damage(cr, log, surveys_t, turn_t)
            if turn_t is None and kw is None:
                break
            if kw is not None:
                # the end a survey starts from has to matter: the rope's damage must not be alike from both ends
                if (np.abs(acc - acc[::-1]) > 0.15 * acc.max()).sum() >= 6:
                    break
                continue
            # a turn has to matter: the unturned reading must miss by well over the band at several stations
            accw, _ = station_damage(cr, log, surveys_t, None)   # same log, damage laid as if never turned
            if (np.abs(accw - acc) > 0.15 * acc.max()).sum() >= 4:
                break
        else:
            raise SystemExit("no crane for %s %d" % (name, i))
        cr["turn_day"] = turn_t; cr["from_dead_end_since"] = None if kw is None else surveys_t[kw]
        cranes.append(cr)
        L = cr["L"]; ns = int(L / 5)
        for s in range(ns):
            out_rows.append(["%s-%03d" % (cr["crane"], s + 1), "%.5f" % acc[s]])
        for k, ts in enumerate(surveys_t):
            # a survey lists stations from the drum anchorage as the rope sits on that day
            el = diam[k]
            row_d = el[::-1] if (turn_t is not None and ts < turn_t) else el
            if kw is not None and k >= kw:
                row_d = row_d[::-1]
            for s in range(ns):
                srows.append([cr["crane"], "%.2f" % ts, "%.1f" % (2.5 + 5 * s), "%.2f" % row_d[s]])
        for r in log:
            lrows.append([cr["crane"], "%.4f" % r[0], "%.2f" % r[1], "%.2f" % r[2], "%.2f" % r[3]])
    base = os.path.join(HERE, "core")
    d = {"example": os.path.join(base, "environment", "data", "examples", name),
         "pending": os.path.join(base, "environment", "data", "pending", name),
         "hidden": os.path.join(base, "hidden", name)}[spec["role"]]
    os.makedirs(d, exist_ok=True)
    def wr(fn, head, rs):
        with open(os.path.join(d, fn), "w", newline="") as f:
            x = csv.writer(f, lineterminator="\n"); x.writerow(head); x.writerows(rs)
    wr("cranes.csv", ["crane", "falls", "upper_block_height_m", "block_mass_t", "reeving_efficiency", "rope_construction", "rope_length_m"],
       [[c["crane"], c["falls"], c["H"], c["block"], c["eff"], c["cons"], "%.0f" % c["L"]] for c in cranes])
    wr("sheaves.csv", ["crane", "sheave", "parts", "offset_m", "diameter_mm", "bend_weight"],
       [[c["crane"], s["name"], s["parts"], "%.3f" % s["offset"], "%.0f" % s["D"], s["weight"]] for c in cranes for s in c["sheaves"]])
    wr("movements.csv", ["crane", "day", "from_height_m", "to_height_m", "hook_load_t"], lrows)
    wr("surveys.csv", ["crane", "day", "station_m", "diameter_mm"], srows)
    head = ["row", "damage"]
    if spec["role"] == "example":
        wr("expected.csv", head, out_rows)
    else:
        os.makedirs(os.path.join(base, "truth"), exist_ok=True)
        with open(os.path.join(base, "truth", name + ".csv"), "w", newline="") as f:
            x = csv.writer(f, lineterminator="\n"); x.writerow(head); x.writerows(out_rows)
    os.makedirs(os.path.join(base, "sealed"), exist_ok=True)
    json.dump({"works": name, "role": spec["role"], "survey_days": surveys_t, "cranes": cranes}, open(os.path.join(base, "sealed", name + ".json"), "w"), indent=1)
    return name, spec["role"], len(out_rows), len(lrows), [(c["crane"], c["falls"], c["H"], c["L"], c["turn_day"], c["from_dead_end_since"]) for c in cranes]


if __name__ == "__main__":
    for nm in (sys.argv[1:] or list(WORKS)):
        print(build(nm), flush=True)
