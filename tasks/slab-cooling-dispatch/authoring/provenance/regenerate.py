"""Regenerate every shipped data file from the disclosed generator and its fixed seeds, and compare.

  python3 authoring/provenance/regenerate.py          # agent data only (about 10 s)
  python3 authoring/provenance/regenerate.py --bench  # also the benchmark costs (about 7 min)

The generator is the sealed simulator in tests/ (weather.py, wx.py, zone.py, chiller.py, instance.py,
sim.py, world.py) driven by world.SEEDS. Weather is real: Chicago O'Hare TMY3 (NREL, from the
EnergyPlus repository, tests/chicago_tmy3.epw, md5 4c7bb1655aa251a7420514c9e7512310); the graded weeks
use days of that file resampled within +/-10 days and offset by a seeded day-to-day temperature
anomaly (wx.py), so the graded weather is not the public file."""
import hashlib, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests")); sys.path.insert(0, HERE)


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


tmp = tempfile.mkdtemp()
import make_public
make_public.main(out=tmp)
ok = True
for f in sorted(os.listdir(os.path.join(ROOT, "environment", "data"))):
    a, b = md5(os.path.join(tmp, f)), md5(os.path.join(ROOT, "environment", "data", f))
    print(("same     " if a == b else "DIFFERS  ") + f)
    ok &= a == b
print("epw md5", md5(os.path.join(ROOT, "tests", "chicago_tmy3.epw")))
if "--bench" in sys.argv:
    subprocess.run([sys.executable, os.path.join(HERE, "run_bench.py"), "regen", "0.3"], check=True)
    a = json.load(open(os.path.join(HERE, "bench_regen.json")))["cost"]
    b = json.load(open(os.path.join(ROOT, "tests", "bench.json")))["cost"]
    same = all(abs(x - y) < 1e-9 for x, y in zip(a, b))
    print(("same     " if same else "DIFFERS  ") + "tests/bench.json weekly costs")
    ok &= same
print("ALL REPRODUCED" if ok else "MISMATCH")
