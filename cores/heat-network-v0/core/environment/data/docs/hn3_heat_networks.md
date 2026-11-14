# HN-3: Calculation of hot-water heat networks

Revision 4. Applies to every calculation of supply temperatures and delivered heat made for the group's heat
networks, for planning, for complaints and for the annual loss statement.

## 1. Scope

A heat network carries hot water from one plant through a network of supply pipes to substations, and back
through a network of return pipes laid alongside. Every supply pipe has a return pipe of the same length,
volume, resistance and loss time constant between the same two nodes, so the return network is the supply
network with every flow reversed. Each substation stands at one node and takes water from the supply pipes
there and gives it back to the return pipes there.

The supply network may have loops. Every pipe in it can carry water in either direction, and in a pipe that
is part of a loop the direction can change as the demands move. Every substation's heat demand is above zero
at all times, and at every node the supply temperature stays at least 15 K above the return temperature of any
substation there.

In every network the standard is applied to, no pipe passes a volume of water as large as its own volume in one
calculation step (section 5).

## 2. Units and constants

Temperatures in deg C, heat in kW, mass flow in kg/s, pressures in Pa, volumes in m3, times in hours from the
start of the record unless a column says otherwise. Water has density 975 kg/m3 and specific heat
4.19 kJ/(kg K) throughout.

## 3. Hydraulics

The plant holds the difference between its supply and its return pressure at the value its log gives. A pipe
carrying mass flow m from its node u to its node v loses p_u - p_v = R m |m| in the supply and the same in its
return pipe from v to u. Mass is conserved at every node.

A substation at node n wants the mass flow

    m_want = Q / (c (T_n - T_r))

where Q is its heat demand, c the specific heat, T_n the supply temperature at its node and T_r its return
temperature. Its control valve passes at most

    m_max = K sqrt(dp)

where K is the valve capacity and dp the difference between the supply and the return pressure at its node.
It takes the smaller of the two: m = min(m_want, m_max). Where dp is not above zero it takes nothing.

The supply pressures, the return pressures, every pipe's flow and every substation's flow are the one state
that satisfies all of the above together.

## 4. Heat transport

Water moves through a pipe as a plug: it neither mixes along the pipe nor overtakes itself. Water that enters
a pipe at temperature T_0 at time t_0 has, at any later time t while it is still in the pipe, the temperature

    T = T_g + (T_0 - T_g) exp(-(t - t_0) / tau)

where T_g is the ground temperature of the network and tau the pipe's loss time constant.

Water arriving at a node from all the pipes and substations that feed it is mixed completely. The water that
leaves the node, into pipes and into substations, leaves at the mixed temperature. At the plant, the plant adds to its supply node the water that the network takes from it, at the supply
temperature its log gives.

## 5. Calculation steps

The calculation runs in steps of 120 s from the start of the record. Within a step every flow is constant.
Step k runs from t_(k-1) to t_k. In each step, in this order:

1. Every substation takes for T_n the supply temperature at its node from step k - 1, and for Q its demand as
   the log gives it at t_(k-1). With the plant's pressure difference at t_(k-1), the hydraulic state of
   section 3 gives every flow for the step.
2. In every supply pipe a volume of m * 120 / 975 moves along. The water that leaves the pipe in the step is the
   part of the plug at its outlet end of that volume; its temperature is taken at t_k, as section 4 gives it for
   each part, and averaged by volume.
3. At every supply node the water that arrives in the step, from pipes and, at the plant, from the plant at
   its supply temperature at t_(k-1), is mixed. That is the node's supply temperature for step k. All water leaving the node in the step, into pipes
   and into substations, leaves at that temperature, and the water entering a pipe in the step is taken to enter
   at t_k.
4. A substation delivers in the step the heat m c (T_n - T_r), with m its flow for the step and T_n the supply
   temperature at its node for step k. It gives its flow back to the return network at its return temperature.
5. The return network is carried through the step in the same way: pipe outflows as in 2, and at every return
   node the water from return pipes and from substations mixed as in 3. The mixed temperature at the plant's
   return node is the plant's return temperature for step k.

A node at which no water arrives in a step keeps its temperature from the step before.

As the record opens, at t_0 = 0, every pipe is full of water at one temperature and that water is taken to
have entered at t_0. The package gives it, and the supply temperature of every node for step 0.

## 6. Results

At each survey time, which is a whole hour of the record:

- `supply_C` of a substation: the supply temperature at its node for the step that ends at that time;
- `heat_kW` of a substation: the heat it delivered over the hour that ends at that time, divided by 3600 s;
- `return_C` of the plant: the plant's return temperature for the step that ends at that time.

A calculation made to this standard reproduces these to 0.01 K and 0.01 per cent.
