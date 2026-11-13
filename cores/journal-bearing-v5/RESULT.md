# journal-bearing v5 (Nov 12): v4 with the condition in the visible data. Built as a bundle, not probed.

v5 is `tasks/journal-bearing-survey`. It is v4 with three changes, made while the bundle was built:

1. **A third visible package, `/app/data/pending/west_quarry`, without results.** Its console LO-2 is two
   charges: K-120 and K-122 analyse at 44.0 to 44.6 mm2/s, M-123 at 39.3 to 39.9 in the same four rounds, and
   the allowance is 5 against 4 systems renewed in the register. The agent's laboratory answers for it.
2. **quay_site reseeded** (21 to 37). On the old seed its two new charges were 2.2 per cent apart, so a
   program that sampled one of them was only marginally out there. Now every such console's new charges
   stand 10.2 to 24.9 per cent apart. The other five hidden sites and both examples are byte for byte v4's.
3. **The format document names the pending package** in one sentence. Nothing else the agent reads changed.

## Why

v4 broke the first of AfterQuery's Nov 12 tips (`docs/afterquery-asks-2026-11-11.md`, "Further guidance"):
every deciding condition must show at least once in the visible data. In v4 the split console existed only
in the hidden sites, and all six probes failed the same check the same way, which is the tips' own warning
sign. v4's result (low 0 of 3, xhigh 0 of 3) therefore does not carry over.

The two examples still have no such console, so their results still confirm a program that follows the
register. What is new is that the condition can be found by looking: the pending package runs with a sample
to spare, and its analyses on file show why.

## What is measured

| what was run through the bundle's checker | examples | hidden sites with points out |
|---|---|---|
| reference (`solution/bearing.py`), 13 to 27 s a site from one run to the next on the shared sandbox | accepted | 0 of 6 |
| second solution (`naive_bearing.py`), 0.34 to 0.46 s a point | | right on cut-down sites; over 60 s on the first full site |
| one sample for each listed system | accepted | 5 of 6, 223 to 315 points each |
| the same, spare spent on unsampled machines | accepted | 5 of 6, 223 to 315 |
| charges sorted for the oil on file, order by the register | accepted | 5 of 6, 68 to 151 |

## What is not

No probe has seen v5. The open question is how many runs look at the pending package closely enough to ask
why its allowance is 5. Expect more than v4's zero; three v4 runs already wrote a check that compares a
machine's analyses with its system's. A round of 3 low and 3 xhigh on `model: "opus"` settles it:
- low 0 of 3 and xhigh 1 or 2 of 3: ship as built. xhigh 3 of 3 is the too-easy pattern against the bar as of
  Nov 13 (easiness 0 of 3, difficulty band 0 to 5 of 8): harden before shipping;
- low 1 or more of 3: too visible; the next step is a pending package whose console differs by less, or
  whose allowance has no spare (a kept console), not a return to v4;
- 0 of 6 again with nobody opening the pending package: the instance is fair but unread; say so in the notes.

## Nov 13: oracle failure and fix

20261113 failed intake's oracle check in 2 s. The checker's scratch directories took their modes through the
umask that test.sh sets (077), so the program could not read its package. Fixed in 20261113b; the lesson is in
`docs/rejection-patterns.md`. Nothing the agent sees changed.

## Nov 13: oracle confirmed in Docker

`tools/run_oracle.sh journal-bearing-survey-20261113b.zip` on Alex's Mac: both images build, solve.sh runs as
the agent user (examples 0 points out), test.sh gives reward 1 with the real ctrf plugin, verifier 58 s. The
six runs took 7.4 to 10.2 s there against 12 to 27 s in the sandbox, so the 60 s limit is about 6 times the
slowest run on that machine and 2.2 to 3.5 times here.
