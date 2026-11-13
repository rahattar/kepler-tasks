# VS-4: Airflow in a ventilation district

## 1 Scope
VS-4 gives the airflow in every branch of an underground ventilation district from the district's network,
the catalogue characteristics of its fans and the settings of its regulators and doors. It covers districts
exhausted by main fans standing in parallel at one fan house. The air is taken as incompressible at the
standard density of 1.2 kg/m3, and natural ventilation pressure is left out.

Every district the standard is applied to keeps each of its fans between shutoff and free delivery of its
catalogue table at all times, and all its fans run throughout a record.

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
- An airway has the resistance given for it.
- A regulator has the resistance of the setting it stands at, from its table.
- A door has its closed or its open resistance. A closed door leaks.
- A fan branch has the resistance of the fan's ducting, in series with the fan. The fan acts in the direction
  of its branch.

## 4 Fans
A fan's characteristic is the catalogue table of its model at its blade setting: fan pressure in Pa against
the airflow through the fan in m3/s, from shutoff to free delivery. Between tabulated points the
characteristic is the straight line joining them.

## 5 Settings
At any time every regulator and door stands at the setting of its latest entry in the district's log.
Regulators are wound and doors are swung by hand. A change takes a minute or more, the air follows within
seconds, and entries are at least 10 minutes apart, so the flow in the district is steady at every moment.

## 6 Results
The result for a survey point is the airflow in its branch at its time, in m3/s, signed in the branch's
direction. Calculations are carried far enough that a result is within 0.1 per cent of the airflow that
satisfies section 2.
