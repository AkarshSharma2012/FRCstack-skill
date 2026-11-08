"""Fix wheel_assembly to remove broken revolve call."""
import sys

lines = open('scripts/drivetrain_2026.py', encoding='utf-8').readlines()

new_func = [
    'def wheel_assembly(w_diam=WHEEL_DIAM, w_width=WHEEL_WIDTH):\n',
    '    """Pneumatic wheel: annular tire disk + hub cylinder + axle bore."""\n',
    '    r = w_diam / 2.0\n',
    '    hub_r = 0.75 * IN\n',
    '    tire_inner_r = r - 1.1 * IN  # ~28mm radial tread depth\n',
    '    # Outer tire ring (annular disk, broad-face = wheel width)\n',
    '    tire_outer = cq.Workplane("YZ").circle(r).extrude(w_width, both=True)\n',
    '    tire_void  = cq.Workplane("YZ").circle(tire_inner_r).extrude(w_width + 2, both=True)\n',
    '    tire = tire_outer.cut(tire_void)\n',
    '    # Hub cylinder\n',
    '    hub = cq.Workplane("YZ").circle(hub_r).extrude(w_width, both=True)\n',
    '    # Axle bore\n',
    '    bore = cq.Workplane("YZ").circle(GB_OUTPUT_DIAM / 2.0 + 0.5).extrude(w_width + 2, both=True)\n',
    '    return tire.union(hub).cut(bore)\n',
    '\n',
]

# Find the function start and end (0-indexed)
start = None
end = None
for i, l in enumerate(lines):
    if 'def wheel_assembly' in l:
        start = i
    if start is not None and i > start + 2 and l.startswith('def '):
        end = i
        break

print(f'Found wheel_assembly at line {start+1} (0-indexed {start}), next def at {end}')
if start is None:
    print('ERROR: could not find wheel_assembly')
    sys.exit(1)

out = lines[:start] + new_func + lines[end:]
with open('scripts/drivetrain_2026.py', 'w', encoding='utf-8') as f:
    f.writelines(out)
print(f'Written: {len(out)} lines total')
