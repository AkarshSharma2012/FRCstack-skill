# Reusable custom structural parts

`scripts/parts_geometry.py` provides `generate_part(kind, parameters)` using the optional CadQuery environment. It returns one valid solid plus an independently calculated volume in mm3. These are parametric custom parts, not catalog substitutes or a full robot.

| Kind | Required parameters |
| --- | --- |
| `rect_tube` | `width_mm`, `height_mm`, `wall_mm`, `length_mm` |
| `round_tube` | `outer_diameter_mm`, `inner_diameter_mm`, `length_mm` |
| `plate` | `width_mm`, `height_mm`, `thickness_mm`, `holes` |

Every hole is an explicit `{x_mm, y_mm, diameter_mm}` object. Use `holes: []` for an undrilled plate. Dimensions must be finite numbers from 0.01 to 10000 mm; coordinates may be negative. Booleans, missing parameters, impossible walls/bores, overlapping holes and edge tangencies are refused. Cross sections are centered in XY, bottom is Z=0, extrusion is positive Z. No physical material, density, strength or manufacturing tolerance is inferred.

From a repository checkout with the optional CAD requirements installed:

```python
import sys
sys.path.insert(0, "skills/frcstack/scripts")
from parts_geometry import generate_part

rail, analytic_volume_mm3 = generate_part("rect_tube", {
    "width_mm": 50.8, "height_mm": 25.4,
    "wall_mm": 1.5875, "length_mm": 250
})
```

The example length is a test input, not a verified robot cut length. Retain the supplied parameters and design assumptions when exporting or placing a generated part. The library validates geometry and analytic volume; exporting a shape alone does not provide native Onshape history, assembly mates or a fabrication package.

## Native rectangular-tube generator

`assets/features/rect-tube.fs` is original FeatureScript 3095. Create it in a separate Feature Studio within an authorized editable document, commit and resolve actual compiler errors, then select the workspace custom feature **FRCstack rectangular tube** in a separate Part Studio. Leave publication and sharing unchanged.

Executed native cases on October 29, 2026, independently checked after export:

| Case | Observed result |
| --- | --- |
| Width 50.8, height 25.4, wall 1.5875, length 250 mm | One valid solid; volume 57963.59375 mm3; bounds 50.8 x 25.4 x 250 mm |
| Length 500 mm, other values unchanged | One valid solid; volume 115927.1875 mm3; bounds 50.8 x 25.4 x 500 mm |
| Wall 13 mm with height 25.4 mm | Native regeneration refused; no generated part; valid state restored |

Both native exported solids matched independently generated BReps with zero reported differences in either direction, within a 0.0001 mm3 acceptance threshold. Ten faces per case retained the illustrative grey RGB (0.72, 0.74, 0.77) within 0.002 per channel. These colors are appearance, not material specifications. Native source copy-back matched the local file after line-ending normalization.

Read Part Studio STEP styles through a shape/color reader: a Part Studio export need not be a semantic assembly and cannot be assumed to load with `Assembly.load`. The local helper and native UI have different input bounds; the two executed cases do not prove every combination or native round-tube/drilled-plate generation. Round tubes and drilled plates currently have local-kernel tests only. Native assembly integration, fastening, cut lengths, moving clearances and structural validation remain separate work.
