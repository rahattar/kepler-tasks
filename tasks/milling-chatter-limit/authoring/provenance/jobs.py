"""Sealed definitions of the milling jobs.

A job: the machine, the tool assembly and its true tool-tip modes in machine X and Y as it is now, the cut (milling
mode, feed axis, radial depth, programmed speed, material), the tap tests in the job's records (date, assembly,
stickout, units, accelerometer mass and whether the data are corrected for it, accelerometer flank, the modes the
test measured) and the machine log (spindle rebuild, spindle speed limit).

The truth of a job is the zero-order stability limit (chat.limit) of its operation at the speed the spindle will run
(the programmed speed, or the machine's speed limit when that is lower), with N the inserts fitted, from the true
modes of the assembly as it is now on a 0.1 Hz grid. The tap test files carry the modes the test measured, as the
lab recorded them (rounded noise of 0.3 percent; the accelerometer mass when uncorrected; the sign when the
accelerometer was on the opposite flank; the quantity measured)."""
import numpy as np
import chat as C

MAT = {"6061-T6": (7.0e8, 0.30), "7075-T6": (8.2e8, 0.28), "1045": (2.0e9, 0.35), "4140 QT": (2.6e9, 0.38),
       "GG25": (1.1e9, 0.40)}


def J(name, seed, machine, D, teeth, material, milling, feed, ae, S, assembly, stickout, modes, tests=None, inserts=None,
      ae_form="mm", log=(), clamp=None, units="receptance"):
    if tests is None:
        tests = [dict(date="2026-03-10", assembly=assembly, stickout=stickout, units=units, modes=modes)]
    for t in tests:
        t.setdefault("mass_g", 3.0); t.setdefault("corrected", True); t.setdefault("opposite", ())
    return dict(name=name, seed=seed, machine=machine, D=D, teeth=teeth, inserts=inserts, material=material,
                milling=milling, feed=feed, ae=ae, ae_form=ae_form, S=S, assembly=assembly, stickout=stickout,
                modes=modes, tests=tests, log=list(log), clamp=clamp)


def M(fx1, kx1, fx2, kx2, fy1, ky1, fy2, ky2, z=(0.032, 0.03, 0.036, 0.028)):
    return dict(X=[(fx1, z[0], kx1), (fx2, z[1], kx2)], Y=[(fy1, z[2], ky1), (fy2, z[3], ky2)])


A_EX = M(780, 6.0e6, 1720, 1.4e7, 735, 5.0e6, 1640, 1.6e7)
A1 = M(910, 1.3e6, 2100, 3.4e6, 850, 1.05e6, 1980, 3.7e6)
A2 = M(640, 4.6e6, 1500, 1.2e7, 600, 3.8e6, 1420, 1.3e7)
A3 = M(520, 5.5e6, 1350, 1.0e7, 565, 6.8e6, 1280, 8.8e6, z=(0.04, 0.03, 0.035, 0.03))
A4 = M(700, 5.5e6, 1610, 1.3e7, 690, 4.4e6, 1530, 1.5e7)
A4_OLD = M(760, 6.3e6, 1700, 1.3e7, 745, 5.2e6, 1600, 1.5e7)            # before the spindle rebuild
A5 = M(820, 3.9e6, 1880, 1.0e7, 790, 3.2e6, 1810, 1.1e7)
A5_LONG = M(690, 2.6e6, 1700, 0.9e7, 665, 2.2e6, 1650, 1.0e7)             # the same tool set out to a longer stickout
A6 = M(590, 1.8e7, 1420, 3.6e7, 630, 2.3e7, 1330, 3.1e7, z=(0.042, 0.03, 0.036, 0.03))
A7 = M(870, 1.45e6, 1950, 4.0e6, 820, 1.2e6, 1870, 4.4e6)
A7_OLD = M(930, 1.7e6, 2040, 4.3e6, 880, 1.4e6, 1950, 4.6e6)            # before the spindle rebuild
A7_LONG = M(735, 1.0e6, 1760, 3.4e6, 700, 0.84e6, 1700, 3.8e6)

EXAMPLE = "job-ex"
JOBS = [
    J("job-ex", 1, "VMC-3", 0.016, 3, "6061-T6", "climb", "X", 0.004, 12000, "TA-16-45", 45, A_EX),
    # feed along machine Y; programmed speed in a lobe pocket
    J("bracket-pocket", 11, "VMC-2", 0.012, 3, "7075-T6", "climb", "Y", 0.003, 17000, "TA-12-40", 40, A1,
      tests=[dict(date="2026-03-10", assembly="TA-12-40", stickout=40, units="receptance", modes=A1, corrected=False)]),
    # conventional milling; accelerance FRFs; stepover given in percent
    J("shaft-flat", 12, "VMC-3", 0.020, 4, "1045", "conventional", "X", 0.006, 6500, "TA-20-60", 60, A2,
      units="accelerance", ae_form="percent"),
    # face mill body with 6 pockets, 3 inserts fitted; mobility FRFs
    J("housing-face", 13, "HMC-1", 0.050, 6, "GG25", "climb", "X", 0.030, 5200, "FM-50-6", 0, A3, inserts=3,
      units="mobility"),
    # spindle rebuilt after the first test; speed limit after the rebuild
    J("valve-body", 14, "VMC-1", 0.020, 4, "7075-T6", "climb", "X", 0.006, 15000, "TA-20-50", 50, A4,
      tests=[dict(date="2025-11-04", assembly="TA-20-50", stickout=50, units="receptance", modes=A4_OLD),
             dict(date="2026-02-19", assembly="TA-20-50", stickout=50, units="receptance", modes=A4, opposite=("X",))],
      log=[("2026-01-27", "spindle", "Spindle cartridge rebuilt with hybrid ceramic bearings of a lower speed rating."),
           ("2026-01-28", "parameter", "Spindle maximum speed parameter set to 12000 rpm after the rebuild.")], clamp=12000),
    # the latest test is of the same tool at a longer stickout; feed along Y; conventional
    J("manifold-slot", 15, "VMC-2", 0.016, 3, "7075-T6", "conventional", "Y", 0.005, 9000, "TA-16-42", 42, A5,
      tests=[dict(date="2025-12-02", assembly="TA-16-42", stickout=42, units="receptance", modes=A5, opposite=("Y",)),
             dict(date="2026-04-08", assembly="TA-16-42", stickout=55, units="receptance", modes=A5_LONG)]),
    # face mill, 8 pockets, 4 inserts fitted; conventional; accelerance; speed limit
    J("pump-cover", 16, "HMC-1", 0.063, 8, "4140 QT", "conventional", "X", 0.035, 3200, "FM-63-8", 0, A6, inserts=4,
      units="accelerance", log=[("2025-09-15", "parameter", "Spindle maximum speed parameter set to 2800 rpm (gearbox high range locked out).")],
      clamp=2800),
    # the latest test is at a longer stickout; feed along Y; stepover percent
    J("lever-profile", 17, "VMC-4", 0.012, 3, "6061-T6", "climb", "Y", 0.004, 16000, "TA-12-38", 38, A7, ae_form="percent",
      tests=[dict(date="2025-10-21", assembly="TA-12-38", stickout=38, units="receptance", modes=A7_OLD),
             dict(date="2026-01-20", assembly="TA-12-38", stickout=38, units="receptance", modes=A7, corrected=False),
             dict(date="2026-03-30", assembly="TA-12-38", stickout=50, units="receptance", modes=A7_LONG)],
      log=[("2025-12-15", "spindle", "Spindle cartridge replaced by a reconditioned unit; drive derated."),
           ("2025-12-16", "parameter", "Spindle maximum speed parameter set to 9000 rpm.")], clamp=9000),
]
BY = {j["name"]: j for j in JOBS}
HIDDEN = [j["name"] for j in JOBS if j["name"] != EXAMPLE]


def run_speed(j):
    return min(j["S"], j["clamp"]) if j["clamp"] else j["S"]


def stability(j, modes=None, speed=None, swap=False, mode_flip=False, N=None, shortcut=False, df=0.1):
    f = np.arange(50, 8000, df)
    Kt, Kr = MAT[j["material"]]
    N = N or j["inserts"] or j["teeth"]
    modes = modes or j["modes"]
    feed = j["feed"] if not swap else ("Y" if j["feed"] == "X" else "X")
    Gx, Gy = C.frf(f, modes["X"]), C.frf(f, modes["Y"])
    Gf, Gn = (Gx, Gy) if feed == "X" else (Gy, Gx)
    m = "down" if j["milling"] == "climb" else "up"
    if mode_flip: m = "up" if m == "down" else "down"
    s, e = C.immersion(j["ae"], j["D"], m)
    if shortcut:
        return C.abs_min(f, Gf, Gn, N, Kt, Kr, s, e)
    return C.limit(speed or run_speed(j), f, Gf, Gn, N, Kt, Kr, s, e)


def truth(j):
    return stability(j)
