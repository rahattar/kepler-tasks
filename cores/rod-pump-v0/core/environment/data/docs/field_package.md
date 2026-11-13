# Field package

A field sends one directory. Text files, comma separated, a header row, decimal points.

## field.json

- `field`: name of the field
- `damping_per_s`: the viscous damping coefficient c of RL-2 section 2, 1/s
- `liquid_density_kg_m3`: density of the liquid the field's wells produce, kg/m3

## wells.csv

One row a well. The well file is kept from workover reports: it records what was run into the well and set at
its last workover.

- `well`: the well's name
- `pump_depth_m`: depth of the pump, m; the rod string reaches from the polished rod to it
- `plunger_mm`: plunger diameter, mm
- `tubing_od_mm`: outside diameter of the tubing, mm, one of the sizes of RL-2 section 5
- `anchor_depth_m`: depth at which a tubing anchor was set, m; empty where no anchor was run
- `tubing_head_pressure_kPa`: pressure in the tubing at the wellhead, kPa
- `unit_factor`: the unit factor k of RL-2 section 3
- `found_surface_stroke_m`, `found_spm`: the polished rod stroke, m, and the pumping speed, strokes a minute, the
  well was running at when its cards were taken

## rods.csv

The rod string of each well, one row a taper, `taper` counted from the polished rod down.

- `well`, `taper`, `material` (`steel` or `fibreglass`), `diameter_mm`, `length_m`

## cards.csv

The dynamometer cards on record, two a well, taken one after the other at the found setting.

- `well`, `card`: the well and the number of the card
- `sample`: 0 to 199; the 200 samples of a card are equally spaced in time over one stroke cycle, and sample 0 is
  at the bottom of the polished rod's stroke
- `position_m`: polished rod position above the bottom of its stroke, m
- `load_kN`: polished rod load, kN

## settings.csv

The setting table of the field: every setting its wells are to be calculated at.

- `setting`: the name of the setting
- `well`: the well
- `surface_stroke_m`: polished rod stroke, m
- `spm`: pumping speed, strokes a minute

## expected.csv

Only in a package that comes with its results: the results to RL-2 section 7 for every setting.

- `setting`, `plunger_stroke_m`, `liquid_m3_d`, `pprl_kN`, `mprl_kN`
