"""Writes everything generated in the bundle from the sealed definition.

    python3 authoring/provenance/build.py [ROOT]

ROOT (default: the bundle) gets environment/data (documents and the example case package), tests/hidden (the eight
hidden case packages and truth.json), tests/app_data (a copy of environment/data, installed at /app/data in the
verifier image) and tests/rate.py and tests/catalog.py (the rating standard and catalogue the grader rates with).
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen3  # noqa: E402

BUNDLE = os.path.abspath(os.path.join(HERE, "..", ".."))


def main(root=BUNDLE):
    tmp = tempfile.mkdtemp()
    gen3.main(tmp)
    for sub in ("environment/data", "tests/hidden", "tests/app_data"):
        shutil.rmtree(os.path.join(root, sub), ignore_errors=True)
    shutil.copytree(os.path.join(tmp, "data"), os.path.join(root, "environment", "data"))
    shutil.copytree(os.path.join(tmp, "hidden"), os.path.join(root, "tests", "hidden"))
    shutil.copytree(os.path.join(tmp, "data"), os.path.join(root, "tests", "app_data"))
    for f in ("rate.py", "catalog.py"):
        shutil.copy(os.path.join(HERE, f), os.path.join(root, "tests", f))
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else BUNDLE)
