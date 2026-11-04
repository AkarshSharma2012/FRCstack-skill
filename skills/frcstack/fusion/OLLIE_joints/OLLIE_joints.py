"""
OLLIE_joints.py -- Fusion 360 script: turns the imported ollie-stand.step into a moving robot.

How to use (Fusion 360):
  1. File > Open > ollie-stand.step  (or Upload, then open).  Leave it in the STANDING pose.
  2. Utilities > Add-Ins > Scripts and Add-Ins > Scripts tab > the green "+" > pick the folder that
     contains this file and ollie-joints.json > select OLLIE_joints > Run.
  3. The script grounds the "base" (torso) component, then creates one revolute joint per actuator
     (16 ST3215, 4 SC09, 2 heel wheels) with the real axis, pivot point and angle limits.
  4. Drag any limb, or right-click a joint > Drive Joints, to pose it.  Skate / crawl poses are in
     ollie-skate.step and ollie-crawl.step for reference.

The STEP is in millimetres; Fusion's API works in centimetres, so points are divided by 10.
"""
import json
import math
import os
import traceback

import adsk.core
import adsk.fusion

HERE = os.path.dirname(os.path.realpath(__file__))


def _find(root, name):
    for occ in root.allOccurrences:
        if occ.component.name == name or occ.name.split(":")[0] == name:
            return occ
    return None


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if design is None:
            ui.messageBox("Open ollie-stand.step first.")
            return
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        root = design.rootComponent
        spec = json.load(open(os.path.join(HERE, "ollie-joints.json")))
        base = _find(root, "base")
        if base is None:
            ui.messageBox("Could not find the 'base' component. Import ollie-stand.step (standing pose).")
            return
        base.isGrounded = True
        made, missing = 0, []
        for j in spec["joints"]:
            parent = base if j["parent"] == "base" else _find(root, j["parent"])
            child = _find(root, j["child"])
            if parent is None or child is None:
                missing.append(j["name"])
                continue
            p = adsk.core.Point3D.create(*(v / 10.0 for v in j["point_mm"]))
            geo = adsk.fusion.JointGeometry.createByPoint(p)
            ax = j["axis"]
            direction = (adsk.fusion.JointDirections.XAxisJointDirection if abs(ax[0]) > 0.5 else
                         adsk.fusion.JointDirections.YAxisJointDirection if abs(ax[1]) > 0.5 else
                         adsk.fusion.JointDirections.ZAxisJointDirection)
            ji = root.asBuiltJoints.createInput(child, parent, geo)
            ji.setAsRevoluteJointMotion(direction)
            joint = root.asBuiltJoints.add(ji)
            joint.name = j["name"]
            rng = j.get("range_deg")
            if rng:
                lim = joint.jointMotion.rotationLimits
                sign = 1.0 if (ax[0] + ax[1] + ax[2]) > 0 else -1.0
                lo, hi = sorted((sign * rng[0], sign * rng[1]))
                lim.isMinimumValueEnabled = True
                lim.minimumValue = math.radians(lo)
                lim.isMaximumValueEnabled = True
                lim.maximumValue = math.radians(hi)
            made += 1
        msg = f"OLLIE: created {made} joints."
        if missing:
            msg += "\nSkipped (component not found): " + ", ".join(missing)
        ui.messageBox(msg)
    except Exception:  # noqa: BLE001
        if ui:
            ui.messageBox("OLLIE_joints failed:\n" + traceback.format_exc())
