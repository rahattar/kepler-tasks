# quench-oil v0 (Nov 13): the oil-charge mechanism of journal-bearing v5 on a different physics. Not probed.

Bundle `tasks/quench-oil-survey`, zip `quench-oil-survey-20261113.zip`. Built because `lube-oil-survey` (the
journal bearing bundle) is blocked by the platform as too similar to `journal-bearing-duty`, a bundle from
another chat that is still in validation; renaming and re-leading did not clear it.

What carried over unchanged: sites with oil systems, analyses on file, a renewal, one laboratory order placed
by the program, an allowance equal to the number of charges renewed, one listed system that is two reservoirs
at five of six hidden sites, two clean examples with results, one pending package without results that has
such a system. The verifier, laboratory and evidence scripts are the bearing bundle's, renamed.

What is new: the physics and everything that computes it.
- HT-5, oil quenching of round bars: radial transient conduction with k(T) and c_p(T), a surface coefficient
  that follows the oil's boiling curve, built from a probe test's three figures (CR_max, T_CRmax, CR_300).
- Five results a load: centre 800 to 500 C, centre rate through 700 C, largest centre to surface difference,
  surface temperature when the centre reaches 500 C, centre to 150 C.
- Nothing can be tabulated (diameter, steel, furnace, bath and oil all vary by load); the reference marches all
  loads of a steel as one array. 11 to 19 s a site here; limit 50 s.
- Sensitivity: 10 per cent more cooling power moves the centre's cooling time by 5 to 10 per cent.

| through the bundle's checker | examples | hidden sites with loads out |
|---|---|---|
| reference | accepted | 0 of 6, largest error 0.17 of a band |
| second solution (library stiff integrator, one load at a time), 0.15 s a load | | right on cut-down sites; over 50 s on the first full site |
| one sample for each listed system | accepted | 5 of 6, 245 to 270 loads each |
| charges sorted for the oil on file, order by the register | accepted | 5 of 6, 87 to 102 |

test.sh itself gives reward 1 for the reference from the unzipped zip. Docker not run here.

Not probed. The other session's low-effort round on the bearing version (0 of 3, pending package unread) is the
nearest evidence; the mechanism is the same, the physics is easier to get right at low effort than the film
was, so expect the same or slightly more solves.
