"""Builds all nine works again from the generator, somewhere else, and compares what comes out with the bundle.

    python3 regenerate.py > ../evidence/regenerate.txt

Every package file, every expected.csv and every sealed result that ships must be byte for byte what works.py
writes today from rope.py, and must carry the hash manifest.json has for it. If a file differs, the shipped data
and the sealed definition no longer say the same thing, and this ends with status 1.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
import works  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def sha(path):
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None


def main():
    with open(os.path.join(HERE, "manifest.json")) as handle:
        book = {entry["works"]: entry for entry in json.load(handle)["works"]}
    again = tempfile.mkdtemp(prefix="again-")
    total, wrong = 0, []
    try:
        for spec in works.WORKS:
            works.build(spec, root=again)
            listed = book[spec["works"]]["files"]
            differing = [path for path, facts in listed.items()
                         if not (sha(os.path.join(again, path)) == sha(os.path.join(works.BUNDLE, path)) == facts["sha256"])]
            total += len(listed)
            wrong += differing
            print("%-12s %-8s %d files, %s" % (spec["works"], spec["role"], len(listed),
                                               "all as generated" if not differing else "%d DIFFER" % len(differing)))
    finally:
        shutil.rmtree(again, ignore_errors=True)
    for path in wrong:
        print("PROBLEM: %s is not what the generator writes" % path)
    print("\n%d files compared, %d differ" % (total, len(wrong)))
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
