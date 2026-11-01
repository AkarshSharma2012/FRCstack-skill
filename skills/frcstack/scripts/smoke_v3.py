"""smoke_v3.py -- build each v3 section separately and report validity / timing."""
import sys
import time
import traceback

import hand_kinematics as hk
import hand_v3_geometry as g


def run(name, fn):
    t = time.time()
    try:
        out = fn()
        if not isinstance(out, dict):
            out = {name: out} if not isinstance(out, tuple) else {f"{name}_{i}": v for i, v in enumerate(out)}
        bad = [k for k, v in out.items() if not v.isValid()]
        print(f"{name}: {len(out)} parts, invalid={bad}, {time.time() - t:.1f}s", flush=True)
        return out
    except Exception:
        print(f"{name}: FAILED {time.time() - t:.1f}s", flush=True)
        traceback.print_exc()
        return {}


if __name__ == "__main__":
    which = sys.argv[1:] or ["shell", "cage", "act", "fingers", "tendons", "wrist", "pcb"]
    q = hk.pose("open")
    fns = {"shell": g._palm_shell, "cage": g._cage, "act": g.build_actuators,
           "fingers": lambda: g.build_fingers(q), "tendons": g.build_tendons,
           "wrist": g._wrist_mount, "pcb": g.build_electronics_placeholder,
           "bosses": g._knuckle_bosses}
    for w in which:
        run(w, fns[w])
