# Design note: journal-bearing-survey (Nov 12)

A timed program on shifted hidden data, to the Nov 11 ask. Built from bare cores v0 to v4
(`docs/difficulty-calibration.md`, the journal bearing sections) and changed once more while it was built
(`cores/journal-bearing-v5/RESULT.md`).

**Mechanism.** Kind A of `docs/trap-analysis-2026-11-11.md` inside a program: coverage under a zero-slack
budget, where the class left uncovered is one the solver never counted, and the program has to spend the
budget before it sees a result.

- A site's oil systems were drained and refilled; LS-3 takes a bearing's oil from the laboratory's analysis
  of its charge, never from the grade.
- The program places one laboratory order while it runs, of at most `lab_samples` bearings.
- The legible count is one sample for each system the register shows renewed. At five of six hidden sites one
  listed console is two reservoirs, so the allowance is that count plus one.
- The second reservoir shows in numbers only: its machine's analyses on file stand 9.4 to 12.1 per cent from
  the other two machines' in all four rounds, against 0.67 per cent between two samples of one charge.
- Both examples with results have no such console. The pending package, without results, has one.

**What must not be changed without re-probing.**
- The pending package has no results. With results the wrong program fails a visible test.
- The examples' allowance equals the register's count. A spare in an example with results is a visible test
  of the same kind.
- One order for a package, placed by the program. Two orders let a program sample, look and sample again.
- The format document's wording of `oil_system`: "the lube oil system the machine is connected to in the
  site register". It is accurate and it does not say the register is right.

**The timed half.** Limit 60 s a run on one CPU; reference 13 to 27 s a site here from one run to the next
(the committed run: 2.2 times the slowest; nearly all of it is the four film tables); the
unoptimised second solution 0.46 s a point, 16 to 18 times the limit. v3 showed the limit does not separate
runs: every probe found the tabulation. It is there because the ask requires it.

**Verifier.** The program runs as nobody, so the laboratory cannot be a sudo call as it is in the agent's
image; the checker opens a Unix socket for the length of a run and `labsample` in the verifier's image is a
client of it. Same rule file (`lab.py`) in both images.

**Local rates.** None for v5. v4 on `model: "opus"`: low 0 of 3, xhigh 0 of 3.
