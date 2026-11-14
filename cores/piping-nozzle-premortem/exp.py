import numpy as np
from line1 import build, STATES, node_at, xyz
line = build()
SUP_NODES = {s["node"] for s in line.sup}
# survey targets: 10 nodes spread along the line, at least 2 nodes from any support or anchor
cand = [i for i in range(3, line.n - 3) if all(abs(i - k) >= 2 for k in SUP_NODES)]
TGT = [cand[int(round(q))] for q in np.linspace(0, len(cand) - 1, 10)]
def run(ov=None):
    out = {}
    uc, Lc, act = line.solve(*STATES["cold"], override=ov)
    out["cold"] = (uc, Lc)
    for st in ["hot_60", "hot_80", "hot_100", "design"]:
        u, L, act = line.solve(*STATES[st], state=act, override=ov)
        out[st] = (u, L)
    return out
def survey(res, st):
    u = res[st][0].reshape(-1, 6)[:, :3]
    return u[TGT]
base = run()
def compare(name, ov):
    r = run(ov)
    line_ = "%-22s" % name
    for st in ["cold", "hot_100", "design"]:
        dL = r[st][1] - base[st][1]
        line_ += " %s dF %5.1f kN dM %6.1f kNm |" % (st[:4], np.abs(dL[:3]).max() / 1e3, np.abs(dL[3:]).max() / 1e3)
    dS = [np.abs(survey(r, st) - survey(base, st)).max() * 1e3 for st in ["cold", "hot_60", "hot_100"]]
    print(line_, " survey dmax mm cold/60/100: %.1f %.1f %.1f" % tuple(dS))
    return r
if __name__ == "__main__":
    print("base", {st: np.round(base[st][1] / 1e3, 1).tolist() for st in ["cold", "hot_100", "design"]})
    for s in line.sup:
        if s["kind"] == "spring":
            print(s["name"], "hot %.1f kN travel %+.1f mm rate %.0f kN/m cold %.1f kN" % (s["hot_load"]/1e3, s["travel"]*1e3, s["rate"]/1e3, s["cold_load"]/1e3))
    for s in line.sup:
        if s["kind"] == "spring":
            n = s["name"]
            compare("locked " + n, {n: dict(kind="locked")})
            compare("rate x2 " + n, {n: dict(rate=2 * s["rate"])})
            compare("rate /2 " + n, {n: dict(rate=0.5 * s["rate"])})
            compare("cold load +15%% " + n, {n: dict(dload=0.15 * s["cold_load"])})
    compare("R1 settled 10 mm", {"R1": dict(set=-0.010)})
    for g in ["G1", "G2"]:
        for side in ["plus", "minus"]:
            compare(g + " gap_" + side + " 0", {g: {"gap_" + side: 0.0}})
            compare(g + " gap_" + side + " 20mm", {g: {"gap_" + side: 0.020}})
