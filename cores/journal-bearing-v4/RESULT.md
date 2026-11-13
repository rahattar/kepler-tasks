# journal-bearing bare core v4 (Nov 12): low 0 of 3, xhigh 0 of 3, every failure the designed miss

v4 keeps the film physics and the 60 s limit and makes the program spend something on each hidden package. A
package is a site: 14 to 24 bearings on shared lube oil systems, 1 500 to 2 600 operating points. Most systems
were drained and refilled, the standard forbids nominal grade figures, and the program may place one
laboratory order of at most `lab_samples` bearings while it runs. In five of the six hidden sites one listed
system is two charges: samples drawn at its machines on the same dates differ by 8 to 11 per cent where every
other system's agree within about half a per cent, and the allowance is the listed count plus one. In the two
example sites the systems are what the register says and the allowance equals the listed count.

| what was run | split sites failed | points out on each | what it did with the allowance |
|---|---|---|---|
| the reference (machines sorted into charges by their analyses) | 0 of 5 | 0 | one sample for each charge; 21 s a site |
| one sample for each listed system (`as_listed.py`) | 5 of 5 | 223 to 293 | left one unused |
| low 1 (opus) | 5 of 5 | 223 to 482 | left one unused; "the examples can't show which reading is meant" |
| low 2 (opus) | 5 of 5 | 223 to 368 | left one unused; the examples matching "confirms the oil and lab-order logic" |
| low 3 (opus) | 5 of 5 | 112 to 298 | spare on "other current charges"; moves a machine whose analyses match a different listed system |
| xhigh 4 (opus) | 5 of 5 | 139 to 298 | spare on another machine, which "gets its own figures" if it disagrees |
| xhigh 5 (opus) | 5 of 5 | 112 to 298 | left one unused; 1 s a site |
| xhigh 6 (opus) | 5 of 5 | 223 to 482 | spare on the second bearing of a machine already sampled, averaged |

Every program passed both examples and the hidden site with no
split, within 0.4 per cent.

- **The mechanism that held on the alignment task holds inside a program.** The solver's own test packages
  carry its own assumption that the register is right, so every check it can run passes. Nothing it can make
  itself shows the miss, and the visible data cannot either.
- **The miss is wide and the same in every run:** the machines of one half of the split system, both before and
  after the refill, on five sites.
- **Three runs were one step away (low 3, xhigh 4, xhigh 5).** Each wrote a check that moves a machine to another listed system when
  its analyses match that system's. None asked whether one listed system could hold two charges.
- **The time limit is met by every program** (1 to 40 s a site); it is not what decides.
- **Risk:** 0 of 3 at xhigh. The Nov 11 ask allows 0 to 5 of 8. Whether a reviewer accepts an unstated split is
  the same question turbine-tool-repair's frozen sensor raised, and that passed.
