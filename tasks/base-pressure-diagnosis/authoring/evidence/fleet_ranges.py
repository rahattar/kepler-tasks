"""Every range the difficulty explanation quotes about the fleet, computed from the sealed definition and the
built records.

The explanation used to state these from memory. Two of them were wrong - the wall gas load coefficient's lower
end, and the longest pumpdown, which a 26 h record on VC06 put outside the range claimed - and a reviewer found
them by recomputing what the author had asserted. There is no reason for a number in the prose to be a different
number from the one in the data, so `meta.py` reads the lines below and writes the list from them.

Each line is `key: text`, where the text is the phrase the explanation uses.

    python3 -I fleet_ranges.py  > fleet_ranges.txt
"""
import collections
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C                                                      # noqa: E402

sys.path.insert(0, os.path.join(C.TASK, "tests", "sealed"))
import bpphys as P                                                      # noqa: E402

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def sci(v):
    """7e-06 as the prose writes it: 7 x 10^-6."""
    s = "%.1e" % v
    mant, exp = s.split("e")
    mant = mant.rstrip("0").rstrip(".")
    return "%s x 10^%d" % (mant, int(exp))


def span(vals, fmt="%g"):
    lo, hi = min(vals), max(vals)
    return "%s to %s" % (fmt % lo, fmt % hi)


def main():
    fleet = [ch for ch in C.F.FLEET if ch["id"] in C.F.CHAMBER_IDS]
    cfg = {ch["id"]: C.F.config(ch) for ch in fleet}
    tr = {ch["id"]: C.F.truth(ch) for ch in fleet}
    out = collections.OrderedDict()

    out["volume_l"] = span([c["volume"] for c in cfg.values()], "%.0f")
    out["turbo_l_s"] = span([max(p for _x, p in P.TURBO[c["turbo"]]) for c in cfg.values()], "%.0f")
    out["port_l_s"] = span([c["c_port"] for c in cfg.values()], "%.0f")
    out["s_eff_l_s"] = span([t["s_eff"] for t in tr.values()], "%.0f")
    out["seal_cm"] = span([c["seal_cm"] for c in cfg.values()], "%.0f")
    mats = sorted({c["seal"] for c in cfg.values()})
    out["seal_materials"] = (" and ".join([", ".join(mats[:-1]), mats[-1]]) if len(mats) > 1 else mats[0])
    out["surface_m2"] = span([sum(a for a, _m in c["surfaces"]) / 1e4 for c in cfg.values()], "%.2g")
    out["wall_factor"] = span([c["wall_factor"] for c in cfg.values()], "%.3g")

    leaks = [c["leak"] for c in cfg.values() if c["leak"]]
    out["leak"] = "%s to %s" % (sci(min(leaks)), sci(max(leaks)))
    taus = sorted({c["tau"] for c in cfg.values() if c["qv0"]})
    out["tau_h"] = (" and ".join("%g" % t for t in taus) if len(taus) < 3
                    else span(taus, "%g"))
    out["q_total"] = "%s to %s" % (sci(min(t["q_total"] for t in tr.values())),
                                   sci(max(t["q_total"] for t in tr.values())))
    out["p_base"] = "%s to %s" % (sci(min(t["p_base"] for t in tr.values())),
                                  sci(max(t["p_base"] for t in tr.values())))

    rows = list(csv.DictReader(open(os.path.join(C.DATA, "base_pressure_log.csv"))))
    seen = collections.defaultdict(set)
    for r in rows:
        seen[r["chamber"]].add(r["pumpdown"])
    counts = [len(v) for v in seen.values()]
    words = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight",
             9: "Nine", 10: "Ten"}
    out["pumpdowns"] = "%s to %s" % (words[min(counts)], words[max(counts)].lower())
    out["pumpdown_h"] = span([float(r["pumpdown_h"]) for r in rows], "%g")

    # the shop air over the period the log covers, not over the whole climate file: the explanation is
    # describing the conditions the records were taken in
    lo_date, hi_date = min(r["date"] for r in rows), max(r["date"] for r in rows)
    clim = [r for r in csv.DictReader(open(os.path.join(C.DATA, "shop_climate.csv")))
            if lo_date <= r["date"] <= hi_date]
    temps = [(float(r["air_temp_c"]), r["date"]) for r in clim]
    hot, cold = max(temps), min(temps)
    out["climate"] = ("%.0f C in %s to %.0f C in %s"
                      % (hot[0], MONTHS[int(hot[1].split("-")[1]) - 1],
                         cold[0], MONTHS[int(cold[1].split("-")[1]) - 1]))
    out["log_period"] = "%s to %s" % (lo_date, hi_date)

    # the repeatability the records are generated with, as a percentage
    sys.path.insert(0, os.path.join(C.TASK, "authoring", "provenance"))
    import build as B
    out["read_noise_pct"] = "%.1f" % (100 * B.READ_NOISE)

    print("Ranges of the shipped fleet, computed from the sealed definition and the built records")
    print("=" * 86)
    print("")
    for k, v in out.items():
        print("%s: %s" % (k, v))
    print("")
    print("every figure the difficulty explanation quotes about the fleet is above")
    C.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
