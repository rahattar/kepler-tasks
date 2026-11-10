For each outlet element in Boiler B2's secondary superheater, determine the consumed creep life fraction at the crown of its outlet leg. The ten elements are E1 to E10; each figure is a Robinson sum under the plant's standard, covering that tube's entry into service through the end of October 31 2026. The site records in /app/data are read-only.

The outage allows up to two measurements across the whole superheater, booked together in a single inspection order through fieldwork. The order can be placed only once, with no changes or additions afterward. fieldwork status lists the available test types and the budget. Submit the plan on standard input to fieldwork submit; its error message gives the plan format. Results go to /app/fieldwork/.

Save the ten figures in /app/output/damage.json as one JSON object keyed by element, such as {"E1": 0.25, ...}. Include each element exactly once. Every figure must be within 25% of that element's true consumed creep life fraction.

You have 10800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
