"""End-to-end chassis export and failure-evidence checks."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/frcstack/scripts'))
import frame_runtime as fr
from test_frame_geometry import NOMINAL


@unittest.skipUnless(importlib.util.find_spec('cadquery'),'optional CadQuery unavailable')
class FrameExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.parameters=self.root/'parameters.json'
        self.parameters.write_text(json.dumps(NOMINAL),encoding='utf-8')

    def test_cli_export_has_verified_geometry_and_preserves_existing_output(self):
        out=self.root/'frame'
        with contextlib.redirect_stdout(io.StringIO()):
            code=fr.main(['build-frame','--parameters',str(self.parameters),'--output',str(out)])
        self.assertEqual(code,0)
        report=json.loads((out/'validation.json').read_text())
        self.assertTrue(report['roundtrip_passed'] and report['clearance_passed'] and report['analytic_passed'])
        self.assertEqual(len(report['roundtrip_results']),6)
        self.assertEqual(report['parameters_sha256'],hashlib.sha256(self.parameters.read_bytes()).hexdigest())
        self.assertEqual(report['step_sha256'],hashlib.sha256((out/'frame.step').read_bytes()).hexdigest())
        for key in ('onshape_verified','fea_executed','fabrication_ready','exact_team_replica','name_roundtrip_verified','color_appearance_verified'):
            self.assertIs(report[key],False)
        before=(out/'frame.step').read_bytes()
        with self.assertRaises(FileExistsError):
            fr.build_frame_export(self.parameters,out)
        self.assertEqual((out/'frame.step').read_bytes(),before)

    def test_invalid_parameters_and_linked_output_create_no_artifacts(self):
        self.parameters.write_text(json.dumps(dict(NOMINAL,wall_mm=100)))
        out=self.root/'invalid'
        with self.assertRaises(ValueError):
            fr.build_frame_export(self.parameters,out)
        self.assertFalse(out.exists())
        self.parameters.write_text(json.dumps(NOMINAL))
        real=self.root/'real'; real.mkdir()
        linked=self.root/'alias'
        try:
            linked.symlink_to(real,target_is_directory=True)
        except (OSError,NotImplementedError) as error:
            self.skipTest(str(error))
        with self.assertRaises(ValueError):
            fr.build_frame_export(self.parameters,linked/'child')
        self.assertFalse((real/'child').exists())

    def test_failed_roundtrip_keeps_evidence_and_returns_nonzero(self):
        out=self.root/'failed'
        with patch.object(fr,'_bijective_roundtrip',return_value=(False,[{'error':'injected displacement'}])):
            with contextlib.redirect_stderr(io.StringIO()):
                code=fr.main(['build-frame','--parameters',str(self.parameters),'--output',str(out)])
        self.assertEqual(code,2)
        report=json.loads((out/'validation.json').read_text())
        self.assertFalse(report['roundtrip_passed'])
        self.assertTrue(report['export_success'])
        self.assertIn('injected displacement',report['roundtrip_results'][0]['error'])


if __name__=='__main__':
    unittest.main()
