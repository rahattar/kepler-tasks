"""Makes the nine sites again with sites.py and compares every file with the one shipped.

    python3 regenerate.py [DIR] > ../evidence/regenerate.txt

With DIR, an output directory of `sites.py DIR` that already exists is compared and nothing is generated; the
generation takes about twenty-five minutes on one CPU. manifest.py writes the list of files this compares.
"""
import filecmp
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.dirname(os.path.dirname(HERE))


def main():
    made = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="sites_")
    if len(sys.argv) < 2:
        subprocess.run([sys.executable, os.path.join(HERE, "sites.py"), made], check=True, stdout=subprocess.DEVNULL)
    with open(os.path.join(HERE, "manifest.json")) as handle:
        listed = sorted(json.load(handle)["files"])
    different = 0
    print("authoring/provenance/sites.py run again, its output compared with the shipped files byte for byte")
    print()
    groups = {}
    for name in listed:
        same = os.path.exists(os.path.join(made, name)) and filecmp.cmp(os.path.join(made, name),
                                                                        os.path.join(BUNDLE, name), shallow=False)
        different += not same
        site = os.path.basename(name).split(".")[0] if name.endswith((".json", ".csv")) and "/sealed/" in name \
            else name.split("/")[-2]
        groups.setdefault(site, []).append(same)
        if not same:
            print("DIFFERENT  %s" % name)
    for site, flags in groups.items():
        print("%-12s %2d files, %d the same" % (site, len(flags), sum(flags)))
    extra = []
    for base, _, names in os.walk(made):
        for name in names:
            rel = os.path.relpath(os.path.join(base, name), made)
            if rel not in listed:
                extra.append(rel)
    print()
    print("files the generator writes that are not shipped: %d" % len(extra))
    print("%d files, %d different" % (len(listed), different))
    return 1 if different or extra else 0


if __name__ == "__main__":
    sys.exit(main())
