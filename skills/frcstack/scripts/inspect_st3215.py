"""Check whether the vendor ST3215 STEP solids can be repaired, and time a placed copy."""
import sys
import time
from pathlib import Path

import cadquery as cq

ROOT = Path(__file__).resolve().parents[3] / ".frcstack" / "vendor" / "humanoid"


def main():
    t = time.time()
    sols = cq.importers.importStep(str(ROOT / "st3215" / "ST3215.step")).val().Solids()
    print("import", round(time.time() - t, 1), "s")
    for i, s in enumerate(sols):
        if not s.isValid():
            f = s.fix()
            print("solid", i, "fixed valid", f.isValid(), "vol", round(f.Volume(), 1), "orig", round(s.Volume(), 1))
    comp = cq.Compound.makeCompound([s if s.isValid() else s.fix() for s in sols])
    print("compound valid", comp.isValid(), "faces", len(comp.Faces()))
    t = time.time()
    v, tr = comp.tessellate(0.5, 0.5)
    print("tessellate", len(tr), "tris", round(time.time() - t, 1), "s")


if __name__ == "__main__":
    sys.exit(main())
