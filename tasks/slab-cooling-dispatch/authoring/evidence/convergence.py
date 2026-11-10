"""Discretisation study: rebuild the world with a finer slab (N cells) and finer sub-steps, recompute the
benchmark and grade the reference on it.

  python3 convergence.py 12 15 shipped     # the plant as shipped
  python3 convergence.py 24 30 fine        # twice the slab cells, half the sub-step
convergence.txt holds the recorded results."""
import os, sys, json, time, tempfile, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C
N, NSUB, tag = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
import zone
for p in (zone.WEST, zone.EAST, zone.PAR):
    p["N"] = N
import sim
sim.NSUB = NSUB; sim.DTS = sim.DT / NSUB
from world import build
from bench import InfoMatchedMPC
w = build(keep_log=False)
tic = time.time()
c = InfoMatchedMPC(w["plants"], w["ep_hid"], w["fc_hid"], margin=0.3)
W, _ = sim.run(w["ep_hid"], c, w["X0_hid"], w["fc_hid"], plants=w["plants"], seed=w["seeds"]["noise_hid"], want_obs=False)
bench_total = float(W["cost"].sum())
import importlib.util
ref = C.fit_reference(os.path.join(C.ROOT, "environment", "data"), os.path.join(tempfile.mkdtemp(), "ref.py"))
spec = importlib.util.spec_from_file_location("ref", ref); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
ctrl = m.Controller()
def f(obs, t, X):
    out = ctrl.step(obs); return out["supply_temp_c"], out["valve_duty"]
Wr, _ = sim.run(w["ep_hid"], f, w["X0_hid"], w["fc_hid"], plants=w["plants"], seed=w["seeds"]["noise_hid"])
res = dict(N=N, NSUB=NSUB, bench_total=bench_total, ref_total=float(Wr["cost"].sum()),
           ratio=float(Wr["cost"].sum()) / bench_total,
           ref_dev_max=max(float(Wr["dev_west"].max()), float(Wr["dev_east"].max())),
           bench_dev_max=max(float(W["dev_west"].max()), float(W["dev_east"].max())), sec=time.time() - tic)
json.dump(res, open(os.path.join(HERE, f"convergence_{tag}.json"), "w"))
print(res)
