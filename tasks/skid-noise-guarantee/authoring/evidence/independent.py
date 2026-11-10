"""A second solution, written separately from solution/solve.py, with its own code, its own reading of the documents
and its own choices.

    python3 authoring/evidence/independent.py > authoring/evidence/independent.txt

It works in mean-square ratios rather than decibels wherever it can, reads the tables with pandas, joins the survey to
the position table on the position and keeps the position table's machine, picks out the machines that were changed
after the survey by excluding the routine entries of the log (filters, oil, samples, readings, traps, strainers,
grease) rather than by looking for the words that name a change, finds the certified insertion loss in the register
by looking for the words rather than for the pattern of figures, subtracts the background of P1 from the room check rather than a mean of the quiet positions, measures each
configuration difference at the last valid position of the machine's array instead of the first, and
decides the measurement surface from the wall clearance and the median radius of the array. The levels it reports are
rounded to 0.1 dB, as the sheet is. It is graded on the shipped seed and on the laboratory seeds 7101-7120 with the
in-process instrument.
"""
import re

import numpy as np
import pandas as pd

import common as C

D = C.DATA
LAB = C.LABEL
ROUTINE = r"filter|oil|sample|readings|trap|strainer|grease|regreased|lamp|relamped|marking|handrail|extinguisher"


def documents():
    std = open(D + "/docs/standard.md").read()
    room = open(D + "/docs/room_report.md").read()
    cert = open(D + "/docs/meter_certificates.md").read()

    def row(doc, tag):
        m = re.search(r"^\| %s[^|]*\|(.+)\|\s*$" % tag, doc, re.M)
        return [float(x) for x in m.group(1).split("|")]

    corr = {}
    for name, cells in re.findall(r"^\| (M-\d+) \([^)]*\) \|(.+)\|\s*$", cert, re.M):
        corr[name] = pd.Series([float(x) for x in cells.split("|")], index=LAB)
    return dict(aw=pd.Series(row(std, re.escape("Aw (dB)")), index=LAB),
                corr=corr,
                t_report=pd.Series(row(room, re.escape("T (s)")), index=LAB),
                vol=float(re.search(r"volume of (\d+) m3", room).group(1)),
                sab=float(re.search(r"A = ([\d.]+) V / T", std).group(1)),
                clear=float(re.search(r"standing ([\d.]+) m or more", std).group(1)),
                rss_lw=pd.Series(row(open(D + "/docs/room_check.md").read(), re.escape("Lw (dB)")), index=LAB),
                rss_r=float(re.search(r"hemisphere of ([\d.]+) m",
                                      open(D + "/docs/room_check.md").read()).group(1)),
                margin=float(re.search(r"less than (\d+) dB in any band", std).group(1)),
                exp=float(re.search(r"(\d+) lg \(n_rated / n\)", std).group(1)))


def tables():
    cols = ["lp_%s" % k for k in LAB]
    mach = pd.read_csv(D + "/machines.csv").set_index("machine")
    pos = pd.read_csv(D + "/positions.csv").set_index("position")
    sur = pd.read_csv(D + "/survey_levels.csv").drop(columns=["machine"]).set_index("position")
    bg = pd.read_csv(D + "/background_levels.csv").set_index("position")
    sur = pos.join(sur)                       # the position table's machine column wins
    sur.columns = [c.replace("lp_", "") if c in cols else c for c in sur.columns]
    bg.columns = [c.replace("lp_", "") if c in cols else c for c in bg.columns]
    log = pd.read_csv(D + "/maintenance_log.csv").fillna({"machine": ""})
    return mach, sur, bg, log


def run(seed):
    doc = documents()
    mach, sur, bg, log = tables()
    survey_day = log.loc[log.entry.str.contains("acceptance survey"), "date"].min()
    after = log[(log.machine != "") & (log.date > survey_day)]
    moved = set(after.loc[~after.entry.str.lower().str.contains(ROUTINE), "machine"])
    lab = C.Lab(seed)
    # the absorption area from the survey's room check: the certified source against its own measured level
    rss = pd.read_csv(D + "/rss_levels.csv").set_index("position")
    rss.columns = [c.replace("lp_", "") for c in rss.columns]
    quiet = bg.loc["P1", LAB] + doc["corr"]["M-2"]
    rlev = 10.0 ** (0.1 * (rss[LAB] + doc["corr"][rss.meter.iloc[0]])) - 10.0 ** (0.1 * quiet)
    lp_rss = 10.0 * np.log10(rlev.mean(axis=0))
    absorption = 4.0 / (10.0 ** (0.1 * (lp_rss - doc["rss_lw"])) - 1.0 / (2.0 * np.pi * doc["rss_r"] ** 2))

    out, extra = {}, {}
    for m in mach.index:
        mine = sur[sur.machine == m]
        radius = float(mine.radius_m.median())
        speed = float(mine.speed_rpm.iloc[0])
        # every level with its own instrument's certificate, as a mean-square ratio
        on = 10.0 ** (0.1 * (mine[LAB] + pd.DataFrame(
            [doc["corr"][t] for t in mine.meter], index=mine.index)))
        off = 10.0 ** (0.1 * (bg.loc[mine.index, LAB] + pd.DataFrame(
            [doc["corr"][t] for t in bg.loc[mine.index, "meter"]], index=mine.index)))
        alone = on - off
        keep = mine.index[(np.abs(mine.radius_m - radius) < 1e-9)
                          & ((10.0 * np.log10(on / off)).min(axis=1) >= doc["margin"])]
        area = (2.0 if mach.loc[m, "wall_clearance_m"] >= doc["clear"] else 1.0) * np.pi * radius ** 2
        lp = 10.0 * np.log10(alone.loc[keep].mean(axis=0))
        lw = lp + 10.0 * np.log10(area) - 10.0 * np.log10(1.0 + 4.0 * area / absorption)
        if speed != mach.loc[m, "rated_speed_rpm"]:
            lw = lw + doc["exp"] * np.log10(mach.loc[m, "rated_speed_rpm"] / speed)
            extra[m] = "referred from %.0f rpm" % speed
        elif m in moved and isinstance(mach.loc[m, "note"], str) and "insertion loss" in mach.loc[m, "note"]:
            # the register certifies what was fitted to this one, so no reading is needed for it
            il = pd.Series([float(x) for x in re.search(r"band ([\d./]+) dB",
                                                        mach.loc[m, "note"]).group(1).split("/")], index=LAB)
            lw = lw - il
            extra[m] = "certified insertion loss from the register"
        elif m in moved:
            p = keep[-1]
            now = 10.0 ** (0.1 * pd.Series(lab.slm(p, m.lower())))
            then = alone.loc[p]
            lw = lw + 10.0 * np.log10((now - off.loc[p]) / then)
            extra[m] = "difference measured at %s" % p
        out[m] = {k: round(float(lw[k]), 1) for k in LAB}
        out[m]["A"] = round(float(10.0 * np.log10((10.0 ** (0.1 * (lw + doc["aw"]))).sum())), 1)
    return out, lab.log, extra


def main():
    total = len(C.IDS) * len(C.KEYS)
    sheet, log, extra = run(C.SEED)
    n, err, _ = C.grade(sheet)
    print("shipped seed %d: readings %s" % (C.SEED, log))
    for m in C.IDS:
        print("%s %s  %s  worst %+.2f dB  (%s)" % (
            m, " ".join("%6.1f" % sheet[m][k] for k in C.KEYS),
            "ok " if all(abs(err[m][k]) <= C.S.TOL for k in C.KEYS) else "BAD",
            max(err[m].values(), key=abs), extra.get(m, "as surveyed")))
    print("right %d of %d; worst error %+.2f dB" % (n, total, max(
        (err[m][k] for m in C.IDS for k in C.KEYS), key=abs)))
    ns = [C.grade(run(s)[0])[0] for s in C.SEEDS]
    print("seeds 7101-7120: all right on %d of 20 (right counts %s)" % (sum(x == total for x in ns), ns))


if __name__ == "__main__":
    main()
