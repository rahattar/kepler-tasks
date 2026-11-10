"""Writes the turbine-tool task's files from gtsim.py.

    python3 gen.py DATA_DIR [HIDDEN_DIR]

DATA_DIR gets docs/ and examples/<test>/ (what the agent sees); HIDDEN_DIR, when given, gets <test>/ record sets and
truth.json for the hidden tests (what the verifier uses).
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gtsim as G  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT = """# Contractor's test report, GT-1, 2025-04-09 (summary page)

Performance test of GT-1 per TP-GT-07, three runs, all valid. Results at the contract reference conditions:

| quantity | result |
|---|---|
| corrected gross output | %.2f MW |
| corrected heat rate (LHV) | %.0f kJ/kWh |

The plant's own reduction program was not used for this report.
"""


def tables():
    cit = ["| CIT (degC) | output factor | heat rate factor |", "|---|---|---|"]
    cit += ["| %d | %.4f | %.4f |" % (t, f, g) for t, f, g in zip(G.CIT_PTS, G.CIT_F, G.CIT_G)]
    dpi = np.arange(0.0, 3.01, 0.5)
    rin = ["| inlet loss (kPa) | output factor | heat rate factor |", "|---|---|---|"]
    rin += ["| %.1f | %.4f | %.4f |" % (d, G.f_in(d), G.g_in(d)) for d in dpi]
    dpe = np.arange(0.0, 6.01, 1.0)
    rex = ["| exhaust loss (kPa) | output factor | heat rate factor |", "|---|---|---|"]
    rex += ["| %.1f | %.4f | %.4f |" % (d, G.f_ex(d), G.g_ex(d)) for d in dpe]
    w = np.arange(0.002, 0.0201, 0.002)
    rh = ["| specific humidity (kg/kg dry air) | output factor | heat rate factor |", "|---|---|---|"]
    rh += ["| %.3f | %.4f | %.4f |" % (x, G.f_hum(x), G.g_hum(x)) for x in w]
    return {"{CIT_TABLE}": "\n".join(cit), "{IN_TABLE}": "\n".join(rin), "{EX_TABLE}": "\n".join(rex),
            "{HUM_TABLE}": "\n".join(rh), "{W_REF}": "%.5f" % G.W_REF}


def write_set(name, out):
    s = G.TESTS[name]
    das, dcs, gas, log = G.simulate(s, s["seed"])
    os.makedirs(out, exist_ok=True)
    das.to_csv(os.path.join(out, "test_das_1min.csv"), index=False)
    dcs.to_csv(os.path.join(out, "dcs_1min.csv"), index=False)
    gas.to_csv(os.path.join(out, "gas_analysis.csv"), index=False)
    log.to_csv(os.path.join(out, "test_log.csv"), index=False)


def main(data, hidden=None):
    os.makedirs(os.path.join(data, "docs"), exist_ok=True)
    rep = tables()
    for n in sorted(os.listdir(os.path.join(HERE, "docs"))):
        txt = open(os.path.join(HERE, "docs", n)).read()
        for k, v in rep.items():
            txt = txt.replace(k, v)
        open(os.path.join(data, "docs", n), "w").write(txt)
    for name in G.EXAMPLES:
        write_set(name, os.path.join(data, "examples", name.replace("example_", "")))
    t = G.truth(G.EXAMPLES[0])
    open(os.path.join(data, "examples", G.EXAMPLES[0].replace("example_", ""), "contractor_report.md"), "w").write(
        REPORT % (t["output_mw"], t["heat_rate"]))
    if hidden:
        for name in G.HIDDEN:
            write_set(name, os.path.join(hidden, name))
        with open(os.path.join(hidden, "truth.json"), "w") as f:
            json.dump({n: G.truth(n) for n in G.HIDDEN}, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
