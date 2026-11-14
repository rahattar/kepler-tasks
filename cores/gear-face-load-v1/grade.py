"""grade.py PROGRAM [LIMIT_S] [DIR]: run the program on every hidden pair under the limit and compare."""
import csv, os, resource, shutil, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
TOL = {"k_face": 0.015, "sigma_H_MPa": 0.015}


def main(argv):
    program = argv[1]
    limit = float(argv[2]) if len(argv) > 2 else 10.0
    hid = argv[3] if len(argv) > 3 else os.path.join(HERE, "core", "hidden")
    ok_all = True
    for tag in sorted(os.listdir(hid)):
        case = os.path.join(hid, tag)
        truthf = os.path.join(case, "truth.csv") if os.path.exists(os.path.join(case, "truth.csv")) else os.path.join(case, "expected.csv")
        box = tempfile.mkdtemp(prefix="gf_")
        shutil.copy(program, os.path.join(box, "faceload.py"))
        os.makedirs(os.path.join(box, "pkg"))
        for f in ("pair.json", "lead_charts.csv", "duty.csv"):
            shutil.copy(os.path.join(case, f), os.path.join(box, "pkg"))
        env = dict(PATH=os.environ["PATH"], OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        soft = int(limit) + 2
        ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        status = "ran"
        try:
            p = subprocess.run([sys.executable, "faceload.py", "pkg", "out.csv"], cwd=box, env=env, capture_output=True,
                               text=True, timeout=4 * limit,
                               preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CPU, (soft, soft + 3)))
            if p.returncode != 0:
                status = "exit %d: %s" % (p.returncode, (p.stderr.strip().splitlines() or ["?"])[-1][:70])
        except subprocess.TimeoutExpired:
            status = "timed out"
        ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = ru1.ru_utime + ru1.ru_stime - ru0.ru_utime - ru0.ru_stime
        if status == "ran" and cpu > limit:
            status = "over the limit"
        bad, n, worst = 0, 0, 0.0
        if status == "ran":
            truth = {r["point"]: r for r in csv.DictReader(open(truthf))}
            try:
                got = {r["point"]: r for r in csv.DictReader(open(os.path.join(box, "out.csv")))}
            except Exception:
                got = {}
            for k, tr in truth.items():
                n += 1
                miss = False
                for q, tol in TOL.items():
                    try:
                        e = abs(float(got[k][q]) / float(tr[q]) - 1)
                    except Exception:
                        e = 9.9
                    worst = max(worst, e / tol)
                    miss |= e > tol
                bad += miss
        ok = status == "ran" and bad == 0
        ok_all &= ok
        print("%-5s %-5s cpu %5.1f s  %5d of %5d points out  worst/band %.2f  %s" % ("ok" if ok else "FAIL", tag, cpu, bad, n, worst, status), flush=True)
        shutil.rmtree(box, ignore_errors=True)
    print("ACCEPTED" if ok_all else "NOT ACCEPTED")


if __name__ == "__main__":
    main(sys.argv)
