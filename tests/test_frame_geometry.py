"""Frame geometry checks independent of generator formulas and placement code."""
import importlib.util
import itertools
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/frcstack/scripts'))
import frame_geometry as fg

NOMINAL=dict(width_mm=635,length_mm=812.8,stock_width_mm=25.4,
             stock_height_mm=50.8,wall_mm=1.5875,crossbar_spacing_mm=300)


class InputTests(unittest.TestCase):
    def test_inputs_must_be_explicit_finite_numeric_and_geometrically_possible(self):
        for key in NOMINAL:
            for bad in (True,'25.4',float('nan'),float('inf'),0,-1,10**500):
                with self.subTest(key=key,bad=str(bad)[:10]), self.assertRaises((TypeError,ValueError)):
                    fg.build_frame(dict(NOMINAL,**{key:bad}))
        for change in (dict(width_mm=50.8),dict(wall_mm=12.7),
                       dict(crossbar_spacing_mm=25.4),dict(crossbar_spacing_mm=736.6),
                       dict(length_mm=76.2),dict(extra=1)):
            with self.subTest(change=change),self.assertRaises(ValueError):
                fg.build_frame(dict(NOMINAL,**change))
        with self.assertRaises(ValueError):
            fg.build_frame({})


@unittest.skipUnless(importlib.util.find_spec('cadquery'),'optional CadQuery unavailable')
class KernelTests(unittest.TestCase):
    def test_nominal_cut_list_bounds_open_ends_volume_and_clearance(self):
        import cadquery as cq
        model=fg.build_frame(NOMINAL)
        parts=model['parts']
        self.assertEqual(set(parts),{'left_rail','right_rail','front_rail','rear_rail',
                                     'crossbar_front','crossbar_rear'})
        self.assertTrue(all(s.isValid() and len(s.Solids())==1 for s in parts.values()))
        cuts={c['name']:c['length_mm'] for c in model['cut_list']}
        self.assertEqual(cuts['left_rail'],812.8)
        self.assertAlmostEqual(cuts['crossbar_front'],584.2)
        self.assertAlmostEqual(sum(cuts.values()),3962.4)
        # Independently: 2*t*(b+h)-4*t^2 times the total cut length.
        area=2*1.5875*(25.4+50.8-2*1.5875)
        volume=sum(s.Volume() for s in parts.values())
        self.assertAlmostEqual(volume,area*3962.4,places=4)
        self.assertAlmostEqual(model['expected_volume_mm3'],volume,places=4)
        bb=cq.Compound.makeCompound(list(parts.values())).BoundingBox()
        for actual,expected in ((bb.xmin,-317.5),(bb.xmax,317.5),
                                (bb.ymin,-406.4),(bb.ymax,406.4),
                                (bb.zmin,0),(bb.zmax,50.8)):
            self.assertAlmostEqual(actual,expected,places=5)
        self.assertAlmostEqual(parts['crossbar_front'].Center().y,-150,places=5)
        for a,b in itertools.combinations(parts.values(),2):
            self.assertLessEqual(abs(a.intersect(b).Volume()),1e-6)
        # A small probe along the left rail's entire bore must contain no stock.
        probe=cq.Workplane().box(1,820,1).val().translate((-304.8,0,25.4))
        self.assertLessEqual(abs(parts['left_rail'].intersect(probe).Volume()),1e-6)

    def test_variant_regenerates_six_rails_at_changed_dimensions(self):
        import cadquery as cq
        p=dict(width_mm=700,length_mm=900,stock_width_mm=30,
               stock_height_mm=60,wall_mm=2,crossbar_spacing_mm=400)
        model=fg.build_frame(p)
        parts=model['parts']
        bb=cq.Compound.makeCompound(list(parts.values())).BoundingBox()
        self.assertEqual(len(parts),6)
        self.assertAlmostEqual(bb.xlen,700,places=5)
        self.assertAlmostEqual(bb.ylen,900,places=5)
        self.assertAlmostEqual(bb.zlen,60,places=5)
        self.assertAlmostEqual(parts['crossbar_rear'].Center().y,200,places=5)
        for a,b in itertools.combinations(parts.values(),2):
            self.assertLessEqual(abs(a.intersect(b).Volume()),1e-6)


if __name__=='__main__':
    unittest.main()
