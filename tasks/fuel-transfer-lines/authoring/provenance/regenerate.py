"""regenerate.py: sites.py run again into an empty directory, and every file it makes held against manifest.json.

    python3 authoring/provenance/regenerate.py > authoring/evidence/regenerate.txt

The nine sites at full size go in two streams side by side, then the nine at the small size. Every site is
drawn from its own seed, so the order does not matter. About forty minutes on two CPUs.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
PROVENANCE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROVENANCE)
import manifest  # noqa: E402


def main():
    with open(os.path.join(PROVENANCE, "manifest.json")) as handle:
        listed = json.load(handle)["files"]
    with open(os.path.join(PROVENANCE, "manifest.json")) as handle:
        names = sorted(json.load(handle)["sites"])
    empty = tempfile.mkdtemp(prefix="sites_again_")
    began = time.time()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    script = os.path.join(PROVENANCE, "sites.py")
    said, codes = [], []
    for extra in ([], ["small"]):
        streams = [subprocess.Popen([sys.executable, script, empty] + extra + names[k::2], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, env=env) for k in (0, 1)]
        for stream in streams:
            said.append(stream.communicate()[0])
            codes.append(stream.returncode)
    print("sites.py run into an empty directory: the nine sites at full size, then at the small size")
    for text in said:
        for line in text.strip().splitlines():
            print("  " + line[:118])
    made = manifest.listing(empty)
    different = sorted(path for path in listed if made.get(path) != listed[path])
    unlisted = sorted(path for path in made if path not in listed)
    for path in different[:25]:
        print("  DIFFERENT   " + path)
    for path in unlisted[:25]:
        print("  NOT LISTED  " + path)
    print("exit statuses %s, %.0f minutes" % (codes, (time.time() - began) / 60.0))
    print("%d files listed, %d made differently, %d made and not listed" % (len(listed), len(different), len(unlisted)))
    shutil.rmtree(empty, ignore_errors=True)
    return 1 if different or unlisted or any(codes) else 0


if __name__ == "__main__":
    sys.exit(main())
