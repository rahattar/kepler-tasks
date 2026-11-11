"""Answers made without doing the work: constants, and transcriptions of the shop's own inspection report. Each
feature is graded on its own, so these show what a sheet gets for free, and the gate is all 14.

    python3 null_baselines.py > null_baselines.txt
"""
import csv
import os
import re

import common as C


def shop_report():
    """The roundness and mean diameter the shop's software printed, as the inspection report gives them."""
    out = {}
    path = os.path.join(C.DATA, "docs", "inspection_report.md")
    for line in open(path):
        m = re.match(r"\|\s*([A-Z]{2}-\d+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|", line)
        if m:
            out[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    return out


def tally(name, ans):
    """Scored by the verifier's own module, on a written sheet, like every other study here."""
    r = C.score(ans)
    feats = r["features"]
    right_f = sum(1 for f in C.ORDER if feats[f]["form_ok"])
    right_v = sum(1 for f in C.ORDER if feats[f]["verdict_ok"])
    print("  %-62s right %2d of %d (form %2d, sentence %2d)%s" % (
        name, r["npass"], len(C.ORDER), right_f, right_v, "  ACCEPTED" if r["accepted"] else ""))
    return r["npass"]


def sweep():
    """Every sheet that names one form figure and one sentence for all 14 features. The form figure is swept in
    0.05 um steps from 0 to 60, which is a fiftieth of the band, and each sheet is scored by the verifier. What
    matters is not that such a sheet fails - the gate is all 14 - but how many features it can pick up for
    free, because a feature a method-free sheet can earn is a feature that is not discriminating. The form
    errors of the features sharing any one sentence are spaced more than twice the band apart, so the most any
    constant sheet can reach is one; preflight.py keeps that spacing true."""
    best, where = 0, []
    for v in ("accept", "reject_size", "reject_form", "reject_both"):
        for i in range(0, 1201):
            form = i * 0.05
            r = C.score({f: (form, v) for f in C.ORDER})
            if r["npass"] > best:
                best, where = r["npass"], [(form, v, [f for f in C.ORDER if r["features"][f]["ok"]])]
            elif r["npass"] == best and best:
                where.append((form, v, [f for f in C.ORDER if r["features"][f]["ok"]]))
    pairs = [w for w in where if len(w[2]) > 1]
    print("\n  swept %d constant sheets through the verifier: the best of them picks up %d of %d features"
          % (4 * 1201, best, len(C.ORDER)))
    print("  one feature is the floor and cannot be helped: a sheet that happens to name a feature's own form\n"
          "  figure and its own sentence is right about that feature by luck, and every feature has such a\n"
          "  sheet. What matters is that no sheet reaches two: %s"
          % ("none does" if not pairs else "%d do, at %s" % (len(pairs), pairs[:3])))
    return best


def main():
    rep = shop_report()
    print("the sentence is one of four words, so a constant sentence gets whatever share of the bank happens to\n"
          "carry it; the true bank is %s\n" % ", ".join(
              "%s %d" % (v, sum(1 for f in C.ORDER if C.TRUTH[f]["verdict"] == v))
              for v in ("accept", "reject_size", "reject_form", "reject_both")))
    for v in ("accept", "reject_size", "reject_form", "reject_both"):
        tally("every feature %s, form 0" % v, {f: (0.0, v) for f in C.ORDER})
    tally("every feature accept, form taken as the drawing tolerance",
          {f: (float(C.DRAW[f]["form_tolerance_um"]), "accept") for f in C.ORDER})
    tally("the inspection report's roundness, every feature accept",
          {f: (rep[f][1], "accept") for f in C.ORDER})
    tally("the inspection report's roundness, sentenced on it and the report's mean diameter",
          report_sentence(rep))
    tally("the inspection report's roundness, sentenced on form alone",
          {f: (rep[f][1], "accept" if rep[f][1] <= float(C.DRAW[f]["form_tolerance_um"]) else "reject_form")
           for f in C.ORDER})
    best = sweep()
    assert best <= 1, "a constant sheet reaches %d features" % best
    print("\nno constant sentence and no transcription of the report passes; the gate is all %d." % len(C.ORDER))


def report_sentence(rep):
    """What the report alone says: its roundness against the form tolerance, its mean diameter against the size
    limits. Both of its figures are the software's defaults, which FM-7 does not use."""
    out = {}
    for f in C.ORDER:
        dia, rnd = rep[f]
        nom = float(C.REG[f]["nominal_mm"])
        dev = (dia - nom) * 1000.0
        lo, hi = float(C.DRAW[f]["size_lower_um"]), float(C.DRAW[f]["size_upper_um"])
        size_ok = lo <= dev <= hi
        form_ok = rnd <= float(C.DRAW[f]["form_tolerance_um"])
        out[f] = (rnd, {(True, True): "accept", (False, True): "reject_size",
                        (True, False): "reject_form", (False, False): "reject_both"}[(size_ok, form_ok)])
    return out


if __name__ == "__main__":
    main()
