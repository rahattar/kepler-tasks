"""Closed-loop grading of a submitted chill-station controller.

For every hidden wafer the submitted controller runs in its own sandboxed process (see
host.py) and drives the sealed plant (plant.py) one control period at a time: it receives
the production sensor readings, returns a pressure command or a release, and the plant
integrates the command. The graded quantities are never shown to it.

A wafer PASSES when, from landing until release,
  * the inner/outer zone difference never exceeds 25.0 K (checked at every 0.01 s step),
  * the mass-mean temperature at release is at or below 50.0 C,
  * it is released before 30 s,
and the controller answered every call in time with a valid command.

The REWARD is 1 when every wafer passes and the total cycle time over all wafers is within
the allowance (10%) of the total of each wafer's perfect-knowledge cycle, which is computed
here at grade time from the sealed plant (plant.clairvoyant), never stored and never taken
from the reference solution.

ISOLATION. The controller process runs as an unprivileged user with resource limits, in a
scratch directory holding only a copy of the controller and of host.py. The sealed plant,
the truth file and the logs are not readable or writable by that user, the verifier has no
network, and after each wafer every process the user owns is killed and everything it left
in a world-writable directory or as a System V IPC object is removed, so nothing carries
from one wafer to the next.
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
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plant as pl  # noqa: E402

INIT_TIMEOUT_S = 20.0
STEP_TIMEOUT_S = 1.0
WAFER_BUDGET_S = 60.0          # controller wall time per wafer, init included
EPS = 1e-9


# ---------------------------------------------------------------- truth
def load_truth(path=None):
    with open(path or os.path.join(HERE, "truth.json")) as f:
        return json.load(f)


def station_record(truth, sid):
    """What the controller is told about its station: the public inspection record."""
    s = truth["stations"][sid]
    return {"station": sid, "inner_standoff_um": s["inner_um"],
            "outer_standoff_um": s["outer_um"], "plate_setpoint_C": s["setpoint_C"]}


def make_wafer(truth, w):
    s = truth["stations"][w["station"]]
    return pl.Wafer(s["inner_um"] * 1e-6, s["outer_um"] * 1e-6, s["setpoint_C"],
                    s["_alpha_plate"], truth["films"][w["film"]]["_alpha_wafer"],
                    w["_sag_um"] * 1e-6, w["_T0_C"])


# ---------------------------------------------------------------- sandbox
def _sandbox_ids():
    import pwd
    import grp
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
    """Kill every process owned by uid, so nothing outlives its wafer. Repeated until none
    is left alive, so a process that forks while being killed does not escape."""
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
    """Remove everything the sandbox user left behind, so no state carries from one wafer
    to the next: files in world-writable directories and System V IPC objects."""
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
        self.dir = tempfile.mkdtemp(prefix="wcc_sandbox_")
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
        resource.setrlimit(resource.RLIMIT_CPU, (int(WAFER_BUDGET_S * 2), int(WAFER_BUDGET_S * 2) + 5))
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
        budget = WAFER_BUDGET_S - self.used
        limit = min(timeout, budget)
        if limit <= 0:
            return None, "controller exceeded its %.0f s budget for the wafer" % WAFER_BUDGET_S
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
        if self.root:
            _kill_user(self.uid)
            _sweep_user(self.uid)
        shutil.rmtree(self.dir, ignore_errors=True)


# ---------------------------------------------------------------- one wafer
def _command(reply):
    """Validate a step reply. Returns (release, pressure, error)."""
    if not isinstance(reply, dict) or not reply.get("ok"):
        err = reply.get("error", "") if isinstance(reply, dict) else ""
        return None, None, "controller raised: " + str(err)[-300:]
    cmd = reply.get("command")
    if not isinstance(cmd, dict):
        return None, None, "step must return a dict, got %r" % (cmd,)
    rel = cmd.get("release", False)
    if not isinstance(rel, bool):
        return None, None, "'release' must be true or false, got %r" % (rel,)
    if rel:
        return True, None, None
    P = cmd.get("pressure_torr")
    if isinstance(P, bool) or not isinstance(P, (int, float)) or not math.isfinite(P):
        return None, None, "'pressure_torr' must be a finite number, got %r" % (P,)
    if not (pl.P_MIN - EPS <= P <= pl.P_MAX + EPS):
        return None, None, ("pressure command %.4g Torr is outside %.0f-%.0f Torr"
                            % (P, pl.P_MIN, pl.P_MAX))
    return False, float(P), None


def _drive(box, wafer, rng, truth, w, out):
    """Initialise the controller and run the closed loop until release, a fault or 30 s.
    Fills out[]; any early return leaves out["error"] set."""
    box.start()
    reply, err = box.call({"op": "init", "station": station_record(truth, w["station"]),
                           "wafer": {"film": w["film"]}}, INIT_TIMEOUT_S)
    if err or not isinstance(reply, dict) or not reply.get("ok"):
        detail = reply.get("error", "") if isinstance(reply, dict) else reply
        out["error"] = err or ("controller failed to initialise: " + str(detail)[-300:])
        return
    Tw, Tp, P = wafer.landing()
    n_sub = int(round(pl.CTRL_DT / pl.DT))
    worst = 0.0
    try:
        for k in range(int(round(pl.T_CYCLE_MAX / pl.CTRL_DT)) + 1):
            t = round(k * pl.CTRL_DT, 6)
            reading = {key: round(v, 4) for key, v in wafer.reading(Tw, Tp, P, rng).items()}
            if t >= pl.T_CYCLE_MAX - EPS:
                out["error"] = "wafer still on the plate at %.0f s" % pl.T_CYCLE_MAX
                return
            reply, err = box.call({"op": "step", "t": t, "reading": reading}, STEP_TIMEOUT_S)
            if err:
                out["error"] = err
                return
            release, P_cmd, err = _command(reply)
            if err:
                out["error"] = err
                return
            if release:
                out["released"] = True
                out["cycle_s"] = t
                out["T_release_C"] = round(float(wafer.t_mean(Tw)[0]), 4)
                return
            Pc = np.array([[P_cmd]])
            for _ in range(n_sub):
                Tw, Tp, P = wafer.step(Tw, Tp, P, Pc)
                worst = max(worst, float(wafer.zone_dT(Tw)[0]))
    finally:
        out["worst_zone_dT_K"] = round(worst, 4)


def run_wafer(controller_path, truth, w):
    """One wafer, end to end. Always returns the full record, whatever the controller did."""
    wafer = make_wafer(truth, w)
    rng = np.random.default_rng(w["_noise_seed"])
    out = {"id": w["id"], "station": w["station"], "film": w["film"], "released": False,
           "cycle_s": None, "T_release_C": None, "worst_zone_dT_K": 0.0, "error": None}
    box = Sandbox(controller_path)
    try:
        _drive(box, wafer, rng, truth, w, out)
    finally:
        out["controller_wall_s"] = round(box.used, 3)
        box.close()
    out["meets_zone"] = out["worst_zone_dT_K"] <= pl.ZONE_CAP + EPS
    out["meets_release"] = bool(out["released"] and out["T_release_C"] is not None
                                and out["T_release_C"] <= pl.T_TARGET + EPS)
    out["passed"] = bool(out["error"] is None and out["meets_zone"] and out["meets_release"])
    return out


def _bench(args):
    truth, w = args
    cyc, worst = pl.clairvoyant(make_wafer(truth, w))
    return w["id"], cyc, worst


def benchmarks(truth, workers=2):
    jobs = [(truth, w) for w in truth["wafers"]]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return {i: (c, wst) for i, c, wst in ex.map(_bench, jobs)}


# ---------------------------------------------------------------- the whole set
def grade(controller_path, truth=None):
    truth = truth or load_truth()
    res = {"error": None, "reward": 0, "wafers": [], "allowance": truth["allowance"]}
    if not os.path.isfile(controller_path):
        res["error"] = "%s does not exist" % controller_path
        return res
    for w in truth["wafers"]:
        res["wafers"].append(run_wafer(controller_path, truth, w))
    bench = benchmarks(truth)
    total, total_b = 0.0, 0.0
    for r in res["wafers"]:
        b = bench[r["id"]][0]
        r["benchmark_s"] = b
        r["cycle_ratio"] = (round(r["cycle_s"] / b, 4) if r["cycle_s"] is not None else None)
        total += r["cycle_s"] if r["cycle_s"] is not None else pl.T_CYCLE_MAX
        total_b += b
    res["passed_wafers"] = sum(r["passed"] for r in res["wafers"])
    res["total_cycle_s"] = round(total, 3)
    res["total_benchmark_s"] = round(total_b, 3)
    res["cycle_ratio"] = round(total / total_b, 4)
    res["cycle_limit_ratio"] = round(1.0 + truth["allowance"], 4)
    all_pass = res["passed_wafers"] == len(res["wafers"])
    fast = res["cycle_ratio"] <= 1.0 + truth["allowance"] + EPS
    res["reward"] = int(all_pass and fast)
    return res


if __name__ == "__main__":
    r = grade(sys.argv[1] if len(sys.argv) > 1 else "/app/controller.py")
    print(json.dumps({k: v for k, v in r.items() if k != "wafers"}, indent=1))
    for w in r["wafers"]:
        print(w)
