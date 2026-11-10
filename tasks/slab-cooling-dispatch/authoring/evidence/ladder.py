"""The ladder: what each piece of the solution is worth, on the shipped graded weeks.

  python3 ladder.py exact      # benchmark ablations: exact models and states, one capability removed
  python3 ladder.py agent      # the reference (fitted from the public data) and variants of it
  python3 ladder.py rules      # model-free sequences a BMS would run
Each part prints a table; ladder.txt holds the recorded output. Gate: total cost <= 1.15 x benchmark,
at most 1 of 16 zone-weeks above 0.5 K h. The exact part takes about 40 min, the agent part about
45 min on 2 CPUs, the rules part about 2 min.
"""
import os, sys, json, subprocess, tempfile
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C


def exact():
    rows = [("benchmark (margin 0.3 K)", "0.3", "1 1 1 1"), ("margin 0", "0.0", "1 1 1 1"),
            ("forecast used as issued", "0.3", "0 1 1 1"), ("COP taken at 16 C (efficiency ignored)", "0.3", "1 0 1 1"),
            ("chiller capacity ignored", "0.3", "1 1 0 1"), ("Labor Day treated as a working day", "0.3", "1 1 1 0"),
            ("all four ignored", "0.3", "0 0 0 0")]
    base = sum(C.shipped_bench())
    print(f"{'exact models and states; removed':42s} {'total $':>8s} {'ratio':>6s} {'zone-weeks > 0.5 K h':>21s}")
    for name, m, flags in rows:
        tag = "abl%d" % abs(hash(name))
        subprocess.run([sys.executable, os.path.join(C.PROV, "run_bench.py"), tag, m] + flags.split(),
                       check=True, stdout=subprocess.DEVNULL)
        r = json.load(open(os.path.join(C.PROV, f"bench_{tag}.json")))
        os.remove(os.path.join(C.PROV, f"bench_{tag}.json"))
        fails = sum(d > 0.5 for z in ("west", "east") for d in r[f"dev_{z}"])
        print(f"{name:42s} {sum(r['cost']):8.3f} {sum(r['cost']) / base:6.3f} {fails:21d}", flush=True)


def _agent_one(args):
    name, path = args
    return name, C.grade_inprocess(path, C.shipped_bench())


def agent():
    d = tempfile.mkdtemp()
    ref = C.fit_reference(os.path.join(C.ROOT, "environment", "data"), os.path.join(d, "ref.py"))
    V = [("reference as shipped (margins 0.2 / 0.2 K)", ref),
         ("margins 0.3 / 0.3 K", C.variant(ref, os.path.join(d, "m3.py"), margin_hi=0.3, margin_lo=0.3)),
         ("margins 0 / 0 K", C.variant(ref, os.path.join(d, "m0.py"), margin_hi=0.0, margin_lo=0.0)),
         ("forecast used as issued", C.variant(ref, os.path.join(d, "nd.py"), debias=False)),
         ("COP taken at 16 C (efficiency ignored)", C.variant(ref, os.path.join(d, "fc.py"), cop_var=False)),
         ("chiller capacity ignored", C.variant(ref, os.path.join(d, "nc.py"), use_cap=False)),
         ("Labor Day treated as a working day", C.variant(ref, os.path.join(d, "nh.py"), holidays=False)),
         ("all four ignored, margins 0.3 K", C.variant(ref, os.path.join(d, "nv.py"), margin_hi=0.3, margin_lo=0.3,
                                                      debias=False, cop_var=False, use_cap=False, holidays=False))]
    print(f"{'fitted from the public data':42s} {'ratio':>6s} {'fails':>5s} {'worst K h':>9s} {'gate':>5s}")
    with ProcessPoolExecutor(2) as ex:
        for name, r in ex.map(_agent_one, V):
            print(f"{name:42s} {r['ratio']:6.3f} {r['fails']:5d} {r['worst_dev']:9.2f} {'pass' if r['passed'] else 'fail':>5s}",
                  flush=True)


def rules():
    import numpy as np
    from world import build
    from sim import run, SPD
    w = build(keep_log=False)
    base = sum(C.shipped_bench())

    class Reset:
        def __init__(self, a, b, on=None, off=None):
            self.a, self.b, self.on, self.off, self.h = a, b, on, off, []

        def __call__(self, o, t, X):
            self.h.append(o["outdoor_temp_c"]); self.h = self.h[-SPD:]
            sp = float(np.clip(self.a - self.b * (np.mean(self.h) - 18), 15, 22))
            hr = (t % SPD) / 4
            d = 1.0 if self.on is None or (hr >= self.on or hr < self.off) else 0.0
            return sp, {"west": d, "east": d}

    class Reactive:
        def __init__(self, sp):
            self.sp = sp

        def __call__(self, o, t, X):
            return 17.0, {z: float(np.clip(o["zones"][z]["air_temp_c"] - self.sp + 0.5, 0, 1)) for z in ("west", "east")}

    cands = [("outdoor reset 24 h, a=%g b=%g" % (a, b), Reset(a, b)) for a in (20, 21, 22, 23) for b in (0.3, 0.6)]
    cands += [("night only %02d-07 h, a=%g" % (on, a), Reset(a, 0.5, on, 7)) for a in (18, 19, 20, 21) for on in (18, 20, 22)]
    cands += [("reactive on air, %g C" % sp, Reactive(sp)) for sp in (22.5, 23.0, 23.5, 24.0)]
    rows = []
    for name, c in cands:
        W, _ = run(w["ep_hid"], c, w["X0_hid"], w["fc_hid"], plants=w["plants"], seed=w["seeds"]["noise_hid"])
        fails = int(sum((W[f"dev_{z}"] > 0.5).sum() for z in ("west", "east")))
        rows.append((name, float(W["cost"].sum()) / base, fails))
    rows.sort(key=lambda r: (r[2] > 1, r[1]))
    print(f"{'model-free sequence (all 24 tried)':42s} {'ratio':>6s} {'fails':>5s} {'gate':>5s}")
    for name, ratio, fails in rows:
        print(f"{name:42s} {ratio:6.3f} {fails:5d} {'pass' if fails <= 1 and ratio <= 1.15 else 'fail':>5s}")


if __name__ == "__main__":
    {"exact": exact, "agent": agent, "rules": rules}[sys.argv[1]]()
