"""CPU time of the naive version on hidden packages, stopped by the kernel at CAP seconds.
Usage: python3 time_naive.py CAP TAG [TAG ...]"""
import os
import resource
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
cap = int(sys.argv[1])
for tag in sys.argv[2:]:
    ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    p = subprocess.run([sys.executable, os.path.join(HERE, "naive_rerate.py"),
                        os.path.join(HERE, "core", "hidden", tag), "/tmp/naive_%s.json" % tag],
                       stderr=subprocess.DEVNULL, env=dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1"),
                       preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CPU, (cap, cap + 2)))
    ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = ru1.ru_utime - ru0.ru_utime + ru1.ru_stime - ru0.ru_stime
    print("%s  naive: %s after %.0f s of CPU" % (tag, "finished" if p.returncode == 0 else "stopped", cpu), flush=True)
