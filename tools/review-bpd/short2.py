import sys, math
import os
TASK = os.path.abspath(os.environ.get("TASK", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tasks", "base-pressure-diagnosis")))
sys.dont_write_bytecode = True
C = TASK
sys.path.insert(0, C + "/solution"); sys.path.insert(0, C + "/tests/sealed")
import diagnose as D, fleet as F
data = D.load_data(C + "/environment/data"); certs = data["certs"]; fix = D.crossed_serials(data, certs)
TR = {c: F.truth(F.BY[c]) for c in F.CHAMBER_IDS}
for cid in F.CHAMBER_IDS:
    cfg, pts, s = D.front_end(cid, data, certs, fix, None)
    t = TR[cid]; mat, cm = D.seal_at(cfg, D.AUDIT); qp20 = D.q_perm(mat, cm, D.T_REF)
    w36 = D.q_wall_nominal(cfg["surfaces"], 36.0, "air", D.T_REF)
    out = []
    for p in sorted(pts, key=lambda p: p["date"]):
        W = D.nominal_wall(cfg, p); Pm = D.perm_of(cfg, p)
        for mode in ("leak", "wall"):
            corr = 1.0
            for _ in range(40):
                q = p["p_n2"] * corr * s; rest = max(q - (W if mode == "leak" else 0) - Pm, 0)
                parts = {"wall-outgassing": W if mode == "leak" else rest, "permeation": Pm, "air-leak": rest if mode == "leak" else 0}
                corr = D.gas_correction(parts, D.seal_at(cfg, p["date"])[0])
            q = p["p_n2"] * corr * s
            if mode == "leak":
                leak = q - W - Pm; P36 = {"wall-outgassing": w36, "permeation": qp20, "air-leak": leak}
            else:
                c_w = (q - Pm) / W; P36 = {"wall-outgassing": c_w * w36, "permeation": qp20, "air-leak": 0.0}
            q36 = sum(P36.values()); cause = max(P36, key=P36.get)
            ok = abs(q36 / t["q_total"] - 1) <= 0.04 and (cause == t["cause"] or t["cause"] == "pump-speed")
            out.append("%s/%s:%+.1f%%%s%s" % (p["pd"], mode[0], 100 * (q36 / t["q_total"] - 1), "" if cause == t["cause"] else "(" + cause[:4] + ")", "*" if ok else ""))
    print(cid, t["cause"][:9], " ".join(out))
