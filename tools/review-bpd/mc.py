import sys, math
import numpy as np
from scipy.optimize import least_squares
import os
TASK = os.path.abspath(os.environ.get("TASK", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tasks", "base-pressure-diagnosis")))
sys.path.insert(0, os.path.join(TASK, "tests/sealed")); import fleet as F, bpphys as P
rng = np.random.default_rng(7)
NOISE = 0.006
def kept(ch):
    lc = max([d for d, k, a in ch["events"] if k in ("internals", "seal", "trap", "trapped", "pump")] or ["0"])
    seen = {}
    for e in ch["log"]:
        if e[0] >= lc and (e[0], e[1]) not in seen: seen[(e[0], e[1])] = e
    return list(seen.values())
for cid in F.CHAMBER_IDS:
    ch = F.BY[cid]; c = F.config(ch); q36 = F.truth(ch)["q_total"]
    E = kept(ch)
    rows = []
    for e in E:
        date, pid, vent, h, tc, ser, load = e[:7]
        cc = F.config(ch, date)
        if load: cc = dict(cc, surfaces=list(cc["surfaces"]) + F.load_surfaces([load], F.FIXTURES))
        T = tc + 273.15
        rows.append((h, P.q_total(cc, h, vent, T), P.q_wall_nominal(cc["surfaces"], h, vent, T), P.q_perm(cc["seal"], cc["seal_cm"], T)))
    H = np.array([r[0] for r in rows]); Q = np.array([r[1] for r in rows]); W = np.array([r[2] for r in rows]); PM = np.array([r[3] for r in rows])
    w36 = P.q_wall_nominal(c["surfaces"], 36.0, "air", P.T_REF); p36 = P.q_perm(c["seal"], c["seal_cm"], P.T_REF)
    virt = c["qv0"] > 0
    if len(set(H)) < 2: print(cid, "single pumping time: q36 not identifiable from the log"); continue
    est = []
    for _ in range(400):
        Qn = Q * np.exp(rng.normal(0, NOISE, len(Q)))
        y = Qn - PM
        if not virt:
            A = np.column_stack([W, np.ones_like(W)]); x, *_ = np.linalg.lstsq(A / Qn[:, None], y / Qn, rcond=None)
            est.append(x[0] * w36 + max(x[1], 0) + p36)
        else:
            def res(t): cw, ql, qv, lt = t; return (cw * W + ql + qv * np.exp(-H / math.exp(lt)) - y) / Qn
            f = least_squares(res, [c["wall_factor"], c["leak"], c["qv0"], math.log(c["tau"])],
                              bounds=([0, 0, 0, math.log(0.5)], [10, 1e-2, 1e-1, math.log(48)]))
            cw, ql, qv, lt = f.x; est.append(cw * w36 + ql + qv * math.exp(-36 / math.exp(lt)) + p36)
    e = np.array(est) / q36 - 1
    print("%s %s n=%d times=%s  q36 MC (0.6%% read noise, exact model, true speed): sd %.1f%%, 95%% range %+.1f..%+.1f%%, P(|err|<=4%%)=%.2f" % (
        cid, "4-param" if virt else "2-param", len(H), sorted(set(H)), 100 * e.std(), 100 * np.percentile(e, 2.5), 100 * np.percentile(e, 97.5), np.mean(np.abs(e) <= 0.04)))
