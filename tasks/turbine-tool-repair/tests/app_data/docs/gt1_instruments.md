# GT-1 performance test instrumentation

| tag | measurement | notes |
|---|---|---|
| JT-001 | generator active and reactive power, three-phase test wattmeter on the generator terminal PTs and CTs | class 0.1 |
| CIT-1..8 | Pt100 RTD array across the compressor inlet plenum, downstream of the inlet silencer | |
| PDT-101 | differential pressure across the inlet filter stages (pre-filters and final cartridges) | filter condition monitoring |
| PT-102 | absolute total pressure at the compressor bellmouth (pitot rake) | |
| PDT-201 | static pressure at the exhaust diffuser exit, relative to atmosphere | |
| FT-301 | fuel gas Coriolis mass flowmeter, on the fuel line upstream of the fuel gas heater | |
| TE-301 | fuel gas temperature at FT-301 | |
| TE-305 | fuel gas temperature at the turbine fuel skid inlet, after the fuel gas heater | |
| ST-001 | rotor speed | |
| IGV | compressor inlet guide vane position | fully open at 86 deg |
| TTXM | exhaust temperature, average of the control thermocouples | |
| TTRF | exhaust temperature control reference (set by the temperature control curve) | |
| met station | dry bulb, relative humidity, barometric pressure | 40 m north of the filter house |

The inlet system between ambient and the compressor bellmouth comprises the weather hoods, the filter stages, the
silencer and the inlet ducting. The fuel gas heater raises the fuel to about 210 degC before it enters the turbine.

When GT-1 is shut down its rotor is held on the turning gear at about 0.2 % speed; after a stop or a trip it coasts
down to the turning gear over a few tens of minutes. Before every start the fuel gas lines downstream of FT-301 are
purged and packed from the supply.
