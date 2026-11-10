"""Runs a submitted audit program on the hidden compressed air audit packages and compares its results with the
sealed true ones.

Each hidden audit package (hidden/<site>/) is copied, with the program alone, to a scratch directory, and the program
is run there as the unprivileged user nobody, with only PATH and HOME set, as `python3 -I audit.py <audit>
<out.json>`, with a time limit, in its own process group. When it ends or times out, its process group and every
process of nobody are killed, so nothing it started outlives its run. The sealed results (hidden/truth.json) stay in this directory, which only root can
read. A site is right when every result is within its relative tolerance (TOL) of the true value. The submission is
accepted when at most MAX_WRONG sites are wrong.
"""
import json
import math
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_WRONG = 1            # of 8 hidden sites, from the requirement (at least seven right)
TOL = {"avg_demand_m3_min": 0.03, "specific_power_kw_per_m3_min": 0.03,       # relative, from the requirement
       "peak_demand_m3_min": 0.05, "leak_m3_min": 0.05}
TIME_LIMIT_S = 120
NOBODY_UID = 65534
NOBODY = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "--inh-caps=-all"]


def kill_leftovers(proc, as_nobody):
    """Kills the run's process group and, when it ran as nobody, every process of that user, so nothing the program
    started (including a process that left the group with setsid) outlives its run."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if not as_nobody:
        return
    for _ in range(3):
        found = False
        for d in os.listdir("/proc"):
            if not d.isdigit():
                continue
            try:
                with open("/proc/%s/status" % d) as f:
                    st = f.read().splitlines()
                uid = next(int(l.split()[1]) for l in st if l.startswith("Uid:"))
                zombie = any(l.startswith("State:") and "Z" in l.split()[1] for l in st)
                if uid == NOBODY_UID and not zombie:
                    os.kill(int(d), signal.SIGKILL)
                    found = True
            except (OSError, StopIteration, ValueError):
                pass
        if not found:
            break


def run_one(program, hist_dir, as_nobody=True):
    work = tempfile.mkdtemp(prefix="airaudit_")
    proc = None
    os.chmod(work, 0o755)
    try:
        shutil.copy(program, os.path.join(work, "audit.py"))
        shutil.copytree(hist_dir, os.path.join(work, "audit"))
        outdir = os.path.join(work, "out")
        os.makedirs(outdir)
        for top, dirs, files in os.walk(work):
            for n in dirs:
                os.chmod(os.path.join(top, n), 0o755)
            for n in files:
                os.chmod(os.path.join(top, n), 0o644)
        os.chmod(outdir, 0o777)
        out = os.path.join(outdir, "result.json")
        cmd = [sys.executable, "-I", os.path.join(work, "audit.py"), os.path.join(work, "audit"), out]
        if as_nobody:
            cmd = NOBODY + cmd
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": work, "OMP_NUM_THREADS": "2"}
        # output to a file outside the scratch directory, readable by root only, so that a process the program
        # leaves behind cannot hold the run open
        errf = tempfile.TemporaryFile(mode="w+")
        proc = subprocess.Popen(cmd, cwd=work, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=errf, start_new_session=True)  # its own process group, killed as a whole
        try:
            proc.wait(timeout=TIME_LIMIT_S)
        except subprocess.TimeoutExpired:
            kill_leftovers(proc, as_nobody)
            proc.wait()
            return None, "time limit of %d s exceeded" % TIME_LIMIT_S
        kill_leftovers(proc, as_nobody)              # anything left running in the background, before reading
        if proc.returncode != 0:
            errf.seek(0)
            return None, "exit status %d: %s" % (proc.returncode, errf.read().strip()[-300:])
        return read_result(out), None
    except Exception as e:                           # missing or malformed output
        return None, repr(e)
    finally:
        if proc is not None:
            kill_leftovers(proc, as_nobody)
        shutil.rmtree(work, ignore_errors=True)


def _no_duplicates(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key in the result")
    return dict(pairs)


def read_result(out):
    """The result file must be a regular file (not a symlink) holding one JSON object without duplicate keys."""
    st = os.lstat(out)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("the result is not a regular file")
    fd = os.open(out, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as f:
        res = json.load(f, object_pairs_hook=_no_duplicates)
    if not isinstance(res, dict):
        raise ValueError("the result is not a JSON object")
    return res


def judge(res, truth):
    """Right when the result has exactly the procedure's four keys, each a finite number (not a boolean, string,
    array or null), within its relative tolerance of the true value."""
    errs = {}
    if not isinstance(res, dict) or set(res) != set(TOL):
        return False, "not a result: keys must be exactly %s" % sorted(TOL)
    for k in TOL:
        v = res[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return False, "%s is not a number" % k
        v = float(v)
        if not math.isfinite(v):
            return False, "%s is not a finite number" % k
        errs[k] = v / truth[k] - 1
    ok = all(abs(errs[k]) <= TOL[k] for k in TOL)
    return ok, {k: round(100 * e, 2) for k, e in errs.items()}


def score(program, hidden=os.path.join(HERE, "hidden"), as_nobody=True):
    truth = json.load(open(os.path.join(hidden, "truth.json")))
    cases, wrong = {}, 0
    for name in sorted(truth):
        res, err = run_one(program, os.path.join(hidden, name), as_nobody)
        if err:
            cases[name] = {"right": False, "error": err}
        else:
            ok, info = judge(res, truth[name])
            cases[name] = {"right": ok, "result": res, "error_pct": info}
        wrong += not cases[name]["right"]
    return {"accepted": wrong <= MAX_WRONG, "wrong": wrong, "cases": cases}


if __name__ == "__main__":
    r = score(sys.argv[1], as_nobody=os.geteuid() == 0)
    for k, v in r["cases"].items():
        print(k, "ok " if v["right"] else "BAD", v.get("error") or v["error_pct"])
    print("%d of %d wrong: %s" % (r["wrong"], len(r["cases"]), "accepted" if r["accepted"] else "rejected"))
