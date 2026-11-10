"""Writes every data file of the bundle from the sealed farm definitions (model.py) and the documents (docs.py):

    python3 authoring/provenance/build.py [BUNDLE_ROOT]

- environment/data: the procedure, the package format and the example package ridgeback-2026h1 with the results the
  owner's engineer reported (the agent's /app/data);
- tests/app_data: the same files, for the verifier's read-only /app/data;
- tests/hidden: the six hidden farm-period packages and truth.json, the true annual energy ratio and claim of every
  turbine (from its true power curve, not from the records).
The generation is seeded, so a rebuild writes the same files."""
import csv, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import model as M
import docs as Dd


def write_agent_data(root):
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, "docs")); os.makedirs(os.path.join(root, "examples"))
    open(os.path.join(root, "docs", "pp12_power_performance.md"), "w").write(Dd.PROCEDURE)
    open(os.path.join(root, "docs", "package_format.md"), "w").write(Dd.PACKAGE_FORMAT)
    pk = M.BY_NAME[M.EXAMPLE]
    out = os.path.join(root, "examples", pk["name"]); os.makedirs(os.path.join(out, "records"))
    tr = M.generate(pk, out); Dd.write(pk, out)
    with open(os.path.join(out, "reported_results.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["turbine", "aep_ratio", "warranty_claim"])
        for t in pk["turbines"]: w.writerow([t, "%.3f" % tr[t][0], tr[t][1]])


def write_hidden(root):
    shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
    truth = {}
    for name in M.HIDDEN:
        pk = M.BY_NAME[name]
        out = os.path.join(root, name); os.makedirs(os.path.join(out, "records"))
        tr = M.generate(pk, out); Dd.write(pk, out)
        truth[name] = {t: {"aep_ratio": tr[t][0], "warranty_claim": tr[t][1]} for t in pk["turbines"]}
    with open(os.path.join(root, "truth.json"), "w") as f:
        json.dump(truth, f, indent=1, sort_keys=True)


def main(bundle):
    write_agent_data(os.path.join(bundle, "environment", "data"))
    write_agent_data(os.path.join(bundle, "tests", "app_data"))
    write_hidden(os.path.join(bundle, "tests", "hidden"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(HERE, "..", "..")))
