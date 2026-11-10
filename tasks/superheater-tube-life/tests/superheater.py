"""Sealed values for superheater-tube-life: the consumed creep life fraction of each outlet element at the crown of
its outlet leg, from the tube's entry into service through 2026-10-31, under PS-14 with the true operating history,
flux, oxide and wall of every element (authoring/provenance/tubes.py, truth(); authoring/evidence/calibration.txt
recomputes them).
"""
ELEMENTS = ["E%d" % i for i in range(1, 11)]
DAMAGE = {
    "E1": 0.676893,
    "E2": 0.037493,
    "E3": 0.816577,
    "E4": 0.234038,
    "E5": 0.070814,
    "E6": 0.362499,
    "E7": 0.186745,
    "E8": 0.730069,
    "E9": 0.025828,
    "E10": 0.441742,
}
