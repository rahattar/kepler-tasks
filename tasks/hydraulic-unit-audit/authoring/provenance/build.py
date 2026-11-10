"""Writes everything generated in the bundle from the sealed definition.

    python3 authoring/provenance/build.py [ROOT]

ROOT (default: the bundle) gets environment/data (documents and the example package), tests/hidden (the eight
hidden packages and truth.json) and tests/app_data (a copy of environment/data, installed at /app/data in the
verifier image).
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen  # noqa: E402

BUNDLE = os.path.abspath(os.path.join(HERE, "..", ".."))


def main(root=BUNDLE):
    tmp = tempfile.mkdtemp()
    gen.main(tmp)
    for src, dst in (("data", "environment/data"), ("hidden", "tests/hidden"), ("data", "tests/app_data")):
        d = os.path.join(root, dst)
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(os.path.join(tmp, src), d)
    ev = os.path.join(root, "authoring", "evidence")
    os.makedirs(ev, exist_ok=True)
    shutil.copy(os.path.join(tmp, "simulated.json"), os.path.join(ev, "simulated.json"))
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else BUNDLE)
