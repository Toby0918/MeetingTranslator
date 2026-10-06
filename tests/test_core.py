import queue
import threading
import unittest
from unittest.mock import patch
import numpy as np
from core import Caption, Segmenter, Session, export_text, offer_latest


class CoreTests(unittest.TestCase):
    def test_maximum_duration_uses_recent_pause_without_losing_tail(self):
        s = Segmenter()
        loud = np.full(1600, .1, dtype=np.float32)
        quiet = np.zeros(1600, dtype=np.float32)
        frames = [loud] * 110 + [quiet] * 2 + [loud] * 8
        result = None
        for frame in frames:
            result = s.push(frame)
        self.assertEqual(len(result), 112 * 1600)
        for frame in [loud] * 8 + [quiet] * 5:
            trailing = s.push(frame)
        self.assertIsNotNone(trailing)
        np.testing.assert_array_equal(np.concatenate([result, trailing]),
            np.concatenate(frames + [loud] * 8 + [quiet] * 5))

    def test_silence_does_not_produce_caption_audio(self):
        s = Segmenter()
        for _ in range(300):
            self.assertIsNone(s.push(np.zeros(1600, dtype=np.float32)))
        self.assertIsNone(s.flush())

    def test_pause_preserves_quiet_word_boundaries(self):
        s = Segmenter()
        quiet = np.zeros(1600, dtype=np.float32)
        loud = np.full(1600, .1, dtype=np.float32)
        for _ in range(3):
            s.push(quiet)
        for _ in range(8):
            self.assertIsNone(s.push(loud))
        for _ in range(4):
            self.assertIsNone(s.push(quiet))
        audio = s.push(quiet)
        self.assertIsNotNone(audio)
        self.assertEqual(np.count_nonzero(audio), 8 * 1600)
        self.assertIsNone(s.flush())

    def test_continuous_speech_is_bounded(self):
        s = Segmenter(max_seconds=3)
        results = [s.push(np.full(1600, .1, dtype=np.float32)) for _ in range(90)]
        phrases = [x for x in results if x is not None]
        self.assertEqual(len(phrases), 3)
        self.assertTrue(all(len(x) == 48000 for x in phrases))

    def test_default_keeps_eight_second_clause_together(self):
        # The TED baseline cut a negation away from its verb at the old 6s limit.
        s = Segmenter()
        speech = np.full(1600, .1, dtype=np.float32)
        silence = np.zeros(1600, dtype=np.float32)
        chunks = [s.push(speech) for _ in range(80)]
        chunks += [s.push(silence) for _ in range(5)]
        self.assertEqual(len([x for x in chunks if x is not None]), 1)

    def test_playback_ending_without_silence_frames_flushes_tail(self):
        class FakeModels:
            def load(self): pass
            def recognize(self, audio): return 'The meeting is over.'
            def translate(self, text): return '会议结束了。'
        got_caption = threading.Event()
        events = []
        def emit(kind, data):
            events.append((kind, data))
            if kind == 'caption': got_caption.set()
        session = Session(FakeModels(), 'fake', emit)
        def fake_capture(q, done):
            import time
            for _ in range(4):
                q.put((np.full(1600, .1, dtype=np.float32), time.monotonic()))
            session.stop_event.wait(3)
            done.set()
        with patch.object(session, 'capture', fake_capture):
            session.start()
            received = got_caption.wait(2)
            session.stop()
            session.thread.join(2)
        self.assertTrue(received, 'No trailing caption when WASAPI stops delivering frames')

    def test_click_is_not_a_phrase(self):
        s = Segmenter()
        s.push(np.ones(1600, dtype=np.float32))
        for _ in range(6):
            self.assertIsNone(s.push(np.zeros(1600, dtype=np.float32)))

    def test_backpressure_is_bounded_and_visible(self):
        q = queue.Queue(maxsize=2)
        self.assertFalse(offer_latest(q, 1))
        self.assertFalse(offer_latest(q, 2))
        self.assertTrue(offer_latest(q, 3))
        self.assertEqual([q.get(), q.get()], [2, 3])

    def test_stop_during_load_does_not_open_capture(self):
        started, release = threading.Event(), threading.Event()
        class FakeModels:
            def load(self):
                started.set()
                release.wait(3)
        events = []
        session = Session(FakeModels(), 'fake', lambda *event: events.append(event))
        with patch.object(session, 'capture') as capture:
            session.start()
            self.assertTrue(started.wait(2))
            session.stop()
            release.set()
            self.assertTrue(session.done.wait(2))
            session.thread.join(1)
            capture.assert_not_called()
        self.assertEqual(events[-1][0], 'stopped')

    def test_load_failure_returns_stopped_and_error(self):
        class FakeModels:
            def load(self):
                raise RuntimeError('missing model')
        events = []
        session = Session(FakeModels(), 'fake', lambda *event: events.append(event))
        session.run()
        self.assertTrue(session.done.is_set())
        self.assertTrue(any(kind == 'error' for kind, _ in events))
        self.assertEqual(events[-1][0], 'stopped')

    def test_export_preserves_original_translation_and_time(self):
        result = export_text([Caption('12:34:56', 'Friday.', '星期五。', .8)])
        self.assertIn('[12:34:56]\nFriday.\n星期五。', result)

    def test_cloud_failure_preserves_original_and_does_not_silently_downgrade(self):
        import time
        from deepseek_translation import TranslationError
        class FakeModels:
            def recognize(self, audio): return 'Do not approve the order.'
            def translate(self, text): raise AssertionError('Unexpected silent fallback')
        class FailingTranslator:
            def translate(self, text, stop_event): raise TranslationError('DeepSeek 请求超时')
        events = []
        session = Session(FakeModels(), 'fake', lambda *e: events.append(e), translator=FailingTranslator())
        session.process_phrase(np.ones(16000, dtype=np.float32), time.monotonic())
        caption = next(data for kind, data in events if kind == 'caption')
        self.assertEqual(caption.original, 'Do not approve the order.')
        self.assertEqual(caption.translation_source, '翻译失败')
        self.assertTrue(any(kind == 'warning' for kind, _ in events))


if __name__ == '__main__':
    unittest.main()
