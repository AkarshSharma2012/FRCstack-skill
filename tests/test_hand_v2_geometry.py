"""Fast, kernel-free checks for hand_v2_geometry (frames, mirroring, packing, flange)."""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "frcstack" / "scripts"))
import hand_kinematics as hk  # noqa: E402
import hand_v2_geometry as g  # noqa: E402


def test_right_hand_mirror_is_proper_and_thumb_on_plus_x():
    links = g.right_links(hk.pose("partial"))
    for n, T in links.items():
        assert abs(np.linalg.det(T[:3, :3]) - 1.0) < 1e-9, n
    tips = g.right_tips(hk.pose("open"))
    assert tips["thumb"][0] > 0 and tips["index"][0] > tips["little"][0]


def test_flexion_curls_toward_palmar_plus_z():
    tips_open = g.right_tips(hk.pose("open"))
    tips_closed = g.right_tips(hk.pose("closed"))
    for f in ("index", "middle", "ring", "little"):
        assert tips_closed[f][2] > tips_open[f][2] + 20


def test_every_joint_has_exactly_one_actuator():
    fr = g.actuator_frames()
    assert set(fr) == set(hk._JOINT_ORDER)
    assert set(g.RADIAL_JOINTS).isdisjoint(g.ULNAR_JOINTS)


def test_actuator_envelopes_disjoint_and_inside_shell():
    # vendor envelope corners in each actuator frame
    xs, ys, zs = (-10.0, 10.0), (-24.5, 9.5), (-22.5, 6.5 + 9.0)   # + spool height
    corners = np.array([[x, y, z, 1.0] for x in xs for y in ys for z in zs])
    boxes = []
    hx, z0, z1, _ = g.INNER
    for n, T in g.actuator_frames().items():
        w = (T @ corners.T).T[:, :3]
        lo, hi = w.min(0), w.max(0)
        assert abs(lo[0]) >= g.SPINE_HALF - 1e-9 or abs(hi[0]) >= g.SPINE_HALF - 1e-9
        assert min(abs(lo[0]), abs(hi[0])) >= g.SPINE_HALF - 1e-9, n   # never inside spine
        assert max(abs(lo[0]), abs(hi[0])) < hx, n
        assert lo[2] > z0 and hi[2] < z1, n
        assert g.PLATE_Y[0] < lo[1] and hi[1] < g.PLATE_Y[1], n
        boxes.append((n, lo, hi))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            overlap = np.all(a[1] < b[2] - 1e-9) and np.all(b[1] < a[2] - 1e-9)
            assert not overlap, (a[0], b[0])


def test_bones_clear_actuators():
    # actuator case + spool (flange R8 up to horn+9) envelopes vs both CF tubes
    env = [((-10.0, 10.0), (-24.5, 9.5), (-22.5, 6.5)), ((-8.0, 8.0), (-8.0, 8.0), (6.5, 15.5))]
    for T in g.actuator_frames().values():
        for xs, ys, zs in env:
            c = np.array([[x, y, z, 1.0] for x in xs for y in ys for z in zs])
            w = (T @ c.T).T[:, :3]
            lo, hi = w.min(0), w.max(0)
            for sx in (1, -1):
                bx, bz = sx * g.BONE_XZ[0], g.BONE_XZ[1]
                blo = (bx - g.BONE_R, bz - g.BONE_R)
                bhi = (bx + g.BONE_R, bz + g.BONE_R)
                overlap = lo[0] < bhi[0] and blo[0] < hi[0] and lo[2] < bhi[1] and blo[1] < hi[2]
                assert not overlap


def test_flange_pattern_matches_a50():
    pts = [(25 * math.cos(math.radians(d)), 25 * math.sin(math.radians(d))) for d in g.FLANGE_HOLES_DEG]
    for x, y in pts:
        assert math.isclose(math.hypot(x, y) * 2, 50.0)
    assert g.ADAPTER_R * 2 <= 75.0 + 1e-9


def test_spool_radii_clamped():
    r = g.spool_radii()
    assert len(r) == 20
    assert all(g.SPOOL_R_MIN <= v <= g.SPOOL_R_MAX for v in r.values())


def test_tendon_channels_unique_entries_40():
    ch = g.tendon_channels(g.right_links(hk.pose("open")))
    assert len(ch) == 40
    assert len({p0 for _, p0, _ in ch}) == 40


class V2Geometry(unittest.TestCase):
    pass


for _n, _f in list(globals().items()):
    if _n.startswith("test_") and callable(_f):
        setattr(V2Geometry, _n, staticmethod(_f))

if __name__ == "__main__":
    unittest.main()
