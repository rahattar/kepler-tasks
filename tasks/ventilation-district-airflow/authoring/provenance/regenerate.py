"""regenerate.py: every data file made again from districts.py and compared with the manifest.

    python3 authoring/provenance/regenerate.py > authoring/evidence/regenerate.txt

districts.py is run into an empty directory, the nine districts as shipped in two streams side by side and
then the seven small ones, each from the draw recorded in its table. Every file it writes is compared by
SHA-256 with manifest.json. Takes about twenty minutes on two CPUs.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import manifest  # noqa: E402


def main():
    with open(os.path.join(HERE, "manifest.json")) as handle:
        listed = json.load(handle)
    room = tempfile.mkdtemp(prefix="regen_")
    started = time.time()
    names = list(listed["districts"])
    streams = [names[0::2], names[1::2]]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    going = [subprocess.Popen([sys.executable, os.path.join(HERE, "districts.py"), "--to", room] + part,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env) for part in streams]
    said = [p.communicate()[0] for p in going]
    small = subprocess.run([sys.executable, os.path.join(HERE, "districts.py"), "--to", room, "--small"],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    said.append(small.stdout)
    status = [p.returncode for p in going] + [small.returncode]
    print("districts.py run into an empty directory: the nine districts, then the seven small ones")
    for text in said:
        for line in text.splitlines():
            print("  " + " ".join(line.split()[:9]))
    made = manifest.files(room)
    different = sorted(name for name in listed["files"] if made.get(name) != listed["files"][name])
    extra = sorted(name for name in made if name not in listed["files"])
    for name in different[:20]:
        print("  DIFFERENT  " + name)
    for name in extra[:20]:
        print("  NOT LISTED  " + name)
    print("exit statuses %s; %.0f minutes" % (status, (time.time() - started) / 60.0))
    print("%d files, %d different, %d not listed" % (len(listed["files"]), len(different), len(extra)))
    shutil.rmtree(room, ignore_errors=True)
    return 1 if different or extra or any(status) else 0


if __name__ == "__main__":
    sys.exit(main())
