# Boring practice, press overhaul line

Process engineering note PE-114, issued with the overhaul machining records.

## What one setup leaves on the features finished in it

The borers on this line hold a casting once and finish every feature of a setup before the clamps are
released. The machining log records which features those are, setup by setup.

The lobing left on a feature is a property of the setup rather than of the feature. It comes from the bar's
deflection as the insert goes round, from the way the casting is held, and from the state of the insert, and
none of that changes between one feature and the next of the same clamping. The shop has checked this
repeatedly on scrap and on production parts: two features finished in one setup carry the same undulations per
revolution at the same amplitudes, within the repeatability of the measurement. Nothing is implied about two
features finished in different setups, on different machines, or on different days, even where they are the
same size and the same drawing calls them out alike.

Three things do **not** carry across the features of a setup, and have to come from the feature itself.

- **Where the pattern sits.** The machine's angular reference and the measuring instrument's are unrelated, and
  a part is clamped on the instrument wherever it comes to rest, so the pattern appears at a different angle in
  each record. What two features of one setup share is the shape of the lobing and its size, not its angular
  position.
- **The diameter.** The bar is set for each feature, and the insert wears, so size is a feature's own.
- **The taper.** Taper is the bar's axis against that one feature's length, so each feature has its own, and a
  feature's taper has to be read from a measurement of that feature.

## Rework

A feature re-worked after its setup no longer carries that setup's lobing: honing, lapping or a second boring
pass puts its own signature on the surface. Where the log shows a feature re-worked, treat the setup it was
originally finished in as telling nothing about the surface it now has. A hone is also the wrong tool for
taper, and does not correct it.
