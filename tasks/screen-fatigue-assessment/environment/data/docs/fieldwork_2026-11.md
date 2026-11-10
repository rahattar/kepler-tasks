# Field work in the November outage

The contractor can carry out up to three field tests on the screens during the outage. The whole programme is
ordered at once and cannot be changed or extended afterwards: list every test in one plan.

Tests (each on one screen):
- coast-down: the drive's brake is disabled for one stop and the screen, running empty, coasts down to standstill
  as it did before 2026-03-02. Recorded from the stop command to standstill with the contractor's own gauges at 0.4t
  and 1.0t from the monitored weld toe (gauge factor set correctly), 500 samples per second, with the drive speed.
- strain-survey: the contractor's gauges at 0.4t and 1.0t, logged over a production day: eight steady records at
  the feeds of the day and two running empty, 8 s each, 500 samples per second.

Ordering: run `fieldwork submit` with the plan on standard input, as JSON:
  {"tests": [{"screen": "S6", "test": "coast-down"}, {"screen": "S5", "test": "strain-survey"}]}
`fieldwork status` shows whether the programme has been ordered. Results are written to /app/fieldwork/: one CSV per
record (ch1_ue, ch2_ue, and speed_rpm for a coast-down) and an index, fieldwork_index.csv.
