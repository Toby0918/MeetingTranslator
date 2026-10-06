import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


class DiagnosticsTests(unittest.TestCase):
    def test_incomplete_download_fails_self_test_and_writes_actionable_report(self):
        path = Path(__file__).resolve().parents[1] / 'app' / 'diagnostics.py'
        self.assertTrue(path.exists(), 'Download integrity diagnostic is missing')
        spec = importlib.util.spec_from_file_location('diagnostics', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = root / 'check.json'
            self.assertEqual(module.run_self_test(report, root / 'missing-models'), 1)
            result = json.loads(report.read_text(encoding='utf-8'))
            self.assertFalse(result['passed'])
            self.assertIn('whisper-small.en/model.bin', result['missing_models'])


if __name__ == '__main__':
    unittest.main()
