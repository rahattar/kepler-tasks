# GD-3: Design-day pressures in an intermediate-pressure network

## 1 Scope
GD-3 gives the lowest pressure at the inlet of every district governor of an intermediate-pressure network on
the network's design day, from the network's records. It covers networks held between 2 and 7 bar gauge, fed
from the transmission system through pressure-reducing stations (PRS) and joined to neighbouring networks
only through boundary valves. The gas has a relative density of 0.6 and is taken as an ideal gas at 15 C
throughout the network.

Records give gauge pressures in bar. The equations below use absolute pressure, p = p_gauge + 1.01325 bar.
Flows are in m3/h at standard conditions, 15 C and 1.01325 bar.

## 2 Mains
A main joins two nodes and has a direction, from its `from` node to its `to` node. Its flow Q is positive in
that direction, and

    p_from^2 - p_to^2 = K Q |Q|^0.82

where K is the main's resistance. A main's K comes from a survey of the main: the pressures at its two ends
and the flow through it, read together, give K = (p_from^2 - p_to^2) / (Q |Q|^0.82). The main's latest survey
is used.

Renewing a main, relining it or laying it makes a main whose K no earlier survey measured: its K comes from a
survey made after the work. Inspections and repairs leave a main's K as it was.

## 3 Linepack
The gas in the mains is held at the nodes. A node holds half the geometric volume of every main it joins,

    V = sum of pi D^2 L / 8

with D the main's internal diameter and L its length, and the gas held at the node is V p / 1.01325 m3 at
standard conditions.

## 4 Nodes
At every node and at every moment, the flow arriving through mains and boundary valves, plus what a PRS at the
node delivers, less the demand taken at the node, is the rate at which the gas held at the node grows.

## 5 Pressure-reducing stations
A PRS delivers gas from the transmission system into its node. It holds the node at its set point while doing
so needs a delivery between nothing and its capacity. Where holding the set point would need more than its
capacity, the PRS delivers its capacity and the node stands below the set point. Where the node would stand
above the set point with nothing delivered, the PRS delivers nothing: a PRS never takes gas back from the
network.

## 6 Boundary valves
A boundary valve joins a node of the network to a neighbouring network, whose pressure at the valve is held at
the value in the register by the neighbour's own PRS. A closed valve passes nothing. A valve that passes gas is
taken as a main between its node and the neighbouring network that holds no gas, its K found by a survey across
it: the pressures on its two sides and the flow through it, read together.

## 7 Demand
A district governor takes its design-day demand for each hour, from the package, whatever the pressure.

A large customer takes, in each hour of the design day, the mean of the flow it takes in the same hour of the
day on the weekdays (Monday to Friday) of its meter record.

Demand is steady within each hour.

## 8 The design day
The design day runs from 06:00 to 06:00. It is one of a run of identical days: the state of the network at the
end of the day is its state at the start.

The day is calculated in 240 steps of 0.1 h. Each step is implicit: its flows, PRS deliveries and rate of
growth of the gas held at each node are those of the pressures at the end of the step, with the demand of the
hour the step lies in. Every PRS keeps the set point and capacity of the register through the day.

## 9 Results
The result for a district governor is the lowest pressure at its node, in bar gauge, at the ends of the 240
steps of the design day. Calculations are carried to within 0.001 bar.
