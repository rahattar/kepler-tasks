"""Vendor catalogue: standard shells, tubes, tube counts and prices."""
import math

SHELLS_MM = [305, 337, 387, 438, 489, 540, 591, 635, 686, 737, 787, 838]
TUBES = {"19.05x1.65": (19.05, 1.65), "19.05x2.11": (19.05, 2.11), "25.40x2.11": (25.40, 2.11)}
LENGTHS_M = [2.44, 3.66, 4.88, 6.10]
PASSES = [2, 4, 6]
LAYOUTS = [30, 90]
CUTS = [20, 25, 35]
CTP = {2: 0.90, 4: 0.85, 6: 0.80}
SPAN_MAX_MM = {19.05: 1524.0, 25.40: 1880.0}       # TEMA maximum unsupported straight tube span, steel


def tube_count(shell_mm, od, layout, passes):
    pt = 1.25 * od
    Dotl = shell_mm - (12.0 + 0.005 * shell_mm)
    cl = 0.866 if layout == 30 else 1.0
    return int(CTP[passes] * math.pi * Dotl ** 2 / 4 / (cl * pt * pt))


def price(shell_mm, length_m, tubes, od, passes, layout):
    area = tubes * math.pi * od / 1000 * length_m
    return round(9000 + 26.0 * shell_mm * length_m + 210.0 * area + 450.0 * passes + (600 if layout == 90 else 0), -1)


def designs(spacing_step_mm=25):
    for s in SHELLS_MM:
        for tk, (od, wall) in TUBES.items():
            for L in LENGTHS_M:
                for npass in PASSES:
                    for lay in LAYOUTS:
                        nt = tube_count(s, od, lay, npass)
                        if nt < 20:
                            continue
                        for cut in CUTS:
                            lo = max(0.2 * s, 50.0)
                            hi = min(s, SPAN_MAX_MM[od] / 2)
                            sp = math.ceil(lo / spacing_step_mm) * spacing_step_mm
                            while sp <= hi:
                                for ns in (1, 2, 3):
                                    yield dict(shell_id_mm=s, tube=tk, tube_od_mm=od, tube_wall_mm=wall, tube_length_m=L,
                                               tube_passes=npass, layout_deg=lay, pitch_mm=round(1.25 * od, 3),
                                               baffle_cut_pct=cut, baffle_spacing_mm=sp, shells_in_series=ns, tubes=nt)
                                sp += spacing_step_mm
