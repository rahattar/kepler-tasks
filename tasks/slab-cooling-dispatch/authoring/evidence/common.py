"""Shared helpers for the evidence scripts: an in-process grader that applies exactly the gate of
tests/grade.py (the sandboxed verifier reproduces its per-week numbers bit for bit; the sandbox only
adds isolation), and helpers to fit the reference and write variants of it."""
import importlib.util, json, os, subprocess, sys, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TESTS = os.path.join(ROOT, "tests")
SOL = os.path.join(ROOT, "solution")
PROV = os.path.join(ROOT, "authoring", "provenance")
for p in (TESTS, PROV):
    if p not in sys.path:
        sys.path.insert(0, p)

ALLOW, DEV_MAX, FAILS_OK = 1.15, 0.5, 1
BASE_SEEDS = dict(occ_log=11, occ_hid=12, fc_log=21, fc_hid=22, noise_log=31, noise_hid=32, wx=41)


def reseed(j):
    return {k: v + 100 * j for k, v in BASE_SEEDS.items()}


def load_controller(path):
    spec = importlib.util.spec_from_file_location("ctrl_%d" % abs(hash(path)), path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.Controller()


def grade_inprocess(path, bench_cost, seeds=None):
    from world import build
    from sim import run
    from instance import ZONES
    w = build(keep_log=False, seeds=seeds)
    ctrl = load_controller(path)

    def f(obs, t, X):
        out = ctrl.step(obs)
        return float(out["supply_temp_c"]), {z: float(out["valve_duty"][z]) for z in ZONES}

    W, _ = run(w["ep_hid"], f, w["X0_hid"], w["fc_hid"], plants=w["plants"], seed=w["seeds"]["noise_hid"])
    dev = {z: W[f"dev_{z}"] for z in ZONES}
    fails = int(sum((dev[z] > DEV_MAX).sum() for z in ZONES))
    ratio = float(W["cost"].sum()) / float(np.sum(bench_cost))
    return dict(ratio=ratio, fails=fails, week_cost=W["cost"].tolist(),
                worst_dev=max(float(dev[z].max()) for z in ZONES),
                passed=bool(fails <= FAILS_OK and ratio <= ALLOW))


def fit_reference(data_dir, out_path):
    env = dict(os.environ, TABS_DATA=data_dir, OUT=out_path)
    subprocess.run([sys.executable, os.path.join(SOL, "fit.py")], env=env, check=True,
                   stdout=subprocess.DEVNULL)
    return out_path


def variant(fitted_path, out_path, **kw):
    """Copy of a fitted controller with PARAMS entries overridden (margins, ablation switches)."""
    src = open(fitted_path).read()
    head, rest = src.split("PARAMS = ", 1)
    line, tail = rest.split("\n", 1)
    import ast
    P = ast.literal_eval(line)
    P.update(kw)
    open(out_path, "w").write(head + "PARAMS = " + repr(P) + "\n" + tail)
    return out_path


def shipped_bench():
    return json.load(open(os.path.join(TESTS, "bench.json")))["cost"]
