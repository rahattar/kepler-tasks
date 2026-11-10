"""Writes every data file of the bundle from the sealed definitions (jobs.py) and the documents (docs_weld.py):

    python3 authoring/provenance/build.py [BUNDLE_ROOT]

- environment/data: the standard MS-PH, the welding data, the package format and the example joint joint-ex (the
  agent's /app/data);
- tests/app_data: the same files, for the verifier's read-only /app/data;
- tests/hidden: the seven hidden joints' packages, and truth.json with each joint's minimum preheat and its parts
  (each plate's hydrogen and hardness requirement, each run's true heat input and diffusible hydrogen).
The definitions are fixed and the generation is seeded, so a rebuild writes the same files."""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jobs as Jm
import docs_weld as Dw


def write_agent_data(root):
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, "docs")); os.makedirs(os.path.join(root, "examples"))
    open(os.path.join(root, "docs", "ms_ph_preheat.md"), "w").write(Dw.STANDARD)
    open(os.path.join(root, "docs", "welding_data.md"), "w").write(Dw.DATA)
    open(os.path.join(root, "docs", "package_format.md"), "w").write(Dw.FORMAT)
    Dw.write(Jm.BY[Jm.EXAMPLE], os.path.join(root, "examples", Jm.EXAMPLE))


def main(bundle):
    write_agent_data(os.path.join(bundle, "environment", "data"))
    write_agent_data(os.path.join(bundle, "tests", "app_data"))
    hid = os.path.join(bundle, "tests", "hidden")
    shutil.rmtree(hid, ignore_errors=True); os.makedirs(hid)
    truth = {}
    for name in Jm.HIDDEN:
        j = Jm.BY[name]
        Dw.write(j, os.path.join(hid, name))
        v, plates, runs = Jm.assess_true(j)
        truth[name] = dict(min_preheat_c=round(v, 3),
                           joint=dict(plates=[dict(mark=p["mark"], heat=p["heat"], d_mm=p["d"],
                                                   hydrogen_c=round(a, 2), hardness_c=round(b, 2))
                                              for p, (a, b) in zip(j["plates"], plates)],
                                      runs=[dict(kind=k, heat_input_kj_mm=round(q, 4), hd_ml_100g=round(h, 3))
                                            for q, h, k in runs]))
    with open(os.path.join(hid, "truth.json"), "w") as fh:
        json.dump(truth, fh, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(HERE, "..", "..")))
