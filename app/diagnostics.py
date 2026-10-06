"""Explicit self-test of a downloaded bundle; does not start audio capture."""
import json
import sys
import time
from pathlib import Path

from runtime import VERSION, missing_model_files, resolve_model_root


def run_self_test(report_path, model_root=None, audio_path=None):
    root = Path(model_root) if model_root is not None else resolve_model_root()
    report = {'version': VERSION, 'frozen': bool(getattr(sys, 'frozen', False)),
              'passed': False, 'model_root': str(root), 'missing_models': missing_model_files(root)}
    started = time.perf_counter()
    if not report['missing_models']:
        try:
            from core import Models, list_sources
            from app import App
            import tkinter as tk
            window = tk.Tk()
            window.withdraw()
            try:
                application = App(window)
                window.update()
                report['gui_created'] = True
                report['default_mode'] = 'offline' if application.mode.current() == 1 else 'cloud'
                report['capture_started'] = application.session is not None
                report['system_device_count'] = len(list_sources('system')[0])
                report['microphone_device_count'] = len(list_sources('microphone')[0])
            finally:
                window.destroy()
            models = Models(root)
            tick = time.perf_counter()
            models.load()
            report['model_load_seconds'] = time.perf_counter() - tick
            report['offline_translation'] = models.translate(
                'The meeting starts at ten. Do not approve the order. Write 500 words.')
            if audio_path:
                from faster_whisper.audio import decode_audio
                audio = decode_audio(str(audio_path), sampling_rate=16000)
                report['audio_seconds'] = len(audio) / 16000
                report['recognized'] = models.recognize(audio)
                report['audio_translation'] = models.translate(report['recognized'])
            report['passed'] = bool(report['offline_translation']) and report['default_mode'] == 'offline' \
                and not report['capture_started'] and (not audio_path or bool(report.get('recognized')))
        except Exception as exc:
            # No provider calls, headers or credentials are part of this test.
            report['error'] = f'{type(exc).__name__}: {exc}'
    report['elapsed_seconds'] = time.perf_counter() - started
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['passed'] else 1
