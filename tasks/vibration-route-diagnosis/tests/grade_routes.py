"""Runs a submitted route diagnosis program on the hidden route packages and compares its diagnoses with the sealed
ones.

Each hidden route package (hidden/<route>/) is copied to a scratch directory, and the program is run there as the
unprivileged user nobody, with no environment, as `python3 -I diagnose.py <route> <out.csv>`, with a time limit. The
sealed diagnoses (hidden/truth.json) stay in this directory, which only root can read. A machine counts as correct
when its row has the sealed condition code and component (case and surrounding spaces ignored). A machine with no
row, and every machine of a route on which the program fails, counts as wrong. The submission is accepted when at
most MAX_WRONG of the hidden machines are wrong.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_WRONG = 2            # of 60 hidden machines, from the requirement (at least 58 correct)
TIME_LIMIT_S = 300
NOBODY = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "--inh-caps=-all"]


def run_one(program, route_dir, as_nobody=True):
    work = tempfile.mkdtemp(prefix="diag_")
    os.chmod(work, 0o755)
    try:
        shutil.copy(program, os.path.join(work, "diagnose.py"))
        shutil.copytree(route_dir, os.path.join(work, "route"))
        outdir = os.path.join(work, "out")
        os.makedirs(outdir)
        for top, dirs, files in os.walk(work):
            for n in dirs:
                os.chmod(os.path.join(top, n), 0o755)
            for n in files:
                os.chmod(os.path.join(top, n), 0o644)
        os.chmod(outdir, 0o777)
        out = os.path.join(outdir, "result.csv")
        cmd = [sys.executable, "-I", os.path.join(work, "diagnose.py"), os.path.join(work, "route"), out]
        if as_nobody:
            cmd = NOBODY + cmd
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": work, "OMP_NUM_THREADS": "2"}
        p = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, timeout=TIME_LIMIT_S)
        if p.returncode != 0:
            return None, "exit status %d: %s" % (p.returncode, p.stderr.strip()[-300:])
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        got = {}
        for r in rows:
            got[(r.get("machine") or "").strip()] = ((r.get("fault") or "").strip().upper(),
                                                     (r.get("component") or "").strip().lower())
        return got, None
    except subprocess.TimeoutExpired:
        return None, "time limit of %d s exceeded" % TIME_LIMIT_S
    except Exception as e:                           # missing or malformed output
        return None, repr(e)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def score(program, hidden=os.path.join(HERE, "hidden"), as_nobody=True):
    truth = json.load(open(os.path.join(hidden, "truth.json")))
    routes, wrong, total = {}, 0, 0
    for name in sorted(truth):
        got, err = run_one(program, os.path.join(hidden, name), as_nobody)
        n = len(truth[name])
        total += n
        if err:
            routes[name] = {"error": err, "wrong": n}
            wrong += n
            continue
        bad = {m: {"expected": list(t), "got": list(got.get(m, ("", "")))} for m, t in truth[name].items()
               if got.get(m) != (t[0], t[1])}
        routes[name] = {"wrong": len(bad), "machines": len(truth[name])}
        wrong += len(bad)
        routes[name]["misdiagnosed"] = bad
    return {"accepted": wrong <= MAX_WRONG, "wrong": wrong, "machines": total, "routes": routes}


if __name__ == "__main__":
    r = score(sys.argv[1], as_nobody=os.geteuid() == 0)
    for k, v in r["routes"].items():
        print(k, v.get("error") or "%d wrong %s" % (v["wrong"], json.dumps(v["misdiagnosed"])))
    print("%d of %d wrong: %s" % (r["wrong"], r["machines"], "accepted" if r["accepted"] else "rejected"))
