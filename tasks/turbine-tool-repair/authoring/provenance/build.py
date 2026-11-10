"""Writes everything generated in the bundle from the sealed definition.

    python3 authoring/provenance/build.py [ROOT]

ROOT (default: the bundle) gets environment/data (documents and the two example record sets), environment/tool/gtperf.py
(the plant's program as shipped: solution/gtperf.py with every defect in bugs.py applied), tests/hidden (the eight
hidden record sets and truth.json) and tests/app_data (a copy of environment/data, installed at /app/data in the
verifier image so that a program sees the same /app/data there as in the agent's environment).
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bugs  # noqa: E402
import gen   # noqa: E402

BUNDLE = os.path.abspath(os.path.join(HERE, "..", ".."))


def main(root=BUNDLE):
    for sub in ("environment/data", "tests/hidden", "tests/app_data"):
        shutil.rmtree(os.path.join(root, sub), ignore_errors=True)
    gen.main(os.path.join(root, "environment", "data"), os.path.join(root, "tests", "hidden"))
    os.makedirs(os.path.join(root, "environment", "tool"), exist_ok=True)
    with open(os.path.join(root, "environment", "tool", "gtperf.py"), "w") as f:
        f.write(bugs.make(bugs.ALL))
    shutil.copytree(os.path.join(root, "environment", "data"), os.path.join(root, "tests", "app_data"))


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else BUNDLE)
