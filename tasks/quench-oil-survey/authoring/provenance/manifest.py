"""Writes manifest.json: the generator's table of sites and the SHA-256 of every data file shipped.

    python3 manifest.py
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.dirname(os.path.dirname(HERE))
sys.dont_write_bytecode = True
sys.path.insert(0, HERE)
import sites  # noqa: E402

PLACES = ("environment/data/examples", "environment/data/pending", "environment/rig/sealed", "tests/sites",
          "tests/sealed", "tests/lab/sealed")


def main():
    files = {}
    for place in PLACES:
        for base, dirs, names in os.walk(os.path.join(BUNDLE, place)):
            dirs.sort()
            for name in sorted(names):
                path = os.path.join(base, name)
                with open(path, "rb") as handle:
                    files[os.path.relpath(path, BUNDLE)] = hashlib.sha256(handle.read()).hexdigest()
    table = {name: dict(seed=seed, role=role,
                        central_system_that_is_two_charges=None if split is None else "QS-%d" % (split + 1),
                        central_systems=central, tanks_with_their_own_oil=single)
             for name, (seed, role, split, central, single) in sites.SITES.items()}
    with open(os.path.join(HERE, "manifest.json"), "w") as handle:
        json.dump(dict(generator="authoring/provenance/sites.py", sites=table, files=files), handle, indent=1)
        handle.write("\n")
    print("%d files" % len(files))


if __name__ == "__main__":
    main()
