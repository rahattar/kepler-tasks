"""Runs a submitted bearing.py on the six sites and judges what it writes for each.

    python3 grade_program.py /app/output/bearing.py

One site at a time, in the order of their names:

  1. A scratch directory is made. In it, `run/` holds a copy of bearing.py and nothing else, and `package/` a
     read-only copy of the site's six files.
  2. The laboratory opens for that site (Desk): it holds the site's book from lab/sealed and takes one order,
     by the rule of lab/lab.py, through the `labsample` command on the PATH.
  3. The program is started in `run/` as `python3 bearing.py PACKAGE_DIR OUT_CSV`, as the user nobody, on one
     CPU, with the numerical libraries held to one thread, in a process group of its own. It is given
     RUN_LIMIT_S seconds from start to exit.
  4. When it exits or the time is up, its process group and every process of nobody are killed.
  5. A run that is still going at the limit ends the whole assessment there: nothing it wrote is opened, no
     later site is run, and the program is not accepted.
  6. Otherwise OUT_CSV is read and every point is compared with sealed/truth/<site>.csv.

The program is accepted when every run finished in time with exit status 0, every OUT_CSV is the table the task
statement describes, and every quantity of every point of every site is within its band (BANDS).

The truth files are the results of authoring/provenance/sites.py for the oil each bearing really drew. This
directory is readable by root alone, so the program, which runs as nobody, can read neither them nor the
laboratory's books.
"""
import csv
import io
import json
import math
import os
import re
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(HERE, "lab"))
import lab  # noqa: E402

RUN_LIMIT_S = 60                     # seconds for each run of bearing.py, as the task statement gives it
COLUMNS = ["point", "h_min_um", "attitude_deg", "power_kW", "t_eff_C", "p_max_MPa"]
# quantity, how its error is measured, the band the task statement gives
BANDS = (
    ("h_min_um", "of the true value", 0.015),
    ("attitude_deg", "degrees", 1.0),
    ("power_kW", "of the true value", 0.015),
    ("t_eff_C", "K", 0.5),
    ("p_max_MPa", "of the true value", 0.015),
)
PACKAGE = ("site.json", "bearings.csv", "oil_systems.csv", "oil_log.csv", "oil_samples.csv", "points.csv")
DECIMAL = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?\Z")
OUTPUT_CAP = 4 * 1024 * 1024         # bytes; a table of 3 000 points is about 0.2 MB
NOBODY = 65534
AS_NOBODY = ["setpriv", "--reuid=%d" % NOBODY, "--regid=%d" % NOBODY, "--clear-groups", "--inh-caps=-all"]
DESK = "/run/oil-lab/desk"           # where tests/lab/labsample finds the laboratory


class Refused(Exception):
    """OUT_CSV is not the table the task statement describes."""


@dataclass
class Outcome:
    accepted: bool = False
    stopped: str = ""                           # why the assessment ended early, when it did
    sites: dict = field(default_factory=dict)   # site -> what happened there


class Desk:
    """The laboratory for the length of one run: one order, for the site being run."""

    def __init__(self, site, book, where=DESK):
        self.site, self.book, self.where = site, book, where
        self.order = None
        self._lock = threading.Lock()
        self._closing = threading.Event()

    def take(self, site, tags):
        if site != self.site:
            return 1, lab.NO_BOOK
        taken, text = lab.answer(self.book, tags)
        if not taken:
            return 1, text
        with self._lock:
            if self.order is not None:
                return 1, lab.TAKEN
            self.order = list(tags)                    # on the books before any figure leaves
        return 0, text

    def _hear(self, caller):
        with caller:
            caller.settimeout(5.0)
            heard = b""
            while len(heard) < 262144:
                part = caller.recv(65536)
                if not part:
                    break
                heard += part
            try:
                words = json.loads(heard.decode())
                if not (isinstance(words, list) and words and all(isinstance(w, str) for w in words)):
                    raise ValueError
                reply = self.take(words[0], words[1:])
            except ValueError:
                reply = (2, "usage: labsample PACKAGE_DIR TAG [TAG ...]")
            caller.sendall(json.dumps(reply).encode())

    def _serve(self):
        while not self._closing.is_set():
            try:
                caller, _ = self._door.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            try:
                self._hear(caller)
            except Exception:                          # a caller that hangs up, or sends what cannot be
                pass                                   # answered, gets no analysis; the desk stays open

    def __enter__(self):
        os.makedirs(os.path.dirname(self.where), exist_ok=True)
        os.chmod(os.path.dirname(self.where), 0o755)       # set outright: the umask may be 077
        if os.path.lexists(self.where):
            os.unlink(self.where)
        self._door = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._door.bind(self.where)
        os.chmod(self.where, 0o666)
        self._door.listen(8)
        self._door.settimeout(0.2)
        self._clerk = threading.Thread(target=self._serve, daemon=True)
        self._clerk.start()
        return self

    def __exit__(self, *_):
        self._closing.set()
        self._clerk.join(timeout=10.0)
        self._door.close()
        if os.path.lexists(self.where):
            os.unlink(self.where)


def one_cpu():
    """Holds this process, and so everything it starts from here on, to a single CPU. Where the platform
    does not let a process choose its CPUs the runs go ahead, still with one thread to a library."""
    try:
        allowed = sorted(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {allowed[-1]})
    except (AttributeError, OSError):
        pass


def sweep(started, unprivileged):
    """Ends the run's process group and, when it ran as nobody, every process of that user."""
    try:
        os.killpg(started.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if not unprivileged:
        return
    for _ in range(60):
        alive = False
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                with open("/proc/%s/status" % entry) as handle:
                    lines = handle.read().splitlines()
                owner = next(int(line.split()[1]) for line in lines if line.startswith("Uid:"))
                gone = any(line.startswith("State:") and line.split()[1] == "Z" for line in lines)
                if owner == NOBODY and not gone:
                    os.kill(int(entry), signal.SIGKILL)
                    alive = True
            except (OSError, StopIteration, ValueError):
                continue
        if not alive:
            return
        time.sleep(0.05)


def plain_copy(source, target):
    """Copies a regular file that is not reached through a link; anything else is an error."""
    handle = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(handle, "rb") as given:
        if not stat.S_ISREG(os.fstat(given.fileno()).st_mode):
            raise OSError("%s is not a regular file" % source)
        with open(target, "wb") as copy:
            shutil.copyfileobj(given, copy)
    os.chmod(target, 0o644)


def run_site(program, package, desk, limit, unprivileged, tools=None):
    """Runs the program on one package. Returns (how it ended, seconds, what OUT_CSV holds or None).

    How it ended is "finished", "over the limit", or a sentence about a run that could not be started or that
    exited with a status other than 0. OUT_CSV is read only after a run that finished.
    """
    box = tempfile.mkdtemp(prefix="survey_")
    started = None
    try:
        work, copy = os.path.join(box, "run"), os.path.join(box, "package")
        os.mkdir(work)
        os.mkdir(copy)
        # Modes are set outright, never left to the umask: test.sh runs this under umask 077, and the program,
        # which is another user, has to reach its package and its run directory all the same.
        os.chmod(box, 0o755)
        os.chmod(copy, 0o755)
        try:
            plain_copy(program, os.path.join(work, "bearing.py"))
        except OSError as problem:
            return "bearing.py could not be read: %s" % problem, 0.0, None
        for name in PACKAGE:
            plain_copy(os.path.join(package, name), os.path.join(copy, name))
        os.chmod(work, 0o700)
        if unprivileged:
            os.chown(work, NOBODY, NOBODY)
        out_csv = os.path.join(work, "results.csv")
        command = [sys.executable, "bearing.py", copy, out_csv]
        if unprivileged:
            command = AS_NOBODY + command
        surroundings = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": work, "TMPDIR": work, "LANG": "C.UTF-8",
                        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        if tools:                                       # a checkout outside the image: where labsample is
            surroundings["PATH"] = tools + os.pathsep + surroundings["PATH"]
        complaints = tempfile.TemporaryFile()           # root's, outside the scratch directory
        with desk:
            begun = time.monotonic()
            started = subprocess.Popen(command, cwd=work, env=surroundings, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=complaints, start_new_session=True)
            try:
                started.wait(timeout=limit)
                in_time = True
            except subprocess.TimeoutExpired:
                in_time = False
            taken = time.monotonic() - begun
            sweep(started, unprivileged)
            started.wait()
        if not in_time:
            return "over the limit", taken, None        # whatever it wrote is left unopened
        if started.returncode != 0:
            complaints.seek(0)
            last = complaints.read()[-400:].decode("utf-8", "replace").strip().splitlines()
            return "exit status %d: %s" % (started.returncode, last[-1] if last else "nothing on stderr"), taken, None
        try:
            found = os.lstat(out_csv)
            if not stat.S_ISREG(found.st_mode):
                raise OSError("not a regular file")
            handle = os.open(out_csv, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(handle, "rb") as written:
                raw = written.read(OUTPUT_CAP + 1)
        except OSError as problem:
            return "finished", taken, Refused("OUT_CSV was not written as a file: %s" % problem)
        return "finished", taken, raw
    finally:
        if started is not None:
            sweep(started, unprivileged)
        shutil.rmtree(box, ignore_errors=True)


def read_table(raw, points):
    """{point: {quantity: value}} from what a run wrote, or Refused."""
    if isinstance(raw, Refused):
        raise raw
    if len(raw) > OUTPUT_CAP:
        raise Refused("OUT_CSV is larger than %d bytes" % OUTPUT_CAP)
    try:
        rows = [row for row in csv.reader(io.StringIO(raw.decode("utf-8"), newline="")) if row]
    except (UnicodeDecodeError, csv.Error) as problem:
        raise Refused("OUT_CSV cannot be read as CSV: %s" % problem)
    if not rows or rows[0] != COLUMNS:
        raise Refused("the first line of OUT_CSV is not the header %s" % ",".join(COLUMNS))
    table = {}
    for row in rows[1:]:
        if len(row) != len(COLUMNS):
            raise Refused("a row of OUT_CSV has %d fields, not %d" % (len(row), len(COLUMNS)))
        point = row[0].strip()                        # blanks round a field are not judged
        if point not in points:
            raise Refused("OUT_CSV has a row for %r, which is not a point of the package" % point[:60])
        if point in table:
            raise Refused("OUT_CSV has two rows for the point %s" % point)
        values = {}
        for name, text in zip(COLUMNS[1:], row[1:]):
            if not DECIMAL.match(text.strip()):
                raise Refused("%s of the point %s is not a decimal number: %r" % (name, point, text[:40]))
            value = float(text)
            if not math.isfinite(value):
                raise Refused("%s of the point %s is not finite" % (name, point))
            values[name] = value
        table[point] = values
    if len(table) != len(points):
        raise Refused("OUT_CSV has rows for %d of the package's %d points" % (len(table), len(points)))
    return table


def compare(table, truth):
    """(points with any quantity out of band, {quantity: largest error as a multiple of its band}, the worst)."""
    out, largest, worst = 0, {name: 0.0 for name, _, _ in BANDS}, None
    for point, true in truth.items():
        missed = False
        for name, measure, band in BANDS:
            error = abs(table[point][name] - true[name])
            if measure == "of the true value":
                error /= abs(true[name])
            share = error / band
            if share > largest[name]:
                largest[name] = share
            if error > band:
                missed = True
                if worst is None or share > worst[0]:
                    worst = (share, point, name, table[point][name], true[name])
        out += missed
    return out, largest, worst


def results_of(path):
    with open(path, newline="") as handle:
        return {row["point"]: {name: float(row[name]) for name in COLUMNS[1:]} for row in csv.DictReader(handle)}


def assess(program, sites=None, truths=None, books=None, limit=RUN_LIMIT_S, desk_at=DESK, tools=None):
    """Runs the program on every site under `sites` and judges it. Returns an Outcome."""
    sites = sites or os.path.join(HERE, "sites")
    truths = truths or os.path.join(HERE, "sealed", "truth")
    books = books or os.path.join(HERE, "lab", "sealed")
    outcome = Outcome()
    unprivileged = os.geteuid() == 0
    if unprivileged and shutil.which("setpriv") is None:
        outcome.stopped = "the program cannot be run as an unprivileged user here, so it is not run at all"
        return outcome
    one_cpu()
    names = sorted(name for name in os.listdir(sites) if os.path.isdir(os.path.join(sites, name)))
    sound = bool(names)
    for name in names:
        truth = results_of(os.path.join(truths, name + ".csv"))
        desk = Desk(name, lab.book_of(books, name), desk_at)
        ended, seconds, raw = run_site(program, os.path.join(sites, name), desk, limit, unprivileged, tools)
        entry = {"run": ended, "seconds": round(seconds, 1), "points": len(truth), "laboratory_order": desk.order}
        outcome.sites[name] = entry
        if ended == "over the limit":
            outcome.stopped = "the run on %s was still going after %d s" % (name, limit)
            return outcome                               # a run over the limit decides the whole assessment
        if ended != "finished":
            sound = False
            continue
        try:
            table = read_table(raw, truth)
        except Refused as problem:
            entry["refused"] = str(problem)
            sound = False
            continue
        out, largest, worst = compare(table, truth)
        entry["points_out_of_band"] = out
        entry["largest_error_over_band"] = {key: round(value, 3) for key, value in largest.items()}
        if worst is not None:
            entry["worst"] = "%s %s: %.6g against %.6g" % (worst[1], worst[2], worst[3], worst[4])
            sound = False
    outcome.accepted = sound
    return outcome


def explain(outcome):
    lines = []
    for name, entry in outcome.sites.items():
        if entry["run"] != "finished":
            lines.append("%s: %s" % (name, entry["run"]))
        elif "refused" in entry:
            lines.append("%s: %s" % (name, entry["refused"]))
        else:
            lines.append("%s: %d of %d points out of band in %.1f s%s" % (
                name, entry["points_out_of_band"], entry["points"], entry["seconds"],
                "; worst " + entry["worst"] if "worst" in entry else ""))
    if outcome.stopped:
        lines.append("stopped: " + outcome.stopped)
    lines.append("accepted" if outcome.accepted else "not accepted")
    return "\n".join(lines)


if __name__ == "__main__":
    print(explain(assess(sys.argv[1] if len(sys.argv) > 1 else "/app/output/bearing.py")))
