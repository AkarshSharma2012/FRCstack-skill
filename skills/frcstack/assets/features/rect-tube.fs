FeatureScript 3095;
import(path : "onshape/std/common.fs", version : "3095.0");

// Original parametric stock geometry. No mounting, material or strength claim.
annotation { "Feature Type Name" : "FRCstack rectangular tube" }
export const frcstackRectTube = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Width" }
        isLength(definition.width, { (millimeter) : [1, 50.8, 1000] } as LengthBoundSpec);
        annotation { "Name" : "Height" }
        isLength(definition.height, { (millimeter) : [1, 25.4, 1000] } as LengthBoundSpec);
        annotation { "Name" : "Wall" }
        isLength(definition.wall, { (millimeter) : [0.01, 1.5875, 100] } as LengthBoundSpec);
        annotation { "Name" : "Length" }
        isLength(definition.length, { (millimeter) : [1, 250, 10000] } as LengthBoundSpec);
    }
    {
        if (2 * definition.wall >= definition.width || 2 * definition.wall >= definition.height)
            throw regenError("Twice the wall must be smaller than width and height", ["wall", "width", "height"]);
        const w = definition.width;
        const h = definition.height;
        fCuboid(context, id + "outer", {
                    "corner1" : vector(-w / 2, -h / 2, 0 * millimeter),
                    "corner2" : vector(w / 2, h / 2, definition.length)
        });
        fCuboid(context, id + "inner", {
                    "corner1" : vector(-w / 2 + definition.wall, -h / 2 + definition.wall, -1 * millimeter),
                    "corner2" : vector(w / 2 - definition.wall, h / 2 - definition.wall, definition.length + 1 * millimeter)
        });
        opBoolean(context, id + "hollow", {
                    "targets" : qCreatedBy(id + "outer", EntityType.BODY),
                    "tools" : qCreatedBy(id + "inner", EntityType.BODY),
                    "operationType" : BooleanOperationType.SUBTRACTION
        });
        const body = qCreatedBy(id + "outer", EntityType.BODY);
        setProperty(context, { "entities" : body, "propertyType" : PropertyType.NAME, "value" : "CUSTOM_rectangular_tube" });
        setProperty(context, { "entities" : body, "propertyType" : PropertyType.APPEARANCE, "value" : color(0.72, 0.74, 0.77) });
    });
