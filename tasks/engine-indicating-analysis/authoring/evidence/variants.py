"""Programs made from the reference by one change each.

ROUTES are programs that stop short: each leaves out, or gets wrong, one thing the records require.
SOUND are the same method carried out another defensible way; they differ from the reference in a choice the
physics does not make for the programmer.

Each change is a list of (text in solution/indicate.py, text put in its place); the text must occur exactly
once, so a change that no longer applies stops the study instead of passing silently.
"""
import common

ROUTES = [
    ("taken as the system has it",
     "IS-2 on the indicating system's angles and scale; nothing is settled from the records",
     [('RIG = "index and gain"', 'RIG = "as the system has it"')]),
    ("index alone",
     "the misfit on the compression stroke is put down to the encoder's index, whatever its shape",
     [('RIG = "index and gain"', 'RIG = "index alone"')]),
    ("gain alone",
     "the misfit on the compression stroke is put down to the transducer's gain, whatever its shape",
     [('RIG = "index and gain"', 'RIG = "gain alone"')]),
    ("no wall heat on the compression stroke",
     "index and gain are fitted to an adiabatic compression",
     [(' + wall_factor(eng, pt["speed"], vol_mid) * (\n                p_mid * 1e-5) ** 0.8 * temp ** -0.4 * (temp - pt["t_wall"])', '')]),
    ("constant ratio of specific heats",
     "index and gain are fitted with gamma fixed at 1.35 on the compression stroke",
     [('            g = gamma(temp, 0.0)\n', '            g = 1.35 + 0.0 * temp\n')]),
]

SOUND = [
    ("stretch from 8 degrees after inlet valve closing to 55 before top dead centre",
     [('eng["ivc_deg"] + 12.0', 'eng["ivc_deg"] + 8.0'), ('SYSTEM_ANGLE, -47.0', 'SYSTEM_ANGLE, -55.0')]),
    ("stretch from 25 degrees after inlet valve closing to 45 before top dead centre",
     [('eng["ivc_deg"] + 12.0', 'eng["ivc_deg"] + 25.0'), ('SYSTEM_ANGLE, -47.0', 'SYSTEM_ANGLE, -45.0')]),
    ("the summed heat release unweighted",
     [('        weight = 1.0 / vol[1:]\n', '        weight = np.ones_like(vol[1:])\n')]),
    ("half the cycles of each record for the index and gain",
     [('eng["cylinders"], -1, 720).mean(axis=1) for pt in points]', 'eng["cylinders"], -1, 720)[:, ::2].mean(axis=1) for pt in points]')]),
    ("burned fraction repeated to one part in a thousand",
     [('np.abs(released[:, -1])) < 1e-6', 'np.abs(released[:, -1])) < 1e-3')]),
]


def made(changes):
    """The reference's text with the changes applied."""
    with open(common.SOLUTION) as handle:
        text = handle.read()
    for old, new in changes:
        if text.count(old) != 1:
            raise SystemExit("variants: %r occurs %d times in solution/indicate.py, not once" % (old[:50], text.count(old)))
        text = text.replace(old, new)
    return text
