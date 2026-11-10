# Brake laboratory

The laboratory runs two kinds of test.

    friction <T> [<lining>]               friction coefficient of a series SB organic lining
    engage <size> <setting> <AC|DC>       engagement time of a series SB brake on the test bench

`friction` measures a bedded-in specimen, cut from the lining batch the brakes are supplied from, against a disc held
at the temperature T you choose, from 20 to 320 C, and gives eight readings. The lining is O1 or O2, the grades in the
catalogue; without one the specimen is O1. `engage` fits springs for the setting you choose (a whole percent from 50
to 100) to a bench brake of that size, supplied as on the hoists, and times five engagements with switching on the
side you choose.

Run them from `/app`. Each test's readings are printed and saved under `/app/lab_reports`. The allowance for the whole
selection is 8 tests of either kind; the laboratory refuses further tests once it is used.
