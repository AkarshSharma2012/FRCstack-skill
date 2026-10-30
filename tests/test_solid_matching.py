"""Independent matcher regressions, including actual kernel/export checks."""
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/frcstack/scripts'))
import solid_matching as sm
import component_runtime as cr


class Opaque:
    def __init__(self, volume=100):
        self.volume = volume
    def Volume(self):
        return self.volume


class Centered(Opaque):
    def __init__(self, volume=100, x=0, y=0, z=0):
        super().__init__(volume)
        self.center = SimpleNamespace(x=x, y=y, z=z)
    def Center(self):
        return self.center


class LogicTests(unittest.TestCase):
    def test_augmentation_uses_verified_edges_not_greedy(self):
        a, b, x, y = [Opaque() for _ in range(4)]
        allowed = {(id(a), id(x)), (id(a), id(y)), (id(b), id(x))}
        passed, rows = sm.match_solids([a,b], [x,y], lambda u,v,t: (id(u),id(v)) in allowed)
        self.assertTrue(passed)
        self.assertEqual([r['solid_rt_index'] for r in rows], [1,0])
        self.assertFalse(sm.match_solids([a,b], [x,y], lambda u,v,t: v is x)[0])

    def test_long_augmenting_path_is_iterative(self):
        # Last left node forces a 1200-node augmenting path.
        n = 1200
        graph = [[i,i+1] for i in range(n-1)] + [[0]]
        match = sm._maximum_matching(graph,n)
        self.assertEqual(len(match),n)
        self.assertEqual(len(set(match.values())),n)

    def test_invalid_tolerance_even_on_empty_input(self):
        for bad in (True,'0',-1,float('nan'),float('inf'),10**500):
            with self.subTest(bad=str(bad)[:20]), self.assertRaises((TypeError,ValueError)):
                sm.match_solids([],[],lambda a,b,t: True,bad)
        self.assertFalse(sm.match_solids([],[],lambda a,b,t: True)[0])
        self.assertFalse(sm.match_solids([Opaque()],[],lambda a,b,t: True)[0])

    def test_invalid_properties_do_not_fall_back(self):
        for bad in (True,'2',float('nan'),float('inf')):
            self.assertFalse(sm.match_solids([Centered(x=bad)],[Centered()],lambda a,b,t: True)[0])
            self.assertFalse(sm.match_solids([Opaque(bad)],[Opaque()],lambda a,b,t: True)[0])
        class Broken(Centered):
            def Center(self):
                raise RuntimeError('center kernel failed')
        passed, rows = sm.match_solids([Broken()],[Centered()],lambda a,b,t: True)
        self.assertFalse(passed)
        self.assertIn('center kernel failed',rows[0]['error'])

    def test_heuristics_cannot_override_absolute_tolerance(self):
        # A deliberately permissive oracle and remote center exercise exact fallback.
        a, b = Centered(1e-8,0), Centered(2e-8,500)
        calls=[]
        passed,_=sm.match_solids([a],[b],lambda u,v,t: calls.append((u,v,t)) is None)
        self.assertTrue(passed)
        self.assertEqual(len(calls),1)

    def test_errors_remain_visible_on_failed_matching(self):
        def fail(a,b,t):
            raise RuntimeError('Boolean failed')
        passed, rows=sm.match_solids([Opaque()],[Opaque()],fail)
        self.assertFalse(passed)
        self.assertEqual(rows[0]['verifier_error_count'],1)
        self.assertIn('Boolean failed',rows[0]['verifier_errors'][0]['error'])

    @unittest.skipUnless(importlib.util.find_spec('cadquery'),'optional CadQuery unavailable')
    def test_lazy_nearby_equal_boxes_exactly_two_verifier_calls(self):
        # Two boxes 20 mm apart, both within the 50 mm proximity window.
        # With reversed candidate order, a greedy-eager approach would make 4
        # calls; lazy BFS finds a perfect match after exactly 2 calls.
        import cadquery as cq
        a = cq.Workplane().box(2,3,4).val()
        b = a.translate((20,0,0))
        x, y = b.copy(), a.copy()
        calls = []
        def verify(u, v, t):
            calls.append((id(u), id(v)))
            return cr.verify_solid_pair(u,v,t)
        passed, rows = sm.match_solids([a, b], [x, y], verify)
        self.assertTrue(passed)
        # Lazy evaluation must find both correct mates with exactly 2 calls.
        self.assertEqual(len(calls), 2, f'expected 2 verifier calls, got {len(calls)}: {calls}')

    def test_lazy_fallback_reassigns_and_caches_each_edge_once(self):
        # Both shortlists contain only x; fallback must move a from x to y
        # so b can take x. A permissive tiny-body oracle isolates graph logic.
        a, b = Centered(1e-8,0), Centered(2e-8,0)
        x, y = Centered(1e-8,0), Centered(2e-8,500)
        oracle = {(id(a), id(x)), (id(a), id(y)), (id(b), id(x))}
        calls = []
        def verify(u, v, t):
            key = (id(u), id(v))
            calls.append(key)
            return key in oracle
        passed, rows = sm.match_solids([a, b], [x, y], verify)
        self.assertTrue(passed)
        self.assertEqual([r['solid_rt_index'] for r in rows],[1,0])
        # Each distinct (i, j) pair must be evaluated at most once.
        self.assertEqual(len(calls), len(set(calls)),
                         f'duplicate verifier calls detected: {calls}')


@unittest.skipUnless(importlib.util.find_spec('cadquery'),'optional CadQuery unavailable')
class KernelTests(unittest.TestCase):
    def test_step_roundtrip_reversed_and_repeated_occurrences(self):
        import cadquery as cq
        a=cq.Workplane().box(2,3,4).val()
        b=a.translate((20,0,0))
        original=[a,a.copy(),b]
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'shapes.step'
            cq.exporters.export(cq.Compound.makeCompound(original),str(path))
            rt=cq.Compound.makeCompound(cq.importers.importStep(str(path)).vals()).Solids()
            passed,rows=sm.match_solids(original,list(reversed(rt)),cr.verify_solid_pair)
        self.assertTrue(passed)
        self.assertEqual(len({r['solid_rt_index'] for r in rows}),3)

    def test_displaced_equal_volume_is_verified_and_rejected(self):
        import cadquery as cq
        a=cq.Workplane().box(2,3,4).val()
        calls=[]
        def verify(u,v,t):
            calls.append(1)
            return cr.verify_solid_pair(u,v,t)
        self.assertFalse(sm.match_solids([a],[a.translate((1,0,0))],verify)[0])
        self.assertEqual(len(calls),1)

    def test_100_separated_real_boxes_use_100_pair_checks(self):
        import cadquery as cq
        original=[cq.Workplane().box(2,3,4).val().translate((i*500,0,0)) for i in range(100)]
        calls=[]
        def verify(u,v,t):
            calls.append(1)
            return cr.verify_solid_pair(u,v,t)
        self.assertTrue(sm.match_solids(original,list(reversed(original)),verify)[0])
        self.assertEqual(len(calls),100)


if __name__=='__main__':
    unittest.main()
