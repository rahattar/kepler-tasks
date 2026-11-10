"""How the tuned values in isim.py were set, and a check that they still follow from the rules.

    python3 authoring/provenance/tune.py

Design rules. Every value a route can get wrong has to move at least one band of one machine by at least twice the
grading tolerance (2 x %.1f dB), so that no single number can be right under both answers to a choice, and no reading
of the survey can land a machine inside the band by luck. Two groups of values in isim.py are tuned to that:

- the radius of each position the surveyor had to set off the measurement surface is the largest multiple of 0.05 m
  at which keeping it in its machine's energy average costs at least 2.5 dB in every band;
- the adjacent bay's blower, at the positions by the louvred wall, is in the 250 Hz and 500 Hz bands the smallest
  multiple of 0.1 dB at which keeping those positions with no background correction costs the worst affected machine
  at least 3.0 dB in that band. In the other bands the blower is set well below the machines, so only those two bands
  make the positions invalid.

The rest are checked as they stand: the acoustic report's reverberation time against the hall's own, the environmental
correction itself, the speed referrals, the configuration differences, the quarter space and array radius of the
machines against a wall, the instrument certificates, and the sheet's mislabelled rows. The script also checks that
every valid position is valid by the standard's background rule, that the positions by the louvred wall are not, that
each machine keeps at least the standard's least number of positions, and that the direct field averages to the
free-field value over each machine's valid positions, which is what makes a correct reduction of the survey give the
definition's sound power back exactly.
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isim as S  # noqa: E402

__doc__ = __doc__ % S.TOL
BAR = 2.0 * S.TOL


def e(x):
    return 10.0 ** (0.1 * x)


def db(x):
    return 10.0 * math.log10(x)


def valid(m):
    return [p for p in S.MACHINES[m]["positions"] if S.POS[p]["valid"]]


def surface_term(m, band, space=None, r=None):
    """10 lg S - K2 for a machine, with the surface the route uses"""
    j = S.MACHINES[m]
    s = S.surface(space or j["space"], r or j["r"])
    return db(s) - db(1.0 + 4.0 * s / S.area(band))


def cost_keep_off(pid, radius):
    """dB by which keeping an off-surface position at that radius raises its machine's energy average, by band"""
    m = S.POS[pid]["machine"]
    j = S.MACHINES[m]
    others = [p for p in j["positions"] if p != pid and p not in S.NEAR_WALL]
    out = []
    for b in S.BANDS:
        base = 1.0 / S.surface(j["space"], j["r"]) + 4.0 / S.area(b)
        bad = S.dev(pid) / S.surface(j["space"], radius) + 4.0 / S.area(b)
        out.append(db((len(others) * base + bad) / ((len(others) + 1) * base)))
    return out


def cost_keep_near(m, band, level):
    """dB by which keeping m's positions by the louvred wall with no background correction raises its average"""
    j = S.MACHINES[m]
    good = valid(m)
    base = sum(e(S.lp_machine(m, p, band, "survey")) for p in good) / len(good)
    rows = good + [p for p in j["positions"] if p in S.NEAR_WALL]
    tot = 0.0
    for p in rows:
        bg = level if p in S.NEAR_WALL else S.BLOWER_FAR[band]
        tot += e(S.lp_machine(m, p, band, "survey")) + e(S.BG[band]) + e(bg)
    return db((tot / len(rows)) / base)


def cost_relabel(band):
    """dB by which trusting the survey sheet's machine column moves the worst machine's energy average"""
    worst = 0.0
    for m in set(S.MISLABEL.values()):
        good = valid(m)
        right = sum(e(S.lp_machine(m, p, band, "survey")) for p in good) / len(good)
        rows = [p for p in good if p not in S.MISLABEL] + [p for p, v in S.MISLABEL.items() if v == m]
        wrong = sum(e(S.lp_machine(S.POS[p]["machine"], p, band, "survey")) for p in rows) / len(rows)
        worst = max(worst, abs(db(wrong / right)))
    return worst


def main():
    bad = 0

    for pid in S.OFF_SURFACE:
        r = max(x * 0.05 for x in range(1, 61) if min(cost_keep_off(pid, x * 0.05)) >= 2.5)
        ok = abs(r - S.POS[pid]["r"]) < 1e-9
        bad += not ok
        print("%s radius %.2f m (isim %.2f, %s); keeping it costs %.2f to %.2f dB" % (
            pid, r, S.POS[pid]["r"], "matches" if ok else "DIFFERS",
            min(cost_keep_off(pid, r)), max(cost_keep_off(pid, r))))

    near = sorted({S.POS[p]["machine"] for p in S.NEAR_WALL})
    for band in (250, 500):
        lv = next(x / 10.0 for x in range(500, 1200)
                  if max(cost_keep_near(m, band, x / 10.0) for m in near) >= 3.0)
        ok = abs(lv - S.BLOWER_NEAR[band]) < 1e-9
        bad += not ok
        print("blower by the louvred wall, %4s Hz: %.1f dB (isim %.1f, %s); keeping those positions costs %s" % (
            S.LABEL[band], lv, S.BLOWER_NEAR[band], "matches" if ok else "DIFFERS",
            ", ".join("%s %.2f dB" % (m, cost_keep_near(m, band, lv)) for m in near)))

    def report(name, worst):
        nonlocal bad
        ok = worst >= BAR
        bad += not ok
        print("%-62s worst band %+5.2f dB  %s" % (name, worst, "ok" if ok else "UNDER THE BAR of %.1f" % BAR))

    report("the acoustic report's reverberation time",
           max(S.k2(m, b) - S.k2(m, b, S.T60_REPORT) for m in S.MACHINES for b in S.BANDS))
    report("the environmental correction left out", max(S.k2(m, b) for m in S.MACHINES for b in S.BANDS))
    for m in S.MACHINES:
        j = S.MACHINES[m]
        if j["survey_rpm"] != j["rated"]:
            report("%s not referred to its rated speed" % m, S.speed_referral(m))
            report("%s referred with 20 lg instead of 50 lg" % m, abs(S.speed_referral(m) - 20.0 * math.log10(
                j["rated"] / j["survey_rpm"])))
        if j["sdelta"]:
            report("%s's configuration difference left out" % m,
                   max(S.lw(m, b, "survey") - S.lw(m, b) for b in S.BANDS))
            da = S.lwa(m, "survey") - S.lwa(m)
            report("%s's difference applied as one A-weighted figure" % m,
                   max(abs(da - (S.lw(m, b, "survey") - S.lw(m, b))) for b in S.BANDS))
        if j["space"] == "quarter":
            report("%s taken to radiate into a half space" % m,
                   max(surface_term(m, b, space="half") - surface_term(m, b) for b in S.BANDS))
            report("%s's array taken at the register's nominal radius" % m,
                   max(surface_term(m, b, r=S.NOMINAL_R) - surface_term(m, b) for b in S.BANDS))
    report("an instrument certificate left out, or applied to every row",
           max(max(v.values()) for v in S.METER.values()))
    report("the survey sheet's machine column trusted", max(cost_relabel(b) for b in S.BANDS))

    print()
    # the room check: the reference source's own level on its hemisphere gives the absorption area back exactly,
    # and the source stands far enough above the hall's background for the standard's rule
    worst_a, worst_m = 0.0, 0.0
    for b in S.BANDS:
        lp = db(sum(e(S.lp_rss(p, b)) for p in S.RSS_POS) / len(S.RSS_POS))
        a = 4.0 / (e(lp - S.RSS_LW[b]) - 1.0 / S.surface("half", S.RSS_R))
        worst_a = max(worst_a, abs(a / S.area(b) - 1.0))
        worst_m = max(worst_m, S.BG_MARGIN - min(S.lp_rss(p, b) - S.BG[b] for p in S.RSS_POS))
    ok = worst_a < 1e-9 and worst_m <= 0.0
    bad += not ok
    print("the room check returns the absorption area to %.1e and clears the background rule by %+.1f dB  %s" % (
        worst_a, -worst_m, "ok" if ok else "FAILS"))
    needed = [m for m, j in S.MACHINES.items() if j["sdelta"]]
    ok = len(needed) - 1 == S.BUDGET and S.CERTIFIED in needed
    bad += not ok
    print("%d machines need a configuration difference, %s's is certified in the register and the booking is %d  %s"
          % (len(needed), S.CERTIFIED, S.BUDGET, "ok" if ok else "FAILS"))

    # the machines referred by a measured difference cannot carry a constant certificate error through, so at least
    # one machine on each instrument must need no difference for the certificates to decide anything
    for name, machines in S.METER_DAY.items():
        plain = [m for m in machines if not S.MACHINES[m]["sdelta"]]
        ok = bool(plain) and set(machines) <= set(S.MACHINES)
        bad += not ok
        print("%s read %s; of those %s need no configuration difference  %s" % (
            name, " ".join(machines), " ".join(plain) or "none", "ok" if ok else "DIFFERS"))
    radii = {S.POS[p]["r"] for p in S.MISLABEL} | {S.MACHINES[m]["r"] for m in set(S.MISLABEL.values())}
    ok = len(radii) == 1 and len(set(S.MISLABEL.values())) == 2
    bad += not ok
    print("the mislabelled rows swap two arrays set at the same radius  %s" % ("ok" if ok else "DIFFERS"))
    print()
    for m in S.MACHINES:
        d = [S.lp_machine(m, p, b, "survey") - S.lp_background(p, b) for p in valid(m) for b in S.BANDS]
        f = sum(S.dev(p) for p in valid(m)) / len(valid(m))
        ok = min(d) >= S.BG_MARGIN and len(valid(m)) >= S.MIN_POSITIONS and abs(f - 1.0) < 1e-12
        bad += not ok
        print("%s: %2d valid positions, smallest margin over the background %+5.1f dB, direct field %.12f  %s" % (
            m, len(valid(m)), min(d), f, "ok" if ok else "FAILS"))
    for p in S.NEAR_WALL:
        m = S.POS[p]["machine"]
        d = min(S.lp_machine(m, p, b, "survey") - S.lp_background(p, b) for b in S.BANDS)
        ok = d < S.BG_MARGIN and not S.POS[p]["valid"]
        bad += not ok
        print("%s (%s): %+.1f dB over the background, so not a valid position  %s" % (
            p, m, d, "ok" if ok else "DIFFERS"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
