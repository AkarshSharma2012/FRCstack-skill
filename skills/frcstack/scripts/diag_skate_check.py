"""Check the chosen skate gains: several speed caps plus a 2-minute endurance run."""
import sys

import diag_skate_long as D

G = dict(k_th=12, k_dth=0.3, k_v=0.4, k_vi=0.5, k_x=0.0, a_max=0.05)
xml = sys.argv[1]
for vmax in (0.2, 0.25, 0.3, 0.35):
    print("vmax", vmax, D.run(xml, G, T=60.0, vmax=vmax), flush=True)
D.PROFILE = D.PROFILE + [(t, f) for t, f in ((60, 0.5), (75, 0.0), (85, -0.5), (95, 1.0), (110, 0.0))]
print("endurance 120 s @0.25", D.run(xml, G, T=120.0, vmax=0.25), flush=True)
