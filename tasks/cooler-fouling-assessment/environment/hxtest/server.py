"""Clean-and-test slots for the glycol cooler bank (runs as the contractor user). Three slots in total.

    python3 -I server.py PORT OUT_DIR STATE_FILE
      GET  /status                 slots left and the tests so far
      POST /test?unit=E8           as-found performance test, hydroblast, repeat test; uses one slot

A slot is charged to the state file before the test is made, so restarting the service does not reset the count.
Reports are returned and also written to OUT_DIR/test<k>_<unit>.json, readable by the agent. The service's code,
the sealed definition and the state file are private to the contractor user.

The test record trusts nothing the agent can touch:
- the state file is opened without following links, the slots left are recomputed from the list of tests, and a
  state that cannot be read or does not add up counts as no slots left (it never resets to the full budget);
- OUT_DIR must be a real directory owned by this user and writable by no one else; it is opened once at start and
  reports are created inside that open directory as new files only (no links followed, nothing overwritten);
- state changes are serialised across threads and across processes.
"""
import fcntl, json, os, stat, sys, threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hx

BUDGET = 3
PORT, OUT, STATE = int(sys.argv[1]), sys.argv[2], sys.argv[3]
LOCK = threading.Lock()
FLEET = hx.make_fleet(11)
ENDPOINTS = ["GET /status", "POST /test?unit=<E1..E10>"]
NOFOLLOW = os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def open_report_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or st.st_mode & 0o022:
        os.close(fd)
        raise SystemExit("report directory %s must be this user's own directory, writable by no one else" % path)
    return fd


@contextmanager
def state_lock():
    with LOCK:
        fd = os.open(STATE + ".lock", os.O_RDWR | os.O_CREAT | NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)


def load_state():
    """The tests so far and the slots left. A missing file is a fresh bank; anything else unreadable is exhausted."""
    try:
        fd = os.open(STATE, os.O_RDONLY | NOFOLLOW)
    except FileNotFoundError:
        return dict(left=BUDGET, tests=[], ok=True)
    except OSError as e:
        log("state unreadable: %s" % e)
        return dict(left=0, tests=[], ok=False)
    try:
        with os.fdopen(fd) as f:
            s = json.load(f)
        tests = []
        for i, r in enumerate(s["tests"], 1):
            if r["test"] != i or r["unit"] not in FLEET:
                raise ValueError("test %d malformed" % i)
            tests.append(dict(test=i, unit=r["unit"]))
        if len(tests) > BUDGET or int(s["left"]) != BUDGET - len(tests):
            raise ValueError("slots do not add up")
        return dict(left=BUDGET - len(tests), tests=tests, ok=True)
    except Exception as e:                      # fail closed: never hand back a fresh budget
        log("state invalid: %r" % e)
        return dict(left=0, tests=[], ok=False)


def save_state(s):
    tmp = STATE + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(dict(left=s["left"], tests=s["tests"]), f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE)


def write_report(name, rec):
    """Create OUT_DIR/name as a new file inside the directory opened at start; never follow or overwrite."""
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o644, dir_fd=OUT_FD)
    except OSError as e:
        log("report %s not written: %s" % (name, e))
        return
    with os.fdopen(fd, "w") as fh:
        os.fchmod(fh.fileno(), 0o644)
        json.dump(rec, fh, indent=1)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, obj):
        body = json.dumps(obj, indent=1).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if urlparse(self.path).path == "/status":
            with state_lock():
                s = load_state()
            return self.reply(200, dict(slots_left=s["left"], tests=[r["unit"] for r in s["tests"]]))
        self.reply(404, dict(error="unknown path", endpoints=ENDPOINTS))

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/test":
            return self.reply(404, dict(error="unknown path", endpoints=ENDPOINTS))
        unit = (parse_qs(u.query).get("unit") or [""])[0].strip().upper()
        if unit not in FLEET:
            return self.reply(400, dict(error="unknown unit %r" % unit, units=hx.UNITS))
        with state_lock():
            s = load_state()
            if s["left"] < 1:
                return self.reply(409, dict(error="no clean-and-test slots left", slots_left=s["left"]))
            s["left"] -= 1                      # charged before the test is made
            k = len(s["tests"]) + 1
            s["tests"].append(dict(test=k, unit=unit))
            save_state(s)
            rec = dict(test=k, unit=unit, date=hx.TEST_DATE, **hx.clean_and_test(FLEET[unit], k), slots_left=s["left"])
            write_report("test%d_%s.json" % (k, unit.lower()), rec)
        self.reply(200, rec)


if __name__ == "__main__":
    OUT_FD = open_report_dir(OUT)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
