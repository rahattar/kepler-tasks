"""Design-rule checks on the sealed fleet. Run from this directory:  python3 -I tune.py

Checks, all of which must pass before the fleet is shipped:
- every cause in MS-BP's list, and every cause used by at least two chambers;
- the dominant gas mechanism clear of the next by DOM_RATIO, so no chamber sits on a boundary;
- S_eff / S_rated either at or above PUMP_CLEAR_HI or at or below PUMP_CLEAR_LO, so clause 6 is never a knife edge;
- every chamber's base pressure above its specified base pressure (each is a chamber under audit);
- the quantities spread over at least a decade, so no constant answer can pass;
- no two chambers within NEAR of each other in both quantities;
- the example chamber plainly dominated by one mechanism and sound in every record;
- every chamber load-bearing and identifiable (identify.py), with exactly NEEDS_TEST needing the audit test,
  and the test at the contractor's default pumping time not enough.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpphys as P                                                      # noqa: E402
import fleet as F                                                       # noqa: E402

DOM_RATIO = 1.60                    # the largest gas load over the next largest
PUMP_CLEAR_LO = 0.62                # a degraded pump must sit at or below this fraction of rated
PUMP_CLEAR_HI = 0.95                # a sound pump at or above it
NEAR = 0.08
NEEDS_TEST = ("VC08",)              # the one chamber the audit test must be spent on
TEST_TIMES = (16.0, 20.0, 24.0, 30.0, 36.0, 42.0, 48.0)
DEFAULT_TEST_H = F.DEFAULT_TEST_H    # the contractor's standing pumping time, used when a plan names none

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)
    return ok


def main():
    rows = []
    for cid in F.CHAMBER_IDS:
        ch = F.BY[cid]
        t = F.truth(ch)
        m = t["margins"]
        c = F.config(ch)
        comp = P.components(c, F.REF_H, "air", P.T_REF)
        rows.append((cid, t, m, comp, ch))

    print("%-5s %-16s %10s %8s %8s %7s %7s %7s  %s" % (
        "id", "cause", "q_total", "s_eff", "s_rated", "ratio", "pump", "p/spec", "gas split"))
    for cid, t, m, comp, ch in rows:
        order = sorted(comp.items(), key=lambda kv: -kv[1])
        split = " ".join("%s=%.0f%%" % (k[:4], 100 * v / t["q_total"]) for k, v in order if v > 0)
        print("%-5s %-16s %10.3e %8.1f %8.1f %7.2f %7.3f %7.2f  %s" % (
            cid, t["cause"], t["q_total"], t["s_eff"], t["s_rated"], m["ratio"], m["pump"],
            t["p_base"] / ch["reg"]["p_spec"], split))

    for cid, t, m, comp, ch in rows:
        check(t["cause"] in P.CAUSES, "%s: cause %r not in MS-BP's list" % (cid, t["cause"]))
        if t["cause"] == "pump-speed":
            check(m["pump"] <= PUMP_CLEAR_LO,
                  "%s: pump at %.3f of rated, not clear of the %.2f gate" % (cid, m["pump"], P.PUMP_GATE))
        else:
            check(m["pump"] >= PUMP_CLEAR_HI,
                  "%s: pump at %.3f of rated, too near the %.2f gate" % (cid, m["pump"], P.PUMP_GATE))
            check(m["ratio"] >= DOM_RATIO,
                  "%s: dominant gas load only %.2f x the next (want %.2f)" % (cid, m["ratio"], DOM_RATIO))
        check(t["p_base"] > ch["reg"]["p_spec"],
              "%s: base pressure %.2e is already inside its specified %.2e" % (cid, t["p_base"], ch["reg"]["p_spec"]))

    used = {}
    for cid, t, _m, _c, _ch in rows:
        used.setdefault(t["cause"], []).append(cid)
    for cause in P.CAUSES:
        check(len(used.get(cause, [])) >= 2,
              "cause %s is used by %d chambers (want at least 2)" % (cause, len(used.get(cause, []))))
    print("\ncauses: " + "; ".join("%s %s" % (k, ",".join(v)) for k, v in sorted(used.items())))

    qs = [t["q_total"] for _c, t, _m, _cc, _ch in rows]
    ss = [t["s_eff"] for _c, t, _m, _cc, _ch in rows]
    check(max(qs) / min(qs) >= 10, "the gas loads span only %.1f x (want a decade)" % (max(qs) / min(qs)))
    check(max(ss) / min(ss) >= 4, "the speeds span only %.1f x" % (max(ss) / min(ss)))
    print("q_total %.3e to %.3e (%.1f x); s_eff %.1f to %.1f (%.1f x)" % (
        min(qs), max(qs), max(qs) / min(qs), min(ss), max(ss), max(ss) / min(ss)))

    for i, (ci, ti, _mi, _xi, _hi) in enumerate(rows):
        for cj, tj, _mj, _xj, _hj in rows[i + 1:]:
            if (abs(ti["q_total"] - tj["q_total"]) / ti["q_total"] < NEAR
                    and abs(ti["s_eff"] - tj["s_eff"]) / ti["s_eff"] < NEAR):
                check(False, "%s and %s are within %.0f%% in both quantities" % (ci, cj, 100 * NEAR))

    import datetime
    import math as _m

    def climate(date):
        doy = datetime.date(*map(int, date.split("-"))).timetuple().tm_yday
        return 16.0 + 9.0 * _m.sin(2 * _m.pi * (doy - 112) / 365.25)

    for cid in F.CHAMBER_IDS + [F.EXAMPLE]:
        ch = F.BY[cid]
        by_pd = {}
        for e in ch["log"]:
            by_pd.setdefault((e[0], e[1]), set()).add(e[4])
        for (date, pid), temps in by_pd.items():
            check(len(temps) == 1,
                  "%s %s on %s has more than one wall temperature: %s" % (cid, pid, date, sorted(temps)))
            t = sorted(temps)[0]
            check(abs(t - climate(date)) <= 3.0,
                  "%s %s wall temperature %.1f C is %.1f C off the shop climate on %s"
                  % (cid, pid, t, t - climate(date), date))
        for date, hours, temp, *_g in ch["speed"]:
            check(abs(temp - climate(date)) <= 3.0,
                  "%s speed test of %s at %.1f C is %.1f C off the shop climate"
                  % (cid, date, temp, temp - climate(date)))
    for cid, (hours, temp) in F.AUDIT_TESTS.items():
        check(abs(temp - climate(F.AUDIT)) <= 3.0,
              "%s audit test at %.1f C is %.1f C off the shop climate on the audit date"
              % (cid, temp, temp - climate(F.AUDIT)))

    # The two rules the review of 11 November showed the fleet must be designed to: the gas budget is
    # load-bearing on every chamber, and identifiable on every chamber. Exactly NEEDS_TEST needs the one audit
    # test to be identified, and must not be identifiable without it, so the budget is spent where it counts.
    import identify as I
    print("\nload-bearing and identifiable (identify.py)")
    for cid in F.CHAMBER_IDS:
        ch = F.BY[cid]
        lb, nearest, surv = I.load_bearing(ch)
        p_rec, sd, _p99 = I.identifiability(ch)
        line = "  %s  nearest single-entry route %6.1f%%   records alone P=%.2f (sd %.1f%%)" % (
            cid, 100 * nearest, p_rec, 100 * sd)
        check(lb, "%s is not load-bearing: %d single-entry route(s) within %.0fx the tolerance, nearest %.1f%%"
              % (cid, len(surv), I.SHORTCUT_X, 100 * nearest))
        if cid in NEEDS_TEST:
            check(p_rec < 0.5, "%s is meant to need the audit test but its records alone give P=%.2f"
                  % (cid, p_rec))
            ok_times = [t for t in TEST_TIMES if I.identifiability(ch, t, draws=200)[0] >= I.IDENT_P]
            line += "   with a test at %s h" % (" ".join("%.0f" % t for t in ok_times) or "no time")
            check(ok_times, "%s cannot be identified with one test at any of %s h" % (cid, TEST_TIMES))
            check(DEFAULT_TEST_H not in ok_times,
                  "%s is identified by a test at the contractor's default %.0f h; the time must matter"
                  % (cid, DEFAULT_TEST_H))
        else:
            check(p_rec >= I.IDENT_P, "%s is not identifiable from its records: P=%.2f" % (cid, p_rec))
        print(line)

    te = F.truth(F.EX)
    check(te["margins"]["ratio"] >= 3.0, "the example's dominance is only %.2f x" % te["margins"]["ratio"])
    check(te["margins"]["pump"] >= PUMP_CLEAR_HI, "the example's pump is not clearly sound")
    print("\nexample %s: %s q=%.3e s=%.1f (ratio %.2f, pump %.3f)" % (
        F.EXAMPLE, te["cause"], te["q_total"], te["s_eff"], te["margins"]["ratio"], te["margins"]["pump"]))

    print("\n%d checks failed" % len(fails))
    for f in fails:
        print("  FAIL " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
