"""Runs a submitted GT-1 reduction program on the hidden record sets and compares its results with the sealed values.

Each hidden record set (hidden/<name>/) is copied to a scratch directory, and the program is run there as the
unprivileged user nobody, with no environment, as `python3 -I gtperf.py <set> <out.csv>`, with a time limit. The
sealed values (hidden/truth.json) stay in this directory, which only root can read. A set is accepted when the program
exits normally and writes corrected_output_mw and corrected_heat_rate_kj_kwh, both finite and within LIMIT of the
sealed values, relative.
"""
import csv
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIMIT = 0.003            # relative (0.3 %), from the requirement
TIME_LIMIT_S = 300
NOBODY = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "--inh-caps=-all"]


def run_one(program, set_dir, as_nobody=True):
    work = tempfile.mkdtemp(prefix="gtperf_")
    os.chmod(work, 0o755)
    try:
        shutil.copy(program, os.path.join(work, "gtperf.py"))
        shutil.copytree(set_dir, os.path.join(work, "set"))
        outdir = os.path.join(work, "out")
        os.makedirs(outdir)
        os.chmod(outdir, 0o777)
        for top, dirs, files in os.walk(work):
            for n in dirs:
                os.chmod(os.path.join(top, n), 0o755 if top != work or n != "out" else 0o777)
            for n in files:
                os.chmod(os.path.join(top, n), 0o644)
        out = os.path.join(outdir, "result.csv")
        cmd = [sys.executable, "-I", os.path.join(work, "gtperf.py"), os.path.join(work, "set"), out]
        if as_nobody:
            cmd = NOBODY + cmd
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": work, "OMP_NUM_THREADS": "2"}
        p = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, timeout=TIME_LIMIT_S)
        if p.returncode != 0:
            return None, "exit status %d: %s" % (p.returncode, p.stderr.strip()[-300:])
        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 1:
            return None, "expected one result row, found %d" % len(rows)
        v = (float(rows[0]["corrected_output_mw"]), float(rows[0]["corrected_heat_rate_kj_kwh"]))
        if not all(math.isfinite(x) and x > 0 for x in v):
            return None, "results must be finite positive numbers"
        return v, None
    except subprocess.TimeoutExpired:
        return None, "time limit of %d s exceeded" % TIME_LIMIT_S
    except Exception as e:                           # missing or malformed output
        return None, repr(e)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def score(program, hidden=os.path.join(HERE, "hidden"), as_nobody=True):
    truth = json.load(open(os.path.join(hidden, "truth.json")))
    sets = {}
    for name in sorted(truth):
        v, err = run_one(program, os.path.join(hidden, name), as_nobody)
        if err:
            sets[name] = {"accepted": False, "error": err}
            continue
        mo = v[0] / truth[name]["output_mw"] - 1.0
        mh = v[1] / truth[name]["heat_rate"] - 1.0
        sets[name] = {"output_mw": v[0], "heat_rate": v[1], "output_miss": round(mo, 5), "heat_rate_miss": round(mh, 5),
                      "accepted": bool(abs(mo) <= LIMIT and abs(mh) <= LIMIT)}
    return {"accepted": all(s["accepted"] for s in sets.values()), "sets": sets}


if __name__ == "__main__":
    r = score(sys.argv[1], as_nobody=os.geteuid() == 0)
    for k, v in r["sets"].items():
        print(k, "ok " if v["accepted"] else "BAD", v.get("error") or "output %+.2f %%  heat rate %+.2f %%"
              % (100 * v["output_miss"], 100 * v["heat_rate_miss"]))
    print("accepted" if r["accepted"] else "rejected")
