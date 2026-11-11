# Unit 400 field testing

Issue 2, October 2026. What the unit's test crew will run during an assessment, and how it is ordered.

## Ordering

The crew takes its orders through the `fieldtest` command, one test to an order:

    fieldtest <test>

The booking for an assessment is 2 tests. A test is charged to the booking when it is ordered, whatever
its result, and the same test will not be run twice. The crew reports to `/app/field_reports`, one file an
order, and prints where it has written. Orders are taken in any sequence, but the crew is on the unit for one
shift only, so all of them have to be placed on what is already known rather than on the result of an earlier
test in the same booking.

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
