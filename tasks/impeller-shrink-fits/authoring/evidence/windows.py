"""Each part's window: the whole-micrometre mean interferences (true seat at 20 C less the bore) that meet RS-3 with
the oven at the heating limit, what bounds it, and the expansion facts behind the clearance-limited ones.

    python3 authoring/evidence/windows.py > authoring/evidence/windows.txt
"""
import common as C

S = C.S


def main():
    print("part  description           material  window um  width  top set by                 seat 20 C  seat in bay  oven limit C")
    for k in C.IDS:
        j = S.PARTS[k]
        W = S.window(k)
        lo, hi = W[0], W[-1]
        assert W == list(range(lo, hi + 1))
        a = S.margins(k, round(j["seat"] - (hi + 1) * 1e-3, 3), j["Tlim"])
        top = "clearance at %d C" % j["Tlim"] if a["clear"] < 0 and a["stress"] >= 0 else "hub stress at trip"
        print("%-5s %-21s %-9s %4d-%-4d   %3d   %-26s %.3f    %.4f     %d" % (
            k, j["desc"], j["mat"], lo, hi, hi - lo + 1, top, j["seat"], S.seat_bay(j), j["Tlim"]))
    print()
    print("Every window is one contiguous run of whole micrometres; the bore is the seat at 20 C less the interference.")
    print("Mean expansion from 20 C (um/m K):")
    for m, Ts in (("FV520B", (100, 260, 375)), ("Ti64", (100, 285)), ("42CrMo4", (100, 190, 220)), ("rotor", (28.5, 100))):
        print("  %-8s %s" % (m, ", ".join("%.2f to %g C" % (S.cte(m, T) * 1e6, T) for T in Ts)))
    print("Trip speed %.0f %% of MCS (the OEM sheet says 105 %%); the overhaul bay is at %.1f C." % (S.TRIP * 100, S.T_BAY))
    for k in C.IDS:
        j = S.PARTS[k]
        st = S.states(j)[1]
        print("  %s in running at trip: interference change %+.1f um (thermal %+.1f, bore less seat growth %.1f); "
              "hoop stress %.0f MPa" % (k, st[1] * 1e3, S.thermal_change(j) * 1e3,
                                        (S.bore_growth(j, S.TRIP) - S.seat_growth(j, S.TRIP)) * 1e3, st[2]))


if __name__ == "__main__":
    main()
