The screen house needs a fatigue damage total for each of its ten vibrating screens, S1 to S10. For each screen's monitored gusset weld toe, report the Miner's sum under the plant's fatigue standard from the weld's entry into service through the end of October 31 2026. The available site records are in `/app/data`.

One field program can be booked with the contractor for the November outage, with up to three tests across the whole screen house. Order it once through the `fieldwork` command. Once placed, the order cannot be changed or extended; results go to `/app/fieldwork/`.

Put all ten estimates in `/app/output/damage.json`, using a single JSON object keyed by screen, such as `{"S1": 0.25, ...}`. Include every screen exactly once. Each estimate must be within 20% of that screen's true damage.

You have 10800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
