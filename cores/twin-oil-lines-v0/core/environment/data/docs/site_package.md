# Site package

A site sends the heated oil lines on its register in as one package, a directory of four files.

| file | columns |
|---|---|
| `site.json` | `site`, the site's name; `lines` and `records`, the number of lines and of records in the package |
| `oils.csv` | `oil`; `density_kg_m3`; `cp_J_kgK`, the specific heat; `k_W_mK`, the thermal conductivity; `nu50_cSt` and `nu100_cSt`, the kinematic viscosity at 50 C and at 100 C (TS-2 section 2) |
| `lines.csv` | `line`; `pipes`, 1 for a single pipe and 2 for a pair (TS-2 section 4); `bore_mm` and `length_m` of a pipe; `u_o_W_m2K`, the outside coefficient of a pipe referred to its bore (TS-2 3.2); `oil`, as named in `oils.csv` |
| `records.csv` | `record`; `line`; `hour`, counted from the start of the line's survey; `flow_t_h`, the oil delivered to the line's inlet manifold in t/h; `t_in_C`, its temperature there; `t_amb_C`, the temperature of the line's surroundings |

The records of a line are the hourly readings of one survey, an unbroken run of hours in time order, taken with
the line in service throughout and its conditions steady at each reading.

The results of a package are one row for each row of `records.csv`: `record`, `dp_kPa` and `t_out_C`, the two
results of TS-2 section 5.

The packages under `examples/` have been calculated: each holds `expected.csv`, its results to TS-2. The
package under `pending/` has not been calculated yet.
