"""Outage inspection of boiler B2's secondary superheater (runs as the contractor user). One order of up to two
measurements, placed once.

    python3 -I fieldwork.py status OUT_DIR STATE_FILE
    python3 -I fieldwork.py submit OUT_DIR STATE_FILE  < plan.json

plan.json: {"tests": [{"element": "E4", "test": "oxide-ut"}, ...]}, 1-2 entries, test is "oxide-ut" or "wall-ut",
no entry twice. The order is charged to the state file before any result is made; a state that
cannot be read counts as already placed. Results are created in OUT_DIR as new files only, never following links.
"""
import fcntl
import json
import os
import stat
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tubes as S

BUDGET = 2
TESTS = ("oxide-ut", "wall-ut")
NOFOLLOW = os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def fail(msg, code=2):
    print(json.dumps(dict(error=msg)), flush=True)
    sys.exit(code)


def open_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or st.st_mode & 0o022:
        os.close(fd)
        fail("output directory must be this user's own and writable by no one else")
    return fd


def load(state):
    try:
        fd = os.open(state, os.O_RDONLY | NOFOLLOW)
    except FileNotFoundError:
        return dict(ordered=False, tests=[])
    except OSError:
        return dict(ordered=True, tests=[], note="state unreadable")
    try:
        with os.fdopen(fd) as f:
            s = json.load(f)
        return dict(ordered=bool(s["ordered"]), tests=list(s["tests"]))
    except Exception:
        return dict(ordered=True, tests=[], note="state invalid")


def save(state, s):
    tmp = state + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(s, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, state)


def parse(text):
    try:
        plan = json.loads(text)
        tests = plan["tests"]
        assert isinstance(tests, list) and 1 <= len(tests) <= BUDGET
        out = []
        for t in tests:
            u = str(t["element"]).strip().upper()
            k = str(t["test"]).strip().lower()
            assert u in S.ELEMENTS and k in TESTS
            out.append((u, k))
        assert len(set(out)) == len(out)
        return out
    except Exception:
        fail('plan must be {"tests": [{"element": "E1".."E10", "test": "oxide-ut" | "wall-ut"}, ...]}, '
             "1 to %d entries, none repeated" % BUDGET)


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("status", "submit"):
        fail("usage: fieldwork status | fieldwork submit < plan.json")
    cmd, out, state = sys.argv[1:]
    lockfd = os.open(state + ".lock", os.O_RDWR | os.O_CREAT | NOFOLLOW, 0o600)
    fcntl.flock(lockfd, fcntl.LOCK_EX)
    s = load(state)
    if cmd == "status":
        print(json.dumps(dict(ordered=s["ordered"], tests=s["tests"], budget=BUDGET,
                              tests_available=list(TESTS)), indent=1))
        return
    if s["ordered"]:
        fail("the outage inspection order has already been placed", 3)
    plan = parse(sys.stdin.read(65536))
    s = dict(ordered=True, tests=[dict(element=u, test=k) for u, k in plan])
    save(state, s)                                      # charged before any result is made
    dfd = open_dir(out)
    lines = ["element,test,date,result,unit"]
    for u, k in plan:
        rng = np.random.default_rng(7000 + 31 * S.ELEMENTS.index(u) + TESTS.index(k))
        r = S.measure(u, k, rng)
        if k == "oxide-ut":
            lines.append("%s,%s,2026-10-31,%.0f,um steam-side oxide at the outlet-leg crown (mean of 8 readings)" % (u, k, r["oxide_um"]))
        else:
            lines.append("%s,%s,2026-10-31,%.2f,mm minimum wall at the outlet-leg crown" % (u, k, r["min_wall_mm"]))
    fd = os.open("results.csv", os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o644, dir_fd=dfd)
    with os.fdopen(fd, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(json.dumps(dict(ordered=True, tests=s["tests"], results="results.csv"), indent=1))


if __name__ == "__main__":
    main()
