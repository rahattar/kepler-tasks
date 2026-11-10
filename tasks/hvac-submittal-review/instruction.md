Tallgrass Community College District is renovating and extending Whitlock Hall, built in 2004. The design-build mechanical contractor has submitted cooling load calculations and selections for seven new packaged rooftop units, RTU-1 through RTU-7. Decide whether each selection is acceptable under the District's standard, the contract documents and the building as it exists.

The review package is under `/app/data`; the District's standard, `/app/data/owner/design_standard_23_05_10.docx`, sets the method this review must follow.

Run `start-verification` to start the facilities office's field-verification service; the `VERIFY_URL` environment variable gives its address. `GET $VERIFY_URL/status` lists the available items, including rooms, roof levels and existing units, and the number of verifications remaining. `GET $VERIFY_URL/verify?item=<id>` returns the office's field report for that item in the standard's terms: areas, glazing, roof assembly, current occupancy, nameplate equipment and what serves the room. At most 8 items can be verified for this review; requesting an item again does not use another verification.

Write `/app/review.json` as a JSON object covering RTU-1 through RTU-7, with `submittal` set to `approve` or `return_for_revision`. The layout below shows the required structure:

    {
      "units": {
        "RTU-1": {"verdict": "...", "outdoor_air_l_s": 0.0, "coil_entering_wb_c": 0.0,
                  "block_total_kw": 0.0, "block_sensible_kw": 0.0, "block_latent_kw": 0.0,
                  "net_capacity_total_kw": 0.0, "net_capacity_sensible_kw": 0.0, "net_capacity_latent_kw": 0.0},
        ...
        "RTU-7": {...}
      },
      "submittal": "approve" | "return_for_revision"
    }

For each unit, `verdict` must be `accept`, `reject_undersized`, `reject_oversized` or `undetermined`, as defined by the standard. A determined unit reports its outdoor air intake flow in `outdoor_air_l_s` (L/s), its coil entering wet bulb in `coil_entering_wb_c` (C), its design block loads in `block_total_kw`, `block_sensible_kw` and `block_latent_kw`, and the selected unit's net capacities in `net_capacity_total_kw`, `net_capacity_sensible_kw` and `net_capacity_latent_kw`, all in kW and using the standard's definitions. An undetermined unit carries no quantities; its `missing` value names the information the documents do not provide and must be `tenant_fitout_loads`, `envelope_areas`, `catalogue_data` or `design_conditions`.

Each verdict and quantity must be the one the standard's method gives for the building as it exists, each undetermined unit must carry the correct missing-information code, and the overall submittal decision must follow from the standard. `/app/review.json` must be a regular file holding only the keys described above, each exactly once, with every quantity a finite number.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
