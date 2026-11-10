# Laboratory booking: instrument M-7

Two commands, run from `/app`:

    slm <position> <state>

one reading of the eight band levels at a position, dB as indicated by M-7, with `state` one of `off`, `c1`, `c2`, `c3`, `c4`, `c5`, `c6`, `c7`, `c8` or `all`:
which machine is running while the reading is taken, `off` for none of them and `all` for every one. `c1` is C1 and
so on through `c8`. Every machine runs at its rated speed and the adjacent bay is in its normal service.

    rt <position>

one reverberation time measurement at a position: the decay time of the eight bands, in seconds.

Positions are those of `positions.csv`. The two commands draw on one booking of 2 readings in all. Each report is
printed and saved under `/app/lab_reports`.
