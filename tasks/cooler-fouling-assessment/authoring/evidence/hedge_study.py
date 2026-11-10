"""Hedging. Two of the ten units turn on a reading a solver has to take: how the ribbed tubes' film gain follows
their friction gain (E3, E7), and what the rebuilt bundle's wider baffle spacing does to its shell film (E5). Each
reading is settled by a document in /app/data/docs, and this study shows what each one is worth: the laws that fit
the single tested ribbed unit equally well, the figure each gives, and whether one number could satisfy two
readings at once. The requirement itself is stated in no file the solver can read, so a split answer cannot be
aimed at it.

    python3 authoring/evidence/hedge_study.py > authoring/evidence/hedge_study.txt
"""
import numpy as np
import methods as M

hx = M.hx
P = M.REF_PLAN                       # one C-310 of the pair, E9's open sheet, and the ribbed unit E8
RIB = ["E3", "E7"]


def errors(**kw):
    _, _, _, res = M.grade(M.estimate(P, **kw)[0])
    return {u: res[u][0] for u in hx.UNITS}


def main():
    print("requirement %.3f m2K/kW (stated in no file the solver can read)\n" % M.TOL)

    # what the one tested ribbed unit gives: its friction gain from the tube-side dp, its film gain from the clean test
    t = M.test_result("E8", P.index("E8") + 1)
    ft, fs = t["after_cleaning_flows"]
    st, ss = M.unit_scale("E8", "common")
    ht_old, hs, rw = M.design_split(M.MODEL_OF["E8"], ft, fs, st, ss)
    meas = [(1 / (1 / t["after_cleaning"] - 1 / hs - rw) / ht_old, M.dp_ratio("E8"))]
    eh0, ef0 = meas[0]
    print("tested ribbed unit E8: friction gain %.3f from its tube-side dp (sealed %.2f), film gain %.3f measured\n"
          "from its clean test; the retube note's relation gives K = %.3f (sealed %.2f)"
          % (ef0, hx.ENH["E8"], eh0, (eh0 - 1) / (ef0 - 1), hx.K_EH))
    print("\nribbed film gain at the untested units, from laws that all reproduce E8's measured point")
    print("  %-34s %-12s %-12s %-10s %-10s" % ("law", "E3 gain", "E7 gain", "E3 error", "E7 error"))
    err = {}
    for law in M.LAWS + ("midpoint",):
        e = errors(law=law)
        err[law] = e
        g = [M.gain_law(law, meas, M.dp_ratio(u)) for u in RIB]
        name = {"stated": "1 + K (f - 1)   [retube note]", "power": "f ** n", "root": "1 + a sqrt(f - 1)",
                "saturating": "1 + a (1 - exp(-(f - 1)))", "midpoint": "middle of the four above (hedge)"}[law]
        print("  %-34s %-12.3f %-12.3f %+.3f     %+.3f" % (name, g[0], g[1], e["E3"], e["E7"]))
    print("  %-34s %-12.3f %-12.3f" % ("sealed definition", 1 + hx.K_EH * (hx.ENH["E3"] - 1),
                                       1 + hx.K_EH * (hx.ENH["E7"] - 1)))
    for u in RIB:
        v = [err[l][u] for l in M.LAWS]
        print("  %s: the four laws span %.3f m2K/kW; worst of them %+.3f; the note's law %+.3f"
              % (u, max(v) - min(v), max(v, key=abs), err["stated"][u]))

    print("\nE5's replacement bundle, baffle spacing 300 -> 400 mm")
    e_doc, e_flat = errors(e5="baffle"), errors(e5="2025")
    mid = {u: (e_doc[u] + e_flat[u]) / 2 for u in hx.UNITS}
    print("  %-56s error %+.3f" % ("crossflow velocity inversely with the spacing [design sheet]", e_doc["E5"]))
    print("  %-56s error %+.3f" % ("2025 test used as it stands", e_flat["E5"]))
    print("  %-56s error %+.3f" % ("middle of the two (hedge)", mid["E5"]))

    print("\nthe new C-310 pair, one vendor rating for both")
    e_twin, e_ds = errors(newfill="twin"), errors(newfill="vendor")
    other = [u for u in hx.NEW if u not in P][0]
    print("  %-56s error %+.3f" % ("the tested twin's measured factor [datasheet note]", e_twin[other]))
    print("  %-56s error %+.3f" % ("the shared datasheet as it stands", e_ds[other]))
    print("  %-56s error %+.3f" % ("middle of the two (hedge)", (e_twin[other] + e_ds[other]) / 2))

    print("\nwhether one number can satisfy two readings at once (|reading A - reading B| against 2 x %.2f)" % M.TOL)
    pairs = [("E3", "stated", "saturating"), ("E7", "stated", "saturating"), ("E7", "stated", "power"),
             ("E7", "stated", "root")]
    for u, a, b in pairs:
        d = abs(err[a][u] - err[b][u])
        print("  %-3s %-11s vs %-11s gap %.3f -> %s" % (u, a, b, d, "a split answer satisfies both" if d <= 2 * M.TOL
                                                        else "no number satisfies both"))
    dn = abs(e_twin[other] - e_ds[other])
    print("  %-3s %-11s vs %-11s gap %.3f -> %s" % (other, "twin factor", "datasheet", dn,
                                                    "a split answer satisfies both" if dn <= 2 * M.TOL
                                                    else "no number satisfies both"))
    d5 = abs(e_doc["E5"] - e_flat["E5"])
    print("  %-3s %-11s vs %-11s gap %.3f -> %s" % ("E5", "design sheet", "2025 flat", d5,
                                                    "a split answer satisfies both" if d5 <= 2 * M.TOL
                                                    else "no number satisfies both"))
    print("\nconclusion: each reading is settled in the documents, not left to the solver's judgement. The retube\n"
          "note ties the film gain to the friction gain through one coefficient of the rib form, so the single\n"
          "tested ribbed unit fixes that coefficient and every other ribbed unit follows from its own dp; the\n"
          "design sheet ties the shell-side crossflow velocity to the baffle spacing, so the rebuilt bundle's\n"
          "shell film follows from its new spacing. Read that way there is one figure per unit, and it is the one\n"
          "the records support. The gaps between readings are under 2 x the requirement, so a number split\n"
          "between two readings could in principle satisfy both: that is why the requirement appears in no file\n"
          "the solver can read, and a split answer cannot be aimed at a band it cannot see.")


if __name__ == "__main__":
    main()
