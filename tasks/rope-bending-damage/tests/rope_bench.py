"""The rope bench: puts a delivered ropes.py to work on six works it has never seen, and decides on it.

    python3 rope_bench.py PROGRAM               works the program on tests/works; status 0 if it is accepted
    python3 rope_bench.py --one-passed REPORT   status 0 if pytest's ctrf REPORT counts one test, passed

What the bench takes from the program's author is the program file and nothing else. For each works it lays
out a fresh trial box, starts the program in it, watches the clock and the CPU, and, if the run ends in time
and cleanly, reads the damage sheet the run wrote and lays it against the sealed damages of sealed/results.

The trial box (modes set one by one with os.chmod, since test.sh runs under umask 077 and the program runs as
another user):
    bench/   ropes.py, copied from the delivered file, alone; the run's working directory
    works/   the package, every file read-only
    sheet/   empty at the start; OUT_CSV is sheet/damage.csv

The run is `python3 ropes.py WORKS_DIR OUT_CSV`, in a session of its own, as the user nobody when the bench is
root, with OMP_NUM_THREADS=1 and OPENBLAS_NUM_THREADS=1, no standard input, its output thrown away, and no CPU
affinity. It has LIMIT_S seconds, and is out of time as soon as either the clock since its start or the CPU
time (user and system) of every process it started reaches LIMIT_S. A run out of time is killed with all it
started, its sheet is never opened, no later works is tried, and the program is not accepted.

The program is accepted only if every works is run in time with exit status 0, and every row of every sheet
is within SHARE of the greatest sealed damage of its rope.
"""
import csv
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

LIMIT_S = 4                     # the statement's "within 4 seconds on 1 CPU", on the clock and on CPU
SHARE = 0.08                    # the statement's 8 per cent of the greatest damage of the rope
SHEET_HEADER = "row,damage"
SHEET_CAP = 1 << 20             # 1 MiB; the largest true sheet of the six is about 25 kB
NOBODY = 65534
NUMBER = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
HZ = os.sysconf("SC_CLK_TCK")
ONE_PASSED = (("tests", 1), ("passed", 1), ("failed", 0), ("skipped", 0), ("pending", 0), ("other", 0))


class Unreadable(Exception):
    """The file at OUT_CSV is not the damage sheet the statement asks for."""


def rope_of(row):
    """FB-1-017 -> FB-1"""
    return row.rsplit("-", 1)[0]


def sealed_sheet(path):
    with open(path, newline="") as handle:
        return {entry["row"]: float(entry["damage"]) for entry in csv.DictReader(handle)}


def read_sheet(path, rows):
    """The damages a run wrote, {row: damage}, for exactly the given rows; Unreadable otherwise.

    Held to what the statement says: an ordinary file, not a link, of at most SHEET_CAP bytes, beginning with the
    header row,damage, then one row of two fields for each station of the works and for nothing else, every
    damage a finite decimal number. Not held to anything it leaves open: order, line ends, blank lines, quotes,
    blanks round a field, digits."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as why:
        raise Unreadable("no sheet at OUT_CSV (%s)" % (why.strerror or why))
    facts = os.fstat(fd)
    if not stat.S_ISREG(facts.st_mode):
        os.close(fd)
        raise Unreadable("OUT_CSV is not an ordinary file")
    with os.fdopen(fd, "rb") as handle:
        blob = handle.read(SHEET_CAP + 1)
    if len(blob) > SHEET_CAP or facts.st_size > SHEET_CAP:
        raise Unreadable("OUT_CSV is larger than %d bytes" % SHEET_CAP)
    if any(byte > 127 for byte in blob):
        raise Unreadable("OUT_CSV is not plain text")
    lines = [line for line in blob.decode("ascii").splitlines() if line.strip()]
    if not lines:
        raise Unreadable("OUT_CSV is empty")
    if lines[0] != SHEET_HEADER:
        raise Unreadable("the first line is not %s" % SHEET_HEADER)
    damages = {}
    for number, fields in zip(range(2, len(lines) + 1), csv.reader(lines[1:])):
        if len(fields) != 2:
            raise Unreadable("line %d has %d fields, not 2" % (number, len(fields)))
        row, text = (field.strip() for field in fields)
        if row not in rows:
            raise Unreadable("line %d: %r is not a station of this works" % (number, row))
        if row in damages:
            raise Unreadable("line %d: %s is given a second time" % (number, row))
        if NUMBER.fullmatch(text) is None:
            raise Unreadable("line %d: %r is not a decimal number" % (number, text))
        if not math.isfinite(float(text)):
            raise Unreadable("line %d: the damage is not finite" % number)
        damages[row] = float(text)
    missing = sorted(set(rows) - set(damages))
    if missing:
        raise Unreadable("%d stations have no row, %s the first" % (len(missing), missing[0]))
    return damages


def hold(sheet, sealed):
    """Lays a sheet against the sealed damages: (rows out, widest departure in bands, per rope facts)."""
    greatest = {}
    for row, value in sealed.items():
        greatest[rope_of(row)] = max(greatest.get(rope_of(row), 0.0), value)
    ropes = {rope: [0, 0, 0.0] for rope in greatest}
    for row, value in sealed.items():
        facts = ropes[rope_of(row)]
        bands = abs(sheet[row] - value) / (SHARE * greatest[rope_of(row)])
        facts[0] += not bands <= 1.0
        facts[1] += 1
        facts[2] = max(facts[2], bands)
    out = sum(facts[0] for facts in ropes.values())
    widest = max(facts[2] for facts in ropes.values())
    return out, widest, {rope: tuple(facts) for rope, facts in ropes.items()}


class TrialBox:
    """The directory one run of the program lives in, and the run itself."""

    def __init__(self, program, package):
        self.root = tempfile.mkdtemp(prefix="trial-")
        self.bench, self.works, self.sheets = (os.path.join(self.root, name) for name in ("bench", "works", "sheet"))
        self.out_csv = os.path.join(self.sheets, "damage.csv")
        for folder in (self.bench, self.works, self.sheets):
            os.mkdir(folder)
        fd = os.open(program, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise OSError("the program is not an ordinary file")
            with open(os.path.join(self.bench, "ropes.py"), "wb") as copy:
                shutil.copyfileobj(source, copy)
        for name in sorted(os.listdir(package)):
            if os.path.isfile(os.path.join(package, name)):
                shutil.copyfile(os.path.join(package, name), os.path.join(self.works, name))
                os.chmod(os.path.join(self.works, name), 0o444)
        os.chmod(os.path.join(self.bench, "ropes.py"), 0o644)
        for folder, mode in ((self.root, 0o755), (self.works, 0o555), (self.bench, 0o755), (self.sheets, 0o755)):
            os.chmod(folder, mode)

    def start(self, lowered):
        command = [sys.executable, "ropes.py", self.works, self.out_csv]
        if lowered:
            os.chown(self.bench, NOBODY, NOBODY)
            os.chown(self.sheets, NOBODY, NOBODY)
            command = ["setpriv", "--reuid", str(NOBODY), "--regid", str(NOBODY), "--clear-groups"] + command
        surroundings = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": self.bench,
                        "TMPDIR": self.sheets, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
                        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        return subprocess.Popen(command, cwd=self.bench, env=surroundings, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    def clear(self):
        shutil.rmtree(self.root, ignore_errors=True)


def processes(leader, lowered):
    """{pid: CPU seconds} for the live processes of a run: all of nobody's when the run is nobody's, otherwise
    those of the run's session."""
    found = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            if lowered and os.stat("/proc/" + entry).st_uid != NOBODY:
                continue
            with open("/proc/%s/stat" % entry) as handle:
                after_name = handle.read().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        state, session, user, system = after_name[0], int(after_name[3]), int(after_name[11]), int(after_name[12])
        if state == "Z" or (not lowered and session != leader):
            continue
        found[int(entry)] = (user + system) / HZ
    return found


def stop_all(leader, lowered):
    """Kills the run's session and anything of the run's that has left it."""
    for _ in range(50):
        left = processes(leader, lowered)
        left.pop(os.getpid(), None)
        for victim in [-leader] + list(left):
            try:
                os.kill(victim, signal.SIGKILL)
            except OSError:
                pass
        if not left:
            return
        time.sleep(0.04)


def watch(child, limit, lowered):
    """Waits for a run, or ends it at the limit. (ending, seconds, CPU seconds); ending is "over" or the exit
    status. The CPU seconds are the larger of what /proc showed while it ran and the kernel's count at its end."""
    started = time.monotonic()
    most, usage, ending = {}, None, None
    while ending is None:
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
    stop_all(child.pid, lowered)
    if usage is None:
        usage = os.wait4(child.pid, 0)[2]
    child.returncode = 0                # already reaped by wait4
    cpu = max(sum(most.values()), usage.ru_utime + usage.ru_stime)
    if cpu >= limit:
        ending = "over"
    return ending, seconds, cpu


def judge(program, works_dir=None, sealed_dir=None, limit=LIMIT_S, lowered=None):
    """{"accepted": bool, "halted": reason the judging stopped early or "", "trials": one note a works}"""
    works_dir = works_dir or os.path.join(TESTS, "works")
    sealed_dir = sealed_dir or os.path.join(TESTS, "sealed", "results")
    if lowered is None:
        lowered = os.geteuid() == 0 and shutil.which("setpriv") is not None
    verdict = {"accepted": False, "halted": "", "trials": []}
    every = sorted(name for name in os.listdir(works_dir) if os.path.isdir(os.path.join(works_dir, name)))
    if not every:
        verdict["halted"] = "no works to try the program on"
        return verdict
    if os.path.islink(program) or not os.path.isfile(program):
        verdict["halted"] = "no program file at %s" % program
        return verdict
    clean = True
    for name in every:
        box = TrialBox(program, os.path.join(works_dir, name))
        try:
            ending, seconds, cpu = watch(box.start(lowered), limit, lowered)
            note = {"works": name, "seconds": round(seconds, 2), "cpu_seconds": round(cpu, 2)}
            verdict["trials"].append(note)
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
                sheet = read_sheet(box.out_csv, sealed)
            except Unreadable as why:
                note["outcome"] = str(why)
                clean = False
                continue
            out, widest, ropes = hold(sheet, sealed)
            note.update(rows=len(sealed), rows_out=out, widest=round(widest, 3),
                        ropes={rope: {"rows_out": a, "rows": b, "widest": round(c, 3)} for rope, (a, b, c) in sorted(ropes.items())})
            note["outcome"] = "every row right" if not out else "%d of %d rows out" % (out, len(sealed))
            clean = clean and not out
        finally:
            box.clear()
    verdict["accepted"] = clean
    return verdict


def account(verdict):
    """The verdict as lines for a person."""
    told = []
    for note in verdict["trials"]:
        line = "%-12s %5.1f s, %5.1f s of CPU: %s" % (note["works"], note["seconds"], note["cpu_seconds"], note["outcome"])
        if "ropes" in note:
            line += "; widest departure %.2f of the band" % note["widest"]
            missed = ["%s %d/%d" % (rope, f["rows_out"], f["rows"]) for rope, f in note["ropes"].items() if f["rows_out"]]
            line += " (%s)" % ", ".join(missed) if missed else ""
        told.append(line)
    if verdict["halted"]:
        told.append(verdict["halted"])
    told.append("ACCEPTED" if verdict["accepted"] else "NOT ACCEPTED")
    return "\n".join(told)


def delivered_verdict():
    """pytest's question, answered: (accepted, account) for the delivered program, with the verdict kept for a
    person reading the logs at ROPES_NOTES, which nothing reads back. ROPES_PROGRAM and ROPES_NOTES move the two
    paths for the studies in authoring/evidence; the verifier sets neither."""
    verdict = judge(os.environ.get("ROPES_PROGRAM", "/app/output/ropes.py"))
    try:
        with open(os.environ.get("ROPES_NOTES", "/logs/verifier/trials.json"), "w") as notes:
            notes.write(json.dumps(verdict, indent=1, sort_keys=True))
    except OSError:
        pass
    return verdict["accepted"], account(verdict)


def one_passed(report):
    """True only for a ctrf report whose summary counts exactly one test, and that one passed."""
    try:
        with open(report, encoding="utf-8") as handle:
            summary = json.load(handle)["results"]["summary"]
        return all(int(summary.get(kind, 0)) == count for kind, count in ONE_PASSED)
    except Exception:
        return False


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--one-passed":
        sys.exit(0 if one_passed(sys.argv[2]) else 3)
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    result = judge(sys.argv[1])
    print(account(result))
    sys.exit(0 if result["accepted"] else 1)
