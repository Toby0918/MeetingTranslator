"""Portable assets are resolved relative to the executable, never a user's PC."""
import json
import sys
from pathlib import Path

VERSION = '1.1.0'
MODEL_FILES = (
    'whisper-small.en/model.bin',
    'whisper-small.en/config.json',
    'whisper-small.en/tokenizer.json',
    'translation/translate-en_zh-1_9/model/model.bin',
    'translation/translate-en_zh-1_9/model/config.json',
    'translation/translate-en_zh-1_9/sentencepiece.model',
)
MARIAN_DIRECTORY = 'translation/meeting-en_zh-v1_1'
MARIAN_FILES = MODEL_FILES[:3] + tuple(MARIAN_DIRECTORY + '/' + name for name in (
    'model.bin', 'config.json', 'shared_vocabulary.json', 'source.spm', 'target.spm'))


def translation_directory(root):
    """Prefer the release model; retain existing developer Argos assets."""
    root = Path(root)
    marian = root / MARIAN_DIRECTORY
    return marian if marian.is_dir() else root / 'translation' / 'translate-en_zh-1_9'


def resolve_model_root(executable=None, frozen=None, project_root=None):
    frozen = getattr(sys, 'frozen', False) if frozen is None else frozen
    if frozen:
        return Path(executable or sys.executable).resolve().parent / 'models'
    root = Path(project_root or Path(__file__).resolve().parents[1])
    config = root / 'runtime-config.json'
    if config.is_file():
        try:
            value = json.loads(config.read_text(encoding='utf-8'))['model_root']
            if isinstance(value, str) and value:
                return Path(value)
        except (OSError, ValueError, KeyError):
            pass
    return root / 'models'


def missing_model_files(root):
    files = MARIAN_FILES if translation_directory(root).name == 'meeting-en_zh-v1_1' else MODEL_FILES
    return [name for name in files if not (Path(root) / name).is_file()]
