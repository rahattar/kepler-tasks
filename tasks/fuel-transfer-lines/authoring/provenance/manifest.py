"""manifest.py: every data file sites.py makes, listed with its SHA-256 in manifest.json.

    python3 authoring/provenance/manifest.py

tests/app_data, the verifier's copy of what the program's author had, is first made again from
environment/data, so that the two are the same files. Then manifest.json gets the table of sites as sites.py
holds it, the two sizes it draws them at, and the SHA-256 of every file under PLACES. regenerate.py runs
sites.py again into an empty directory and holds what it makes against this list.
"""
import hashlib
import json
import os
import shutil
import sys

sys.dont_write_bytecode = True
PROVENANCE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.dirname(os.path.dirname(PROVENANCE))
PLACES = ("environment/data/examples", "environment/data/pending", "environment/rig/sealed", "tests/sites", "tests/results",
          "tests/crew/books", "authoring/provenance/as_it_stands", "authoring/evidence/small")


def listing(root=BUNDLE):
    """{path under root: SHA-256} of every file under PLACES."""
    found = {}
    for place in PLACES:
        for folder, inner, names in os.walk(os.path.join(root, place)):
            inner.sort()
            for name in sorted(names):
                path = os.path.join(folder, name)
                digest = hashlib.sha256()
                with open(path, "rb") as handle:
                    digest.update(handle.read())
                found[os.path.relpath(path, root)] = digest.hexdigest()
    return found


def main():
    sys.path.insert(0, PROVENANCE)
    import sites
    copy = os.path.join(BUNDLE, "tests", "app_data")
    shutil.rmtree(copy, ignore_errors=True)
    shutil.copytree(os.path.join(BUNDLE, "environment", "data"), copy)
    table = {name: dict(seed=spec[0], role=spec[1], narrowing=spec[2], declining=spec[3], t_now_C=spec[4], t_campaigns_C=list(spec[5]))
             for name, spec in sites.SITES.items()}
    files = listing()
    with open(os.path.join(PROVENANCE, "manifest.json"), "w") as handle:
        json.dump({"sites": table, "full": sites.FULL, "small": sites.SMALL, "files": files}, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print("manifest.json: %d files" % len(files))


if __name__ == "__main__":
    main()
