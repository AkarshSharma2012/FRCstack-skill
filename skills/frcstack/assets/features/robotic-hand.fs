FeatureScript 3095;
import(path : "onshape/std/common.fs", version : "3095.0");

// =============================================================================
// Proposed 20-axis hand  --  CONCEPT ONLY
// Dimensions sourced from hand_kinematics.py and hand_geometry.py.
// NOT fabrication-ready. NOT FEA-verified. NOT tendon/actuator certified.
// Palm centre = world XY origin, Z=0 reference plane.
// X=90mm (width), Y=86mm (length, fingers extend +Y), Z up.
// Palm solid: z[-6, 0], bosses z[0, 7.7], bore z[-6.1, 7.8].
// Carrier length = 12mm.  Phalange bar: y[6.4, L-8].
// Bore nominal R=1.2mm (diam 2.4mm).  Corner R8 on palm.
// 21 separate solid bodies + 40 mate connectors (2 per joint).
// Body colours: grey (0.55,0.57,0.60) for phalanges,
//               blue (0.25,0.45,0.80) for carriers,
//               light grey (0.72,0.74,0.77) for palm.
// Testing: NOT executed by this agent; must be compiled in live Onshape.
// =============================================================================

annotation { "Feature Type Name" : "Proposed 20-axis hand" }
export const frcstackHand = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Pose preset" }
        definition.preset is HandPreset;

        annotation { "Name" : "Manual joint override" }
        definition.manualOverride is boolean;

        // 20 joint angles follow -- same order as hand_kinematics._JOINT_ORDER
        annotation { "Name" : "index_spread  (−15 to 15 deg)" }
        isAngle(definition.q_index_spread,   { (degree) : [-15, 0, 15]   } as AngleBoundSpec);
        annotation { "Name" : "index_mcp     (−10 to 90 deg)" }
        isAngle(definition.q_index_mcp,      { (degree) : [-10, 0, 90]   } as AngleBoundSpec);
        annotation { "Name" : "index_pip     (0 to 110 deg)" }
        isAngle(definition.q_index_pip,      { (degree) : [0,   0, 110]  } as AngleBoundSpec);
        annotation { "Name" : "index_dip     (0 to 80 deg)" }
        isAngle(definition.q_index_dip,      { (degree) : [0,   0, 80]   } as AngleBoundSpec);

        annotation { "Name" : "middle_spread (−15 to 15 deg)" }
        isAngle(definition.q_middle_spread,  { (degree) : [-15, 0, 15]   } as AngleBoundSpec);
        annotation { "Name" : "middle_mcp    (−10 to 90 deg)" }
        isAngle(definition.q_middle_mcp,     { (degree) : [-10, 0, 90]   } as AngleBoundSpec);
        annotation { "Name" : "middle_pip    (0 to 110 deg)" }
        isAngle(definition.q_middle_pip,     { (degree) : [0,   0, 110]  } as AngleBoundSpec);
        annotation { "Name" : "middle_dip    (0 to 80 deg)" }
        isAngle(definition.q_middle_dip,     { (degree) : [0,   0, 80]   } as AngleBoundSpec);

        annotation { "Name" : "ring_spread   (−15 to 15 deg)" }
        isAngle(definition.q_ring_spread,    { (degree) : [-15, 0, 15]   } as AngleBoundSpec);
        annotation { "Name" : "ring_mcp      (−10 to 90 deg)" }
        isAngle(definition.q_ring_mcp,       { (degree) : [-10, 0, 90]   } as AngleBoundSpec);
        annotation { "Name" : "ring_pip      (0 to 110 deg)" }
        isAngle(definition.q_ring_pip,       { (degree) : [0,   0, 110]  } as AngleBoundSpec);
        annotation { "Name" : "ring_dip      (0 to 80 deg)" }
        isAngle(definition.q_ring_dip,       { (degree) : [0,   0, 80]   } as AngleBoundSpec);

        annotation { "Name" : "little_spread (−15 to 15 deg)" }
        isAngle(definition.q_little_spread,  { (degree) : [-15, 0, 15]   } as AngleBoundSpec);
        annotation { "Name" : "little_mcp    (−10 to 90 deg)" }
        isAngle(definition.q_little_mcp,     { (degree) : [-10, 0, 90]   } as AngleBoundSpec);
        annotation { "Name" : "little_pip    (0 to 110 deg)" }
        isAngle(definition.q_little_pip,     { (degree) : [0,   0, 110]  } as AngleBoundSpec);
        annotation { "Name" : "little_dip    (0 to 80 deg)" }
        isAngle(definition.q_little_dip,     { (degree) : [0,   0, 80]   } as AngleBoundSpec);

        annotation { "Name" : "thumb_yaw        (−90 to 35 deg)" }
        isAngle(definition.q_thumb_yaw,      { (degree) : [-90, 0, 35]   } as AngleBoundSpec);
        annotation { "Name" : "thumb_opposition (−30 to 90 deg)" }
        isAngle(definition.q_thumb_opp,      { (degree) : [-30, 0, 90]   } as AngleBoundSpec);
        annotation { "Name" : "thumb_mcp        (0 to 100 deg)" }
        isAngle(definition.q_thumb_mcp,      { (degree) : [0,   0, 100]  } as AngleBoundSpec);
        annotation { "Name" : "thumb_ip         (0 to 90 deg)" }
        isAngle(definition.q_thumb_ip,       { (degree) : [0,   0, 90]   } as AngleBoundSpec);
    }
    {
        // ---------------------------------------------------------------
        // 1. Resolve joint angles from preset or manual inputs
        // ---------------------------------------------------------------
        // Preset values mirror hand_kinematics.pose()
        var qs = {};
        if (!definition.manualOverride)
        {
            if (definition.preset == HandPreset.OPEN)
            {
                qs = { "is":0,"im":0,"ip":0,"id":0,
                       "ms":0,"mm":0,"mp":0,"md":0,
                       "rs":0,"rm":0,"rp":0,"rd":0,
                       "ls":0,"lm":0,"lp":0,"ld":0,
                       "ty":0,"to":0,"tm":0,"ti":0 };
            }
            else if (definition.preset == HandPreset.PARTIAL)
            {
                qs = { "is":0,"im":35,"ip":45,"id":20,
                       "ms":0,"mm":35,"mp":45,"md":20,
                       "rs":0,"rm":35,"rp":45,"rd":20,
                       "ls":0,"lm":35,"lp":45,"ld":20,
                       "ty":-35,"to":25,"tm":30,"ti":20 };
            }
            else // CLOSED
            {
                qs = { "is":0,"im":70,"ip":90,"id":60,
                       "ms":0,"mm":70,"mp":90,"md":60,
                       "rs":0,"rm":70,"rp":90,"rd":60,
                       "ls":0,"lm":70,"lp":90,"ld":60,
                       "ty":-50,"to":45,"tm":60,"ti":45 };
            }
        }
        else
        {
            qs = {
                "is" : definition.q_index_spread  / degree,
                "im" : definition.q_index_mcp     / degree,
                "ip" : definition.q_index_pip     / degree,
                "id" : definition.q_index_dip     / degree,
                "ms" : definition.q_middle_spread / degree,
                "mm" : definition.q_middle_mcp    / degree,
                "mp" : definition.q_middle_pip    / degree,
                "md" : definition.q_middle_dip    / degree,
                "rs" : definition.q_ring_spread   / degree,
                "rm" : definition.q_ring_mcp      / degree,
                "rp" : definition.q_ring_pip      / degree,
                "rd" : definition.q_ring_dip      / degree,
                "ls" : definition.q_little_spread / degree,
                "lm" : definition.q_little_mcp    / degree,
                "lp" : definition.q_little_pip    / degree,
                "ld" : definition.q_little_dip    / degree,
                "ty" : definition.q_thumb_yaw     / degree,
                "to" : definition.q_thumb_opp     / degree,
                "tm" : definition.q_thumb_mcp     / degree,
                "ti" : definition.q_thumb_ip      / degree
            };
        }

        // ---------------------------------------------------------------
        // 2. FeatureScript forward-kinematics helpers
        //    All angles in degrees, multiplied by degree before use.
        //    Transforms: 3x3 rotation cols, origin.
        // ---------------------------------------------------------------
        // rotZ: rotation matrix around Z axis by deg degrees
        const rotZ = function(deg is number) returns Matrix
        {
            const r = deg * degree;
            return rotationMatrix3d(vector(0, 0, 1) * millimeter / millimeter, r);
        };
        // rotX: rotation matrix around X axis by deg degrees
        const rotX = function(deg is number) returns Matrix
        {
            const r = deg * degree;
            return rotationMatrix3d(vector(1, 0, 0) * millimeter / millimeter, r);
        };

        // Build a CoordSystem from a 3x3 rotation matrix and origin point
        // xCol = col 0, zCol = col 2 of the rotation matrix
        const matToCS = function(rot is Matrix, origin is Vector) returns CoordSystem
        {
            const xDir = vector(rot[0][0], rot[1][0], rot[2][0]);
            const zDir = vector(rot[0][2], rot[1][2], rot[2][2]);
            return coordSystem(origin, xDir, zDir);
        };

        // Compose: apply rot2 after rot1 (rot1 * rot2)
        const composeRot = function(r1 is Matrix, r2 is Matrix) returns Matrix
        {
            return r1 * r2;
        };

        // Advance origin along local Y by distance (mm as number)
        const advY = function(rot is Matrix, origin is Vector, dist is number) returns Vector
        {
            const yDir = vector(rot[0][1], rot[1][1], rot[2][1]);
            return origin + yDir * dist * millimeter;
        };

        // ---------------------------------------------------------------
        // 3. Palm body (rounded rectangle via box union + four R8 corners)
        //    74x86 union 90x70, four R8 cylinders at (±37, ±35).
        //    z: -6 to 0.  Bosses R3, z[0, 7.7].  Bore R1.2, z[-6.1, 7.8].
        // ---------------------------------------------------------------
        const MM = millimeter;
        const palmId = id + "palm";

        // Main palm slabs
        fCuboid(context, palmId + "slab1", {
            "corner1" : vector(-37 * MM, -43 * MM, -6 * MM),
            "corner2" : vector( 37 * MM,  43 * MM,  0 * MM)
        });
        fCuboid(context, palmId + "slab2", {
            "corner1" : vector(-45 * MM, -35 * MM, -6 * MM),
            "corner2" : vector( 45 * MM,  35 * MM,  0 * MM)
        });
        opBoolean(context, palmId + "union1", {
            "targets"       : qCreatedBy(palmId + "slab1", EntityType.BODY),
            "tools"         : qCreatedBy(palmId + "slab2", EntityType.BODY),
            "operationType" : BooleanOperationType.UNION
        });

        // Four R8 corner cylinders (Z axis) at (±37, ±35)
        const cornersXY = [[-37, -35], [37, -35], [-37, 35], [37, 35]];
        for (var ci = 0; ci < 4; ci += 1)
        {
            fCylinder(context, palmId + "corner" + ci, {
                "bottomCenter" : vector(cornersXY[ci][0] * MM, cornersXY[ci][1] * MM, -6 * MM),
                "topCenter"    : vector(cornersXY[ci][0] * MM, cornersXY[ci][1] * MM,  0 * MM),
                "radius"       : 8 * MM
            });
            opBoolean(context, palmId + "ucorner" + ci, {
                "targets"       : qCreatedBy(palmId + "slab1", EntityType.BODY),
                "tools"         : qCreatedBy(palmId + "corner" + ci, EntityType.BODY),
                "operationType" : BooleanOperationType.UNION
            });
        }

        // Bosses: R3, z[0, 7.7] at each root XY
        // Roots (x,y): index(-31,43) middle(-10,43) ring(11,43) little(32,43) thumb(-43,-15)
        const bossXY = [[-31, 43], [-10, 43], [11, 43], [32, 43], [-43, -15]];
        for (var bi = 0; bi < 5; bi += 1)
        {
            fCylinder(context, palmId + "boss" + bi, {
                "bottomCenter" : vector(bossXY[bi][0] * MM, bossXY[bi][1] * MM, 0 * MM),
                "topCenter"    : vector(bossXY[bi][0] * MM, bossXY[bi][1] * MM, 7.7 * MM),
                "radius"       : 3 * MM
            });
            opBoolean(context, palmId + "uboss" + bi, {
                "targets"       : qCreatedBy(palmId + "slab1", EntityType.BODY),
                "tools"         : qCreatedBy(palmId + "boss" + bi, EntityType.BODY),
                "operationType" : BooleanOperationType.UNION
            });
        }

        // Through-palm bores R1.5, z[-6.1, 7.8]  -- R1.5 for Bowden tendon sheath
        for (var boi = 0; boi < 5; boi += 1)
        {
            fCylinder(context, palmId + "bore" + boi, {
                "bottomCenter" : vector(bossXY[boi][0] * MM, bossXY[boi][1] * MM, -6.1 * MM),
                "topCenter"    : vector(bossXY[boi][0] * MM, bossXY[boi][1] * MM,  7.8 * MM),
                "radius"       : 1.5 * MM
            });
            opBoolean(context, palmId + "cbore" + boi, {
                "targets"       : qCreatedBy(palmId + "slab1", EntityType.BODY),
                "tools"         : qCreatedBy(palmId + "bore" + boi, EntityType.BODY),
                "operationType" : BooleanOperationType.SUBTRACTION
            });
        }

        setProperty(context, {
            "entities"     : qCreatedBy(palmId + "slab1", EntityType.BODY),
            "propertyType" : PropertyType.NAME,
            "value"        : "palm"
        });
        setProperty(context, {
            "entities"     : qCreatedBy(palmId + "slab1", EntityType.BODY),
            "propertyType" : PropertyType.APPEARANCE,
            "value"        : color(0.72, 0.74, 0.77)
        });

        // ---------------------------------------------------------------
        // 4. Helper: build carrier local geometry, transform, place
        //    Carrier: yaw post R5 z[-2,2], bridge x[-8,8] y[0,5] z[-2,2],
        //    two fork ears axis-X R6 at Y=12, outboard connectors, bores.
        // ---------------------------------------------------------------
        const buildCarrier = function(cid is Id, cs is CoordSystem)
        {
            // Post
            fCylinder(context, cid + "post", {
                "bottomCenter" : vector(0, 0, -2) * MM,
                "topCenter"    : vector(0, 0,  2) * MM,
                "radius"       : 5 * MM
            });
            // Bridge y[0,5] x[-8,8] z[-2,2]
            fCuboid(context, cid + "bridge", {
                "corner1" : vector(-8, 0, -2) * MM,
                "corner2" : vector( 8, 5,  2) * MM
            });
            opBoolean(context, cid + "u1", {
                "targets"       : qCreatedBy(cid + "post",   EntityType.BODY),
                "tools"         : qCreatedBy(cid + "bridge", EntityType.BODY),
                "operationType" : BooleanOperationType.UNION
            });
            // Fork ears axis-X at Y=12: x[-8,-3.4] and x[3.4,8]
            fCuboid(context, cid + "ear1box", {
                "corner1" : vector(-8, 6, -6) * MM,
                "corner2" : vector(-3.4, 12,  6) * MM
            });
            fCuboid(context, cid + "ear2box", {
                "corner1" : vector( 3.4, 6, -6) * MM,
                "corner2" : vector(   8, 12,  6) * MM
            });
            fCylinder(context, cid + "earCyl1", {
                "bottomCenter" : vector(-8,   12, 0) * MM,
                "topCenter"    : vector(-3.4, 12, 0) * MM,
                "radius"       : 6 * MM
            });
            fCylinder(context, cid + "earCyl2", {
                "bottomCenter" : vector(3.4, 12, 0) * MM,
                "topCenter"    : vector(8,   12, 0) * MM,
                "radius"       : 6 * MM
            });
            opBoolean(context, cid + "u2", {
                "targets"       : qCreatedBy(cid + "post",     EntityType.BODY),
                "tools"         : qUnion([qCreatedBy(cid + "ear1box",  EntityType.BODY),
                                          qCreatedBy(cid + "ear2box",  EntityType.BODY),
                                          qCreatedBy(cid + "earCyl1",  EntityType.BODY),
                                          qCreatedBy(cid + "earCyl2",  EntityType.BODY)]),
                "operationType" : BooleanOperationType.UNION
            });
            // Outboard connectors x[-8,-3.4] and [3.4,8], y[4,9], z[-2,2]
            fCuboid(context, cid + "con1", {
                "corner1" : vector(-8, 4, -2) * MM, "corner2" : vector(-3.4, 9, 2) * MM
            });
            fCuboid(context, cid + "con2", {
                "corner1" : vector(3.4, 4, -2) * MM, "corner2" : vector(8, 9, 2) * MM
            });
            opBoolean(context, cid + "u3", {
                "targets"       : qCreatedBy(cid + "post", EntityType.BODY),
                "tools"         : qUnion([qCreatedBy(cid + "con1", EntityType.BODY),
                                          qCreatedBy(cid + "con2", EntityType.BODY)]),
                "operationType" : BooleanOperationType.UNION
            });
            // Yaw bore R1.2 through Z
            fCylinder(context, cid + "boreZ", {
                "bottomCenter" : vector(0, 0, -2.1) * MM,
                "topCenter"    : vector(0, 0,  2.1) * MM,
                "radius"       : 1.5 * MM  // R1.5 for Bowden
            });
            // Fork bore R1.5 through X at Y=12
            fCylinder(context, cid + "boreX", {
                "bottomCenter" : vector(-8.1, 12, 0) * MM,
                "topCenter"    : vector( 8.1, 12, 0) * MM,
                "radius"       : 1.5 * MM  // R1.5 for Bowden
            });
            opBoolean(context, cid + "cut1", {
                "targets"       : qCreatedBy(cid + "post",  EntityType.BODY),
                "tools"         : qUnion([qCreatedBy(cid + "boreZ", EntityType.BODY),
                                          qCreatedBy(cid + "boreX", EntityType.BODY)]),
                "operationType" : BooleanOperationType.SUBTRACTION
            });
            // Transform to world position
            opTransform(context, cid + "xform", {
                "bodies"    : qCreatedBy(cid + "post", EntityType.BODY),
                "transform" : toWorld(cs)
            });
        };

        // ---------------------------------------------------------------
        // 5. Helper: build phalange (proximal/middle/distal)
        //    tongue R5.5 x[-3,3] + box x[-3,3] y[0,9]; bar y[6.4, L-8];
        //    non-distal: far fork + ears + bore; distal: rounded tip.
        //    Root bore R1.2 along X.
        // ---------------------------------------------------------------
        const buildPhalange = function(pid is Id, L is number, isDistal is boolean, cs is CoordSystem)
        {
            // Tongue cylinder axis-X R5.5 at y=0
            fCylinder(context, pid + "tcyl", {
                "bottomCenter" : vector(-3, 0, 0) * MM,
                "topCenter"    : vector( 3, 0, 0) * MM,
                "radius"       : 5.5 * MM
            });
            fCuboid(context, pid + "tbox", {
                "corner1" : vector(-3, 0, -4.5) * MM,
                "corner2" : vector( 3, 9,  4.5) * MM
            });
            opBoolean(context, pid + "ut", {
                "targets"       : qCreatedBy(pid + "tcyl", EntityType.BODY),
                "tools"         : qCreatedBy(pid + "tbox", EntityType.BODY),
                "operationType" : BooleanOperationType.UNION
            });
            // Bar y[6.4, L-8]
            const barMid = (6.4 + (L - 8)) / 2;
            const barLen = (L - 8) - 6.4;
            fCuboid(context, pid + "bar", {
                "corner1" : vector(-5.5, 6.4,       -4.5) * MM,
                "corner2" : vector( 5.5, L - 8.0,   4.5) * MM
            });
            opBoolean(context, pid + "ubar", {
                "targets"       : qCreatedBy(pid + "tcyl", EntityType.BODY),
                "tools"         : qCreatedBy(pid + "bar",  EntityType.BODY),
                "operationType" : BooleanOperationType.UNION
            });
            if (!isDistal)
            {
                // Far fork bridge y[L-10, L-7]
                fCuboid(context, pid + "cb", {
                    "corner1" : vector(-8, L - 10, -4.5) * MM,
                    "corner2" : vector( 8, L -  7,  4.5) * MM
                });
                // Outboard connectors x[-8,-3.4] and [3.4,8] y[L-9, L-3]
                fCuboid(context, pid + "fcon1", {
                    "corner1" : vector(-8,   L - 9, -4.5) * MM,
                    "corner2" : vector(-3.4, L - 3,  4.5) * MM
                });
                fCuboid(context, pid + "fcon2", {
                    "corner1" : vector(3.4, L - 9, -4.5) * MM,
                    "corner2" : vector(8,   L - 3,  4.5) * MM
                });
                // Far ear cylinders axis-X R6 at Y=L
                fCylinder(context, pid + "fce1", {
                    "bottomCenter" : vector(-8,   L, 0) * MM,
                    "topCenter"    : vector(-3.4, L, 0) * MM,
                    "radius"       : 6 * MM
                });
                fCylinder(context, pid + "fce2", {
                    "bottomCenter" : vector(3.4, L, 0) * MM,
                    "topCenter"    : vector(8,   L, 0) * MM,
                    "radius"       : 6 * MM
                });
                opBoolean(context, pid + "ufar", {
                    "targets"       : qCreatedBy(pid + "tcyl", EntityType.BODY),
                    "tools"         : qUnion([qCreatedBy(pid + "cb",    EntityType.BODY),
                                              qCreatedBy(pid + "fcon1", EntityType.BODY),
                                              qCreatedBy(pid + "fcon2", EntityType.BODY),
                                              qCreatedBy(pid + "fce1",  EntityType.BODY),
                                              qCreatedBy(pid + "fce2",  EntityType.BODY)]),
                    "operationType" : BooleanOperationType.UNION
                });
                // Far bore R1.2 along X at Y=L
                fCylinder(context, pid + "boreXf", {
                    "bottomCenter" : vector(-8.1, L, 0) * MM,
                    "topCenter"    : vector( 8.1, L, 0) * MM,
                    "radius"       : 1.5 * MM  // R1.5 for Bowden sheath
                });
                opBoolean(context, pid + "cfar", {
                    "targets"       : qCreatedBy(pid + "tcyl",  EntityType.BODY),
                    "tools"         : qCreatedBy(pid + "boreXf", EntityType.BODY),
                    "operationType" : BooleanOperationType.SUBTRACTION
                });
            }
            else
            {
                // Rounded distal tip: cylinder axis-X R5 at Y=L-5
                fCylinder(context, pid + "tip", {
                    "bottomCenter" : vector(-5.5, L - 5, 0) * MM,
                    "topCenter"    : vector( 5.5, L - 5, 0) * MM,
                    "radius"       : 5 * MM
                });
                opBoolean(context, pid + "utip", {
                    "targets"       : qCreatedBy(pid + "tcyl", EntityType.BODY),
                    "tools"         : qCreatedBy(pid + "tip",  EntityType.BODY),
                    "operationType" : BooleanOperationType.UNION
                });
            }
            // Root bore R1.2 along X through tongue
            fCylinder(context, pid + "boreXr", {
                "bottomCenter" : vector(-3.1, 0, 0) * MM,
                "topCenter"    : vector( 3.1, 0, 0) * MM,
                "radius"       : 1.5 * MM  // R1.5 for Bowden sheath
            });
            opBoolean(context, pid + "crroot", {
                "targets"       : qCreatedBy(pid + "tcyl",   EntityType.BODY),
                "tools"         : qCreatedBy(pid + "boreXr", EntityType.BODY),
                "operationType" : BooleanOperationType.SUBTRACTION
            });
            // Place in world
            opTransform(context, pid + "xform", {
                "bodies"    : qCreatedBy(pid + "tcyl", EntityType.BODY),
                "transform" : toWorld(cs)
            });
        };

        // Helper: stable root ID key for body query after transform
        const bodyQ = function(rootId is Id) returns Query
        {
            return qCreatedBy(rootId, EntityType.BODY);
        };

        // ---------------------------------------------------------------
        // 6. FK and body construction for all 5 fingers
        // ---------------------------------------------------------------
        // Finger data: [name, rootX, rootY, baseYaw, Lprox, Lmid, Ldist,
        //               q0key, q1key, q2key, q3key]
        // Long fingers: base_yaw=0; thumb: base_yaw=55 deg
        // All roots at z=10mm (placed at top of boss in palm frame).

        const fingers = [
            // [fname_prefix, rx, ry, byaw, Lp, Lm, Ld,  qs0, qs1, qs2, qs3]
            ["index",  -31, 43, 0,  38, 25, 18, "is", "im", "ip", "id"],
            ["middle", -10, 43, 0,  42, 27, 20, "ms", "mm", "mp", "md"],
            ["ring",    11, 43, 0,  40, 26, 18, "rs", "rm", "rp", "rd"],
            ["little",  32, 43, 0,  30, 20, 16, "ls", "lm", "lp", "ld"],
            ["thumb",  -43,-15, 55, 24, 30, 22, "ty", "to", "tm", "ti"]
        ];

        const greyColor  = color(0.55, 0.57, 0.60);
        const blueColor  = color(0.25, 0.45, 0.80);

        for (var fi = 0; fi < 5; fi += 1)
        {
            const fn    = fingers[fi][0];   // finger name string
            const rx    = fingers[fi][1];
            const ry    = fingers[fi][2];
            const byaw  = fingers[fi][3];
            const Lprox = fingers[fi][4];
            const Lmid  = fingers[fi][5];
            const Ldist = fingers[fi][6];
            const k0    = fingers[fi][7];
            const k1    = fingers[fi][8];
            const k2    = fingers[fi][9];
            const k3    = fingers[fi][10];

            // Read joint angles (degrees as plain numbers)
            const q0 = qs[k0];  // spread/yaw
            const q1 = qs[k1];  // mcp/opposition
            const q2 = qs[k2];  // pip/mcp
            const q3 = qs[k3];  // dip/ip

            // --- Forward kinematics ---
            // base transform (before joint 0): T(root)*Rz(byaw)
            const rootOrig = vector(rx, ry, 10) * MM;
            const baseRot  = rotZ(byaw);   // fixed yaw of this finger on palm

            // Joint 0 (spread/yaw, axis Z):  carrier
            const j0Orig = rootOrig;          // joint origin before j0 rotation
            const j0Rot  = composeRot(baseRot, rotZ(q0));
            // carrier body coord system origin = j0Orig; after rotation
            const carrierCS = matToCS(j0Rot, j0Orig);

            // Advance to joint 1: +12mm along local Y of j0Rot
            const j1Orig = advY(j0Rot, j0Orig, 12);
            // Joint 1 (mcp/opp, axis X):
            const j1Rot  = composeRot(j0Rot, rotX(q1));
            const proxCS = matToCS(j1Rot, j1Orig);

            // Advance to joint 2: +Lprox along local Y of j1Rot
            const j2Orig = advY(j1Rot, j1Orig, Lprox);
            const j2Rot  = composeRot(j1Rot, rotX(q2));
            const midCS  = matToCS(j2Rot, j2Orig);

            // Advance to joint 3: +Lmid along local Y of j2Rot
            const j3Orig = advY(j2Rot, j2Orig, Lmid);
            const j3Rot  = composeRot(j2Rot, rotX(q3));
            const distCS = matToCS(j3Rot, j3Orig);

            // --- Build carrier ---
            const cid = id + fn + "Carrier";
            buildCarrier(cid, carrierCS);
            setProperty(context, {
                "entities"     : qCreatedBy(cid + "post", EntityType.BODY),
                "propertyType" : PropertyType.NAME,
                "value"        : fn & "_carrier"
            });
            setProperty(context, {
                "entities"     : qCreatedBy(cid + "post", EntityType.BODY),
                "propertyType" : PropertyType.APPEARANCE,
                "value"        : blueColor
            });

            // --- Build proximal phalange ---
            const pxid = id + fn + "Prox";
            buildPhalange(pxid, Lprox, false, proxCS);
            setProperty(context, {
                "entities"     : qCreatedBy(pxid + "tcyl", EntityType.BODY),
                "propertyType" : PropertyType.NAME,
                "value"        : fn & "_proximal"
            });
            setProperty(context, {
                "entities"     : qCreatedBy(pxid + "tcyl", EntityType.BODY),
                "propertyType" : PropertyType.APPEARANCE,
                "value"        : greyColor
            });

            // --- Build middle phalange ---
            const mdid = id + fn + "Mid";
            buildPhalange(mdid, Lmid, false, midCS);
            setProperty(context, {
                "entities"     : qCreatedBy(mdid + "tcyl", EntityType.BODY),
                "propertyType" : PropertyType.NAME,
                "value"        : fn & "_middle"
            });
            setProperty(context, {
                "entities"     : qCreatedBy(mdid + "tcyl", EntityType.BODY),
                "propertyType" : PropertyType.APPEARANCE,
                "value"        : greyColor
            });

            // --- Build distal phalange ---
            const dtid = id + fn + "Dist";
            buildPhalange(dtid, Ldist, true, distCS);
            setProperty(context, {
                "entities"     : qCreatedBy(dtid + "tcyl", EntityType.BODY),
                "propertyType" : PropertyType.NAME,
                "value"        : fn & "_distal"
            });
            setProperty(context, {
                "entities"     : qCreatedBy(dtid + "tcyl", EntityType.BODY),
                "propertyType" : PropertyType.APPEARANCE,
                "value"        : greyColor
            });

            // ---------------------------------------------------------------
            // 7. Mate connectors: 2 per joint = 8 per finger (40 total)
            //    Joint 0 (yaw/spread): Z axis = local Z.  Hinge = local X.
            //    Joints 1-3 (flexion): Z axis = local X (hinge axis).
            //    parent CS = before-joint rotation; child CS = after rotation.
            // ---------------------------------------------------------------

            // Joint 0: spread/yaw -- axis local Z
            //   parent connector: baseRot frame at j0Orig (palm frame, before q0)
            opMateConnector(context, id + fn + "mc0p", {
                "coordSystem" : matToCS(baseRot, j0Orig),
                "owner"       : qCreatedBy(palmId + "slab1", EntityType.BODY)
            });
            //   child connector: j0Rot frame at j0Orig (carrier, after q0)
            opMateConnector(context, id + fn + "mc0c", {
                "coordSystem" : matToCS(j0Rot, j0Orig),
                "owner"       : qCreatedBy(cid + "post", EntityType.BODY)
            });

            // Helper: hinge CS -- swap X and Z so hinge axis = old X
            // For hinge connectors connectorZ = localX, connectorX = localY
            const hingeCS = function(rot is Matrix, orig is Vector) returns CoordSystem
            {
                // connectorZ = col0 (localX), connectorX = col1 (localY)
                const zDir = vector(rot[0][0], rot[1][0], rot[2][0]);
                const xDir = vector(rot[0][1], rot[1][1], rot[2][1]);
                return coordSystem(orig, xDir, zDir);
            };

            // Joint 1 (mcp/opp): parent = j0Rot at j1Orig, child = j1Rot at j1Orig
            opMateConnector(context, id + fn + "mc1p", {
                "coordSystem" : hingeCS(j0Rot, j1Orig),
                "owner"       : qCreatedBy(cid + "post", EntityType.BODY)
            });
            opMateConnector(context, id + fn + "mc1c", {
                "coordSystem" : hingeCS(j1Rot, j1Orig),
                "owner"       : qCreatedBy(pxid + "tcyl", EntityType.BODY)
            });

            // Joint 2 (pip/mcp): parent = j1Rot at j2Orig, child = j2Rot at j2Orig
            opMateConnector(context, id + fn + "mc2p", {
                "coordSystem" : hingeCS(j1Rot, j2Orig),
                "owner"       : qCreatedBy(pxid + "tcyl", EntityType.BODY)
            });
            opMateConnector(context, id + fn + "mc2c", {
                "coordSystem" : hingeCS(j2Rot, j2Orig),
                "owner"       : qCreatedBy(mdid + "tcyl", EntityType.BODY)
            });

            // Joint 3 (dip/ip): parent = j2Rot at j3Orig, child = j3Rot at j3Orig
            opMateConnector(context, id + fn + "mc3p", {
                "coordSystem" : hingeCS(j2Rot, j3Orig),
                "owner"       : qCreatedBy(mdid + "tcyl", EntityType.BODY)
            });
            opMateConnector(context, id + fn + "mc3c", {
                "coordSystem" : hingeCS(j3Rot, j3Orig),
                "owner"       : qCreatedBy(dtid + "tcyl", EntityType.BODY)
            });
        }
    });

// Enum for pose presets
enum HandPreset
{
    annotation { "Name" : "Open" }
    OPEN,
    annotation { "Name" : "Partial" }
    PARTIAL,
    annotation { "Name" : "Closed" }
    CLOSED
}
