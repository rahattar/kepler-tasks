# journal-bearing bare core v1 (Nov 12): low 1 of 3, xhigh 2 of 2 (one still running)

v1 is v0's physics and cases with the inputs wrapped in plant records: a datasheet as built, a maintenance
history (shell fitted, journal ground, split line set, oil changed, orifice changed, on either of the machine's
two bearings), oil analyses and two supply RTDs. The three example packages have sound records; the eight
hidden packages carry events, and one has a supply RTD stuck at one value through the whole record.

| probe (opus) | result | the stuck-sensor package |
|---|---|---|
| low 1 | accepted | dropped "the one that repeats its earlier value" |
| low 2 | 7 of 8 packages | kept the reading nearer the package median, which is the stuck one |
| low 3 | 7 of 8 packages | judged disagreement against the pair's usual offset; stuck all record long, the offset looks usual |
| xhigh 5 | accepted | a reading that repeats exactly while its partner moves |
| xhigh 6 | accepted | stuck on one value for three or more points while its partner moves |

- **Every run got every maintenance and oil record right**: diametral against radial clearance, a grind before
  or after a shell fit, the other bearing's jobs, the split line, the oil charge and its analysis, by date.
  Record semantics that a format document defines are implemented, at any effort, with no example to check
  against. A datasheet-only program fails six of the eight packages; no probe wrote one.
- **The one thing that separated runs was the fault no document names.** "The control system marks only the
  failures it detects" made all five write a screen. Whether the screen was right decided the run.
- **A stuck sensor is too easy a fault to carry a task.** "Repeats while its partner moves" is the first idea of
  three runs in five. Low 1 of 3 fails a 0 of 3 screen two times in three, and xhigh is at the ceiling.

v2 keeps v1 and replaces the guessable screen with one that needs the physics: supply RTDs that read 4 to 5 K
out for a period, with the drain RTD as the only witness (all the power loss leaves with the oil, so the right
inlet temperature reproduces the drain reading). The three accepted v1 programs all fail v2.
