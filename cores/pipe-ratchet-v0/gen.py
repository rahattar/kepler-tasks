"""Builds the works of the pipe-ratchet core. python3 gen.py [works ...]

Each works has six pipe lines. A line has a material, a mean radius and a wall, an operating pressure, and a
plant history: a sequence of load states (pressure, through-wall temperature difference) joined by straight
ramps. The truth is the layered wall of wallmodel.py integrated along every ramp in TRUTH_SUBSTEPS equal
parts with the exact laws; the result is the ratchet strain at the checkpoint states.

Hidden works differ on purpose: three materials never seen in the visible works (constants outside the
visible ranges), lines loaded nearer the ratchet limit, more trips and hydrotests, and longer histories."""
import csv, json, os, sys
import numpy as np
import wallmodel as W

HERE = os.path.dirname(os.path.abspath(__file__))
TRUTH_SUBSTEPS = 32
MATERIALS = {
    # name: E, alpha, k0, (C1,C2,C3), (g1,g2,g3), Q, b
    "316H":    (176300.0, 1.73e-5, 92.6, (104800.0, 19400.0, 2310.0), (1860.0, 227.0, 8.4), 58.0, 6.7),
    "P91":     (191400.0, 1.27e-5, 231.0, (156300.0, 38200.0, 3150.0), (1430.0, 182.0, 6.1), -34.0, 2.9),
    "A106B":   (193100.0, 1.36e-5, 168.0, (87400.0, 21100.0, 1690.0), (1210.0, 151.0, 4.7), 21.5, 9.3),
    # only in the hidden works
    "304H":    (172800.0, 1.81e-5, 78.4, (132600.0, 24700.0, 2870.0), (2410.0, 268.0, 11.2), 71.0, 5.2),
    "P22":     (189600.0, 1.32e-5, 197.0, (119200.0, 29400.0, 2460.0), (1640.0, 205.0, 7.3), -26.0, 3.6),
    "800H":    (168200.0, 1.62e-5, 118.0, (96400.0, 17300.0, 2010.0), (980.0, 131.0, 5.9), 88.0, 4.1),
}
VISIBLE_MATS = ["316H", "P91", "A106B"]
HIDDEN_MATS = ["304H", "P22", "800H", "316H", "P91", "A106B"]
WORKS = [
    dict(works="kiln_row", role="example", seed=11, cycles=(1200, 1500), mats=VISIBLE_MATS, x=(0.62, 0.84), y=(1.6, 2.3), trip=0.12, hydro=0.004),
    dict(works="boiler_east", role="example", seed=12, cycles=(1200, 1500), mats=VISIBLE_MATS, x=(0.62, 0.84), y=(1.6, 2.3), trip=0.12, hydro=0.004),
    dict(works="steam_header", role="pending", seed=13, cycles=(1200, 1500), mats=VISIBLE_MATS, x=(0.62, 0.84), y=(1.6, 2.3), trip=0.12, hydro=0.004),
    dict(works="unit_four", role="hidden", seed=21, cycles=(1500, 1800), mats=HIDDEN_MATS, x=(0.72, 0.92), y=(1.7, 2.5), trip=0.22, hydro=0.008),
    dict(works="reheat_link", role="hidden", seed=22, cycles=(1500, 1800), mats=HIDDEN_MATS, x=(0.72, 0.92), y=(1.7, 2.5), trip=0.22, hydro=0.008),
    dict(works="feed_train", role="hidden", seed=23, cycles=(1500, 1800), mats=HIDDEN_MATS, x=(0.72, 0.92), y=(1.7, 2.5), trip=0.22, hydro=0.008),
]
BAND = 0.03


def mat_row(name):
    E, a, k0, C, g, Q, b = MATERIALS[name]
    return dict(E=E, alpha=a, k0=k0, C=C, g=g, Q=Q, b=b)


def make_line(rng, name, mat, xr, yr):
    E, a, k0, C, g, Q, b = MATERIALS[mat]
    R = float(round(rng.uniform(80, 320), 1)); t = float(round(rng.uniform(0.055, 0.12) * R, 1))
    sm = rng.uniform(*xr) * (k0 + 0.35 * sum(c / gg for c, gg in zip(C[:2], g[:2])))   # membrane stress, MPa
    p = float(round(sm * t / R, 2)); sm = p * R / t
    # thermal stress at the surface E a dT / 2 against the yield stress
    y = rng.uniform(*yr)
    a_up = y * 2 * k0 / (E * a)
    return dict(line=name, material=mat, radius_mm=R, wall_mm=t, p_op=p, a_up=float(a_up))


def make_history(rng, ln, cycles, trip, hydro):
    p, a_up = ln["p_op"], ln["a_up"]
    H = [(0.0, 0.0, 0)]
    for c in range(cycles):
        if rng.random() < hydro:
            H += [(round(1.25 * p, 2), 0.0, 0), (0.0, 0.0, 0)]
        a = round(a_up * rng.uniform(0.62, 1.0), 1)
        H += [(p, a, 0), (p, 0.0, 1 if (c % 10 == 9 or c == cycles - 1) else 0)]
        for _ in range(rng.poisson(0.7)):
            d = round(a_up * rng.uniform(0.15, 0.45) * rng.choice([-1, 1]), 1)
            H += [(p, d, 0), (p, 0.0, 0)]
        if rng.random() < trip:
            H += [(0.0, -round(a_up * rng.uniform(0.55, 0.85), 1), 0), (0.0, 0.0, 0)]
        else:
            H += [(0.0, -round(a_up * rng.uniform(0.18, 0.32), 1), 0), (0.0, 0.0, 0)]
    return H


def integrate(lines, hists, substeps):
    """Lockstep over the lines. Returns {line: [(state index, ratchet strain)] at checkpoints}."""
    m = W.Mat([mat_row(l["material"]) for l in lines]); n = len(lines)
    st = W.State(n)
    T = max(len(h) for h in hists)
    R_t = np.array([l["radius_mm"] / l["wall_mm"] for l in lines])
    out = [[] for _ in lines]
    for k in range(1, T):
        sm = np.array([R_t[i] * hists[i][min(k, len(hists[i]) - 1)][0] for i in range(n)])
        dT = np.array([hists[i][min(k, len(hists[i]) - 1)][1] for i in range(n)])
        W.advance(st, m, sm, dT, substeps)
        for i in range(n):
            if k < len(hists[i]) and hists[i][k][2]:
                out[i].append((k, float(st.eps[i] - sm[i] / m.E[i, 0])))
    return out


def build(spec):
    rng = np.random.default_rng(spec["seed"])
    lines, hists = [], []
    for i in range(6):
        mat = spec["mats"][i % len(spec["mats"])] if spec["role"] == "hidden" else str(rng.choice(spec["mats"]))
        ln = make_line(rng, "%s-%d" % (spec["works"][:2].upper(), i + 1), mat, spec["x"], spec["y"])
        lines.append(ln)
        hists.append(make_history(rng, ln, int(rng.integers(*spec["cycles"])), spec["trip"], spec["hydro"]))
    truth = integrate(lines, hists, TRUTH_SUBSTEPS)
    d = os.path.join(HERE, "core", {"example": "environment/data/examples", "pending": "environment/data/pending",
                                     "hidden": "hidden"}[spec["role"]], spec["works"])
    os.makedirs(d, exist_ok=True)

    def wr(fn, head, rows, where=d):
        with open(os.path.join(where, fn), "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n"); w.writerow(head); w.writerows(rows)
    used = sorted(set(l["material"] for l in lines))
    wr("materials.csv", ["material", "E_MPa", "alpha_per_K", "k0_MPa", "C1_MPa", "gamma1", "C2_MPa", "gamma2",
                         "C3_MPa", "gamma3", "Q_MPa", "b"],
       [[mname, MATERIALS[mname][0], MATERIALS[mname][1], MATERIALS[mname][2], *[x for pair in zip(MATERIALS[mname][3], MATERIALS[mname][4]) for x in pair],
         MATERIALS[mname][5], MATERIALS[mname][6]] for mname in used])
    wr("lines.csv", ["line", "material", "mean_radius_mm", "wall_mm"],
       [[l["line"], l["material"], "%.1f" % l["radius_mm"], "%.1f" % l["wall_mm"]] for l in lines])
    wr("history.csv", ["line", "state", "pressure_MPa", "dT_K", "checkpoint"],
       [[l["line"], k, "%.2f" % s[0], "%.1f" % s[1], s[2]] for l, h in zip(lines, hists) for k, s in enumerate(h)])
    rows = [["%s-%05d" % (l["line"], k), "%.5f" % (100 * v)] for l, tr in zip(lines, truth) for k, v in tr]
    if spec["role"] == "example":
        wr("expected.csv", ["row", "ratchet_pct"], rows)
    else:
        os.makedirs(os.path.join(HERE, "core", "truth"), exist_ok=True)
        wr(spec["works"] + ".csv", ["row", "ratchet_pct"], rows, os.path.join(HERE, "core", "truth"))
    return spec["works"], [(l["line"], l["material"], l["radius_mm"], l["wall_mm"], l["p_op"], round(l["a_up"], 1), len(h),
                             round(100 * tr[-1][1], 3)) for l, h, tr in zip(lines, hists, truth)]


if __name__ == "__main__":
    for nm in (sys.argv[1:] or [w["works"] for w in WORKS]):
        print(build(next(w for w in WORKS if w["works"] == nm)), flush=True)
