"""Defective routes, measured by the verifier: the reference with one record check left out or done the obvious way,
each a complete program run through tests/grade.py on the six hidden mains exactly as a submission.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt

- drawing profile kept: the design levels of an unrecorded diversion are used as they stand;
- chamber point only: the crown found at the chamber replaces the drawing's level there, the other design levels of
  the diversion are kept;
- crown tapping assumed: the transmitter is taken to sit on the crown tapping wherever it is;
- drawing corrected at every chamber, crown tapping assumed: the drawing's level at the chamber is replaced by the
  transmitter's, on every main, with the transmitter taken to sit on the crown tapping;
- design roughness: the roughness of the system description;
- roughness from the pump station over every running period: the head loss from PT201 to the reservoir, throttled
  periods included;
- middle reservoir level only.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

ONLY_POINT = [('            if c0 < c < c1:\n                z[i] = np.interp(c, [c0, S["kx"], c1], [z0, zc, z1])\n',
               '            if abs(c - S["kx"]) < 1.0:\n                z[i] = zc\n')]
EVERYWHERE = [('    if S["div"] is not None and S["div"][0] < S["kx"] < S["div"][1]:\n',
               '    if S["div"] is None: S["div"] = (S["kx"] - 1.0, S["kx"] + 1.0)\n    if S["div"] is not None and S["div"][0] < S["kx"] < S["div"][1]:\n')]
ROUTES = [("drawing profile kept", dict(skip={"div"})),
          ("chamber point only", dict(replace=ONLY_POINT)),
          ("crown tapping assumed", dict(skip={"datum"})),
          ("drawing corrected at every chamber, crown tapping assumed", dict(skip={"datum"}, replace=EVERYWHERE)),
          ("design roughness", dict(skip={"friction"})),
          ("roughness from the pump station over every running period", dict(skip={"segment", "throttle"})),
          ("middle reservoir level only", dict(skip={"levels"})),
          ("all of the above but the chamber variants (drawings, design roughness, middle level)",
           dict(skip={"div", "datum", "friction", "levels"}))]
T = C.truth(); PK = sorted(T)
print("Routes as complete programs through tests/grade.py (run as %s); six hidden mains; accepted when at most %d is "
      "wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.MAX_WRONG))
print("%-80s %5s  %s" % ("route", "wrong", "mains wrong (ratio of the design to the smallest vessel; < 1 is unsafe)"))
for name, kw in ROUTES:
    r = C.verify(C.program(**kw))
    bad = ["%s %.3f" % (p, r["packages"][p].get("ratio_to_smallest") or float("nan")) for p in PK if not r["packages"][p]["right"]]
    print("%-80s %5d  %s  %s" % (name, r["wrong"], ", ".join(bad), "accepted" if r["accepted"] else "rejected"))
