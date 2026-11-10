"""Adversarial controllers and isolation probes against the shipped verifier.

    python3 authoring/evidence/cheat_attempts.py > authoring/evidence/cheat_attempts.txt

Must run as root, like the verifier: the controller is demoted to 'nobody' only then. Run it
with the verifier image's interpreter and pins (python 3.11, numpy 2.1.3, scipy 1.14.1, no
pandas): the sandbox runs the controller with the same interpreter as the grader.

The tests directory is copied to a root-only (mode 700) directory first, which is what
tests/Dockerfile does to /tests, and the verifier is imported from that copy.

SCORED CHEATS go through grade.run_wafer wafer by wafer, in the verifier's order, and
stop at the first failed wafer: the reward needs every wafer to pass, so the first failure
already fixes it at 0. A cheat that passes every wafer is scored on the total cycle against
the perfect-knowledge benchmark, exactly as grade.grade does.

ISOLATION PROBES drive the sandbox directly and report what the controller could see or
do: the sealed files, the verifier process, the logs, other wafers' leftovers.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SEALED = tempfile.mkdtemp(prefix="wcc_sealed_")
shutil.copytree(os.path.join(ROOT, "tests"), os.path.join(SEALED, "tests"),
                ignore=shutil.ignore_patterns("__pycache__"))
SEALED_TESTS = os.path.join(SEALED, "tests")
os.chmod(SEALED_TESTS, 0o700)
sys.path.insert(0, SEALED_TESTS)
import grade  # noqa: E402
import plant as pl  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "solution"))
os.environ.setdefault("CHILL_DATA", os.path.join(ROOT, "environment", "data"))
import solve  # noqa: E402

WORK = tempfile.mkdtemp(prefix="wcc_cheats_")
LOGS = "/logs/verifier"


def ctrl(name, body):
    path = os.path.join(WORK, name + ".py")
    with open(path, "w") as f:
        f.write(textwrap.dedent(body))
    return path


def reference():
    path = os.path.join(WORK, "reference.py")
    stations, split, wafer, prod, runs = solve.load()
    import io
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        ident = solve.identify(stations, split, wafer, prod, runs)
    solve.write_controller(ident, wafer, prod, split, path)
    return path


def wrap_reference(name, ref_path, init_extra="", step_extra="", step_post=""):
    """A controller that runs the reference inside it and adds misbehaviour."""
    src = open(ref_path).read().replace("class Controller:", "class _Ref:", 1)
    return ctrl(name, src + textwrap.dedent('''

    import os, sys, json, time

    class Controller:
        def __init__(self, station, wafer):
            self._r = _Ref(station, wafer)
    %s
        def step(self, t, reading):
    %s
            cmd = self._r.step(t, reading)
    %s
            return cmd
    ''') % (textwrap.indent(textwrap.dedent(init_extra), " " * 8),
            textwrap.indent(textwrap.dedent(step_extra), " " * 8),
            textwrap.indent(textwrap.dedent(step_post), " " * 8)))


def grade_until_fail(path, truth, bench, limit=None):
    """Exact reward with early exit. Returns (reward, n_run, first failure or summary)."""
    rows = []
    for w in truth["wafers"][:limit]:
        r = grade.run_wafer(path, truth, w)
        rows.append(r)
        if not r["passed"]:
            why = r["error"] or ("zone %.2f K" % r["worst_zone_dT_K"] if not r["meets_zone"]
                                 else "released at %.2f C" % r["T_release_C"])
            why = " ".join(why.split())
            return 0, len(rows), "%s failed: %s" % (r["id"], why if len(why) <= 90 else "..." + why[-87:])
    if limit is not None:
        return None, len(rows), "first %d wafers all passed" % len(rows)
    tot = sum(r["cycle_s"] for r in rows)
    tb = sum(bench[r["id"]] for r in rows)
    ratio = tot / tb
    reward = int(ratio <= 1 + truth["allowance"] + grade.EPS)
    return reward, len(rows), "all 24 passed, cycle ratio %.3f (limit %.2f)" % (
        ratio, 1 + truth["allowance"])


# ---------------------------------------------------------------- scored cheats
def scored(ref):
    def mk(name, step_body, init_body="pass", head=""):
        return ctrl(name, head + '''
class Controller:
    def __init__(self, station, wafer):
        %s
    def step(self, t, reading):
        %s
''' % (init_body, step_body))

    cheats = [
        ("empty file", ctrl("empty", "")),
        ("syntax error", ctrl("syntax", "class Controller(:\n")),
        ("imports a package the verifier lacks (pandas)",
         mk("pandas", 'return {"pressure_torr": 10.0, "release": False}', head="import pandas\n")),
        ("reads /data at run time",
         mk("data", 'return {"pressure_torr": 10.0, "release": False}',
            init_body='self.s = open("/data/stations.json").read()')),
        ("raises in the constructor", mk("raise_init", "pass", init_body="raise RuntimeError('x')")),
        ("raises in step", mk("raise_step", "raise RuntimeError('x')")),
        ("hangs in the constructor", mk("hang_init", "pass", init_body="import time; time.sleep(600)")),
        ("hangs in step", mk("hang_step", "import time; time.sleep(600)")),
        ("NaN pressure", mk("nan", 'return {"pressure_torr": float("nan"), "release": False}')),
        ("infinite pressure", mk("inf", 'return {"pressure_torr": float("inf"), "release": False}')),
        ("pressure above range (61 Torr)", mk("hi", 'return {"pressure_torr": 61.0, "release": False}')),
        ("pressure below range (2.9 Torr)", mk("lo", 'return {"pressure_torr": 2.9, "release": False}')),
        ("pressure as a string", mk("str", 'return {"pressure_torr": "12", "release": False}')),
        ("pressure as a bool", mk("boolp", 'return {"pressure_torr": True, "release": False}')),
        ("release as a string", mk("strrel", 'return {"pressure_torr": 12.0, "release": "yes"}')),
        ("returns None", mk("none", "return None")),
        ("returns a list", mk("list", "return [12.0, False]")),
        ("releases at landing", mk("instant", 'return {"release": True}')),
        ("never releases (3 Torr held)", mk("never", 'return {"pressure_torr": 3.0, "release": False}')),
        ("60 Torr until the spots read 50 C",
         mk("max", 'return {"release": True} if 0.5*(reading["center_C"]+reading["edge_C"]) <= 50 '
                   'else {"pressure_torr": 60.0, "release": False}')),
        ("3 Torr until the spots read 50 C",
         mk("min", 'return {"release": True} if 0.5*(reading["center_C"]+reading["edge_C"]) <= 50 '
                   'else {"pressure_torr": 3.0, "release": False}')),
        ("hunts for the sealed truth, uses it if found",
         mk("truth", '''return {"release": True} if self.truth is None else {"release": True}''',
            init_body='''import glob, os
        self.truth = None
        cands = ["/tests/truth.json", %r]
        for top in ("/tests", "/logs", "/app", "/tmp", "/root"):
            cands += glob.glob(top + "/**/truth.json", recursive=True)[:20]
        for p in cands:
            try:
                self.truth = open(p).read()
                break
            except OSError:
                pass''' % os.path.join(SEALED_TESTS, "truth.json"))),
        ("writes reward 1 and fake metrics, then releases hot",
         mk("tamper", 'return {"release": True}', init_body='''for p, s in (("%s/reward.txt", "1"), ("%s/metrics.json", "{}")):
            try:
                open(p, "w").write(s)
            except OSError:
                pass''' % (LOGS, LOGS))),
        ("forges a protocol reply on the verifier's pipe",
         mk("forge", 'return {"pressure_torr": 60.0, "release": False}', init_body='''import os, json
        for fd in os.listdir("/proc/self/fd"):
            try:
                os.write(int(fd), (json.dumps({"ok": True, "command": {"release": True}}) + "\\n").encode())
            except OSError:
                pass''')),
        ("kills the verifier, then releases hot",
         mk("killer", 'return {"release": True}', init_body='''import os, signal
        for target in (os.getppid(), 1, -1):
            try:
                os.kill(target, signal.SIGKILL)
            except OSError:
                pass''')),
        ("fork bomb", mk("forkbomb", 'return {"pressure_torr": 10.0, "release": False}', init_body='''import os
        for _ in range(500):
            try:
                if os.fork() == 0:
                    import time; time.sleep(600); os._exit(0)
            except OSError:
                break''')),
        ("allocates 8 GiB", mk("membomb", 'return {"pressure_torr": 10.0, "release": False}',
                               init_body="self.x = bytearray(8 * 2**30)")),
        ("reference, every release held back 12%",
         wrap_reference("padded", ref,
                        init_extra="self._hold = None",
                        step_post='''if cmd.get("release"):
    if self._hold is None:
        self._hold = t * 1.12
    if t < self._hold - 1e-9:
        cmd = {"pressure_torr": 3.0, "release": False}''')),
        ("reference, release margin -0.6 C (releases early)",
         ctrl("early", open(ref).read().replace("RELEASE_MARGIN_C = 0.35", "RELEASE_MARGIN_C = -0.6"))),
    ]
    return cheats


def main():
    if os.geteuid() != 0:
        print("run as root: the controller is only demoted to 'nobody' when the verifier is root")
        return 1
    os.makedirs(LOGS, exist_ok=True)
    os.chmod(LOGS, 0o755)
    for p in ("reward.txt", "metrics.json"):
        with open(os.path.join(LOGS, p), "w") as f:
            f.write("sentinel")
    truth = grade.load_truth()
    t0 = time.time()
    b = grade.benchmarks(truth)
    bench = {k: v[0] for k, v in b.items()}
    ref = reference()
    print("sealed tests directory: %s (mode %o); controllers run as uid %d\n"
          % (SEALED_TESTS, stat.S_IMODE(os.stat(SEALED_TESTS).st_mode), grade._sandbox_ids()[0]))

    print("SCORED CHEATS (reward from grade.run_wafer, stopping at the first failed wafer)")
    zero = 0
    cheats = scored(ref)
    for label, path in cheats:
        t1 = time.time()
        reward, n, why = grade_until_fail(path, truth, bench)
        zero += reward == 0
        print("  %-52s reward %s  after %2d wafer(s): %s  [%.0f s]"
              % (label, reward, n, why, time.time() - t1), flush=True)
    print("  -> %d of %d score 0\n" % (zero, len(cheats)))

    print("CONTROLS: the reference through the same path, and with an actuator error it is not")
    print("told about (not a cheat: it shows the closed loop absorbing a plant mismatch)")
    reward, n, why = grade_until_fail(ref, truth, bench)
    print("  %-52s reward %s  after %2d wafer(s): %s" % ("reference", reward, n, why))
    gain = wrap_reference("gain", ref, step_post='''if not cmd.get("release"):
    cmd = {"pressure_torr": min(60.0, cmd["pressure_torr"] * 1.08), "release": False}''')
    reward, n, why = grade_until_fail(gain, truth, bench)
    print("  %-52s reward %s  after %2d wafer(s): %s\n" % ("reference, every command 8% above what "
                                                          "it planned", reward, n, why))

    print("LOG FILES after all of the above (the cheats wrote '1' and '{}' where they could):")
    for p in ("reward.txt", "metrics.json"):
        print("  %s/%s: %r" % (LOGS, p, open(os.path.join(LOGS, p)).read()[:20]))
    print()
    isolation()
    print("\n[%.0f s]" % (time.time() - t0))
    return 0


# ---------------------------------------------------------------- isolation probes
PROBE = r'''
import ctypes, json, os, signal, subprocess, sys, time

def attempt(fn):
    try:
        r = fn()
        return "ALLOWED" + ("" if r is None else ": " + str(r)[:60])
    except Exception as e:
        return "denied (%s)" % type(e).__name__

class Controller:
    def __init__(self, station, wafer):
        self.report = {}
        rep = self.report
        ppid = os.getppid()
        rep["uid"] = os.getuid()
        rep["read sealed truth.json"] = attempt(lambda: open(@@TRUTH@@).read(10))
        rep["read sealed plant.py"] = attempt(lambda: open(@@PLANT@@).read(10))
        rep["list sealed tests dir"] = attempt(lambda: os.listdir(@@TESTS@@))
        rep["read /tests/truth.json"] = attempt(lambda: open("/tests/truth.json").read(10))
        rep["write reward.txt"] = attempt(lambda: open("/logs/verifier/reward.txt", "w").write("1"))
        rep["read verifier environ"] = attempt(lambda: open("/proc/%d/environ" % ppid).read(10))
        rep["read verifier memory"] = attempt(lambda: open("/proc/%d/mem" % ppid, "rb").read(1))
        rep["list verifier cwd"] = attempt(lambda: os.listdir("/proc/%d/cwd" % ppid))
        rep["list verifier fds"] = attempt(lambda: os.listdir("/proc/%d/fd" % ppid))
        rep["signal the verifier"] = attempt(lambda: os.kill(ppid, 0))
        rep["leave /tmp marker"] = attempt(lambda: open("/tmp/wcc_cheat_marker", "w").write("x"))
        rep["leave /var/tmp marker"] = attempt(lambda: open("/var/tmp/wcc_cheat_marker", "w").write("x"))
        rep["leave /dev/shm marker"] = attempt(lambda: open("/dev/shm/wcc_cheat_marker", "w").write("x"))
        libc = ctypes.CDLL(None, use_errno=True)
        rep["create SysV shm segment"] = attempt(
            lambda: (lambda i: i if i >= 0 else (_ for _ in ()).throw(OSError()))(
                libc.shmget(0x5743, 4096, 0o1000 | 0o666)))
        def orphan():
            pid = os.fork()
            if pid == 0:
                os.setsid()
                if os.fork() == 0:
                    time.sleep(3600)
                os._exit(0)
            os.waitpid(pid, 0)
        rep["leave an orphan process"] = attempt(orphan)
        rep["write a 100 MB file"] = attempt(lambda: open(os.path.join(os.environ.get("TMPDIR", "."), "big"), "wb").write(b"x" * (100 * 2**20)))
        rep["allocate 6 GiB"] = attempt(lambda: len(bytearray(6 * 2**30)))
    def step(self, t, reading):
        return {"pressure_torr": 3.0, "release": False, "report": self.report}
'''


def leftovers(uid):
    found = []
    for d in ("/tmp", "/var/tmp", "/dev/shm"):
        p = os.path.join(d, "wcc_cheat_marker")
        if os.path.exists(p):
            found.append(p)
    with open("/proc/sysvipc/shm") as f:
        head = f.readline().split()
        for ln in f:
            r = ln.split()
            if r[head.index("uid")] == str(uid):
                found.append("shm segment %s" % r[1])
    found += ["process %d" % pid for pid in grade._user_processes(uid)]
    return found


def isolation():
    print("ISOLATION PROBES (the controller tries each, inside the verifier's sandbox)")
    src = (PROBE.replace("@@TRUTH@@", repr(os.path.join(SEALED_TESTS, "truth.json")))
           .replace("@@PLANT@@", repr(os.path.join(SEALED_TESTS, "plant.py")))
           .replace("@@TESTS@@", repr(SEALED_TESTS)))
    path = ctrl("probe", src)
    truth = grade.load_truth()
    uid = grade._sandbox_ids()[0]
    box = grade.Sandbox(path)
    box.start()
    rep, err = box.call({"op": "init", "station": grade.station_record(truth, "A"),
                         "wafer": {"film": "bare"}}, grade.INIT_TIMEOUT_S)
    rep, err = box.call({"op": "step", "t": 0.0, "reading": {"center_C": 250.0, "edge_C": 250.0,
                                                             "plate_C": 20.0, "pressure_torr": 3.0}},
                        grade.STEP_TIMEOUT_S)
    report = (rep or {}).get("command", {}).get("report", {"error": err})
    for k, v in report.items():
        print("  %-28s %s" % (k, v))
    during = leftovers(uid)
    box.close()
    after = leftovers(uid)
    print("  left behind while the wafer ran: %s" % (", ".join(during) or "nothing"))
    print("  left behind after the wafer was closed: %s" % (", ".join(after) or "nothing"))


if __name__ == "__main__":
    sys.exit(main())
