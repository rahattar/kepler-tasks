# Metrology room: dense form scans for the press overhaul

The metrology room is temperature controlled at 20.4 C and holds an RT-1 form tester with a 1 mm ball stylus.
While the overhaul parts are still in the works it will scan a feature on request:

    formscan <feature>

It returns, in `/app/scan_reports`, the same three sections as the shop records, at 1800 points a revolution, with
absolute radius in mm, measured at the room's own temperature. It reports no roundness, diameter or sentence: the
points are the output.

The booking for this overhaul is **4 scans**. A scan is charged when it is ordered, whether or not its points are
used afterwards, and the booking does not refill. Ordering a scan takes the part out of the fitting shop's hands
for half a shift, so the room will not take an order for a feature it has already scanned.
