import sys, math, csv
import numpy as np
from scipy.optimize import least_squares
import os
TASK = os.path.abspath(os.environ.get("TASK", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tasks", "base-pressure-diagnosis")))
sys.path.insert(0, os.path.join(TASK, "tests/sealed")); import fleet as F, bpphys as P
log = list(csv.DictReader(open(os.path.join(TASK, "environment/data/base_pressure_log.csv"))))
def ideal(cid, pool_pump):
    ch = F.BY[cid]; c = F.config(ch); q36 = F.truth(ch)["q_total"]
    kinds = ("internals", "seal", "trap", "trapped") + (() if pool_pump else ("pump",))
    lc = max([d for d, k, a in ch["events"] if k in kinds] or ["0"])
    rows = []
    for e in ch["log"]:
        date, pid, vent, h, tc, ser, load = e[:7]
        if date < lc: continue
        actual = e[7] if len(e) > 7 else ser
        r = [x for x in log if x["chamber"] == cid and x["date"] == date and x["gauge"] == ser][0]
        cc = F.config(ch, date)
        if load: cc = dict(cc, surfaces=list(cc["surfaces"]) + F.load_surfaces([load], F.FIXTURES))
        T = tc + 273.15
        # ideal reading correction: true certificate, true drift and true wrong-cert factors, true gas composition
        ind = float(r["reading_mbar"]) * F.cert_factor(actual, date) * F.drift_factor(ch, actual, date) * F.cert_wrong_factor(ch, actual)
        k = P.indicated(cc, h, vent, T) / P.p_base(cc, P.q_total(cc, h, vent, T))     # indicated / true
        p_true = ind / k
        S = P.s_eff(cc, p_true)
        rows.append((date, pid, h, p_true * S, P.q_wall_nominal(cc["surfaces"], h, vent, T), P.q_perm(cc["seal"], cc["seal_cm"], T)))
    uniq = {}
    for r in rows: uniq.setdefault((r[0], r[1]), []).append(r)
    rows = [v[0] for v in uniq.values()]     # one per pumpdown (first gauge listed)
    H = np.array([r[2] for r in rows]); Q = np.array([r[3] for r in rows]); W = np.array([r[4] for r in rows]); PM = np.array([r[5] for r in rows])
    w36 = P.q_wall_nominal(c["surfaces"], 36.0, "air", P.T_REF); p36 = P.q_perm(c["seal"], c["seal_cm"], P.T_REF)
    y = Q - PM
    if c["qv0"] > 0:
        def res(t): cw, ql, qv, lt = t; return (cw * W + ql + qv * np.exp(-H / math.exp(lt)) - y) / Q
        f = least_squares(res, [1, 1e-5, 1e-4, math.log(20)], bounds=([0, 0, 0, math.log(0.5)], [10, 1e-2, 1e-1, math.log(48)]))
        cw, ql, qv, lt = f.x; est = cw * w36 + ql + qv * math.exp(-36 / math.exp(lt)) + p36
        extra = " tau=%.1f (true %.0f)" % (math.exp(lt), c["tau"])
    else:
        A = np.column_stack([W, np.ones_like(W)]); x, *_ = np.linalg.lstsq(A / Q[:, None], y / Q, rcond=None)
        est = x[0] * w36 + max(x[1], 0) + p36; extra = " C_w=%.2f (true %.2f) leak=%.2e (true %.2e)" % (x[0], c["wall_factor"], x[1], c["leak"])
    print("%s pool_pump=%s n=%d: ideal-method q36 error on the SHIPPED readings %+.1f%%%s" % (cid, pool_pump, len(rows), 100 * (est / q36 - 1), extra))
for cid in ("VC07", "VC09", "VC10"):
    ideal(cid, False)
    if cid != "VC07": ideal(cid, True)
