"""Correct side of the 0.3 % bound: the correct program (solution/gtperf.py) with other sound choices, one at a time,
graded on the hidden record sets.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import common as C

VARIANTS = {
    "last qualifying 30-minute period of each run": (
        "    for i in range(len(x) - WINDOW + 1):\n        if ok[i:i + WINDOW].all()",
        "    for i in reversed(range(len(x) - WINDOW + 1)):\n        if ok[i:i + WINDOW].all()"),
    "run window taken from the start minute inclusive": (
        "x = d[(d.index > se[\"start\"]) & (d.index <= se[\"end\"])]",
        "x = d[(d.index >= se[\"start\"]) & (d.index <= se[\"end\"])]"),
    "LHV of the day's mean composition instead of the mean of the samples' LHVs": (
        "    lhv = float(np.mean([lhv_kj_kg(r) for _, r in gas[same_day].iterrows()]))",
        "    lhv = float(lhv_kj_kg(gas[same_day].drop(columns=[\"sample_time\"]).mean()))"),
    "power factor from the mean of the minute power factors": (
        "        pf = abs(P) / np.hypot(P, Qr)",
        "        pf = float((d.loc[win].gen_mw_jt001.abs() / np.hypot(d.loc[win].gen_mw_jt001, d.loc[win].gen_mvar_jt001)).mean())"),
    "rest taken as zero generator frequency (includes the coast-down)": (
        "    rest = d.speed_pct < AT_REST", "    rest = d.freq_hz < 0.5"),
    "rest taken as rotor speed below 0.5 %": (
        "    rest = d.speed_pct < AT_REST", "    rest = d.speed_pct < 0.5"),
    "fuel meter zero from rest minutes with no packing flow (mean of readings below 0.1 kg/s)": (
        "        d[\"m_fuel\"] = d.m_fuel - d.m_fuel[rest].median()",
        "        d[\"m_fuel\"] = d.m_fuel - d.m_fuel[rest & (d.m_fuel.abs() < 0.1)].mean()"),
    "rest minutes only 15 or more after a stop and 5 or more before a start": (
        "    rest = d.speed_pct < AT_REST",
        "    rest = (d.speed_pct < AT_REST).rolling(16, min_periods=1).min().astype(bool) & "
        "(d.speed_pct < AT_REST)[::-1].rolling(6, min_periods=1).min()[::-1].astype(bool)"),
    "frozen RTD found from the spread of its readings during the runs (max - min below 0.05 K)": (
        "    rtd = rtd.loc[:, rtd.std() > FROZEN]",
        "    rtd = rtd.loc[:, (rtd[d.speed_pct > 99].max() - rtd[d.speed_pct > 99].min()) > 0.05]"),
}

if __name__ == "__main__":
    base = open(C.SOLUTION).read()
    print("Largest miss over the hidden record sets (percent); the bound is 0.3 %.\n")
    worst = 0.0
    n, w, _ = C.summary(C.grade_text(base))
    print("%-76s %d fail, largest %.3f %%" % ("reference", n, w))
    for name, (old, new) in VARIANTS.items():
        assert base.count(old) == 1, name
        n, w, _ = C.summary(C.grade_text(base.replace(old, new)))
        worst = max(worst, w)
        print("%-76s %d fail, largest %.3f %%" % (name, n, w))
    print("\nLargest miss over all variants: %.3f %%" % worst)
