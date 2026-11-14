# hoist-rope-v0: low 0 of 3, xhigh 3 of 3 (Nov 13)

A program reckons the bending damage along a crane's hoist rope from the movement log and the rope surveys, to
a company standard (reeving geometry, tension, a Feyrer-type endurance, Miner's sum by rope element). In five
of six hidden works one or two ropes were turned end for end at a time no record gives; the only trace is a
survey that is the mirror of the one before. One such rope is in the package without results. Small core:
five or six cranes and about 80,000 to 97,000 movements a works, 30 s limit, runs of 0.5 to 2 s.

| program | examples | pending | six hidden works |
|---|---|---|---|
| reference (`ref_ropes.py`: each survey laid against the one before, as listed and mirrored; turn at mid interval) | exact | accepted, 0.14 band | accepted, worst 0.44 band |
| as listed (`as_listed.py`) | exact | MH-1 24 of 29 out | every turned rope out, 10 to 28 stations, 5 to 13 bands |
| low 1, 2, 3 (1 to 3 min) | accepted | MH-1 24 of 29 out | not accepted, as the as-listed program |
| xhigh 1 (cut off by an environment restart at about 40 min; its program as left) | exact | accepted | accepted, worst 0.05 band |
| xhigh 2 (33 min) | exact | accepted | accepted, worst 0.08 band |
| xhigh 3 (27 min) | exact | accepted | accepted, worst 0.04 band |

The low probes ran on the first build; the xhigh probes on the build after two noise fixes (below). The low
programs give the same result on the second build: examples exact, MH-1 24 of 29 out.

What was seen:

- Low effort wrote the standard as stated, matched the examples and stopped. None opened the surveys of the
  package without results beyond what the calculation reads.
- All three xhigh probes found the mirrored survey of MH-1 and followed the element. All three went further
  than the reference: the survey diameters were generated as a fixed law of the damage (loss = constant x
  (D/Dmax)^0.7 plus a uniform drift), they fitted that law on the sound ropes and used it to place the turn
  inside its interval to about a day.
- The same law is a hole: the last survey alone gives the shape of the damage along the rope, turned or not.
  No probe used it that way. A survey must not be a function of the result.
- First build: about 300 movements a works were logged out of time order (cycles overlapping by a few
  ten-thousandths of a day), and a sheave could stop exactly on a station, which the crossing rule does not
  settle; the low programs were 1 per cent off on the examples and two of the three reports dwelt on it. Fixed
  in `gen.py` (cycles spaced, sheave offsets in millimetres and never on the centimetre grid of the heights).
- The time limit separated no run.

Not at the bar: one data-only condition, plainly visible in the unscored package, is found by every careful
run. Next: v1, a second condition with the same signature (surveys taken from the dead end from one survey on,
written down as if from the drum), and a wear behaviour that belongs to the rope and the element.

`core/` (24 MB, mostly movement logs) is not committed. `python3 gen.py` rebuilds it from fixed seeds; then
copy `docs_src/*.md` into `core/environment/data/docs/`. `./mk.sh NAME` makes a probe sandbox at `/tmp/NAME`.
