# Set packages

The test bed sends each generating set's sequence as one package, a directory with these files.

## shaftline.json

| field | meaning |
|---|---|
| `set` | the set's name |
| `engine` | the engine's cylinder arrangement |
| `inertia_kgm2` | J of the `engine`, `flywheel`, `hub` and `generator`, kg m2 |
| `crankshaft`, `generator_shaft` | each connection's `stiffness_Nm_per_rad` and `damping_Nms_per_rad` |
| `coupling` | `stiffness_Nm_per_rad` (k_ref, at `reference_C`), `damping_Nms_per_rad`, `softening_per_K` (a), `reference_C` (T_ref), `heat_capacity_J_per_K` (C_th), `cooling_W_per_K` (G) |
| `engine_damping_Nms_per_rad` | c_e |
| `ambient_C` | T_air |
| `start_C` | the rubber temperature when the sequence starts |
| `orders` | for each excitation order: `order` (k), `amplitude_Nm` (T_k), `phase_deg` (psi_k, degrees) |

## runs.csv

One row for each run, in the order the runs follow one another.

| column | meaning |
|---|---|
| `run` | the run's name |
| `n_start_rpm`, `n_end_rpm` | starting and final speed |
| `ramp_s` | ramp D |
| `hold_s` | hold H at the final speed |

## Results

The results of a package are a CSV table with the header

    run,crankshaft_kNm,coupling_kNm,generator_shaft_kNm,rubber_C

and one row for every run of `runs.csv`: the peak torques and the rubber temperature of TS-4 section 6.

## Packages on file

`examples/set_03` and `examples/set_08` are sequences that have been worked out: each holds `expected.csv`,
its results to TS-4. `pending/set_11` and `pending/set_13` have not been worked out yet.
