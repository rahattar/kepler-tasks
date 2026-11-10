# Condition codes for route reports

Each machine on a route gets one condition code and the component it applies to. Report the condition of the machine
itself: vibration that reaches it from elsewhere is not its condition, and neither is a problem with the
measurement. No machine on the plant's routes had more than one developing fault at its last survey.

| code | meaning | component |
|---|---|---|
| NONE | no developing fault | none |
| UNBALANCE | mass unbalance of a rotor | the rotor's machine element: motor, pump, fan or compressor |
| MISALIGNMENT | shaft misalignment across a coupling | coupling |
| LOOSENESS | structural looseness of a machine's mounting | the machine element whose mounting is loose: motor, pump, fan or compressor |
| BEARING_OUTER, BEARING_INNER, BEARING_BALL, BEARING_CAGE | rolling-element bearing defect, by location | the machine element that carries the bearing: motor, pump, fan or compressor |
| GEAR_TOOTH | gear tooth damage | pinion or gear |
| ELECTRICAL | stator or air-gap (static eccentricity) fault | motor |
| ROTOR_BAR | broken or cracked rotor bars | motor |
| BELT | worn or damaged drive belt | belt |
| RESONANCE | running speed close to a structural natural frequency | structure |
| CAVITATION | hydraulic cavitation | pump |
