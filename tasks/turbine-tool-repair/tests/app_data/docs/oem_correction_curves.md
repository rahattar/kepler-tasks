# GT-1 correction curves (OEM performance document, gas fuel, base load)

Each factor is the ratio of gross output at the reference power factor (or of heat rate) at the stated condition to
its value at the reference condition, with all other parameters at reference. Ambient pressure: output is proportional
to ambient pressure and heat rate does not change. Interpolate linearly between tabulated points.

## Compressor inlet temperature

| CIT (degC) | output factor | heat rate factor |
|---|---|---|
| -5 | 1.1300 | 0.9660 |
| 0 | 1.1001 | 0.9730 |
| 5 | 1.0685 | 0.9810 |
| 10 | 1.0351 | 0.9900 |
| 15 | 1.0000 | 1.0000 |
| 20 | 0.9631 | 1.0110 |
| 25 | 0.9245 | 1.0230 |
| 30 | 0.8841 | 1.0360 |
| 35 | 0.8420 | 1.0500 |
| 40 | 0.7981 | 1.0650 |

## Inlet loss

| inlet loss (kPa) | output factor | heat rate factor |
|---|---|---|
| 0.0 | 1.0145 | 0.9950 |
| 0.5 | 1.0072 | 0.9975 |
| 1.0 | 1.0000 | 1.0000 |
| 1.5 | 0.9928 | 1.0025 |
| 2.0 | 0.9855 | 1.0050 |
| 2.5 | 0.9782 | 1.0075 |
| 3.0 | 0.9710 | 1.0100 |

## Exhaust loss

| exhaust loss (kPa) | output factor | heat rate factor |
|---|---|---|
| 0.0 | 1.0165 | 0.9850 |
| 1.0 | 1.0110 | 0.9900 |
| 2.0 | 1.0055 | 0.9950 |
| 3.0 | 1.0000 | 1.0000 |
| 4.0 | 0.9945 | 1.0050 |
| 5.0 | 0.9890 | 1.0100 |
| 6.0 | 0.9835 | 1.0150 |

## Ambient specific humidity

| specific humidity (kg/kg dry air) | output factor | heat rate factor |
|---|---|---|
| 0.002 | 0.9987 | 1.0002 |
| 0.004 | 0.9993 | 1.0001 |
| 0.006 | 0.9999 | 1.0000 |
| 0.008 | 1.0005 | 0.9999 |
| 0.010 | 1.0011 | 0.9999 |
| 0.012 | 1.0017 | 0.9998 |
| 0.014 | 1.0023 | 0.9997 |
| 0.016 | 1.0029 | 0.9996 |
| 0.018 | 1.0035 | 0.9995 |
| 0.020 | 1.0041 | 0.9995 |
