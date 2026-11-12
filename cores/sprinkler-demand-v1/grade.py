"""Grades a re-rating program on the hidden packages: every package inside the CPU limit and the tolerance.

    python3 grade.py PROGRAM [SET]        SET is `hidden` (default) or `examples`

Each run takes place in a scratch directory holding a copy of the program and of the package (system.json and
campaign.csv only). The limit is on the run's CPU time (user + system); the kernel stops the program a little
past it, and a wall-clock safeguard stops one that sleeps.
"""
import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
P_TOL = 0.03
Q_TOL = 0.03
CPU_LIMIT_S = 20.0
WALL_GUARD_S = 300.0


def run(program, pkg_dir, cpu_limit=CPU_LIMIT_S):
    work = tempfile.mkdtemp(prefix="sprk-")
    prog = os.path.join(work, os.path.basename(program))
    shutil.copy(program, prog)
    pkg = os.path.join(work, "package")
    os.makedirs(pkg)
    for name in ("system.json", "campaign.csv"):
        shutil.copy(os.path.join(pkg_dir, name), pkg)
    out = os.path.join(work, "result.json")
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    soft = int(cpu_limit) + 2

    def cap():
        resource.setrlimit(resource.RLIMIT_CPU, (soft, soft + 3))

    t0 = time.time()
    ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    status = "done"
    try:
        subprocess.run([sys.executable, prog, pkg, out], cwd=work, env=env, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=cap, timeout=WALL_GUARD_S)
    except subprocess.TimeoutExpired:
        status = "timeout"
    ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (ru1.ru_utime - ru0.ru_utime) + (ru1.ru_stime - ru0.ru_stime)
    result = None
    if status == "done" and cpu > cpu_limit:
        status = "over cpu limit"
    elif status == "done":
        try:
            with open(out) as f:
                result = json.load(f)
        except (OSError, ValueError):
            status = "no result"
    shutil.rmtree(work, ignore_errors=True)
    return dict(status=status, result=result, cpu_s=cpu, wall_s=time.time() - t0)


def main(argv):
    program = os.path.abspath(argv[1])
    which = argv[2] if len(argv) > 2 else "hidden"
    root = os.path.join(HERE, "core", "hidden") if which == "hidden" else os.path.join(HERE, "core", "data", "examples")
    ok_all = True
    for tag in sorted(os.listdir(root)):
        d = os.path.join(root, tag)
        with open(os.path.join(d, "truth.json" if which == "hidden" else "expected.json")) as f:
            tr = json.load(f)
        tr = tr.get("result", tr)
        r = run(program, d)
        line = "%-5s %-14s cpu %5.1f s" % (tag, r["status"], r["cpu_s"])
        ok = False
        if r["status"] == "done":
            try:
                dp = r["result"]["pressure_psi"] / tr["pressure_psi"] - 1
                dq = r["result"]["flow_gpm"] / tr["flow_gpm"] - 1
                ok = abs(dp) <= P_TOL and abs(dq) <= Q_TOL
                line += "  P %+6.2f%%  Q %+6.2f%%" % (100 * dp, 100 * dq)
                if "let_go" in r["result"]:
                    line += "  " + "; ".join(r["result"]["let_go"])
            except (KeyError, TypeError, ZeroDivisionError):
                line += "  result lacks pressure_psi or flow_gpm"
        print(("ok    " if ok else "FAIL  ") + line, flush=True)
        ok_all &= ok
    print("ACCEPTED" if ok_all else "REJECTED")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
