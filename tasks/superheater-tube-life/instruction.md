The October 2026 outage inspection results for Boiler B2 are in `/app/data` along with the other plant records, which are read-only. The secondary superheater has ten outlet elements, E1 to E10.

For each element, estimate the fraction of creep life used at the crown of its outlet leg under the plant's standard, `/app/data/docs/creep_life_standard.md`. The period runs from the present tube's entry into service through the end of October 31 2026.

Return `/app/output/creep_life.csv` with the header `element,life_fraction` followed by ten data rows, each element appearing exactly once. Report life used as a fraction, such as 0.25. Each estimate must be within 25% of the element's true life fraction.

You have 10800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
