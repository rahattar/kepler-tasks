# MS-CH Milling stability limits (owner's standard, revision 1)

1. The stability limit of a milling operation is the axial depth of cut at which regenerative chatter starts at the
   spindle speed of the operation.
2. Method: the zero-order (average tooth angle) solution of Altintas and Budak (1995) for a cylindrical cutter of
   uniform pitch, helix and runout neglected:
   - x along the feed direction, y normal to it in the plane of the cut; the immersion angle measured from y in the
     direction of rotation; up (conventional) milling: entry 0, exit acos(1 - 2 ae/D); down (climb) milling: entry
     acos(2 ae/D - 1), exit pi, with ae the radial depth of cut and D the tool diameter;
   - the tool-tip receptances along x and y only (cross receptances neglected), N the number of cutting teeth,
     tangential cutting coefficient Kt and radial-to-tangential ratio Kr from `cutting_coefficients.md`;
   - the limit at a speed is the lowest positive limiting depth over the chatter frequencies whose stability lobe
     passes through that speed.
3. The tool-tip receptances are those of the tool assembly as it will cut, from tap tests at the tool tip along the
   machine's X and Y axes.
