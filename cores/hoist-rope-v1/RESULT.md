# hoist-rope-v1: low 0 of 3, xhigh 1 of 3 (Nov 13)

v0 with a second condition that has the first one's signature, and a wear behaviour that is the rope's own.

- **Turned** (as v0): a rope turned end for end at a time no record gives. The next survey is the mirror of
  the one before, and the damage goes with the element.
- **Counted from the dead end** (new): from one survey on, a rope's stations were counted from the dead end
  and written down as if from the drum. The next survey is the mirror of the one before, exactly as for a
  turn, but the rope never moved: the damage stays where the log puts it, and only the diameters have to be
  read from the right element.
- The two are told apart by where the rope goes on thinning. Bendings fall where the reeving puts them, so
  after a turn the loss of diameter follows the bendings as listed, and after a change of end it follows them
  mirrored (`ref_ropes.py`: correlation of the loss with the bendings of the same days, 0.90 to 0.98 one way
  against -0.58 to 0.44 the other, on every rope concerned).
- Wear: per-rope constants (rate, exponent, drift) and a gain that varies along the rope element by element
  (about 16 per cent), so the last survey is no longer a readout of the result.
- The package without results holds one rope of each kind (MH-1 turned, MH-5 counted from the dead end). Hidden:
  six turned and six counted from the dead end over five works, one works sound.

| program | examples | pending | six hidden works |
|---|---|---|---|
| reference | exact | accepted, 0.14 band | accepted, worst 0.34 band |
| every survey as listed (`MODE=listed`) | exact | MH-1 24 of 29 out; MH-5 within 0.15 band | every turned rope out (6 to 48 stations, 8 to 15 bands); ropes counted from the dead end within 0.22 band |
| every mirroring a turn (`MODE=allturn`) | exact | MH-5 20 of 25 out | every rope counted from the dead end out (16 to 62 stations, 5 to 8 bands) |
| the three v0 xhigh programs | exact | MH-5 20 of 25 out | not accepted |
| low 1 (4 min) | exact | MH-5 20 of 25 out | not accepted, as `allturn` |
| low 2, low 3 (1 min) | exact | MH-1 24 of 29 out | not accepted, as `listed` |
| xhigh 1 (33 min) | exact | MH-5 20 of 25 out | not accepted, as `allturn` |
| xhigh 3 (43 min) | exact | MH-5 20 of 25 out | not accepted, as `allturn` |
| xhigh 2 (52 min) | exact | accepted | accepted, worst 0.39 band |

What was seen:

- Low 1 laid each interval's loss of diameter against the bendings of the interval, rope by rope, as a first
  look at the surveys, saw two ropes break, found both mirrors and called both turns, in four minutes. On v0
  that run would have passed. The second condition is what holds low effort at 0 of 3, not the first.
- Xhigh 1 and 3 found both mirrors, called both turns and then spent their time on dating the turn inside its
  interval and on synthetic packages of their own, which they generated with turns only. Xhigh 3 wrote that
  the wear history narrows the date for MH-1 "but not for MH-5" and went on. The first explanation fits the
  mirror itself perfectly and so confirmed itself.
- Xhigh 2 fitted every interval's wear to the bendings, as listed and mirrored, saw MH-5 follow the mirrored
  bendings in all eight later intervals, and separated the two. Its method is the reference's.
- Xhigh 2 asked which reading of MH-5 the results take and how the rows are numbered where a survey was
  written from the other end. The standard has to say in physical terms what a station of the result is.
- The time limit separated no run (0.4 to 2.6 s against 30 s).

At the bar on the core. Next: the bundle at shipping size.

`core/` is not committed. `python3 gen.py` rebuilds it from fixed seeds; then copy `docs_src/*.md` into
`core/environment/data/docs/`. `./mk.sh NAME` makes a probe sandbox at `/tmp/NAME`.
