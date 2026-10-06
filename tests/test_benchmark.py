import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


class BenchmarkTests(unittest.TestCase):
    def test_pre_v1_baseline_rejects_a_different_model_family(self):
        module = self.module()
        with self.assertRaisesRegex(ValueError, 'Argos'):
            module.baseline_translation(SimpleNamespace(source_prefix=['>>cmn_Hans<<']), 'Do not approve.')

    def module(self):
        path = Path(__file__).resolve().parents[1] / 'scripts' / 'evaluate_ted.py'
        self.assertTrue(path.exists(), 'Reproducible TED evaluation script is missing')
        spec = importlib.util.spec_from_file_location('evaluate_ted', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_reference_stage_directions_are_excluded_without_dropping_speech(self):
        module = self.module()
        self.assertEqual(module.normalize_for_wer("(Laughter) We can’t wait 30 days. [Applause]"),
                         "we can't wait 30 days")

    def test_vtt_timing_and_markup_are_parsed_for_reference_only(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'en.vtt'
            path.write_text('WEBVTT\n\n1\n00:01:02.500 --> 00:01:04.000\n<c>Do not approve</c>\nthe order.\n', encoding='utf-8')
            self.assertEqual(module.parse_vtt(path),
                             [{'start': 62.5, 'end': 64.0, 'text': 'Do not approve the order.'}])


if __name__ == '__main__':
    unittest.main()
