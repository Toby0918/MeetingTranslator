import queue
import threading
import time
import unittest
from unittest.mock import patch
import numpy as np
import pyaudiowpatch as pa
from scipy.signal import resample_poly  # Preload DSP before timing the callback itself.
from core import Session, source_devices


class FakeStream:
    def __init__(self): self.closed = False
    def is_active(self): return not self.closed
    def stop_stream(self): self.closed = True
    def close(self): self.closed = True


class FakeAudio:
    def __init__(self):
        self.devices = [
            dict(index=0, name='MME duplicate mic', hostApi=0, maxInputChannels=1, defaultSampleRate=44100),
            dict(index=1, name='Headset mic', hostApi=2, maxInputChannels=1, defaultSampleRate=48000, isLoopbackDevice=False),
            dict(index=2, name='Speakers [Loopback]', hostApi=2, maxInputChannels=2, defaultSampleRate=48000, isLoopbackDevice=True),
            dict(index=3, name='Speakers', hostApi=2, maxInputChannels=0, defaultSampleRate=48000),
        ]
        self.open_args = None
        self.stream = FakeStream()
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def get_device_count(self): return len(self.devices)
    def get_device_info_by_index(self, index): return self.devices[index]
    def get_host_api_info_by_type(self, kind): return dict(index=2, defaultInputDevice=1)
    def get_loopback_device_info_generator(self): return iter([self.devices[2]])
    def get_default_wasapi_loopback(self): return self.devices[2]
    def open(self, **kwargs):
        self.open_args = kwargs
        channels = kwargs['channels']
        samples = np.full((4800, channels), .08, dtype=np.float32)
        kwargs['stream_callback'](samples.tobytes(), 4800, {}, 0)
        return self.stream


class AudioInputTests(unittest.TestCase):
    def test_microphones_exclude_loopback_outputs_and_other_host_duplicates(self):
        devices, default = source_devices(FakeAudio(), 'microphone')
        self.assertEqual([d['name'] for d in devices], ['Headset mic'])
        self.assertEqual(default, 'Headset mic')

    def test_system_audio_excludes_microphones(self):
        devices, default = source_devices(FakeAudio(), 'system')
        self.assertEqual([d['name'] for d in devices], ['Speakers [Loopback]'])
        self.assertEqual(default, 'Speakers [Loopback]')

    def test_capture_routes_selected_endpoint_resamples_and_closes(self):
        for kind, name, index in [('microphone', 'Headset mic', 1), ('system', 'Speakers [Loopback]', 2)]:
            with self.subTest(kind=kind):
                audio = FakeAudio()
                q, done, events = queue.Queue(), threading.Event(), []
                session = Session(None, name, lambda *e: events.append(e), input_kind=kind)
                with patch.object(pa, 'PyAudio', return_value=audio):
                    thread = threading.Thread(target=session.capture, args=(q, done))
                    thread.start()
                    try:
                        block, _ = q.get(timeout=3)
                    finally:
                        session.stop()
                        thread.join(3)
                self.assertTrue(done.is_set())
                self.assertFalse(thread.is_alive())
                self.assertEqual(audio.open_args['input_device_index'], index)
                self.assertEqual(block.shape, (1600,))
                self.assertGreater(np.mean(block), .075)
                self.assertTrue(audio.stream.closed)
                self.assertFalse(any(k == 'error' for k, _ in events))

    def test_missing_mic_never_opens_loopback_as_fallback(self):
        audio = FakeAudio()
        events = []
        session = Session(None, 'Speakers [Loopback]', lambda *e: events.append(e), input_kind='microphone')
        with patch.object(pa, 'PyAudio', return_value=audio):
            session.capture(queue.Queue(), threading.Event())
        self.assertIsNone(audio.open_args)
        self.assertTrue(session.stop_event.is_set())
        self.assertTrue(any(k == 'error' for k, _ in events))

    def test_requested_stop_during_empty_callback_wait_is_not_device_failure(self):
        audio = FakeAudio()
        events = []
        session = Session(None, 'Headset mic', lambda *e: events.append(e), input_kind='microphone')
        class StoppingQueue(queue.Queue):
            def get(self, *args, **kwargs):
                session.stop()
                audio.stream.closed = True
                raise queue.Empty()
        raw = StoppingQueue()
        with patch.object(pa, 'PyAudio', return_value=audio), patch('core.queue.Queue', return_value=raw):
            session.capture(queue.Queue(), threading.Event())
        self.assertFalse(any(k == 'error' for k, _ in events))
        self.assertTrue(audio.stream.closed)

    def test_microphone_caption_has_source_and_uses_selected_translator(self):
        class Models:
            def recognize(self, audio): return 'Please speak clearly.'
            def translate(self, text): raise AssertionError('Unexpected local translator')
        class Translator:
            def translate(self, text, stop_event): return '请说清楚。'
        events = []
        session = Session(Models(), 'Headset mic', lambda *e: events.append(e),
                          translator=Translator(), input_kind='microphone')
        session.process_phrase(np.ones(16000, dtype=np.float32), time.monotonic())
        caption = next(data for kind, data in events if kind == 'caption')
        self.assertEqual(caption.audio_source, '麦克风')
        self.assertEqual(caption.original, 'Please speak clearly.')
        self.assertEqual(caption.translated, '请说清楚。')
        self.assertEqual(caption.translation_source, 'DeepSeek')
