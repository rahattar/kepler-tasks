# Metallurgical laboratory

    temper <heat> <T> [<diameter_mm> <surface|half-radius>] [double]

hardens a test piece cut from the heat as production does (austenitise, oil quench), tempers it once for 2 h at T
(400 to 700 C), and reports the hardness (HRC, mean of five indentations) at the location given. With `double` the
test piece is tempered twice for 2 h at T, cooled to room temperature between the two tempers. Without a diameter the
test piece is a 25 mm round and the hardness is read at half-radius. A test piece of a larger diameter (up to 300 mm)
is cut from bar of that size. Run it from `/app`; each report is printed and saved under `/app/lab_reports`.

The laboratory furnace is booked for 11 tempers for all thirteen batches: a test tempered once uses one of them and a
test tempered twice uses two.
