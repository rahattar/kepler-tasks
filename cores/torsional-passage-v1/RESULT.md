# torsional-passage v1 (Nov 14, small hours): the coupling stiffens with twist

v0 with the coupling's torque k23 (d + b d^3) + c23 d', b about 80 per rad2, so that the line is nonlinear at
the fast time scale and its recursion cannot be run as a linear filter; the heating keeps a set's runs in one
sequence, so they cannot be batched either. Hidden ramps 10 to 100 s, sequences to about 430 s; scope widened
to 900 s and ramps to 120 s. Everything stated in `ts4_torsional.md` issue 3.

The reference (`peaks.py`, a state envelope with the stiffening as a describing function, the third harmonic
quasi-steady) is 0.7 to 1.4 per cent from the truth on 10 to 15 s ramps and 2.6 per cent on a 6 s ramp: not
good enough to ship at 3 per cent bands. It was built only to show a fast method exists.

## Probes (opus = claude-opus-5-5), graded by v0's `check_program.py`, limit 6 s

| probe | time | hidden | method |
|---|---|---|---|
| low 1 | 19 min | accepted, widest 0.11 of a band | exact linear propagation in windows of up to 1 s, every step of a window in one array operation; the stiffening iterated to convergence in each window around a matched linear stiffness; windows halved when they do not settle |
| low 2 | 17 min | accepted, widest 0.14 | (report not read; program graded) |
| low 3 | 15 min | accepted, widest 0.42 | the linear line solved exactly mode by mode on a 0.25 ms grid; the stiffening and the heating in a Python loop on a 2 ms step, fed back through the modes |

Low 3 of 3, all more accurate than the reference, 1.0 to 2.5 s a set. Each wrote its own brute-force simulator
and checked its fast program against it on the pending sets and on stress sets of its own at the edge of the
stated scope.

## What it shows

A nonlinearity at the fast time scale did not keep a Python loop in the way. Low effort split the line into an
exactly propagated linear part and a nonlinear correction on a coarser step or iterated within windows, and
validated the split against its own slow simulator. Making stepping costly does not make a task hard for this
model; it writes the fast method and the check in a quarter of an hour.
