import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core import Models


class RuntimeTests(unittest.TestCase):
    def test_model_loading_avoids_native_sentencepiece_unicode_path(self):
        with tempfile.TemporaryDirectory(prefix='翻译 portable ') as folder:
            root = Path(folder)
            model = root / 'translation' / 'translate-en_zh-1_9' / 'sentencepiece.model'
            model.parent.mkdir(parents=True)
            model.write_bytes(b'example serialized sentencepiece model')
            def sentencepiece_boundary(**kwargs):
                if 'model_file' in kwargs:
                    raise RuntimeError('Native Windows narrow-character path cannot open this file')
                self.assertEqual(kwargs['model_proto'], model.read_bytes())
                return object()
            modules = {
                'faster_whisper': SimpleNamespace(WhisperModel=lambda *a, **k: object()),
                'ctranslate2': SimpleNamespace(Translator=lambda *a, **k: object()),
                'sentencepiece': SimpleNamespace(SentencePieceProcessor=sentencepiece_boundary),
            }
            with patch.dict('sys.modules', modules):
                models = Models(root)
                models.load()
                self.assertIsNotNone(models.sp)

    def runtime(self):
        path = Path(__file__).resolve().parents[1] / 'app' / 'runtime.py'
        self.assertTrue(path.is_file(), 'Portable model discovery is missing')
        spec = importlib.util.spec_from_file_location('runtime', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_frozen_application_uses_models_beside_executable(self):
        runtime = self.runtime()
        with tempfile.TemporaryDirectory(prefix='翻译 portable ') as folder:
            root = Path(folder)
            self.assertEqual(runtime.resolve_model_root(executable=root / 'MeetingTranslator.exe', frozen=True),
                             root / 'models')

    def test_source_runtime_reads_local_developer_configuration(self):
        import json
        runtime = self.runtime()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'runtime-config.json').write_text(json.dumps({'model_root': str(root / 'shared-models')}))
            self.assertEqual(runtime.resolve_model_root(project_root=root, frozen=False), root / 'shared-models')

    def test_frozen_runtime_ignores_original_computer_configuration(self):
        runtime = self.runtime()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'runtime-config.json').write_text('{"model_root":"C:/someone/models"}')
            self.assertEqual(runtime.resolve_model_root(executable=root / 'MeetingTranslator.exe',
                                                       project_root=root, frozen=True), root / 'models')

    def test_incomplete_models_report_missing_files_before_loading(self):
        runtime = self.runtime()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            missing = runtime.missing_model_files(root)
            self.assertIn('whisper-small.en/model.bin', missing)
            self.assertIn('translation/translate-en_zh-1_9/model/model.bin', missing)


if __name__ == '__main__':
    unittest.main()
