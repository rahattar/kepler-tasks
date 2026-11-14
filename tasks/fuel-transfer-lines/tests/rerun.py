"""rerun.py: runs a delivered lines.py on the six sites under tests/sites and compares what it writes with the
sealed results.

    python3 rerun.py [/app/output/lines.py]

One site at a time, in name order (`Run`):

  room/work   a copy of lines.py and nothing else; the program's working directory, HOME and TMPDIR. When
              the checker is root the directory is given to the user nobody and the program is started as that
              user (setresuid and setresgid, through subprocess's user= and group=), with no supplementary
              group, in a session of its own, with one thread to a numerical library;
  room/site   the six files of the package, which the program can read and cannot change;
  the desk    the survey crew for this one run. The `heatsurvey` on the PATH leaves the program's order as a
              file under <desk>/asks; the checker picks it up between two looks at the clock, answers it by
              crew/lab.py from the site's book under crew/books, which only the checker can open, and leaves
              the answer under <desk>/answers. One order is taken for the run; an order that lab.py turns down
              is not that order.

The program is started as `python3 lines.py PACKAGE_DIR OUT_CSV` and has LIMIT_S seconds on 1 CPU. That is
held two ways, and the run is over the limit when either is used up: LIMIT_S seconds on the clock; and LIMIT_S
seconds of CPU time, user and system, added over the program and every process it starts (`Meter`). A
program that keeps to one CPU meets both together; one that spreads its work over two uses up its CPU time
in half the time on the clock. No CPU affinity is set anywhere.

When the program has exited, or is over the limit, its session and (as root) every process of nobody are
killed. A run over the limit ends the whole comparison: nothing that run wrote is opened, no further site is
run, and the program is not accepted. Otherwise OUT_CSV has to be the table the task statement describes
(`table`), and every pressure drop and outlet temperature in it has to be within the band of the sealed result
of authoring/provenance for that record (`inside`).

Accepted: all six runs inside the limit with exit status 0, six tables, every value of every record in band.
"""
import csv
import io
import json
import math
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(TESTS, "crew"))
import lab  # noqa: E402  the crew's rule; environment/rig/lab.py is the same file

LIMIT_S = 40                      # seconds for one run of lines.py, as the task statement gives it
COLUMNS = ["record", "dp_kPa", "t_out_C"]
DP_SHARE = 0.025                  # of the sealed pressure drop
T_BAND_K = 0.5                    # kelvin either side of the sealed outlet temperature
MOST_BYTES = 1000000              # the largest OUT_CSV that is read, as the task statement gives it
SIX_FILES = ("site.json", "oils.csv", "lines.csv", "surveys.csv", "work_log.csv", "records.csv")
DESK = "/run/heat-desk"           # where the heatsurvey of the verifier's image leaves an order
NOBODY = 65534
LOOK_S = 0.05                     # between two looks at the clock, the meter and the desk
DECIMAL = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?\Z")
SLIP = re.compile(r"\d{1,12}-\d{1,24}\.ask\Z")


class Unreadable(Exception):
    """OUT_CSV is not the table the task statement describes; the message says in what."""


class Desk:
    """The survey crew for one run of one site."""

    def __init__(self, where, site, book, run_user):
        self.where, self.site, self.book = where, site, book
        self.order = None                                   # the pipes of the one order taken
        self.turned_down = 0
        self.asks, self.answers = os.path.join(where, "asks"), os.path.join(where, "answers")
        shutil.rmtree(where, ignore_errors=True)
        for place, mode in ((where, 0o755), (self.asks, 0o700), (self.answers, 0o755)):
            os.makedirs(place, exist_ok=True)
            os.chmod(place, mode)                           # outright: tests/test.sh works under umask 077
        if run_user is not None:
            os.chown(self.asks, run_user, run_user)

    def answer(self, site, pipes):
        if site != self.site or self.book is None:
            return 1, lab.NO_SUCH_SITE
        taken, words = lab.weigh(self.book, pipes)
        if not taken:
            self.turned_down += 1
            return 1, words
        if self.order is not None:
            return 1, lab.ONE_A_RUN
        self.order = list(pipes)                            # entered before a figure leaves the desk
        return 0, words

    def serve(self):
        """Answers every order waiting under asks/."""
        try:
            waiting = sorted(name for name in os.listdir(self.asks) if SLIP.match(name))
        except OSError:
            return
        for name in waiting[:50]:
            path = os.path.join(self.asks, name)
            status, words = 2, lab.USAGE
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, "rb") as slip:
                    if stat.S_ISREG(os.fstat(slip.fileno()).st_mode):
                        asked = json.loads(slip.read(200000).decode("utf-8"))
                        if (isinstance(asked, dict) and isinstance(asked.get("site"), str) and isinstance(asked.get("pipes"), list)
                                and all(isinstance(p, str) for p in asked["pipes"])):
                            status, words = self.answer(asked["site"], asked["pipes"])
            except (OSError, ValueError):
                pass
            try:
                os.unlink(path)
            except OSError:
                pass
            reply = os.path.join(self.answers, name[:-4])
            try:
                fd = os.open(reply + ".part", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
                with os.fdopen(fd, "w") as handle:
                    json.dump({"status": status, "words": words}, handle)
                os.chmod(reply + ".part", 0o644)
                os.rename(reply + ".part", reply + ".txt")
            except OSError:
                pass

    def close(self):
        shutil.rmtree(self.where, ignore_errors=True)


class Meter:
    """CPU seconds, user and system, of a run: the program and every process it starts.

    Each look reads /proc and keeps, for every process of the run, its own CPU time as last seen; a process is
    of the run if it is nobody's (where the program runs as nobody) or in the program's session (where it runs
    as the checker's own user). `total` is the sum over every process ever seen. `settle` takes, at the end,
    the larger of that sum and the kernel's own figure for the program and all the descendants it waited for.
    Either count can only fall short: what both miss is a process that lived for less than one look and was
    never waited for.
    """

    def __init__(self, leader, as_nobody):
        self.leader, self.as_nobody, self.last = leader, as_nobody, {}
        self.hz = float(os.sysconf("SC_CLK_TCK"))

    def total(self):
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                if self.as_nobody and os.stat("/proc/" + entry).st_uid != NOBODY:
                    continue
                with open("/proc/%s/stat" % entry) as handle:
                    text = handle.read()
                field = text[text.rindex(")") + 2:].split()     # field[0] is the state, the third field of stat
                if not self.as_nobody and int(field[3]) != self.leader:
                    continue
                self.last[(entry, field[19])] = (int(field[11]) + int(field[12])) / self.hz
            except (OSError, ValueError, IndexError):
                continue
        return sum(self.last.values())

    def settle(self, usage):
        return max(self.total(), usage.ru_utime + usage.ru_stime if usage else 0.0)


def sweep(leader, as_nobody):
    """Kills the program's session and, where it ran as nobody, everything else nobody has running."""
    try:
        os.killpg(leader, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if not as_nobody:
        return
    for _ in range(100):
        alive = 0
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                if os.stat("/proc/" + entry).st_uid != NOBODY:
                    continue
                with open("/proc/%s/stat" % entry) as handle:
                    text = handle.read()
                if text[text.rindex(")") + 2] == "Z":
                    continue
                os.kill(int(entry), signal.SIGKILL)
                alive += 1
            except (OSError, ValueError, IndexError):
                continue
        if not alive:
            return
        time.sleep(0.03)


def copy_plain(source, target):
    """A copy of a regular file, read without following a link, readable by all."""
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as given:
        if not stat.S_ISREG(os.fstat(given.fileno()).st_mode):
            raise OSError("not a regular file")
        with open(target, "wb") as copy:
            shutil.copyfileobj(given, copy)
    os.chmod(target, 0o644)


class Run:
    """One run of the program on one site. After `go`: ending, seconds, cpu_seconds, raw."""

    def __init__(self, program, package, desk, limit, path_first=None):
        self.program, self.package, self.desk, self.limit, self.path_first = program, package, desk, limit, path_first
        self.as_nobody = os.geteuid() == 0
        self.ending, self.seconds, self.cpu_seconds, self.raw = "not started", 0.0, 0.0, None

    def go(self):
        room = tempfile.mkdtemp(prefix="site_run_")
        child = None
        try:
            work, site = os.path.join(room, "work"), os.path.join(room, "site")
            for place, mode in ((room, 0o755), (work, 0o700), (site, 0o755)):
                if place != room:
                    os.mkdir(place)
                os.chmod(place, mode)
            try:
                copy_plain(self.program, os.path.join(work, "lines.py"))
            except OSError as trouble:
                self.ending = "lines.py could not be read (%s)" % trouble
                return self
            for name in SIX_FILES:
                copy_plain(os.path.join(self.package, name), os.path.join(site, name))
            if self.as_nobody:
                os.chown(work, NOBODY, NOBODY)
            out_csv = os.path.join(work, "out.csv")
            env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": work, "TMPDIR": work, "LANG": "C.UTF-8",
                   "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
            if self.path_first:                             # outside the image: where the verifier's heatsurvey is
                env["PATH"] = self.path_first + os.pathsep + env["PATH"]
            if self.desk.where != DESK:
                env["HEAT_DESK"] = self.desk.where
            who = dict(user=NOBODY, group=NOBODY, extra_groups=[]) if self.as_nobody else {}
            stderr = tempfile.TemporaryFile()
            began = time.monotonic()
            child = subprocess.Popen([sys.executable, "lines.py", site, out_csv], cwd=work, env=env, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=stderr, start_new_session=True, **who)
            meter = Meter(child.pid, self.as_nobody)
            status, usage, over = None, None, False
            while True:
                self.desk.serve()
                pid, code, used = os.wait4(child.pid, os.WNOHANG)     # wait4, for the kernel's count of CPU time
                if pid == child.pid:
                    status, usage = code, used
                    break
                if time.monotonic() - began >= self.limit or meter.total() >= self.limit:
                    over = True
                    break
                time.sleep(LOOK_S)
            self.seconds = time.monotonic() - began
            meter.total()
            sweep(child.pid, self.as_nobody)
            if status is None:
                _, status, usage = os.wait4(child.pid, 0)
            child.returncode = os.waitstatus_to_exitcode(status)
            self.cpu_seconds = meter.settle(usage)
            if over or self.cpu_seconds >= self.limit:
                self.ending = "over the limit"              # and out.csv stays unopened
                return self
            if child.returncode != 0:
                stderr.seek(0)
                last = stderr.read()[-400:].decode("utf-8", "replace").strip().splitlines()
                self.ending = "exit status %d (%s)" % (child.returncode, last[-1] if last else "nothing on stderr")
                return self
            self.ending = "in time"
            try:
                if not stat.S_ISREG(os.lstat(out_csv).st_mode):
                    raise OSError("not a regular file")
                fd = os.open(out_csv, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd, "rb") as written:
                    self.raw = written.read(MOST_BYTES + 1)
            except OSError as trouble:
                self.raw = Unreadable("OUT_CSV was not written as a file (%s)" % trouble)
            return self
        finally:
            if child is not None:
                sweep(child.pid, self.as_nobody)
            self.desk.close()
            shutil.rmtree(room, ignore_errors=True)


def table(raw, records):
    """{record: (dp_kPa, t_out_C)} from the bytes of OUT_CSV; what the task statement asks of it and no more."""
    if isinstance(raw, Unreadable):
        raise raw
    if len(raw) > MOST_BYTES:
        raise Unreadable("OUT_CSV is larger than %d bytes" % MOST_BYTES)
    try:
        rows = [row for row in csv.reader(io.StringIO(raw.decode("utf-8"), newline="")) if row]
    except (UnicodeDecodeError, csv.Error) as trouble:
        raise Unreadable("OUT_CSV cannot be read as CSV (%s)" % trouble)
    if not rows or rows[0] != COLUMNS:
        raise Unreadable("the first row of OUT_CSV is not the header %s" % ",".join(COLUMNS))
    found = {}
    for row in rows[1:]:
        if len(row) != len(COLUMNS):
            raise Unreadable("a row of OUT_CSV has %d fields" % len(row))
        record = row[0].strip()
        if record not in records:
            raise Unreadable("OUT_CSV has a row for %r, which is not a record of the package" % record[:40])
        if record in found:
            raise Unreadable("OUT_CSV has the record %s twice" % record)
        pair = []
        for column, field in zip(COLUMNS[1:], row[1:]):
            field = field.strip()
            if not DECIMAL.match(field) or not math.isfinite(float(field)):
                raise Unreadable("%s of %s is not a decimal number (%r)" % (column, record, field[:24]))
            pair.append(float(field))
        found[record] = tuple(pair)
    if len(found) != len(records):
        raise Unreadable("OUT_CSV has %d of the package's %d records" % (len(found), len(records)))
    return found


def shares(got, sealed):
    """How far a record's two values are from the sealed ones, each as a share of its band."""
    return abs(got[0] - sealed[0]) / (DP_SHARE * abs(sealed[0])), abs(got[1] - sealed[1]) / T_BAND_K


def inside(got, sealed):
    return abs(got[0] - sealed[0]) <= DP_SHARE * abs(sealed[0]) and abs(got[1] - sealed[1]) <= T_BAND_K


def sealed_results(path):
    with open(path, newline="") as handle:
        return {row["record"]: (float(row["dp_kPa"]), float(row["t_out_C"])) for row in csv.DictReader(handle)}


def judge(program, sites=None, results=None, books=None, limit=LIMIT_S, desk=DESK, path_first=None):
    """The verdict: {"accepted": bool, "stopped": why the comparison ended early, "sites": {name: notes}}."""
    sites = sites or os.path.join(TESTS, "sites")
    results = results or os.path.join(TESTS, "results")
    books = books or os.path.join(TESTS, "crew", "books")
    verdict = {"accepted": False, "stopped": "", "sites": {}}
    names = sorted(name for name in os.listdir(sites) if os.path.isdir(os.path.join(sites, name)))
    sound = bool(names)
    for name in names:
        sealed = sealed_results(os.path.join(results, name + ".csv"))
        crew = Desk(desk, name, lab.book_of(books, name), NOBODY if os.geteuid() == 0 else None)
        run = Run(program, os.path.join(sites, name), crew, limit, path_first).go()
        note = verdict["sites"][name] = {"run": run.ending, "seconds": round(run.seconds, 1), "cpu_seconds": round(run.cpu_seconds, 1),
                                         "records": len(sealed), "survey_order": crew.order}
        if run.ending == "over the limit":
            verdict["stopped"] = "the run on %s used up its %g s, on the clock or in CPU time" % (name, limit)
            return verdict
        if run.ending != "in time":
            sound = False
            continue
        try:
            got = table(run.raw, sealed)
        except Unreadable as trouble:
            note["not_the_table"] = str(trouble)
            sound = False
            continue
        out = [record for record in sealed if not inside(got[record], sealed[record])]
        far = {record: max(shares(got[record], sealed[record])) for record in sealed}
        worst = max(far, key=far.get)
        note["records_out_of_band"] = len(out)
        note["lines_out_of_band"] = sorted({record.split("/")[0] for record in out})
        note["largest_error_over_band"] = round(far[worst], 3)
        if out:
            note["worst"] = "%s: %.6g kPa and %.3f C against %.6g and %.3f" % ((worst,) + got[worst] + sealed[worst])
            sound = False
    verdict["accepted"] = sound
    return verdict


def account(verdict):
    """The verdict in words, one line a site."""
    lines = []
    for name, note in verdict["sites"].items():
        if note["run"] != "in time":
            lines.append("%s: %s" % (name, note["run"]))
        elif "not_the_table" in note:
            lines.append("%s: %s" % (name, note["not_the_table"]))
        else:
            lines.append("%s: %d of %d records out of band%s, largest error %.2f of the band, %.1f s on the clock and %.1f s of CPU, %s" % (
                name, note["records_out_of_band"], note["records"],
                " (%s)" % ", ".join(note["lines_out_of_band"]) if note["lines_out_of_band"] else "",
                note["largest_error_over_band"], note["seconds"], note["cpu_seconds"],
                "surveyed " + " ".join(note["survey_order"]) if note["survey_order"] else "no survey order"))
    if verdict["stopped"]:
        lines.append("stopped: " + verdict["stopped"])
    lines.append("accepted" if verdict["accepted"] else "not accepted")
    return "\n".join(lines)


if __name__ == "__main__":
    print(account(judge(sys.argv[1] if len(sys.argv) > 1 else "/app/output/lines.py")))
