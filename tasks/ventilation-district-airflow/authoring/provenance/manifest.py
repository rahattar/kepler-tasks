"""manifest.py: the list of every data file districts.py makes, with its SHA-256.

    python3 authoring/provenance/manifest.py

First the verifier's copy of the agent's data, tests/app_data, is made again from environment/data, so the two
are one set of files. Then manifest.json is written: the districts' table as districts.py has it and the
SHA-256 of every file under the folders below. regenerate.py makes the districts again and compares.
"""
import hashlib
import json
import os
import shutil
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
MADE = ("environment/data/examples", "environment/data/pending", "environment/rig/sealed", "tests/districts",
        "tests/results", "tests/crew/books", "authoring/provenance/as_it_is", "authoring/evidence/small")


def files(root=ROOT):
    out = {}
    for top in MADE:
        for base, dirs, names in os.walk(os.path.join(root, top)):
            dirs.sort()
            for name in sorted(names):
                path = os.path.join(base, name)
                with open(path, "rb") as handle:
                    out[os.path.relpath(path, root)] = hashlib.sha256(handle.read()).hexdigest()
    return out


def table(small):
    sys.argv = [sys.argv[0]] + (["--small"] if small else [])
    sys.modules.pop("districts", None)
    sys.path.insert(0, HERE)
    import districts
    return {name: {key: (list(value) if isinstance(value, tuple) else value) for key, value in spec.items()}
            for name, spec in districts.SITES.items()}


def main():
    copy = os.path.join(ROOT, "tests", "app_data")
    shutil.rmtree(copy, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "environment", "data"), copy)
    listed = files()
    with open(os.path.join(HERE, "manifest.json"), "w") as out:
        json.dump({"districts": table(False), "small": table(True), "files": listed}, out, indent=1, sort_keys=True)
        out.write("\n")
    print("%d files listed" % len(listed))


if __name__ == "__main__":
    main()
