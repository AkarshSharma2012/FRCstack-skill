"""Review regressions for false clearance and aliased output paths."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/frcstack/scripts'))
import component_runtime as cr


class KernelFailureTests(unittest.TestCase):
    def test_negative_overlap_is_not_clearance(self):
        bad = Mock()
        bad.intersect.return_value.Volume.return_value = -1.0
        with self.assertRaises(ValueError):
            cr._interferences([('a', bad), ('b', bad)])

    def test_nan_source_volume_cannot_pass_import(self):
        bad_solid = Mock()
        bad_solid.isValid.return_value = True
        bad_solid.Volume.return_value = float('nan')
        kernel = Mock()
        kernel.Compound.makeCompound.return_value.Solids.return_value = [bad_solid]
        with patch.object(cr, '_kernel', return_value=kernel):
            with self.assertRaises(ValueError):
                cr._import_solids(Path('fault-injected.step'))


@unittest.skipUnless(importlib.util.find_spec('cadquery'), 'optional CadQuery not installed')
class LinkedOutputTests(unittest.TestCase):
    def test_symlink_above_immediate_output_parent_is_refused(self):
        import cadquery as cq
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'box.step'
            cq.exporters.export(cq.Workplane().box(10, 20, 30), str(source))
            real = root / 'real'
            (real / 'nested').mkdir(parents=True)
            alias = root / 'alias'
            try:
                alias.symlink_to(real, target_is_directory=True)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f'OS refused directory symlink: {error}')
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'schema': 1, 'components': [{
                'instance_name': 'part', 'file': 'box.step',
                'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'manufacturer': 'Original test', 'part_number': 'box', 'source_revision': '1',
                'source_url': 'https://example.com/test.step',
                'translation_mm': [0, 0, 0], 'rotation': {'axis': [0, 0, 1], 'degrees': 0}
            }]}))
            with self.assertRaises(ValueError):
                cr.assemble(manifest, alias / 'nested' / 'new')
            self.assertFalse((real / 'nested' / 'new').exists())


if __name__ == '__main__':
    unittest.main()
