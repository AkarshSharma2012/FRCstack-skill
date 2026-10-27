# Team-specific engineering checks

Apply checks appropriate to the component and process. Record actual evidence, assumptions, and missing checks rather than checking boxes without executing them.

- Geometry: units, reference planes, closed/manifold solids where required, hole sizes/spacing, shaft/bearing fits, stock thickness, edge distances, assembly constraints, and accessible fasteners.
- Motion: full intended sweep, hard stops, collisions, belt/chain paths and tensioning, cable bend/service loops, game-piece path, retention, and clearance under plausible deflection. Static interference and a few sampled poses are not proof of continuous collision-free motion.
- Manufacturing: the team's measured process capability, cutting-tool radius/access, sheet bend allowance/radius, print orientation and anisotropy, support/removal access, inserts, tap engagement, and tolerances appropriate to the actual machine. Do not prescribe one universal printer tolerance.
- Performance: sourced masses/inertia, load cases, duty cycle, reduction, speed/torque tradeoffs, traction, center of mass, fastener loading, and serviceability. State units and uncertainty. FEA requires justified materials, constraints, mesh convergence, and load cases; a colored rendering is not validation.
- Rules: selected-season envelope in required states, weight accounting, allowed components/energy/storage, bumpers or other program-specific requirements, game interaction, and relevant updates/Q&A. Cite rule IDs and distinguish a design review from an official inspection decision.
- Practical release: part numbering, BOM with purchasable items, assembly sequence, replaceability, spare strategy, fabrication drawings, verified version/export provenance, and a bench/prototype test plan for unvalidated behavior.

For a design derived from a video hypothesis, choose the cheapest test that can disprove it before manufacturing a full mechanism. Examples include a retained-fuel shake test, intake throughput fixture, controlled firing interval, and clearance mockup. Hardware operation requires the team's ordinary supervision and procedures. Do not claim the design passed a physical test that has not happened.
