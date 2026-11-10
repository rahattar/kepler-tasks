"""Hedge study: can a selection that leaves a choice unresolved pass by hedging it?

    python3 authoring/evidence/hedge_study.py > authoring/evidence/hedge_study.txt

The selection is accepted only with all 12 brakes right, so a hedge cannot split hoists between two answers to a
choice: whichever answer is true, the hoists given the other one fail. What remains is a hedge within a hoist: a
size and setting that meets every requirement under both answers, so that the choice need not be resolved. For each
choice (A, the right reading, against B, a tempting wrong one), the reference's model is run under A and under B
with the reference's reports, and on every hoist whose selection the choice affects the best common selection (the
largest smaller margin of the two models) is found. If there is none on some hoist, the choice has to be resolved.
Where there is one, its verdict under the sealed definition is shown.

The friction of lining O2 near 200 C, which decides H05, is a choice of a different kind: a plan without a test there
knows the curve at its tested temperatures and not the height of what lies between. Its hedge is a selection that
meets every requirement for every height of the O2 curve between the tests at 160 and 260 C, from a straight line to
a peak of 1.35 times the friction at 20 C.
"""
import numpy as np

import common as C
import solve as R
from common import F

REQ = R.REQ


def worst_by_size(M, h, **flags):
    out = {}
    with C.physics(**flags):
        for size in M.cat:
            r = R.margins(M, h, size)
            w = np.min([r[k] for k in REQ], axis=0)
            w = np.where(np.maximum(r["Tp"], r["Tend"]) <= M.top(M.cat[size]["lining"]) + R.REACH, w, -np.inf)
            out[size] = w
    return out


def common_pick(wa, wb):
    best = None
    for size in wa:
        j = np.minimum(wa[size], wb[size])
        i = int(np.argmax(j))
        if best is None or j[i] > best[0]:
            best = (float(j[i]), size, int(R.SETTINGS[i]))
    return best


def solo_pick(w):
    best = None
    for size, v in w.items():
        i = int(np.argmax(v))
        if best is None or v[i] > best[0]:
            best = (float(v[i]), size, int(R.SETTINGS[i]))
    return best


def study(name, MA, HA, MB, HB, fa=None, fb=None):
    fa, fb = fa or {}, fb or {}
    lines, blocked, passes = [], [], 0
    for hid in C.IDS:
        wa = worst_by_size(MA, HA[hid], **fa)
        wb = worst_by_size(MB, HB[hid], **fb)
        pa, pb = solo_pick(wa), solo_pick(wb)
        if (pa[1], pa[2]) == (pb[1], pb[2]):
            continue
        c = common_pick(wa, wb)
        if c[0] < 0:
            blocked.append(hid)
            lines.append("    %s: A picks %s/%d, B picks %s/%d; no size and setting meets both (best %+.3f)" %
                         (hid, pa[1], pa[2], pb[1], pb[2], c[0]))
        else:
            tm = C.truth_margin(hid, c[1], c[2])
            passes += tm >= 0
            lines.append("    %s: A picks %s/%d, B picks %s/%d; common %s/%d (both models %+.3f), true margin %+.3f" %
                         (hid, pa[1], pa[2], pb[1], pb[2], c[1], c[2], c[0], tm))
    print(name)
    print("\n".join(lines) if lines else "    no hoist's selection changes")
    if blocked:
        print("  => no hedge: the choice must be resolved (%s)\n" % " ".join(blocked))
    elif lines:
        print("  => a common selection exists on every affected hoist: a sensitivity the windows absorb\n")
    else:
        print()


class Peak(R.Model):
    """O2 known at the tested temperatures; between 160 and 260 C a bump of chosen height on the straight line"""
    height = 1.0

    def ratio(self, T, lining):
        y = super().ratio(T, lining)
        if lining != "O2":
            return y
        x, v = self.curve["O2"]
        base = np.interp(T, x, v)
        bump = np.exp(-((np.asarray(T, float) - 200.0) / 28.0) ** 2)
        line200 = np.interp(200.0, x, v)
        return base + (self.height - line200) * bump * ((np.asarray(T, float) > 160) & (np.asarray(T, float) < 260))


def main():
    print(__doc__.split("\n\n")[0].strip())
    print("Shipped scenario, laboratory seed %d; gate 12 of 12.\n" % C.SEED)
    tests = C.lab(C.REF_PLAN)
    M = C.model(tests)
    H = C.H0
    for name, miss in (("H05 re-reeved to 2 falls (A) or as the register shows (B)", ("reeve",)),
                       ("inverter retrofits on H04, H08, H12 (A) or contactor control (B)", ("inverter",)),
                       ("fast lowering on H04 and H08 (A) or not (B)", ("fast",)),
                       ("two-speed hoists' working stops from slow speed (A) or full speed (B)", ("twospeed",)),
                       ("contactor lowering above synchronous speed (A) or at rated speed (B)", ("lower_speed",))):
        study(name, M, H, M, C.hoists(miss=miss))
    study("engagement time from the test (A) or the catalogue's at every setting (B)", M, H,
          C.model(tests, engagement="catalogue"), H)
    for name, flags in (("holding without (A) or with (B) the gear's efficiency", dict(hold_eff=True)),
                        ("deceleration hoisting the rated load (A) or with the empty hook (B)", dict(decel_case="empty")),
                        ("deceleration at the highest torque reached (A) or at the duty temperature (B)", dict(decel_T="duty")),
                        ("duty temperature the peak after a stop (A) or the time-average (B)", dict(duty_T="mean")),
                        ("backdriving efficiency 2 - 1/eta (A) or eta (B)", dict(backdrive="eta"))):
        study(name, M, H, M, H, fb=flags)

    # O2 near 200 C untested: tests at 160 and 260 only (and the rest of the reference plan)
    plan = [t for t in C.REF_PLAN if t != F(200, "O2")] + [F(110)]
    gap = C.lab(plan)
    heights = np.round(np.arange(1.10, 1.351, 0.05), 2)
    models = []
    for ht in heights:
        Mh = C.model(gap, cls=Peak)
        Mh.height = ht
        models.append(Mh)
    base = C.model(gap)
    print("O2 near 200 C untested (tests at 160 and 260 C): a selection meeting every requirement for every O2 peak "
          "height from %.2f to %.2f" % (heights[0], heights[-1]))
    blocked = []
    for hid in C.IDS:
        ws = [worst_by_size(Mh, H[hid]) for Mh in models]
        w0 = worst_by_size(base, H[hid])
        joint = {s: np.min([w[s] for w in ws] + [w0[s]], axis=0) for s in ws[0]}
        c = solo_pick(joint)
        p0 = solo_pick(w0)
        if c[0] < 0:
            blocked.append(hid)
            print("    %s: straight line picks %s/%d; no size and setting meets every height (best %+.3f)" % (hid, p0[1], p0[2], c[0]))
        elif (c[1], c[2]) != (p0[1], p0[2]):
            print("    %s: common %s/%d (all heights %+.3f), true margin %+.3f" % (hid, c[1], c[2], c[0], C.truth_margin(hid, c[1], c[2])))
    print("  => %s\n" % ("no hedge: H05 needs O2's friction near 200 C measured (%s)" % " ".join(blocked) if blocked
                         else "a common selection exists"))
    print("Across hoists no hedge passes: the gate is all 12, so any split of hoists between two answers loses the "
          "hoists given the wrong one.")


if __name__ == "__main__":
    main()
