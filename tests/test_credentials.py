import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from credentials import CredentialError, load_api_key


class CredentialTests(unittest.TestCase):
    def settings(self, root, values):
        workbook = root / 'KEY.xlsx'
        with zipfile.ZipFile(workbook, 'w') as archive:
            archive.writestr('xl/sharedStrings.xml', '<sst>' + ''.join('<si><t>'+v+'</t></si>' for v in values) + '</sst>')
        settings = root / 'settings.json'
        settings.write_text(json.dumps({'deepseek_key_file': str(workbook)}), encoding='utf-8')
        return settings

    @patch.dict(os.environ, {}, clear=True)
    def test_reads_existing_workbook_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            key = 'sk-fakecredentialfortestonly'
            settings = self.settings(root, ['DeepSeek', key])
            before = (root / 'KEY.xlsx').read_bytes()
            self.assertEqual(load_api_key(settings), key)
            self.assertEqual((root / 'KEY.xlsx').read_bytes(), before)
            self.assertNotIn(key, settings.read_text())

    @patch.dict(os.environ, {}, clear=True)
    def test_ambiguous_keys_fail_without_exposing_them(self):
        with tempfile.TemporaryDirectory() as folder:
            keys = ['sk-fakecredentialfirstonly', 'sk-fakecredentialsecondonly']
            settings = self.settings(Path(folder), keys)
            with self.assertRaises(CredentialError) as result:
                load_api_key(settings)
            self.assertTrue(all(k not in str(result.exception) for k in keys))

    @patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'provided-in-memory'}, clear=True)
    def test_environment_override_needs_no_file(self):
        self.assertEqual(load_api_key('does-not-exist.json'), 'provided-in-memory')

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_config_is_not_a_crash(self):
        self.assertEqual(load_api_key('does-not-exist.json'), '')
