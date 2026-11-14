"""Writes manifest.json: what each of the nine works is, and every data file the bundle ships for it.

    python3 manifest.py

For each works: its role, the days of its surveys, and for each crane its reeving, the size of its log, the
greatest damage of its rope and what happened to the rope that no record says (`rope`: sound, turned, dead_end
or both, with the day of the turn and the day of the first survey taken from the dead end). Then each file of
its package, and its sealed result where it has one, with size and SHA-256. The facts come from the generator
(works.draw); the files are the ones on disk. regenerate.py is the check that the two still belong together.
"""
import hashlib
import json
import os
import sys

sys.dont_write_bytecode = True
import works  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def fingerprint(path):
    with open(path, "rb") as handle:
        blob = handle.read()
    return {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}


def files_of(spec):
    """{path within the bundle: size and hash} for one works."""
    folder = os.path.join(works.PLACE[spec["role"]], spec["works"])
    listed = {"%s/%s" % (folder, name): fingerprint(os.path.join(works.BUNDLE, folder, name))
              for name in sorted(os.listdir(os.path.join(works.BUNDLE, folder)))}
    if spec["role"] in works.SEALED:
        sealed = "%s/%s.csv" % (works.SEALED[spec["role"]], spec["works"])
        listed[sealed] = fingerprint(os.path.join(works.BUNDLE, sealed))
    return listed


def main():
    book = {"band": works.BAND, "station_spacing_m": works.SPACING, "log_days": works.DAYS, "works": []}
    for spec in works.WORKS:
        scratch = os.path.join(HERE, "_scratch")
        facts = works.build(spec, root=scratch)
        entry = {key: spec[key] for key in ("works", "role", "seed", "turned", "dead_end", "both", "eight", "tall")}
        entry.update(survey_days=facts["survey_days"], movements=facts["movements"], rows=facts["rows"],
                     cranes=facts["cranes"], files=files_of(spec))
        book["works"].append(entry)
        print("%-12s %-8s %d cranes, %d movements, %d files" % (spec["works"], spec["role"], len(facts["cranes"]),
                                                                facts["movements"], len(entry["files"])))
    import shutil
    shutil.rmtree(os.path.join(HERE, "_scratch"), ignore_errors=True)
    with open(os.path.join(HERE, "manifest.json"), "w") as handle:
        json.dump(book, handle, indent=1)
        handle.write("\n")


if __name__ == "__main__":
    main()
