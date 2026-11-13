#!/usr/bin/env python3
"""Reference for the engine-indicating core: python3 indicate.py PACKAGE_DIR OUT_CSV [--phase model|sheet|phase|gain]"""
import csv, json, os, sys
import numpy as np

R_GAS = 287.0
ENC = -180.0 + 0.5 * np.arange(720)


def volume(th, e):
    B, S, L = e["bore_mm"] * 1e-3, e["stroke_mm"] * 1e-3, e["conrod_mm"] * 1e-3
    a = S / 2
    Vd = np.pi * B * B / 4 * S
    t = np.deg2rad(th)
    return Vd / (e["compression_ratio"] - 1) + np.pi * B * B / 4 * (a * (1 - np.cos(t)) + L - np.sqrt(L * L - (a * np.sin(t)) ** 2))


def gam(T, xb):
    gu = 1.375 - 6.99e-5 * T
    return gu + (1.330 - 4.50e-5 * T - gu) * xb


def setup(e, pt, eps):
    """Geometry and per-step factors for one point at index error eps."""
    th = ENC + eps
    V = volume(th, e)
    B = e["bore_mm"] * 1e-3
    speed = pt["speed"]
    k0 = int(np.searchsorted(th, e["ivc_deg"]))
    k1 = int(np.searchsorted(th, e["evo_deg"], side="right")) - 1
    Vm = 0.5 * (V[k0 + 1:k1 + 1] + V[k0:k1])
    dV = np.diff(V[k0:k1 + 1])
    m = pt["pman"] * volume(e["ivc_deg"], e) / (R_GAS * pt["tivc"])
    sp = 2 * e["stroke_mm"] * 1e-3 * speed / 60
    hfac = 130.0 * Vm ** -0.06 * (sp + 1.4) ** 0.8 * (np.pi * B * B / 2 + 4 * Vm / B) * 0.5 / (6.0 * speed)
    return dict(th=th, V=V, k0=k0, k1=k1, Vm=Vm, dV=dV, mR=m * R_GAS, hfac=hfac, tw=pt["twall"])


def heat_steps(pw, s, xbm):
    """Net and wall heat per step (J) for pressures pw (cycles x window samples, Pa)."""
    pm = 0.5 * (pw[:, 1:] + pw[:, :-1])
    dp = pw[:, 1:] - pw[:, :-1]
    Tm = pm * s["Vm"] / s["mR"]
    g = gam(Tm, xbm)
    dqn = (g * pm * s["dV"] + s["Vm"] * dp) / (g - 1)
    dqw = s["hfac"] * (pm * 1e-5) ** 0.8 * Tm ** -0.4 * (Tm - s["tw"])
    return dqn, dqw


def pegged(rec, scale, pman, gain=1.0):
    p = rec.reshape(-1, 720).astype(np.float64) * (scale * 1e5 / gain)
    p += pman - p[:, :20].mean(axis=1, keepdims=True)
    return p


def rig_state(e, pts, recs, mode):
    """Index error (deg) and transducer gain from the compression strokes: before combustion starts the gross heat
    release of section 7 is nil. Its running sum, weighted by 1/V so that it is of the size of a pressure error,
    is made as small as it can be over the samples from 12 degrees after inlet valve closing to 47 before top
    dead centre."""
    if mode == "sheet":
        return 0.0, 1.0
    means = [pegged(recs[p["point"]], e["bar_per_count"], p["pman"]).reshape(e["cylinders"], -1, 720).mean(axis=1) for p in pts]
    ka = int(np.searchsorted(ENC, e["ivc_deg"] + 12.0))
    kb = int(np.searchsorted(ENC, -47.0))
    B = e["bore_mm"] * 1e-3

    def resid(x):
        eps, gain = x
        V = volume(ENC[ka:kb + 1] + eps, e)
        Vm, dV = 0.5 * (V[1:] + V[:-1]), np.diff(V)
        wgt = 1.0 / V[1:]
        out = []
        for p, mc in zip(pts, means):
            pc = (mc[:, ka:kb + 1] - p["pman"]) / gain + p["pman"]
            pm = 0.5 * (pc[:, 1:] + pc[:, :-1])
            Tm = pm * Vm / (p["pman"] * volume(e["ivc_deg"], e) / p["tivc"])
            g = gam(Tm, 0.0)
            sp = 2 * e["stroke_mm"] * 1e-3 * p["speed"] / 60
            dq = (g * pm * dV + Vm * (pc[:, 1:] - pc[:, :-1])) / (g - 1) + 130.0 * Vm ** -0.06 * (sp + 1.4) ** 0.8 * (
                np.pi * B * B / 2 + 4 * Vm / B) * 0.5 / (6.0 * p["speed"]) * (pm * 1e-5) ** 0.8 * Tm ** -0.4 * (Tm - p["twall"])
            q = np.cumsum(dq, axis=1) * wgt / p["pman"]
            q = q - (q * wgt).sum(axis=1, keepdims=True) / (wgt * wgt).sum() * wgt
            out.append(q.ravel())
        return np.concatenate(out)

    free = {"model": (True, True), "phase": (True, False), "gain": (False, True)}[mode]
    best, x = None, None
    for eps in (np.arange(-4.0, 4.01, 0.5) if free[0] else [0.0]):
        for gain in (np.arange(0.88, 1.121, 0.03) if free[1] else [1.0]):
            r = resid((eps, gain))
            c = float(r @ r)
            if best is None or c < best:
                best, x = c, np.array([eps, gain])
    idx = [i for i in (0, 1) if free[i]]
    step = (1e-3, 1e-4)
    for _ in range(12):
        r0 = resid(x)
        J = np.empty((len(r0), len(idx)))
        for j, i in enumerate(idx):
            xp = x.copy()
            xp[i] += step[i]
            J[:, j] = (resid(xp) - r0) / step[i]
        d = np.linalg.lstsq(J, -r0, rcond=None)[0]
        x[idx] += d
        if np.max(np.abs(d) / np.array(step)[idx]) < 1.0:
            break
    return float(x[0]), float(x[1])


def analyse(e, pt, rec, eps, gain):
    p = pegged(rec, e["bar_per_count"], pt["pman"], gain)
    s = setup(e, pt, eps)
    th, V = s["th"], s["V"]
    Vd = np.pi * (e["bore_mm"] * 1e-3) ** 2 / 4 * e["stroke_mm"] * 1e-3
    imep = (0.5 * (p[:, 1:] + p[:, :-1]) @ np.diff(V)) / Vd * 1e-5
    kmax = np.clip(np.argmax(p, axis=1), 10, 709)
    x = np.arange(-10, 11) * 0.5
    X = np.stack([np.ones_like(x), x, x * x], axis=1)
    y = np.take_along_axis(p, kmax[:, None] + np.arange(-10, 11)[None, :], axis=1)
    c = y @ np.linalg.pinv(X).T
    xv = -c[:, 1] / (2 * c[:, 2])
    out = [imep, (c[:, 0] + c[:, 1] * xv + c[:, 2] * xv * xv) * 1e-5, th[kmax] + xv]
    pw = p[:, s["k0"]:s["k1"] + 1]
    thw = th[s["k0"]:s["k1"] + 1]
    xbm = np.zeros((p.shape[0], pw.shape[1] - 1))
    qend = None
    for _ in range(20):
        dqn, dqw = heat_steps(pw, s, xbm)
        Q = np.cumsum(dqn + dqw, axis=1)
        new = Q[:, -1]
        fr = np.clip(Q / new[:, None], 0.0, 1.0)
        xbm = np.concatenate([0.5 * fr[:, :1], 0.5 * (fr[:, 1:] + fr[:, :-1])], axis=1)
        if qend is not None and np.max(np.abs(new - qend) / np.abs(new)) < 1e-6:
            break
        qend = new
    frac = np.concatenate([np.zeros((len(Q), 1)), Q / Q[:, -1:]], axis=1)
    r = np.arange(len(Q))
    for level in (0.1, 0.5):
        k = np.clip(np.argmax(frac >= level, axis=1), 1, frac.shape[1] - 1)
        f0, f1 = frac[r, k - 1], frac[r, k]
        out.append(thw[k - 1] + (level - f0) / (f1 - f0) * 0.5)
    out.append(Q[:, -1])
    return out


def main():
    pkg, dst = sys.argv[1], sys.argv[2]
    mode = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--phase" else "model"
    e = json.load(open(os.path.join(pkg, "engine.json")))
    pts = []
    for r in csv.DictReader(open(os.path.join(pkg, "points.csv"))):
        pts.append(dict(point=r["point"], speed=float(r["speed_rpm"]), pman=float(r["p_man_bar"]) * 1e5,
                        tivc=float(r["t_ivc_K"]), twall=float(r["t_wall_K"]), record=r["record"]))
    recs = {p["point"]: np.load(os.path.join(pkg, p["record"])) for p in pts}
    eps, gain = rig_state(e, pts, recs, mode)
    sys.stderr.write("index %.3f deg, gain %.4f\n" % (eps, gain))
    with open(dst, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["point", "cylinder", "imep_bar", "pmax_bar", "apmax_deg", "ca10_deg", "ca50_deg", "q_gross_J"])
        for p in pts:
            res = analyse(e, p, recs[p["point"]], eps, gain)
            n = e["cylinders"]
            for cy in range(n):
                vals = ["%.4f" % v.reshape(n, -1)[cy].mean() for v in res]
                w.writerow([p["point"], cy + 1] + vals)


if __name__ == "__main__":
    main()
