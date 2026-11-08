"""Continuous nominal backing geometry for a two-pulley open timing belt."""

import math

from transmission_layout import open_belt_layout


def build_open_belt(
    driver_teeth, driven_teeth, belt_teeth, pitch_mm, width_mm, backing_thickness_mm
):
    """Build the backing envelope, with pulley axes +Z and the driver at the origin.

    The driven axis is on +X, and the backing is centered about Z=0 and
    about the pitch line. Thickness is a user-supplied clearance parameter.
    Tooth profile, vendor dimensions, load and flex require separate evidence.
    """
    for name, value in (("Width", width_mm), ("Backing thickness", backing_thickness_mm)):
        if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    layout = open_belt_layout(driver_teeth, driven_teeth, belt_teeth, pitch_mm)
    driver_radius, driven_radius = (value / 2 for value in layout["pitch_diameters_mm"])
    offset = backing_thickness_mm / 2
    if offset >= min(driver_radius, driven_radius):
        raise ValueError("Backing thickness must leave a positive inner radius")

    try:
        import cadquery as cq
    except ImportError as error:
        raise RuntimeError("CadQuery is required for belt solid generation") from error

    center = layout["center_distance_mm"]
    normal_x = (driver_radius - driven_radius) / center
    normal_y = math.sqrt(1 - normal_x**2)
    base_z = -width_mm / 2

    def outline(left_radius, right_radius):
        top_left = cq.Vector(left_radius * normal_x, left_radius * normal_y, base_z)
        top_right = cq.Vector(center + right_radius * normal_x, right_radius * normal_y, base_z)
        bottom_left = cq.Vector(top_left.x, -top_left.y, base_z)
        bottom_right = cq.Vector(top_right.x, -top_right.y, base_z)
        return cq.Wire.assembleEdges([
            cq.Edge.makeLine(top_left, top_right),
            cq.Edge.makeThreePointArc(
                top_right, cq.Vector(center + right_radius, 0, base_z), bottom_right
            ),
            cq.Edge.makeLine(bottom_right, bottom_left),
            cq.Edge.makeThreePointArc(
                bottom_left, cq.Vector(-left_radius, 0, base_z), top_left
            ),
        ])

    outer = outline(driver_radius + offset, driven_radius + offset)
    inner = outline(driver_radius - offset, driven_radius - offset)
    belt = cq.Solid.extrudeLinear(outer, [inner], cq.Vector(0, 0, width_mm))
    length = layout["pitch_length_mm"]
    expected = length * backing_thickness_mm * width_mm
    if (
        len(belt.Solids()) != 1
        or not belt.isValid()
        or not math.isclose(belt.Volume(), expected, rel_tol=1e-8, abs_tol=1e-7)
    ):
        raise RuntimeError("Belt backing did not produce a valid solid with the expected volume")
    return {
        "solid": belt,
        "layout": layout,
        "nominal_pitch_circumference_mm": length,
        "expected_volume_mm3": expected,
    }
