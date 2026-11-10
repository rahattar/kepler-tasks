"""Writes every data file of the bundle from the sealed definitions (mains.py) and the documents (docs_main.py):

    python3 authoring/provenance/build.py [BUNDLE_ROOT]

- environment/data: the standard MS-SV, the package format and the example main kestrel-lane with the design the
  utility's engineer reported for it (the agent's /app/data);
- tests/app_data: the same files, for the verifier's read-only /app/data;
- tests/hidden: the six hidden mains' packages, and truth.json with each main as installed (profile, roughness,
  pumps, levels) and its smallest compliant vessel;
- tests/moc.py: a copy of moc.py, the method of characteristics the verifier's check runs.
The generation is seeded, so a rebuild writes the same files."""
import json, os, shutil, sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mains as M
import docs_main as Dm


def sealed(m):
    """What the verifier's check needs: the main as installed."""
    return dict(L=m["L"], D=m["D"], a=m["a"], k=m["k_true"], ch=[float(c) for c in m["ch"]], z=[float(z) for z in m["z"]],
                ww=m["ww"], header=m["header"], BWL=m["BWL"], TWL=m["TWL"],
                pump={k: v for k, v in m["new"].items() if k not in ("I_pump", "I_motor")}, vessel=dict(M.VESSEL))


def vmin_of(name):
    V, Vg = M.vmin(M.BY[name])
    return name, V, Vg


def write_agent_data(root, ex):
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, "docs")); os.makedirs(os.path.join(root, "examples"))
    open(os.path.join(root, "docs", "ms_sv_surge_standard.md"), "w").write(Dm.STANDARD)
    open(os.path.join(root, "docs", "package_format.md"), "w").write(Dm.FORMAT)
    out = os.path.join(root, "examples", M.EXAMPLE)
    Dm.write(M.BY[M.EXAMPLE], out)
    with open(os.path.join(out, "reported_design.json"), "w") as f:
        json.dump({"vessel_volume_m3": round(1.05 * ex[0], 1), "gas_volume_m3": round(1.02 * ex[1], 1)}, f)


def main(bundle):
    with Pool(2) as p:
        res = {n: (V, Vg) for n, V, Vg in p.map(vmin_of, [m["name"] for m in M.MAINS])}
    write_agent_data(os.path.join(bundle, "environment", "data"), res[M.EXAMPLE])
    write_agent_data(os.path.join(bundle, "tests", "app_data"), res[M.EXAMPLE])
    hid = os.path.join(bundle, "tests", "hidden")
    shutil.rmtree(hid, ignore_errors=True); os.makedirs(hid)
    truth = {}
    for name in M.HIDDEN:
        Dm.write(M.BY[name], os.path.join(hid, name))
        truth[name] = dict(vmin_m3=res[name][0], gas_m3=res[name][1], main=sealed(M.BY[name]))
    with open(os.path.join(hid, "truth.json"), "w") as f:
        json.dump(truth, f, indent=1, sort_keys=True)
    shutil.copy(os.path.join(HERE, "moc.py"), os.path.join(bundle, "tests", "moc.py"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(HERE, "..", "..")))
