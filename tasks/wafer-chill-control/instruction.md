After anneal, each wafer stops at a vacuum chill station on its way back to the carrier, resting on proximity pins above a chilled plate while backside helium carries heat away. Both the real-time helium pressure and the lift timing are left to the controller. A short cycle matters, but the center and edge temperatures have to stay close.

For stations A and B, the inspection records are in `/data/stations.json`. Alongside them are `/data/wafer.json`, with the wafer and chamber properties, and `/data/production.json`, with the production limits in machine-readable form. The eighteen instrumented test-wafer runs in `/data/characterization/` are described in `/data/characterization/index.json`.

At r = 75 mm, a step in standoff separates the plate's two concentric zones. The wafers need not be flat: with center sag s, the gap at radius r is zone standoff - s(1 - (r/(150 mm))^2), with standoff, sag and gap in um. From one wafer to the next, s varies between -50 and +50 um. It is neither measured nor given to the controller. The film label, bare, oxide or nitride, is known for each wafer.

The controller belongs in one self-contained Python file, `/app/controller.py`, with this interface:

```python
class Controller:
    def __init__(self, station, wafer):
        ...

    def step(self, t, reading):
        return {"pressure_torr": 12.0, "release": False}
```

At construction, `station` is that station's record from `/data/stations.json`, and `wafer` is a dictionary such as `{"film": "oxide"}`. Landing marks t = 0, with the chamber at 3.0 Torr. The first call to `step` comes at t = 0 with the landing `reading` dictionary, and calls continue every 0.1 s with t in seconds. In that dictionary, the pyrometer readings `center_C` and `edge_C` give area-mean wafer temperatures over radii 0 to 10 mm and 135 to 145 mm, respectively. The other readings are `plate_C` from the plate RTD and `pressure_torr` from the chamber manometer. Each call returns a dictionary with a Boolean `release` value. For continued cooling, the return needs `release` set to `False` and a finite `pressure_torr` between 3.0 and 60.0 Torr, held for the next 0.1 s. Returning `{"release": True}` lifts the wafer immediately at time t and makes t its cycle time. An invalid return, an exception, or a call beyond its time limit fails that wafer.

From landing to release, the absolute difference between the area-mean temperatures over r < 75 mm and r >= 75 mm must stay at or below 25.0 K at every instant. Release must occur before 30 s, with the mass-mean wafer temperature at or below 50.0 C. Testing covers 24 hidden wafers, 12 per station, across the sag range and the three film types. Every wafer must pass. Added across all 24, their cycle times must be within 10% of the total achieved by a controller with perfect knowledge of each wafer.

In the separate grading environment, `/data` does not exist and only the Python standard library, numpy and scipy are available. Grading starts over for every wafer, in a fresh process with a new `Controller`. Nothing carries over. The constructor has 20 s, each `step` call has 1 s, and the controller has 60 s of total computing time per wafer, including the constructor and all `step` calls. The interface check at `/app/check_controller.py` uses a stand-in plant rather than the station physics.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
