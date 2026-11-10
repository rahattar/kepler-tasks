"""Spread of correct methods, measured by the verifier. Each method is a complete program run through tests/grade.py
on the six hidden mains exactly as a submission. Each is run twice: as designed (with its margins), and with its
margins removed, so that its design is its own smallest vessel; the ratio of that to the true smallest vessel is the
method's own spread about the truth.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

DIV_SHIFT = ('                z[i] = np.interp(c, [c0, S["kx"], c1], [z0, zc, z1])\n',
             '                w = 1 - abs(c - S["kx"]) / ((c1 - S["kx"]) if c > S["kx"] else (S["kx"] - c0))\n'
             '                z[i] = min(S["z"][i] + (zc - np.interp(S["kx"], S["ch"], S["z"])) * w, zc)\n')
VARIANTS = [
    ("time step 0.01 s (not 0.02)", [("P = dict(dt=0.02, sections=[dict(L=S[\"L\"], D=S[\"D\"], a=S[\"a\"], f=f)], profile=(S[\"ch\"], z), Hs=S[\"ww\"], Ht=Ht,\n",
                                       "P = dict(dt=0.01, sections=[dict(L=S[\"L\"], D=S[\"D\"], a=S[\"a\"], f=f)], profile=(S[\"ch\"], z), Hs=S[\"ww\"], Ht=Ht,\n")]),
    ("seven reservoir levels (not three)", [('    levels = (S["BWL"], 0.5 * (S["BWL"] + S["TWL"]), S["TWL"])\n',
                                             '    levels = tuple(np.linspace(S["BWL"], S["TWL"], 7))\n')]),
    ("atmospheric head 10.33 m (not 10.2)", [("HB = 10.2      # atmospheric pressure head, m water\n", "HB = 10.33\n")]),
    ("diversion: drawing shape shifted to the chamber crown, tapered (not straight lines)", [DIV_SHIFT]),
]
T = C.truth(); PK = sorted(T)
print("Correct methods as complete programs through tests/grade.py (run as %s), six hidden mains; a design is right "
      "when it meets MS-SV clause 3 and is at most 1.15 of the smallest vessel.\n" % ("nobody" if C.AS_NOBODY else "the current user"))
print("columns: ratio of the design to the true smallest vessel for " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
rows = [("solution/surge.py (reference)", C.REFERENCE, C.REF_NO_MARGIN, []),
        ("independent.py (shares no code with the reference)", C.INDEPENDENT, C.IND_NO_MARGIN, [])]
rows += [("reference, " + n, C.REFERENCE, C.REF_NO_MARGIN, rep) for n, rep in VARIANTS]
lo_all, hi_all, own_lo, own_hi = 9, 0, 9, 0
for name, path, nomargin, rep in rows:
    for label, extra in (("as designed", []), ("no margins", nomargin)):
        prog = C.program(path, replace=rep + extra) if (rep or extra) else path
        r = C.verify(prog)
        rs = [r["packages"][p].get("ratio_to_smallest") or float("nan") for p in PK]
        cells = "  ".join("%5.3f%s" % (x, "" if r["packages"][p]["right"] else "*") for x, p in zip(rs, PK))
        print("%-86s %-11s wrong %d  %s" % (name, label, r["wrong"], cells))
        if label == "as designed":
            lo_all, hi_all = min(lo_all, min(rs)), max(hi_all, max(rs))
        else:
            own_lo, own_hi = min(own_lo, min(rs)), max(own_hi, max(rs))
print("\n* the main is wrong (with no margins, a ratio below 1 fails clause 3)")
print("as designed, every correct method: %.3f to %.3f of the smallest vessel (limit 1.15)" % (lo_all, hi_all))
print("each method's own smallest vessel: %.3f to %.3f of the true smallest" % (own_lo, own_hi))
