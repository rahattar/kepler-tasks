#!/usr/bin/env python3
"""Interface check for a Puller 11 supervisor. NOT the puller, and NOT a grade.

    python3 /app/check_interface.py [path/to/supervisor.py]      (default /app/supervisor.py)

Loads the supervisor the way it will be run: a copy of the file alone in an empty scratch directory, imported by
path in a separate Python process, constructed as Supervisor() with no arguments. Then calls update(meas) once a
minute with the first 600 minutes of a logged HZ-B body (B2411, fast-pull recipe; the crucible setpoint is
replaced by PS-R07's at each length). Observations are replayed from the log whatever the controller returns:
nothing is simulated and nothing about growth rate or diameter is measured.

It reports whether the constructor and update() behave, whether every reply is a pair of finite numbers
(pull rate in mm/min, heater power in kW), whether the controller tried to open files it will not have (it runs
alone in an empty directory, without /app/data), and how long the calls take against the limits (constructor
120 s, step 5 s, 600 s per body).
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = "/app/data" if os.path.isfile("/app/data/logs/B2411_minute.csv") else os.path.join(HERE, "data")
INIT_LIMIT_S, STEP_LIMIT_S, BODY_LIMIT_S = 120.0, 5.0, 600.0
MINUTES = 600

CHILD = r'''
import importlib.util, json, math, os, sys, time
opened = []
base = os.getcwd()
prefixes = tuple(p for p in set(sys.path + [os.path.dirname(os.__file__), sys.prefix, sys.base_prefix]) if p)
def hook(event, args):
    if event == "open" and args and isinstance(args[0], str):
        p = os.path.abspath(args[0])
        if not p.startswith(base) and not p.startswith(prefixes) and not p.startswith(("/dev/", "/proc/", "/sys/", "/etc/")):
            opened.append(p)
sys.addaudithook(hook)
obs_all = json.load(open(sys.argv[2]))
out = {"init_s": None, "steps": 0, "step_max_s": 0.0, "total_s": 0.0, "errors": [], "opened": opened}
t0 = time.time()
try:
    spec = importlib.util.spec_from_file_location("submitted_controller", sys.argv[1])
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    ctl = mod.Supervisor()
except BaseException as e:
    out["errors"].append("constructor/import failed: %s: %s" % (type(e).__name__, e))
    print("RESULT " + json.dumps(out)); sys.exit(0)
out["init_s"] = time.time() - t0
def finite(v):
    return not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(float(v))
for obs in obs_all:
    t1 = time.time()
    try:
        cmd = ctl.update(dict(obs))
    except BaseException as e:
        out["errors"].append("update raised at minute %s: %s: %s" % (obs["time_min"], type(e).__name__, e)); break
    dt = time.time() - t1
    out["step_max_s"] = max(out["step_max_s"], dt)
    def plain(o):
        if callable(getattr(o, "tolist", None)):
            return o.tolist()
        if callable(getattr(o, "item", None)):
            return o.item()
        return o
    try:
        cmd = json.loads(json.dumps(cmd, default=plain))
    except (TypeError, ValueError):
        out["errors"].append("reply at minute %s is not plain numbers: %r" % (obs["time_min"], cmd)); break
    if not isinstance(cmd, (list, tuple)) or len(cmd) != 2 or not all(finite(v) for v in cmd):
        out["errors"].append("invalid reply at minute %s: %r" % (obs["time_min"], cmd)); break
    out["steps"] += 1
out["total_s"] = time.time() - t0
print("RESULT " + json.dumps(out))
'''


def ps_r07_rpm(L):
    rows = list(csv.DictReader(open(os.path.join(DATA, "recipes", "perfect_si_r07.csv"))))
    w = float(rows[0]["crucible_rpm"])
    for r in rows:
        if float(r["length_mm"]) <= L:
            w = float(r["crucible_rpm"])
    return w


def observations():
    out = []
    with open(os.path.join(DATA, "logs", "B2411_minute.csv")) as f:
        for i, r in enumerate(csv.DictReader(f)):
            if i >= MINUTES:
                break
            L = float(r["length_mm"])
            out.append(dict(time_min=float(r["time_min"]), length_mm=L,
                            camera_diameter_mm=float(r["camera_diameter_mm"]),
                            pull_rate_mm_min=float(r["pull_rate_mm_min"]), heater_power_kw=float(r["heater_power_kw"]),
                            pyrometer_c=float(r["pyrometer_c"]), crucible_rpm_set=ps_r07_rpm(L)))
    return out


def main():
    path = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "/app/supervisor.py")
    if not os.path.isfile(path):
        print("FAIL: %s does not exist" % path)
        return 1
    scratch = tempfile.mkdtemp(prefix="check_interface_")
    try:
        ctrl = os.path.join(scratch, "supervisor.py")
        shutil.copyfile(path, ctrl)
        obs_file = os.path.join(scratch, ".obs.json")
        with open(obs_file, "w") as f:
            json.dump(observations(), f)
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": scratch, "TMPDIR": scratch, "LANG": "C.UTF-8",
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        p = subprocess.run([sys.executable, "-I", "-B", "-c", CHILD, ctrl, obs_file], cwd=scratch, env=env,
                           capture_output=True, text=True, timeout=INIT_LIMIT_S + STEP_LIMIT_S * MINUTES + 60)
    except subprocess.TimeoutExpired:
        print("FAIL: the check timed out")
        return 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    res = None
    for line in p.stdout.splitlines():
        if line.startswith("RESULT "):
            res = json.loads(line[7:])
    if res is None:
        print("FAIL: the supervisor process died:\n" + p.stderr[-1500:])
        return 1
    ok = not res["errors"]
    for e in res["errors"]:
        print("FAIL:", e)
    opened = sorted(set(o for o in res["opened"] if not o.endswith(".obs.json")))
    if opened:
        ok = False
        print("FAIL: the supervisor opened files it will not have when run: %s" % ", ".join(opened[:5]))
    if res["init_s"] is not None:
        print("constructor %.2f s (limit %.0f s)" % (res["init_s"], INIT_LIMIT_S))
    print("%d of %d steps answered; slowest step %.3f s (limit %.0f s)" % (res["steps"], MINUTES, res["step_max_s"],
                                                                          STEP_LIMIT_S))
    if res["steps"]:
        per = (res["total_s"] - (res["init_s"] or 0)) / res["steps"]
        est = (res["init_s"] or 0) + per * 2000
        print("estimated controller time for a 1500 mm body (about 2000 steps): %.0f s (limit %.0f s)" % (est, BODY_LIMIT_S))
        if est > BODY_LIMIT_S:
            ok = False
            print("FAIL: too slow for a whole body")
    if res["init_s"] is not None and res["init_s"] > INIT_LIMIT_S:
        ok = False
        print("FAIL: constructor too slow")
    if res["step_max_s"] > STEP_LIMIT_S:
        ok = False
        print("FAIL: a step took longer than the limit")
    print("interface OK" if ok else "interface NOT OK")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
