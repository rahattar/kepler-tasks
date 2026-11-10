"""The reference end to end on redrawn instances: new seeds for the graded weeks' weather, occupancy,
forecast errors and sensor noise, and for the logged period's occupancy, forecasts and noise. For each:
regenerate the public data, fit the reference from it, recompute the benchmark, grade.

  python3 reference_reseeds.py 0 1 2 3      # 0 is the shipped instance; about 12 min per instance
reference_reseeds.txt holds the recorded output. The allowance (1.15) was fixed from these before any
other controller was graded: the smallest 0.05 step at least 0.03 above the reference's worst total.
"""
import os, sys, json, subprocess, tempfile, contextlib, io
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C

print(f"{'instance':>8s} {'bench $':>8s} {'ref $':>8s} {'ratio':>6s} {'fails':>5s} {'worst K h':>9s} {'gate':>5s}")
for j in map(int, sys.argv[1:]):
    seeds = C.reseed(j)
    d = tempfile.mkdtemp()
    import make_public
    with contextlib.redirect_stdout(io.StringIO()):
        make_public.main(seeds=seeds, out=os.path.join(d, "data"))
    ref = C.fit_reference(os.path.join(d, "data"), os.path.join(d, "ref.py"))
    tag = f"reseed{j}"
    subprocess.run([sys.executable, os.path.join(C.PROV, "run_bench.py"), tag, "0.3", "1", "1", "1", "1",
                    json.dumps(seeds)], check=True, stdout=subprocess.DEVNULL)
    bfile = os.path.join(C.PROV, f"bench_{tag}.json")
    bench = json.load(open(bfile))["cost"]
    os.remove(bfile)
    r = C.grade_inprocess(ref, bench, seeds)
    print(f"{j:8d} {sum(bench):8.3f} {sum(r['week_cost']):8.3f} {r['ratio']:6.3f} {r['fails']:5d} "
          f"{r['worst_dev']:9.2f} {'pass' if r['passed'] else 'fail':>5s}", flush=True)
