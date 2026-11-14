"""Tries a delivered ropes.py on the six works under works/ and says whether it is accepted.

    python3 rope_bench.py /app/output/ropes.py        prints the account; exit status 0 only when accepted

Only the program file is taken from its author. Every sheet judged here is written by a run this module starts,
on a works the author has not had, and is held against the sealed damages in sealed/results/.

One trial, of one works
  1. staging: a new directory with three parts, all with their modes set outright, because test.sh works under
     umask 077 and the program is another user:
       bench/    a copy of ropes.py and nothing else; the program's working directory;
       works/    a copy of the package, every file read-only;
       sheet/    empty; OUT_CSV is sheet/damage.csv.
  2. the run: `python3 ropes.py WORKS_DIR OUT_CSV`, as the user nobody whenever this module is root, in a
     session of its own, with OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1, no standard input, its output
     discarded. No CPU affinity is set.
  3. the limit, LIMIT_S seconds on 1 CPU, is held twice: the run is over it when LIMIT_S seconds have gone by
     since it was started, and also when the CPU time, user plus system, of the program and of every process
     it has started reaches LIMIT_S. A single process on one CPU meets both together; a program that spreads
     its work over several processes or CPUs meets the second first.
  4. a run that is over the limit ends everything: the run's processes are killed, its sheet is not opened,
     the works after it are not tried, and the program is not accepted.
  5. a run that ends inside the limit must have exit status 0. Its sheet is read by `read_sheet`, which holds
     it to what the task statement says of OUT_CSV, and every row is held to the accuracy the statement gives:
     within SHARE of the greatest sealed damage of the row's rope.

The program is accepted when every trial ends inside the limit with status 0, a sheet that reads, and no row
out. No share of rows, ropes or works stands in for the rest.
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
HERE = os.path.dirname(os.path.abspath(__file__))

LIMIT_S = 4                     # seconds, of the clock and of CPU; the task statement's "within 4 seconds on 1 CPU"
SHARE = 0.08                    # a row is right within this share of the greatest damage of its rope
SHEET_HEADER = "row,damage"
SHEET_CAP = 1024 * 1024         # bytes; the statement's 1 MiB. The largest sheet of the six is about 9 kB
UNPRIVILEGED = 65534            # nobody
DECIMAL = re.compile(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?\Z")
TICK = os.sysconf("SC_CLK_TCK")


class Unreadable(Exception):
    """OUT_CSV is not the sheet the task statement describes."""


# ----------------------------------------------------------------------------------------------- the sheet

def sealed_sheet(path):
    """{row: damage} of a sealed result."""
    with open(path, newline="") as handle:
        return {line["row"]: float(line["damage"]) for line in csv.DictReader(handle)}


def read_sheet(path, rows):
    """{row: damage} from the file at path, for exactly the rows given, or Unreadable.

    What the statement says, and so what is held: an ordinary file, not a link; no more than SHEET_CAP bytes;
    the header `row,damage`; one row for every station of every crane; each damage a decimal number.
    What it does not say, and so what is left alone: the order of the rows, the line ends, a last line end,
    empty lines, quotes round a field, blanks round a field, how many digits.
    """
    try:
        handle = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as trouble:
        raise Unreadable("no sheet at OUT_CSV (%s)" % (trouble.strerror or trouble))
    try:
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            raise Unreadable("OUT_CSV is not an ordinary file")
        if os.fstat(handle).st_size > SHEET_CAP:
            raise Unreadable("OUT_CSV is larger than %d bytes" % SHEET_CAP)
        blob = b""
        while len(blob) <= SHEET_CAP:
            piece = os.read(handle, 65536)
            if not piece:
                break
            blob += piece
    finally:
        os.close(handle)
    if len(blob) > SHEET_CAP:
        raise Unreadable("OUT_CSV is larger than %d bytes" % SHEET_CAP)
    try:
        text = blob.decode("ascii")
    except UnicodeDecodeError:
        raise Unreadable("OUT_CSV is not plain text")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise Unreadable("OUT_CSV is empty")
    if lines[0] != SHEET_HEADER:
        raise Unreadable("the first line is not %s" % SHEET_HEADER)
    found = {}
    for at, fields in enumerate(csv.reader(lines[1:]), start=2):
        if len(fields) != 2:
            raise Unreadable("line %d has %d fields, not 2" % (at, len(fields)))
        name, value = fields[0].strip(), fields[1].strip()
        if name not in rows:
            raise Unreadable("line %d: %r is not a station of this works" % (at, name))
        if name in found:
            raise Unreadable("line %d: %s is given a second time" % (at, name))
        if not DECIMAL.match(value):
            raise Unreadable("line %d: %r is not a decimal number" % (at, value))
        number = float(value)
        if not math.isfinite(number):
            raise Unreadable("line %d: the damage is not finite" % at)
        found[name] = number
    if len(found) != len(rows):
        absent = sorted(set(rows) - set(found))
        raise Unreadable("%d stations have no row, %s the first" % (len(absent), absent[0]))
    return found


def rope_of(row):
    return row.rsplit("-", 1)[0]


def hold(sheet, sealed):
    """(rows out, widest departure in bands, {rope: (rows out, rows, widest)})."""
    greatest = {}
    for row, damage in sealed.items():
        greatest[rope_of(row)] = max(greatest.get(rope_of(row), 0.0), damage)
    by_rope, out, widest = {}, 0, 0.0
    for row, damage in sealed.items():
        rope = rope_of(row)
        depart = abs(sheet[row] - damage) / (SHARE * greatest[rope])
        miss = not depart <= 1.0
        was = by_rope.get(rope, (0, 0, 0.0))
        by_rope[rope] = (was[0] + miss, was[1] + 1, max(was[2], depart))
        out += miss
        widest = max(widest, depart)
    return out, widest, by_rope


# ------------------------------------------------------------------------------------------------- the run

def staged(program, package):
    """The three parts of a trial's directory: (root, bench, works, OUT_CSV)."""
    root = tempfile.mkdtemp(prefix="trial-")
    bench, works, sheet = (os.path.join(root, part) for part in ("bench", "works", "sheet"))
    for folder in (bench, works, sheet):
        os.mkdir(folder)
    source = os.open(program, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(source, "rb") as given:
        if not stat.S_ISREG(os.fstat(given.fileno()).st_mode):
            raise OSError("the program is not an ordinary file")
        with open(os.path.join(bench, "ropes.py"), "wb") as copy:
            shutil.copyfileobj(given, copy)
    for name in sorted(os.listdir(package)):
        if os.path.isfile(os.path.join(package, name)):
            shutil.copyfile(os.path.join(package, name), os.path.join(works, name))
            os.chmod(os.path.join(works, name), 0o444)
    os.chmod(os.path.join(bench, "ropes.py"), 0o644)
    os.chmod(root, 0o755)
    os.chmod(works, 0o555)
    os.chmod(bench, 0o755)
    os.chmod(sheet, 0o755)
    return root, bench, works, os.path.join(sheet, "damage.csv")


def processes(leader, lowered):
    """pid -> CPU seconds so far, for the processes of a run: every process of nobody when the run is nobody's,
    else every process of the run's session."""
    seen = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            if lowered and os.stat("/proc/" + entry).st_uid != UNPRIVILEGED:
                continue
            with open("/proc/%s/stat" % entry) as handle:
                tail = handle.read().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        # after the name: state, ppid, pgrp, session, ... utime and stime are the 12th and 13th of these
        if not lowered and int(tail[3]) != leader:
            continue
        if tail[0] == "Z":
            continue
        seen[int(entry)] = (int(tail[11]) + int(tail[12])) / TICK
    return seen


def sweep(leader, lowered):
    """Kills whatever a run still has going."""
    for _ in range(50):
        alive = processes(leader, lowered)
        alive.pop(os.getpid(), None)
        try:
            os.killpg(leader, signal.SIGKILL)
        except OSError:
            pass
        for pid in alive:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        if not alive:
            return
        time.sleep(0.04)


def trial(program, package, limit, lowered):
    """One run. (ending, seconds, CPU seconds, staging root, OUT_CSV); ending is "over" or the exit status."""
    root, bench, works, out_csv = staged(program, package)
    command = [sys.executable, "ropes.py", works, out_csv]
    if lowered:
        for folder in (bench, os.path.dirname(out_csv)):
            os.chown(folder, UNPRIVILEGED, UNPRIVILEGED)
        command = ["setpriv", "--reuid", str(UNPRIVILEGED), "--regid", str(UNPRIVILEGED), "--clear-groups"] + command
    surroundings = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": bench,
                    "TMPDIR": os.path.dirname(out_csv), "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
                    "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    started = time.monotonic()
    child = subprocess.Popen(command, cwd=bench, env=surroundings, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    most = {}                       # pid -> the most CPU seen for it
    ending, usage = None, None
    while ending is None:
        # reaped with wait4 and not by Popen, for the kernel's own count of the CPU time when it ends
        pid, status, used = os.wait4(child.pid, os.WNOHANG)
        if pid:
            ending, usage = os.waitstatus_to_exitcode(status), used
            break
        for one, cpu in processes(child.pid, lowered).items():
            most[one] = max(most.get(one, 0.0), cpu)
        if time.monotonic() - started >= limit or sum(most.values()) >= limit:
            ending = "over"
            break
        time.sleep(0.02)
    seconds = time.monotonic() - started
    for one, cpu in processes(child.pid, lowered).items():
        most[one] = max(most.get(one, 0.0), cpu)
    sweep(child.pid, lowered)
    if usage is None:
        _, _, usage = os.wait4(child.pid, 0)
    child.returncode = 0            # reaped above; tells Popen there is nothing left to wait for
    cpu = max(sum(most.values()), usage.ru_utime + usage.ru_stime)
    if ending != "over" and cpu >= limit:
        ending = "over"
    return ending, seconds, cpu, root, out_csv


# ------------------------------------------------------------------------------------------- the whole lot

def judge(program, works_dir=None, sealed_dir=None, limit=LIMIT_S, lowered=None):
    """{"accepted": bool, "halted": str, "trials": [one dict a works tried]}"""
    works_dir = works_dir or os.path.join(HERE, "works")
    sealed_dir = sealed_dir or os.path.join(HERE, "sealed", "results")
    if lowered is None:
        lowered = os.geteuid() == 0 and shutil.which("setpriv") is not None
    verdict = {"accepted": False, "halted": "", "trials": []}
    names = sorted(name for name in os.listdir(works_dir) if os.path.isdir(os.path.join(works_dir, name)))
    if not names:
        verdict["halted"] = "no works to try the program on"
        return verdict
    if not os.path.isfile(program) or os.path.islink(program):
        verdict["halted"] = "no program file at %s" % program
        return verdict
    clean = True
    for name in names:
        ending, seconds, cpu, root, out_csv = trial(program, os.path.join(works_dir, name), limit, lowered)
        note = {"works": name, "seconds": round(seconds, 2), "cpu_seconds": round(cpu, 2)}
        verdict["trials"].append(note)
        try:
            if ending == "over":
                note["outcome"] = "over the limit of %d s" % limit
                verdict["halted"] = "the run on %s reached %d s, of the clock or of CPU; nothing after it was tried" % (name, limit)
                return verdict
            if ending != 0:
                note["outcome"] = "ended with status %s" % ending
                clean = False
                continue
            sealed = sealed_sheet(os.path.join(sealed_dir, name + ".csv"))
            try:
                sheet = read_sheet(out_csv, sealed)
            except Unreadable as why:
                note["outcome"] = str(why)
                clean = False
                continue
            out, widest, by_rope = hold(sheet, sealed)
            note.update(rows=len(sealed), rows_out=out, widest=round(widest, 3),
                        ropes={rope: {"rows_out": a, "rows": b, "widest": round(c, 3)} for rope, (a, b, c) in sorted(by_rope.items())})
            note["outcome"] = "every row right" if out == 0 else "%d of %d rows out" % (out, len(sealed))
            clean = clean and out == 0
        finally:
            shutil.rmtree(root, ignore_errors=True)
    verdict["accepted"] = clean
    return verdict


def account(verdict):
    """The verdict in lines a person reads."""
    lines = []
    for note in verdict["trials"]:
        line = "%-12s %5.1f s, %5.1f s of CPU: %s" % (note["works"], note["seconds"], note["cpu_seconds"], note["outcome"])
        if "ropes" in note:
            line += "; widest departure %.2f of the band" % note["widest"]
            missed = ["%s %d/%d" % (rope, facts["rows_out"], facts["rows"]) for rope, facts in note["ropes"].items() if facts["rows_out"]]
            if missed:
                line += " (" + ", ".join(missed) + ")"
        lines.append(line)
    if verdict["halted"]:
        lines.append(verdict["halted"])
    lines.append("ACCEPTED" if verdict["accepted"] else "NOT ACCEPTED")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 rope_bench.py PROGRAM")
    result = judge(sys.argv[1])
    print(account(result))
    sys.exit(0 if result["accepted"] else 1)
