# gear-face-load bare core v1 (Nov 13): exchanged flank names shown only by pitting; low 0 of 3

v0 with the contact pattern check replaced by the mesh misalignment measured at assembly, so no calculation
shows a misfit. On the pending pair and four of six hidden pairs one gear's lead charts carry the flank names
the other way round. The evidence is physical: pitting forms only on a flank that carries load, and every
exchanged gear's working flank is pitted under the name of the other flank; some sound gears are pitted on
their own working flank. 100 000 duty points, 10 s of CPU a run, 1.5 per cent.

## Probes (opus)

| probe | effort | time | hidden | what it did |
|---|---|---|---|---|
| G1 | low | 3 min | not accepted, the four exchanged pairs out (9.6 to 22 bands) | named flanks; noted as an open point that another pair's record might name flanks differently, and did not look |
| G2 | low | 2 min | not accepted, the same | tried all four pairings on the examples only |
| G3 | low | 1.5 min | not accepted, the same | tried all four pairings on the examples only |

| X1 | xhigh | 36 min | not accepted, the same | **found it**: pending pinion's R charts crowned only, L carries the lead correction and the only pits, the wheel's working flank pitted too; computed both answers; kept `pair.json` "as GF-4 and the package format require" and asked the owner to confirm |
| X2 | xhigh | 27 min | not accepted, the same | **noticed it** by the lead correction (on L in GB-P, on the working flank in both examples); did not look at pits; kept the package and flagged it |
| X3 | xhigh | 46 min | not accepted, the same | did not notice; saw the wheel's pits only as dips a median would drop |

Low 0 of 3; xhigh 0 of 3, two of three having found or noticed the condition.

## Reading: the evidence is found; the decision is unclear

- **The tell is legible.** Two xhigh runs found it from the pending package alone, one through the pits and
  the lead correction together. Nothing in a routine calculation shows it: no low run looked.
- **Every probe fails the same check the same way, and the two that saw it say why:** they took the package's
  working flank and the chart names as binding, and treated overriding them as the owner's decision. Nothing
  in the brief says the program's results are used unreviewed, and nothing says the chart names follow some
  convention other than GF-4's. Failing them grades a judgement the task never asks for: the "unwritten rule"
  of the Nov 12 tips.
- **The fix is in the framing, two factual sentences:** (1) the brief says the results are used as they come,
  with no review of a package before it runs; (2) the package format says the inspection records come from
  more than one shop and a shop's flank names need not follow GF-4 section 1. Then the low round has to be run
  again: sentence 2 is a pointer.
- Truth check: the 240-station truth is within 0.27 per cent of 960 stations on every package. For a bundle,
  compute the truth on 480.
- The time limit separated nothing: xhigh runs solved by contact set in 0.4 to 0.9 s.


## Checks before the probes

| program | hidden |
|---|---|
| reference (`ref_faceload.py`) | accepted, 0.6 to 3.0 s a pair (4.2 s on the slowest example) |
| charts as named (`named_faceload.py`) | fails 4 of 6, 93 to 99 per cent of points out, up to 22 bands |
| unoptimised (each point solved on its own) | 0.7 ms a point, about 70 s a pair |

- Pits: dips of 5 to 11 um in single tooth charts against 0.5 um of scatter about a smooth lead curve.
- The time limit separated nothing among the probes: all tabulated over force and misalignment or solved full
  contact in closed form, 0.6 to 2.3 s a pair.

## Files

`gf.py`, `gen.py` (specs, shift, `core/manifest.json`; the data is rebuilt by `mk.sh` and kept out of git),
`ref_faceload.py`, `named_faceload.py`, `grade.py`, `brief.txt`, `mk.sh`.
