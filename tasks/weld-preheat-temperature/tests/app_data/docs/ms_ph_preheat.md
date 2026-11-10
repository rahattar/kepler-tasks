# MS-PH Minimum preheat of butt welds in structural steel (owner's standard, revision 2)

1. The minimum preheat temperature of a joint is the highest of the requirements of clauses 2 and 3, over both plates
   of the joint, each plate taken with its own composition and thickness. It is also the joint's minimum interpass
   temperature.
2. Hydrogen cracking (EN 1011-2, Annex C, method B). For each run of the joint,
   Tp = 697 CET + 160 tanh(d / 35) + 62 HD^0.35 + (53 CET - 32) Q - 328 (C), where:
   - CET = C + (Mn + Mo) / 10 + (Cr + Cu) / 20 + Ni / 40, in mass percent;
   - d is the plate thickness (mm);
   - HD is the diffusible hydrogen of the run's weld metal (ml per 100 g of deposited metal), clause 5;
   - Q is the run's heat input (kJ/mm), clause 4.
3. HAZ hardness. The hardness of the plate's heat affected zone under each capping run (no later run tempers it) must
   not exceed 380 HV10:
   - HV = 2019 [C (1 - 0.5 log t) + 0.3 (CE - C)] + 66 (1 - 0.8 log t), with t the run's cooling time t8/5 (s),
     log to base 10, and CE = C + Si / 11 + Mn / 8 + Cu / 9 + Cr / 5 + Ni / 17 + Mo / 6 + V / 3;
   - t8/5 at the preheat temperature T0 (C) is the larger of
     t3 = (6700 - 5 T0) Q [1 / (500 - T0) - 1 / (800 - T0)] F3 and
     t2 = (4300 - 4.3 T0) 10^5 (Q / d)^2 [1 / (500 - T0)^2 - 1 / (800 - T0)^2] F2,
     with F2 = 1.0 and F3 = 0.9 for a capping run of a butt weld (EN 1011-2, Annex D).
4. Heat input. Q = k P / v / 1000 for each run as welded, from the arc monitor's record of the run, where:
   - k is the thermal efficiency of the process: 0.8 for processes 111, 135 and 136, and 0.6 for process 141;
   - P (W) is the arc power: the mean current times the mean arc voltage, or, for a waveform-controlled (pulsed) run,
     the mean of the instantaneous arc power over the run's waveform record;
   - v (mm/s) is the travel speed: the run's length divided by its arc time.
5. Diffusible hydrogen. HD is the certificate value of the consumable batch the run was welded with (ISO 3690). Covered
   electrodes in an unheated quiver also pick up moisture from the shop air: HD = HD0 + s E, where:
   - HD0 is the batch's certificate value;
   - E (kPa h) is the time integral of the water vapor partial pressure of the shop air, from the time the electrodes
     were issued to the quiver until the start of the run;
   - s is the pick-up rate of the electrode type, from the shop's exposure tests (`welding_data.md`).
   Electrodes in a heated quiver pick up no moisture. Electrodes returned to the oven and issued again count from the
   new issue. The vapor pressure is p = RH / 100 x 0.61094 exp(17.625 T / (T + 243.04)) kPa, with T the air
   temperature (C) and RH its relative humidity (percent).
