# The audit test order

The audit has a budget of **1 test across the whole fleet**, ordered once, with the contractor who does
the shop's vacuum work.

    vacwork status
    vacwork submit < plan.json

`vacwork status` reports whether the order has been placed, what was ordered and how many tests remain.
`vacwork submit` reads the plan on standard input and places the order. **The order can be placed only once.** It
cannot be changed, extended or replaced afterwards, and the results of no test are known until the whole order has
been placed.

The plan names a chamber and a test for each of its entries, and may hold no more entries than the budget:

    {"tests": [{"chamber": "VC03", "test": "rga", "pumping_time_h": 20}]}

The plan holds one entry. `pumping_time_h` is optional: the time from the start of roughing
at which the measurement is taken, from 4 to 48 hours. A plan that names none is tested at 16 h,
the contractor's standing practice. The reports are written to `/app/vacwork/`, with an index of what each file is.

## The tests

Every test of this order is run on the chamber's next pumpdown after an air vent. The chamber wall is at whatever
temperature the shop is on the day, and each report gives it, with the pumping time of the measurement.

**`rate-of-rise`** - the chamber is pumped to its base pressure, the high-vacuum valve is closed, and the pressure
is logged for 60 minutes at 10 s intervals with a spinning rotor gauge, which needs no gas correction. The record
holds the time from valve closure, the pressure, the pumping time and wall temperature at which the test was run,
and the chamber's base pressure over the ten minutes before the valve was closed.

**`speed-test`** - a throughput test as the shop's own speed tests are run: a known flow of dry nitrogen through a
calibrated leak, the pressure read with and without the flow on the contractor's own gauge. The record holds the
flow, both pressures, the speed they give, and the gauge's calibration factor.

**`rga`** - a quadrupole residual gas analyser on the chamber at its base pressure. The record holds the partial
pressure of each species it resolves, with the pumping time and wall temperature of the measurement.

**`helium`** - a helium leak test with the chamber under vacuum: the suspect seals and welds are hooded in turn and
the leak detector's signal is logged against time. The record holds the signal against time for each hooded region.
It does not depend on the pumping time.
