#!/usr/bin/env python3
"""Reference for the conveyor core: python3 drives.py LINE_DIR OUT_CSV
The load on a flight is the feed carried along it, so the mass in each section is a difference of running sums
taken against belt travel; the belt speed and the drives' shares then come for all steps at once. Each drive
pulley's diameter is taken from what the surveys show of belt speed against shaft speed, unless
TRUST_REGISTER=1."""
import csv, json, os, sys
import numpy as np

G = 9.80665; N0 = 1500.0
TRUST = os.environ.get("TRUST_REGISTER") == "1"


def rd(d, name):
    return list(csv.DictReader(open(os.path.join(d, name))))


def tensions(fl, F, Rr):
    Ttu = fl["T_tu"]; base = Ttu + Rr - fl["m_belt"] * G * fl["rise"]
    Fh1 = F.get("head1", 0.0); Fh2 = F.get("head2", 0.0); Ft = F.get("tail", 0.0)
    ent = {"head1": Ttu + Fh2 + Fh1, "head2": Ttu + Fh2, "tail": base + 0 * Fh1}
    ext = {"head1": Ttu + Fh2, "head2": Ttu + 0 * Fh1, "tail": base - Ft}
    return ent, ext, base - Ft


def solve(fl, Ftot, Rr, v):
    dr = fl["drives"]
    F = {d["role"]: 0.0 * Ftot for d in dr}
    for _ in range(6):
        ent, ext, Tw = tensions(fl, F, Rr)
        a = [(1 + ent[d["role"]] / fl["EA"]) / d["v0"] for d in dr]
        v = (sum(d["k"] for d in dr) - Ftot) / sum(d["k"] * ai for d, ai in zip(dr, a))
        F = {d["role"]: d["k"] * (1 - v * ai) for d, ai in zip(dr, a)}
    ent, ext, Tw = tensions(fl, F, Rr)
    return v, F, ent, ext, Tw


def calibrate(fl, camps):
    """Rated slip of each drive, pulley diameters as the surveys show them, and the friction factor."""
    L = fl["length"]; H = fl["rise"]
    for d in fl["drives"]:
        s = [(1 - c["rpm"][d["role"]] / N0) * d["P_rated"] / c["kW"][d["role"]] for c in camps if abs(c["kW"][d["role"]]) > 0.08 * d["P_rated"]]
        d["s_rated"] = float(np.mean(s)); d["D"] = d["D_reg"]
    f = 0.02
    for _ in range(8):
        fs = []; Dm = {d["role"]: [] for d in fl["drives"]}
        for c in camps:
            F = {}
            for d in fl["drives"]:
                v0 = np.pi * d["D"] * 1e-3 * N0 / (60 * d["ratio"])
                F[d["role"]] = d["eta"] * c["kW"][d["role"]] * 1e3 / v0
            Rr = fl["C"] * f * G * L * (fl["m_belt"] + fl["m_idler_return"])
            ent, ext, Tw = tensions(fl, F, Rr)
            v = c["vw"] / (1 + Tw / fl["EA"])
            q = c["q"] / 3.6; mL = q / v
            fs.append((sum(F.values()) - G * mL * H - q * v) / (fl["C"] * G * (L * (2 * fl["m_belt"] + fl["m_idler_carry"] + fl["m_idler_return"]) + mL * L)))
            for d in fl["drives"]:
                Dm[d["role"]].append(60 * d["ratio"] * v * (1 + ent[d["role"]] / fl["EA"]) / (np.pi * c["rpm"][d["role"]]) * 1e3)
        f = float(np.mean(fs))
        for d in fl["drives"]:
            meas = float(np.mean(Dm[d["role"]]))
            d["D_meas"] = meas
            if not TRUST and abs(meas / d["D_reg"] - 1) > 0.003:
                d["D"] = meas
    fl["f"] = f
    for d in fl["drives"]:
        d["v0"] = np.pi * d["D"] * 1e-3 * N0 / (60 * d["ratio"])
        d["k"] = d["eta"] * d["P_rated"] * 1e3 / (d["s_rated"] * d["v0"])


def run(fl, feed, dt):
    n = feed.size; L = fl["length"]; q = feed / 3.6
    edges = np.concatenate([[0.0], np.cumsum([s[0] for s in fl["sections"]])])
    sin = np.array([s[1] / s[0] for s in fl["sections"]])
    Mc = np.concatenate([[0.0], np.cumsum(q * dt)])
    v = np.full(n, 0.97 * fl["drives"][0]["v0"])
    Cf = fl["C"] * fl["f"]
    Rr = Cf * G * L * (fl["m_belt"] + fl["m_idler_return"])
    for _ in range(3):
        xi = np.concatenate([[0.0], np.cumsum(v * dt)])
        m_at = np.interp(xi[:-1, None] - edges[None, :], xi, Mc, left=0.0)
        m_sec = m_at[:, :-1] - m_at[:, 1:]
        Rc = Cf * G * (L * (fl["m_belt"] + fl["m_idler_carry"]) + m_sec.sum(1)) + G * (m_sec @ sin) + q * np.concatenate([[v[0]], v[:-1]])
        v, F, ent, ext, Tw = solve(fl, Rc + Rr, Rr, v)
    xi = np.concatenate([[0.0], np.cumsum(v * dt)])
    gone = np.interp(xi - L, xi, Mc, left=0.0)
    out = np.diff(gone) / dt * 3.6
    P = {d["role"]: F[d["role"]] * d["v0"] / d["eta"] / 1e3 for d in fl["drives"]}
    TR = {d["role"]: np.maximum(ent[d["role"]], ext[d["role"]]) / np.minimum(ent[d["role"]], ext[d["role"]]) for d in fl["drives"]}
    return P, TR, out


def main(line_dir, out_csv):
    line = json.load(open(os.path.join(line_dir, "line.json")))
    dt = line["step_s"]; per = line["interval_steps"]
    fls = {}
    for r in rd(line_dir, "flights.csv"):
        fls[r["flight"]] = dict(m_belt=float(r["belt_kg_m"]), m_idler_carry=float(r["idlers_carry_kg_m"]), m_idler_return=float(r["idlers_return_kg_m"]),
                                C=float(r["secondary_factor"]), EA=float(r["belt_stiffness_MN"]) * 1e6, T_tu=float(r["take_up_tension_kN"]) * 1e3,
                                sections=[], drives=[])
    for r in sorted(rd(line_dir, "profile.csv"), key=lambda r: (r["flight"], int(r["section"]))):
        fls[r["flight"]]["sections"].append((float(r["length_m"]), float(r["rise_m"])))
    for r in rd(line_dir, "drives.csv"):
        fls[r["flight"]]["drives"].append(dict(role=r["drive"], P_rated=float(r["rated_kW"]), ratio=float(r["gear_ratio"]),
                                               D_reg=float(r["pulley_diameter_mm"]), eta=float(r["efficiency"])))
    camps = {}
    for r in rd(line_dir, "surveys.csv"):
        c = camps.setdefault(r["flight"], {}).setdefault(r["campaign"], dict(q=float(r["feed_t_h"]), vw=float(r["belt_speed_m_s"]), rpm={}, kW={}))
        c["rpm"][r["drive"]] = float(r["input_rpm"]); c["kW"][r["drive"]] = float(r["motor_kW"])
    feed = np.array([float(r["feed_t_h"]) for r in rd(line_dir, "feed.csv")])
    rows = []
    for name in line["flights"]:
        fl = fls[name]
        fl["length"] = sum(s[0] for s in fl["sections"]); fl["rise"] = sum(s[1] for s in fl["sections"])
        calibrate(fl, list(camps[name].values()))
        if os.environ.get("VERBOSE"):
            print(name, "f %.4f" % fl["f"], [(d["role"], "s_r %.4f" % d["s_rated"], "D reg %.1f meas %.1f used %.1f" % (d["D_reg"], d["D_meas"], d["D"])) for d in fl["drives"]], file=sys.stderr)
        P, TR, feed = run(fl, feed, dt)
        nint = feed.size // per
        for d in fl["drives"]:
            p = P[d["role"]][:nint * per].reshape(nint, per); tr = TR[d["role"]][:nint * per].reshape(nint, per)
            for i in range(nint):
                rows.append(["%s-%s-%03d" % (name, d["role"], i + 1), "%.3f" % p[i].mean(), "%.3f" % p[i].max(), "%.3f" % p[i].min(), "%.5f" % tr[i].max()])
    with open(out_csv, "w", newline="") as f:
        x = csv.writer(f); x.writerow(["row", "mean_kW", "max_kW", "min_kW", "traction_peak"]); x.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
