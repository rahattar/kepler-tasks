"""Lists every shipped data file with its size and SHA-256, and what each cell is.

    python3 manifest.py          writes manifest.json beside this file

manifest.json is the record of what the visible and the hidden data are: for each cell its role, its engine,
the index error and transducer gain built into its records, and its files. regenerate.py checks the shipped
files against the generator; this file is what a reader checks the bundle against.
"""
import sys

sys.dont_write_bytecode = True
import hashlib
import json
import os

import cells

BUNDLE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def listing(folder):
    out = {}
    for base, _, files in os.walk(folder):
        for name in sorted(files):
            path = os.path.join(base, name)
            with open(path, "rb") as handle:
                data = handle.read()
            out[os.path.relpath(path, BUNDLE).replace(os.sep, "/")] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return dict(sorted(out.items()))


def main():
    book = {"cells": []}
    for c in cells.CELLS:
        folder = os.path.join(BUNDLE, cells.PLACE[c["role"]], c["cell"])
        files = listing(folder)
        if c["role"] != "example":
            sealed = os.path.join(BUNDLE, cells.SEALED[c["role"]], c["cell"] + ".csv")
            with open(sealed, "rb") as handle:
                data = handle.read()
            files[os.path.relpath(sealed, BUNDLE).replace(os.sep, "/")] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        book["cells"].append({
            "cell": c["cell"], "role": c["role"], "index_deg": c["index_deg"], "gain": c["gain"],
            "wall_heat_factor": c["f_ht"], "cylinders": c["cyl"], "ignition": c["ignition"], "engine": c["eng"],
            "cycles_per_point": cells.CYCLES[c["role"]], "files": files})
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json"), "w") as handle:
        json.dump(book, handle, indent=1)
        handle.write("\n")
    print("%d cells, %d files" % (len(book["cells"]), sum(len(c["files"]) for c in book["cells"])))


if __name__ == "__main__":
    main()
