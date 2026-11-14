# gear-face-load bare core v0 (Nov 13): the pattern check has two edges for one unknown, and low effort reads the surplus

A timed program: at every point of a spur gear pair's duty record, the face load factor and the contact
stress, from the gears' lead charts, the pinion's mounting and a contact pattern check on file (GF-4 in
`core/data/docs`). The mounting misalignment is the value that reproduces the recorded pattern. On the pending
pair and on four of six hidden pairs one gear's lead charts carry the flank names exchanged; both examples
with results are sound. 40 s of CPU a run, 20 000 duty points a pair, 1.5 per cent.

## Probes (opus, low effort)

| probe | time | hidden | what it did |
|---|---|---|---|
| G2 | 3.5 min | **accepted, 6 of 6**, worst 0.38 of the band, 4 to 5 s a pair | fitted m_0 to both edges, saw GB-P miss by 3.2 mm as named and fit with the pinion's other flank; falls back to the best-fitting flanks whenever the named ones miss |
| G3 | 4 min | **accepted, 6 of 6**, worst 0.25 of the band, 20 s a pair | found m_0 from each edge separately and compared the two; the same fallback |
| G1 | 7 min | not accepted: the four exchanged pairs out, 5.3 to 12.4 bands; 1.5 s a pair | checked the pattern fit on the two examples only; ran GB-P and did not look at its fit |

Low effort: 2 of 3 solved. The screen allows 0, so no xhigh probes were run.

## Reading

- **Two edges for one misalignment is a surplus measurement, and the surplus is a test** (the conveyor-drive
  lesson, which I had read and discounted because the package has no results). Fitting m_0 is a step every
  correct program takes; the misfit shows in that step on the pending pair, results or none.
- **"Low effort does not examine a package without results" holds only while nothing in the routine
  calculation reports a number.** Here the fit reports one.
- **The repair is discrete and small:** two gears, two flanks each, so trying the alternatives is three more
  fits. A condition with a short list of alternatives is found as soon as it is noticed.
- **Reused shapes are a second signpost:** both probes remarked that GB-P's pinion L charts look like GB-A's
  pinion R charts. Charts across packages must not resemble each other.
- The time limit separated nothing: one probe tabulated over force and temperature (4 s), one solved every
  point directly (20 s).

## Checks before the probes

| program | hidden |
|---|---|
| reference (`ref_faceload.py`) | accepted; 16 to 19 s a pair; worst 0.31 of the band |
| charts as named (`named_faceload.py`) | fails 4 of 6, most points out, up to 7.9 bands |
| unoptimised (`naive_faceload.py`, projected Gauss-Seidel in plain loops) | about 7.5 s a duty point at 240 stations |

- A mesh cycle with two tooth pairs sharing load was built and dropped: the heaviest load is always in single
  pair contact, so it changed no result.

## Files

`gf.py` truth physics, `gen.py` (specs, shift, `core/manifest.json`), `ref_faceload.py`, `named_faceload.py`,
`naive_faceload.py`, `grade.py`, `brief.txt`, `mk.sh`.
