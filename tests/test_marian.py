import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core import Models
from runtime import missing_model_files


class SourceTokens:
    def encode(self, text, out_type=str):
        return ['SOURCE:' + text]

    def decode(self, tokens):
        raise AssertionError('Chinese must not be decoded with the English tokenizer')


class TargetTokens:
    def decode(self, tokens):
        return ''.join(tokens)


class MarianTests(unittest.TestCase):
    def test_target_vocabulary_and_language_markers_preserve_all_sentences(self):
        model = Models(Path('unused'))
        model.sp, model.target_sp = SourceTokens(), TargetTokens()
        model.source_prefix, model.source_suffix = ['>>cmn_Hans<<'], ['</s>']
        expected = [['>>cmn_Hans<<', 'SOURCE:This is not the conclusion.', '</s>'],
                    ['>>cmn_Hans<<', 'SOURCE:The trial may fail.', '</s>']]
        def translate(batches, **kwargs):
            self.assertEqual(batches, expected)
            return [SimpleNamespace(hypotheses=[['这不是结论。']]),
                    SimpleNamespace(hypotheses=[['试验可能失败。']])]
        model.mt = SimpleNamespace(translate_batch=translate)
        self.assertEqual(model.translate('This is not the conclusion. The trial may fail.'),
                         '这不是结论。 试验可能失败。')

    def test_invalid_retry_keeps_language_markers_and_target_decoder(self):
        model = Models(Path('unused'))
        model.sp, model.target_sp = SourceTokens(), TargetTokens()
        model.source_prefix, model.source_suffix = ['>>cmn_Hans<<'], ['</s>']
        calls = []
        def translate(batches, **kwargs):
            self.assertEqual(batches, [['>>cmn_Hans<<', 'SOURCE:Do not approve.', '</s>']])
            calls.append(kwargs['beam_size'])
            return [SimpleNamespace(hypotheses=[['\ue000' if kwargs['beam_size'] == 2 else '不要批准。']])]
        model.mt = SimpleNamespace(translate_batch=translate)
        self.assertEqual(model.translate('Do not approve.'), '不要批准。')
        self.assertEqual(calls, [2, 4])

    def test_unicode_directory_loads_two_distinct_tokenizers_from_bytes(self):
        with tempfile.TemporaryDirectory(prefix='翻译 portable ') as folder:
            root = Path(folder)
            translation = root / 'translation' / 'meeting-en_zh-v1_1'
            translation.mkdir(parents=True)
            (translation / 'source.spm').write_bytes(b'source')
            (translation / 'target.spm').write_bytes(b'target')
            serialized = []
            def sp(**kwargs):
                self.assertNotIn('model_file', kwargs)
                serialized.append(kwargs['model_proto'])
                return object()
            def mt(path, **kwargs):
                self.assertEqual(Path(path), translation)
                self.assertEqual(kwargs['device'], 'cpu')
                return object()
            modules = {'faster_whisper': SimpleNamespace(WhisperModel=lambda *a, **k: object()),
                       'ctranslate2': SimpleNamespace(Translator=mt),
                       'sentencepiece': SimpleNamespace(SentencePieceProcessor=sp)}
            with patch.dict('sys.modules', modules):
                model = Models(root)
                model.load()
            self.assertEqual(serialized, [b'source', b'target'])
            self.assertIsNot(model.sp, model.target_sp)
            self.assertEqual(model.source_prefix, ['>>cmn_Hans<<'])
            self.assertEqual(model.source_suffix, ['</s>'])

    def test_new_model_reports_missing_target_vocabulary_before_load(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            translation = root / 'translation' / 'meeting-en_zh-v1_1'
            translation.mkdir(parents=True)
            (translation / 'source.spm').write_bytes(b'source')
            missing = missing_model_files(root)
            self.assertIn('translation/meeting-en_zh-v1_1/target.spm', missing)
            self.assertNotIn('translation/meeting-en_zh-v1_1/source.spm', missing)


if __name__ == '__main__':
    unittest.main()
