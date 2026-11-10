# MS-GB Grinding burn limits for surface grinding (owner's standard, revision 1)

1. The burn-limited depth of cut of a surface grinding operation is the largest depth of cut per pass at which the
   ground surface temperature stays at or below the part's burn limit, at the operation's work speed and ground width,
   with the wheel at the end of its dressing interval.
2. Surface temperature: coolant temperature plus the maximum temperature rise of a uniform band heat source moving
   over a semi-infinite workpiece at high Peclet number, theta = 1.13 Rw q sqrt(lc / vw) / beta, with:
   - lc = sqrt(ae ds), the geometric contact length, ae the depth of cut and ds the wheel diameter;
   - q = P / (b lc), the heat flux of the net grinding power P over the contact area of ground width b;
   - Rw, the share of the heat entering the workpiece, and beta = sqrt(k rho c), the workpiece's thermal property,
     from `grinding_data.md`.
3. Net grinding power: the spindle power less the spindle's idle power with the wheel running and not in contact,
   P = b (p0 + p1 V) + u Q, with V the specific volume removed since the last dressing (mm3 per mm of width) and
   Q = b ae vw the removal rate. p0, p1 and u are identified by least squares from the machine's power records of
   passes made with the operation's wheel specification and coolant.
4. Burn limit: the highest temperature at which the part's lot was tempered, plus 200 K.
