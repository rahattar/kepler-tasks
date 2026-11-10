"""Hedging. The gate is all 12 joints, so no split of joints between two answers to a choice can pass: the joints given
the wrong answer fail. Within a joint, a mean interference that is right under both answers to a choice exists where
the window the wrong reading computes (with the true friction law and everything else right) overlaps the true one.

    python3 authoring/evidence/hedge_study.py > authoring/evidence/hedge_study.txt
"""
import common as C

S = C.S
TRUE_STEEL_270 = S.cte("steel", 270) * 1e6


def oracle_mu(j, p):
    key = {"steel": "steel", "ductile iron": "GJS", "tin bronze CuSn12": "CuSn12", "aluminium AlSi10Mg": "AlSi10Mg"}[j["mat"]]
    return S.MU50[(key, j["prep"])] * (max(p, 1.0) / 50.0) ** (-S.KF)


CHOICES = [
    ("hub stress at rest only", dict(running_stress=False)),
    ("thermal change in running as a loss only", dict(clip_gain=True)),
    ("smoothing not deducted", dict(smooth=False)),
    ("steel expansion from the 20-100 C table", dict(table=True)),
    ("steel expansion 13.0 (handbook)", dict(assumed=13.0e-6)),
    ("J10 shaft solid", dict(log=("J07", "J11"))),
    ("J07 oiled", dict(log=("J10", "J11"))),
    ("J11 at 55 kW torque", dict(log=("J07", "J10"))),
]


def agent_window(k, kw):
    log = kw.get("log", ("J07", "J10", "J11"))
    mats, J = C.load(log)
    A = C.Agent(mats, J, None if kw.get("table") else TRUE_STEEL_270 * 1e-6,
                kw.get("smooth", True), kw.get("running_stress", True), kw.get("clip_gain", False), True,
                kw.get("assumed"), 270)
    j = J[k]
    return [m for m in range(1, 1500) if A.torque_ok(j, m, oracle_mu) and A.stress_ok(j, m) and A.clear_ok(j, m, j["Tlim"])]


def main():
    truth = {k: S.fit_window(k) for k in C.IDS}
    base = {k: agent_window(k, {}) for k in C.IDS}
    print("the model with every choice right reproduces the true window to within %d um at either end" % max(
        max(abs(base[k][0] - truth[k][0]), abs(base[k][-1] - truth[k][-1])) for k in C.IDS))
    print()
    print("choice | joints whose window moves | joints with no interference right under both answers")
    for name, kw in CHOICES:
        moved, nohedge = [], []
        for k in C.IDS:
            W = agent_window(k, kw)
            if W != base[k]:
                moved.append(k)
                if not set(W) & set(truth[k]):
                    nohedge.append(k)
        print("%-42s | %-28s | %s" % (name, " ".join(moved) or "-", " ".join(nohedge) or "-"))


if __name__ == "__main__":
    main()
