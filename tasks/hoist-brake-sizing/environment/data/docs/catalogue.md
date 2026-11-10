# Spring-applied brake, series SB: catalogue notes

Electromagnetically released, spring-applied disc brake with one rotor and two organic friction linings, for mounting
on the non-drive end of the motor. Sizes, ratings, lining grade and thermal data are in `brake_catalogue.csv`.

- Rated torque: the braking torque of a bedded-in brake with its linings at 20 C at 100 % setting. The torque is set
  with the adjusting ring, from 50 to 100 % of rated torque to a whole percent, and is proportional to the setting.
- Rotor inertia: the inertia of the rotor and hub, which turn with the motor shaft.
- Engagement time: from switching off the coil supply until the brake develops its torque, for the rated torque
  (100 % setting). With switching on the DC side the coil current is interrupted directly. With switching on the AC
  side the coil current decays through the rectifier and the brake engages later. The brake does not act on the motor
  before the engagement time.
- Heat capacity: rotor, linings and armature plate together, which heat up with each stop.
- Heat dissipation: the heat flow from the brake to the surrounding air per kelvin of lining temperature above it.
- Lining temperature limit: 300 C.
