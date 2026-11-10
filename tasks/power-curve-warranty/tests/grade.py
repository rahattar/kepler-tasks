"""Runs a submitted PP-12 program on the hidden farm-period packages and compares its results with the sealed true ones.

Each hidden package (hidden/<package>/) is copied, with the program alone, to a scratch directory owned by root, where
the package is read-only to the program. The program runs there as the unprivileged user nobody, with only PATH and
HOME set, as `python3 -I pp12.py <package> <output>`, with a time limit, in its own process group. When it ends or
times out, its process group and every process of nobody are killed before the output is read, so nothing it started
outlives its run. The sealed results (hidden/truth.json) stay in this directory, which only root can read.

The output must be a regular file (not a symlink) holding the header turbine,aep_ratio,warranty_claim and one row per
turbine of the package, each turbine exactly once, each ratio a finite number and each claim yes or no. A package
whose output breaks any of this has all its turbines counted wrong. A turbine is right when its claim is the true one
and its ratio is within TOL of the true ratio. The submission is accepted when at most MAX_WRONG turbines of all the
hidden packages are wrong.
"""
import csv
import io
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
TOL = 0.01               # on the annual energy ratio (absolute)
MAX_WRONG = 1            # turbines, over all hidden packages
TIME_LIMIT_S = 600       # per package, as the instruction states
MAX_BYTES = 1 << 20
HEADER = ["turbine", "aep_ratio", "warranty_claim"]
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


def read_result(out, turbines):
    """{turbine: (ratio, claim)} from the output file, or ValueError when it is not exactly what the instruction asks."""
    st = os.lstat(out)
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("the output is not a regular file")
    fd = os.open(out, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as f:
        raw = f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("the output is larger than %d bytes" % MAX_BYTES)
    rows = [r for r in csv.reader(io.StringIO(raw.decode("utf-8"), newline="")) if r != []]
    if not rows or rows[0] != HEADER:
        raise ValueError("the header is not %s" % ",".join(HEADER))
    res = {}
    for r in rows[1:]:
        if len(r) != 3:
            raise ValueError("a row does not have three fields: %r" % r[:4])
        t, a, c = r
        if t not in turbines:
            raise ValueError("not a turbine of the package: %r" % t[:20])
        if t in res:
            raise ValueError("turbine %s appears twice" % t)
        a = float(a)
        if not math.isfinite(a):
            raise ValueError("the ratio of %s is not a finite number" % t)
        if c not in ("yes", "no"):
            raise ValueError("the claim of %s is not yes or no" % t)
        res[t] = (a, c)
    missing = sorted(set(turbines) - set(res))
    if missing:
        raise ValueError("turbines missing: %s" % ",".join(missing))
    return res


def run_one(program, pkg_dir, turbines, as_nobody=True):
    work = tempfile.mkdtemp(prefix="pp12_")
    proc = None
    os.chmod(work, 0o755)
    try:
        shutil.copy(program, os.path.join(work, "pp12.py"))
        shutil.copytree(pkg_dir, os.path.join(work, "package"))
        outdir = os.path.join(work, "out")
        os.makedirs(outdir)
        for top, dirs, files in os.walk(work):
            for n in dirs:
                os.chmod(os.path.join(top, n), 0o755)
            for n in files:
                os.chmod(os.path.join(top, n), 0o644)
        os.chmod(outdir, 0o777)
        out = os.path.join(outdir, "results.csv")
        cmd = [sys.executable, "-I", os.path.join(work, "pp12.py"), os.path.join(work, "package"), out]
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
        return read_result(out, turbines), None
    except Exception as e:                           # missing or malformed output
        return None, repr(e)[:300]
    finally:
        if proc is not None:
            kill_leftovers(proc, as_nobody)
        shutil.rmtree(work, ignore_errors=True)


def score(program, hidden=os.path.join(HERE, "hidden"), as_nobody=True):
    truth = json.load(open(os.path.join(hidden, "truth.json")))
    packages, wrong, total = {}, 0, 0
    for name in sorted(truth):
        tr = truth[name]
        total += len(tr)
        res, err = run_one(program, os.path.join(hidden, name), sorted(tr), as_nobody)
        if err:
            packages[name] = {"wrong": len(tr), "error": err}
            wrong += len(tr)
            continue
        per = {}
        for t in sorted(tr):
            a, c = res[t]
            ok = c == tr[t]["warranty_claim"] and abs(a - tr[t]["aep_ratio"]) <= TOL
            per[t] = {"right": ok, "aep_ratio": a, "warranty_claim": c}
        n_bad = sum(not v["right"] for v in per.values())
        packages[name] = {"wrong": n_bad, "turbines": per}
        wrong += n_bad
    return {"accepted": wrong <= MAX_WRONG, "wrong": wrong, "turbines": total, "packages": packages}


if __name__ == "__main__":
    r = score(sys.argv[1], hidden=sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "hidden"),
              as_nobody=os.geteuid() == 0 and shutil.which("setpriv") is not None)
    for k, v in r["packages"].items():
        print("%-22s wrong %2d  %s" % (k, v["wrong"], v.get("error", "")))
    print("%d of %d turbines wrong: %s" % (r["wrong"], r["turbines"], "accepted" if r["accepted"] else "rejected"))
