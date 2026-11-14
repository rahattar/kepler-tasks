# Heat network packages

A network's records for one calculation to HN-3 come as a package: a folder holding the files below. Every
CSV has a header row. Names of nodes, pipes and substations are unique within a package.

| file | contents |
|---|---|
| `network.json` | `district`, the network's name; `plant_node`, the node the plant feeds; `ground_C`, the ground temperature; `hours`, the length of the record |
| `nodes.csv` | `node`: every node of the network |
| `pipes.csv` | `pipe`, `from_node`, `to_node`, `length_m`, `volume_m3`, `resistance_Pa_s2_kg2` (R of HN-3 section 3, Pa per (kg/s)^2), `loss_time_h` (tau of section 4, hours). The row describes the supply pipe and its return pipe alike. `from_node` and `to_node` name the ends; they say nothing about the direction of flow. |
| `substations.csv` | `substation`, `node`, `return_C` (T_r), `valve_capacity` (K of section 3, kg/s per Pa^0.5) |
| `demand.csv` | `time_h`, `substation`, `heat_kW`: a substation's heat demand from that time until its next row |
| `plant.csv` | `time_h`, `supply_C`, `dp_Pa`: the plant's supply temperature and its supply-return pressure difference from that time until the next row |
| `initial.csv` | `kind` (`pipe` or `node`), `name`, `network` (`supply` or `return`), `temp_C`: the temperature of the water filling each pipe as the record opens, and each node's temperature for step 0 |
| `points.csv` | `point`, `time_h`, `item` (a substation, or `plant`), `quantity` (`supply_C`, `heat_kW` or `return_C`): the results wanted, as HN-3 section 6 defines them |

Every schedule has a row at time 0. A package holds up to 1,000 pipes, 800 substations, a record of up to
96 hours and up to 40,000 points.
