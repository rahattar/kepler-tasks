# Stratified chilled-water storage: pre-mortem, not built (Nov 14)

A 1D tank: exact advection, inlet mixing over h_m = h_d (1 + (Re/Re0)^2), diffusion, wall gain, and cut-offs at
7.0 C (discharge) and 6.0 C (charge). `pm.py`, `pm2.py`.
- **Blocked diffuser** (effective length halved): forecast usable cooling at design flow 14 to 16 per cent low.
  After fitting the diffusivity, the history residual is 0.36 K against 0.03 K of noise. The flow dependence
  points to the mixing law, and the law's constant and the diffuser length enter only as a product, so refitting
  the one constant is the identification.
- **Passing valve in standby** (1.5 m3/h): under 0.5 per cent on the forecast unless the tank sits charged for
  days. When it does, the thermocline moves with no metered flow, which shows plainly.
- **Same failure as the boiler and the piping line:** the conditions that matter are plain in the records, and
  each is one continuous parameter that a fit recovers.
