#!/usr/bin/env python3
"""The laboratory and the weigh shop (run as the lab user; the agent reaches them only through the `gc` and `weigh`
wrappers).

    lab.py gc <stage>         the gas analysis of a stage's sample stream, mol per cent to 0.01
    lab.py weigh <cylinder>   the weight of a throw's reciprocating assembly, kg to 0.1

Both commands draw on one allowance of isim.BUDGET readings, which does not refill. Each reading leaves one record
file in STATE, created exclusively (O_EXCL, O_NOFOLLOW). A weighing comes from numpy's generator seeded with (seed,
the reading number, the command and its arguments), so the same reading in the same place of a plan always gives the
same report; an analysis is the laboratory's report of record and does not move. The services refuse to run if their
directories are not as installed.
"""
import json
import os
import re
import stat
import sys

sys.dont_write_bytecode = True
LAB = os.environ.get("LAB_DIR", "/opt/lab")          # the overrides are for local testing; sudo resets the environment
SEALED = os.path.join(LAB, "sealed")
STATE = os.path.join(LAB, "state")
REPORTS = os.environ.get("REPORT_DIR", "/app/lab_reports")


def refuse(msg, code=1):
    print(msg)
    sys.exit(code)


def check_dir(path, mode=0o700):
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid() and (st.st_mode & 0o777) == mode


def main(argv):
    sys.path.insert(0, SEALED)
    import isim as S  # noqa: E402
    import numpy as np  # noqa: E402
    usage = ("usage: gc <stage>        (stages: 1 2 3)\n"
             "       weigh <cylinder>  (cylinders: %s)" % " ".join(sorted(S.CYL)))
    if len(argv) != 2 or argv[0] not in S.LAB_CMDS:
        refuse(usage, 2)
    cmd, arg = argv
    if cmd == "gc" and arg not in ("1", "2", "3"):
        refuse(usage, 2)
    if cmd == "weigh" and arg not in S.CYL:
        refuse(usage, 2)
    if not (check_dir(SEALED) and check_dir(STATE) and check_dir(REPORTS, 0o755)):
        refuse("the service is not available (state check failed)")
    seed = json.load(open(os.path.join(SEALED, "seed.json")))["seed"]
    done = 0
    for name in os.listdir(STATE):
        if re.match(r"^reading_\d{2}\.json$", name):
            if not stat.S_ISREG(os.lstat(os.path.join(STATE, name)).st_mode):
                refuse("the service's records are damaged; refusing")
            done += 1
    if done >= S.BUDGET:
        refuse("allowance used: %d of %d readings" % (done, S.BUDGET))
    idx = done + 1
    try:
        fd = os.open(os.path.join(STATE, "reading_%02d.json" % idx),
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        refuse("the service is busy; try again")
    if cmd == "gc":
        v = S.lab_gc(int(arg))
        head = "# reading %d: gas analysis, stage %s sample stream" % (idx, arg)
        body = "component,mol_per_cent\n" + "\n".join("%s,%.2f" % (c, v[c]) for c in S.COMPONENTS)
        name = "reading_%02d_gc_stage%s.csv" % (idx, arg)
    else:
        rng = np.random.default_rng([seed, idx, 5, list(S.LAB_CMDS).index(cmd), sorted(S.CYL).index(arg)])
        w = S.lab_weigh(arg, rng)
        v = {"reciprocating_weight_kg": w}
        head = "# reading %d: weigh shop, reciprocating assembly of cylinder %s" % (idx, arg)
        body = "cylinder,reciprocating_weight_kg\n%s,%.1f" % (arg, w)
        name = "reading_%02d_weigh_%s.csv" % (idx, arg)
    text = "%s\n%s\n" % (head, body)
    with os.fdopen(fd, "w") as f:
        json.dump({"reading": idx, "argv": argv, "value": v}, f)
    rfd = os.open(os.path.join(REPORTS, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(rfd, "w") as f:
        f.write(text)
    sys.stdout.write(text)
    print("# readings used %d of %d; report saved as %s" % (idx, S.BUDGET, os.path.join(REPORTS, name)))


if __name__ == "__main__":
    main(sys.argv[1:])
