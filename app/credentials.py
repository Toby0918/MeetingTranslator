"""Read a credential from its existing location; never copy it to app settings."""
import json
import os
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


class CredentialError(Exception):
    pass


def load_api_key(settings_path=None):
    value = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    if value:
        return value
    settings = Path(settings_path) if settings_path else Path(__file__).with_name('settings.json')
    if not settings.exists():
        return ''
    try:
        path = Path(json.loads(settings.read_text(encoding='utf-8'))['deepseek_key_file'])
        if path.suffix.lower() != '.xlsx':
            raise CredentialError('密钥来源需为已配置的 XLSX 文件。')
        texts = []
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name == 'xl/sharedStrings.xml' or (name.startswith('xl/worksheets/') and name.endswith('.xml')):
                    root = ElementTree.fromstring(archive.read(name))
                    texts.extend(node.text or '' for node in root.iter()
                                 if node.tag.rsplit('}', 1)[-1] in ('t', 'v'))
        keys = set(re.findall(r'(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{16,}(?![A-Za-z0-9_-])', '\n'.join(texts)))
        if len(keys) != 1:
            raise CredentialError('密钥文件中没有唯一可用的 DeepSeek 密钥，请使用“设置 API 密钥”。')
        return keys.pop()
    except CredentialError:
        raise
    except Exception:
        raise CredentialError('无法读取现有密钥文件，请检查文件是否在本机可用，或使用“设置 API 密钥”。') from None
