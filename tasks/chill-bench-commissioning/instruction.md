Wafers leaving anneal are cooled at a vacuum chill station before they return to the carrier. They sit on proximity pins above a temperature-controlled plate, with backside helium carrying heat away. It is required that the wafers have a uniform temperature profile, to prevent an acceptable average temperature from hiding a hot region at hand-off.

Sixteen stations have just been installed, and the job is to commission all sixteen. Each has an incoming-inspection report, but none has had a wafer run on it; there is no thermal data anywhere in `/data`. The single source of thermal measurement is the bench, and it has a shared budget of eight runs for sixteen stations that does not refill.

The reports are saved in the `/data/stations.json` file, and these reports give the inner and outer standoff for each station. Wafer and chamber properties are included in the `/data/wafer.json` file, and the file `/data/spec.json` has the production requirements in machine-readable form.

The bench client at `/app/bench.py` provides a status query and accepts run requests in this form:

```
/app/bench.py status
/app/bench.py run --station S03 --pressure 12.0 --seconds 20
```

Each accepted run costs one budget unit and places an instrumented test wafer on one station at the requested helium pressure for a chosen duration between 0.5 and 30 seconds. It logs four temperatures at 10 Hz: the wafer mass mean, inner-zone and outer-zone means, and the plate RTD temperature. Test wafers are scrap, so a bench run need not meet the production thermal limits. There is no budget cost for a request refused for an unknown station, a pressure outside the supply range or an invalid duration.

Each plate has two machined concentric zones with a step in standoff at r = 75 mm; its inspection report gives both standoffs in micrometres. In the bench logs and the production checks, `T_mean_C` is the mass-mean wafer temperature, `T_inner_C` is the area-mean temperature over r < 75 mm, and `T_outer_C` is the area-mean temperature over r >= 75 mm.

Write one recipe for each station to `/app/recipe.json`, with helium pressure in Torr and dwell time in seconds. Include S01 through S16 exactly once. The two entries below illustrate the format:

```json
{
  "stations": [
    {"station": "S01", "he_pressure_torr": 11.6, "dwell_s": 7.64},
    {"station": "S02", "he_pressure_torr": 9.3, "dwell_s": 9.2}
  ]
}
```

At every station, `T_mean_C` must be at or below 50.0 C when the dwell ends. The absolute difference between `T_inner_C` and `T_outer_C` must stay at or below 25.0 K throughout the entire dwell. Helium pressure must be between 3.0 and 60.0 Torr. Shorter dwell is better, and each station's dwell must be within 8% of the shortest dwell that station could achieve while meeting both thermal limits at any permitted pressure. This allowance applies per station: spare margin at one station cannot offset an overrun at another. At least fifteen of the sixteen stations must meet all the requirements above.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
