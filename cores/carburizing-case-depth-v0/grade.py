"""grade.py PROGRAM [LIMIT_S] [DIR]: run the program on every furnace under the CPU limit and compare."""
import csv, os, resource, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
D_TOL, C_TOL = 0.02, 0.02          # case depth within 2 per cent, surface carbon within 0.02 %C


def main(argv):
    program = argv[1]
    limit = float(argv[2]) if len(argv) > 2 else 20.0
    hid = argv[3] if len(argv) > 3 else os.path.join(HERE, "core", "hidden")
    ok_all = True
    for tag in sorted(os.listdir(hid)):
        case = os.path.join(hid, tag)
        truthf = os.path.join(case, "truth.csv")
        if not os.path.exists(truthf):
            truthf = os.path.join(case, "expected.csv")
        box = tempfile.mkdtemp(prefix="cd_")
        shutil.copy(program, os.path.join(box, "casedepth.py"))
        os.makedirs(os.path.join(box, "pkg"))
        for f in ("furnace.json", "loads.csv", "record.csv"):
            shutil.copy(os.path.join(case, f), os.path.join(box, "pkg"))
        env = dict(PATH=os.environ["PATH"], OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        soft = int(limit) + 2
        ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        status = "ran"
        try:
            p = subprocess.run([sys.executable, "casedepth.py", "pkg", "out.csv"], cwd=box, env=env, capture_output=True,
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
        bad, n, wd, wc = 0, 0, 0.0, 0.0
        if status == "ran":
            truth = {r["load"]: r for r in csv.DictReader(open(truthf))}
            try:
                got = {r["load"]: r for r in csv.DictReader(open(os.path.join(box, "out.csv")))}
            except Exception:
                got = {}
            for k, tr in truth.items():
                n += 1
                try:
                    ed = abs(float(got[k]["case_depth_mm"]) / float(tr["case_depth_mm"]) - 1)
                    ec = abs(float(got[k]["surface_C_pct"]) - float(tr["surface_C_pct"]))
                except Exception:
                    ed = ec = 9.9
                wd, wc = max(wd, ed / D_TOL), max(wc, ec / C_TOL)
                bad += (ed > D_TOL) or (ec > C_TOL)
        ok = status == "ran" and bad == 0
        ok_all &= ok
        print("%-5s %-5s cpu %5.1f s  %3d of %3d loads out  worst depth/band %.2f  surface/band %.2f  %s"
              % ("ok" if ok else "FAIL", tag, cpu, bad, n, wd, wc, status), flush=True)
        shutil.rmtree(box, ignore_errors=True)
    print("ACCEPTED" if ok_all else "NOT ACCEPTED")


if __name__ == "__main__":
    main(sys.argv)
