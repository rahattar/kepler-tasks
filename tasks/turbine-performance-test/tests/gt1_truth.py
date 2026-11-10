"""Sealed values for turbine-performance-test: GT-1's corrected gross output (MW) and corrected heat rate (kJ/kWh, LHV)
at the contract reference conditions, as found (2026-10-13) and as left (2026-10-15) (authoring/provenance/gt.py,
STATE; authoring/evidence/calibration.txt recomputes them).
"""
CONDITIONS = ["as_found", "as_left"]
OUTPUT_MW = {"as_found": 41.62, "as_left": 42.81}
HEAT_RATE = {"as_found": 10923.0, "as_left": 10702.0}
