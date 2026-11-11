"""Noise-free check of the single-record routes: the latest pumpdown's true gas load, permeation from the seal
table, the rest taken as a constant leak (wall at the table's nominal) or as wall gas, referred to 36 h and 20 C."""
import os
import sys
TASK = os.path.abspath(os.environ.get("TASK", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tasks", "base-pressure-diagnosis")))
sys.path.insert(0, os.path.join(TASK, "tests", "sealed"))
import fleet as F, bpphys as P                                          # noqa: E402
for cid in F.CHAMBER_IDS:
    ch = F.BY[cid]; c = F.config(ch); q36 = F.truth(ch)["q_total"]
    e = sorted(ch["log"])[-1]; date, pid, vent, h, tc, ser, load = e[:7]
    cc = F.config(ch, date)
    if load:
        cc = dict(cc, surfaces=list(cc["surfaces"]) + F.load_surfaces([load], F.FIXTURES))
    T = tc + 273.15
    q = P.q_total(cc, h, vent, T); W = P.q_wall_nominal(cc["surfaces"], h, vent, T); Pm = P.q_perm(cc["seal"], cc["seal_cm"], T)
    w36 = P.q_wall_nominal(c["surfaces"], F.REF_H, "air", P.T_REF); p36 = P.q_perm(c["seal"], c["seal_cm"], P.T_REF)
    leakmode = (q - W - Pm) + w36 + p36
    wallmode = (q - Pm) / W * w36 + p36
    print("%s %-15s latest %s %4.1fh %4.1fC  rest-as-leak %+6.1f%%  rest-as-wall %+6.1f%%" % (
        cid, F.truth(ch)["cause"], pid, h, tc, 100 * (leakmode / q36 - 1), 100 * (wallmode / q36 - 1)))
