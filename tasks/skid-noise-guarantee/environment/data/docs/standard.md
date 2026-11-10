# Plant standard NS-7: the sound power of a machine in the compressor hall

The sound power level of a packaged machine is determined in each octave band from 63 Hz to 8 kHz, and as an
A-weighted level, from the sound pressure levels measured on a measurement surface around it while it runs alone.
Levels are in decibels. The machine is taken as it stands at the date of the determination.

## 1 The measurement surface

The surface is the one through the positions of the machine's array, at the radius the array was set at. A machine
standing 1.5 m or more from every wall radiates into a half space and its surface area is 2 pi r^2. A machine standing
closer than that to a wall radiates into a quarter space: its surface area is pi r^2 and its positions lie on the
available arc.

## 2 Valid positions

A position lies on the measurement surface. A position set at another radius is not a valid position. A position at
which the level with the machine running exceeds the level with every machine off by less than 6 dB in any band is
not a valid position. At least 6 valid positions are needed.

## 3 Reduction

At each valid position the level with every machine off is subtracted from the level with the machine running, band by
band and position by position, in energy. The surface sound pressure level of the band is the energy average of those
levels over the valid positions:

    Lp = 10 lg ( (1/N) sum 10^(0.1 Lp,i) )

and the sound power level of the band is

    Lw = Lp + 10 lg (S / S0) - K2,   S0 = 1 m2

where K2 is the environmental correction of the hall,

    K2 = 10 lg (1 + 4 S / A).

A is the equivalent absorption area of the hall in that band, as the hall is at the date of the determination. It is
determined either from the hall's reverberation time T,

    A = 0.161 V / T,

with V the volume of the hall, or from a source of known sound power level standing in the hall, by the same relation
between level and surface as above applied to that source. The sound field of the hall away from the machines is
diffuse, so one station is enough for a reverberation measurement.

## 4 Corrections

The correction on the certificate of the instrument that took a level is added to the level as indicated.

Levels measured with the machine at a speed other than its rated speed are referred to the rated speed by adding

    50 lg (n_rated / n)

to every band.

Where a machine has been modified since the levels were measured, those levels are referred to the machine as it
stands now by adding, band by band, the difference between the level measured now and the level measured then at one
position of its own array, the hall being unchanged between the two. Where the modification is a part whose insertion
loss is certified by its supplier, the certified figures may be used in place of that measurement.

## 5 The A-weighted level

    LwA = 10 lg sum 10^(0.1 (Lw + Aw))

over the eight bands, with the weightings

| Band (Hz) | 63 | 125 | 250 | 500 | 1k | 2k | 4k | 8k |
|---|---|---|---|---|---|---|---|---|
| Aw (dB) | -26.2 | -16.1 | -8.6 | -3.2 | +0.0 | +1.2 | +1.0 | -1.1 |

## 6 Repeatability

One reading of a band level by a class 1 instrument on a steady source repeats to 0.15 dB, one standard deviation. One
reverberation time reading repeats to 2 per cent.
