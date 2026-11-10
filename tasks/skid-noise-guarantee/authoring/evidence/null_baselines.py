"""Answers made without the booking, and the values each gets right (free passes).

    python3 authoring/evidence/null_baselines.py > authoring/evidence/null_baselines.txt
"""
import math

import common as C

S = C.S
LAB = C.LABEL


def raw_reduction(t60=None, hemisphere=True, nominal=True, background=False, drop=False):
    """the survey read off as it stands: the energy average of the indicated levels over the positions, the
    measurement surface from the register's nominal radius in a half space, and the acoustic report's reverberation
    time"""
    t60 = t60 or S.T60_REPORT
    sheet = {}
    for m, j in S.MACHINES.items():
        pos = [p for p in j["positions"] if S.POS[p]["valid"]] if drop else j["positions"]
        r = S.NOMINAL_R if nominal else j["r"]
        area = (2.0 * math.pi if hemisphere else (2.0 * math.pi if j["space"] == "half" else math.pi)) * r * r
        out = {}
        for b in S.BANDS:
            k = S.LABEL[b]
            vals = []
            for p in pos:
                v = C.e(S.lp_total((m,), p, b, "survey") - S.METER[S.meter_of(p)][b])
                if background:
                    v = max(v - C.e(S.lp_background(p, b) - S.METER[S.meter_of(p)][b]), 1e-12)
                vals.append(v)
            lp = C.db(sum(vals) / len(vals))
            out[k] = lp + C.db(area) - C.db(1.0 + 4.0 * area / (S.SOUND_C * S.ROOM["V"] / t60[b]))
        out["A"] = C.db(sum(C.e(out[S.LABEL[b]] + S.AW[b]) for b in S.BANDS))
        sheet[m] = out
    return sheet


def flat(level):
    return {m: {k: level for k in C.KEYS} for m in C.IDS}


def with_offset(sheet, off):
    return {m: {k: v + off for k, v in sheet[m].items()} for m in C.IDS}


def guarantee_sheet():
    sheet = raw_reduction()
    for m in C.IDS:
        sheet[m]["A"] = S.GUARANTEE[m]
    return sheet


def lpa_sheet():
    """the survey's own A-weighted pressure column, read as if it were the sound power level"""
    sheet = raw_reduction()
    for m, j in S.MACHINES.items():
        vals = []
        for p in j["positions"]:
            vals.append(C.e(C.db(sum(C.e(S.lp_total((m,), p, b, "survey") - S.METER[S.meter_of(p)][b] + S.AW[b])
                                     for b in S.BANDS))))
        sheet[m]["A"] = C.db(sum(vals) / len(vals))
    return sheet


def line(name, sheet):
    n, err, _ = C.grade(sheet)
    right = ["%s %s" % (m, k) for m in C.IDS for k in C.KEYS if abs(err[m][k]) <= S.TOL]
    print("%-74s %2d of %d  right: %s" % (name, n, len(C.IDS) * len(C.KEYS), " ".join(right) or "-"))
    return right


def main():
    got = []
    got += line("the survey read off as it stands (nominal radius, half space, report's T, no corrections)",
                raw_reduction())
    got += line("the same, the background subtracted and the invalid positions dropped",
                raw_reduction(background=True, drop=True))
    got += line("the same again, with the true radius and quarter space for C3",
                raw_reduction(background=True, drop=True, hemisphere=False, nominal=False))
    got += line("the guaranteed A-weighted level as LwA, the survey read off for the bands", guarantee_sheet())
    got += line("the survey's own A-weighted pressure column as LwA", lpa_sheet())
    got += line("a flat 95.0 dB everywhere", flat(95.0))
    base = raw_reduction()
    best = max(((C.grade(with_offset(base, o / 10.0))[0], o / 10.0) for o in range(-100, 101)))
    got += line("the survey read off with the best single offset (%+.1f dB, chosen with the truth)" % best[1],
                with_offset(base, best[1]))
    print()
    print("values no answer above gets right: %s" % (" ".join(
        "%s %s" % (m, k) for m in C.IDS for k in C.KEYS if "%s %s" % (m, k) not in got) or "none"))
    print("the gate is all %d values, so none of these answers is accepted." % (len(C.IDS) * len(C.KEYS)))


if __name__ == "__main__":
    main()
