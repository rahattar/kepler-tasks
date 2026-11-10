"""Each joint's window: the whole-micrometre mean interferences that meet ST-9 with the hub at its heating limit,
what bounds it, and the oven temperatures that work at its ends.

    python3 authoring/evidence/windows.py > authoring/evidence/windows.txt
"""
import common as C

S = C.S


def main():
    print("joint  part                    hub       prep   window um  width  bottom set by     top set by             "
          "p at bottom MPa  oven C at top (limit)")
    for k in C.IDS:
        j = S.JOINTS[k]
        W = S.fit_window(k)
        lo, hi = W[0], W[-1]
        assert W == list(range(lo, hi + 1))
        # what sets the bottom: the state whose torque fails just below
        dmin = (lo - 1) * 1e-3 - S.span(j["d"]) / 2
        caps = [(S.tcap(j, dmin - S.smoothing(j) + dd)[0], name) for name, dd, _ in S.states(j)]
        bottom = "torque " + min(caps)[1]
        a = S.margins(k, hi + 1, j["Tlim"])
        if a["clear"] < 0 and a["stress"] >= 0:
            top = "clearance at %d C" % j["Tlim"]
        else:
            dmax = (hi + 1) * 1e-3 + S.span(j["d"]) / 2
            st = [(S.vm_bore(j, S.pressure(j, dmax - S.smoothing(j) + dd), rot), name) for name, dd, rot in S.states(j)]
            top = "stress " + max(st)[1]
        print("%s    %-22s %-9s %-6s %4d-%-4d    %3d   %-17s %-22s %6.0f          %d (%d)" % (
            k, j["desc"], j["hub"], j["cond"], lo, hi, hi - lo + 1, bottom, top, S.margins(k, lo, j["Tlim"])["p"],
            S.t_need(k, hi), j["Tlim"]))
    print()
    print("Every window is one contiguous run of whole micrometres. Steel's mean expansion from 20 C is %.2f (to 100 C), "
          "%.2f (270 C) and %.2f (280 C) um/m K." % tuple(S.cte("steel", T) * 1e6 for T in (100, 270, 280)))
    print("In steady running J01 and J12 gain %.1f and %.1f um of interference (shaft hotter than hub); J02, J03 and "
          "J05 lose %.1f, %.1f and %.1f um." % tuple(-1e3 * (S.thermal_loss(S.JOINTS[k]) + S.centrifugal_loss(S.JOINTS[k]))
                                                    if k in ("J01", "J12") else 1e3 * (S.thermal_loss(S.JOINTS[k]) + S.centrifugal_loss(S.JOINTS[k]))
                                                    for k in ("J01", "J12", "J02", "J03", "J05")))


if __name__ == "__main__":
    main()
