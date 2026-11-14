# VS-4: Airflow in a ventilation district

## 1 Scope
VS-4 gives the airflow in every branch of an underground ventilation district from the district's network,
the resistances of its branches, the catalogue characteristics of its fans and the settings of its regulators
and doors. It covers districts exhausted by main fans standing in parallel at one fan house. The air is taken
as incompressible at the standard density of 1.2 kg/m3, and natural ventilation pressure is left out.

Every district the standard is applied to keeps each of its fans between shutoff and free delivery of its
catalogue table at all times, and all its fans run throughout a record. In no steady state of a record does a
fan run between the lowest point of the dip in its characteristic and the peak (section 4).

## 2 The network
A district is a set of nodes joined by branches. A branch has a direction, from its `from` node to its `to`
node, and its airflow q, in m3/s, is positive in that direction. The surface is one node, `ATM`. Pressures are
gauge pressures in Pa: p = 0 at `ATM`.

In steady flow
- at every node the airflows in and out balance, and
- along every branch p_from - p_to = R q |q| - P_fan(q),

where R is the branch's resistance in N s2/m8 and P_fan is the pressure of the fan standing in the branch,
zero where there is none.

## 3 Resistances
- An airway's resistance is found by a pressure-quantity survey: the pressure difference dp between its ends
  and the airflow q through it, read together, give R = dp / (q |q|). The airway's latest survey is used.
  Re-supporting or enlarging an airway changes its resistance. A survey made before such work does not
  describe the airway that is there now, and its resistance has to come from a survey made since.
- A stopping closes a cut-through between an intake and a return airway, and leaks. Stoppings are not taken in
  a district's survey campaigns. The register carries the resistance each stopping was built to.
- A regulator has the resistance of the setting it stands at, from its table.
- A door has its closed or its open resistance. A closed door leaks.
- A fan branch has the resistance of the fan's ducting, from the register, in series with the fan. The fan
  acts in the direction of its branch.

## 4 Fans
A fan's characteristic is the catalogue table of its model at its blade setting: fan pressure in Pa against
the airflow through the fan in m3/s, from shutoff to free delivery. Between tabulated points the
characteristic is the straight line joining them.

The characteristics of the fans in these districts fall from shutoff to a dip, rise to a peak and fall again
to free delivery. A fan runs on one of the two falling parts: beyond the peak, or short of the lowest point of
the dip. With more than one fan against one district, the district can have more than one steady state at the
same settings, its fans on different parts. A steady state here is one the air returns to after a small
disturbance.

## 5 Settings
At any time every regulator and door stands at the setting of its latest entry in the district's log.
Regulators are wound and doors are swung by hand. A change takes a minute or more, the air follows within
seconds, and entries are at least 10 minutes apart, so the flow in the district is steady at every moment.

As the record opens, every fan runs beyond its peak. From there the flow follows the log. While a change is
made, every fan stays on the part of its characteristic it is on, for as long as the district has a steady
state with it there. Where a change brings a fan to the end of the part it is on, to the peak from beyond it
or to the lowest point of the dip from short of it, that steady state ends: that fan crosses to the other
falling part of its characteristic, every other fan stays on its part, and the district settles in the steady
state so reached.

## 6 Results
The result for a survey point is the airflow in its branch at its time, in m3/s, signed in the branch's
direction. Calculations are carried to within 0.1 per cent.
