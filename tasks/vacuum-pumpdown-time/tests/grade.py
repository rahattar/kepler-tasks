"""Runs a submitted MS-VP program on the hidden chambers and checks each job's pump-down time against the truth.

Each hidden chamber's package (hidden/<chamber>/) is copied, with the program alone, to a scratch directory owned by root,
where the package is read-only to the program. The program runs there as the unprivileged user nobody, with only
PATH and HOME set, as `python3 -I pumpdown.py <package> <output>`, with a time limit, in its own process group. When
it ends or times out, its process group and every process of nobody are killed before the output is read, so nothing
it started outlives its run. The truth (hidden/truth.json) stays in this directory, which only root can read.

The output must be a regular file (not a symlink) of at most MAX_BYTES bytes holding a JSON object with exactly the
key pumpdown_min, once, a finite positive number. A chamber whose output breaks any of this is wrong. A chamber
is right when the value is within TOL of its job's pump-down time (truth.json, computed on the sealed chamber by
authoring/provenance/jobs.py and vac.py). The submission is accepted when at most MAX_WRONG chambers are wrong.
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
import time

HERE = os.path.dirname(os.path.abspath(__file__))

MAX_WRONG = 1            # chambers, over all hidden chambers
TOL = 0.04               # relative, as the instruction states
TIME_LIMIT_S = 600       # per job, as the instruction states
MAX_BYTES = 65536        # bytes, as the instruction states
KEYS = ("pumpdown_min",)
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
    for _ in range(40):                              # until none is left running (at most about 2 s)
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
        time.sleep(0.05)


def _no_duplicates(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("a key appears twice")
    return dict(pairs)


def _no_constants(name):
    raise ValueError("%s is not a finite number" % name)


def read_result(out, _unused=None):
    """(pump-down time,) from the output file, or ValueError when it is not exactly what the instruction
    asks."""
    st = os.lstat(out)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("the output is not a regular file")
    fd = os.open(out, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        raw = f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("the output is larger than %d bytes" % MAX_BYTES)
    d = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates, parse_constant=_no_constants)
    if not isinstance(d, dict) or set(d) != set(KEYS):
        raise ValueError("the keys are not exactly %s" % ", ".join(KEYS))
    vals = []
    for k in KEYS:
        v = d[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            raise ValueError("%s is not a finite positive number" % k)
        vals.append(float(v))
    return tuple(vals)


def run_one(program, pkg_dir, _unused=None, as_nobody=True):
    work = tempfile.mkdtemp(prefix="pumpdown_")
    proc = None
    os.chmod(work, 0o755)
    try:
        shutil.copy(program, os.path.join(work, "pumpdown.py"))
        shutil.copytree(pkg_dir, os.path.join(work, "package"))
        outdir = os.path.join(work, "out")
        os.makedirs(outdir)
        for top, dirs, files in os.walk(work):
            for n in dirs:
                os.chmod(os.path.join(top, n), 0o755)
            for n in files:
                os.chmod(os.path.join(top, n), 0o644)
        os.chmod(outdir, 0o777)
        out = os.path.join(outdir, "pumpdown.json")
        cmd = [sys.executable, "-I", os.path.join(work, "pumpdown.py"), os.path.join(work, "package"), out]
        if as_nobody:
            cmd = NOBODY + cmd
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": work, "OMP_NUM_THREADS": "2"}
        # stderr to a file outside the scratch directory, readable by root only, so that a process the program
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
        return None, repr(e)[:300]
    finally:
        if proc is not None:
            kill_leftovers(proc, as_nobody)
        shutil.rmtree(work, ignore_errors=True)


def score(program, hidden=os.path.join(HERE, "hidden"), as_nobody=True):
    truth = json.load(open(os.path.join(hidden, "truth.json")))
    jobs, wrong = {}, 0
    for name in sorted(truth):
        true = truth[name]["pumpdown_min"]
        res, err = run_one(program, os.path.join(hidden, name), None, as_nobody)
        if err:
            jobs[name] = {"right": False, "error": err}
            wrong += 1
            continue
        ratio = res[0] / true
        right = abs(ratio - 1) <= TOL
        jobs[name] = {"right": right, "pumpdown_min": res[0], "true_min": true, "ratio": ratio}
        wrong += not right
    return {"accepted": wrong <= MAX_WRONG, "wrong": wrong, "jobs": len(truth), "packages": jobs}


if __name__ == "__main__":
    r = score(sys.argv[1], hidden=sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "hidden"),
              as_nobody=os.geteuid() == 0 and shutil.which("setpriv") is not None)
    for k, v in r["packages"].items():
        msg = v["error"] if "error" in v else "%.2f min, %.3f of the true" % (v["pumpdown_min"], v["ratio"])
        print("%-16s %s  %s" % (k, "right" if v["right"] else "WRONG", msg))
    print("%d of %d chambers wrong: %s" % (r["wrong"], r["jobs"], "accepted" if r["accepted"] else "rejected"))
