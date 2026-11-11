# Instrument notes, shop metrology (issued with the inspection report)

## The instruments

- **RT-1 form tester**, 1 mm ball stylus, 1800 points a revolution, the shop's own machine and the only form
  tester on the floor. Radial scale calibrated against a reference hemisphere, so its records carry absolute
  radius, traceable to 0.2 um. Repeatability on a section, one standard deviation: 0.12 um. A record's angle is
  the spindle's angle, from the spindle encoder's zero; a part is clamped wherever it comes to rest. Its spindle
  error motion was last certified in 2019 and the certificate has not been renewed.
- **CMM-4 coordinate machine**, 1 mm probe, bore and journal program. The program takes 12 touch points a
  revolution at each section, which is what the cycle time allows on the floor. Its radii are absolute and
  traceable to 0.3 um.

## What the software reports

Both the form tester's software and the coordinate machine's bore program report, by default:

- **roundness** as the radial separation of the measured profile about its **least-squares** circle, section by
  section, after the same 2 to 50 UPR filter FM-7 describes. It reports this figure whatever form characteristic
  the drawing calls for, and it has no cylindricity option fitted;
- **diameter** as the **mean** of the measured radii of a section, doubled, averaged over the sections.

Those are the figures in the inspection report. Neither default is the reference figure FM-7 requires, and the
shop has no licence for the minimum-zone and gauge-size options.

## Temperature

The shop floor is not controlled. The room temperature at the time of each measurement is in
`measurement_index.csv`, from the wall instrument beside the machine, to 0.1 C. The parts were left to stand
overnight in the same room, so part and room are at the same temperature.
