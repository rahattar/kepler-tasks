# Heat network packages

A network's records for one calculation to HN-3 come as a package: a folder holding the files below. Every
CSV has a header row. Names of nodes, pipes and substations are unique within a package.

| file | contents |
|---|---|
| `network.json` | `district`, the network's name; `plant_node`, the node the plant feeds; `ground_C`, the ground temperature; `hours`, the length of the record |
| `nodes.csv` | `node`: every node of the network |
| `pipes.csv` | `pipe`, `from_node`, `to_node`, `length_m`, `volume_m3`, `loss_time_h` (tau of HN-3 section 4, hours). The row describes the supply pipe and its return pipe alike. `from_node` and `to_node` name the ends; they say nothing about the direction of flow. |
| `substations.csv` | `substation`, `node` (the node the register has it connected at), `return_C` (T_r), `valve_capacity` (K of section 3, kg/s per Pa^0.5), `bypass_resistance` (R_b of section 3 for its bypass, closed, as fitted) |
| `campaign_pipes.csv` | `campaign`, `pipe`, `flow_kg_s`, `drop_Pa`: the network's hydraulic campaigns. In each campaign every pipe's flow (from `from_node` to `to_node`, so negative the other way) and its supply drop p_from - p_to were logged at the same moment, the flow within 0.1 per cent and the drop within 0.2 per cent. |
| `campaign_flows.csv` | `campaign`, `item` (a substation, or `plant`), `flow_kg_s`, `dp_Pa`: in the same campaigns, each substation's metered flow, within 0.1 per cent, and the plant's total flow and its pressure difference (`dp_Pa`, given for the plant only). |
| `demand.csv` | `time_h`, `substation`, `heat_kW`: a substation's heat demand from that time until its next row |
| `plant.csv` | `time_h`, `supply_C`, `dp_Pa`: the plant's supply temperature and its supply-return pressure difference from that time until the next row |
| `initial.csv` | `kind` (`pipe` or `node`), `name`, `network` (`supply` or `return`), `temp_C`: the temperature of the water filling each pipe as the record opens, and each node's temperature for step 0 |
| `points.csv` | `point`, `time_h`, `item` (a substation, or `plant`), `quantity` (`supply_C`, `return_C` or `heat_kW`): the results wanted, as HN-3 section 6 defines them |

Every schedule has a row at time 0. The campaigns were made in the weeks before the record; no pipe or substation was worked on between the
campaigns and the end of the record. A package holds up to 1,000 pipes, 800 substations, a record of up to
96 hours and up to 60,000 points.
