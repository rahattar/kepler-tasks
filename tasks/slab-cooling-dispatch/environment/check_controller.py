#!/usr/bin/env python3
"""Interface check for a TABS group controller. NOT the plant, and NOT a grade.

    python3 /app/check_controller.py [path/to/controller.py]      (default /app/controller.py)

Loads the controller the way the grader does - a copy of the file alone in an empty scratch
directory, imported by path in a separate Python process with only the standard library, numpy
and scipy importable, constructed as Controller() with no arguments - and calls step(obs) once
per 15-minute step over the last two logged days of the trend log, with the forecast issue that
was current at each step taken from the forecast archive. Observations are replayed from the log
whatever the controller returns: nothing is simulated and nothing about cost or comfort is
measured.

It reports whether the constructor and step() behave, whether every command is valid, whether
the controller tried to open files it will not have when graded (it then runs alone in an empty
scratch directory, without /app/data or anything else from /app), and how long the calls take
against the grader's limits.

A valid command is a dict {"supply_temp_c": x, "valve_duty": {"west": a, "east": b}} with x, a
and b finite real numbers (booleans are not numbers). Duties are clipped to [0, 1] and the
setpoint to the chiller's 15-22 C range when graded.
"""
import csv
import datetime as dt
import json
import math
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = "/app/data" if os.path.isdir("/app/data") else os.path.join(HERE, "data")
ZONES = ("west", "east")
INIT_LIMIT_S = 600.0
STEP_LIMIT_S = 10.0
BUDGET_S = 7200.0                # controller wall time over the graded run, init included
GRADED_STEPS = 56 * 96
TS_MIN, TS_MAX = 15.0, 22.0

HOST = r'''
import importlib.util, json, os, sys, traceback
pin = os.fdopen(os.dup(0), "r", buffering=1)
pout = os.fdopen(os.dup(1), "w", buffering=1)
os.dup2(os.open(os.devnull, os.O_RDONLY), 0)
os.dup2(2, 1)
sys.stdin = open(os.devnull)
sys.stdout = sys.stderr
HERE = os.path.dirname(os.path.realpath(sys.argv[1]))
ALLOWED = set(sys.stdlib_module_names) | {"numpy", "scipy"}

class Guard:
    def find_spec(self, name, path=None, target=None):
        top = name.partition(".")[0]
        # _sysconfigdata_* is the standard library's platform-named build data (sysconfig
        # loads it, and scipy calls sysconfig on import); it is not in stdlib_module_names
        if top not in ALLOWED and not top.startswith("_sysconfigdata"):
            raise ModuleNotFoundError("No module named %r here: only the standard library, "
                                      "numpy and scipy are available when the controller "
                                      "is graded" % top)
        return None

sys.meta_path.insert(0, Guard())
KEEP = tuple(sorted({os.path.realpath(p) for p in (sys.prefix, sys.base_prefix,
                                                  sys.exec_prefix)}
                    | {"/proc", "/sys", "/dev", HERE}))
foreign = []

def audit(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.path.realpath(os.fsdecode(args[0]))
        if not p.startswith(KEEP) and p not in foreign:
            foreign.append(p)

sys.addaudithook(audit)

def plain(o):
    item = getattr(o, "item", None)
    if callable(item):
        return item()
    raise TypeError("%r is not JSON-serialisable" % (o,))

def send(o):
    o["opened"] = foreign[:5]
    pout.write(json.dumps(o) + "\n")
    pout.flush()

try:
    spec = importlib.util.spec_from_file_location("submitted_controller", sys.argv[1])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cls = mod.Controller
except BaseException:
    send({"ok": False, "error": "import failed: " + traceback.format_exc(limit=3)[-600:]})
    sys.exit(0)
ctrl = None
for line in pin:
    m = json.loads(line)
    if m["op"] == "exit":
        break
    try:
        if m["op"] == "init":
            ctrl = cls()
            send({"ok": True})
        else:
            cmd = ctrl.step(m["obs"])
            try:
                payload = json.loads(json.dumps(cmd, default=plain))
            except (TypeError, ValueError):
                send({"ok": False, "error": "step returned something that is not "
                                            "JSON-serialisable: %r" % (cmd,)})
                continue
            send({"ok": True, "command": payload})
    except BaseException:
        send({"ok": False, "error": traceback.format_exc(limit=3)[-600:]})
'''


def observations():
    """The last two logged days as the grader would send them (values measured at the end of
    an interval are the observation at the start of the next)."""
    with open(os.path.join(DATA, "trend_log.csv")) as f:
        rows = list(csv.DictReader(f))
    fc = {}
    with open(os.path.join(DATA, "forecast_archive.csv")) as f:
        for r in csv.DictReader(f):
            fc.setdefault(r["issued"], []).append(r)
    rows = rows[-193:]
    out = []
    for prev, r in zip(rows[:-1], rows[1:]):
        t = dt.datetime.fromisoformat(r["time"])
        iss = t.replace(hour=(t.hour // 6) * 6, minute=0).strftime("%Y-%m-%dT%H:%M")
        f = fc[iss]
        out.append({
            "time": r["time"], "outdoor_temp_c": float(r["outdoor_temp_c"]),
            "facade_irradiance_w_m2": {"west": float(prev["facade_irradiance_west_w_m2"]),
                                       "east": float(prev["facade_irradiance_east_w_m2"])},
            "supply_temp_c": float(prev["supply_temp_c"]),
            "supply_setpoint_c": float(prev["supply_setpoint_c"]),
            "zones": {z: {"air_temp_c": float(r[f"{z}_air_temp_c"]),
                          "slab_temp_c": float(r[f"{z}_slab_temp_c"]),
                          "return_temp_c": float(prev[f"{z}_return_temp_c"]),
                          "valve_duty": float(prev[f"{z}_valve_command"])} for z in ZONES},
            "forecast": {"issued": iss, "step_minutes": 15,
                         "outdoor_temp_c": [float(x["outdoor_temp_c"]) for x in f],
                         "facade_irradiance_w_m2": {
                             "west": [float(x["facade_irradiance_west_w_m2"]) for x in f],
                             "east": [float(x["facade_irradiance_east_w_m2"]) for x in f]}}})
    return out


def _finite_real(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    try:
        return math.isfinite(float(v))
    except OverflowError:
        return False


def validate(cmd):
    """The grader's rules. Returns (error or None, list of clipping notes)."""
    if not isinstance(cmd, dict):
        return "step must return a dict, got %r" % (cmd,), []
    if "supply_temp_c" not in cmd:
        return "command has no 'supply_temp_c': %r" % (cmd,), []
    sp = cmd["supply_temp_c"]
    if not _finite_real(sp):
        return "'supply_temp_c' must be a finite number, got %r" % (sp,), []
    if "valve_duty" not in cmd:
        return "command has no 'valve_duty': %r" % (cmd,), []
    vd = cmd["valve_duty"]
    if not isinstance(vd, dict):
        return "'valve_duty' must be a dict with 'west' and 'east', got %r" % (vd,), []
    notes = []
    if not TS_MIN <= sp <= TS_MAX:
        notes.append("setpoint")
    for z in ZONES:
        if z not in vd:
            return "'valve_duty' has no %r: %r" % (z, vd), []
        if not _finite_real(vd[z]):
            return "'valve_duty'[%r] must be a finite number, got %r" % (z, vd[z]), []
        if not 0.0 <= vd[z] <= 1.0:
            notes.append("duty")
    return None, notes


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/app/controller.py"
    if not os.path.isfile(path):
        print("no controller at %s" % path)
        return 1
    obs = observations()
    problems, opened = [], []
    tmp = tempfile.mkdtemp(prefix="check_")
    proc = None
    try:
        host = os.path.join(tmp, "host.py")
        ctrl = os.path.join(tmp, "controller.py")
        with open(host, "w") as f:
            f.write(HOST)
        shutil.copyfile(path, ctrl)
        work = os.path.join(tmp, "tmp")
        os.mkdir(work)
        proc = subprocess.Popen([sys.executable, "-I", "-B", host, ctrl],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=None, text=True, bufsize=1, cwd=work,
                                env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": work,
                                     "TMPDIR": work, "LANG": "C.UTF-8", "PYTHONHASHSEED": "0",
                                     "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                                     "MKL_NUM_THREADS": "1"})
        q = queue.Queue()

        def pump(stream, out):
            for line in stream:
                out.put(line)
            out.put(None)
        threading.Thread(target=pump, args=(proc.stdout, q), daemon=True).start()

        def call(msg, limit):
            t0 = time.monotonic()
            try:
                proc.stdin.write(json.dumps(msg) + "\n")
                proc.stdin.flush()
            except OSError:
                return None, time.monotonic() - t0, "controller process is gone"
            try:
                line = q.get(timeout=limit)
            except queue.Empty:
                return None, time.monotonic() - t0, "no answer within %.0f s (the grader's limit)" % limit
            el = time.monotonic() - t0
            if line is None:
                return None, el, "controller process exited"
            try:
                rep = json.loads(line)
            except ValueError:
                return None, el, "malformed reply on the protocol pipe"
            for p in rep.get("opened", []):
                if p not in opened:
                    opened.append(p)
            if not rep.get("ok"):
                return None, el, "raised: " + str(rep.get("error", ""))[-600:]
            return rep, el, None

        rep, t_init, err = call({"op": "init"}, INIT_LIMIT_S)
        steps, t_steps, t_max, clip = 0, 0.0, 0.0, {"setpoint": 0, "duty": 0}
        if err:
            print("Controller() failed after %.2f s (limit %.0f s)" % (t_init, INIT_LIMIT_S))
            problems.append("Controller(): %s" % err)
        else:
            print("constructed in %.2f s (limit %.0f s)" % (t_init, INIT_LIMIT_S))
            for o in obs:
                rep, el, err = call({"op": "step", "obs": o}, STEP_LIMIT_S)
                t_max = max(t_max, el)
                if err:
                    problems.append("step at %s: %s" % (o["time"], err))
                    break
                bad, notes = validate(rep.get("command"))
                if bad:
                    problems.append("step at %s: %s" % (o["time"], bad))
                    break
                for k in notes:
                    clip[k] += 1
                t_steps += el
                steps += 1
        if steps or t_max:
            print("%d of %d steps answered with valid commands; slowest call %.2f s (limit %.0f s)"
                  % (steps, len(obs), t_max, STEP_LIMIT_S))
        if steps == len(obs):
            mean = t_steps / steps
            proj = t_init + mean * GRADED_STEPS
            print("mean step %.3f s: at this pace the %d graded steps take about %.0f s of "
                  "controller time, init included (budget %.0f s)"
                  % (mean, GRADED_STEPS, proj, BUDGET_S))
            if proj > BUDGET_S:
                problems.append("projected controller time %.0f s exceeds the %.0f s budget"
                                % (proj, BUDGET_S))
            if clip["setpoint"]:
                print("note: %d setpoints outside %.0f-%.0f C; the chiller clips them"
                      % (clip["setpoint"], TS_MIN, TS_MAX))
            if clip["duty"]:
                print("note: %d valve duties outside [0, 1]; the grader clips them" % clip["duty"])
        print("note: archived forecasts end with the log, so late issues here are shorter than "
              "the 216 values the grader sends")
    finally:
        if proc is not None:
            try:
                proc.stdin.write(json.dumps({"op": "exit"}) + "\n")
                proc.stdin.flush()
            except (OSError, ValueError):
                pass
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)
    for p in opened:
        problems.append("the controller opened %s; when graded it runs alone in an empty scratch "
                        "directory, without /app/data or anything else from /app" % p)
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  " + p)
        return 1
    print("interface OK (this says nothing about cost or comfort on the graded weeks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
