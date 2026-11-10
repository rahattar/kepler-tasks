"""TC-wafer runs for diffusion bay 2 (runs as the metrology user). Three temperature steps in total.

    python3 -I server.py PORT OUT_DIR STATE_FILE
      GET  /status                              steps left and the runs so far
      POST /run?furnace=F2&steps=600,1050      an instrumented-wafer run with corrections disabled, at the listed
                                                steps (any of 600, 850, 1050); each listed step uses one of the three

The steps are charged to the state file before the readings are taken, so restarting the service does not reset
the count. Reports are returned and also written to OUT_DIR/run<k>_<furnace>.json, readable by the agent. The
service's code, the sealed definition and the state file are private to the metrology user.

The run record trusts nothing the agent can touch:
- the state file is opened without following links, the steps left are recomputed from the list of runs, and a
  state that cannot be read or does not add up counts as no steps left (it never resets to the full budget);
- OUT_DIR must be a real directory owned by this user and writable by no one else; it is opened once at start and
  reports are created inside that open directory as new files only (no links followed, nothing overwritten);
- state changes are serialised across threads and across processes.
"""
import fcntl, json, os, stat, sys, threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tc

BUDGET = 3
PORT, OUT, STATE = int(sys.argv[1]), sys.argv[2], sys.argv[3]
LOCK = threading.Lock()
BAY = tc.make_bay(7)
ENDPOINTS = ["GET /status", "POST /run?furnace=<F1..F8>&steps=<600,850,1050>"]
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
    """The runs so far and the steps left. A missing file is a fresh bay; anything else unreadable is exhausted."""
    try:
        fd = os.open(STATE, os.O_RDONLY | NOFOLLOW)
    except FileNotFoundError:
        return dict(left=BUDGET, runs=[], ok=True)
    except OSError as e:
        log("state unreadable: %s" % e)
        return dict(left=0, runs=[], ok=False)
    try:
        with os.fdopen(fd) as f:
            s = json.load(f)
        runs, used = [], 0
        for i, r in enumerate(s["runs"], 1):
            steps = [int(x) for x in r["steps"]]
            if r["run"] != i or r["furnace"] not in BAY or not steps or any(float(x) not in tc.STEPS for x in steps):
                raise ValueError("run %d malformed" % i)
            runs.append(dict(run=i, furnace=r["furnace"], steps=steps))
            used += len(steps)
        if used > BUDGET or int(s["left"]) != BUDGET - used:
            raise ValueError("steps do not add up")
        return dict(left=BUDGET - used, runs=runs, ok=True)
    except Exception as e:                      # fail closed: never hand back a fresh budget
        log("state invalid: %r" % e)
        return dict(left=0, runs=[], ok=False)


def save_state(s):
    tmp = STATE + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(dict(left=s["left"], runs=s["runs"]), f)
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
            return self.reply(200, dict(steps_left=s["left"], runs=[dict(furnace=r["furnace"], steps=r["steps"])
                                                                     for r in s["runs"]]))
        self.reply(404, dict(error="unknown path", endpoints=ENDPOINTS))

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/run":
            return self.reply(404, dict(error="unknown path", endpoints=ENDPOINTS))
        q = parse_qs(u.query)
        f = (q.get("furnace") or [""])[0].strip().upper()
        if f not in BAY:
            return self.reply(400, dict(error="unknown furnace %r" % f, furnaces=tc.FURN))
        try:
            want = sorted({float(x) for x in (q.get("steps") or [""])[0].split(",") if x.strip()})
        except ValueError:
            want = []
        if not want or any(x not in tc.STEPS for x in want):
            return self.reply(400, dict(error="steps must be a comma-separated subset of 600,850,1050"))
        with state_lock():
            s = load_state()
            if s["left"] < len(want):
                return self.reply(409, dict(error="not enough steps left", steps_left=s["left"]))
            s["left"] -= len(want)              # charged before the readings are taken
            k = len(s["runs"]) + 1
            s["runs"].append(dict(run=k, furnace=f, steps=[int(x) for x in want]))
            save_state(s)
            rec = dict(run=k, furnace=f, date=tc.CAL_DATE, corrections="disabled (raw profile control)",
                       steps=tc.tc_wafer_run(BAY[f], k, f, tuple(want)), steps_left=s["left"])
            write_report("run%d_%s.json" % (k, f.lower()), rec)
        self.reply(200, rec)


if __name__ == "__main__":
    OUT_FD = open_report_dir(OUT)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
