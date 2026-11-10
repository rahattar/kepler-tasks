#!/usr/bin/env python3
"""Interface check for a chill-station controller. NOT the station physics.

    python3 /app/check_controller.py [path/to/controller.py]

Loads the controller the way the grader does - a copy of the file alone in an empty
scratch directory, imported by path in a separate Python process, with only the standard
library, numpy and scipy importable - and drives it for a few simulated wafers against a
crude two-node STAND-IN plant. It reports whether the constructor and step() behave,
whether every command is valid, whether the controller tried to read files it will not
have when graded, and how long the calls take against the grader's time limits.

The stand-in plant exists only to exercise the interface. Its temperatures, cycle times
and limits mean nothing about the real stations, and tuning against it is pointless.
"""
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

INIT_LIMIT_S = 20.0
STEP_LIMIT_S = 1.0
WAFER_LIMIT_S = 60.0
CTRL_DT = 0.1
P_MIN, P_MAX = 3.0, 60.0

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
        if top not in ALLOWED:
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
    send({"ok": False, "error": traceback.format_exc(limit=3)[-600:]})
    sys.exit(0)
ctrl = None
for line in pin:
    m = json.loads(line)
    if m["op"] == "exit":
        break
    try:
        if m["op"] == "init":
            ctrl = cls(m["station"], m["wafer"])
            send({"ok": True})
        else:
            cmd = ctrl.step(m["t"], m["reading"])
            send({"ok": True, "command": json.loads(json.dumps(cmd, default=plain))})
    except BaseException:
        send({"ok": False, "error": traceback.format_exc(limit=3)[-600:]})
'''


class StandIn:
    """Two lumped nodes and a lagged pressure. Invented numbers, not the station."""

    def __init__(self, T0, setpoint, k_in, k_out):
        self.Ti = self.To = T0
        self.Tp = setpoint
        self.P = 3.0
        self.k_in, self.k_out = k_in, k_out

    def advance(self, P_cmd, dt):
        for _ in range(10):
            self.P += (P_cmd - self.P) * (dt / 10) / 0.25
            g = self.P / (self.P + 12.0)
            self.Ti += -(self.Ti - self.Tp) * self.k_in * g * dt / 10
            self.To += -(self.To - self.Tp) * self.k_out * g * dt / 10

    def reading(self):
        return {"center_C": round(self.Ti, 4), "edge_C": round(self.To, 4),
                "plate_C": round(self.Tp, 4), "pressure_torr": round(self.P, 4)}


def run_one(path, st, film, T0, kin, kout, problems, opened):
    tmp = tempfile.mkdtemp(prefix="check_")
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
                                     "TMPDIR": work, "LANG": "C.UTF-8",
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
                return None, time.monotonic() - t0, "no answer within %.1f s" % limit
            if line is None:
                return None, time.monotonic() - t0, "controller process exited"
            rep = json.loads(line)
            for p in rep.get("opened", []):
                if p not in opened:
                    opened.append(p)
            if not rep.get("ok"):
                return None, time.monotonic() - t0, "raised: " + rep.get("error", "")[-400:]
            return rep, time.monotonic() - t0, None

        plant = StandIn(T0, st["plate_setpoint_C"], kin, kout)
        rep, dt, err = call({"op": "init", "station": st, "wafer": {"film": film}},
                            INIT_LIMIT_S)
        worst_init, worst_step = dt, 0.0
        used, released, t = dt, False, 0.0
        if err:
            problems.append("init (%s, %s): %s" % (st["station"], film, err))
        else:
            for k in range(300):
                t = round(k * CTRL_DT, 6)
                rep, dt, err = call({"op": "step", "t": t, "reading": plant.reading()},
                                    STEP_LIMIT_S)
                used += dt
                worst_step = max(worst_step, dt)
                if err:
                    problems.append("step at t=%.1f: %s" % (t, err))
                    break
                cmd = rep["command"]
                if not isinstance(cmd, dict):
                    problems.append("step returned %r, not a dict" % (cmd,))
                    break
                rel = cmd.get("release", False)
                if not isinstance(rel, bool):
                    problems.append("'release' must be true or false, got %r" % (rel,))
                    break
                if rel:
                    released = True
                    break
                P = cmd.get("pressure_torr")
                if isinstance(P, bool) or not isinstance(P, (int, float)) \
                        or not math.isfinite(P) or not (P_MIN <= P <= P_MAX):
                    problems.append("invalid pressure_torr %r at t=%.1f" % (P, t))
                    break
                plant.advance(float(P), CTRL_DT)
            if used > WAFER_LIMIT_S:
                problems.append("used %.1f s of controller time on one wafer (limit %.0f s)"
                                % (used, WAFER_LIMIT_S))
        try:
            proc.stdin.write(json.dumps({"op": "exit"}) + "\n")
            proc.stdin.flush()
        except OSError:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("stand-in wafer %s/%s: %s at t = %.1f s, controller time %.2f s"
              % (st["station"], film, "released" if released else "not released", t, used))
        return worst_init, worst_step
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/app/controller.py"
    if not os.path.isfile(path):
        print("no controller at %s" % path)
        return 1
    with open(os.path.join(os.environ.get("CHILL_DATA", "/data"), "stations.json")) as f:
        stations = json.load(f)["stations"]
    problems, opened = [], []
    worst_init = worst_step = 0.0
    trials = [(stations[0], "bare", 250.0, 0.55, 0.40),
              (stations[-1], "oxide", 240.0, 0.70, 0.45),
              (stations[0], "nitride", 262.0, 0.45, 0.35)]
    for st, film, T0, kin, kout in trials:
        wi, ws = run_one(path, st, film, T0, kin, kout, problems, opened)
        worst_init, worst_step = max(worst_init, wi), max(worst_step, ws)
    for p in opened:
        problems.append("the controller opened %s; when graded it runs alone in an empty "
                        "scratch directory, without /data or anything else from /app" % p)
    print("slowest constructor %.3f s (limit %.0f s), slowest step %.3f s (limit %.1f s)"
          % (worst_init, INIT_LIMIT_S, worst_step, STEP_LIMIT_S))
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  " + p)
        return 1
    print("interface OK (this says nothing about how the controller does on the real stations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
