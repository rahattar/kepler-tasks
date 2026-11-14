# Works package

One directory a works. Text files, comma separated, a header row, decimal points. Days are counted from the
day the ropes were put on.

## cranes.csv

- `crane`: name of the crane
- `falls`: number of falls n the hook hangs on
- `upper_block_height_m`: the height H of RS-4 section 1, m
- `block_mass_t`: mass of the lower block, t
- `reeving_efficiency`: the efficiency e of RS-4 section 3
- `rope_construction`: construction of the hoist rope, as in the table of RS-4 section 4
- `rope_length_m`: length L of the rope from the drum anchorage to the dead end, m

## sheaves.csv

One row for each sheave of a crane's reeving and one for its drum (`drum`).

- `crane`, `sheave`
- `parts`: the number p of falls between the sheave and the dead end
- `offset_m`: the offset a of RS-4 section 1, m
- `diameter_mm`: diameter of the sheave or drum, mm
- `bend_weight`: the weight w of RS-4 section 2

## movements.csv

The hoist controller's log, one row a movement, in order of time.

- `crane`, `day`: the crane and the time of the movement, in days
- `from_height_m`, `to_height_m`: hook height at the start and the end of the movement, m
- `hook_load_t`: load on the hook during the movement, t

## surveys.csv

The rope surveys: at each survey the rope's diameter is measured with a caliper at stations 5 m apart along
the whole rope. The caliper reads to 0.01 mm and repeats to about 0.02 mm.

- `crane`, `day`: the crane and the day of the survey
- `station_m`: distance of the station from the drum anchorage, along the rope, m
- `diameter_mm`: rope diameter at the station, mm

## expected.csv

Only in a package that comes with its results: the result to RS-4 section 5.

- `row`: the crane and the number of the station, counted from the drum anchorage from 001, joined by a hyphen
- `damage`
