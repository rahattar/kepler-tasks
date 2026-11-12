# Laser alignment service

The contractor measures one train a visit, with the coupling made up and the machine cold, and leaves the heads
on through the start-up and until the train is at its running condition.

The contractor has time for 6 trains at this turnaround and plans the whole programme before coming to site.
Place it in one order, naming every train to be visited:

    laservisit <tag> <tag> <tag> <tag> <tag> <tag>

The order is taken once. No train is added or changed afterwards, and the contractor does not return to a train.
Each report is written to `/app/laser_reports/<tag>.csv` and gives, in mm:

- `y_stationary_plane`, `y_movable_plane`, `z_stationary_plane`, `z_movable_plane`: the cold position of the
  movable shaft's centreline relative to the stationary shaft's, at the two hubs' reading planes, in the sense
  of AP-12 section 2;
- `stationary_rise`, `stationary_lateral`, `movable_rise`, `movable_lateral`: how far each machine's shaft moved
  from cold to running.

The laser carries no bracket and has no sag.
