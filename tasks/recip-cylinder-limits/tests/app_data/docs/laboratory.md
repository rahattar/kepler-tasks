# Laboratory and shop services

Two services are available to the study. Both are booked against the same allowance.

## The allowance

**2 readings in all.** The allowance does not refill. Every reading is reported back and a copy is written to
`/app/lab_reports`.

## gc

    gc <stage>

Draws a sample from the stage's sample stream and reports the gas analysis, mol per cent of each component to 0.01.
The stages are 1, 2 and 3. A stage's sample stream is taken at its suction. One reading.

## weigh

    weigh <cylinder>

Has the shop weigh the reciprocating assembly of the throw and reports the weight in kg to 0.1. The cylinders are
1A 1B 2A 2B 3A 3B. One reading.
