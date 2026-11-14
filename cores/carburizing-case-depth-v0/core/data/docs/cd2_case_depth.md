# CD-2: Carbon profile and effective case depth of carburized loads

Works standard, revision 4. It gives the surface carbon and the effective case depth of each load carburized in
a batch furnace, from the furnace's record of the load's cycle.

## 1. Scope

A load is carburized in one charge, from charging to quench. Its parts are taken as one section: a section of
8 mm or more is carburized from one face into a depth of 4 mm, with no flux at that depth; a thinner section is
carburized from both faces, and is taken over half its thickness with no flux at its centre.

## 2. Carbon in the steel

Carbon C (wt %) diffuses from the surface,

    dC/dt = d/dx ( D dC/dx ),

with x the depth below the surface (mm). D is Tibbetts' diffusivity of carbon in austenite:

    D = 47 exp(-1.6 C) exp( -(37000 - 6600 C) / (1.987 T) )      mm^2/s,  T in K.

The load is at the furnace temperature throughout. At charging the steel is at its grade's core carbon.

## 3. The surface

The flux of carbon into the steel at the surface is

    J = beta ( f Cp - C_s ),

with Cp the carbon potential of the furnace atmosphere, f the grade's alloy factor, C_s the surface carbon and
beta the furnace's mass transfer coefficient (mm/s).

## 4. Results

For each load at the end of its cycle: the surface carbon (wt %) and the effective case depth, the depth at
which the carbon falls to 0.35 per cent (mm).

The results are those of the continuous problem; a calculation on nodes in depth and steps in time is fine
enough when halving both moves no result by more than 0.2 per cent.
