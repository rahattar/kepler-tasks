"""The checker: runs a delivered airflow.py on the six districts and says whether it is accepted.

    python3 judge_airflow.py [/app/output/airflow.py]

For each district under districts/, in name order:

  - a scratch directory is laid out: `prog/` with a copy of airflow.py and nothing else, owned by the user the
    program runs as, and `package/` with the district's ten files, readable and not writable by that user;
  - the survey crew's window opens for that district alone (Window). It holds the district's book from
    crew/books and answers one order by the rule in crew/lab.py, reached through `pqsurvey` on the PATH;
  - the program is started in `prog/` as `python3 airflow.py PACKAGE_DIR OUT_CSV` as the user nobody, in a
    session of its own, with one thread to a numerical library, and is given LIMIT_S seconds to exit. No CPU
    affinity is set: trials run side by side on one host would all land on the same core;
  - at exit or at the limit, the session and every other process of nobody are killed;
  - a run still going at the limit ends the judging: its output is not opened, no later district is run and
    the program is not accepted;
  - otherwise OUT_CSV is read (read_flows) and each flow compared with results/<district>.csv (in_band).

Accepted means: every run ended in time with exit status 0, every OUT_CSV is the table the task statement
describes, and every flow of every district is in band.

results/ holds the sealed result of authoring/provenance for the district as it is. This directory and the
crew's books are root's alone; the program runs as nobody.
"""
import csv
import io
import json
import math
import os
import re
import shutil
import signal
import socketserver
import stat
import subprocess
import sys
import tempfile
import threading
import time

sys.dont_write_bytecode = True
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "crew"))
import lab  # noqa: E402  (the crew's rule, the same file the program was written against)

LIMIT_S = 35                                  # seconds for each run of airflow.py, as the task statement has it
HEADER = ["point", "flow_m3_s"]
BAND_SHARE = 0.015                            # of the sealed flow
BAND_FLOOR = 0.03                             # m3/s, where that is more
MOST_BYTES = 2000000                          # the largest OUT_CSV that is read, as the task statement has it
PACKAGE = ("district.json", "branches.csv", "surveys.csv", "work_log.csv", "regulators.csv", "doors.csv",
           "fans.csv", "fan_curves.csv", "log.csv", "points.csv")
WINDOW = "/run/survey-crew/window"            # where the verifier's pqsurvey finds the crew
RUNS_AS = 65534                               # nobody
NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


class NotTheTable(Exception):
    """OUT_CSV is not what the task statement describes."""


class Window(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    """The survey crew for one run: the book of one district, one order."""
    daemon_threads = True
    allow_reuse_address = True

    class Caller(socketserver.StreamRequestHandler):
        timeout = 5.0

        def handle(self):
            try:
                words = json.loads(self.rfile.read(200000).decode())
                if not (isinstance(words, list) and words and all(isinstance(w, str) for w in words)):
                    raise ValueError
                reply = self.server.order(words[0], words[1:])
            except (ValueError, OSError):
                reply = [2, lab.USAGE]
            try:
                self.wfile.write(json.dumps(reply).encode())
            except OSError:
                pass

    def __init__(self, district, book, where):
        self.district, self.book, self.where = district, book, where
        self.placed = None
        self._one = threading.Lock()
        os.makedirs(os.path.dirname(where), exist_ok=True)
        os.chmod(os.path.dirname(where), 0o755)                 # said outright: test.sh sets umask 077
        if os.path.lexists(where):
            os.unlink(where)
        super().__init__(where, Window.Caller)
        os.chmod(where, 0o666)
        self._clerk = threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        self._clerk.start()

    def order(self, district, branches):
        if district != self.district or self.book is None:
            return [1, lab.UNKNOWN]
        taken, words = lab.answer(self.book, branches)
        if not taken:
            return [1, words]
        with self._one:
            if self.placed is not None:
                return [1, lab.ALREADY]
            self.placed = list(branches)                        # written down before a figure leaves
        return [0, words]

    def shut(self):
        self.shutdown()
        self.server_close()
        if os.path.lexists(self.where):
            os.unlink(self.where)


def clear_out(leader, others_too):
    """Kills the run's session and, when it ran as nobody, whatever else that user still has running."""
    try:
        os.killpg(leader, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if not others_too:
        return
    for _ in range(80):
        found = False
        for pid in filter(str.isdigit, os.listdir("/proc")):
            try:
                with open("/proc/%s/status" % pid) as handle:
                    status = dict(line.split(":", 1) for line in handle.read().splitlines() if ":" in line)
                if int(status["Uid"].split()[0]) == RUNS_AS and status["State"].split()[0] != "Z":
                    os.kill(int(pid), signal.SIGKILL)
                    found = True
            except (OSError, KeyError, ValueError, IndexError):
                pass
        if not found:
            return
        time.sleep(0.05)


def bring(source, target):
    """A copy of a regular file, never through a link."""
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as given:
        if not stat.S_ISREG(os.fstat(given.fileno()).st_mode):
            raise OSError("not a regular file")
        with open(target, "wb") as copy:
            shutil.copyfileobj(given, copy)
    os.chmod(target, 0o644)


def run_district(program, package, window, limit, lowered, path_first=None):
    """One run. Returns (ending, seconds, bytes of OUT_CSV or a NotTheTable or None).

    ending is "in time", "over the limit", or a sentence for a run that could not start or ended with a
    status other than 0. OUT_CSV is opened only after a run that ended in time with status 0.
    """
    scratch = tempfile.mkdtemp(prefix="district_")
    child = None
    try:
        prog, pack = os.path.join(scratch, "prog"), os.path.join(scratch, "package")
        os.mkdir(prog)
        os.mkdir(pack)
        for place, mode in ((scratch, 0o755), (pack, 0o755), (prog, 0o700)):
            os.chmod(place, mode)                               # never left to the umask
        try:
            bring(program, os.path.join(prog, "airflow.py"))
        except OSError as trouble:
            return "airflow.py could not be read (%s)" % trouble, 0.0, None
        for name in PACKAGE:
            bring(os.path.join(package, name), os.path.join(pack, name))
        if lowered:
            os.chown(prog, RUNS_AS, RUNS_AS)
        out_csv = os.path.join(prog, "out.csv")
        argv = [sys.executable, "airflow.py", pack, out_csv]
        if lowered:
            argv = ["setpriv", "--reuid=%d" % RUNS_AS, "--regid=%d" % RUNS_AS, "--clear-groups", "--inh-caps=-all"] + argv
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": prog, "TMPDIR": prog, "LANG": "C.UTF-8",
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        if path_first:                                          # a checkout outside the image: where pqsurvey is
            env["PATH"] = path_first + os.pathsep + env["PATH"]
        if window.where != WINDOW:
            env["SURVEY_WINDOW"] = window.where
        said = tempfile.TemporaryFile()
        clock = time.monotonic()
        child = subprocess.Popen(argv, cwd=prog, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=said, start_new_session=True)
        try:
            child.wait(timeout=limit)
            late = False
        except subprocess.TimeoutExpired:
            late = True
        spent = time.monotonic() - clock
        clear_out(child.pid, lowered)
        child.wait()
        if late:
            return "over the limit", spent, None                # nothing it wrote is opened
        if child.returncode != 0:
            said.seek(0)
            tail = said.read()[-500:].decode("utf-8", "replace").strip().splitlines()
            return "exit status %d (%s)" % (child.returncode, tail[-1] if tail else "nothing on stderr"), spent, None
        try:
            if not stat.S_ISREG(os.lstat(out_csv).st_mode):
                raise OSError("not a regular file")
            fd = os.open(out_csv, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as written:
                return "in time", spent, written.read(MOST_BYTES + 1)
        except OSError as trouble:
            return "in time", spent, NotTheTable("OUT_CSV was not written as a file (%s)" % trouble)
    finally:
        if child is not None:
            clear_out(child.pid, lowered)
        window.shut()
        shutil.rmtree(scratch, ignore_errors=True)


def read_flows(raw, points):
    """{point: flow} from the bytes of OUT_CSV, held to the task statement and no further."""
    if isinstance(raw, NotTheTable):
        raise raw
    if len(raw) > MOST_BYTES:
        raise NotTheTable("OUT_CSV is larger than %d bytes" % MOST_BYTES)
    try:
        rows = [row for row in csv.reader(io.StringIO(raw.decode("utf-8"), newline="")) if row]
    except (UnicodeDecodeError, csv.Error) as trouble:
        raise NotTheTable("OUT_CSV does not read as CSV (%s)" % trouble)
    if not rows or rows[0] != HEADER:
        raise NotTheTable("OUT_CSV does not begin with the header %s" % ",".join(HEADER))
    flows = {}
    for row in rows[1:]:
        if len(row) != 2:
            raise NotTheTable("a row of OUT_CSV has %d fields" % len(row))
        point, figure = row[0].strip(), row[1].strip()
        if point not in points:
            raise NotTheTable("OUT_CSV has a row for %r, which is no point of the package" % point[:50])
        if point in flows:
            raise NotTheTable("OUT_CSV has the point %s twice" % point)
        if not NUMBER.fullmatch(figure) or not math.isfinite(float(figure)):
            raise NotTheTable("the airflow at %s is not a decimal number (%r)" % (point, figure[:30]))
        flows[point] = float(figure)
    if len(flows) != len(points):
        raise NotTheTable("OUT_CSV has %d of the package's %d points" % (len(flows), len(points)))
    return flows


def in_band(flow, sealed):
    return abs(flow - sealed) <= max(BAND_SHARE * abs(sealed), BAND_FLOOR)


def sealed_flows(path):
    with open(path, newline="") as handle:
        return {row["point"]: float(row["flow_m3_s"]) for row in csv.DictReader(handle)}


def judge(program, districts=None, results=None, books=None, limit=LIMIT_S, window=WINDOW, path_first=None):
    """The verdict as a dictionary: accepted, stopped (why the judging ended early, if it did), districts."""
    districts = districts or os.path.join(BASE, "districts")
    results = results or os.path.join(BASE, "results")
    books = books or os.path.join(BASE, "crew", "books")
    verdict = {"accepted": False, "stopped": "", "districts": {}}
    lowered = os.geteuid() == 0
    if lowered and shutil.which("setpriv") is None:
        verdict["stopped"] = "the program cannot be run as an unprivileged user here, so it is not run"
        return verdict
    names = sorted(n for n in os.listdir(districts) if os.path.isdir(os.path.join(districts, n)))
    clean = bool(names)
    for name in names:
        sealed = sealed_flows(os.path.join(results, name + ".csv"))
        crew = Window(name, lab.book(books, name), window)
        ending, seconds, raw = run_district(program, os.path.join(districts, name), crew, limit, lowered, path_first)
        note = verdict["districts"][name] = {"run": ending, "seconds": round(seconds, 1), "points": len(sealed),
                                             "survey_order": crew.placed}
        if ending == "over the limit":
            verdict["stopped"] = "the run on %s was still going after %d s" % (name, limit)
            return verdict
        if ending != "in time":
            clean = False
            continue
        try:
            flows = read_flows(raw, sealed)
        except NotTheTable as trouble:
            note["not_the_table"] = str(trouble)
            clean = False
            continue
        out = [p for p in sealed if not in_band(flows[p], sealed[p])]
        share = max(abs(flows[p] - sealed[p]) / max(BAND_SHARE * abs(sealed[p]), BAND_FLOOR) for p in sealed)
        note["points_out_of_band"] = len(out)
        note["largest_error_over_band"] = round(share, 3)
        if out:
            worst = max(out, key=lambda p: abs(flows[p] - sealed[p]) / max(BAND_SHARE * abs(sealed[p]), BAND_FLOOR))
            note["worst"] = "%s: %.5g against %.5g" % (worst, flows[worst], sealed[worst])
            clean = False
    verdict["accepted"] = clean
    return verdict


def account(verdict):
    lines = []
    for name, note in verdict["districts"].items():
        if note["run"] != "in time":
            lines.append("%s: %s" % (name, note["run"]))
        elif "not_the_table" in note:
            lines.append("%s: %s" % (name, note["not_the_table"]))
        else:
            lines.append("%s: %d of %d points out of band, largest error %.2f of the band, %.1f s%s" % (
                name, note["points_out_of_band"], note["points"], note["largest_error_over_band"], note["seconds"],
                "; worst " + note["worst"] if "worst" in note else ""))
    if verdict["stopped"]:
        lines.append("stopped: " + verdict["stopped"])
    lines.append("accepted" if verdict["accepted"] else "not accepted")
    return "\n".join(lines)


if __name__ == "__main__":
    print(account(judge(sys.argv[1] if len(sys.argv) > 1 else "/app/output/airflow.py")))
