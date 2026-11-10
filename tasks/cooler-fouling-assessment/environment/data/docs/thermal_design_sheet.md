# Glycol cooler bank: thermal design sheet (model C-200, units E1-E9)

Shell-and-tube coolers, glycol solution on the shell side, cooling water in the tubes, counter-current. Rate them
as pure counterflow (the duty is computed with the log-mean temperature difference, no correction factor).

| item | C-200 |
|---|---|
| heat-transfer area (all tubes open) | 90 m2 |
| design cooling-water flow | 180 m3/h |
| design glycol flow | 60 m3/h |
| clean tube-side (water) film coefficient at design | 3000 W/m2K |
| clean shell-side (glycol) film coefficient at design | 2500 W/m2K |
| tube wall | 0.05 m2K/kW |
| tube-side pressure drop at design, clean | 42 kPa |

- Overall coefficient: 1/U = 1/h_tube + 1/h_shell + R_wall + R_fouling.
- The tube-side film coefficient follows the water velocity in the tubes to the power 0.8; the shell-side film
  coefficient follows the glycol crossflow velocity across the tube bank to the power 0.6 (for a given bundle, the
  glycol flow to the power 0.6). Original C-200 bundles: baffle spacing 300 mm, 25 percent baffle cut.
- Tube-side pressure drop follows the water velocity in the tubes to the power 1.8, times the tube friction factor.
- Fluids: cooling water 995 kg/m3, 4.18 kJ/kg K; glycol solution 1050 kg/m3, 3.60 kJ/kg K.
- Individual units differ from the design split, most by a few per cent, some by more (bundles rebuilt or
  repaired over the years). The March 2025 acceptance tests, made just after hydroblasting, are each unit's own
  clean performance.
