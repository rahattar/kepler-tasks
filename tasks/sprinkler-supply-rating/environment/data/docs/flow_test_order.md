# The flow test order

The audit can call on **one flow test**, ordered once, from the contractor who tests the site's hydrants.

    flowtest status
    flowtest submit < plan.json

`flowtest status` reports whether the order has been placed and what was ordered. `flowtest submit` reads the
plan on standard input and places the order. **The order can be placed only once.** It cannot be changed, extended
or replaced afterwards, and no result is known before it is placed.

The plan names one riser and one flow:

    {"riser": "SR05", "flow_gpm": 600}

## The test

The contractor connects hoses and a flow meter to the riser's test header, which is above the riser's alarm valve,
and sets the flow named in the plan, between 300 and 1000 gpm. Nothing else flows on the site. The test is
run on 2026-10-08.

The report gives the flow on the contractor's meter, the riser's supply gauge before the header was opened and
with the flow steady, the gauge's serial, and the reading of the utility's transmitter PT-0 at the same minute.
The meter is good to about 0.3 per cent. The report is written to `/app/flowtest/`.
