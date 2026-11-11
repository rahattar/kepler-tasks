import sys, math, os
import numpy as np
import os
TASK = os.path.abspath(os.environ.get("TASK", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tasks", "base-pressure-diagnosis")))
sys.dont_write_bytecode = True
C = TASK
sys.path.insert(0, C + "/solution"); sys.path.insert(0, C + "/tests/sealed")
import diagnose as D, fleet as F, bpphys as P
data = D.load_data(C + "/environment/data"); certs = data["certs"]; fix = D.crossed_serials(data, certs)
vac = None
TR = {c: F.truth(F.BY[c]) for c in F.CHAMBER_IDS}
def pct(a, b): return 100 * (a / b - 1)
print("chamber  truth: cause  q36   | routes: q36 error %")
for cid in F.CHAMBER_IDS:
    cfg, pts, s = D.front_end(cid, data, certs, fix, vac)
    t = TR[cid]
    mat, cm = D.seal_at(cfg, D.AUDIT)
    qp20 = D.q_perm(mat, cm, D.T_REF)
    w36 = D.q_wall_nominal(cfg["surfaces"], 36.0, "air", D.T_REF)
    res = {}
    # q of each point with a gas correction from (wall nominal, perm, rest)
    def qpt(p, c_w=1.0):
        W = c_w * D.nominal_wall(cfg, p); Pm = D.perm_of(cfg, p)
        corr = 1.0
        for _ in range(30):
            q = p["p_n2"] * corr * s
            rest = max(q - W - Pm, 0)
            corr = D.gas_correction({"wall-outgassing": W, "permeation": Pm, "air-leak": rest}, D.seal_at(cfg, p["date"])[0])
        return p["p_n2"] * corr * s, W, Pm
    last = max(pts, key=lambda p: p["date"])
    # R1: one record (latest), wall at table nominal (C_w = 1), perm computed, rest = leak
    q, W, Pm = qpt(last, 1.0)
    res["1rec,Cw=1"] = (q - W - Pm) + w36 + qp20
    # R2: one record, no wall at all: rest constant
    q, W, Pm = qpt(last, 0.0)
    res["1rec,nowall"] = (q - Pm) + qp20
    # R3: empirical log-law fit  ln q = a + b ln t + c/T over pts (no mechanisms), gas corr assumed by R1 model
    if len(set(p["t_h"] for p in pts)) >= 2 and len(pts) >= 3:
        Q = np.array([qpt(p, 1.0)[0] for p in pts]); H = np.array([p["t_h"] for p in pts]); T = np.array([p["t_k"] for p in pts])
        A = np.column_stack([np.ones_like(H), np.log(H), 1 / T]); x, *_ = np.linalg.lstsq(A, np.log(Q), rcond=None)
        res["loglaw"] = math.exp(x[0] + x[1] * math.log(36.0) + x[2] / D.T_REF)
    # R4: wall + perm(computed) + leak, no trapped volume (the reference without its virtual-leak branch)
    if len(set(p["t_h"] for p in pts)) >= 2:
        c_w, q_l, _qv, _ss, _q = D.fit_split(cfg, pts, s)
        res["wall+perm+leak"] = c_w * w36 + qp20 + max(q_l, 0)
    print("%s %-15s %.3e | " % (cid, t["cause"], t["q_total"]) + "  ".join("%s %+6.1f" % (k, pct(v, t["q_total"])) for k, v in res.items()),
          "| n=%d last=%s %sh %.1fC" % (len(pts), last["date"], last["t_h"], last["t_k"] - 273.15))
