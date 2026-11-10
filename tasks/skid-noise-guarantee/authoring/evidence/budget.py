"""Where each of the 27 values comes from: the hall, each machine's measurement surface and valid positions, the
environmental correction of each band, the correction that refers the survey to the machine as it stands, and the
sealed definition's own levels against the reference's.

    python3 authoring/evidence/budget.py > authoring/evidence/budget.txt
"""
import common as C

S = C.S
LAB = C.LABEL


def main():
    print("the hall: %.1f by %.1f by %.1f m, %.0f m3" % (S.ROOM["L"], S.ROOM["W"], S.ROOM["H"], S.ROOM["V"]))
    print("the survey ran over three days, one instrument a day; the sheet enters %s under the wrong machine"
          % ", ".join(sorted(S.MISLABEL, key=lambda p: int(p[1:]))))
    print("band                 %s" % "  ".join("%6s" % k for k in LAB))
    print("T as it is now (s)   %s" % "  ".join("%6.2f" % S.T60[b] for b in S.BANDS))
    print("T in the report (s)  %s   (with the ceiling panels the roof repair took down)" % "  ".join(
        "%6.2f" % S.T60_REPORT[b] for b in S.BANDS))
    print("A as it is now (m2)  %s" % "  ".join("%6.1f" % S.area(b) for b in S.BANDS))
    print("A weighting (dB)     %s" % "  ".join("%+6.1f" % S.AW[b] for b in S.BANDS))
    print("background (dB)      %s   (the hall away from the louvred wall)" % "  ".join(
        "%6.1f" % S.BG[b] for b in S.BANDS))
    print("the blower at P15,P16%s   (the adjacent bay, behind the louvres)" % "  ".join(
        "%6.1f" % S.BLOWER_NEAR[b] for b in S.BANDS))
    for name in ("M-2", "M-5", "M-9"):
        print("certificate of %-5s %s   (read %s)" % (
            name, "  ".join("%+6.1f" % S.METER[name][b] for b in S.BANDS), " ".join(S.METER_DAY[name])))
    print("a reading of a band level repeats to %.2f dB and a reverberation time to %.0f per cent, one standard "
          "deviation, as the standard states; the booking is %d readings." % (
              S.NOISE_SLM, 100 * S.NOISE_RT, S.BUDGET))
    print()
    ref, _ = C.solve_route()
    truth = S.truth()
    for m, j in S.MACHINES.items():
        good = [p for p in j["positions"] if S.POS[p]["valid"]]
        print("%s  %s" % (m, j["desc"]))
        print("  %s space, array at %.2f m (the register's nominal radius is %.1f m), surface %.2f m2, "
              "wall clearance %.1f m" % (j["space"], j["r"], S.NOMINAL_R, S.surface(j["space"], j["r"]),
                                         S.WALL[m]))
        print("  %d of %d positions valid: %s; dropped: %s" % (
            len(good), len(j["positions"]), " ".join(good),
            " ".join("%s (radius %.2f m, %s)" % (p, S.POS[p]["r"], S.POS[p]["note"] or "on the surface")
                     for p in j["positions"] if not S.POS[p]["valid"]) or "none"))
        print("  K2 (dB)            %s" % "  ".join("%6.2f" % S.k2(m, b) for b in S.BANDS))
        print("  read with %s" % S.meter_of(j["positions"][0]))
        if j["sdelta"]:
            print("  surveyed as it was before %s" % (
                "its access cover was refitted" if m == "C1" else "its intake silencer was installed"))
            print("  difference (dB)    %s" % "  ".join(
                "%+6.2f" % (S.lw(m, b) - S.lw(m, b, "survey")) for b in S.BANDS))
        elif j["survey_rpm"] != j["rated"]:
            print("  surveyed at %.0f rpm against its rated %.0f rpm: %+.2f dB in every band" % (
                j["survey_rpm"], j["rated"], S.speed_referral(m)))
        else:
            print("  surveyed at its rated %.0f rpm and nothing was done to it since: no referral" % j["rated"])
        print("  definition (dB)    %s   LwA %.2f (guarantee %.0f)" % (
            "  ".join("%6.2f" % truth[m][k] for k in LAB), truth[m]["A"], S.GUARANTEE[m]))
        print("  reference's error  %s   LwA %+.2f" % (
            "  ".join("%+6.2f" % (ref[m][k] - truth[m][k]) for k in LAB), ref[m]["A"] - truth[m]["A"]))
        print()
    n, err, (wm, wk, wv) = C.grade(ref)
    print("the reference gets %d of %d values inside the band of +/- %.1f dB; its worst is %s %s %+.2f dB." % (
        n, 3 * len(C.KEYS), S.TOL, wm, wk, wv))
    print("Each of the %d values is graded on its own and all of them are required." % (3 * len(C.KEYS)))


if __name__ == "__main__":
    main()
