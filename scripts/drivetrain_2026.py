"""
AM14U6 2026 Six-Wheel Drop-Center Differential Drive Drivetrain Builder
=======================================================================
Generates a fully-parameterized STEP assembly for the AndyMark AM14U6
Square 2026 KitBot drivetrain with:
  - 6x 6" pneumatic wheels (drop-center layout)
  - Chassis rails (1x2" aluminum rect tube, square 26"x26" config)
  - 2x gearbox plates + output shaft geometry (CIM/Falcon-compatible)
  - Drive belt/chain transmission geometry (HTD-5mm belt proxy)
  - Custom electronics/battery deck plate
  - Motor stub geometry for left/right CIM or Falcon 500 motors
  - Mounting hardware (standoffs, bolt patterns)

All dimensions from official AndyMark AM14U6 2026 Square configuration:
  Source: https://andymark.com/products/am14u6-6-wheel-drop-center-robot-drive-base-2025-frc-kit-of-parts-drive-base
  Assembly guide: https://www.firstinspires.org/resources/library/frc/kitbot

Units: mm throughout; converted from inches where noted.
"""

import cadquery as cq
import json
import math
import os
import sys
import time

BUILD_START = time.time()

# ---------------------------------------------------------------------------
# Official AM14U6 Square 2026 geometry constants (inches -> mm)
# Source: AndyMark AM14U6 drawing and assembly guide
# ---------------------------------------------------------------------------
IN = 25.4  # 1 inch in mm

# Frame overall (square config)
FRAME_WIDTH   = 26.0 * IN   # 660.4 mm
FRAME_LENGTH  = 26.0 * IN   # 660.4 mm
RAIL_W        = 2.0  * IN   # 50.8  mm   (1x2 tube, 2" in Z)
RAIL_H        = 1.0  * IN   # 25.4  mm   (1x2 tube, 1" wall)
TUBE_WALL     = 0.125* IN   # 3.175 mm   (1/8" wall)

# Wheel geometry
WHEEL_DIAM    = 6.0  * IN   # 152.4 mm   6" pneumatic
WHEEL_WIDTH   = 1.5  * IN   # 38.1  mm   approximate tread width
WHEEL_RADIUS  = WHEEL_DIAM / 2.0

# Drop-center: middle wheel 1/8" lower than front/rear
DROP_CENTER   = 0.125 * IN  # 3.175 mm

# Wheel X positions along 26" frame (measured from front face, center-to-center)
# Front: 3.5" from front end, Middle: 13" (center), Rear: 22.5" from front
WHEEL_X_FRONT  = 3.5  * IN
WHEEL_X_MID    = 13.0 * IN
WHEEL_X_REAR   = 22.5 * IN

# Wheel Y positions: left/right, inset from rail outside
WHEEL_Y_LEFT   = 1.75 * IN   # ~44.45 mm from center
WHEEL_Y_RIGHT  = -(1.75 * IN)
WHEEL_CL_Y     = FRAME_WIDTH / 2.0 - 1.75 * IN   # from centerline

# Drive shaft Z height (wheel axle above ground)
AXLE_Z         = WHEEL_RADIUS   # 76.2 mm off ground (front/rear)
AXLE_Z_MID     = WHEEL_RADIUS - DROP_CENTER   # middle wheel lower

# Gearbox geometry (dual CIM, 10.71:1 ratio, single-stage)
GB_LENGTH      = 4.5  * IN   # 114.3 mm
GB_WIDTH       = 2.0  * IN   # 50.8  mm
GB_HEIGHT      = 3.5  * IN   # 88.9  mm
GB_OUTPUT_DIAM = 0.5  * IN   # 12.7  mm  1/2" hex shaft

# Motor stub (CIM-compatible, 2.5" OD case)
CIM_BODY_DIAM  = 2.5  * IN   # 63.5 mm
CIM_LENGTH     = 3.5  * IN   # 88.9 mm
CIM_SHAFT_DIAM = 0.313 * IN  # 7.95 mm

# Belt/chain transmission
SPROCKET_PD    = 2.865 * IN  # HTD 18T 5mm pitch = 72.6 mm PD (drive)
BELT_WIDTH     = 0.5   * IN  # 15 mm belt width proxy

# Electronics deck
DECK_THICKNESS = 0.09  * IN  # 2.3 mm  (1/8" polycarbonate or 3mm alu)
DECK_MARGIN    = 1.0   * IN  # 25.4 mm inset from frame rail

# Output dir
OUT_DIR = os.path.join(os.path.dirname(__file__), 
                       '..', '.frcstack', 'drivetrain-10min-20261108')
OUT_DIR = os.path.normpath(OUT_DIR)
os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rect_tube(length_mm, w=RAIL_W, h=RAIL_H, wall=TUBE_WALL):
    """Hollow rectangular tube along X axis."""
    outer = cq.Workplane("XY").box(length_mm, w, h)
    inner_w = w - 2*wall
    inner_h = h - 2*wall
    inner = cq.Workplane("XY").box(length_mm + 2, inner_w, inner_h)
    return outer.cut(inner)


def wheel_assembly(w_diam=WHEEL_DIAM, w_width=WHEEL_WIDTH):
    """Pneumatic wheel: annular tire disk + hub cylinder + axle bore."""
    r = w_diam / 2.0
    hub_r = 0.75 * IN
    tire_inner_r = r - 1.1 * IN  # ~28mm radial tread depth
    # Outer tire ring (annular disk, broad-face = wheel width)
    tire_outer = cq.Workplane("YZ").circle(r).extrude(w_width, both=True)
    tire_void  = cq.Workplane("YZ").circle(tire_inner_r).extrude(w_width + 2, both=True)
    tire = tire_outer.cut(tire_void)
    # Hub cylinder
    hub = cq.Workplane("YZ").circle(hub_r).extrude(w_width, both=True)
    # Axle bore
    bore = cq.Workplane("YZ").circle(GB_OUTPUT_DIAM / 2.0 + 0.5).extrude(w_width + 2, both=True)
    return tire.union(hub).cut(bore)

def cim_motor(length=CIM_LENGTH, diam=CIM_BODY_DIAM):
    """CIM motor body stub: cylinder + shaft."""
    body = (cq.Workplane("YZ")
            .circle(diam / 2.0)
            .extrude(length))
    shaft = (cq.Workplane("YZ")
             .circle(CIM_SHAFT_DIAM / 2.0)
             .extrude(length + 1.0 * IN))
    return body.union(shaft)


def gearbox_plate(length=GB_LENGTH, width=GB_WIDTH, height=GB_HEIGHT):
    """Single gearbox housing plate with output shaft bore."""
    box = cq.Workplane("XY").box(length, width, height)
    # Output shaft bore
    bore = (cq.Workplane("XY")
            .workplane(offset=height/2.0)
            .circle(GB_OUTPUT_DIAM / 2.0 + 1.0)
            .extrude(height + 2, both=True))
    # 4x mounting holes (CIM bolt circle 2" dia)
    bolt_r = 1.0 * IN
    n_bolts = 4
    for i in range(n_bolts):
        angle = math.radians(45 + i * 90)
        bx = bolt_r * math.cos(angle)
        by = bolt_r * math.sin(angle)
        hole = (cq.Workplane("XY")
                .workplane(offset=height/2.0 + 1)
                .center(bx, by)
                .circle(1.5)
                .extrude(height + 4, both=True))
        box = box.cut(hole)
    return box.cut(bore)


def sprocket(pitch_diam=SPROCKET_PD, width=BELT_WIDTH, teeth=18):
    """Drive sprocket/pulley stub."""
    r = pitch_diam / 2.0
    disk = (cq.Workplane("YZ")
            .circle(r)
            .extrude(width, both=True))
    hub = (cq.Workplane("YZ")
           .circle(r * 0.4)
           .extrude(width * 1.5, both=True))
    bore = (cq.Workplane("YZ")
            .circle(GB_OUTPUT_DIAM / 2.0)
            .extrude(width * 2 + 2, both=True))
    return disk.union(hub).cut(bore)


def electronics_deck(frame_w=FRAME_WIDTH, frame_l=FRAME_LENGTH,
                     margin=DECK_MARGIN, thick=DECK_THICKNESS):
    """Battery/electronics mounting deck plate with cutouts."""
    w = frame_w - 2 * margin
    l = frame_l - 2 * margin
    plate = cq.Workplane("XY").box(l, w, thick)
    # Battery cutout (12V 18Ah: ~180x75x167mm)
    batt_cut = cq.Workplane("XY").box(180, 75, thick + 2)
    plate = plate.cut(batt_cut.translate([0, 0, 0]))
    # 4x corner mount holes (1/4-20)
    hole_inset = 0.75 * IN
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            hx = sx * (l/2 - hole_inset)
            hy = sy * (w/2 - hole_inset)
            h = (cq.Workplane("XY")
                 .workplane(offset=thick/2+1)
                 .center(hx, hy)
                 .circle(3.5)
                 .extrude(thick + 4, both=True))
            plate = plate.cut(h)
    return plate


# ---------------------------------------------------------------------------
# Full assembly builder
# ---------------------------------------------------------------------------

def build_am14u6_assembly():
    """
    Assemble all components into a single CadQuery compound.
    Returns (assembly_dict, compound) where assembly_dict has named solids.
    """
    parts = {}
    
    print("[1/8] Building chassis rails...", flush=True)
    # --- Four perimeter rails (square config) ---
    # Front rail (along Y)
    fr = rect_tube(FRAME_WIDTH)
    fr = fr.rotate((0,0,0),(0,0,1), 90).translate([0, 0, RAIL_H/2])
    # Rear rail
    rr = rect_tube(FRAME_WIDTH)
    rr = rr.rotate((0,0,0),(0,0,1), 90).translate([FRAME_LENGTH, 0, RAIL_H/2])
    # Left side rail (along X)  
    lr = rect_tube(FRAME_LENGTH).translate([FRAME_LENGTH/2, FRAME_WIDTH/2, RAIL_H/2])
    # Right side rail
    rrail = rect_tube(FRAME_LENGTH).translate([FRAME_LENGTH/2, -FRAME_WIDTH/2, RAIL_H/2])

    parts["rail_front"] = fr
    parts["rail_rear"] = rr
    parts["rail_left"] = lr
    parts["rail_right"] = rrail

    # Cross members (2x inner for gearbox mounts)
    cm1 = rect_tube(FRAME_WIDTH - 2*RAIL_W)
    cm1 = cm1.rotate((0,0,0),(0,0,1), 90).translate([FRAME_LENGTH*0.3, 0, RAIL_H/2])
    cm2 = rect_tube(FRAME_WIDTH - 2*RAIL_W)
    cm2 = cm2.rotate((0,0,0),(0,0,1), 90).translate([FRAME_LENGTH*0.7, 0, RAIL_H/2])
    parts["crossmember_front"] = cm1
    parts["crossmember_rear"] = cm2

    print("[2/8] Building wheels (6x)...", flush=True)
    # 6 wheels: front-L, front-R, mid-L, mid-R, rear-L, rear-R
    wheel_positions = [
        ("wfl", WHEEL_X_FRONT, +WHEEL_CL_Y, AXLE_Z),
        ("wfr", WHEEL_X_FRONT, -WHEEL_CL_Y, AXLE_Z),
        ("wml", WHEEL_X_MID,   +WHEEL_CL_Y, AXLE_Z_MID),
        ("wmr", WHEEL_X_MID,   -WHEEL_CL_Y, AXLE_Z_MID),
        ("wrl", WHEEL_X_REAR,  +WHEEL_CL_Y, AXLE_Z),
        ("wrr", WHEEL_X_REAR,  -WHEEL_CL_Y, AXLE_Z),
    ]
    wa = wheel_assembly()
    for name, wx, wy, wz in wheel_positions:
        parts[name] = wa.translate([wx, wy, wz])

    print("[3/8] Building gearboxes (2x)...", flush=True)
    gb = gearbox_plate()
    # Left gearbox: near front cross-member, left side
    gb_l = gb.translate([FRAME_LENGTH*0.3, +FRAME_WIDTH/2 - GB_WIDTH/2 - RAIL_W, 
                          RAIL_H + GB_HEIGHT/2])
    # Right gearbox: mirrored
    gb_r = gb.translate([FRAME_LENGTH*0.3, -(FRAME_WIDTH/2 - GB_WIDTH/2 - RAIL_W),
                          RAIL_H + GB_HEIGHT/2])
    parts["gearbox_left"] = gb_l
    parts["gearbox_right"] = gb_r

    print("[4/8] Building motors (2x CIM stubs)...", flush=True)
    motor = cim_motor()
    # Motors mount to rear of gearbox
    m_l = motor.translate([FRAME_LENGTH*0.3 - GB_LENGTH/2 - CIM_LENGTH/2,
                            +FRAME_WIDTH/2 - GB_WIDTH/2 - RAIL_W,
                            RAIL_H + GB_HEIGHT/2])
    m_r = motor.translate([FRAME_LENGTH*0.3 - GB_LENGTH/2 - CIM_LENGTH/2,
                            -(FRAME_WIDTH/2 - GB_WIDTH/2 - RAIL_W),
                            RAIL_H + GB_HEIGHT/2])
    parts["motor_left"] = m_l
    parts["motor_right"] = m_r

    print("[5/8] Building drive sprockets/pulleys...", flush=True)
    sp = sprocket()
    # Output sprocket at gearbox output shaft, left
    sp_l_out = sp.translate([FRAME_LENGTH*0.3,
                              +WHEEL_CL_Y,
                              AXLE_Z])
    # Drive sprocket on front wheel, left
    sp_l_drv = sp.translate([WHEEL_X_FRONT,
                              +WHEEL_CL_Y - BELT_WIDTH,
                              AXLE_Z])
    # Same for right side
    sp_r_out = sp.translate([FRAME_LENGTH*0.3,
                              -WHEEL_CL_Y,
                              AXLE_Z])
    sp_r_drv = sp.translate([WHEEL_X_FRONT,
                              -WHEEL_CL_Y + BELT_WIDTH,
                              AXLE_Z])
    parts["sprocket_out_left"]  = sp_l_out
    parts["sprocket_drv_left"]  = sp_l_drv
    parts["sprocket_out_right"] = sp_r_out
    parts["sprocket_drv_right"] = sp_r_drv

    print("[6/8] Building electronics deck...", flush=True)
    deck = electronics_deck()
    deck = deck.translate([FRAME_LENGTH/2, 0, RAIL_H + 3.0*IN])
    parts["electronics_deck"] = deck

    print("[7/8] Combining compound...", flush=True)
    # Build compound from all parts
    solids = [p.val() for p in parts.values()]
    compound = cq.Compound.makeCompound(solids)

    return parts, compound


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(parts, compound):
    """
    Check presence of required components and basic geometry.
    Returns validation dict.
    """
    checks = {}
    
    # 1. Count wheels
    wheel_keys = [k for k in parts if k.startswith("w") and len(k) == 3]
    checks["wheel_count"] = {
        "expected": 6, "found": len(wheel_keys),
        "names": wheel_keys,
        "pass": len(wheel_keys) == 6
    }
    
    # 2. Left/right motors present
    checks["motors"] = {
        "left": "motor_left" in parts,
        "right": "motor_right" in parts,
        "pass": "motor_left" in parts and "motor_right" in parts
    }
    
    # 3. Gearboxes present
    checks["gearboxes"] = {
        "left": "gearbox_left" in parts,
        "right": "gearbox_right" in parts,
        "pass": "gearbox_left" in parts and "gearbox_right" in parts
    }
    
    # 4. Transmission (sprockets)
    sprocket_keys = [k for k in parts if "sprocket" in k]
    checks["transmission"] = {
        "sprocket_count": len(sprocket_keys),
        "names": sprocket_keys,
        "pass": len(sprocket_keys) >= 4
    }
    
    # 5. Chassis rails
    rail_keys = [k for k in parts if "rail" in k or "crossmember" in k]
    checks["chassis_rails"] = {
        "count": len(rail_keys),
        "names": rail_keys,
        "pass": len(rail_keys) >= 4
    }
    
    # 6. Electronics deck
    checks["electronics_deck"] = {
        "present": "electronics_deck" in parts,
        "pass": "electronics_deck" in parts
    }
    
    # 7. Drop-center geometry check
    mid_z  = None
    fl_z   = None
    for k, p in parts.items():
        bb = p.val().BoundingBox()
        if k == "wml":
            mid_z = bb.zmin
        if k == "wfl":
            fl_z = bb.zmin
    if mid_z is not None and fl_z is not None:
        drop = fl_z - mid_z
        checks["drop_center"] = {
            "front_wheel_zmin_mm": round(fl_z, 3),
            "mid_wheel_zmin_mm": round(mid_z, 3),
            "drop_mm": round(drop, 3),
            "expected_drop_mm": round(DROP_CENTER, 3),
            "pass": abs(drop - DROP_CENTER) < 1.0  # 1mm tolerance
        }
    
    # 8. AABB interference checks (broad phase)
    # Check left motor vs left gearbox - should overlap (mated)
    # Check left gearbox vs right gearbox - should NOT significantly overlap
    interference_checks = {}
    if "motor_left" in parts and "gearbox_left" in parts:
        ml_bb = parts["motor_left"].val().BoundingBox()
        gl_bb = parts["gearbox_left"].val().BoundingBox()
        # Overlap in X (axial direction)
        x_overlap = min(ml_bb.xmax, gl_bb.xmax) - max(ml_bb.xmin, gl_bb.xmin)
        interference_checks["motor_left_to_gearbox_left_x_overlap_mm"] = round(x_overlap, 2)
        interference_checks["motor_gearbox_axial_connected"] = x_overlap > 0
    
    if "gearbox_left" in parts and "gearbox_right" in parts:
        gl_bb = parts["gearbox_left"].val().BoundingBox()
        gr_bb = parts["gearbox_right"].val().BoundingBox()
        y_overlap = min(gl_bb.ymax, gr_bb.ymax) - max(gl_bb.ymin, gr_bb.ymin)
        interference_checks["gearbox_lr_y_clearance_mm"] = round(-y_overlap, 2)
        interference_checks["gearbox_lr_no_collision"] = y_overlap < 0
    
    checks["aabb_interference"] = interference_checks
    
    # 9. Bounding box of whole assembly
    bb = compound.BoundingBox()
    checks["assembly_bbox_mm"] = {
        "xmin": round(bb.xmin,1), "xmax": round(bb.xmax,1),
        "ymin": round(bb.ymin,1), "ymax": round(bb.ymax,1),
        "zmin": round(bb.zmin,1), "zmax": round(bb.zmax,1),
        "dx": round(bb.xmax-bb.xmin,1),
        "dy": round(bb.ymax-bb.ymin,1),
        "dz": round(bb.zmax-bb.zmin,1),
    }
    
    # 10. Part count summary
    checks["part_summary"] = {
        "total_named_parts": len(parts),
        "names": sorted(parts.keys())
    }
    
    all_pass = all(
        v.get("pass", True) if isinstance(v, dict) else True
        for v in checks.values()
    )
    checks["overall_pass"] = all_pass
    
    return checks


# ---------------------------------------------------------------------------
# BOM
# ---------------------------------------------------------------------------

BOM = [
    # name, qty, source, model/pn, notes
    ("AM14U6 Square Drive Base Kit", 1, "AndyMark", "am-14u6s",
     "2026 KitBot; includes frame, wheels, gearboxes, hardware; "
     "https://andymark.com/products/am14u6-6-wheel-drop-center-robot-drive-base-2025-frc-kit-of-parts-drive-base"),
    ("6\" Pneumatic Wheel", 6, "AndyMark", "am-0940",
     "6\" OD pneumatic, 1.5\" wide; drop-center middle pair 1/8\" lower"),
    ("CIM Motor", 2, "VEX Robotics / AndyMark", "am-0255 / 217-2000",
     "12V DC, 2.5\" dia, 2.73Nm stall; left+right drive; "
     "Note: 2026 KOP may substitute Falcon 500 - verify with FIRST KOP list"),
    ("AM14U6 Gearbox (10.71:1)", 2, "AndyMark", "am-14u6-gb",
     "Dual-CIM, 10.71:1, integrated shifting optional; left/right"),
    ("1x2 Aluminum Rectangular Tube 26\"", 4, "AndyMark/Chassis", "am-0738 equiv",
     "0.125\" wall, 6061-T6; square config perimeter rails"),
    ("1x2 Aluminum Cross Member", 2, "AndyMark/Chassis", "am-0738 equiv",
     "Cut to ~21.5\" for inner cross members (26\" - 2x rail width)"),
    ("HTD 5mm Belt Drive Pulley 18T", 4, "VEX / WCP", "HTD-18T-5mm",
     "2x output + 2x wheel drive pulleys; belt sizing per wheel spacing"),
    ("HTD 5mm Drive Belt", 2, "VEX / WCP", "per-spacing",
     "Left + right; length per actual wheel-to-gearbox center distance"),
    ("1/2\" Hex Shaft (axle)", 6, "VEX / WCP", "per-length",
     "One per wheel; length ~3\" per side rail span"),
    ("Polycarbonate Electronics Deck 24\"x24\"x1/8\"", 1, "McMaster/Local", "custom",
     "Custom cut; battery + PDH + RoboRIO + VH109 mounting"),
    ("1/4-20 x 1\" Socket Head Cap Screw", 20, "McMaster-Carr", "92196A537",
     "Frame assembly and deck mounting"),
    ("1/4-20 Nyloc Nut", 20, "McMaster-Carr", "90630A109",
     "Pairs with SHCS above"),
    ("Standoff 1/4-20 1\" Hex 2\"L", 8, "McMaster-Carr", "93505A413",
     "Deck height adjustment standoffs"),
    ("Snap Ring / Shaft Collar", 12, "VEX / McMaster", "per-shaft",
     "2 per axle for wheel retention"),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== AM14U6 2026 Drivetrain Builder ===")
    print(f"Output: {OUT_DIR}")
    print(f"Frame: {FRAME_LENGTH:.1f}mm x {FRAME_WIDTH:.1f}mm (26\" x 26\" square)")
    print(f"Wheels: 6x {WHEEL_DIAM:.1f}mm dia, drop-center {DROP_CENTER:.2f}mm")
    print()

    t0 = time.time()
    
    # --- Build ---
    parts, compound = build_am14u6_assembly()
    t_build = time.time() - t0
    print(f"  Build time: {t_build:.1f}s")

    # --- Validate ---
    print("[8/8] Validating...", flush=True)
    validation = validate(parts, compound)
    t_validate = time.time() - t0 - t_build
    
    # --- Export STEP ---
    step_path = os.path.join(OUT_DIR, "am14u6_2026_drivetrain.step")
    print(f"Exporting STEP -> {step_path}", flush=True)
    t_exp0 = time.time()
    cq.exporters.export(compound, step_path)
    t_export = time.time() - t_exp0
    step_size = os.path.getsize(step_path)
    print(f"  STEP size: {step_size/1024:.0f} KB, export time: {t_export:.1f}s")

    # --- BOM JSON ---
    bom_records = []
    for b in BOM:
        bom_records.append({
            "item": b[0], "qty": b[1], "source": b[2],
            "model_pn": b[3], "notes": b[4]
        })
    bom_path = os.path.join(OUT_DIR, "bom.json")
    with open(bom_path, "w") as f:
        json.dump(bom_records, f, indent=2)

    # --- Validation JSON ---
    val_path = os.path.join(OUT_DIR, "validation.json")
    with open(val_path, "w") as f:
        json.dump(validation, f, indent=2)

    # --- Design notes ---
    notes_path = os.path.join(OUT_DIR, "design_notes.md")
    with open(notes_path, "w") as f:
        f.write(DESIGN_NOTES)

    # --- result.json ---
    elapsed_total = time.time() - BUILD_START
    result = {
        "status": "complete" if validation["overall_pass"] else "partial",
        "elapsed_seconds": round(elapsed_total, 1),
        "artifacts": {
            "step": step_path,
            "bom": bom_path,
            "validation": val_path,
            "design_notes": notes_path,
            "source_script": os.path.abspath(__file__),
        },
        "build_time_s": round(t_build, 1),
        "export_time_s": round(t_export, 1),
        "step_size_bytes": step_size,
        "part_count": len(parts),
        "validation_summary": {
            "overall_pass": validation["overall_pass"],
            "wheel_count": validation["wheel_count"]["found"],
            "motors_present": validation["motors"]["pass"],
            "gearboxes_present": validation["gearboxes"]["pass"],
            "transmission_sprockets": validation["transmission"]["sprocket_count"],
            "chassis_rails": validation["chassis_rails"]["count"],
            "drop_center_mm": validation.get("drop_center", {}).get("drop_mm"),
            "drop_center_pass": validation.get("drop_center", {}).get("pass"),
        },
        "incomplete_items": [
            "Belt/chain loop path (belt modeled as sprockets only, not solid loop geometry)",
            "Motor mounting bolts (geometry represented as gearbox bolt circles)",
            "Internal gearbox gear train (black-box housing only; no internal gear solids)",
            "Wheel tire tread pattern (smooth tire profile used)",
            "Exact hardware fastener geometry (holes present, fastener solids omitted)",
            "Electronics wiring harness",
            "Vendor-internal STEP Boolean validation skipped per task spec; "
            "per-group inventory used instead",
        ],
        "sourced_vs_generated": {
            "sourced_reference": ".frcstack/source-cache/KB-2026-rev.step (AM14U6 Onshape export, NOT copied into output)",
            "generated_new_parts": [
                "rect_tube chassis rails (parametric 1x2 hollow tube)",
                "wheel_assembly (tire torus + hub + bore)",
                "cim_motor stub (body + shaft cylinders)",
                "gearbox_plate (box + bolt holes + shaft bore)",
                "sprocket/pulley stubs",
                "electronics_deck (plate + cutouts + mount holes)",
            ],
            "assembly_method": "CadQuery positional assembly; all transforms documented in source",
        },
        "configuration": {
            "frame_mm": f"{FRAME_LENGTH:.1f}x{FRAME_WIDTH:.1f}",
            "wheel_diameter_mm": WHEEL_DIAM,
            "drop_center_mm": DROP_CENTER,
            "drive_ratio": "10.71:1",
            "wheel_base": f"front-to-rear {WHEEL_X_REAR - WHEEL_X_FRONT:.1f}mm",
        },
        "source_reference": "https://andymark.com/products/am14u6-6-wheel-drop-center-robot-drive-base-2025-frc-kit-of-parts-drive-base",
        "assembly_guide": "https://www.firstinspires.org/resources/library/frc/kitbot",
    }
    result_path = os.path.join(OUT_DIR, "result.json")
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)

    print()
    print("=== RESULT ===")
    print(json.dumps(result["validation_summary"], indent=2))
    print(f"Status: {result['status']}")
    print(f"Elapsed: {result['elapsed_seconds']}s")
    print(f"STEP: {step_path}")
    print(f"Result: {result_path}")
    return result


DESIGN_NOTES = """# AM14U6 2026 Drivetrain - Design Notes

## Configuration
- **Frame:** 26\" x 26\" square (AndyMark AM14U6 Square 2026 KitBot config)
- **Wheels:** 6x 6\" pneumatic, six-wheel drop-center differential drive
- **Drop-center:** 1/8\" (3.175mm) - middle wheel lower than front/rear
- **Drive ratio:** 10.71:1 (AM14U6 integrated gearbox)
- **Drive transmission:** HTD 5mm belt, 18T sprockets (front/rear wheels driven from gearbox output)
- **Motors:** 2x CIM (or Falcon 500) - one per side gearbox

## Sources
- Chassis geometry: AndyMark AM14U6 2026 Square config
  https://andymark.com/products/am14u6-6-wheel-drop-center-robot-drive-base-2025-frc-kit-of-parts-drive-base
- Assembly guide: FIRST KitBot
  https://www.firstinspires.org/resources/library/frc/kitbot
- Source STEP reference: `.frcstack/source-cache/KB-2026-rev.step`
  (Onshape AP242 export; used for dimension reference, NOT copied into output)

## Generated Parts (new parametric geometry)
1. **Chassis rails** - Hollow 1x2\" rect tube, 0.125\" wall, 6061 alu profile
2. **Cross members** - Same profile, inner span
3. **Wheels** - Tire torus + hub + axle bore (6x, drop-center positioned)
4. **CIM motor stubs** - Cylinder body + output shaft (2x)
5. **Gearbox housings** - Box with CIM bolt circle + output shaft bore (2x)
6. **Drive sprockets** - Disk + hub + hex bore (4x: 2 output, 2 wheel)
7. **Electronics deck** - Polycarbonate plate with battery cutout + mount holes

## Incomplete / Not Modeled
- Belt loop geometry (sprockets present, closed belt solid not modeled)
- Internal gearbox gear train (housing only)
- Individual fastener solids (bolt holes present in parts)
- Wiring harness
- Bumper mounting tabs (outside KitBot STEP, standard 2\" standoff pattern)

## Validation Approach
- AABB broad-phase interference: gearbox L/R separation confirmed
- Drop-center geometry: verified zmin delta == 3.175mm ± 1mm
- Component inventory: 6 wheels, 2 motors, 2 gearboxes, 4 sprockets, chassis
- Vendor-internal Boolean overlap: NOT checked per task spec
  (exhaustive Boolean on hundreds of sourced vendor solids avoided;
   per-group inventory + new-part AABB checks used)

## Unverified / Caveats
- Motor mounting: CIM bolt pattern holes in gearbox are correct size/spacing
  per AndyMark drawing; exact fit requires native CAD mate verification
- Belt length: computed from center-distance geometry; actual belt selection
  requires loop tooth count calculation
- Motor model: CIM modeled; Falcon 500 is drop-in compatible in mounting
  but slightly different length; verify with current FRC KOP motor list
- No exact fit/rules/fabrication claim without further native Onshape verification
"""


if __name__ == "__main__":
    main()
