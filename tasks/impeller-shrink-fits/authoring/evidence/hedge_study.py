"""Hedging. The gate is all 8 parts, so no split of parts between two answers to a choice can pass. Within a part, a
bore that is right under both answers to a choice exists where the window the wrong reading computes (with the true
mean expansions and everything else right) overlaps the true one.

    python3 authoring/evidence/hedge_study.py > authoring/evidence/hedge_study.txt
"""
import common as C

S = C.S
TRUE = {"FV520B": (375, S.cte("FV520B", 375)), "Ti-6Al-4V": (285, S.cte("Ti64", 285)),
        "42CrMo4": (250, S.cte("42CrMo4", 250)), "26NiCrMoV14-5": (190, S.cte("rotor", 190))}
LOW = dict(TRUE, **{"FV520B": (240, S.cte("FV520B", 240))})
NO_ROTOR = {k: v for k, v in TRUE.items() if k != "26NiCrMoV14-5"}
NO_CR = {k: v for k, v in TRUE.items() if k != "42CrMo4"}
NO_TI = {k: v for k, v in TRUE.items() if k != "Ti-6Al-4V"}

CHOICES = [
    ("seats taken as at 20 C", dict(bay=False)),
    ("clearance against the seat at 20 C", dict(bay_clear=False)),
    ("trip at 105 %", dict(trip=1.05)),
    ("maintenance log not applied", dict(use_log=False)),
    ("seat growth at speed not credited", dict(seat_growth=False)),
    ("micrometer error not applied", dict(mic=False)),
    ("S4's spin test taken as at MCS", dict(spin=False)),
    ("20-100 C table for every material", dict(meas={}, use_mill=False)),
    ("the rotor steel from the 20-100 C table", dict(meas=NO_ROTOR)),
    ("42CrMo4 from the 20-100 C table", dict(meas=NO_CR, use_mill=False)),
    ("Ti-6Al-4V from the 20-100 C table", dict(meas=NO_TI)),
    ("FV520B extrapolated from 240 C", dict(meas=LOW)),
    ("the 375 C FV520B value used flat", dict(flat=True)),
]


def windows(kw):
    mats, P, Cc = C.solve.load(C.DATA, kw.get("use_log", True), kw.get("mic", True), kw.get("spin", True))
    if "trip" in kw:
        Cc["trip"] = kw["trip"]
    A = C.Agent(mats, P, Cc, kw.get("bay", True), kw.get("bay_clear", True), kw.get("seat_growth", True), kw.get("flat", False),
                None, kw.get("use_mill", True))
    for m, (T, a) in kw.get("meas", TRUE).items():
        A.meas[m] = (T, a)
    out = {}
    for k, j in P.items():
        W = [um for um in range(1, 700) if A.ret_ok(j, um) and A.stress_ok(j, um) and A.clear_ok(j, um, j["Tlim"])]
        out[k] = {round(A.seat20(j) - um * 1e-3, 3) for um in W}
    return out


def main():
    truth = {k: {round(S.PARTS[k]["seat"] - um * 1e-3, 3) for um in S.window(k)} for k in C.IDS}
    base = windows({})
    print("the model with every choice right reproduces every true window to within %d um" % max(
        len(base[k] ^ truth[k]) for k in C.IDS))
    print()
    print("choice | parts whose window moves | parts with no bore right under both answers")
    for name, kw in CHOICES:
        W = windows(kw)
        moved = [k for k in C.IDS if W[k] != base[k]]
        nohedge = [k for k in moved if not (W[k] & truth[k])]
        print("%-38s | %-26s | %s" % (name, " ".join(moved) or "-", " ".join(nohedge) or "-"))


if __name__ == "__main__":
    main()
