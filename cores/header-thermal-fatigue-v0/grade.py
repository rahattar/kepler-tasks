"""grade.py PROGRAM [LIMIT_S] [DIR] [--report]: run the program on every header under the CPU limit and compare."""
import csv, os, resource, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
R_TOL, D_TOL, R_FLOOR = 0.03, 0.08, 120.0   # each event range of 120 MPa or more within 3 %; total damage within 8 %


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    report = "--report" in argv
    program = args[0]
    limit = float(args[1]) if len(args) > 1 else 6.0
    hid = args[2] if len(args) > 2 else os.path.join(HERE, "core", "hidden")
    ok_all = True
    for tag in sorted(os.listdir(hid)):
        case = os.path.join(hid, tag)
        truthf = os.path.join(case, "truth.csv")
        if not os.path.exists(truthf):
            truthf = os.path.join(case, "expected.csv")
        box = tempfile.mkdtemp(prefix="hf_")
        shutil.copy(program, os.path.join(box, "fatigue.py"))
        os.makedirs(os.path.join(box, "pkg"))
        for f in ("header.json", "record.csv"):
            shutil.copy(os.path.join(case, f), os.path.join(box, "pkg"))
        env = dict(PATH=os.environ["PATH"], OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        soft = int(limit) + 2
        ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        status = "ran"
        try:
            p = subprocess.run([sys.executable, "fatigue.py", "pkg", "out.csv"], cwd=box, env=env, capture_output=True,
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
        bad, n, wr, wd = 0, 0, 0.0, 0.0
        if status == "ran":
            truth = {r["event"]: r for r in csv.DictReader(open(truthf))}
            try:
                got = {r["event"]: r for r in csv.DictReader(open(os.path.join(box, "out.csv")))}
            except Exception:
                got = {}
            Dt, Dg = 0.0, 0.0
            for k, tr in truth.items():
                Dt += float(tr["damage"])
                try:
                    Dg += float(got[k]["damage"])
                    rt = float(tr["range_max_MPa"])
                    er = abs(float(got[k]["range_max_MPa"]) / rt - 1) if rt >= R_FLOOR else 0.0
                except Exception:
                    er = 9.9
                if rt >= R_FLOOR:
                    n += 1
                wr = max(wr, er / R_TOL)
                bad += er > R_TOL
            wd = abs(Dg / Dt - 1) / D_TOL
            bad += wd > 1
        ok = status == "ran" and bad == 0
        ok_all &= ok
        print("%-5s %-5s cpu %5.2f s  %2d out (of %2d ranges + total damage)  worst range/band %.2f  total damage/band %.2f  %s"
              % ("ok" if ok else "FAIL", tag, cpu, bad, n, wr, wd, status), flush=True)
        shutil.rmtree(box, ignore_errors=True)
    print("ACCEPTED" if ok_all else "NOT ACCEPTED")


if __name__ == "__main__":
    main(sys.argv)
