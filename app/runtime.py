"""Portable assets are resolved relative to the executable, never a user's PC."""
import json
import sys
from pathlib import Path

VERSION = '1.0.0'
MODEL_FILES = (
    'whisper-small.en/model.bin',
    'whisper-small.en/config.json',
    'whisper-small.en/tokenizer.json',
    'translation/translate-en_zh-1_9/model/model.bin',
    'translation/translate-en_zh-1_9/model/config.json',
    'translation/translate-en_zh-1_9/sentencepiece.model',
)


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
    return [name for name in MODEL_FILES if not (Path(root) / name).is_file()]
