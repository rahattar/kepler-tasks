"""Sealed values for cooling-tower-capability: each CT-2 cell's thermal capability at the end of the record
(2026-09-30 23:00), in percent of the design fill characteristic (authoring/provenance/cells.py, truth_table();
authoring/evidence/calibration.txt recomputes them).
"""
CELLS = ["C%d" % i for i in range(1, 9)]
CAPABILITY = {
    "C1": 96.5,
    "C2": 88.0,
    "C3": 101.0,
    "C4": 92.5,
    "C5": 72.0,
    "C6": 97.5,
    "C7": 79.0,
    "C8": 90.5,
}
