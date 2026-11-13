"""The assessment of a submitted indicate.py.

    python3 check_program.py /app/output/indicate.py

The program is run once on each cell package under cells/, in name order, and what each run writes is compared
with the sealed results under sealed/results/. Nothing the program's author left behind is read: only the
program itself is taken, and every table judged here is written by a run started here.

How one run goes
  - a fresh scratch directory gets two folders: `run`, holding a copy of indicate.py and nothing else, and
    `session`, a read-only copy of the cell's package;
  - the program is started in `run` as `python3 indicate.py SESSION_DIR OUT_CSV`, under the user nobody when
    this checker is root, with OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1 so that a numerical library
    keeps to one thread, as the leader of a session of its own; no CPU is pinned, since several verifiers
    may share a host;
  - it has RUN_LIMIT_S seconds, by subprocess's timeout on the wait for it;
  - a run that is still going when the time is up ends the assessment: its whole session is killed, the table
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

RUN_LIMIT_S = 4                       # seconds a run of indicate.py may take; the task statement gives the same
HEADER = ["point", "cylinder", "imep_bar", "pmax_bar", "apmax_deg", "ca10_deg", "ca50_deg", "q_gross_J"]
# quantity -> ("share", s): within s of the sealed value as a share of it; ("units", d): within d of it, in its own unit (degrees)
BANDS = {
    "imep_bar": ("share", 0.02),
    "pmax_bar": ("share", 0.01),
    "apmax_deg": ("units", 0.3),
    "ca10_deg": ("units", 0.3),
    "ca50_deg": ("units", 0.3),
    "q_gross_J": ("share", 0.03),
}
TABLE_BYTES = 2 * 1024 * 1024         # the statement's 2 MiB; a table of 6 cylinders by 40 points is about 15 kB
NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
WHOLE = re.compile(r"\d+")
NOBODY_UID = 65534


class NotTheTable(Exception):
    """What a run wrote is not the table the task statement describes."""


def session_of(cell_dir):
    """The points and the number of cylinders of a package, read from the package itself."""
    import json
    with open(os.path.join(cell_dir, "engine.json")) as handle:
        cylinders = int(json.load(handle)["cylinders"])
    with open(os.path.join(cell_dir, "points.csv"), newline="") as handle:
        points = [row["point"] for row in csv.DictReader(handle)]
    return points, cylinders


def read_table(path, points, cylinders):
    """The table at `path` as {(point, cylinder): {quantity: value}}, or NotTheTable.

    Held to the task statement and no further. Stated there: the header, a row for every point and cylinder
    and for nothing else, values that are decimal numbers. Not stated, so not judged: the order of the rows,
    LF or CRLF, a final line end, empty lines, quoting of fields, blanks round a field.
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
    wanted = {(p, c) for p in points for c in range(1, cylinders + 1)}
    table = {}
    for number, fields in enumerate(csv.reader(lines[1:]), start=2):
        if len(fields) != len(HEADER):
            raise NotTheTable("line %d has %d fields" % (number, len(fields)))
        fields = [f.strip() for f in fields]
        if not WHOLE.fullmatch(fields[1]):
            raise NotTheTable("line %d: cylinder %r is not a whole number" % (number, fields[1]))
        key = (fields[0], int(fields[1]))
        if key not in wanted:
            raise NotTheTable("line %d: point %r, cylinder %s is not in the package" % (number, fields[0], fields[1]))
        if key in table:
            raise NotTheTable("line %d: point %r, cylinder %s is given twice" % (number, fields[0], fields[1]))
        values = {}
        for name, field in zip(HEADER[2:], fields[2:]):
            if not NUMBER.fullmatch(field):
                raise NotTheTable("line %d: %s is %r, not a decimal number" % (number, name, field))
            value = float(field)
            if not math.isfinite(value):
                raise NotTheTable("line %d: %s is not finite" % (number, name))
            values[name] = value
        table[key] = values
    missing = wanted - set(table)
    if missing:
        point, cylinder = sorted(missing)[0]
        raise NotTheTable("%d rows are missing, the first being point %s, cylinder %d" % (len(missing), point, cylinder))
    return table


def sealed_results(path):
    with open(path, newline="") as handle:
        return {(row["point"], int(row["cylinder"])): {name: float(row[name]) for name in HEADER[2:]}
                for row in csv.DictReader(handle)}


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


def run_once(program, cell_dir, limit, as_nobody):
    """One run on one package. Returns (ending, seconds, scratch directory, path of the table).
    ending is "in time" with the exit status appended, or "over the limit"."""
    scratch = tempfile.mkdtemp(prefix="indicating-")
    run_dir, session = os.path.join(scratch, "run"), os.path.join(scratch, "session")
    os.mkdir(run_dir)
    shutil.copytree(cell_dir, session)
    fd = os.open(program, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as given, open(os.path.join(run_dir, "indicate.py"), "wb") as copy:
        if not stat.S_ISREG(os.fstat(given.fileno()).st_mode):
            raise OSError("indicate.py is not a regular file")
        shutil.copyfileobj(given, copy)
    for folder, _, files in os.walk(session):
        os.chmod(folder, 0o755)
        for name in files:
            os.chmod(os.path.join(folder, name), 0o444)
    os.chmod(scratch, 0o755)
    os.chmod(os.path.join(run_dir, "indicate.py"), 0o644)
    out_dir = os.path.join(scratch, "out")
    os.mkdir(out_dir)
    command = [sys.executable, "indicate.py", session, os.path.join(out_dir, "results.csv")]
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
    try:
        status = started.wait(timeout=limit)
        ending = "in time, exit status %d" % status
    except subprocess.TimeoutExpired:
        ending = "over the limit"
    took = time.monotonic() - began
    end_session(started.pid, as_nobody)
    started.wait()
    return ending, took, scratch, os.path.join(out_dir, "results.csv")


def assess(program, cells_dir=None, results_dir=None, limit=RUN_LIMIT_S, as_nobody=None):
    """Runs the program on every cell. Returns {"accepted": bool, "stopped": str, "cells": {name: finding}}."""
    cells_dir = cells_dir or os.path.join(BASE, "cells")
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
        ending, took, scratch, table_path = run_once(program, cell_dir, limit, as_nobody)
        finding = {"seconds": round(took, 2), "ending": ending}
        report["cells"][name] = finding
        try:
            if ending == "over the limit":
                finding["finding"] = "still running after %d s" % limit
                report["stopped"] = "the run on %s was still going after %d s; the cells after it were not run" % (name, limit)
                return report
            if ending != "in time, exit status 0":
                finding["finding"] = ending
                sound = False
                continue
            points, cylinders = session_of(cell_dir)
            try:
                table = read_table(table_path, points, cylinders)
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
        line = "%-8s %5.2f s  %s" % (name, finding["seconds"], finding["finding"])
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
