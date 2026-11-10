"""Adversarial controllers and isolation probes against the shipped verifier.

    python3 authoring/evidence/cheat_attempts.py > authoring/evidence/cheat_attempts.txt

Must run as root, like the verifier: the controller is demoted to 'nobody' only then. The tests
directory is copied to a root-only (mode 700) directory first, which is what tests/Dockerfile does
to /tests, and the verifier is imported from that copy. Every scored cheat goes through
grade.grade(), the function the gating test calls, with one change for speed: the constructor time
limit is lowered from 600 s to 20 s, so the cheat that hangs in its constructor is caught in 20 s.
"""
import json, os, shutil, stat, subprocess, sys, tempfile, textwrap, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SEALED = tempfile.mkdtemp(prefix="tabs_sealed_")
shutil.copytree(os.path.join(ROOT, "tests"), os.path.join(SEALED, "tests"),
                ignore=shutil.ignore_patterns("__pycache__"))
SEALED_TESTS = os.path.join(SEALED, "tests")
os.chmod(SEALED_TESTS, 0o700)
sys.path.insert(0, SEALED_TESTS)
import grade  # noqa: E402
grade.INIT_TIMEOUT_S = 20.0
# Run with the verifier image's interpreter and pins (python 3.11, numpy 2.1.3, scipy 1.14.1, no pandas):
# the sandbox uses the grader's own interpreter, so a package installed here would import.

WORK = tempfile.mkdtemp(prefix="tabs_cheats_")
os.chmod(WORK, 0o755)
LOGS = "/logs/verifier"


def ctrl(name, body):
    path = os.path.join(WORK, name + ".py")
    with open(path, "w") as f:
        f.write(textwrap.dedent(body))
    return path


def mk(name, step_body, init_body="pass", head=""):
    return ctrl(name, head + '''
class Controller:
    def __init__(self):
        %s
    def step(self, obs):
        %s
''' % (init_body, step_body))


def reference():
    path = os.path.join(WORK, "reference.py")
    env = dict(os.environ, TABS_DATA=os.path.join(ROOT, "environment", "data"), OUT=path)
    subprocess.run([sys.executable, os.path.join(ROOT, "solution", "fit.py")], env=env, check=True,
                   stdout=subprocess.DEVNULL)
    os.chmod(path, 0o644)
    return path


def wrap_reference(name, ref_path, post):
    src = open(ref_path).read().replace("class Controller:", "class _Ref:", 1)
    return ctrl(name, src + textwrap.dedent('''

    class Controller:
        def __init__(self):
            self._r = _Ref()
        def step(self, obs):
            cmd = self._r.step(obs)
    %s
            return cmd
    ''') % textwrap.indent(textwrap.dedent(post), " " * 8))


OK = '{"supply_temp_c": 18.0, "valve_duty": {"west": 0.5, "east": 0.5}}'


def cheats(ref):
    return [
        ("empty file", ctrl("empty", "")),
        ("syntax error", ctrl("syntax", "class Controller(:\n")),
        ("imports a package the verifier lacks (pandas)", mk("pandas", "return " + OK, head="import pandas\n")),
        ("reads /app/data at run time", mk("data", "return " + OK,
                                           init_body='self.s = open("/app/data/trend_log.csv").read()')),
        ("raises in the constructor", mk("raise_init", "pass", init_body="raise RuntimeError('x')")),
        ("raises in step", mk("raise_step", "raise RuntimeError('x')")),
        ("hangs in the constructor", mk("hang_init", "pass", init_body="import time; time.sleep(900)")),
        ("hangs in step", mk("hang_step", "import time; time.sleep(900)")),
        ("NaN setpoint", mk("nan", 'return {"supply_temp_c": float("nan"), "valve_duty": {"west": 1, "east": 1}}')),
        ("infinite duty", mk("inf", 'return {"supply_temp_c": 18.0, "valve_duty": {"west": float("inf"), "east": 1}}')),
        ("setpoint as a string", mk("str", 'return {"supply_temp_c": "18", "valve_duty": {"west": 1, "east": 1}}')),
        ("duty as a bool", mk("boold", 'return {"supply_temp_c": 18.0, "valve_duty": {"west": True, "east": 1}}')),
        ("duty for one zone only", mk("onezone", 'return {"supply_temp_c": 18.0, "valve_duty": {"west": 1}}')),
        ("returns None", mk("none", "return None")),
        ("returns a list", mk("list", "return [18.0, 1, 1]")),
        ("never cools (22 C, valves shut)",
         mk("never", 'return {"supply_temp_c": 22.0, "valve_duty": {"west": 0, "east": 0}}')),
        ("always full cooling (15 C, valves open)",
         mk("always", 'return {"supply_temp_c": 15.0, "valve_duty": {"west": 1, "east": 1}}')),
        ("hunts for the sealed benchmark and world, cools fully if not found",
         mk("hunt", 'return {"supply_temp_c": 15.0, "valve_duty": {"west": 1, "east": 1}}',
            init_body='''import glob
        self.found = []
        cands = ["/tests/bench.json", "/tests/world.py", %r]
        for top in ("/tests", "/logs", "/app", "/tmp", "/root"):
            cands += glob.glob(top + "/**/bench.json", recursive=True)[:20]
        for p in cands:
            try:
                self.found.append(open(p).read(100))
            except OSError:
                pass''' % os.path.join(SEALED_TESTS, "bench.json"))),
        ("writes reward 1 and fake metrics, never cools",
         mk("tamper", 'return {"supply_temp_c": 22.0, "valve_duty": {"west": 0, "east": 0}}',
            init_body='''for p, s in (("%s/reward.txt", "1"), ("%s/metrics.json", "{}")):
            try:
                open(p, "w").write(s)
            except OSError:
                pass''' % (LOGS, LOGS))),
        ("forges a protocol reply on the verifier's pipe",
         mk("forge", 'return {"supply_temp_c": 22.0, "valve_duty": {"west": 0, "east": 0}}', init_body='''import os, json
        for fd in os.listdir("/proc/self/fd"):
            try:
                os.write(int(fd), (json.dumps({"ok": True}) + "\\n").encode())
            except OSError:
                pass''')),
        ("kills the verifier", mk("killer", "return " + OK, init_body='''import os, signal
        for target in (os.getppid(), 1, -1):
            try:
                os.kill(target, signal.SIGKILL)
            except OSError:
                pass''')),
        ("fork bomb", mk("forkbomb", "return " + OK, init_body='''import os
        for _ in range(500):
            try:
                if os.fork() == 0:
                    import time; time.sleep(3600); os._exit(0)
            except OSError:
                break''')),
        ("allocates 8 GiB", mk("membomb", "return " + OK, init_body="self.x = bytearray(8 * 2**30)")),
    ]


def controls(ref):
    """Not cheats: the reference, and the reference with actuator errors it is not told about. In closed
    loop the estimator absorbs such errors, so these show robustness, not a loophole."""
    return [
        ("reference", ref),
        ("reference, every valve held open 40% longer than it planned",
         wrap_reference("padded", ref, '''cmd["valve_duty"] = {z: min(1.0, 1.4 * d) for z, d in cmd["valve_duty"].items()}''')),
        ("reference, supply 1 K colder than it planned",
         wrap_reference("colder", ref, '''cmd["supply_temp_c"] = cmd["supply_temp_c"] - 1.0''')),
    ]


def main():
    if os.geteuid() != 0:
        print("run as root: the controller is only demoted to 'nobody' when the verifier is root")
        return 1
    os.makedirs(LOGS, exist_ok=True)
    os.chmod(LOGS, 0o755)
    for p in ("reward.txt", "metrics.json"):
        with open(os.path.join(LOGS, p), "w") as f:
            f.write("sentinel")
    t0 = time.time()
    ref = reference()
    print("sealed tests directory: %s (mode %o); controllers run as uid %d\n"
          % (SEALED_TESTS, stat.S_IMODE(os.stat(SEALED_TESTS).st_mode), grade._sandbox_ids()[0]))
    print("SCORED CHEATS (reward from grade.grade, the function the gating test calls)")
    zero, cs = 0, cheats(ref)
    for label, path in cs:
        t1 = time.time()
        r = grade.grade(path)
        zero += r["reward"] == 0
        if r.get("error"):
            why = " ".join(str(r["error"]).split())
            why = why if len(why) <= 80 else why[:77] + "..."
            why = "error after %s steps: %s" % (r["steps_completed"], why)
        else:
            why = "ratio %.3f, zone-week fails %d" % (r["ratio_total"], r["zone_week_fails"])
        print("  %-62s reward %d  %s  [%.0f s]" % (label, r["reward"], why, time.time() - t1), flush=True)
    print("  -> %d of %d score 0\n" % (zero, len(cs)))
    print("CONTROLS (not cheats): the reference through the same path, and with actuator errors it is not told about")
    for label, path in controls(ref):
        t1 = time.time()
        r = grade.grade(path)
        print("  %-62s reward %d  ratio %.4f, zone-week fails %s  [%.0f s]"
              % (label, r["reward"], r["ratio_total"] or -1, r["zone_week_fails"], time.time() - t1), flush=True)
    print()
    print("LOG FILES after all of the above (cheats wrote '1' and '{}' where they could):")
    for p in ("reward.txt", "metrics.json"):
        print("  %s/%s: %r" % (LOGS, p, open(os.path.join(LOGS, p)).read()[:20]))
    print()
    isolation()
    print("\n[%.0f s]" % (time.time() - t0))
    return 0


PROBE = r'''
import ctypes, os, time

def attempt(fn):
    try:
        r = fn()
        return "ALLOWED" + ("" if r is None else ": " + str(r)[:60])
    except Exception as e:
        return "denied (%s)" % type(e).__name__

class Controller:
    def __init__(self):
        rep = self.report = {}
        ppid = os.getppid()
        rep["uid"] = os.getuid()
        rep["read sealed bench.json"] = attempt(lambda: open(@@BENCH@@).read(10))
        rep["read sealed world.py"] = attempt(lambda: open(@@WORLD@@).read(10))
        rep["list sealed tests dir"] = attempt(lambda: os.listdir(@@TESTS@@))
        rep["read /tests/bench.json"] = attempt(lambda: open("/tests/bench.json").read(10))
        rep["write reward.txt"] = attempt(lambda: open("/logs/verifier/reward.txt", "w").write("1"))
        rep["read verifier environ"] = attempt(lambda: open("/proc/%d/environ" % ppid).read(10))
        rep["read verifier memory"] = attempt(lambda: open("/proc/%d/mem" % ppid, "rb").read(1))
        rep["list verifier cwd"] = attempt(lambda: os.listdir("/proc/%d/cwd" % ppid))
        rep["list verifier fds"] = attempt(lambda: os.listdir("/proc/%d/fd" % ppid))
        rep["signal the verifier"] = attempt(lambda: os.kill(ppid, 0))
        rep["leave /tmp marker"] = attempt(lambda: open("/tmp/tabs_cheat_marker", "w").write("x"))
        rep["leave /var/tmp marker"] = attempt(lambda: open("/var/tmp/tabs_cheat_marker", "w").write("x"))
        rep["leave /dev/shm marker"] = attempt(lambda: open("/dev/shm/tabs_cheat_marker", "w").write("x"))
        libc = ctypes.CDLL(None, use_errno=True)
        rep["create SysV shm segment"] = attempt(
            lambda: (lambda i: i if i >= 0 else (_ for _ in ()).throw(OSError()))(
                libc.shmget(0x5744, 4096, 0o1000 | 0o666)))
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
    def step(self, obs):
        return {"supply_temp_c": 22.0, "valve_duty": {"west": 0, "east": 0}, "report": self.report}
'''


def leftovers(uid):
    found = []
    for d in ("/tmp", "/var/tmp", "/dev/shm"):
        p = os.path.join(d, "tabs_cheat_marker")
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
    src = (PROBE.replace("@@BENCH@@", repr(os.path.join(SEALED_TESTS, "bench.json")))
           .replace("@@WORLD@@", repr(os.path.join(SEALED_TESTS, "world.py")))
           .replace("@@TESTS@@", repr(SEALED_TESTS)))
    path = ctrl("probe", src)
    uid = grade._sandbox_ids()[0]
    box = grade.Sandbox(path)
    box.start()
    box.call({"op": "init"}, grade.INIT_TIMEOUT_S)
    rep, err = box.call({"op": "step", "obs": {"time": "2017-07-15T00:00"}}, grade.STEP_TIMEOUT_S)
    report = (rep or {}).get("command", {}).get("report", {"error": err})
    for k, v in report.items():
        print("  %-28s %s" % (k, v))
    during = leftovers(uid)
    box.close()
    after = leftovers(uid)
    print("  left behind while the run was live: %s" % (", ".join(during) or "nothing"))
    print("  left behind after the run was closed: %s" % (", ".join(after) or "nothing"))


if __name__ == "__main__":
    sys.exit(main())
