"""Populates the bundle from the sealed definition.

    python3 authoring/provenance/build.py [ROOT]

ROOT (default: the bundle) gets:
  environment/data           the agent's records (installed read-only at /app/data)
  environment/rig/sealed     isim.py + seed.json for the laboratory user (mode 700, unreadable to the agent)
  tests/sealed               the same two files for the verifier
  tests/app_data             a copy of environment/data, installed at /app/data in the verifier image

The three copies of isim.py are byte-identical; preflight checks that they are.
"""
import json
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen  # noqa: E402

BUNDLE = os.path.abspath(os.path.join(HERE, "..", ".."))
SEED = 4101


def main(root=BUNDLE, seed=SEED):
    tmp = tempfile.mkdtemp()
    gen.main(tmp)
    for dst in ("environment/data", "tests/app_data"):
        d = os.path.join(root, dst)
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(tmp, d)
    shutil.rmtree(tmp)
    for dst in ("environment/rig/sealed", "tests/sealed"):
        d = os.path.join(root, dst)
        os.makedirs(d, exist_ok=True)
        shutil.copyfile(os.path.join(HERE, "isim.py"), os.path.join(d, "isim.py"))
        with open(os.path.join(d, "seed.json"), "w") as f:
            json.dump({"seed": seed}, f)
            f.write("\n")
    with open(os.path.join(HERE, "seed.json"), "w") as f:
        json.dump({"seed": seed}, f)
        f.write("\n")
    print("built the bundle at %s with seed %d" % (root, seed))


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else BUNDLE)
