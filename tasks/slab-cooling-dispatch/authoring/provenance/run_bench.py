"""usage: python3 run_bench.py <tag> [margin] [debias] [cop_var] [use_cap] [holidays] [seedset-json]"""
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_sys.path.insert(0, _os.path.join(_HERE, "..", "..", "tests"))
_sys.path.insert(0, _HERE)
import sys, json, time, numpy as np
from world import build
from bench import InfoMatchedMPC
from sim import run
tag = sys.argv[1]
margin = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3
flags = [s == "1" for s in (sys.argv[3:7] if len(sys.argv) > 6 else ["1", "1", "1", "1"])]
seeds = json.loads(sys.argv[7]) if len(sys.argv) > 7 else None
w = build(keep_log=False, seeds=seeds)
c = InfoMatchedMPC(w["plants"], w["ep_hid"], w["fc_hid"], margin=margin, debias=flags[0], cop_var=flags[1],
                   use_cap=flags[2], holidays=flags[3])
tic = time.time()
W, _ = run(w["ep_hid"], c, w["X0_hid"], w["fc_hid"], plants=w["plants"], seed=w["seeds"]["noise_hid"], want_obs=False)
out = {k: v.tolist() for k, v in W.items()}
out.update(sec=time.time() - tic, failures=c.failures, margin=margin, flags=flags)
json.dump(out, open(_os.path.join(_HERE, f"bench_{tag}.json"), "w"))
print(tag, "cost", round(sum(W["cost"]), 3), np.round(W["cost"], 2), "\n  dev W", np.round(W["dev_west"], 2), "E", np.round(W["dev_east"], 2), "fail", c.failures, "%.0fs" % out["sec"])
