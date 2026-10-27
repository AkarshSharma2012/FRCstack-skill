# Onshape authoring workflow

## Establish the real capability

Prefer an existing supported connector/API for document and feature operations. Otherwise use an available authorized browser controller. Do not assume a tool named Onshape exists. Check access by reading the intended document metadata or visible model before editing. Do not ask the user to paste API secrets into chat. An API integration must use the account's configured scopes/secure credential mechanism.

Record document ID, workspace ID, element ID/type, configuration, and a baseline version/microversion. Onshape versions and microversions are immutable; changes target a workspace. Read the current API Explorer/docs for the actual host and endpoint version rather than memorizing endpoints. Enterprise domains can differ from cad.onshape.com.

Do bounded work in a dedicated branch/workspace or copy where appropriate and supported. Preserve the baseline and unrelated geometry. Do not change document sharing or publish team designs without user authorization. Verify the target again after navigation, a retry, or a team switch. Do not retry uncertain create/modify calls blindly; check whether the intended feature/element already exists.

## Team intake

Capture program, season, team, project purpose, CAD ownership/access, preferred units, datum/origin, coordinate convention, naming/part-number scheme, fastener/hardware ecosystem, stock materials, manufacturing tools and limits, measured mating geometry, budget/mass targets, transport envelope, electrical/service access, expected loads, and iteration deadline. Unknown entries remain unknown. Ask only questions that block a meaningful design decision.

Source bolt circles, shafts, hubs, bearings, gears, pulleys, extrusions, motors, servos, slides, and vendor CAD from current manufacturer drawings or the team's verified library. Similar-looking FTC and FRC components are not interchangeable. Never invent a hole pitch or shaft fit from a catalog photo.

## Use real robotics component libraries

For FRC, the default discovery source is [FRCDesignLib](https://www.frcdesign.org/resources/frcdesignlib/), a community-maintained COTS component/assembly collection. FRCDesignApp is its Onshape inserter, not the library itself. Check the current maintainer documentation and actual account availability; do not assume the app is installed. Follow the maintainer's current App Store link if setup is requested. Authentication, account subscriptions, permissions, and terms remain explicit user-controlled gates.

[Onshape's FIRST resources](https://www.onshape.com/en/education/first-robotics) also link FRC and separate FTC parts libraries. Use the selected program's actual library, team-approved hardware ecosystem, and manufacturer's current CAD/drawings. Do not treat every library entry as official FIRST content or imply the library itself certifies season legality.

For each purchased component:

1. Resolve manufacturer, catalog part number, variant/configuration, quantity, and source URL/document. Match shaft profile, bore, length, ratio, fastener pitch, and handedness where relevant. Similar appearance is not a match.
2. Record source document/element IDs, immutable version or microversion, configuration values, checked date, and drawing revision when available. Record missing metadata as unknown. Pin release references; do not silently update component versions mid-design.
3. Cross-check design-critical interfaces and units against manufacturer evidence. Check whether the library representation is simplified and omits service envelopes, moving geometry, mounting details, or internal components. Record material/mass provenance; do not assume a CAD mass is measured hardware mass.
4. Insert assemblies/components or derive geometry as appropriate to the actual task and available tools. Preserve configurations and provenance. Imported/library solids do not necessarily expose an editable native feature tree; custom parts should retain their own readable parameters.
5. Mate using verified axes and mounting datums, then check motion, cable paths, tool access, and clearances. Library presence is not proof of fit, strength, or rule compliance.

If the exact part is missing, use manufacturer CAD or a dimensioned model from verified drawings and label its source. Do not silently replace it with a nearby part or fabricated dimensions. Video reconstruction can use an explicitly uncertain proxy until identity/dimensions are confirmed; that proxy must not enter the fabrication BOM as a verified catalog part.

## Model

Prefer a readable native parametric feature tree: named variables, constrained sketches, explicit datums, functional interfaces, simple solid features, repeated geometry via patterns, and cosmetic edge treatment last. Keep critical interfaces tied to measured/vendor dimensions with explicit units. Parameterize variants without adding unnecessary configurable complexity.

Use FeatureScript for reusable parameterized features when it reduces fragile manual work. Read the current FeatureScript language/library docs and match the source document's language and import versions. Resolve queries robustly instead of assuming transient face/edge order. Test nominal and boundary parameter cases in Onshape. A JavaScript/Python syntax check does not compile FeatureScript.

FeatureScript custom features operate in a Part Studio; they are not a general browser, document, or assembly automation API. Assemble components using actual assembly operations/mates, proper references, and explicit motion limits. Retain configurations and vendor provenance.

## Validate and deliver

Observe Onshape regeneration status, compare parameters with measured geometry, inspect solids/counts/bounding boxes, set physical materials before estimating mass, and test motion/clearance in relevant configurations. Use the engineering checklist. A screenshot or smooth animation is not proof of tolerances, strength, collision-free motion, or legal compliance.

Deliver a versioned document URL with editable source/FeatureScript as applicable. Provide dimensioned drawings and requested STEP/DXF/STL/BOM exports from that verified version. Specify units, tolerances, material, stock thickness, finish, fasteners, and assembly notes. Check export units/orientation/body selection by reimporting/inspecting when supported. Mark unavailable exports and unexecuted code plainly.

If no Onshape write/runtime access exists, produce a source/parameter package and exact import steps labeled uncompiled/unverified. Do not rename a mesh or text file to STEP and call it CAD. Request the actual document/access only when it is necessary to build or test.
