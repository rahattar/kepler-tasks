"""Writes every data file of the bundle from the sealed definitions (jobs.py) and the documents (docs_job.py):

    python3 authoring/provenance/build.py [BUNDLE_ROOT]

- environment/data: the standard MS-CH, the cutting coefficients, the package format and the example job job-ex
  (the agent's /app/data);
- tests/app_data: the same files, for the verifier's read-only /app/data;
- tests/hidden: the seven hidden jobs' packages, and truth.json with each job's stability limit and the job as it
  will be cut (speed, teeth, immersion, true modes).
The definitions are fixed and the generation is seeded, so a rebuild writes the same files."""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jobs as Jm
import docs_job as Dj


def write_agent_data(root):
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, "docs")); os.makedirs(os.path.join(root, "examples"))
    open(os.path.join(root, "docs", "ms_ch_milling_stability.md"), "w").write(Dj.STANDARD)
    open(os.path.join(root, "docs", "cutting_coefficients.md"), "w").write(Dj.COEFFS)
    open(os.path.join(root, "docs", "package_format.md"), "w").write(Dj.FORMAT)
    Dj.write(Jm.BY[Jm.EXAMPLE], os.path.join(root, "examples", Jm.EXAMPLE))


def main(bundle):
    write_agent_data(os.path.join(bundle, "environment", "data"))
    write_agent_data(os.path.join(bundle, "tests", "app_data"))
    hid = os.path.join(bundle, "tests", "hidden")
    shutil.rmtree(hid, ignore_errors=True); os.makedirs(hid)
    truth = {}
    for name in Jm.HIDDEN:
        j = Jm.BY[name]
        Dj.write(j, os.path.join(hid, name))
        truth[name] = dict(stable_depth_mm=round(Jm.truth(j) * 1000, 4),
                           job=dict(speed_rpm=Jm.run_speed(j), teeth=j["inserts"] or j["teeth"], D=j["D"], ae=j["ae"],
                                    milling=j["milling"], feed=j["feed"], material=j["material"], modes=j["modes"]))
    with open(os.path.join(hid, "truth.json"), "w") as fh:
        json.dump(truth, fh, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(HERE, "..", "..")))
