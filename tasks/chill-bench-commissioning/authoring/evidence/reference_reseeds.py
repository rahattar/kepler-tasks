"""Runs the ACTUAL reference across redrawn instances and grades each one.

Each instance is independent: its own seeded fleet, its own bench service on its own
port, its own budget. solve.py buys its eight runs through the same client an agent
uses and never sees the sealed parameters.

    python3 reference_reseeds.py [N] [PARALLEL] [FIRST]

The reseed redraws only the per-station scatter the covariate model cannot explain.
The fleet geometry, roughness, lots and bath temperatures are fixed constants of the
shipped design, so this measures the policy's robustness to the residual it cannot
model, not to a wholly new fleet.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = "/tmp/refseeds2"
BASE = 20260919


def wait_ready(port, timeout=40):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/status", timeout=3):
                return True
        except Exception:
            time.sleep(1)
    return False


def one(idx, seed):
    port = 9500 + idx
    wd = os.path.join(OUT, f"s{seed}")
    os.makedirs(os.path.join(wd, "app"), exist_ok=True)
    env = dict(os.environ, FLEET_SEED=str(seed), BENCH_PORT=str(port))
    srv = subprocess.Popen([sys.executable, "server.py"],
                           cwd=os.path.join(ROOT, "environment", "bench"), env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_ready(port):
            return seed, "bench never came up"
        for flag, dest in (("--emit-data", os.path.join(wd, "data")),
                           ("--emit-truth", os.path.join(wd, "truth.json"))):
            subprocess.run([sys.executable,
                            os.path.join(ROOT, "authoring", "provenance",
                                         "make_fleet.py"), flag, dest],
                           env=env, capture_output=True, timeout=120)
        client = os.path.join(wd, "bench.py")
        src = open(os.path.join(ROOT, "environment", "bench.py")).read()
        open(client, "w").write(src.replace("http://bench:8000",
                                            f"http://127.0.0.1:{port}"))
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "solution", "solve.py")], cwd=wd,
            env=dict(env, BENCH_URL=f"http://127.0.0.1:{port}",
                     CHILL_DATA=os.path.join(wd, "data"),
                     CHILL_RECIPE=os.path.join(wd, "app", "recipe.json"),
                     CHILL_BENCH=client),
            capture_output=True, text=True, timeout=1500)
        if r.returncode != 0:
            return seed, f"solve exited {r.returncode}: {r.stderr.strip()[:80]}"
    except subprocess.TimeoutExpired:
        return seed, "solve timed out"
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=10)
        except Exception:
            srv.kill()

    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import grade
    p = os.path.join(wd, "app", "recipe.json")
    if not os.path.exists(p):
        return seed, "no recipe written"
    res = grade.grade(p, json.load(open(os.path.join(wd, "truth.json"))))
    if res["error"]:
        return seed, f"grader: {res['error'][:70]}"
    rr = [s["dwell_ratio"] for s in res["stations"]]
    return seed, {
        "reward": res["reward"], "commissioned": res["commissioned"],
        "max_ratio": round(max(rr), 4),
        "worst_zone": round(max(s["zone_diff_K"] for s in res["stations"]), 3),
        "hottest": round(max(s["T_end_C"] for s in res["stations"]), 3),
    }


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    par = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    first = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    os.makedirs(OUT, exist_ok=True)
    jobs = [(first + i, BASE + 1000 * (first + i)) for i in range(n)]
    print("the real reference across %d redrawn instances, %d at a time\n" % (n, par))
    print("       seed  reward  commissioned  max ratio  worst zone  hottest")
    rows = []
    with ThreadPoolExecutor(max_workers=par) as ex:
        futs = [ex.submit(one, *a) for a in jobs]
        # as_completed, not map: map yields in submission order, so one slow instance
        # holds back every finished one behind it and the run looks wedged.
        for fut in as_completed(futs):
            seed, r = fut.result()
            if isinstance(r, str):
                print("  %9d  %s" % (seed, r), flush=True)
                continue
            rows.append(r)
            print("  %9d %6d  %9d/16  %9.3f  %10.2f  %7.2f"
                  % (seed, r["reward"], r["commissioned"], r["max_ratio"],
                     r["worst_zone"], r["hottest"]), flush=True)
    if rows:
        ok = sum(r["reward"] for r in rows)
        mr = [r["max_ratio"] for r in rows]
        print("\n  reference passed %d of %d instances" % (ok, len(rows)))
        print("  max dwell ratio: best %.3f  worst %.3f  (limit 1.080)"
              % (min(mr), max(mr)))
        print("  worst zone difference %.2f K (limit 25.0), hottest %.2f C (limit 50.0)"
              % (max(r["worst_zone"] for r in rows), max(r["hottest"] for r in rows)))
    with open(os.path.join(HERE, "reference_reseeds.json"), "w") as f:
        json.dump(rows, f, indent=1)


if __name__ == "__main__":
    main()
