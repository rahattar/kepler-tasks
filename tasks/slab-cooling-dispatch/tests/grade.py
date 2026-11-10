"""Closed-loop grading of a submitted controller for the two-zone TABS group.

The sealed world (world.py) is rebuilt here from its fixed seeds: the warm-up and trend-log period
under the building's existing sequence, then the eight graded weeks (2017-07-15 to 2017-09-08)
with their own weather, occupancy, forecasts and sensor noise. The submitted controller runs in
ONE sandboxed process for the whole graded period (see host.py), so it keeps its state across all
5376 fifteen-minute steps. At each step it receives the observation sim.py builds (sensors, last
commands, the latest forecast issue) and returns a chiller leaving-temperature setpoint and a
valve duty per zone; sim.py applies them to the sealed plant. True states, the weather to come
and the graded quantities are never sent to it.

A step reply is valid when "supply_temp_c" is a finite real number and "valve_duty" is a dict
whose "west" and "east" entries are finite real numbers (booleans are not numbers here). Duties
are clipped to [0, 1]; the setpoint is clipped to the chiller's 15-22 C range by the plant. A
missing key, a non-finite value, a wrong type, an exception in the controller, a reply slower
than STEP_TIMEOUT_S, or running past the total controller time BUDGET_S (init included) stops the
run with an error, and the reward is 0.

GATE (the same as the in-process grader in authoring/evidence/common.py):
REWARD = 1 iff the run finished without error, at most FAILS_OK of the 16 zone-weeks have an
occupied operative-temperature exceedance outside 21-26 C above DEV_MAX K h, and the total
cooling cost over the eight weeks is at most ALLOW x the benchmark's total (bench.json, written
by run_bench.py from the sealed generator; not from any reference solution).

ISOLATION. The controller process runs as the unprivileged user 'nobody' with resource limits,
in a scratch directory holding only a copy of the controller and of host.py, talking over
private pipes. The sealed modules, the benchmark and the logs are not readable or writable by
that user. When the run ends every process the user owns is killed, and everything it left in a
world-writable directory or as a System V IPC object is removed.
"""
import json
import math
import os
import queue
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from instance import HID_D0, HID_D1, SPD, ZONES  # noqa: E402
from sim import run  # noqa: E402
from world import build  # noqa: E402

INIT_TIMEOUT_S = 600.0
STEP_TIMEOUT_S = 10.0
BUDGET_S = 7200.0              # controller wall time over the whole run, init included
ALLOW = 1.15                   # total cost / total benchmark cost
DEV_MAX = 0.5                  # K h of occupied operative exceedance per zone-week
FAILS_OK = 1                   # zone-weeks allowed above DEV_MAX (of 16)
BENCH_FILE = os.path.join(HERE, "bench.json")


# ---------------------------------------------------------------- sandbox
def _sandbox_ids():
    import grp
    import pwd
    try:
        uid = pwd.getpwnam("nobody").pw_uid
    except KeyError:
        uid = 65534
    gid = None
    for name in ("nogroup", "nobody"):
        try:
            gid = grp.getgrnam(name).gr_gid
            break
        except KeyError:
            pass
    return uid, (65534 if gid is None else gid)


def _user_processes(uid):
    """Live (non-zombie) processes owned by uid, other than this one."""
    me, found = os.getpid(), []
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == me:
            continue
        try:
            with open("/proc/%s/status" % pid) as f:
                fields = dict(line.split(":", 1) for line in f if ":" in line)
            if int(fields["Uid"].split()[0]) == uid and not fields["State"].strip().startswith("Z"):
                found.append(int(pid))
        except (OSError, ValueError, KeyError):
            pass
    return found


def _kill_user(uid):
    """Kill every process owned by uid, so nothing outlives the run. Repeated until none is
    left alive, so a process that forks while being killed does not escape."""
    deadline = time.monotonic() + 5.0
    while True:
        alive = _user_processes(uid)
        if not alive or time.monotonic() > deadline:
            return
        for pid in alive:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        time.sleep(0.05)


_SHARED_DIRS = None


def _shared_dirs():
    """Every directory the sandbox user could leave a file in: the world-writable ones.
    Found once per grading run by walking the filesystem."""
    global _SHARED_DIRS
    if _SHARED_DIRS is None:
        found = []
        for top, dirs, _ in os.walk("/", topdown=True):
            if top in ("/proc", "/sys"):
                dirs[:] = []
                continue
            for d in list(dirs):
                p = os.path.join(top, d)
                try:
                    st = os.lstat(p)
                except OSError:
                    dirs.remove(d)
                    continue
                if not os.path.isdir(p) or os.path.islink(p):
                    dirs.remove(d)
                elif st.st_mode & 0o002:
                    found.append(p)
        _SHARED_DIRS = found
    return _SHARED_DIRS


def _sweep_user(uid):
    """Remove everything the sandbox user left behind: files in world-writable directories
    and System V IPC objects."""
    for d in _shared_dirs():
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            try:
                if e.stat(follow_symlinks=False).st_uid != uid:
                    continue
                if e.is_dir(follow_symlinks=False):
                    shutil.rmtree(e.path, ignore_errors=True)
                else:
                    os.unlink(e.path)
            except OSError:
                pass
    for kind, flag in (("shm", "-m"), ("msg", "-q"), ("sem", "-s")):
        try:
            with open("/proc/sysvipc/%s" % kind) as f:
                head = f.readline().split()
                rows = [ln.split() for ln in f]
        except OSError:
            continue
        if "uid" not in head:
            continue
        col_uid = head.index("uid")
        col_id = 1                       # shmid / msqid / semid
        for r in rows:
            if len(r) > col_uid and r[col_uid] == str(uid):
                try:
                    subprocess.run(["ipcrm", flag, r[col_id]], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, check=False, timeout=10)
                except (OSError, subprocess.SubprocessError):
                    pass


class Sandbox:
    def __init__(self, controller_path):
        self.root = os.geteuid() == 0
        self.uid, self.gid = _sandbox_ids()
        self.dir = tempfile.mkdtemp(prefix="tabs_sandbox_")
        os.chmod(self.dir, 0o755)
        self.ctrl = os.path.join(self.dir, "controller.py")
        self.host = os.path.join(self.dir, "host.py")
        shutil.copyfile(controller_path, self.ctrl)
        shutil.copyfile(os.path.join(HERE, "host.py"), self.host)
        os.chmod(self.ctrl, 0o644)
        os.chmod(self.host, 0o644)
        self.tmp = os.path.join(self.dir, "tmp")
        os.mkdir(self.tmp)
        if self.root:
            os.chown(self.tmp, self.uid, self.gid)
        os.chmod(self.tmp, 0o700)
        self.proc = None
        self.lines = queue.Queue()
        self.used = 0.0

    def _demote(self):
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 2**20, 50 * 2**20))
        resource.setrlimit(resource.RLIMIT_CPU, (int(BUDGET_S * 2), int(BUDGET_S * 2) + 5))
        resource.setrlimit(resource.RLIMIT_AS, (4 * 2**30, 4 * 2**30))
        if self.root:
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
            os.setgroups([])
            os.setgid(self.gid)
            os.setuid(self.uid)
        os.setsid()

    def start(self):
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": self.tmp, "TMPDIR": self.tmp,
               "LANG": "C.UTF-8", "PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1",
               "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        self.proc = subprocess.Popen(
            [sys.executable, "-I", "-B", self.host, self.ctrl], cwd=self.tmp, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1, preexec_fn=self._demote, close_fds=True)

        def pump(stream, q):
            for line in stream:
                q.put(line)
            q.put(None)
        threading.Thread(target=pump, args=(self.proc.stdout, self.lines), daemon=True).start()

    def call(self, msg, timeout):
        """Send one message and wait for one reply. Returns (reply or None, error)."""
        budget = BUDGET_S - self.used
        limit = min(timeout, budget)
        if limit <= 0:
            return None, "controller exceeded its %.0f s time budget for the run" % BUDGET_S
        t0 = time.monotonic()
        try:
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            return None, "controller process is gone"
        try:
            line = self.lines.get(timeout=limit)
        except queue.Empty:
            line = False
        self.used += time.monotonic() - t0
        if line is False:
            if limit < timeout:
                return None, ("controller exceeded its %.0f s time budget for the run" % BUDGET_S)
            return None, ("controller took longer than %.1f s to answer" % limit)
        if line is None:
            return None, "controller process exited"
        try:
            return json.loads(line), None
        except ValueError:
            return None, "controller sent a malformed reply"

    def close(self):
        if self.proc is not None:
            try:
                self.proc.stdin.write(json.dumps({"op": "exit"}) + "\n")
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                pass
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                self.proc.kill()
            except ProcessLookupError:
                pass
            try:
                self.proc.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass
        if self.root:
            _kill_user(self.uid)
            _sweep_user(self.uid)
        shutil.rmtree(self.dir, ignore_errors=True)


# ---------------------------------------------------------------- one reply
class ControllerFault(Exception):
    pass


def _finite_real(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    try:
        return math.isfinite(float(v))
    except OverflowError:
        return False


def _command(reply):
    """Validate a step reply. Returns (setpoint, {zone: duty in [0, 1]}, error)."""
    if not isinstance(reply, dict) or not reply.get("ok"):
        err = reply.get("error", "") if isinstance(reply, dict) else ""
        return None, None, "controller raised: " + str(err)[-600:]
    cmd = reply.get("command")
    if not isinstance(cmd, dict):
        return None, None, "step must return a dict, got %r" % (cmd,)
    if "supply_temp_c" not in cmd:
        return None, None, "command has no 'supply_temp_c': %r" % (cmd,)
    sp = cmd["supply_temp_c"]
    if not _finite_real(sp):
        return None, None, "'supply_temp_c' must be a finite number, got %r" % (sp,)
    if "valve_duty" not in cmd:
        return None, None, "command has no 'valve_duty': %r" % (cmd,)
    vd = cmd["valve_duty"]
    if not isinstance(vd, dict):
        return None, None, "'valve_duty' must be a dict with 'west' and 'east', got %r" % (vd,)
    duty = {}
    for z in ZONES:
        if z not in vd:
            return None, None, "'valve_duty' has no %r: %r" % (z, vd)
        d = vd[z]
        if not _finite_real(d):
            return None, None, "'valve_duty'[%r] must be a finite number, got %r" % (z, d)
        duty[z] = min(max(float(d), 0.0), 1.0)
    return float(sp), duty, None


# ---------------------------------------------------------------- the whole run
def _load_bench():
    with open(BENCH_FILE) as f:
        return [float(c) for c in json.load(f)["cost"]]


def _empty_record(path, bench):
    nweek = len(bench)
    return {
        "controller": path, "reward": 0, "error": None, "error_at": None,
        "limits": {"init_s": INIT_TIMEOUT_S, "step_s": STEP_TIMEOUT_S, "budget_s": BUDGET_S,
                   "allow_ratio": ALLOW, "dev_max_kh": DEV_MAX, "zone_week_fails_ok": FAILS_OK},
        "weeks": nweek, "steps_total": (HID_D1 - HID_D0) * SPD, "steps_completed": 0,
        "world_build_s": None, "run_s": None, "init_s": None, "step_max_s": None,
        "controller_wall_s": None,
        "cost": None, "elec_kwh": None, "qth_kwh": None, "bench_cost": bench, "ratio_week": None,
        "dev": {z: None for z in ZONES}, "hot": {z: None for z in ZONES},
        "cold": {z: None for z in ZONES},
        "zone_week_fails": None, "zone_weeks": nweek * len(ZONES),
        "total_cost": None, "bench_total_cost": float(np.sum(bench)), "ratio_total": None,
        "meets_comfort": False, "meets_cost": False,
    }


def grade(controller_path, progress=False):
    """Always returns the full record, whatever the controller did."""
    try:
        bench = _load_bench()
    except Exception as e:          # the verifier itself is broken: still a record, reward 0
        rec = _empty_record(controller_path, [])
        rec["error"] = "benchmark unreadable: %s: %s" % (type(e).__name__, e)
        return rec
    rec = _empty_record(controller_path, bench)
    if not os.path.isfile(controller_path):
        rec["error"] = "%s does not exist" % controller_path
        return rec

    box = None
    try:
        tic = time.time()
        w = build(keep_log=False)
        rec["world_build_s"] = round(time.time() - tic, 2)
        ep = w["ep_hid"]
        n = int(ep["n"])
        rec["steps_total"] = n

        box = Sandbox(controller_path)
        box.start()
        reply, err = box.call({"op": "init"}, INIT_TIMEOUT_S)
        rec["init_s"] = round(box.used, 3)
        if err or not isinstance(reply, dict) or not reply.get("ok"):
            detail = reply.get("error", "") if isinstance(reply, dict) else reply
            rec["error"] = err or ("controller failed to initialise: " + str(detail)[-600:])
            return rec

        stats = {"n": 0, "tmax": 0.0}
        run_t0 = time.time()

        def ctrl(obs, t, X):        # X (the true plant state) is never sent
            if progress and t > 0 and t % (7 * SPD) == 0:
                print("  week %d done: %.0f s elapsed, controller %.0f s, slowest step %.2f s"
                      % (t // (7 * SPD), time.time() - run_t0, box.used, stats["tmax"]),
                      file=sys.stderr, flush=True)
            before = box.used
            reply, err = box.call({"op": "step", "obs": obs}, STEP_TIMEOUT_S)
            stats["tmax"] = max(stats["tmax"], box.used - before)
            if err is None:
                sp, duty, err = _command(reply)
            if err:
                rec["error_at"] = obs.get("time")
                raise ControllerFault(err)
            stats["n"] += 1
            return sp, duty

        try:
            W, _ = run(ep, ctrl, w["X0_hid"], w["fc_hid"], plants=w["plants"],
                       seed=w["seeds"]["noise_hid"])
        except ControllerFault as e:
            rec["error"] = str(e)
            return rec
        finally:
            rec["steps_completed"] = stats["n"]
            rec["step_max_s"] = round(stats["tmax"], 3)
            rec["run_s"] = round(time.time() - run_t0, 1)

        dev = {z: np.asarray(W[f"dev_{z}"], float) for z in ZONES}
        nfail = int(sum((dev[z] > DEV_MAX).sum() for z in ZONES))
        cost = np.asarray(W["cost"], float)
        total = float(cost.sum())
        btotal = float(np.sum(bench))
        ratio = total / btotal
        rec.update(
            cost=cost.tolist(), elec_kwh=np.asarray(W["elec"]).tolist(),
            qth_kwh=np.asarray(W["qth"]).tolist(),
            ratio_week=(cost / np.array(bench)).tolist(),
            dev={z: dev[z].tolist() for z in ZONES},
            hot={z: np.asarray(W[f"hot_{z}"]).tolist() for z in ZONES},
            cold={z: np.asarray(W[f"cold_{z}"]).tolist() for z in ZONES},
            zone_week_fails=nfail, total_cost=total, bench_total_cost=btotal, ratio_total=ratio,
            meets_comfort=bool(nfail <= FAILS_OK), meets_cost=bool(ratio <= ALLOW))
        rec["reward"] = int(nfail <= FAILS_OK and ratio <= ALLOW)
    except Exception as e:
        rec["error"] = "grader error: %s: %s" % (type(e).__name__, e)
        rec["trace"] = traceback.format_exc()[-1500:]
        rec["reward"] = 0
    finally:
        if box is not None:
            rec["controller_wall_s"] = round(box.used, 3)
            box.close()
    return rec


def report(rec, out=sys.stdout):
    if rec.get("error"):
        print("ERROR %s%s (after %s of %s steps)"
              % (rec["error"], " at %s" % rec["error_at"] if rec.get("error_at") else "",
                 rec.get("steps_completed"), rec.get("steps_total")), file=out)
    else:
        print(f"{'week':>4} {'cost $':>8} {'bench $':>8} {'ratio':>6} {'dev W':>6} {'dev E':>6}", file=out)
        for i in range(len(rec["cost"])):
            print(f"{i + 1:4d} {rec['cost'][i]:8.3f} {rec['bench_cost'][i]:8.3f} {rec['ratio_week'][i]:6.3f} "
                  f"{rec['dev']['west'][i]:6.2f} {rec['dev']['east'][i]:6.2f}", file=out)
        print(f"total cost {rec['total_cost']:.3f} vs benchmark {rec['bench_total_cost']:.3f}: "
              f"ratio {rec['ratio_total']:.4f} (limit {ALLOW}); zone-week comfort fails "
              f"{rec['zone_week_fails']} (allowed {FAILS_OK}); init {rec['init_s']:.1f} s, "
              f"run {rec['run_s']:.0f} s, controller {rec['controller_wall_s']:.0f} s, "
              f"slowest step {rec['step_max_s']:.2f} s", file=out)
    print("REWARD", rec["reward"], file=out)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("controller", nargs="?", default="/app/controller.py")
    ap.add_argument("--json", default=None, help="write the full record here")
    a = ap.parse_args()
    r = grade(a.controller, progress=True)
    report(r)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(r, f, indent=1)
