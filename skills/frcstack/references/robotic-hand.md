# Robotic Hand -- 20-DOF Standalone Reference

**Status:** Proposed design targets only. NOT fabrication-ready. NOT FEA-verified.
Native hand FeatureScript authored but has **NOT compiled** in Onshape.

---

## Overview

A proposed standalone 20-axis robotic hand geometry with:
- 21 solid parts: 1 palm + 5 fingers x 4 links (carrier, proximal, middle, distal)
- 20 revolute joints: 4 per finger (spread/yaw, MCP/opposition, PIP/MCP, DIP/IP)
- Palm: 90 mm wide x 86 mm long x 6 mm thick, rounded rectangle with 5 bored bosses
- Carriers (blue): yaw/opposition DOF, 12 mm long, fork joint at distal end
- Phalanges (grey): tongue-in-fork joint at root, fork at far end (except distal tip)

## Dimensions (proposed targets)

| Parameter | Value |
|---|---|
| Palm width | 90 mm |
| Palm length | 86 mm |
| Palm thickness | 6 mm |
| Carrier length | 12 mm |
| Index segments | 38 / 25 / 18 mm |
| Middle segments | 42 / 27 / 20 mm |
| Ring segments | 40 / 26 / 18 mm |
| Little segments | 30 / 20 / 16 mm |
| Thumb segments | 24 / 30 / 22 mm |

## Joint Limits (degrees)

**Long fingers (index/middle/ring/little):**

| DOF | Min | Max |
|---|---|---|
| spread | -15 | +15 |
| MCP | -10 | +90 |
| PIP | 0 | +110 |
| DIP | 0 | +80 |

**Thumb:**

| DOF | Min | Max |
|---|---|---|
| yaw | -90 | +35 |
| opposition | -30 | +90 |
| MCP | 0 | +100 |
| IP | 0 | +90 |

## Named Poses

| Pose | Description |
|---|---|
| `open` | All 20 joints at 0° |
| `partial` | Long fingers MCP=35°, PIP=45°, DIP=20°; thumb yaw=-35°, opp=25°, MCP=30°, IP=20° |
| `closed` | Long fingers MCP=70°, PIP=90°, DIP=60°; thumb yaw=-50°, opp=45°, MCP=60°, IP=45° |

## CLI Invocation

Run from the `skills/frcstack/scripts/` directory with `.venv-cad`:

```
python hand_runtime.py build-hand --pose open    --output /abs/path/to/fresh/open-001
python hand_runtime.py build-hand --pose partial --output /abs/path/to/fresh/partial-001
python hand_runtime.py build-hand --pose closed  --output /abs/path/to/fresh/closed-001
```

**Rejected inputs:**
- Unknown pose name: `ValueError` with nonzero exit
- Output directory already exists: `FileExistsError` with nonzero exit
- Symlink/junction in output path: `ValueError` with nonzero exit
- Path containing `..`: `ValueError` with nonzero exit

## Output Files

Each output directory receives:
- `hand.step` -- CadQuery Assembly with 21 named solids (palm grey, carriers blue, phalanges grey)
- `validation.json` -- Full evidence record (see schema below)

## API

```python
from hand_runtime import build_hand_export
report = build_hand_export("open", "/abs/path/to/fresh/output")
```

Returns the same dict as `validation.json`.
Raises `ValueError` on bad geometry, failed roundtrip, or collisions (nonzero CLI exit).
Raises `FileExistsError` if output already exists.
Always writes `validation.json` before raising so evidence is preserved.

## Executed Checks (as of this reference)

### Geometry

- **21 positive-finite valid solids** verified in source (pre-export)
- **STEP export** via CadQuery Assembly with named parts and authored colours
- **Roundtrip reimport**: 21 solids read back, each checked valid/positive-finite
- **Bijective Boolean-difference matching** (order-independent via `solid_matching.py`):
  both `A.cut(B)` and `B.cut(A)` must be ≤ 1e-5 mm³ for each matched pair

### Collision

- **All 210 part pairs** (21 choose 2) checked
- **AABB broad phase** used to skip non-overlapping bounding boxes
- **Boolean `intersect()` narrow phase** for every AABB-overlapping pair
- Kernel exception **raises `ValueError`** -- never silently becomes zero overlap
- Threshold: > 1e-6 mm³ is a collision; exact pair names and volumes recorded
- **No threshold weakening applied**

### Executed CLI results

| Pose | Parts | Roundtrip | Collision-free | Collision pairs |
|---|---|---|---|---|
| open | 21/21 | PASS | **true** | 0 |
| partial | 21/21 | PASS | **true** | 0 |
| closed | 21/21 | PASS | **true** | 0 |

## Missing / Unexecuted Checks

| Feature | Status |
|---|---|
| Native Onshape FeatureScript compilation | NOT executed (FeatureScript authored, not compiled) |
| Native Onshape assembly mates | NOT verified (`native_mates_verified=false`) |
| Motion/actuation simulation | NOT executed (`actuation_verified=false`) |
| Tendons / actuator routing | Absent from solid model |
| FEA / structural analysis | NOT executed (`fea_executed=false`) |
| Fabrication readiness | NOT verified (`fabrication_ready=false`) |
| STEP name roundtrip | NOT independently verified (`name_roundtrip_verified=false`) |
| STEP colour roundtrip | NOT independently verified (`color_appearance_verified=false`) |
| Continuous collision-freedom (full motion range) | NOT claimed; single sampled poses only |
| Human anatomy accuracy | NOT claimed; proposed targets only |

## validation.json Schema (key fields)

```json
{
  "schema": 1,
  "kind": "proposed_20dof_hand_not_fabrication_ready",
  "pose": "open|partial|closed",
  "source_sha256": {"hand_geometry.py": "...", "hand_kinematics.py": "...", "hand_runtime.py": "..."},
  "step_sha256": "...",
  "part_count_source": 21,
  "part_count_roundtrip": 21,
  "fk_angles_deg": { "<joint_name>": <float>, ... },
  "joint_count": 20,
  "parts": { "<name>": { "volume_mm3": ..., "bounds_mm": {...} }, ... },
  "geometry_roundtrip_passed": true,
  "collision_pairs_checked": 210,
  "aabb_broad_phase_used": true,
  "collisions": [],
  "collision_free_sampled_pose": true,
  "native_mates_verified": false,
  "actuation_verified": false,
  "fea_executed": false,
  "fabrication_ready": false,
  "name_roundtrip_verified": false,
  "color_appearance_verified": false
}
```
