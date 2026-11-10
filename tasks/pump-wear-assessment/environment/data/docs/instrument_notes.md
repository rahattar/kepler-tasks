# Pump bank DCS instruments: service notes

- Suction pressure transmitters PT-x01 (one per pump), 0-200 kPa, +-0.1 % of span.
- Discharge pressure transmitters PT-x06 (one per pump), 0-1000 kPa, +-0.1 % of span, unless the maintenance log
  says otherwise. The DCS scales each transmitter's 4-20 mA signal over the range configured for its tag.
- Header flow: FT-100, a magnetic flowmeter on the common discharge header, is the only flow measurement on the
  bank; individual pump flows are not measured.
- Speed: the fixed-speed pumps log 1480 rpm when running; P9's speed is the VFD's output.
- Portable surveys: clamp-on transit-time flowmeter, +-0.5 % of reading on a clean straight run; hourly means. It
  measures the mean water velocity and reports flow as that velocity times the bore computed from the pipe data
  keyed in at setup.
- Trends: hourly averages, 2026-09-21 08:00 to 2026-10-19 07:00. One file per pump (state, speed, suction and
  discharge pressure) and one for the header (flow, number of pumps running).
