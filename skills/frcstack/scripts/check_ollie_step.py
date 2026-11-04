"""Check a delivered OLLIE STEP: re-import, solid validity, and that every joint's parent/child component
name from ollie-joints.json exists in the STEP product tree (what the Fusion script will look up)."""
import json
import re
import sys
from pathlib import Path

import cadquery as cq


def main(step, joints):
    txt = Path(step).read_text(errors="ignore")
    names = set(re.findall(r"PRODUCT\('([^']*)'", txt))
    spec = json.loads(Path(joints).read_text())
    need = {spec["ground"]} | {j["parent"] for j in spec["joints"]} | {j["child"] for j in spec["joints"]}
    missing = sorted(n for n in need if n not in names)
    shp = cq.importers.importStep(step).val()
    sols = shp.Solids()
    bad = sum(not s.isValid() for s in sols)
    bb = shp.BoundingBox()
    print(f"products {len(names)} joint-components needed {len(need)} missing {missing}")
    print(f"solids {len(sols)} invalid {bad} bbox {bb.xlen:.0f} x {bb.ylen:.0f} x {bb.zlen:.0f}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
