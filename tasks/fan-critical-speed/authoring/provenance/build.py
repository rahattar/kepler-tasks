"""Writes every data file of the bundle from the sealed definitions (fans.py) and the documents (docs_fan.py):

    python3 authoring/provenance/build.py [BUNDLE_ROOT]

- environment/data: the standard MS-RD, the package format and the example fan boiler-fd-fan (the agent's /app/data);
- tests/app_data: the same files, for the verifier's read-only /app/data;
- tests/hidden: the six hidden fans' packages, and truth.json with each fan's two lowest critical speeds with its new
  impeller and the fan as it will run (rotor, true pedestal stiffnesses);
The definitions are fixed and the generation is seeded, so a rebuild writes the same files."""
import json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fans as Fm
import docs_fan as Df


def write_agent_data(root):
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, "docs")); os.makedirs(os.path.join(root, "examples"))
    open(os.path.join(root, "docs", "ms_rd_critical_speeds.md"), "w").write(Df.STANDARD)
    open(os.path.join(root, "docs", "package_format.md"), "w").write(Df.FORMAT)
    Df.write(Fm.BY[Fm.EXAMPLE], os.path.join(root, "examples", Fm.EXAMPLE))


def main(bundle):
    write_agent_data(os.path.join(bundle, "environment", "data"))
    write_agent_data(os.path.join(bundle, "tests", "app_data"))
    hid = os.path.join(bundle, "tests", "hidden")
    shutil.rmtree(hid, ignore_errors=True); os.makedirs(hid)
    truth = {}
    for name in Fm.HIDDEN:
        f = Fm.BY[name]
        Df.write(f, os.path.join(hid, name))
        R = Fm.config(f, None, f["new"])
        truth[name] = dict(critical_rpm=[round(c, 3) for c in Fm.truth(f)],
                           fan=dict(shaft=[list(s) for s in R["shaft"]], disks=[list(d) for d in R["disks"]],
                                    bearings=R["bearings"], kb=R["kb"], mp=R["mp"], kpH=R["kpH"], kpV=R["kpV"]))
    with open(os.path.join(hid, "truth.json"), "w") as fh:
        json.dump(truth, fh, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(HERE, "..", "..")))
