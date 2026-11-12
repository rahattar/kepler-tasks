"""Runs a demand program on one package, answering its one field test from the package's truth, under the
per-run limit. Used by grade.py (hidden packages) and by the agent-visible fieldtest tool (examples, answered from
their survey).

    python3 harness.py PROGRAM PACKAGE_DIR TRUTH_JSON [SEED] [LIMIT_S]
"""
import json
import os
import random
import resource
import selectors
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hyd                                                   # noqa: E402

LIMIT_S = 75.0          # wall-clock safeguard for the agent-visible tool
CPU_LIMIT_S = 60.0      # the brief's limit: CPU time (user + system) of the run


def run(program, pkg_dir, truth, seed=1, limit=LIMIT_S, cpu_limit=CPU_LIMIT_S):
    """Returns dict(status=..., result=..., cpu_s=..., wall_s=..., test=..., report=...).

    The kernel stops the program a little past cpu_limit seconds of CPU; limit is a wall-clock safeguard
    that should be set well above cpu_limit on a shared machine. A run that finishes but used more than
    cpu_limit seconds of CPU has status "over cpu limit"."""
    with open(os.path.join(pkg_dir, "system.json")) as f:
        system = json.load(f)
    rng = random.Random(seed)
    work = tempfile.mkdtemp(prefix="sprk-")
    prog = os.path.join(work, os.path.basename(program))
    shutil.copy(program, prog)
    pkg_copy = os.path.join(work, "package")
    os.makedirs(pkg_copy)
    shutil.copy(os.path.join(pkg_dir, "system.json"), pkg_copy)
    out = os.path.join(work, "result.json")
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    t0 = time.time()
    ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    soft = int(cpu_limit) + 2

    def _cap():
        resource.setrlimit(resource.RLIMIT_CPU, (soft, soft + 3))

    proc = subprocess.Popen([sys.executable, prog, pkg_copy, out], cwd=work, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, text=True, bufsize=1,
                            preexec_fn=_cap)
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ)
    tests = []
    reports = []
    status = None
    buf = ""
    while True:
        left = limit - (time.time() - t0)
        if left <= 0:
            proc.kill()
            status = "timeout"
            break
        ev = sel.select(timeout=min(left, 1.0))
        if not ev:
            if proc.poll() is not None:
                break
            continue
        line = proc.stdout.readline()
        if line == "":
            if proc.poll() is not None:
                break
            continue
        line = line.strip()
        if not line.startswith("TEST "):
            continue
        try:
            req = json.loads(line[5:])
        except ValueError:
            req = None
        if tests:
            rep = {"refused": "the one field test has been spent"}
        elif not isinstance(req, dict):
            rep = {"refused": "the request is not a JSON object"}
        else:
            rep = hyd.field_test(system, truth, req, rng)
        tests.append(req)
        reports.append(rep)
        try:
            proc.stdin.write(json.dumps(rep) + "\n")
            proc.stdin.flush()
        except BrokenPipeError:
            pass
    proc.wait()
    ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (ru1.ru_utime - ru0.ru_utime) + (ru1.ru_stime - ru0.ru_stime)
    wall = time.time() - t0
    result = None
    if status != "timeout" and cpu > cpu_limit:
        status = "over cpu limit"
    elif status != "timeout":
        if os.path.exists(out):
            try:
                with open(out) as f:
                    result = json.load(f)
                status = "done"
            except ValueError:
                status = "unreadable result"
        else:
            status = "no result"
    shutil.rmtree(work, ignore_errors=True)
    return dict(status=status, result=result, cpu_s=cpu, wall_s=wall, tests=tests, reports=reports)


if __name__ == "__main__":
    program, pkg = sys.argv[1], sys.argv[2]
    with open(sys.argv[3]) as f:
        truth = json.load(f)
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    limit = float(sys.argv[5]) if len(sys.argv) > 5 else LIMIT_S
    print(json.dumps(run(program, pkg, truth, seed, limit=max(limit, CPU_LIMIT_S)), indent=1))
