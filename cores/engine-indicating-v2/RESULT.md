# engine-indicating bare core v2 (Nov 13): low effort 1 of 3 accepted

v2 is v1's packages with the `encoder_index` entry taken out of every `engine.json`, and the format document's
two sentences on the index mark replaced by one: "The indicating system's angle for sample k (from 0) is
k/2 - 180 degrees." Records, results and reference are v1's (`cores/engine-indicating-v1`).

## Probes (opus, low effort)

| probe | time | hidden | what it did |
|---|---|---|---|
| low 1 | 7.0 min | **accepted** | "The expected results only matched once I assumed the sample angles are slightly off": it traced the examples' own index errors (+0.014 and -0.038 degrees found, 0.02 and -0.03 built), then found -1.6 in the pending package |
| low 2 | 5.1 min | 5 of 6 cells out, every row | IS-2 as written; saw the examples' angles off by 0.03 to 0.04 degrees one way per cell and did not trace it |
| low 3 | 14.2 min | 5 of 6 cells out, every row | IS-2 as written |

- **Without the entry, two of three took the index as given.** The signpost was doing most of the work in v1.
- **A sound example must be exactly sound.** The examples' index errors of 0.02 and -0.03 degrees, a tenth of a
  band, left a residual of one sign per cell in every angle. One run fitted it. A signature with feedback is
  found however small.
- The run that found it was right on all six cells (worst 0.33 of a band).

## Reading

1 of 3 is over the bar of 0. v3 makes the examples exact and adds a second condition that the same check
answers wrongly.
