"""November-outage field work for the screen house (runs as the contractor user). One programme of up to three tests,
ordered once.

    python3 -I fieldwork.py status OUT_DIR STATE_FILE
    python3 -I fieldwork.py submit OUT_DIR STATE_FILE  < plan.json

plan.json: {"tests": [{"screen": "S6", "test": "coast-down"}, ...]}, 1-3 entries, test is "coast-down" or
"strain-survey", no entry twice. The programme is charged to the state file before any record is made; a state that
cannot be read counts as already ordered. Records are created in OUT_DIR as new files only, never following links.
"""
import fcntl
import json
import os
import stat
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screens as S

BUDGET = 3
TESTS = ("coast-down", "strain-survey")
NOFOLLOW = os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
FS = 500.0
STEADY_S = 8.0


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
            u = str(t["screen"]).strip().upper()
            k = str(t["test"]).strip().lower()
            assert u in S.UNITS and k in TESTS
            out.append((u, k))
        assert len(set(out)) == len(out)
        return out
    except Exception:
        fail('plan must be {"tests": [{"screen": "S1".."S10", "test": "coast-down" | "strain-survey"}, ...]}, '
             "1 to %d entries, none repeated" % BUDGET)


def channels(u, b, sig, rng):
    """Contractor's gauges at 0.4t and 1.0t, gauge factor set correctly."""
    e1 = sig * (1 - 0.4 * b["g"]) / S.E_MPA * 1e6 + rng.normal(0, 0.2, sig.size)
    e2 = sig * (1 - 1.0 * b["g"]) / S.E_MPA * 1e6 + rng.normal(0, 0.2, sig.size)
    return np.round(e1, 2), np.round(e2, 2)


def make_records(u, k, bank):
    rng = np.random.default_rng(9000 + 31 * S.UNITS.index(u) + TESTS.index(k))
    b = bank[u]
    recs = []
    if k == "coast-down":
        sig = S.event(b, "coast", FS, rng)
        n = sig.size
        t = np.arange(n) / FS
        w_rpm = S.RPM[u] * np.exp(-np.maximum(t - 0.5, 0) / b["tau"])
        e1, e2 = channels(u, b, sig, rng)
        rpm = np.round(w_rpm + rng.normal(0, 0.5, n), 1)
        recs.append(("coast", 0, dict(ch1_ue=e1, ch2_ue=e2, speed_rpm=rpm)))
    else:
        feeds = list(np.sort(np.round(rng.uniform(90, 790, 8)))) + [0.0, 0.0]
        for F in feeds:
            A = float(S.amp(b, F)) * (1 + 0.015 * rng.standard_normal())
            tt = np.arange(int(STEADY_S * FS)) / FS
            sig = A * S.wave(2 * np.pi * b["f_op"] * tt + rng.uniform(0, 2 * np.pi), b)
            e1, e2 = channels(u, b, sig, rng)
            recs.append(("loaded" if F > 0 else "empty", int(F), dict(ch1_ue=e1, ch2_ue=e2)))
    return recs


def write_csv(dfd, name, cols):
    keys = list(cols)
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o644, dir_fd=dfd)
    with os.fdopen(fd, "w") as fh:
        os.fchmod(fh.fileno(), 0o644)
        fh.write(",".join(keys) + "\n")
        n = len(cols[keys[0]])
        for i in range(n):
            fh.write(",".join(("%.1f" if k == "speed_rpm" else "%.2f") % cols[k][i] for k in keys) + "\n")


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
        fail("the outage programme has already been ordered", 3)
    plan = parse(sys.stdin.read(65536))
    s = dict(ordered=True, tests=[dict(screen=u, test=k) for u, k in plan])
    save(state, s)                                      # charged before any record is made
    dfd = open_dir(out)
    bank = S.load_bank(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bank.json"))
    index = []
    for u, k in plan:
        for i, (kind, feed, cols) in enumerate(make_records(u, k, bank), 1):
            name = "%s_%s_%02d.csv" % (k, u.lower(), i)
            write_csv(dfd, name, cols)
            index.append(dict(file=name, screen=u, test=k, kind=kind, feed_tph=feed, sample_rate_hz=int(FS)))
    lines = ["file,screen,test,kind,feed_tph,sample_rate_hz"] + [
        "%s,%s,%s,%s,%d,%d" % (r["file"], r["screen"], r["test"], r["kind"], r["feed_tph"], r["sample_rate_hz"])
        for r in index]
    fd = os.open("fieldwork_index.csv", os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o644, dir_fd=dfd)
    with os.fdopen(fd, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(json.dumps(dict(ordered=True, tests=s["tests"], records=len(index), index="fieldwork_index.csv"), indent=1))


if __name__ == "__main__":
    main()
