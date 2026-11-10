# RC-4  Lowest allowable field pressure of a reciprocating booster

Plant standard RC-4, revision 8. Applies to every reciprocating compressor cylinder on the plant.

## 1  Purpose

A booster on a declining field reaches a mechanical or a process limit at some field pressure. This standard fixes
how that pressure is found for each cylinder and how it is reported, so that the figure is the same whoever works
it out.

## 2  The duty

The unit takes suction from the field and discharges into the pipeline. The field pressure, the pipeline pressure
and the contract flow the unit has to hold are in the operating record. Nothing else about the duty is set.

### 2.1  The pressures between the stages

They are not set by anyone. They settle where each stage passes the molar flow the stage before it delivers, less
whatever the separator between them knocks out as condensate:

    n(stage 2) = n(stage 1) * ( 1 - f1 )
    n(stage 3) = n(stage 2) * ( 1 - f2 )

with f1 and f2 the condensate fractions of the two interstage separators. A separator that is out of service knocks
nothing out.

The molar flow of a stage, per revolution of the frame, is

    n = ( p_suction - 0.35 ) * V_stage / ( R * T_suction )

in absolute units, with R the molar gas constant, T_suction the suction temperature at the valve flange of 2.4, and

    V_stage = sum over the stage's cylinders and over each end of ( V_end * E_v,end )

the swept volume of each end times that end's volumetric efficiency of 2.5. The two equations leave one pressure
between the first and second stages and one between the second and third; they are to be found to within 0.001 bar.

### 2.2  The speed

The contract flow is measured at the export meter, so it is the molar flow the last stage delivers. The unit has to
hold it, so the speed is whatever that flow needs at the pressures that settle:

    N = contract flow / n(stage 3)

in revolutions per unit time, with the flow and n in the same units of amount per unit time. By 2.1 the molar flow
of the last stage is the molar flow of the first less what the separators between them knock out.

### 2.3  The range

The drive may not be run above the rated speed of the frame. The range of field pressures considered therefore runs
from the field pressure of the operating record down to the lower of

- the field pressure at which the speed of 2.2 reaches the rated speed, and
- 50 per cent of the field pressure of the operating record.

### 2.4  The suction temperature

The suction temperature of a stage is the reading of its element, as the operating record gives it. Where the
instrument schedule shows the element mounted on the suction bottle rather than at the valve flange, the
temperature at the flange is the reading plus 6 K.

## 3  The isentropic exponent

The isentropic exponent of a stage's gas is taken from the mol-average molar heat capacity of its analysis:

    Cp_mix / R = sum over components of ( mol fraction * Cp_i / R )
    k = ( Cp_mix / R ) / ( Cp_mix / R - 1 )

The component figures are those of the plant's property table, which gives them against temperature, and they are
taken at the mean of the suction and the discharge temperature of the cylinder. The discharge temperature of 4.3 is
therefore found together with the exponent: start from the suction temperature, take the exponent at the mean,
compute the discharge temperature, and repeat until two successive discharge temperatures differ by less than
0.001 K.

The gas of a stage is the gas that enters it, which is the gas the stage before it discharges less whatever its
separator knocks out. Where a separator is out of service, the stage sees the gas of the stage before it.

## 4  The requirements

A cylinder is acceptable at a field pressure when all of the following are met at the pressures and the speed that
field pressure brings, by 2.1 and 2.2.

The pressure ratio of a cylinder is taken across its valves:

    R_p = ( p_discharge + 0.70 ) / ( p_suction - 0.35 )

the valve losses being this standard's figures for the valve type fitted.

### 4.1  Gas load

The gas load on the piston rod is taken through one revolution at each whole crank angle. For a double-acting
cylinder, with the head end leading, the gas load is

    F_gas = p_head * A_head - p_crank * A_crank

where the head end sees the discharge pressure and the crank end the suction pressure through the first half
revolution, and the other way about through the second. A_head is the bore area and A_crank the bore area less the
area of the piston rod. Compression is positive. The peak of its magnitude shall not exceed the maximum allowable
gas load of the cylinder, which is a rating of the cylinder body and its bolting and is on the cylinder data sheet.

### 4.2  Rod load in compression and in tension

The inertia load of the reciprocating weight is added to the gas load at the same crank angle:

    F_inertia = -m * omega^2 * r * ( cos(theta) + cos(2 theta) / L )

with m the reciprocating weight of the running assembly, omega the angular speed at the speed of 2.2, r half the
stroke, theta the crank angle from the head end dead centre and L the ratio of connecting rod length to crank
radius, which is 4.0 on this frame. The peak of the sum in compression and the peak in tension shall each not
exceed the rated rod load of the throw, which is the figure on the frame data sheet as the OEM's service bulletins
revise it, or the de-rated figure of the throw where one has been issued, whichever is the lower.

### 4.3  Discharge temperature

    T_discharge = T_suction * R_p ^ ( ( k - 1 ) / k )

in absolute temperature, with T_suction the suction temperature at the valve flange of 2.4 and k the exponent of
clause 3. It shall not exceed 135 C.

### 4.4  Volumetric efficiency and cylinder power

The volumetric efficiency of an end of a cylinder follows from that end's own clearance:

    E_v = 1 - C * ( R_p ^ ( 1 / k ) - 1 )

with C the clearance volume of that end as a fraction of that end's swept volume, as the pockets now stand. The
indicated power is the two ends added:

    P = sum over the ends of ( p_suction - 0.35 ) * V_end * E_v,end * ( R_p ^ n - 1 ) / n ,    n = ( k - 1 ) / k

with V_end the swept volume of that end in volume per unit time at the speed of 2.2, and the suction pressure in
absolute units. It shall not exceed the rated power of the cylinder, which is on the cylinder data sheet.

### 4.5  Pin reversal

The combined rod load of 4.2 shall be in tension through at least 15 whole degrees of the revolution, counted as
the number of whole crank angles at which it is negative.

## 5  The lowest allowable field pressure

Within the range of 2.3, the lowest allowable field pressure of a cylinder is the lowest whole 0.01 bar at which
that cylinder is acceptable at that pressure and at every higher pressure in the range.

The requirement that fails at the next step below it is the governing requirement, and is reported with it under
one of these names:

    gas_load   rod_load_compression   rod_load_tension   discharge_temperature   cylinder_power   pin_reversal

## 6  The records to be used

The machine as it now stands, not as it was bought.
