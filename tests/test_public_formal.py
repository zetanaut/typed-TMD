"""Publication boundaries: shipped bytes and mandatory proof failures."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from replay_finite_plans import load_fixtures
from check_formal import theorem_inventory


class PublicFormalTests(unittest.TestCase):
    def test_inventory_resolves_dotted_example_namespace(self):
        inventory = theorem_inventory(ROOT/'formal/007')
        names = {row['name'] for row in inventory}
        self.assertIn('TypedTMDPlan.Examples.good_preserves', names)
        self.assertIn('TypedTMDPlan.Category.Arrow.checked_composition', names)
        self.assertNotIn('TypedTMDPlan.good_preserves', names)

    def test_tutorial_executes_rejection_and_reference_transport(self):
        path = ROOT/'examples/formal/cache_and_composition.py'
        spec = importlib.util.spec_from_file_location('formal_tutorial', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.run()
        self.assertEqual(result['primitive_calls_before_refusal'], 0)
        self.assertNotEqual(result['correct_off_reference_value'], result['frozen_off_reference_value'])
        self.assertIn('fixed_parameter_changed', result['wrong_reference_refusal'])

    def test_corrupt_public_fixture_rejected_before_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            manifest = json.loads((ROOT/'evidence/formal/fixtures/MANIFEST.json').read_text())
            entry = manifest['files'][0]
            (target/'MANIFEST.json').write_text(json.dumps({'files': [entry]}))
            (target/entry['path']).write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'fixture byte identity mismatch'):
                load_fixtures(target)

    def test_missing_lean_never_reports_formal_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'proof'
            proc = subprocess.run([sys.executable, str(ROOT/'scripts/check_formal.py'),
                '--output-dir', str(output), '--lake', 'typed-tmd-no-such-lake'],
                text=True, capture_output=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(json.loads((output/'PORTABLE.json').read_text())['status'], 'failed_or_blocked')
            self.assertEqual(json.loads((output/'selected/SUMMARY.json').read_text())['status'], 'blocked')


if __name__ == '__main__':
    unittest.main()
