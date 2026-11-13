"""Builds the nine cell packages of the engine-indicating core and the sealed results.
usage: python3 gen.py OUT   ->  OUT/environment/data/{examples,pending}, OUT/hidden, OUT/truth"""
import json, os, sys, csv
import numpy as np
import ei

FINE = np.arange(-185.0, 185.0 + 1e-9, 0.1)
ENC = -180.0 + 0.5 * np.arange(720)
COLS = ["imep_bar", "pmax_bar", "apmax_deg", "ca10_deg", "ca50_deg", "q_gross_J"]

# role, cell, engine, index error (deg: true crank angle of the index pulse), heat transfer factor, seed
CELLS = [
    dict(role="example", cell="cell_03", seed=3, eps=0.0, gain=1.0, f_ht=1.03, cyl=4,
         eng=dict(bore_mm=82.0, stroke_mm=90.0, conrod_mm=145.0, compression_ratio=10.5, ivc_deg=-140.0, evo_deg=130.0),
         fam="si", speeds=(1500, 2000, 2500, 3000, 3500), mans=(0.45, 0.70, 0.98), nf=10, scale=0.02),
    dict(role="example", cell="cell_08", seed=8, eps=0.0, gain=1.0, f_ht=0.96, cyl=4,
         eng=dict(bore_mm=76.0, stroke_mm=84.0, conrod_mm=138.0, compression_ratio=10.0, ivc_deg=-136.0, evo_deg=128.0),
         fam="si", speeds=(1500, 2500, 3500, 4000), mans=(0.55, 1.00, 1.60), nf=10, scale=0.02),
    dict(role="pending", cell="cell_11", seed=11, eps=-1.60, gain=1.0, f_ht=1.05, cyl=6,
         eng=dict(bore_mm=86.0, stroke_mm=86.0, conrod_mm=143.0, compression_ratio=11.0, ivc_deg=-138.0, evo_deg=130.0),
         fam="si", speeds=(1200, 2000, 2800, 3600), mans=(0.50, 0.80, 1.00), nf=10, scale=0.02),
    dict(role="pending", cell="cell_13", seed=13, eps=0.0, gain=1.06, f_ht=0.97, cyl=4,
         eng=dict(bore_mm=80.0, stroke_mm=84.0, conrod_mm=136.0, compression_ratio=10.8, ivc_deg=-137.0, evo_deg=129.0),
         fam="si", speeds=(1400, 2200, 3000, 3800), mans=(0.48, 0.75, 1.02), nf=10, scale=0.02),
    dict(role="hidden", cell="cell_02", seed=2, eps=+2.20, gain=1.0, f_ht=0.94, cyl=4,
         eng=dict(bore_mm=84.0, stroke_mm=90.0, conrod_mm=145.0, compression_ratio=16.5, ivc_deg=-145.0, evo_deg=125.0),
         fam="ci", speeds=(1000, 1500, 2000, 3000), mans=(1.10, 1.60, 2.30), nf=10, scale=0.05),
    dict(role="hidden", cell="cell_05", seed=5, eps=0.0, gain=0.95, f_ht=1.07, cyl=4,
         eng=dict(bore_mm=130.0, stroke_mm=150.0, conrod_mm=250.0, compression_ratio=17.5, ivc_deg=-150.0, evo_deg=120.0),
         fam="ci", speeds=(800, 1100, 1500, 1900), mans=(1.20, 1.80, 2.50), nf=10, scale=0.05),
    dict(role="hidden", cell="cell_06", seed=6, eps=+1.30, gain=1.05, f_ht=1.02, cyl=6,
         eng=dict(bore_mm=105.0, stroke_mm=125.0, conrod_mm=210.0, compression_ratio=12.5, ivc_deg=-145.0, evo_deg=125.0),
         fam="si", speeds=(1000, 1200, 1500, 1800), mans=(0.80, 1.30, 1.90), nf=10, scale=0.05),
    dict(role="hidden", cell="cell_09", seed=9, eps=-2.40, gain=0.96, f_ht=0.93, cyl=3,
         eng=dict(bore_mm=74.0, stroke_mm=80.0, conrod_mm=132.0, compression_ratio=11.5, ivc_deg=-135.0, evo_deg=128.0),
         fam="si", speeds=(1500, 2500, 4000, 5000), mans=(0.40, 0.90, 1.70), nf=10, scale=0.02),
    dict(role="hidden", cell="cell_12", seed=12, eps=0.0, gain=1.0, f_ht=0.99, cyl=4,
         eng=dict(bore_mm=79.0, stroke_mm=88.0, conrod_mm=140.0, compression_ratio=9.6, ivc_deg=-139.0, evo_deg=131.0),
         fam="si", speeds=(1500, 2200, 3000, 4200), mans=(0.50, 0.85, 1.40), nf=10, scale=0.02),
    dict(role="hidden", cell="cell_14", seed=14, eps=0.0, gain=1.07, f_ht=1.06, cyl=4,
         eng=dict(bore_mm=96.0, stroke_mm=104.0, conrod_mm=165.0, compression_ratio=15.5, ivc_deg=-146.0, evo_deg=124.0),
         fam="ci", speeds=(900, 1400, 2000, 2600), mans=(1.00, 1.50, 2.20), nf=10, scale=0.05),
]
N_FIRED, N_MOTORED = 300, 100
N_EXAMPLE = 150


def points_of(c, rng):
    pts = []
    combos = [(s, m) for s in c["speeds"] for m in c["mans"]]
    pick = rng.choice(len(combos), size=c["nf"], replace=False)
    for i, k in enumerate(sorted(pick)):
        s, m = combos[k]
        pts.append(dict(point="P%02d" % (i + 1), kind="fired", speed_rpm=s, p_man_bar=round(m + 0.01 * rng.integers(-3, 4), 2),
                        t_ivc_K=int(338 + 30 * rng.random()), t_wall_K=int(405 + 12 * m + 20 * rng.random())))
    return pts


def build(c, out):
    rng = np.random.default_rng(1000 + c["seed"])
    eng = c["eng"]
    sub = {"example": "environment/data/examples", "pending": "environment/data/pending", "hidden": "hidden"}[c["role"]]
    d = os.path.join(out, sub, c["cell"])
    os.makedirs(os.path.join(d, "records"), exist_ok=True)
    pts = points_of(c, rng)
    ejson = dict(cell=c["cell"], cylinders=c["cyl"], **eng, bar_per_count=c["scale"])
    json.dump(ejson, open(os.path.join(d, "engine.json"), "w"), indent=1)
    with open(os.path.join(d, "points.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["point", "speed_rpm", "p_man_bar", "t_ivc_K", "t_wall_K", "record"])
        for p in pts:
            w.writerow([p["point"], p["speed_rpm"], "%.2f" % p["p_man_bar"], p["t_ivc_K"], p["t_wall_K"],
                        "records/%s.npy" % p["point"]])
    ncyl = c["cyl"]
    cyl_dth = rng.normal(0, 0.8, ncyl)
    cyl_dq = rng.normal(0, 0.02, ncyl)
    rows = []
    for p in pts:
        fired = p["kind"] == "fired"
        nc = (N_EXAMPLE if c["role"] == "example" else N_FIRED) if fired else N_MOTORED
        speed, pman, tivc, tw = p["speed_rpm"], p["p_man_bar"] * 1e5, float(p["t_ivc_K"]), float(p["t_wall_K"])
        m_ch = pman * ei.volume(eng["ivc_deg"], eng) / (ei.R_GAS * tivc)
        if c["fam"] == "si":
            qspec = 2.25e6 * (0.92 + 0.1 * rng.random())
            th0_0, dur_0, mw_0 = -20 - 4 * rng.random() - 0.002 * (speed - 2000), 46 + 10 * rng.random(), 2.0 + 0.4 * rng.random()
            s_th, s_dur, s_q = 1.4, 0.06, 0.02
        else:
            qspec = 1.0e6 * (0.7 + 0.8 * rng.random())
            th0_0, dur_0, mw_0 = -6 - 3 * rng.random(), 42 + 14 * rng.random(), 1.0 + 0.5 * rng.random()
            s_th, s_dur, s_q = 0.3, 0.03, 0.01
        pexh = (1.05 + 0.25 * max(p["p_man_bar"] - 1.0, 0)) * 1e5
        n = ncyl * nc
        cy_of = np.repeat(np.arange(ncyl), nc)
        if fired:
            q = m_ch * qspec * (1 + cyl_dq[cy_of]) * (1 + s_q * rng.standard_normal(n))
            th0 = th0_0 + cyl_dth[cy_of] + s_th * rng.standard_normal(n)
            dur = dur_0 * (1 + s_dur * rng.standard_normal(n))
            mw = mw_0 * (1 + 0.04 * rng.standard_normal(n))
        else:
            q, th0, dur, mw = np.zeros(n), np.zeros(n), np.ones(n), np.ones(n)
        ptrue = ei.simulate(eng, speed, pman, tivc, tw, q, th0, dur, mw, pexh, c["f_ht"], FINE)
        res = ei.analyse(FINE, ptrue, eng, speed, pman, tivc, tw, fired)
        for cy in range(ncyl):
            rows.append([p["point"], cy + 1] + [("%.4f" % res[k].reshape(ncyl, nc)[cy].mean()) if k in res else "" for k in COLS])
        # what the indicating system stores: samples on the encoder pulses, level arbitrary each cycle
        xs = ENC + c["eps"]
        j = (xs - FINE[0]) / 0.1
        j0 = np.floor(j).astype(int)
        fr = j - j0
        samp = ptrue[:, j0] * (1 - fr) + ptrue[:, j0 + 1] * fr
        # the transducer gives gain times what the indicating system's scale assumes
        meas = c["gain"] * samp * 1e-5 + rng.uniform(-3, 3, (n, 1)) + 0.6 * c["scale"] * rng.standard_normal(samp.shape)
        rec = np.round(meas / c["scale"]).astype(np.int16).reshape(ncyl, nc, 720)
        np.save(os.path.join(d, "records", p["point"] + ".npy"), rec)
    hdr = ["point", "cylinder"] + COLS
    if c["role"] == "example":
        tp = os.path.join(d, "expected.csv")
    else:
        os.makedirs(os.path.join(out, "truth"), exist_ok=True)
        tp = os.path.join(out, "truth", c["cell"] + ".csv")
    with open(tp, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(hdr)
        w.writerows(rows)
    print(c["cell"], c["role"], "points", len(pts), flush=True)


if __name__ == "__main__":
    out = sys.argv[1]
    only = sys.argv[2:]
    for c in CELLS:
        if only and c["cell"] not in only:
            continue
        build(c, out)
