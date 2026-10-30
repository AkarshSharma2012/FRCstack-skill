FeatureScript 3095;
import(path : "onshape/std/common.fs", version : "3095.0");

// Proposed rectangular chassis frame -- six hollow rectangular tube rails.
// Outer dimensions motivated by published 635 x 812.8 mm and 2x1x0.0625 in
// stock references.  Corner chamfers, split rails, module mounts, and hole
// patterns are NOT implemented or claimed verified.
// UI label: Proposed rectangular chassis  (not an exact replica).

annotation { "Feature Type Name" : "Proposed rectangular chassis" }
export const frcstackFrame = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Frame width (X)" }
        isLength(definition.frameWidth, { (millimeter) : [0.01, 635, 10000] } as LengthBoundSpec);

        annotation { "Name" : "Frame length (Y)" }
        isLength(definition.frameLength, { (millimeter) : [0.01, 812.8, 10000] } as LengthBoundSpec);

        annotation { "Name" : "Stock width (tube narrow dim)" }
        isLength(definition.stockWidth, { (millimeter) : [0.01, 25.4, 10000] } as LengthBoundSpec);

        annotation { "Name" : "Stock height (tube tall dim)" }
        isLength(definition.stockHeight, { (millimeter) : [0.01, 50.8, 10000] } as LengthBoundSpec);

        annotation { "Name" : "Wall thickness" }
        isLength(definition.wall, { (millimeter) : [0.01, 1.5875, 10000] } as LengthBoundSpec);

        annotation { "Name" : "Crossbar spacing (centre-to-centre Y)" }
        isLength(definition.crossbarSpacing, { (millimeter) : [0.01, 300, 10000] } as LengthBoundSpec);
    }
    {
        // ----------------------------------------------------------------
        // Guard checks (mirror Python _validate)
        // ----------------------------------------------------------------
        if (2 * definition.wall >= definition.stockWidth)
            throw regenError("2 * wall must be < stock width", ["wall", "stockWidth"]);
        if (2 * definition.wall >= definition.stockHeight)
            throw regenError("2 * wall must be < stock height", ["wall", "stockHeight"]);
        if (definition.frameWidth <= 2 * definition.stockWidth)
            throw regenError("Frame width must be > 2 * stock width", ["frameWidth", "stockWidth"]);
        if (definition.frameLength <= 3 * definition.stockWidth)
            throw regenError("Frame length must be > 3 * stock width", ["frameLength", "stockWidth"]);
        if (definition.crossbarSpacing <= definition.stockWidth)
            throw regenError("Crossbar spacing must be > stock width", ["crossbarSpacing", "stockWidth"]);
        if (definition.crossbarSpacing >= definition.frameLength - 3 * definition.stockWidth)
            throw regenError("Crossbar spacing must be < frameLength - 3*stockWidth",
                             ["crossbarSpacing", "frameLength", "stockWidth"]);

        // ----------------------------------------------------------------
        // Convenience aliases
        // ----------------------------------------------------------------
        const W  = definition.frameWidth;
        const L  = definition.frameLength;
        const b  = definition.stockWidth;
        const hh = definition.stockHeight;
        const t  = definition.wall;
        const sp = definition.crossbarSpacing;

        const innerSpan = W - 2 * b;  // X length of all cross-members

        // ----------------------------------------------------------------
        // Helper: one hollow rectangular tube via fCuboid + SUBTRACTION.
        // cx,cy  -- XY centre of the outer box; Z bottom = 0, top = hh.
        // dx,dy  -- outer X and Y extents.
        // longY  -- true => bore runs in Y; false => bore runs in X.
        // ----------------------------------------------------------------
        const buildTube = function(partId is Id, cx is ValueWithUnits, cy is ValueWithUnits,
                           dx is ValueWithUnits, dy is ValueWithUnits,
                           longY is boolean)
        {
            const eps = 2 * millimeter;  // bore overrun for open tube ends
            fCuboid(context, partId + "outer", {
                        "corner1" : vector(cx - dx / 2, cy - dy / 2, 0 * millimeter),
                        "corner2" : vector(cx + dx / 2, cy + dy / 2, hh)
            });
            var ix;
            var iy;
            if (longY)
            {
                ix = dx - 2 * t;
                iy = dy + eps;
            }
            else
            {
                ix = dx + eps;
                iy = dy - 2 * t;
            }
            const iz = hh - 2 * t;
            const cz = hh / 2;
            fCuboid(context, partId + "bore", {
                        "corner1" : vector(cx - ix / 2, cy - iy / 2, cz - iz / 2),
                        "corner2" : vector(cx + ix / 2, cy + iy / 2, cz + iz / 2)
            });
            opBoolean(context, partId + "hollow", {
                        "targets" : qCreatedBy(partId + "outer", EntityType.BODY),
                        "tools"   : qCreatedBy(partId + "bore",  EntityType.BODY),
                        "operationType" : BooleanOperationType.SUBTRACTION
            });
        };

        // ----------------------------------------------------------------
        // Build six rails
        // ----------------------------------------------------------------

        // Side rails -- long axis Y
        buildTube(id + "leftRail",
                  -(W / 2 - b / 2), 0 * millimeter,
                  b, L, true);
        buildTube(id + "rightRail",
                   (W / 2 - b / 2), 0 * millimeter,
                  b, L, true);

        // End rails -- long axis X, butt-jointed between inner side faces
        buildTube(id + "frontRail",
                  0 * millimeter, -(L / 2 - b / 2),
                  innerSpan, b, false);
        buildTube(id + "rearRail",
                  0 * millimeter,  (L / 2 - b / 2),
                  innerSpan, b, false);

        // Interior crossbars -- long axis X, symmetric about Y = 0
        buildTube(id + "crossbarFront",
                  0 * millimeter, -sp / 2,
                  innerSpan, b, false);
        buildTube(id + "crossbarRear",
                  0 * millimeter,  sp / 2,
                  innerSpan, b, false);

        // ----------------------------------------------------------------
        // Name and colour each of the six resulting bodies
        // ----------------------------------------------------------------
        const railColor = color(0.72, 0.74, 0.77);

        const railIds = [
            id + "leftRail"      + "outer",
            id + "rightRail"     + "outer",
            id + "frontRail"     + "outer",
            id + "rearRail"      + "outer",
            id + "crossbarFront" + "outer",
            id + "crossbarRear"  + "outer",
        ];
        const railNames = [
            "left_rail",
            "right_rail",
            "front_rail",
            "rear_rail",
            "crossbar_front",
            "crossbar_rear",
        ];

        for (var i = 0; i < 6; i += 1)
        {
            const body = qCreatedBy(railIds[i], EntityType.BODY);
            setProperty(context, {
                        "entities"     : body,
                        "propertyType" : PropertyType.NAME,
                        "value"        : railNames[i]
            });
            setProperty(context, {
                        "entities"     : body,
                        "propertyType" : PropertyType.APPEARANCE,
                        "value"        : railColor
            });
        }
    });
