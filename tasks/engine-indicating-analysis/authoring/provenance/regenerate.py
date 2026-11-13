"""Makes the ten cells again from the generator and compares every shipped data file with what comes out.

    python3 regenerate.py > ../evidence/regenerate.txt

The shipped packages, the examples' expected.csv and the sealed results must be, byte for byte, what
cells.py writes from cylinder.py today. A difference means the data and the sealed definition have parted.
"""
import sys

sys.dont_write_bytecode = True
import hashlib
import json
import os
import shutil
import sys
import tempfile

import cells

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.dirname(os.path.dirname(HERE))


def digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main():
    with open(os.path.join(HERE, "manifest.json")) as handle:
        book = json.load(handle)
    fresh = tempfile.mkdtemp(prefix="regenerate_")
    different, files = [], 0
    try:
        for c in cells.CELLS:
            cells.build(c, fresh)
            listed = next(entry for entry in book["cells"] if entry["cell"] == c["cell"])["files"]
            for rel, facts in listed.items():
                files += 1
                made = os.path.join(fresh, rel)
                same = os.path.exists(made) and digest(made) == digest(os.path.join(BUNDLE, rel)) == facts["sha256"]
                if not same:
                    different.append(rel)
            print("%s (%s): %d files %s" % (c["cell"], c["role"], len(listed),
                                             "the same" if not any(d.split("/")[-3:-2] == [c["cell"]] or c["cell"] in d for d in different) else "DIFFERENT"))
    finally:
        shutil.rmtree(fresh, ignore_errors=True)
    for rel in different:
        print("PROBLEM: %s differs from what the generator writes" % rel)
    print("\n%d files, %d different" % (files, len(different)))
    return 1 if different else 0


if __name__ == "__main__":
    sys.exit(main())
