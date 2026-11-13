# Cell packages

A test cell sends each session on an engine as one package, a directory with these files.

## engine.json

| field | meaning |
|---|---|
| `cell` | the cell's name |
| `cylinders` | number of cylinders, all instrumented |
| `bore_mm`, `stroke_mm`, `conrod_mm` | bore, stroke and connecting rod length (centre to centre) |
| `compression_ratio` | geometric compression ratio |
| `ivc_deg`, `evo_deg` | inlet valve closing and exhaust valve opening, in degrees of crank angle from firing top dead centre, positive after it |
| `bar_per_count` | pressure change in bar for one count of a record |

## points.csv

One row for each operating point of the session, all of them fired.

| column | meaning |
|---|---|
| `point` | the point's name |
| `speed_rpm` | engine speed |
| `p_man_bar` | manifold pressure, bar absolute |
| `t_ivc_K` | charge temperature at inlet valve closing, from the cell's filling calculation |
| `t_wall_K` | combustion chamber wall temperature |
| `record` | the point's pressure record, a path within the package |

## Pressure records

A record is a NumPy `.npy` file holding a 16-bit integer array of shape (cylinders, cycles, 720): the
indicating system's counts for each cylinder, in cylinder order, for consecutive cycles.

A cycle's 720 samples are taken on consecutive pulses of the crank angle encoder, 720 to a revolution, over
the compression and expansion strokes. The indicating system's angle for sample k (from 0) is k/2 - 180
degrees.

Counts times `bar_per_count` is pressure in bar above a level that the charge amplifier sets anew each cycle;
the level is not recorded.

## Results

The results of a package are a CSV table with the header

    point,cylinder,imep_bar,pmax_bar,apmax_deg,ca10_deg,ca50_deg,q_gross_J

and one row for every point of `points.csv` and every cylinder (numbered from 1): the gross indicated mean
effective pressure in bar, the peak pressure in bar absolute and its crank angle, the crank angles of 10 and
50 per cent burned, and the gross heat released in J, as IS-2 defines them.

## Packages on file

`examples/cell_03` and `examples/cell_08` are sessions that have been calculated: each holds `expected.csv`,
its results to IS-2. `pending/cell_11` is a session that has not been calculated yet.
