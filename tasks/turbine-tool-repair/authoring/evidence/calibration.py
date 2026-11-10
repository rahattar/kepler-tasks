"""Checks the sealed values and the OEM tables against the sealed definition (authoring/provenance/gtsim.py):
tests/hidden/truth.json equals the test specifications, the tables in the OEM document equal the definition's curves at
the tabulated points, and every correction factor is 1 at the reference conditions.

    python3 authoring/evidence/calibration.py > authoring/evidence/calibration.txt
"""
import json
import os

import numpy as np

import common as C
import gtsim as G

if __name__ == "__main__":
    truth = json.load(open(os.path.join(C.HIDDEN, "truth.json")))
    worst = max(max(abs(truth[n]["output_mw"] - G.TESTS[n]["p_mw"]), abs(truth[n]["heat_rate"] - G.TESTS[n]["hr"]))
                for n in G.HIDDEN)
    print("truth.json against the specifications: %d sets, largest difference %.1e" % (len(truth), worst))
    for n in G.HIDDEN:
        print("  %s  %.2f MW  %.0f kJ/kWh" % (n, truth[n]["output_mw"], truth[n]["heat_rate"]))
    txt = open(os.path.join(C.ROOT, "environment", "data", "docs", "oem_correction_curves.md")).read()
    rows = [l for l in txt.splitlines() if l.startswith("| ") and l[2:3] in "-0123456789"]
    dev = 0.0
    for l in rows:
        x, fo, fh = (float(c) for c in l.strip("|").split("|"))
        sec = txt[:txt.index(l)].rsplit("## ", 1)[1].splitlines()[0]
        f, g = {"Compressor inlet temperature": (G.f_cit, G.g_cit), "Inlet loss": (G.f_in, G.g_in),
                "Exhaust loss": (G.f_ex, G.g_ex), "Ambient specific humidity": (G.f_hum, G.g_hum)}[sec]
        dev = max(dev, abs(float(f(x)) - fo), abs(float(g(x)) - fh))
    print("OEM tables against the definition: %d points, largest difference %.1e (4-decimal rounding)" % (len(rows), dev))
    ref = float(G.f_cit(15.0) * G.f_hum(G.W_REF) * G.f_in(1.0) * G.f_ex(3.0)), \
        float(G.g_cit(15.0) * G.g_hum(G.W_REF) * G.g_in(1.0) * G.g_ex(3.0))
    print("product of the output factors at reference %.6f, of the heat rate factors %.6f" % ref)
    assert worst < 1e-9 and dev <= 5.1e-5 and abs(ref[0] - 1) < 1e-12 and abs(ref[1] - 1) < 1e-12
