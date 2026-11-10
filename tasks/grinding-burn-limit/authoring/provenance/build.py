"""Writes every data file of the bundle from the sealed definitions (jobs.py) and the documents (docs_grind.py):

    python3 authoring/provenance/build.py [BUNDLE_ROOT]

- environment/data: the standard MS-GB, the grinding data, the package format and the example job job-ex (the
  agent's /app/data);
- tests/app_data: the same files, for the verifier's read-only /app/data;
- tests/hidden: the seven hidden jobs' packages, and truth.json with each job's burn-limited depth and the operation
  as it will run (wheel, coolant, power model, speed, coolant temperature, burn limit).
The definitions are fixed and the generation is seeded, so a rebuild writes the same files."""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jobs as Jm
import docs_grind as Dg


def write_agent_data(root):
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, "docs")); os.makedirs(os.path.join(root, "examples"))
    open(os.path.join(root, "docs", "ms_gb_grinding_burn.md"), "w").write(Dg.STANDARD)
    open(os.path.join(root, "docs", "grinding_data.md"), "w").write(Dg.DATA)
    open(os.path.join(root, "docs", "package_format.md"), "w").write(Dg.FORMAT)
    Dg.write(Jm.BY[Jm.EXAMPLE], os.path.join(root, "examples", Jm.EXAMPLE))


def main(bundle):
    write_agent_data(os.path.join(bundle, "environment", "data"))
    write_agent_data(os.path.join(bundle, "tests", "app_data"))
    hid = os.path.join(bundle, "tests", "hidden")
    shutil.rmtree(hid, ignore_errors=True); os.makedirs(hid)
    truth = {}
    for name in Jm.HIDDEN:
        j = Jm.BY[name]
        Dg.write(j, os.path.join(hid, name))
        _, wheel, coolant, _ = Jm.current(j)
        truth[name] = dict(max_depth_um=round(Jm.limit(j), 4),
                           job=dict(wheel=wheel, coolant=coolant, power_model=Jm.PM[(wheel, coolant)], Rw=Jm.RW[(wheel, coolant)],
                                    work_speed_mm_s=round(j["v"], 4), coolant_C=j["T0"], width_mm=j["b"], diameter_mm=j["d_now"],
                                    interval_mm3_mm=j["interval"], burn_limit_C=max(j["certs"][j["lot"]]) + 200))
    with open(os.path.join(hid, "truth.json"), "w") as fh:
        json.dump(truth, fh, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(HERE, "..", "..")))
