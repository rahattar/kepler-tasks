"""Closed-loop grading of a submitted Puller 11 supervisory controller on the perfect-silicon recipe PS-R07.

The sealed definition (puller.py) grows the eight graded HZ-B bodies (seeds 1-8). For each body a fresh sandboxed
supervisor process is started (see host.py): Supervisor() is constructed once and update(meas) is called once
a minute from the end of the crown (length 0) until the body reaches 1500 mm. obs carries the minute-log quantities
(time_min, length_mm, camera_diameter_mm, pull_rate_mm_min, heater_power_kw, pyrometer_c, crucible_rpm_set); true
states and graded quantities are never sent. A reply is valid when it is a pair (pull rate in mm/min, heater power in kW)
of finite real numbers (booleans are not numbers); the plant clips them to the drive limits and follows them at the
slew limits. A missing key, a non-finite value, an exception, a reply slower than STEP_TIMEOUT_S, or more than
BUDGET_S of controller time on one body (constructor included) stops the run with an error, and the reward is 0.

GATE: REWARD = 1 iff every body completes and, on every body from 50 mm to 1500 mm, the true growth rate averaged
over each 5 mm of crystal stays within +-1 % of the PS-R07 program (VG_WINDOW) and the true diameter never falls
below 301.0 mm (puller.D_MIN), and the true diameter averaged from 50 mm to 1500 mm over all bodies is at most
D_MEAN_MAX.

ISOLATION. The controller process runs as the unprivileged user 'nobody' with resource limits, in a scratch
directory holding only a copy of the controller and of host.py, talking over private pipes. The sealed modules are
not readable by that user. When a body ends every process the user owns is killed, and everything it left in a
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
import puller as PU  # noqa: E402

INIT_TIMEOUT_S = 120.0
STEP_TIMEOUT_S = 5.0
BUDGET_S = 600.0               # controller wall time per body, constructor included
VG_WINDOW = 0.01               # +-1 % of the growth-rate program, 5 mm averages
AVG_MM = 5
L0 = 50.0
D_MEAN_MAX = 303.0             # mm, true diameter averaged over all bodies from 50 mm to 1500 mm
MAX_MIN = 4000                 # minutes; a body slower than this is not completed


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
        self.dir = tempfile.mkdtemp(prefix="puller_sandbox_")
        os.chmod(self.dir, 0o755)
        self.ctrl = os.path.join(self.dir, "supervisor.py")
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
            return None, "controller exceeded its %.0f s time budget for the body" % BUDGET_S
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
                return None, ("controller exceeded its %.0f s time budget for the body" % BUDGET_S)
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
    """Validate an update reply: a pair (pull rate mm/min, heater power kW). Returns (pull rate, heater, error)."""
    if not isinstance(reply, dict) or not reply.get("ok"):
        err = reply.get("error", "") if isinstance(reply, dict) else ""
        return None, None, "supervisor raised: " + str(err)[-600:]
    cmd = reply.get("command")
    if not isinstance(cmd, (list, tuple)) or len(cmd) != 2:
        return None, None, "update must return a pair (pull rate, heater power), got %r" % (cmd,)
    for v in cmd:
        if not _finite_real(v):
            return None, None, "update returned a value that is not a finite number: %r" % (cmd,)
    return float(cmd[0]), float(cmd[1]), None


def _obs(m):
    return dict(time_min=round(float(m["t"]), 3), length_mm=round(float(m["length_mm"]), 3),
                camera_diameter_mm=round(float(m["camera_diameter_mm"]), 3),
                pull_rate_mm_min=round(float(m["pull_rate_mm_min"]), 5),
                heater_power_kw=round(float(m["heater_power_kw"]), 3),
                pyrometer_c=round(1428.0 + float(m["pyrometer_k"]), 3), crucible_rpm_set=float(m["crucible_rpm_set"]))


# ---------------------------------------------------------------- one body, the whole run
def grade_body(controller_path, seed):
    rec = {"seed": seed, "error": None, "error_at_min": None, "steps": 0, "init_s": None, "step_max_s": None,
           "controller_wall_s": None}
    rc = PU.RECIPES["perfect_si"]
    box = None
    try:
        b = PU.make_body(seed, PU.HZ)
        pl = PU.Puller(b, rc)
        box = Sandbox(controller_path)
        box.start()
        reply, err = box.call({"op": "init"}, INIT_TIMEOUT_S)
        rec["init_s"] = round(box.used, 3)
        if err or not isinstance(reply, dict) or not reply.get("ok"):
            detail = reply.get("error", "") if isinstance(reply, dict) else reply
            rec["error"] = err or ("controller failed to initialise: " + str(detail)[-600:])
            return rec
        tmax = 0.0
        while pl.L < PU.L_BODY and pl.t < MAX_MIN:
            before = box.used
            reply, err = box.call({"op": "step", "obs": _obs(pl.measure())}, STEP_TIMEOUT_S)
            tmax = max(tmax, box.used - before)
            if err is None:
                vp, p, err = _command(reply)
            if err:
                rec["error"], rec["error_at_min"] = err, round(pl.t, 1)
                return rec
            pl.apply(vp, p, 1.0)
            rec["steps"] += 1
        rec["step_max_s"] = round(tmax, 3)
        sc = PU.score(np.array(pl.log), l0=L0, win=VG_WINDOW, avg_mm=AVG_MM)
        rec.update(sc)
    except Exception as e:
        rec["error"] = "grader error: %s: %s" % (type(e).__name__, e)
        rec["trace"] = traceback.format_exc()[-1500:]
    finally:
        if box is not None:
            rec["controller_wall_s"] = round(box.used, 3)
            box.close()
    return rec


def grade(controller_path, progress=False):
    """Always returns the full record, whatever the controller did."""
    rec = {"controller": controller_path, "reward": 0, "error": None,
           "limits": {"init_s": INIT_TIMEOUT_S, "step_s": STEP_TIMEOUT_S, "budget_s_per_body": BUDGET_S,
                      "vg_window": VG_WINDOW, "avg_mm": AVG_MM, "d_min_mm": PU.D_MIN, "d_mean_max_mm": D_MEAN_MAX},
           "bodies": [], "d_mean_all": None, "fails": []}
    if not os.path.isfile(controller_path):
        rec["error"] = "%s does not exist" % controller_path
        return rec
    for seed in PU.GRADED_SEEDS:
        r = grade_body(controller_path, seed)
        rec["bodies"].append(r)
        if progress:
            if r["error"]:
                print("  body %d: ERROR %s" % (seed, r["error"]), file=sys.stderr, flush=True)
            else:
                print("  body %d: V/G worst %.3f %%, D min %.2f, D mean %.2f, controller %.0f s"
                      % (seed, 100 * r["vg_max"], r["d_min"], r["d_mean"], r["controller_wall_s"]),
                      file=sys.stderr, flush=True)
        if r["error"]:
            rec["error"] = "body %d: %s" % (seed, r["error"])
            return rec
    fails = []
    for r in rec["bodies"]:
        if not r["done"]:
            fails.append("body %d did not reach 1500 mm in %d min" % (r["seed"], MAX_MIN))
        if r["vg_max"] > VG_WINDOW:
            fails.append("body %d: growth rate off its program by %.3f %%" % (r["seed"], 100 * r["vg_max"]))
        if r["d_min"] < PU.D_MIN:
            fails.append("body %d: true diameter down to %.2f mm" % (r["seed"], r["d_min"]))
    rec["d_mean_all"] = float(np.mean([r["d_mean"] for r in rec["bodies"]]))
    if rec["d_mean_all"] > D_MEAN_MAX:
        fails.append("mean true diameter %.3f mm above %.1f mm" % (rec["d_mean_all"], D_MEAN_MAX))
    rec["fails"] = fails
    rec["reward"] = int(not fails)
    return rec


def report(rec, out=sys.stdout):
    if rec.get("error"):
        print("ERROR", rec["error"], file=out)
    else:
        for r in rec["bodies"]:
            print("body %d  V/G worst %.3f %%  D min %.2f  D mean %.2f  controller %.0f s, slowest step %.2f s"
                  % (r["seed"], 100 * r["vg_max"], r["d_min"], r["d_mean"], r["controller_wall_s"], r["step_max_s"]),
                  file=out)
        print("mean true diameter %.3f mm (at most %.1f)" % (rec["d_mean_all"], D_MEAN_MAX), file=out)
        for f in rec["fails"]:
            print("FAIL", f, file=out)
    print("REWARD", rec["reward"], file=out)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("controller", nargs="?", default="/app/supervisor.py")
    ap.add_argument("--json", default=None, help="write the full record here")
    a = ap.parse_args()
    r = grade(a.controller, progress=True)
    report(r)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(r, f, indent=1)
