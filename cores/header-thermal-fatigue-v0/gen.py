"""Builds the core: two example headers with results, one pending header without, six hidden headers.

Condition: the fluid temperature of a header comes from its thermocouple. On the examples it is a bare-tip
thermocouple (time constant about 2 s); on the pending header and on four hidden headers it sits in a heavy
thermowell (25 to 120 s), so the record smooths every fast transient. Nothing lists the instrument. The
outer-surface thermocouple (fast, used by HF-3 for nothing but the wall's starting temperature) shows it:
the wall's outer surface moves sooner than the conduction model allows from the recorded fluid temperature.
Hidden shift: lags beyond the pending header's, more and sharper quenches, hot restarts, a thicker wall.
python3 gen.py
"""
import csv, json, os, shutil
import numpy as np
import hf

HERE = os.path.dirname(os.path.abspath(__file__))


def smooth_noise(rng, n, sd, corr):
    a = np.exp(-1.0 / corr)
    e = rng.normal(0, sd * np.sqrt(1 - a * a), n)
    return hf.lfilter([1.0], [1.0, -a], e)


def ramp(t, t0, t1, v0, v1):
    return v0 + (v1 - v0) * np.clip((t - t0) / max(t1 - t0, 1e-9), 0, 1)


def event(kind, rng, T_op, P_op):
    """True fluid temperature (C) and pressure (bar) at 1 s for one event."""
    if kind == "cold start":
        T0 = rng.uniform(140, 220); r1 = rng.uniform(1.5, 3.0) / 60; r2 = rng.uniform(2.0, 4.0) / 60
        Tm = rng.uniform(300, 340)
        t1 = 300 + (Tm - T0) / r1; t2 = t1 + 600; t3 = t2 + (T_op - Tm) / r2; L = int(t3 + 600)
        t = np.arange(L, dtype=float)
        T = ramp(t, 300, t1, T0, Tm) + ramp(t, t2, t3, 0, T_op - Tm)
        P = P_op * np.clip((T - T0) / (T_op - T0), 0, 1) ** 1.3 + 5
    elif kind == "hot restart":
        T0 = rng.uniform(440, 500); dip = rng.uniform(30, 60); td = rng.uniform(50, 110)
        r = rng.uniform(5.0, 8.0) / 60
        t1 = 200 + td; t2 = t1 + 120; t3 = t2 + (T_op - (T0 - dip)) / r; L = int(t3 + 500)
        t = np.arange(L, dtype=float)
        T = T0 - ramp(t, 200, t1, 0, dip) + ramp(t, t2, t3, 0, T_op - T0 + dip)
        P = 0.75 * P_op + ramp(t, t2, t3, 0, 0.25 * P_op)
    elif kind == "shutdown":
        r = rng.uniform(2.0, 4.0) / 60; T1 = rng.uniform(360, 400)
        t1 = 300 + (T_op - T1) / r; L = int(t1 + 600)
        t = np.arange(L, dtype=float)
        T = ramp(t, 300, t1, T_op, T1)
        P = ramp(t, 300, t1, P_op, 0.5 * P_op)
    elif kind == "quench":
        dT = rng.uniform(40, 90); td = rng.uniform(30, 90); hold = rng.uniform(60, 180); tr = rng.uniform(200, 400)
        t1 = 300 + td; t2 = t1 + hold; t3 = t2 + tr; L = int(t3 + 600)
        t = np.arange(L, dtype=float)
        T = T_op - ramp(t, 300, t1, 0, dT) + ramp(t, t2, t3, 0, dT)
        P = np.full(L, P_op)
    else:                                                                # load swings
        A = rng.uniform(10, 22); per = rng.uniform(240, 420); k = rng.integers(3, 6)
        L = int(300 + k * per + 600)
        t = np.arange(L, dtype=float)
        ph = np.clip((t - 300) / per, 0, k)
        T = T_op - A * (1 - np.cos(2 * np.pi * ph)) / 2
        P = P_op - 0.06 * P_op * (1 - np.cos(2 * np.pi * ph)) / 2
    # process corners are not sharp: the profile passes a critically damped 8 s second-order lag
    a = np.exp(-1.0 / 8.0)
    for _ in range(2):
        T = hf.lfilter([1 - a], [1, -a], T - T[0]) + T[0]
    T = T + smooth_noise(rng, len(T), 0.4, 20.0)
    return T, P


def build(spec, out, kind):
    rng = np.random.default_rng(spec["seed"])
    hdr = {"header": spec["tag"], "inner_radius_mm": spec["ri"], "wall_mm": spec["s"],
           "material": {"grade": spec["grade"], "diffusivity_mm2_s": spec["a"], "E_MPa": spec["E"],
                        "alpha_per_K": spec["alpha"], "poisson": 0.3},
           "k_pressure": spec["kp"], "k_thermal": spec["kt"],
           "sn_curve": {"N_ref": 1.0e4, "range_ref_MPa": 500.0, "m": 3.0, "cutoff_MPa": 60.0}}
    wall = hf.Wall(spec["ri"], spec["ri"] + spec["s"], spec["a"], 300)
    rows, res = [], []
    true_fluid = []
    kinds = rng.choice(list(spec["mix"].keys()), size=spec["events"], p=np.array(list(spec["mix"].values())) / sum(spec["mix"].values()))
    for e, k in enumerate(kinds, 1):
        T, P = event(k, rng, spec["T_op"], spec["P_op"])
        dT, To = wall.response(T)
        true_fluid.append(T)
        rec = hf.lag(T, spec["tau"]) + rng.normal(0, 0.03, len(T))
        outer = hf.lag(To, 0.8) + rng.normal(0, 0.03, len(T))
        P_rec = P + rng.normal(0, 0.05, len(T))
        sig = hf.stress(hdr, dT, P)
        cyc = hf.rainflow(sig)
        res.append((e, max(r for r, _ in cyc), hf.damage(hdr, cyc), k))
        for i in range(len(T)):
            rows.append("%d,%d,%.1f,%.1f,%.1f\n" % (e, i, rec[i], P_rec[i], outer[i]))
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    json.dump(hdr, open(os.path.join(out, "header.json"), "w"), indent=1)
    with open(os.path.join(out, "record.csv"), "w") as f:
        f.write("event,t_s,fluid_C,pressure_bar,outer_C\n"); f.write("".join(rows))
    np.save(os.path.join(HERE, "core", "debug", spec["tag"] + "_fluid.npy"), np.concatenate(true_fluid))
    if kind != "pending":
        with open(os.path.join(out, "truth.csv" if kind == "hidden" else "expected.csv"), "w") as f:
            f.write("event,range_max_MPa,damage\n")
            for e, r, d, _ in res:
                f.write("%d,%.2f,%.4e\n" % (e, r, d))
    D = sum(d for _, _, d, _ in res)
    print(spec["tag"], "tau", spec["tau"], "events", len(res), "rows", len(rows), "D %.3e" % D,
          "max range %.0f" % max(r for _, r, _, _ in res), flush=True)
    return res


MIX = {"cold start": 2, "hot restart": 2, "shutdown": 3, "quench": 2, "load swing": 3}
P91 = dict(grade="X10CrMoVNb9-1", a=7.6, E=191000.0, alpha=12.6e-6)
BASE = dict(P91, T_op=540.0, P_op=170.0, events=24, mix=MIX)
SPECS = {
    "examples": [dict(BASE, tag="HD-A", seed=1, ri=150.0, s=55.0, kp=2.2, kt=1.6, tau=0.8),
                 dict(BASE, tag="HD-B", seed=2, ri=120.0, s=45.0, kp=2.4, kt=1.8, tau=0.8, T_op=520.0, P_op=150.0)],
    "pending": [dict(BASE, tag="HD-P", seed=3, ri=170.0, s=60.0, kp=2.1, kt=1.7, tau=45.0)],
    "hidden": [
        dict(BASE, tag="HX-1", seed=11, ri=160.0, s=60.0, kp=2.3, kt=1.6, tau=70.0,
             shift="a 70 s thermowell (pending: 45 s)"),
        dict(BASE, tag="HX-2", seed=12, ri=140.0, s=50.0, kp=2.2, kt=1.7, tau=0.8, mix=dict(MIX, quench=5),
             shift="bare tip; quenches more than twice as frequent"),
        dict(BASE, tag="HX-3", seed=13, ri=180.0, s=80.0, kp=2.0, kt=1.5, tau=110.0,
             shift="a 110 s thermowell on an 80 mm wall (examples 45 to 55 mm)"),
        dict(BASE, tag="HX-4", seed=14, ri=130.0, s=48.0, kp=2.5, kt=1.9, tau=28.0, mix=dict(MIX, **{"hot restart": 5}),
             shift="a 28 s thermowell; hot restarts dominate"),
        dict(BASE, tag="HX-5", seed=15, ri=155.0, s=58.0, kp=2.2, kt=1.6, tau=0.8, T_op=565.0, P_op=180.0,
             shift="bare tip; 565 C, 180 bar (examples to 540 C, 170 bar)"),
        dict(BASE, tag="HX-6", seed=16, ri=165.0, s=62.0, kp=2.1, kt=1.7, tau=55.0, mix=dict(MIX, quench=4),
             shift="a 55 s thermowell; frequent quenches"),
    ],
}

if __name__ == "__main__":
    man = {}
    for kind, sub in (("examples", "core/data/examples"), ("pending", "core/data/pending"), ("hidden", "core/hidden")):
        for spec in SPECS[kind]:
            build(spec, os.path.join(HERE, sub, spec["tag"]), {"examples": "example"}.get(kind, kind))
            if kind == "hidden":
                man[spec["tag"]] = {"shift": spec["shift"], "tau_s": spec["tau"]}
    json.dump(man, open(os.path.join(HERE, "core", "manifest.json"), "w"), indent=1)
