# Site data

## Datum and the utility's transmitter

Pressures on the site are referred to the **site datum**, the finished floor level of the riser rooms, which is
one level across the site. The yard hydrants' outlets are taken as at the datum.

The utility's transmitter PT-0 is on the city main in the connection pit, **8.0 ft below the site datum**. Its
record is the transmitter's own reading. Water stands at 0.433 psi per ft.

## Pipe

| material | nominal size, in. | internal diameter, in. |
|---|---|---|
| CI | 6 | 6.00 |
| CI | 8 | 8.00 |
| DI-CL | 6 | 6.16 |
| DI-CL | 8 | 8.27 |

`DI-CL` is ductile iron, cement lined; `CI` is unlined cast iron. This site's cast iron lead-ins have been found
between C 55 and C 95.

The yard main is a 12 in. cement-lined loop. Its own loss is negligible at the flows of this standard and it is
taken as standing at one pressure.

## Backflow preventer

The connection has one double check assembly, two spring-loaded checks in series between two isolating valves.
The maker's figures for the assembly as new are an opening differential of **4.0 psi** and a flow coefficient
**Cv 950** (gpm at 1 psi). It passes water towards the site only.

## Lead-in check valves

| model | size, in. | opening differential as new, psi | Cv_c |
|---|---|---|---|
| LC-6 | 6 | 1.5 | 2100 |
| LC-8 | 8 | 1.5 | 3900 |

A lead-in check is a single spring-loaded check where the lead-in enters the building.

## Control valves

Every riser has an OS&Y gate valve below its supply gauge. Fully open: Cv 5200 in 6 in., Cv 9800 in 8 in.

## Main drains

A main drain discharges to the open air through the riser's drain valve, fully open. Its flow is

    q = K * sqrt(p)

with p the residual pressure on the riser's supply gauge in psi.

| drain valve pattern | K |
|---|---|
| 2 in. angle | 52 |
| 1-1/2 in. globe | 36 |

## Hydrant flow by pitot

The flow from one hydrant outlet is

    Q = 29.84 * c * d^2 * sqrt(p_pitot)

with d the outlet's diameter in inches, p_pitot the pitot pressure in the stream in psi and c the outlet's
coefficient. Every outlet on the list below is 2.5 in.

| outlet form | c |
|---|---|
| smooth, rounded | 0.90 |
| square, sharp | 0.80 |
| projecting into the barrel | 0.70 |

| hydrant | on | outlet form |
|---|---|---|
| H-41 | city main, at the connection | smooth, rounded |
| H-42 | city main, 310 ft beyond the connection | smooth, rounded |
| H-43 | city main, 640 ft beyond the connection | square, sharp |
| YH-1 | yard main, building A | smooth, rounded |
| YH-2 | yard main, building C | smooth, rounded |
| YH-3 | yard main, building D | square, sharp |
| WH-6 | SR06's lead-in, at the wall of building C | smooth, rounded |

A wall hydrant stands on a riser's lead-in before the riser's control valve. The register gives how much of the
lead-in's equivalent length lies between the yard main and the hydrant's tee.

## Gauges

Each riser has a digital test gauge on the supply side of its alarm valve, at the height above the datum that the
register gives. The gauges are read to 0.1 psi and repeat to about 0.1 psi. Each has a certificate
(`gauge_certificates.md`).
