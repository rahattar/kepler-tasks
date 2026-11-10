"""Writes every data file of the bundle from the sealed definitions (jobs.py) and the documents (docs_vac.py):

    python3 authoring/provenance/build.py [BUNDLE_ROOT]

- environment/data: the standard MS-VP, the vacuum data, the package format and the example chamber chamber-ex (the
  agent's /app/data);
- tests/app_data: the same files, for the verifier's read-only /app/data;
- tests/hidden: the seven hidden chambers' packages, and truth.json with each job's pump-down time and the chamber's
  true state on the job's date.
The definitions are fixed and the generation is seeded, so a rebuild writes the same files."""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jobs as Jm
import docs_vac as Dv


def write_agent_data(root):
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, "docs")); os.makedirs(os.path.join(root, "examples"))
    open(os.path.join(root, "docs", "ms_vp_pumpdown.md"), "w").write(Dv.STANDARD)
    open(os.path.join(root, "docs", "vacuum_data.md"), "w").write(Dv.DATA)
    open(os.path.join(root, "docs", "package_format.md"), "w").write(Dv.FORMAT)
    Dv.write(Jm.BY[Jm.EXAMPLE], os.path.join(root, "examples", Jm.EXAMPLE))


def main(bundle):
    write_agent_data(os.path.join(bundle, "environment", "data"))
    write_agent_data(os.path.join(bundle, "tests", "app_data"))
    hid = os.path.join(bundle, "tests", "hidden")
    shutil.rmtree(hid, ignore_errors=True); os.makedirs(hid)
    truth = {}
    for name in Jm.HIDDEN:
        ch = Jm.BY[name]
        Dv.write(ch, os.path.join(hid, name))
        c = Jm.config(ch, ch["job"]["date"])
        truth[name] = dict(pumpdown_min=round(Jm.truth(ch), 4),
                           chamber=dict(V_l=round(c["V"], 2), rough=c["rough"], line_cm=[c["D"], c["L"]], turbo=c["turbo"],
                                        p_x=c["p_x"], wall=list(c["wall"]), leak=c["leak"]))
    with open(os.path.join(hid, "truth.json"), "w") as fh:
        json.dump(truth, fh, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(HERE, "..", "..")))
