# Pair packages

A package is a folder with three files.

`pair.json`, one JSON object:
- `pair`: the pair's tag. `face_width_mm`, `ratio` (wheel teeth over pinion teeth), `mesh_stiffness_N_mm_um`
  (c' of GF-4), `Z_MPa_sqrt` (Z of GF-4 section 6), `reference_C`, `thermal_um_per_K`.
- `pinion`: `base_diameter_mm`, `pitch_diameter_mm`, `body_diameter_mm`, `teeth`, `mounting` (`straddle` or
  `overhung`), `datum_to_bearing_mm` (a of GF-4 section 3), `bearing_span_mm` (straddle only), and
  `working_flank` (`L` or `R`, GF-4 section 1).
- `wheel`: `teeth` and `working_flank`.
- `pattern_check`: `force_N`, the check force, and `from_mm`, `to_mm`, the recorded extent of the marking.

`lead_charts.csv`: the lead charts from the gears' inspection records, one row a station:
`gear` (`pinion` or `wheel`), `tooth` (the tooth's number), `flank` (the flank as the record names it, `L` or
`R`), `x_mm`, `dev_um`. Each charted tooth has both flanks charted at the same stations.

`duty.csv`: the duty record, one row a point: `point`, `torque_Nm` (pinion torque), `oil_C`.

The two packages in `examples` also hold `expected.csv`, their results to GF-4 in the columns
`point,k_face,sigma_H_MPa`. The package in `pending` is a pair not yet calculated: it has no results.
