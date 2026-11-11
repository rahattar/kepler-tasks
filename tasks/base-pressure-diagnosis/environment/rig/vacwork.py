"""This quarter's audit test order for the vacuum shop (runs as the contractor user). One order of up to
fleet.BUDGET tests across the whole fleet, placed once.

    python3 -I vacwork.py status OUT_DIR STATE_FILE
    python3 -I vacwork.py submit OUT_DIR STATE_FILE  < plan.json

plan.json: {"tests": [{"chamber": "VC03", "test": "rga", "pumping_time_h": 20}, ...]}, 1 to BUDGET entries, the
test one of rate-of-rise, speed-test, rga or helium, no entry repeated. `pumping_time_h` is optional: the hours from
the start of roughing at which the measurement is taken, from TEST_H_MIN to TEST_H_MAX, and DEFAULT_TEST_H when the
plan names none. A helium test is taken with the chamber under vacuum and does not depend on it.

The order is charged to the state file before any record is written, and a state that cannot be read counts as
already ordered, so no test can be had twice. Records are created in OUT_DIR as new files only, never following a
link. Every reading is a deterministic function of the sealed definition and the test's place in the plan, so a
plan always yields the same reports.
"""
import fcntl
import json
import math
import os
import stat
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "sealed"))
import bpphys as P                                                      # noqa: E402
import fleet as F                                                       # noqa: E402

TESTS = ("rate-of-rise", "speed-test", "rga", "helium")
DEFAULT_TEST_H = F.DEFAULT_TEST_H    # the contractor's standing pumping time, and its range: one source, sealed
TEST_H_MIN = F.TEST_H_MIN
TEST_H_MAX = F.TEST_H_MAX
LAB_SEED = 91137                    # the laboratory's scatter; authoring studies vary it in memory, never here
NOFOLLOW = os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
ROR_MIN = 60
ROR_STEP = 10
HE_SECONDS = 300
HE_STEP = 10
SPECIES_MZ = [("h2", 2), ("h2o", 18), ("n2", 28), ("o2", 32), ("ar", 40), ("co2", 44)]


def fail(msg, code=2):
    print(json.dumps(dict(error=msg)), flush=True)
    sys.exit(code)


def open_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | NOFOLLOW)
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or st.st_mode & 0o022:
        os.close(fd)
        fail("output directory must be this user's own and writable by no one else")
    return fd


def load(state):
    try:
        fd = os.open(state, os.O_RDONLY | NOFOLLOW)
    except FileNotFoundError:
        return dict(ordered=False, tests=[])
    except OSError:
        return dict(ordered=True, tests=[], note="state unreadable")
    try:
        with os.fdopen(fd) as f:
            s = json.load(f)
        return dict(ordered=bool(s["ordered"]), tests=list(s["tests"]))
    except Exception:
        return dict(ordered=True, tests=[], note="state invalid")


def save(state, s):
    tmp = state + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(s, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, state)


def parse_hours(t):
    """The plan's pumping time, or the default. A number in range; never a boolean, a string or a non-finite."""
    if "pumping_time_h" not in t:
        return DEFAULT_TEST_H
    v = t["pumping_time_h"]
    assert isinstance(v, (int, float)) and not isinstance(v, bool)
    v = float(v)
    assert math.isfinite(v) and TEST_H_MIN <= v <= TEST_H_MAX
    return round(v, 1)


def parse(text):
    try:
        plan = json.loads(text)
        assert isinstance(plan, dict) and set(plan) == {"tests"}
        tests = plan["tests"]
        assert isinstance(tests, list) and 1 <= len(tests) <= F.BUDGET
        out = []
        for t in tests:
            assert isinstance(t, dict) and set(t) <= {"chamber", "test", "pumping_time_h"}
            cid = str(t["chamber"]).strip().upper()
            kind = str(t["test"]).strip().lower()
            assert cid in F.CHAMBER_IDS and kind in TESTS
            out.append((cid, kind, parse_hours(t)))
        assert len({(c, k) for c, k, _h in out}) == len(out)
        return out
    except Exception:
        fail('plan must be {"tests": [{"chamber": "VC01".."VC10", "test": "%s", "pumping_time_h": %g..%g}]}, '
             "1 to %d entries, none repeated; pumping_time_h is optional and defaults to %g"
             % (" | ".join(TESTS), TEST_H_MIN, TEST_H_MAX, F.BUDGET, DEFAULT_TEST_H))


def rng_for(cid, kind):
    return np.random.default_rng([LAB_SEED, F.CHAMBER_IDS.index(cid), TESTS.index(kind)])


def day_temperature(cid):
    """The chamber wall temperature on the day the contractor runs this quarter's tests."""
    return F.AUDIT_TESTS[cid][1]


# ----------------------------------------------------------------------------------------------------------------
def make_rate_of_rise(cid, t0):
    """Pressure against time with the high-vacuum valve closed, read with a spinning rotor gauge, which needs no
    gas correction."""
    ch = F.BY[cid]
    c = F.config(ch)
    temp = day_temperature(cid)
    g = rng_for(cid, "rate-of-rise")
    pts = P.rate_of_rise(c, t0, ROR_MIN, ROR_STEP, temp + 273.15)
    base = pts[0][1] * float(math.exp(g.normal(0, 0.003)))
    head = ["# rate-of-rise test, chamber %s" % cid,
            "# pumping time at valve closure: %.1f h" % t0,
            "# chamber wall temperature: %.1f C" % temp,
            "# spinning rotor gauge, total pressure, no gas correction required",
            "# base pressure before valve closure, mean of ten minutes: %.4e mbar" % base,
            "seconds,pressure_mbar"]
    rows = []
    for sec, p in pts:
        rows.append("%d,%.4e" % (sec, p * float(math.exp(g.normal(0, 0.0025)))))
    return "rate_of_rise_%s.csv" % cid.lower(), "\n".join(head + rows) + "\n"


def make_speed_test(cid, t0):
    ch = F.BY[cid]
    c = F.config(ch)
    temp = day_temperature(cid)
    g = rng_for(cid, "speed-test")
    s = P.s_eff(c, P.p_base(c, P.q_total(c, t0, "air", temp + 273.15)))
    base_ind = P.indicated(c, t0, "air", temp + 273.15)
    flow = float("%.3g" % (s * 4.0e-5))
    p_wo = base_ind * float(math.exp(g.normal(0, 0.005)))
    p_w = (base_ind + flow / s) * float(math.exp(g.normal(0, 0.005)))
    head = ["# throughput speed test, chamber %s" % cid,
            "# pumping time: %.1f h" % t0,
            "# chamber wall temperature: %.1f C" % temp,
            "# dry nitrogen admitted through a calibrated leak; gauge calibrated against nitrogen, factor 1.00",
            "flow_mbarl_s,p_with_flow_mbar,p_without_flow_mbar,s_eff_l_s"]
    rows = ["%.4g,%.4e,%.4e,%.1f" % (flow, p_w, p_wo, flow / (p_w - p_wo))]
    return "speed_test_%s.csv" % cid.lower(), "\n".join(head + rows) + "\n"


def make_rga(cid, t0):
    ch = F.BY[cid]
    c = F.config(ch)
    temp = day_temperature(cid)
    g = rng_for(cid, "rga")
    pp = P.partials(c, t0, "air", temp + 273.15)
    head = ["# residual gas analysis, chamber %s" % cid,
            "# pumping time: %.1f h" % t0,
            "# chamber wall temperature: %.1f C" % temp,
            "# quadrupole analyser, partial pressures of the species it resolves",
            "species,mass_number,partial_pressure_mbar"]
    rows = []
    for name, mz in SPECIES_MZ:
        v = pp.get(name, 0.0)
        v = v * float(math.exp(g.normal(0, 0.010))) + abs(float(g.normal(0, 8e-12)))
        rows.append("%s,%d,%.3e" % (name, mz, v))
    return "rga_%s.csv" % cid.lower(), "\n".join(head + rows) + "\n"


def make_helium(cid, _t0=None):
    """The detector's helium leak rate against time while each region is hooded in turn. A channel in molecular
    flow answers in seconds; gas crossing an elastomer seal by permeation answers over minutes."""
    ch = F.BY[cid]
    c = F.config(ch)
    g = rng_for(cid, "helium")
    bg = 4.0e-11
    leak_region = F.LEAK_AT[cid]
    sharp = c["leak"] * F.HE_AIR_RATIO
    # the helium that crosses the seals of a hooded elastomer region, as a share of its length
    perm_he = P.q_perm(c["seal"], c["seal_cm"], P.T_REF) * 9.0
    head = ["# helium leak test, chamber %s" % cid,
            "# chamber under vacuum; each region hooded with helium in turn for %d s" % HE_SECONDS,
            "# detector reads the helium leak rate, mbar L/s",
            "region,seconds,he_leak_rate_mbarl_s"]
    rows = []
    for region in F.REGIONS:
        share = 1.0 / len(F.ELASTOMER_REGIONS) if region in F.ELASTOMER_REGIONS else 0.0
        for i in range(HE_SECONDS // HE_STEP + 1):
            sec = i * HE_STEP
            v = bg
            if region == leak_region:
                v += sharp * (1.0 - math.exp(-sec / 8.0))
            v += perm_he * share * (1.0 - math.exp(-sec / 180.0))
            v = v * float(math.exp(g.normal(0, 0.02))) + abs(float(g.normal(0, 3e-12)))
            rows.append("%s,%d,%.3e" % (region, sec, v))
    return "helium_%s.csv" % cid.lower(), "\n".join(head + rows) + "\n"


MAKERS = {"rate-of-rise": make_rate_of_rise, "speed-test": make_speed_test, "rga": make_rga,
          "helium": make_helium}


def write_file(dfd, name, text):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | NOFOLLOW, 0o644, dir_fd=dfd)
    with os.fdopen(fd, "w") as f:
        os.fchmod(f.fileno(), 0o644)
        f.write(text)


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("status", "submit"):
        fail("usage: vacwork status | vacwork submit < plan.json")
    cmd, out, state = sys.argv[1:]
    lockfd = os.open(state + ".lock", os.O_RDWR | os.O_CREAT | NOFOLLOW, 0o600)
    fcntl.flock(lockfd, fcntl.LOCK_EX)
    s = load(state)
    if cmd == "status":
        print(json.dumps(dict(ordered=s["ordered"], tests=s["tests"], budget=F.BUDGET,
                              tests_remaining=0 if s["ordered"] else F.BUDGET,
                              tests_available=list(TESTS), chambers=list(F.CHAMBER_IDS),
                              pumping_time_h=dict(default=DEFAULT_TEST_H, min=TEST_H_MIN, max=TEST_H_MAX)),
                         indent=1))
        return
    if s["ordered"]:
        fail("the audit test order has already been placed", 3)
    plan = parse(sys.stdin.read(65536))
    s = dict(ordered=True, tests=[dict(chamber=c, test=k, pumping_time_h=h) for c, k, h in plan])
    save(state, s)                                   # charged before any record is written
    dfd = open_dir(out)
    index = []
    for cid, kind, hours in plan:
        name, text = MAKERS[kind](cid, hours)
        write_file(dfd, name, text)
        index.append(dict(file=name, chamber=cid, test=kind, hours=hours))
    lines = ["file,chamber,test,pumping_time_h"] + [
        "%s,%s,%s,%s" % (r["file"], r["chamber"], r["test"], "" if r["test"] == "helium" else "%.1f" % r["hours"])
        for r in index]
    write_file(dfd, "vacwork_index.csv", "\n".join(lines) + "\n")
    print(json.dumps(dict(ordered=True, tests=s["tests"], records=len(index),
                          index="vacwork_index.csv"), indent=1))


if __name__ == "__main__":
    main()
