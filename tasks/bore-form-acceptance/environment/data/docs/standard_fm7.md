# FM-7: sentencing finish-machined bores and journals on form and size

Applies to the cylinder bores, gland bores and ram journals of the press overhaul. It fixes what a measurement of
a feature means, so that two engineers reading the same points reach the same sentence.

## 1. The assessment profile of a section

From the measured radii of one section, at angles covering one revolution:

1. take the mean measured radius of the section, and the deviation of each point from it;
2. express the deviations as a Fourier series in the angle;
3. discard order 0 and order 1. Order 1 is the eccentricity of the part on the instrument, which is a setting, not
   a property of the feature;
4. multiply the amplitude of order n by `exp(-pi (0.4697 n / 50)^2)`.

The result is the section's assessment profile. The band is 2 to 50 undulations per revolution (UPR): finer
waviness, such as the feed marks of the finishing pass, belongs to the surface texture requirement and not to
form or size. A profile cannot be assessed over this band from points that do not resolve it.

## 2. The assessment surface

A feature's assessment surface is, for each measured section, the section's mean radius referred to 20 C plus that
section's assessment profile. Form, the mating size and the local sizes are all taken on this surface.

Every size is referred to 20 C. A radius measured at T C becomes `R / (1 + 11.7e-6 (T - 20))`; 11.7 um/m K is the
coefficient of the 42CrMo4 of every part here. Form needs no temperature correction.

## 3. Form

The form error is a minimum-zone value: the smallest radial separation of two reference figures, concentric or
coaxial, that between them contain the assessment surface.

- **roundness**: two concentric circles, one section at a time, free in position. The feature's roundness error is
  the largest of its sections.
- **cylindricity**: two coaxial cylinders containing all sections at once, the axis free in position and in tilt.
  Taper and a change of profile along the feature therefore count against a cylindricity tolerance; they do not
  count against a roundness tolerance.

A least-squares reference figure is not a minimum-zone one and gives a larger value. It is not what a form
tolerance means.

## 4. Size, with the envelope requirement

Every feature on these drawings carries the envelope requirement, so size is sentenced by Taylor's principle: a
perfect mating part of the limit size must assemble, and no local size may pass the other limit.

- **mating size**: for a bore, the diameter of the largest cylinder, free in position and tilt, that lies within
  the assessment surface over all measured sections; for a journal, the diameter of the smallest such cylinder
  that contains it. This is what a plug or ring gauge of that diameter would find.
- **local size**: in one section, the distance between two diametrically opposite points of the assessment
  surface. A feature's worst local size is the largest of a bore's and the smallest of a journal's.

A mean or average diameter is neither of these. A feature whose form error is F has a mating size that differs
from its mean diameter by an amount of the order of F, so the two cannot be used in place of one another.

Accept on size:

- a **bore** when its mating size is at or above the lower limit of size, and its worst local size is at or below
  the upper limit;
- a **journal** when its mating size is at or below the upper limit, and its worst local size is at or above the
  lower limit.

## 5. The sentence

| | form within tolerance | form outside |
|---|---|---|
| **size accepted** | `accept` | `reject_form` |
| **size rejected** | `reject_size` | `reject_both` |

A feature is sentenced on the surface as it stands now. Where the records hold more than one measurement of a
feature, the one that describes its present condition governs.
