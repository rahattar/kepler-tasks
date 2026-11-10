# The audit test order

The audit has a budget of **4 tests across the whole fleet**, ordered once, with the contractor who does
the shop's vacuum work.

    vacwork status
    vacwork submit < plan.json

`vacwork status` reports whether the order has been placed, what was ordered and how many tests remain.
`vacwork submit` reads the plan on standard input and places the order. **The order can be placed only once.** It
cannot be changed, extended or replaced afterwards, and the results of no test are known until the whole order has
been placed.

The plan names a chamber and a test for each of its entries:

    {"tests": [{"chamber": "VC03", "test": "rga"},
               {"chamber": "VC07", "test": "rate-of-rise"}]}

Between 1 and 4 entries, no entry repeated. The reports are written to `/app/vacwork/`.

## The tests

Every test of this order is run on the chamber's next pumpdown, at the reference pumping time of MS-BP clause 2.
The chamber wall is at whatever temperature the shop is on the day, and each report gives it.

**`rate-of-rise`** - the chamber is pumped to its base pressure, the high-vacuum valve is closed, and the pressure
is logged for 60 minutes at 10 s intervals with a spinning rotor gauge, which needs no gas correction. The record
holds the time from valve closure, the pressure, the pumping time and wall temperature at which the test was run,
and the chamber's base pressure over the ten minutes before the valve was closed.

**`speed-test`** - a throughput test as the shop's own speed tests are run: a known flow of dry nitrogen through a
calibrated leak, the pressure read with and without the flow. The record holds the flow, both pressures and the
gauge.

**`rga`** - a quadrupole residual gas analyser on the chamber at its base pressure. The record holds the partial
pressure of each species it resolves, with the pumping time and wall temperature of the measurement.

**`helium`** - a helium leak test with the chamber under vacuum: the suspect seals and welds are hooded in turn and
the leak detector's signal is logged against time. The record holds the signal against time for each hooded region.
