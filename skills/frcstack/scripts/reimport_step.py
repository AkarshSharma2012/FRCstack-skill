"""Re-import a delivered humanoid STEP and report solid count / validity per top-level part."""
import sys

import cadquery as cq


def main(path):
    a = cq.importers.importStep(path)
    sols = a.val().Solids() if hasattr(a.val(), "Solids") else []
    bad = [i for i, s in enumerate(sols) if not s.isValid()]
    bb = a.val().BoundingBox()
    print("solids", len(sols), "invalid", len(bad), "bbox", round(bb.xlen), round(bb.ylen), round(bb.zlen))
    for i in bad:
        b = sols[i].BoundingBox()
        print(" invalid", i, "vol", round(sols[i].Volume(), 1), "size", round(b.xlen, 1), round(b.ylen, 1), round(b.zlen, 1))


if __name__ == "__main__":
    main(sys.argv[1])
