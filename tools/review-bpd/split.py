import sys, math, itertools
import numpy as np
import os
TASK = os.path.abspath(os.environ.get("TASK", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tasks", "base-pressure-diagnosis")))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(TASK, "authoring/provenance"))
import fleet as F, bpphys as P
from scipy.optimize import least_squares

def entries(ch):
    """unique pumpdowns since the last config change (true q, noise-free)"""
    seen = {}
    for e in ch["log"]:
        key = (e[0], e[1])
        if key in seen: continue
        seen[key] = e
    return list(seen.values())

def last_change(ch):
    ds = [d for d, k, a in ch["events"] if k in ("internals", "seal", "seal_len", "trap", "leak", "trapped", "pump")]
    return max(ds) if ds else "0000"

for ch in F.FLEET:
    cid = ch["id"]
    tr = F.truth(ch)
    c = F.config(ch)
    comp36 = P.components(c, F.REF_H, "air", P.T_REF)
    comp16 = P.components(c, 16.0, "air", P.T_REF)
    q36 = tr["q_total"]; q16 = sum(comp16.values())
    lc = last_change(ch)
    E = [e for e in entries(ch) if e[0] >= lc]
    rows = []
    for e in E:
        date, pid, vent, h, tc, ser, load = e[:7]
        cc = F.config(ch, date)
        if load: cc = dict(cc, surfaces=list(cc["surfaces"]) + F.load_surfaces([load], F.FIXTURES))
        qt = P.q_total(cc, h, vent, tc + 273.15)
        wshape = P.q_wall_nominal(cc["surfaces"], h, vent, tc + 273.15)
        rows.append((h, tc + 273.15, qt, wshape, P.theta_p(tc + 273.15), cc))
    w36 = P.q_wall_nominal(c["surfaces"], F.REF_H, "air", P.T_REF)
    # naive: latest entry's q as is
    naive = rows[-1][2] if rows else float("nan")
    fams = {}
    H = np.array([r[0] for r in rows]); Q = np.array([r[2] for r in rows]); W = np.array([r[3] for r in rows]); TP = np.array([r[4] for r in rows])
    def fit(cols):
        A = np.column_stack(cols); x, *_ = np.linalg.lstsq(A / Q[:, None], np.ones_like(Q), rcond=None); r = A @ x / Q - 1
        return x, np.max(np.abs(r)) if len(Q) else 0
    if len(rows) >= 2:
        x, r = fit([W, np.ones_like(Q)]); fams["wall+leak"] = (x[0]*w36 + x[1], r)
        x, r = fit([W, TP]); fams["wall+perm"] = (x[0]*w36 + x[1], r)
        best = None
        for tau in [2,4,6,9,12,16,24,32,40,48]:
            x, r = fit([W, np.exp(-H/tau)]); v = x[0]*w36 + x[1]*math.exp(-36/tau)
            if best is None or r < best[1]: best = (v, r, tau)
        fams["wall+virt(best tau)"] = best[:2]
    if len(rows) >= 3:
        x, r = fit([W, np.ones_like(Q), TP]); fams["wall+leak+perm"] = (x[0]*w36 + x[1] + x[2], r)
    dom = max(comp36, key=comp36.get)
    print("%s cause=%-15s q36=%.3e  q16/q36=%+.1f%%  latest-entry/q36=%+.1f%%  n=%d  shares36=%s" % (
        cid, tr["cause"], q36, 100*(q16/q36-1), 100*(naive/q36-1), len(rows),
        " ".join("%s:%.2f" % (k[:4], v/q36) for k, v in comp36.items())))
    for k, (v, r) in fams.items():
        print("     %-22s q36 err %+6.1f%%   max fit resid %.2f%%" % (k, 100*(v/q36-1), 100*r))
