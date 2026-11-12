"""The systematic solver's checks, run on the agent-visible files: whatever this prints as odd, a probe finds.

trap-analysis-2026-11-11.md, section 6.3: write the auditor before the probes. This script reads only what the
agent reads (environment/data), takes every record at face value, and runs the checks a careful low-effort run
does unprompted: every speed test against the rated speed of the chamber as documented on its date, pooled and
split by date under three statistics; every pair of instruments on one chamber; every gauge serial against the
certificate that owns it; every controller row against the vacuum data's figures for every model; every chamber's
gas budget fitted at face value, with its residuals, its steps at dated work and the structures a fit would try;
every chamber's spread of pumping times; and every speed test's no-flow pressure against the log.

It borrows only the documented physics from solution/diagnose.py (the tables, the gas budget's shape, the gauge
correction), never the reference's corrections: the readings are taken through their certificates as issued, the
speeds as reported, the register as changed by the maintenance log's own words.

    python3 -I auditor.py [data_dir]   (default: the shipped environment/data)

Each finding is printed as ODD when a solver running that check would see something to explain, and as clean
otherwise. The summary at the end lists, per chamber, every check that is odd.
"""
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TASK = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(TASK, "solution"))
import diagnose as D                                                    # noqa: E402

READ = 0.006
SPEED = 0.005
ODD = {}


def odd(cid, check, text):
    ODD.setdefault(cid, []).append("%s: %s" % (check, text))
    print("  ODD   %-5s %s" % (cid, text))


def clean(cid, text):
    print("  clean %-5s %s" % (cid, text))


def raw(d):
    """The records as the agent reads them: no correction of any kind."""
    return dict(
        register=D.read_csv(os.path.join(d, "chamber_register.csv")),
        log=D.read_csv(os.path.join(d, "base_pressure_log.csv")),
        speed=D.read_csv(os.path.join(d, "speed_tests.csv")),
        ctrl=D.read_csv(os.path.join(d, "turbo_controller.csv")),
        maint=D.read_csv(os.path.join(d, "maintenance_log.csv")),
        certs=D.parse_certs(os.path.join(d, "gauge_certificates.md")),
    )


def ids(data):
    return sorted({r["chamber"] for r in data["register"]})


def header(title):
    print("")
    print(title)
    print("-" * len(title))


# ------------------------------------------------------------------------------------------------- the checks
def check_controllers(data):
    header("Controllers against the vacuum data's figures for a pump in good order")
    for cid in ids(data):
        rows = [r for r in data["ctrl"] if r["chamber"] == cid]
        reg = D.chamber_config(cid, data)["turbo"]
        fig = {m: v for m, v in D.TURBO.items()}
        # nearest model to the median row, and steps along the series
        med = [statistics.median(float(r[k]) for r in rows) for k in ("rotor_hz", "drive_power_w", "bearing_temp_c")]
        best = min(fig, key=lambda m: sum(abs(a - b) / b for a, b in zip(med, D.TURBO_SIG[m])))
        if best != reg:
            odd(cid, "controller", "controller median matches %s, register names %s" % (best, reg))
        else:
            clean(cid, "controller matches the register's %s" % reg)
        hz = [float(r["rotor_hz"]) for r in rows]
        for i in range(2, len(hz) - 1):
            a, b = statistics.mean(hz[:i]), statistics.mean(hz[i:])
            if abs(b / a - 1) > 0.03:
                odd(cid, "controller", "rotor frequency steps %.0f -> %.0f Hz at %s" % (a, b, rows[i]["date"]))
                break


def rated_on(cfg, date):
    return D.rated_on(cfg, date)


def check_speed_tests(data):
    header("Every shop speed test against the rated speed of the chamber as documented on its date")
    pts = []
    for cid in ids(data):
        cfg = D.with_controller_pump(cid, D.chamber_config(cid, data), data)
        changed = D.pump_changed_on(cid, data)
        for r in sorted([r for r in data["speed"] if r["chamber"] == cid], key=lambda r: r["date"]):
            rated = rated_on(cfg, r["date"])
            s = float(r["s_eff_l_s"])
            tag = "after the pump changed" if changed and r["date"] >= changed else ""
            if rated is None:
                odd(cid, "speed", "%s test %.1f L/s, rated unknown (port conductance not recorded)" % (r["date"], s))
                continue
            ratio = s / rated
            if not tag:
                pts.append((r["date"], ratio, cid))
            if abs(ratio - 1) > 0.03 and not tag:
                odd(cid, "speed", "%s test %.1f L/s = %.3f of rated %.1f, pump in order (%s)"
                    % (r["date"], s, ratio, rated, r["gauge"]))
            else:
                clean(cid, "%s test %.3f of rated %s" % (r["date"], ratio, tag))
    header("The fleet's speed ratios, pooled and split by date")
    v = [p[1] for p in pts]
    print("  pooled: mean %.3f median %.3f sd %.3f (n %d)" % (statistics.mean(v), statistics.median(v),
                                                             statistics.pstdev(v), len(v)))
    by_year = {}
    for d, r, _c in pts:
        by_year.setdefault(d[:4], []).append(r)
    for y, vals in sorted(by_year.items()):
        print("  %s: median %.3f mean %.3f n %d" % (y, statistics.median(vals), statistics.mean(vals), len(vals)))
    if len(by_year) > 1:
        meds = [statistics.median(v) for _y, v in sorted(by_year.items())]
        if abs(meds[-1] / meds[0] - 1) > 0.03:
            odd("fleet", "speed", "median speed ratio moves %.3f -> %.3f between years" % (meds[0], meds[-1]))


def check_gauges(data):
    header("Gauges: serials against their certificates, pairs on one chamber, steps at serial changes")
    certs = data["certs"]
    for cid in ids(data):
        rows = sorted([r for r in data["log"] if r["chamber"] == cid], key=lambda r: r["date"])
        serials = []
        for r in rows:
            if r["gauge"] not in serials:
                serials.append(r["gauge"])
            owner = certs.get(r["gauge"], [None])[0]
            if owner and owner != cid:
                odd(cid, "gauge", "%s logged %s, whose certificate says it is installed on %s"
                    % (r["date"], r["gauge"], owner))
                break
        for s in serials:
            if s in certs:
                issued = [d for d, _f in certs[s][1]]
                first_use = min(r["date"] for r in rows if r["gauge"] == s)
                if issued and issued[0] < "2026-01-01":
                    odd(cid, "gauge", "%s certificate issued %s, before this year's" % (s, issued[0]))
                if len(issued) > 1:
                    odd(cid, "gauge", "%s recertified on %s (factor %s)" % (s, issued[1:], certs[s][1][1:]))
                _ = first_use
        pairs = {}
        for r in rows:
            pairs.setdefault((r["date"], r["pumpdown"]), {})[r["gauge"][:2]] = float(r["reading_mbar"])
        both = [(d, v["CC"] / v["IG"]) for (d, _p), v in sorted(pairs.items()) if "CC" in v and "IG" in v]
        if both:
            rs = [x for _d, x in both]
            if abs(rs[-1] - rs[0]) > 0.02:
                odd(cid, "gauge", "CC/IG ratio drifts %.3f -> %.3f (%s to %s)" % (rs[0], rs[-1], both[0][0], both[-1][0]))
            elif abs(statistics.mean(rs) - 1) > 0.03:
                odd(cid, "gauge", "CC/IG ratio steady at %.3f, not 1" % statistics.mean(rs))
            else:
                clean(cid, "CC/IG ratio %.3f" % statistics.mean(rs))


def naive_obs(cid, data, speed_rule):
    """The log at face value: one reading per pumpdown (the ionization gauge where read), through the certificate
    of the serial the log names, at the speed the rule gives."""
    cfg = D.with_controller_pump(cid, D.chamber_config(cid, data), data)
    rows = [r for r in data["log"] if r["chamber"] == cid]
    if cfg["internals_from"]:
        rows = [r for r in rows if r["date"] >= cfg["internals_from"]]
    by = {}
    for r in rows:
        by.setdefault((r["date"], r["pumpdown"]), []).append(r)
    obs = []
    for (date, _pd), g in sorted(by.items()):
        pick = next((r for r in g if r["gauge"].startswith("IG")), sorted(g, key=lambda r: r["gauge"])[0])
        if pick["gauge"] not in data["certs"]:
            continue
        sp = speed_rule(cid, cfg, data, date)
        if sp is None:
            continue
        obs.append(dict(kind="entry", date=date, t_h=float(pick["pumpdown_h"]),
                        t_k=float(pick["wall_temp_c"]) + 273.15, vent=pick["vent_gas"], load=pick["load"].strip(),
                        value=float(pick["reading_mbar"]) * D.cert_factor(data["certs"], pick["gauge"], date),
                        gauge=True, speed=sp, sd=READ, serial=pick["gauge"]))
    return cfg, obs


def rule_rated(cid, cfg, data, date):
    changed = D.pump_changed_on(cid, data)
    if changed and date >= changed:
        return "now"
    return D.rated_on(cfg, date)


def rule_latest_test(cid, cfg, data, date):
    tests = sorted([r for r in data["speed"] if r["chamber"] == cid and r["date"] <= date], key=lambda r: r["date"])
    later = sorted([r for r in data["speed"] if r["chamber"] == cid], key=lambda r: r["date"])
    pick = tests[-1] if tests else (later[0] if later else None)
    return float(pick["s_eff_l_s"]) if pick else None


def fit(cfg, obs, structure, s_now):
    try:
        chi2, k, p, q = D.fit_budget(cfg, obs, structure, s_now)
    except Exception:
        return None
    return chi2, k, p


def check_budgets(data):
    header("Every chamber's gas budget fitted at face value")
    for cid in ids(data):
        for name, rule in (("rated speed", rule_rated), ("speed tests", rule_latest_test)):
            cfg, obs = naive_obs(cid, data, rule)
            if len(obs) < 3:
                odd(cid, "budget", "%s: %d usable entries" % (name, len(obs)))
                continue
            s_now = 1.0 if any(o["speed"] == "now" for o in obs) else None
            if s_now is not None:
                # a pump that changed: its speed now is fitted
                lo = 50.0
                best = None
                for s in [lo * 1.03 ** i for i in range(100)]:
                    r = fit(cfg, obs, dict(seal=None, trapped_from=None), s)
                    if r and (best is None or r[0] < best[0]):
                        best = (r[0], s)
                s_now = best[1]
            plain = fit(cfg, obs, dict(seal=None, trapped_from=None), s_now)
            n = len(obs)
            rms = math.sqrt(plain[0] / n) * READ * 100 if plain else float("nan")
            line = "%s: plain budget chi2 %.1f over %d entries (rms %.2f%%)" % (name, plain[0], n, rms)
            if plain[0] > 2.5 * n:
                odd(cid, "budget", line)
            else:
                clean(cid, line)
            # what a fit would try next: another seal, a trapped volume from each dated piece of work
            for m in D.SEALS:
                if m == cfg["seal"]:
                    continue
                r = fit(cfg, obs, dict(seal=m, trapped_from=None), s_now)
                if r and plain[0] - r[0] > 10:
                    odd(cid, "budget", "%s: seal %s instead of %s improves chi2 %.1f -> %.1f"
                        % (name, m, cfg["seal"], plain[0], r[0]))
            work = sorted({r["date"] for r in data["maint"] if r["chamber"] == cid})
            for wd in ["0000-00-00"] + work:
                if n < 5:
                    break
                r = fit(cfg, obs, dict(seal=None, trapped_from=wd), s_now)
                if r and plain[0] - r[0] > 10:
                    odd(cid, "budget", "%s: a trapped volume from %s improves chi2 %.1f -> %.1f"
                        % (name, wd, plain[0], r[0]))


def check_coverage(data):
    header("Every chamber's spread of pumping times and wall temperatures since its last change of internals")
    for cid in ids(data):
        cfg = D.chamber_config(cid, data)
        rows = [r for r in data["log"] if r["chamber"] == cid and (not cfg["internals_from"] or
                                                                   r["date"] >= cfg["internals_from"])]
        hs = sorted({float(r["pumpdown_h"]) for r in rows})
        ts = [float(r["wall_temp_c"]) for r in rows]
        tests = [(r["date"], float(r["pumping_time_h"])) for r in data["speed"] if r["chamber"] == cid
                 and (not cfg["internals_from"] or r["date"] >= cfg["internals_from"])]
        line = "pumping times %s h, wall %.1f to %.1f C; speed tests at %s" % (
            " ".join("%g" % h for h in hs), min(ts), max(ts), " ".join("%s %g h" % t for t in tests))
        if len(hs) == 1:
            odd(cid, "coverage", "every entry at one pumping time: " + line)
        else:
            clean(cid, line)


def check_steps(data):
    header("Steps in each chamber's face-value gas load at dated work")
    for cid in ids(data):
        cfg, obs = naive_obs(cid, data, rule_rated)
        if any(o["speed"] == "now" for o in obs) or len(obs) < 4:
            continue
        q = [o["value"] * o["speed"] / max(D.nominal_wall(cfg, o), 1e-30) for o in obs]
        work = sorted({r["date"] for r in data["maint"] if r["chamber"] == cid})
        for wd in work:
            a = [x for x, o in zip(q, obs) if o["date"] < wd]
            b = [x for x, o in zip(q, obs) if o["date"] >= wd]
            if len(a) >= 2 and len(b) >= 2:
                ra = statistics.mean([o["value"] * o["speed"] for o in obs if o["date"] < wd])
                rb = statistics.mean([o["value"] * o["speed"] for o in obs if o["date"] >= wd])
                if abs(rb / ra - 1) > 0.25:
                    odd(cid, "steps", "gas load moves %.2fx across the work of %s" % (rb / ra, wd))


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(TASK, "environment", "data")
    data = raw(d)
    D.TURBO_SIG = {}
    with open(os.path.join(d, "docs", "vacuum_data.md")) as f:
        for line in f:
            if line.startswith("| TMP-"):
                c = [x.strip() for x in line.strip().strip("|").split("|")]
                D.TURBO_SIG[c[0]] = (float(c[2]), float(c[3]), float(c[4]))
    check_controllers(data)
    check_speed_tests(data)
    check_gauges(data)
    check_coverage(data)
    check_steps(data)
    check_budgets(data)
    header("Summary: what a systematic first pass sees, per chamber")
    for cid in ["fleet"] + ids(data):
        items = ODD.get(cid, [])
        print("%-5s %d odd" % (cid, len(items)))
        for it in items:
            print("        " + it)


if __name__ == "__main__":
    main()
