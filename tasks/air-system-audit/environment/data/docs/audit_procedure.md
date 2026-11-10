# CA-2 Compressed air system audit: results

Plant procedure for the results of a compressed air system audit, from a logging period of several days.

## Definitions

- **Free air:** air volumes and flows are in free air, m3/min at the site's atmospheric conditions, the basis on
  which compressor free air delivery (FAD) is rated.
- **Demand:** the free-air flow that the plant draws from the compressed air system: production use, leaks and
  everything else downstream of the compressors.
- **Supply:** the free-air flow the compressors deliver into the system.
- **Logging period:** the time covered by every logger.

## Compressors

- A **load/unload** compressor is loaded, unloaded or stopped.
  - Loaded, it delivers its full free air delivery at its discharge pressure and draws its full-load power, both
    from its performance table.
  - Unloaded, it delivers no air. Its power falls from about 60 % to about 25 % of full-load power as its
    separator vessel blows down. After 10 minutes unloaded the motor stops.
- A **variable-speed** compressor delivers the free air that its performance table gives for the power it draws,
  between 25 and 100 % of its maximum delivery. It holds a pressure set point and stops when the demand falls
  below its minimum delivery.

A compressor's discharge pressure is the receiver pressure plus the pressure drop from the receiver to the
compressors.

## Results

The result of an audit is a JSON object with these keys:

- `avg_demand_m3_min`: mean demand over the logging period.
- `peak_demand_m3_min`: the highest mean demand over any 2-minute interval in the logging period.
- `leak_m3_min`: mean demand over the non-production hours.
- `specific_power_kw_per_m3_min`: the compressors' electrical energy over the logging period divided by the free air
  they supplied, in kW per m3/min.
