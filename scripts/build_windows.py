"""Build a self-contained Windows x64 release from a clean build environment."""
import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'app'))
from runtime import VERSION, resolve_model_root, missing_model_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', type=Path, default=resolve_model_root())
    args = parser.parse_args()
    missing = missing_model_files(args.models)
    if missing:
        raise SystemExit('Missing model files: ' + ', '.join(missing))
    if sys.platform != 'win32':
        raise SystemExit('Build this distribution on Windows x64.')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--onedir', '--windowed', '--name', 'MeetingTranslator',
               '--paths', str(PROJECT / 'app'), '--distpath', str(PROJECT / 'dist'),
               '--workpath', str(PROJECT / 'build'), '--specpath', str(PROJECT / 'build'),
               '--exclude-module', 'yt_dlp', '--exclude-module', 'jiwer',
               '--exclude-module', 'pytest', '--exclude-module', 'setuptools',
               '--exclude-module', 'pip']
    for package in ('faster_whisper', 'ctranslate2', 'sentencepiece', 'pyaudiowpatch', 'tokenizers'):
        command += ['--collect-all', package]
    command += [str(PROJECT / 'app' / 'app.py')]
    subprocess.run(command, cwd=PROJECT, check=True)
    bundle = PROJECT / 'dist' / 'MeetingTranslator'
    for model in ('whisper-small.en', 'translation'):
        shutil.copytree(args.models / model, bundle / 'models' / model,
                        dirs_exist_ok=True, ignore=shutil.ignore_patterns('.cache', '*.lock', '*.metadata'))
    for name in ('README.md', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(PROJECT / name, bundle / name)
    (bundle / 'docs').mkdir(exist_ok=True)
    for name in ('使用说明.md', 'TED扩展评估报告_v1.1_2026-10-06.md', 'benchmark-summary.json',
                 'mt-training-v1.1.json', 'mt-pair-scores-v1.1.json'):
        shutil.copy2(PROJECT / 'docs' / name, bundle / 'docs' / name)
    shutil.copytree(PROJECT / 'training', bundle / 'training', dirs_exist_ok=True)
    shutil.copytree(PROJECT / 'licenses', bundle / 'licenses', dirs_exist_ok=True)
    packages = [line.split('==')[0] for line in
                (PROJECT / 'requirements-lock.txt').read_text().splitlines() if line.strip()]
    for name in packages + ['pyinstaller']:
        distribution = importlib.metadata.distribution(name)
        for item in distribution.files or []:
            if any('license' in part.lower() or part.lower().startswith('copying')
                   for part in item.parts) and item.suffix.lower() not in ('.py', '.pyc'):
                origin = distribution.locate_file(item)
                if origin.is_file():
                    # Preserve directories when a wheel contains several licenses.
                    relative = Path(*[part for part in item.parts if part not in ('..', '.')])
                    target = bundle / 'licenses' / name / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(origin, target)
    for name in ('tcl8.6', 'tk8.6'):
        terms = Path(sys.base_prefix) / 'tcl' / name / 'license.terms'
        if terms.is_file():
            shutil.copy2(terms, bundle / 'licenses' / f'{name}-license.terms')
    # Explicitly exclude machine configuration, credentials and benchmark media.
    prohibited = {'settings.json', 'runtime-config.json', 'KEY.xlsx', 'migration-plan.json'}
    bad = [p for p in bundle.rglob('*') if p.name in prohibited]
    if bad:
        raise SystemExit('Private configuration unexpectedly entered the bundle.')
    files = []
    for p in sorted(bundle.rglob('*')):
        if p.is_file() and p.name != 'bundle-manifest.json':
            with p.open('rb') as handle:
                digest = hashlib.file_digest(handle, 'sha256').hexdigest()
            files.append({'path': p.relative_to(bundle).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest})
    (bundle / 'bundle-manifest.json').write_text(json.dumps(
        {'version': VERSION, 'platform': 'Windows x64', 'files': files}, indent=2), encoding='utf-8')
    archive = PROJECT / 'dist' / f'MeetingTranslator-{VERSION}-Windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():
                output.write(path, path.relative_to(bundle.parent))
    with archive.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    (PROJECT / 'dist' / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size, 'sha256': digest}))


if __name__ == '__main__':
    main()
