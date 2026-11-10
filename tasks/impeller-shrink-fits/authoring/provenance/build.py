"""Populates the bundle from the sealed definition.

    python3 authoring/provenance/build.py [ROOT]

ROOT (default: the bundle) gets:
  environment/data           the agent's documents (installed read-only at /app/data)
  environment/rig/sealed     isim.py + seed.json for the laboratory user (mode 700, unreadable to the agent)
  tests/sealed               the same two files for the verifier
  tests/app_data             a copy of environment/data, installed at /app/data in the verifier image
"""
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen  # noqa: E402

BUNDLE = os.path.abspath(os.path.join(HERE, "..", ".."))


def main(root=BUNDLE):
    tmp = tempfile.mkdtemp()
    gen.main(tmp)
    targets = {"environment/data": "data", "environment/rig/sealed": "sealed", "tests/sealed": "sealed",
               "tests/app_data": "data"}
    for dst, src in targets.items():
        d = os.path.join(root, dst)
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(os.path.join(tmp, src), d)
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else BUNDLE)
