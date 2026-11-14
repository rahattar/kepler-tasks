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

Low effort: 0 of 3. All three fail the same check the same way, which the Nov 12 tips call a warning sign;
the xhigh round says whether the pits can be found.

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
