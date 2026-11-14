import csv, sys, os, time, subprocess, resource
prog, d = sys.argv[1], sys.argv[2]
out = "/tmp/cmp_out.csv"
t = time.time()
r0 = resource.getrusage(resource.RUSAGE_CHILDREN)
p = subprocess.run([sys.executable, prog, d, out], capture_output=True, text=True)
r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
cpu = (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
if p.returncode: print(p.stderr[-800:]); sys.exit(1)
exp = os.path.join(d, "expected.csv") if os.path.exists(os.path.join(d, "expected.csv")) else os.path.join(os.path.dirname(d), "_result_%s.csv" % os.path.basename(d))
a = {r["point"]: float(r["value"]) for r in csv.DictReader(open(exp))}
b = {r["point"]: float(r["value"]) for r in csv.DictReader(open(out))}
worst = max(abs(a[k] - b[k]) / (0.01 if k.endswith("-T") else max(1e-4 * abs(a[k]), 0.01)) for k in a)
print("%-14s %5.1f s wall %5.1f s cpu  points %6d  worst %.3f of the band" % (os.path.basename(d), time.time() - t, cpu, len(a), worst))
