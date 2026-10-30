FeatureScript 3095;
import(path : "onshape/std/common.fs", version : "3095.0");

// Original execution fixture, not vendor CAD or a fabrication-ready mechanism.
// Four separate bodies; no material, bearings, retention, drive or mates supplied.
annotation { "Feature Type Name" : "FRCstack test roller fixture" }
export const frcstackRollerFixture = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Inner span" }
        isLength(definition.span, { (millimeter) : [50, 400, 2000] } as LengthBoundSpec);
        annotation { "Name" : "Plate width" }
        isLength(definition.width, { (millimeter) : [10, 80, 300] } as LengthBoundSpec);
        annotation { "Name" : "Plate height" }
        isLength(definition.height, { (millimeter) : [10, 120, 400] } as LengthBoundSpec);
        annotation { "Name" : "Plate thickness" }
        isLength(definition.thickness, { (millimeter) : [0.5, 6, 25] } as LengthBoundSpec);
        annotation { "Name" : "Plate hole diameter" }
        isLength(definition.hole, { (millimeter) : [1, 13, 50] } as LengthBoundSpec);
        annotation { "Name" : "Shaft diameter" }
        isLength(definition.shaft, { (millimeter) : [1, 12, 50] } as LengthBoundSpec);
        annotation { "Name" : "Roller length" }
        isLength(definition.length, { (millimeter) : [10, 360, 1900] } as LengthBoundSpec);
        annotation { "Name" : "Roller diameter" }
        isLength(definition.diameter, { (millimeter) : [5, 50, 200] } as LengthBoundSpec);
        annotation { "Name" : "Roller bore diameter" }
        isLength(definition.bore, { (millimeter) : [1, 14, 50] } as LengthBoundSpec);
    }
    {
        if (definition.length >= definition.span)
            throw regenError("Roller length must be less than the inner span", ["length", "span"]);
        if (definition.shaft >= definition.bore || definition.bore >= definition.diameter)
            throw regenError("Require shaft diameter < bore diameter < roller diameter", ["shaft", "bore", "diameter"]);
        if (definition.shaft >= definition.hole || definition.hole >= definition.width || definition.hole >= definition.height)
            throw regenError("Plate hole must clear the shaft and fit inside the plate", ["shaft", "hole", "width", "height"]);
        if (definition.diameter >= definition.height)
            throw regenError("Roller diameter must be smaller than plate height", ["diameter", "height"]);

        const span = definition.span / millimeter;
        const width = definition.width / millimeter;
        const height = definition.height / millimeter;
        const thickness = definition.thickness / millimeter;
        const hole = definition.hole / millimeter;
        const length = definition.length / millimeter;

        makePlate(context, id + "left", -span / 2 - thickness, thickness, width, height, hole, "TEST_left_plate");
        makePlate(context, id + "right", span / 2, thickness, width, height, hole, "TEST_right_plate");

        makeCylinder(context, id + "shaft", -span / 2 - thickness, span / 2 + thickness, definition.shaft / 2);
        setProperty(context, { "entities" : qCreatedBy(id + "shaft", EntityType.BODY), "propertyType" : PropertyType.NAME, "value" : "TEST_shaft" });

        makeCylinder(context, id + "roller", -length / 2, length / 2, definition.diameter / 2);
        makeCylinder(context, id + "rollerBore", -length / 2 - 1, length / 2 + 1, definition.bore / 2);
        opBoolean(context, id + "boreCut", {
                    "targets" : qCreatedBy(id + "roller", EntityType.BODY),
                    "tools" : qCreatedBy(id + "rollerBore", EntityType.BODY),
                    "operationType" : BooleanOperationType.SUBTRACTION
        });
        setProperty(context, { "entities" : qCreatedBy(id + "roller", EntityType.BODY), "propertyType" : PropertyType.NAME, "value" : "TEST_roller" });

        if (size(evaluateQuery(context, qCreatedBy(id, EntityType.BODY))) != 4)
            throw regenError("Expected exactly four separate test solids");
        applyRolePalette(context, id);
    });

// ---------------------------------------------------------------------------
// Illustrative role-palette appearances.
// NOT verified physical materials, winning-team colours, or fabrication specs.
// A manual Part Studio appearance override can shadow these FeatureScript defaults.
// Do NOT assign MATERIAL based on colour; no material/density/mass claim is made.
// Reference: https://cad.onshape.com/FsDoc/library.html#properties
// ---------------------------------------------------------------------------
function applyRolePalette(context is Context, id is Id)
{
    // Plates: aluminium-like light grey RGB(0.72, 0.74, 0.77)
    setProperty(context, {
                "entities"     : qUnion([qCreatedBy(id + "left",  EntityType.BODY),
                                         qCreatedBy(id + "right", EntityType.BODY)]),
                "propertyType" : PropertyType.APPEARANCE,
                "value"        : color(0.72, 0.74, 0.77)
    });
    // Shaft: steel-like mid-grey RGB(0.42, 0.45, 0.49)
    setProperty(context, {
                "entities"     : qCreatedBy(id + "shaft", EntityType.BODY),
                "propertyType" : PropertyType.APPEARANCE,
                "value"        : color(0.42, 0.45, 0.49)
    });
    // Roller: rubber-like dark RGB(0.08, 0.09, 0.11)
    setProperty(context, {
                "entities"     : qCreatedBy(id + "roller", EntityType.BODY),
                "propertyType" : PropertyType.APPEARANCE,
                "value"        : color(0.08, 0.09, 0.11)
    });
}

function makeCylinder(context is Context, id is Id, x1 is number, x2 is number, radius is ValueWithUnits)
{
    fCylinder(context, id, {
                "bottomCenter" : vector(x1, 0, 0) * millimeter,
                "topCenter" : vector(x2, 0, 0) * millimeter,
                "radius" : radius
    });
}

function makePlate(context is Context, id is Id, x is number, thickness is number, width is number, height is number, hole is number, name is string)
{
    fCuboid(context, id + "block", {
                "corner1" : vector(x, -width / 2, -height / 2) * millimeter,
                "corner2" : vector(x + thickness, width / 2, height / 2) * millimeter
    });
    makeCylinder(context, id + "tool", x - 1, x + thickness + 1, hole / 2 * millimeter);
    opBoolean(context, id + "cut", {
                "targets" : qCreatedBy(id + "block", EntityType.BODY),
                "tools" : qCreatedBy(id + "tool", EntityType.BODY),
                "operationType" : BooleanOperationType.SUBTRACTION
    });
    setProperty(context, { "entities" : qCreatedBy(id + "block", EntityType.BODY), "propertyType" : PropertyType.NAME, "value" : name });
}
