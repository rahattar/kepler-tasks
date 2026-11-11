# Unit 400 field testing

Issue 2, October 2026. What the unit's test crew will run during an assessment, and how it is ordered.

## Ordering

The crew takes the booking through the `fieldtest` command, every test named together in one order:

    fieldtest <test> <test>

The booking for an assessment is 2 tests, and the crew is on the unit for one shift only: it writes the
whole booking down before it runs any of it, and once the order is placed it will take no other. So every test
has to be chosen on what the records already say, not on the result of another test in the same booking. The
crew reports to `/app/field_reports`, one file a test, and prints where it has written.

## What the crew will run

| test | what it does | what it reports |
|---|---|---|
| `tip-backpressure` | runs nitrogen through the stack tip from a temporary compressor | the flow, its temperature and the gauge pressure at the stack base |
| `pump-shutoff` | a four point performance test on P-401 as it now stands | flow against head at the running speed |
| `reboiler-E406` | a performance test on E-406 at three reboil rates | the steam pressure and flow, and the temperatures either side |
| `valve-PV4031` | strokes PV-4031 against measured flow at five travels | the travel, the pressures either side, the upstream temperature and the flow |
| `condenser-E404` | a performance test on E-404 over three cooling water temperatures | the water temperatures, the duty and the condensing temperature |
| `popcheck-PSV404` | lifts PSV-404 on the test stand, three pops | the pressure at which it lifted, as found |

## Reading the reports

Each report is a CSV with a commented first line naming the test and the day it was run. The crew measures and
records; it draws no conclusions, and it does not say whether a test was worth ordering.
