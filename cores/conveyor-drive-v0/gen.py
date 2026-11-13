"""Builds the conveyor lines of the core: visible (two with results, one without) and hidden with the shift.
python3 gen.py [line ...]"""
import csv, json, os, sys
import numpy as np
import convsim as cs

HERE = os.path.dirname(os.path.abspath(__file__))
DT = 5.0; STEPS = 17280; PER = 180          # a day of 5 s steps, 15 minute intervals
# worn: flights whose drive pulley lagging has worn since the register was written
LINES = {
    "quarry_line":  dict(role="example", seed=31, tag="QL", flights=3, worn=0, three=1, down=1),
    "ridge_haul":   dict(role="example", seed=32, tag="RH", flights=3, worn=0, three=1, down=0),
    "pit_incline":  dict(role="pending", seed=33, tag="PI", flights=3, worn=1, three=1, down=0),
    "valley_run":   dict(role="hidden", seed=41, tag="VR", flights=3, worn=1, three=1, down=1),
    "long_reach":   dict(role="hidden", seed=42, tag="LR", flights=4, worn=2, three=2, down=0),
    "east_stack":   dict(role="hidden", seed=43, tag="ES", flights=3, worn=0, three=1, down=1),
    "mill_feed":    dict(role="hidden", seed=44, tag="MF", flights=3, worn=1, three=0, down=1),
    "crest_line":   dict(role="hidden", seed=45, tag="CL", flights=4, worn=2, three=2, down=1),
    "delta_tip":    dict(role="hidden", seed=46, tag="DT", flights=3, worn=1, three=1, down=0),
}


def make_flight(rng, name, three, down, hidden, q_design):
    L_tot = rng.uniform(1500, 5200 if not hidden else 7500)
    nsec = int(rng.integers(3, 7))
    cuts = np.sort(rng.uniform(0.1, 0.9, nsec - 1))
    lens = np.diff(np.concatenate([[0], cuts, [1]])) * L_tot
    if down:
        slopes = rng.uniform(-0.055, -0.01, nsec)
    else:
        slopes = rng.uniform(-0.01, 0.06, nsec)
    sections = [(float(round(l, 0)), float(round(l * s, 1))) for l, s in zip(lens, slopes)]
    L = sum(s[0] for s in sections); H = sum(s[1] for s in sections)
    fl = dict(flight=name, length=L, rise=H, sections=sections,
              m_belt=float(round(rng.uniform(30, 48), 1)), m_idler_carry=float(round(rng.uniform(15, 25), 1)),
              m_idler_return=float(round(rng.uniform(6, 10), 1)), f=float(round(rng.uniform(0.016, 0.024), 4)),
              C=float(round(rng.uniform(1.03, 1.10), 3)), EA=float(round(rng.uniform(1.0, 1.8), 2)) * 1e8)
    roles = ["head1", "head2", "tail"] if three else (["head1", "head2"] if rng.random() < 0.75 else ["head1"])
    v_nom = rng.uniform(4.6, 5.6)
    mL = q_design / 3.6 / v_nom
    F_design = fl["C"] * fl["f"] * cs.G * (L * (2 * fl["m_belt"] + fl["m_idler_carry"] + fl["m_idler_return"]) + mL * L) + cs.G * mL * H
    P_each = abs(F_design) * v_nom / 0.93 / len(roles) / rng.uniform(0.72, 0.9) / 1e3
    P_each = max(float(10 * round(P_each / 10)), 110.0)
    fl["T_tu"] = float(round(max(0.45 * abs(F_design), 40e3) + rng.uniform(10e3, 40e3), -3))
    drives = []
    for r in roles:
        D = float(rng.choice([1000.0, 1100.0, 1250.0, 1400.0])) + float(round(rng.uniform(-3, 3), 1))
        ratio = float(round(np.pi * D * 1e-3 * cs.N0 / (60 * v_nom) * (1 + rng.uniform(-0.002, 0.002)), 3))
        drives.append(dict(role=r, P_rated=P_each, ratio=ratio, D_reg=D, D_true=D, eta=float(round(rng.uniform(0.92, 0.95), 3)),
                           s_rated=float(round(rng.uniform(0.026, 0.040), 4))))
    fl["drives"] = drives
    return fl


def feed_log(rng, q_design):
    q = np.zeros(STEPS); t = 0; level = 0.0
    while t < STEPS:
        dur = int(rng.integers(120, 1400))
        r = rng.random()
        new = 0.0 if r < 0.12 else q_design * rng.uniform(0.35, 1.0)
        ramp = int(rng.integers(6, 60))
        seg = np.full(dur, new); seg[:ramp] = np.linspace(level, new, ramp)
        seg = seg * (1 + 0.03 * rng.standard_normal(dur)) if new > 0 else seg
        q[t:t + dur] = np.clip(seg[:STEPS - t], 0, None); level = new; t += dur
    q[:24] = 0.0
    return np.round(q, 0)


def build(name):
    spec = LINES[name]; rng = np.random.default_rng(spec["seed"]); hidden = spec["role"] == "hidden"
    q_design = float(100 * round(rng.uniform(1600, 3200 if not hidden else 4200) / 100))
    nf = spec["flights"]
    order = rng.permutation(nf)
    kinds = {}
    for i, k in enumerate(order):
        kinds[int(k)] = dict(three=i < spec["three"])
    for i, k in enumerate(rng.permutation(nf)):
        kinds[int(k)]["down"] = i < spec["down"]
    worn_pick = [int(k) for k in rng.permutation(nf)[:spec["worn"]]]
    flights = []
    for j in range(nf):
        for attempt in range(200):
            fl = make_flight(rng, "%s-%d" % (spec["tag"], j + 1), kinds[j]["three"], kinds[j]["down"], hidden, q_design)
            if j in worn_pick:
                multi = [d for d in fl["drives"]]
                if len(multi) < 2:
                    continue
                d = multi[int(rng.integers(0, len(multi)))]
                d["D_true"] = float(round(d["D_reg"] * (1 - rng.uniform(0.008, 0.020)), 1))
            # sane at empty and at full feed: belt in tension everywhere, traction within what lagging holds
            ok = True
            for q in (0.0, 0.5 * q_design, q_design):
                v, vw, dr = cs.survey_state(fl, q)
                c = cs.drive_consts(fl)
                mL = q / 3.6 / v
                Rc, Rr = cs.resist(fl, mL * fl["length"], mL * fl["rise"], q / 3.6, v)
                v2, F, ent, ext, Tw = cs.solve_drives(fl, Rc + Rr, Rr, c, v)
                tmin = min(min(ent.values()), min(ext[r["role"]] for r in c), Tw)
                tr = max(max(ent[r["role"]], ext[r["role"]]) / min(ent[r["role"]], ext[r["role"]]) for r in c)
                load = max(abs(x["kW"]) / d0["P_rated"] for x, d0 in zip(dr, fl["drives"]))
                if tmin < 15e3 or tr > 3.2 or load > 1.25:
                    ok = False
            if ok:
                break
        else:
            raise SystemExit("no flight for %s %d" % (name, j))
        flights.append(fl)
    feed = feed_log(rng, q_design)
    # surveys: five campaigns at steady feeds
    srng = np.random.default_rng(spec["seed"] + 700)
    camp_q = np.round(q_design * np.array([0.0, 0.45, 0.62, 0.8, 0.97]) * (1 + 0.03 * srng.standard_normal(5)), 0)
    camps = []
    for ci, q in enumerate(camp_q):
        for fl in flights:
            v, vw, dr = cs.survey_state(fl, q)
            camps.append(dict(c=ci + 1, flight=fl["flight"], q=q, vw=vw * (1 + 0.0003 * srng.standard_normal()),
                              drives=[(d["role"], d["rpm"] + 0.05 * srng.standard_normal(), d["kW"] * (1 + 0.002 * srng.standard_normal())) for d in dr]))
    # the log
    rows = []; q_in = feed
    for fl in flights:
        P, TR, vs, q_out = cs.run_flight(fl, q_in, DT)
        nint = STEPS // PER
        for d in fl["drives"]:
            p = P[d["role"]].reshape(nint, PER); tr = TR[d["role"]].reshape(nint, PER)
            for i in range(nint):
                rows.append(["%s-%s-%03d" % (fl["flight"], d["role"], i + 1), "%.3f" % p[i].mean(), "%.3f" % p[i].max(), "%.3f" % p[i].min(), "%.5f" % tr[i].max()])
        q_in = q_out
    base = os.path.join(HERE, "core")
    d = {"example": os.path.join(base, "environment", "data", "examples", name),
         "pending": os.path.join(base, "environment", "data", "pending", name),
         "hidden": os.path.join(base, "hidden", name)}[spec["role"]]
    os.makedirs(d, exist_ok=True)
    def wr(fn, head, rs):
        with open(os.path.join(d, fn), "w", newline="") as f:
            x = csv.writer(f, lineterminator="\n"); x.writerow(head); x.writerows(rs)
    json.dump({"line": name, "step_s": DT, "interval_steps": PER, "flights": [fl["flight"] for fl in flights]},
              open(os.path.join(d, "line.json"), "w"), indent=1)
    wr("flights.csv", ["flight", "belt_kg_m", "idlers_carry_kg_m", "idlers_return_kg_m", "secondary_factor", "belt_stiffness_MN", "take_up_tension_kN"],
       [[fl["flight"], fl["m_belt"], fl["m_idler_carry"], fl["m_idler_return"], fl["C"], "%.0f" % (fl["EA"] / 1e6), "%.0f" % (fl["T_tu"] / 1e3)] for fl in flights])
    wr("profile.csv", ["flight", "section", "length_m", "rise_m"],
       [[fl["flight"], i + 1, "%.0f" % s[0], "%.1f" % s[1]] for fl in flights for i, s in enumerate(fl["sections"])])
    wr("drives.csv", ["flight", "drive", "rated_kW", "gear_ratio", "pulley_diameter_mm", "efficiency"],
       [[fl["flight"], dd["role"], "%.0f" % dd["P_rated"], "%.3f" % dd["ratio"], "%.1f" % dd["D_reg"], "%.3f" % dd["eta"]] for fl in flights for dd in fl["drives"]])
    wr("surveys.csv", ["campaign", "flight", "feed_t_h", "belt_speed_m_s", "drive", "input_rpm", "motor_kW"],
       [[c["c"], c["flight"], "%.0f" % c["q"], "%.4f" % c["vw"], r, "%.2f" % n, "%.1f" % p] for c in camps for r, n, p in c["drives"]])
    wr("feed.csv", ["step", "feed_t_h"], [[i, "%.0f" % q] for i, q in enumerate(feed)])
    head = ["row", "mean_kW", "max_kW", "min_kW", "traction_peak"]
    if spec["role"] == "example":
        wr("expected.csv", head, rows)
    else:
        os.makedirs(os.path.join(base, "truth"), exist_ok=True)
        with open(os.path.join(base, "truth", name + ".csv"), "w", newline="") as f:
            x = csv.writer(f, lineterminator="\n"); x.writerow(head); x.writerows(rows)
    os.makedirs(os.path.join(base, "sealed"), exist_ok=True)
    json.dump({"line": name, "role": spec["role"], "design_feed_t_h": q_design, "flights": flights},
              open(os.path.join(base, "sealed", name + ".json"), "w"), indent=1)
    worn = [(fl["flight"], dd["role"], round(100 * (1 - dd["D_true"] / dd["D_reg"]), 2)) for fl in flights for dd in fl["drives"] if dd["D_true"] != dd["D_reg"]]
    return name, spec["role"], len(rows), "design %d t/h" % q_design, [(fl["flight"], round(fl["length"]), round(fl["rise"]), len(fl["drives"])) for fl in flights], "worn", worn


if __name__ == "__main__":
    for nm in (sys.argv[1:] or list(LINES)):
        print(build(nm), flush=True)
