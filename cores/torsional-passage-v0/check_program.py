"""The assessment of a submitted peaks.py.

    python3 check_program.py /app/output/peaks.py

The program is run once on each set under sets/, in name order, and what each run writes is compared
with the sealed results under sealed/results/. Nothing the program's author left behind is read: only the
program itself is taken, and every table judged here is written by a run started here.

How one run goes
  - a fresh scratch directory gets two folders: `run`, holding a copy of peaks.py and nothing else, and
    `session`, a read-only copy of the cell's package;
  - the program is started in `run` as `python3 peaks.py SESSION_DIR OUT_CSV`, under the user nobody when
    this checker is root, with OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1 so that a numerical library
    keeps to one thread, as the leader of a session of its own; no CPU is pinned, since several verifiers
    may share a host;
  - it has RUN_LIMIT_S seconds on 1 CPU: the run is over the limit when RUN_LIMIT_S seconds have passed since
    it started, or when the processor time, user and system, of the program and of every process it starts
    reaches RUN_LIMIT_S seconds (ProcessorTime). On one CPU the two come to the same; work spread over two
    CPUs uses up its seconds in half the time;
  - a run that is over the limit ends the assessment: its whole session is killed, the table
    it may have written is never opened, the cells after it are not run, and the program is not accepted;
  - a run that ends in time must have exit status 0 and must have written the table the task statement
    describes (read_table); each value is then held against its band (BANDS).

The program is accepted when that holds for every cell. There is no share of cells, rows or quantities that
lets a miss or a late run through.
"""
import csv
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
BASE = os.path.dirname(os.path.abspath(__file__))

RUN_LIMIT_S = 6                       # seconds a run of peaks.py may take; the task statement gives the same
HEADER = ["run", "crankshaft_kNm", "coupling_kNm", "generator_shaft_kNm", "rubber_C"]
# quantity -> ("share", s): within s of the sealed value as a share of it; ("units", d): within d of it, in its own unit (degrees)
BANDS = {
    "crankshaft_kNm": ("share", 0.03),
    "coupling_kNm": ("share", 0.03),
    "generator_shaft_kNm": ("share", 0.03),
    "rubber_C": ("units", 1.0),
}
TABLE_BYTES = 2 * 1024 * 1024         # the statement's 2 MiB; a table of 6 cylinders by 40 points is about 15 kB
NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
WHOLE = re.compile(r"\d+")
NOBODY_UID = 65534


class NotTheTable(Exception):
    """What a run wrote is not the table the task statement describes."""


def session_of(set_dir):
    """The runs of a set, read from the set itself."""
    with open(os.path.join(set_dir, "runs.csv"), newline="") as handle:
        return [row["run"] for row in csv.DictReader(handle)]


def read_table(path, runs):
    """The table at `path` as {run: {quantity: value}}, or NotTheTable.

    Held to the task statement and no further. Stated there: the header, a row for every run and for nothing
    else, values that are decimal numbers. Not stated, so not judged: the order of the rows, LF or CRLF, a
    final line end, empty lines, quoting of fields, blanks round a field.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as problem:
        raise NotTheTable("no table was written (%s)" % problem.strerror)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise NotTheTable("what was written is not a regular file")
    with os.fdopen(fd, "rb") as handle:
        raw = handle.read(TABLE_BYTES + 1)
    if len(raw) > TABLE_BYTES:
        raise NotTheTable("the table is larger than %d bytes" % TABLE_BYTES)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise NotTheTable("the table is not text")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise NotTheTable("the table is empty")
    if lines[0] != ",".join(HEADER):
        raise NotTheTable("the header is not %s" % ",".join(HEADER))
    wanted = set(runs)
    table = {}
    for number, fields in enumerate(csv.reader(lines[1:]), start=2):
        if len(fields) != len(HEADER):
            raise NotTheTable("line %d has %d fields" % (number, len(fields)))
        fields = [f.strip() for f in fields]
        key = fields[0]
        if key not in wanted:
            raise NotTheTable("line %d: run %r is not in the set" % (number, key))
        if key in table:
            raise NotTheTable("line %d: run %r is given twice" % (number, key))
        values = {}
        for name, field in zip(HEADER[1:], fields[1:]):
            if not NUMBER.fullmatch(field):
                raise NotTheTable("line %d: %s is %r, not a decimal number" % (number, name, field))
            value = float(field)
            if not math.isfinite(value):
                raise NotTheTable("line %d: %s is not finite" % (number, name))
            values[name] = value
        table[key] = values
    missing = wanted - set(table)
    if missing:
        raise NotTheTable("%d rows are missing, the first being run %s" % (len(missing), sorted(missing)[0]))
    return table


def sealed_results(path):
    with open(path, newline="") as handle:
        return {row["run"]: {name: float(row[name]) for name in HEADER[1:]} for row in csv.DictReader(handle)}


def hold_to_bands(table, sealed):
    """(rows with a value outside its band, the widest departure of each quantity as a multiple of its band)."""
    rows_out, widest = 0, {name: 0.0 for name in BANDS}
    for key, want in sealed.items():
        inside = True
        for name, (kind, size) in BANDS.items():
            gap = abs(table[key][name] - want[name])
            band = size * abs(want[name]) if kind == "share" else size
            widest[name] = max(widest[name], gap / band)
            if not gap <= band:
                inside = False
        rows_out += not inside
    return rows_out, widest


def end_session(leader_pid, as_nobody):
    """Kills the run's session and, where runs are made as nobody, whatever else that user still has going."""
    try:
        os.killpg(leader_pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if not as_nobody:
        return
    for _ in range(40):
        left = 0
        for name in os.listdir("/proc"):
            if not name.isdigit():
                continue
            try:
                with open("/proc/%s/status" % name) as handle:
                    status = handle.read()
            except OSError:
                continue
            owner = re.search(r"^Uid:\s+(\d+)", status, re.M)
            state = re.search(r"^State:\s+(\S)", status, re.M)
            if owner and int(owner.group(1)) == NOBODY_UID and state and state.group(1) != "Z":
                try:
                    os.kill(int(name), signal.SIGKILL)
                    left += 1
                except OSError:
                    pass
        if not left:
            return
        time.sleep(0.05)


class ProcessorTime:
    """User and system time of a run: the program and every process it starts, together.

    Counted twice, and the larger count is taken, since each can only come out short. While the run goes,
    /proc is read every tenth of a second, and the time of each process of the run (any process of nobody when
    runs are made as nobody, else any process in the run's session) is kept as last read, once a process. When
    the run is over, the kernel's own total for the program and every child it waited for. A process that was
    never waited for and lived under a tenth of a second can be missed by both, and used under a tenth of a
    second.
    """
    HZ = os.sysconf("SC_CLK_TCK")

    def __init__(self, leader_pid, as_nobody):
        self.leader_pid, self.as_nobody, self.last_read = leader_pid, as_nobody, {}

    def read(self):
        for name in os.listdir("/proc"):
            if not name.isdigit():
                continue
            try:
                with open("/proc/%s/stat" % name) as handle:
                    fields = handle.read()
                after = fields[fields.rindex(")") + 2:].split()
                if self.as_nobody:
                    if os.stat("/proc/" + name).st_uid != NOBODY_UID:
                        continue
                elif int(after[3]) != self.leader_pid:
                    continue
                # fields 14 and 15 of stat are utime and stime; 22 is the start time, which tells a reused pid apart
                self.last_read[(name, after[19])] = (int(after[11]) + int(after[12])) / float(self.HZ)
            except (OSError, ValueError, IndexError):
                continue
        return sum(self.last_read.values())


def run_once(program, cell_dir, limit, as_nobody):
    """One run on one package. Returns (ending, seconds, processor seconds, scratch directory, path of the table).
    ending is "in time" with the exit status appended, or "over the limit"."""
    scratch = tempfile.mkdtemp(prefix="indicating-")
    run_dir, session = os.path.join(scratch, "run"), os.path.join(scratch, "session")
    os.mkdir(run_dir)
    shutil.copytree(cell_dir, session)
    fd = os.open(program, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as given, open(os.path.join(run_dir, "peaks.py"), "wb") as copy:
        if not stat.S_ISREG(os.fstat(given.fileno()).st_mode):
            raise OSError("peaks.py is not a regular file")
        shutil.copyfileobj(given, copy)
    for folder, _, files in os.walk(session):
        os.chmod(folder, 0o755)
        for name in files:
            os.chmod(os.path.join(folder, name), 0o444)
    os.chmod(scratch, 0o755)
    os.chmod(os.path.join(run_dir, "peaks.py"), 0o644)
    out_dir = os.path.join(scratch, "out")
    os.mkdir(out_dir)
    command = [sys.executable, "peaks.py", session, os.path.join(out_dir, "results.csv")]
    if as_nobody:
        for place in (run_dir, out_dir):
            os.chown(place, NOBODY_UID, NOBODY_UID)
        command = ["setpriv", "--reuid=%d" % NOBODY_UID, "--regid=%d" % NOBODY_UID, "--clear-groups"] + command
    surroundings = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": run_dir, "TMPDIR": out_dir,
                    "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"}
    began = time.monotonic()
    started = subprocess.Popen(command, cwd=run_dir, env=surroundings, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    meter = ProcessorTime(started.pid, as_nobody)
    late, waited = False, None
    while True:
        # the program is reaped with wait4 rather than by Popen, so that the kernel's count of its time comes too
        pid, waited, usage = os.wait4(started.pid, os.WNOHANG)
        if pid == started.pid:
            break
        waited = None
        if time.monotonic() - began >= limit or meter.read() >= limit:
            late = True
            break
        time.sleep(0.1)
    took = time.monotonic() - began
    meter.read()
    end_session(started.pid, as_nobody)
    if waited is None:
        _, waited, usage = os.wait4(started.pid, 0)
    started.returncode = os.waitstatus_to_exitcode(waited)
    processor = max(sum(meter.last_read.values()), usage.ru_utime + usage.ru_stime)
    if late or took >= limit or processor >= limit:
        ending = "over the limit"
    else:
        ending = "in time, exit status %d" % started.returncode
    return ending, took, processor, scratch, os.path.join(out_dir, "results.csv")


def assess(program, cells_dir=None, results_dir=None, limit=RUN_LIMIT_S, as_nobody=None):
    """Runs the program on every cell. Returns {"accepted": bool, "stopped": str, "cells": {name: finding}}."""
    cells_dir = cells_dir or os.path.join(BASE, "sets")
    results_dir = results_dir or os.path.join(BASE, "sealed", "results")
    if as_nobody is None:
        as_nobody = os.geteuid() == 0 and shutil.which("setpriv") is not None
    report = {"accepted": False, "stopped": "", "cells": {}}
    names = sorted(name for name in os.listdir(cells_dir) if os.path.isdir(os.path.join(cells_dir, name)))
    if not names:
        report["stopped"] = "there are no cells to run"
        return report
    if not os.path.isfile(program):
        report["stopped"] = "there is no program at %s" % program
        return report
    sound = True
    for name in names:
        cell_dir = os.path.join(cells_dir, name)
        ending, took, processor, scratch, table_path = run_once(program, cell_dir, limit, as_nobody)
        finding = {"seconds": round(took, 2), "processor_seconds": round(processor, 2), "ending": ending}
        report["cells"][name] = finding
        try:
            if ending == "over the limit":
                finding["finding"] = "over the limit of %d s, of time or of processor time" % limit
                report["stopped"] = "the run on %s had used %d s, of time or of processor time; the cells after it were not run" % (name, limit)
                return report
            if ending != "in time, exit status 0":
                finding["finding"] = ending
                sound = False
                continue
            runs = session_of(cell_dir)
            try:
                table = read_table(table_path, runs)
            except NotTheTable as why:
                finding["finding"] = str(why)
                sound = False
                continue
            rows_out, widest = hold_to_bands(table, sealed_results(os.path.join(results_dir, name + ".csv")))
            finding["rows"] = len(table)
            finding["rows_out"] = rows_out
            finding["widest"] = {quantity: round(value, 3) for quantity, value in widest.items()}
            finding["finding"] = "every row within its bands" if rows_out == 0 else "%d of %d rows out of band" % (rows_out, len(table))
            sound = sound and rows_out == 0
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
    report["accepted"] = sound
    return report


def account(report):
    """The report as lines of text."""
    lines = []
    for name, finding in report["cells"].items():
        line = "%-8s %5.2f s (%5.2f s of processor)  %s" % (name, finding["seconds"], finding.get("processor_seconds", 0.0), finding["finding"])
        if "widest" in finding:
            line += "  (widest departure, in bands: %s)" % ", ".join(
                "%s %.2f" % (quantity.split("_")[0], value) for quantity, value in finding["widest"].items())
        lines.append(line)
    if report["stopped"]:
        lines.append(report["stopped"])
    lines.append("accepted" if report["accepted"] else "not accepted")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 check_program.py PATH_TO_INDICATE_PY")
    outcome = assess(sys.argv[1])
    print(account(outcome))
    sys.exit(0 if outcome["accepted"] else 1)
