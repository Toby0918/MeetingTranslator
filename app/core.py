"""Local speech recognition, with optional explicitly selected text-only cloud translation."""
from __future__ import annotations

import math
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from deepseek_translation import TranslationError
from translation_quality import sentence_units, prepare_source, preserve_word_count, valid_translation
from runtime import translation_directory

import numpy as np


@dataclass
class Caption:
    timestamp: str
    original: str
    translated: str
    processing_seconds: float
    audio_seconds: float = 0.0
    end_to_caption_seconds: float = 0.0
    translation_source: str = '本地翻译'
    audio_source: str = '电脑会议声音'


class Segmenter:
    """Short phrase segmentation with pre-roll and a bounded maximum phrase length."""
    def __init__(self, rate=16000, threshold=0.003, max_seconds=12.0):
        self.rate, self.threshold, self.max_seconds = rate, threshold, max_seconds
        self.pre = deque(maxlen=3)
        self.frames = []
        self.samples = self.quiet = self.voiced = 0

    def push(self, frame):
        loud = float(np.sqrt(np.mean(frame * frame))) >= self.threshold
        if not self.frames:
            self.pre.append(frame)
            if not loud:
                return None
            self.frames = list(self.pre)
            self.samples = sum(len(x) for x in self.frames)
            self.voiced = len(frame)
            self.pre.clear()
        else:
            self.frames.append(frame)
            self.samples += len(frame)
            if loud:
                self.voiced += len(frame)
        self.quiet = 0 if loud else self.quiet + len(frame)
        if self.quiet >= self.rate * .5:
            return self.flush()
        if self.samples >= self.rate * self.max_seconds:
            # Prefer a short recent pause to a cut through a word. Carry the
            # remaining PCM into the next phrase, so no speech is discarded.
            offset, cut = 0, None
            for i, part in enumerate(self.frames):
                offset += len(part)
                if (self.samples - self.rate * 2 <= offset <= self.samples - self.rate * .2
                        and float(np.sqrt(np.mean(part * part))) < self.threshold):
                    cut = i + 1
            if cut:
                result = np.concatenate(self.frames[:cut])
                self.frames = self.frames[cut:]
                self.samples = sum(len(part) for part in self.frames)
                self.voiced = sum(len(part) for part in self.frames
                    if float(np.sqrt(np.mean(part * part))) >= self.threshold)
                self.quiet = 0
                return result
            return self.flush()
        return None

    def flush(self):
        result = np.concatenate(self.frames) if self.frames and self.voiced >= self.rate * .25 else None
        self.frames = []
        self.samples = self.quiet = self.voiced = 0
        return result


def offer_latest(q, item):
    """Bound latency. Tell the caller whenever unprocessed audio was dropped."""
    dropped = False
    try:
        q.put_nowait(item)
    except queue.Full:
        try:
            q.get_nowait()
            dropped = True
        except queue.Empty:
            pass
        q.put_nowait(item)
    return dropped


def source_devices(p, input_kind='system'):
    """Keep microphone inputs and playback loopback endpoints strictly separate."""
    import pyaudiowpatch as pa
    if input_kind == 'system':
        devices = list(p.get_loopback_device_info_generator())
        try:
            default = p.get_default_wasapi_loopback()['name']
        except OSError:
            default = None
    elif input_kind == 'microphone':
        host = p.get_host_api_info_by_type(pa.paWASAPI)
        devices = [p.get_device_info_by_index(i) for i in range(p.get_device_count())]
        devices = [d for d in devices if d['hostApi'] == host['index']
                   and d['maxInputChannels'] > 0 and not d.get('isLoopbackDevice', False)]
        default = next((d['name'] for d in devices if d['index'] == host['defaultInputDevice']), None)
    else:
        raise ValueError('未知声音输入类型。')
    return devices, default


def list_sources(input_kind='system'):
    import pyaudiowpatch as pa
    with pa.PyAudio() as p:
        return source_devices(p, input_kind)


def list_outputs():
    return list_sources('system')


class Models:
    def __init__(self, root: Path):
        self.root = root
        self.asr = self.mt = self.sp = None
        self.target_sp = None
        self.source_prefix, self.source_suffix = [], []

    def load(self):
        if self.asr is not None:
            return
        from faster_whisper import WhisperModel
        import ctranslate2
        import sentencepiece
        translation = translation_directory(self.root)
        marian = translation.name == 'meeting-en_zh-v1_1'
        # CPU int8 avoids system-wide CUDA changes and is tested on this machine.
        asr = WhisperModel(str(self.root / 'whisper-small.en'), device='cpu',
                           compute_type='int8', cpu_threads=8, local_files_only=True)
        mt = ctranslate2.Translator(str(translation if marian else translation / 'model'), device='cpu',
                                   compute_type='int8', intra_threads=4)
        # Native SentencePiece file loading uses narrow Windows paths. Python
        # reads Unicode paths safely; pass the unchanged serialized model.
        sp = sentencepiece.SentencePieceProcessor(model_proto=(translation /
            ('source.spm' if marian else 'sentencepiece.model')).read_bytes())
        target_sp = sentencepiece.SentencePieceProcessor(
            model_proto=(translation / 'target.spm').read_bytes()) if marian else sp
        self.asr, self.mt, self.sp = asr, mt, sp
        self.target_sp = target_sp
        self.source_prefix = ['>>cmn_Hans<<'] if marian else []
        self.source_suffix = ['</s>'] if marian else []

    def encode_source(self, text):
        return self.source_prefix + self.sp.encode(prepare_source(text), out_type=str) + self.source_suffix

    def translate(self, text):
        units = sentence_units(text)
        if not units:
            return ''
        results = self.mt.translate_batch(
            [self.encode_source(unit) for unit in units],
            beam_size=2, replace_unknowns=True, max_decoding_length=256)
        translations = []
        for unit, result in zip(units, results):
            decoder = self.target_sp if self.target_sp is not None else self.sp
            value = decoder.decode(result.hypotheses[0]).replace('▁', ' ').strip()
            if not valid_translation(value):
                alternative = self.mt.translate_batch([self.encode_source(unit)],
                    beam_size=4, replace_unknowns=True, max_decoding_length=256)
                value = decoder.decode(alternative[0].hypotheses[0]).replace('▁', ' ').strip()
                if not valid_translation(value):
                    raise TranslationError('本地模型未返回可读译文，本句请查看英文原文。')
            translations.append(preserve_word_count(unit, value))
        return ' '.join(translations)

    def recognize(self, audio):
        segments, _ = self.asr.transcribe(audio, language='en', beam_size=2,
            vad_filter=True, vad_parameters={'min_silence_duration_ms': 300},
            condition_on_previous_text=False, temperature=0,
            no_speech_threshold=.6, hallucination_silence_threshold=1.0)
        return ' '.join(s.text.strip() for s in segments
                        if s.avg_logprob > -1.0 and s.no_speech_prob < .65).strip()


class Session:
    """One stop event and queues per session; never reuse a previous capture worker."""
    def __init__(self, models, device_name, emit, max_seconds=12.0, translator=None, input_kind='system'):
        if input_kind not in ('system', 'microphone'):
            raise ValueError('未知声音输入类型。')
        self.models, self.device_name, self.emit = models, device_name, emit
        self.input_kind = input_kind
        self.audio_source = '麦克风' if input_kind == 'microphone' else '电脑会议声音'
        self.max_seconds = max_seconds
        self.stop_event = threading.Event()
        self.done = threading.Event()
        self.thread = None
        self.dropped = 0
        self.translator = translator

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def process_phrase(self, phrase, captured_at):
        if phrase is None or self.stop_event.is_set():
            return
        start = time.perf_counter()
        text = self.models.recognize(phrase)
        if self.stop_event.is_set():
            return
        if text:
            source = 'DeepSeek' if self.translator else '本地翻译'
            try:
                translated = self.translator.translate(text, self.stop_event) if self.translator else self.models.translate(text)
            except TranslationError as exc:
                translated = '【本句未翻译，请查看英文原文】'
                source = '翻译失败'
                self.emit('warning', str(exc))
            if not self.stop_event.is_set():
                self.emit('caption', Caption(time.strftime('%H:%M:%S'), text, translated,
                    time.perf_counter() - start, len(phrase) / 16000,
                    max(0.0, time.monotonic() - captured_at), source, self.audio_source))

    def run(self):
        capture = None
        audio_queue = queue.Queue(maxsize=120)  # 12 seconds at 100 ms per block
        capture_done = threading.Event()
        try:
            self.emit('status', '正在加载本地模型…')
            self.models.load()
            if self.stop_event.is_set():
                return
            capture = threading.Thread(target=self.capture, args=(audio_queue, capture_done), daemon=True)
            capture.start()
            segmenter = Segmenter(max_seconds=self.max_seconds)
            last_audio_at = time.monotonic()
            while not self.stop_event.is_set():
                try:
                    block, captured_at = audio_queue.get(timeout=.2)
                except queue.Empty:
                    # WASAPI may emit no frames at all when a player pauses. Flush
                    # the trailing utterance without depending on zero PCM frames.
                    if time.monotonic() - last_audio_at >= .6:
                        self.process_phrase(segmenter.flush(), last_audio_at)
                    if capture_done.is_set():
                        break
                    continue
                if block is None:  # Explicit discontinuity: do not join words across lost audio.
                    segmenter = Segmenter(max_seconds=self.max_seconds)
                    continue
                if time.monotonic() - captured_at > 12:
                    self.emit('warning', '处理落后，已跳过过期声音。部分字幕可能缺失。')
                    segmenter = Segmenter(max_seconds=self.max_seconds)
                    continue
                last_audio_at = captured_at
                phrase = segmenter.push(block)
                if phrase is not None:
                    self.process_phrase(phrase, captured_at - segmenter.samples / segmenter.rate)
        except Exception as exc:
            self.emit('error', f'{type(exc).__name__}: {exc}')
        finally:
            self.stop_event.set()
            if capture is not None:
                capture.join(timeout=3)
            if self.translator is not None:
                self.translator.close()
            self.done.set()
            self.emit('stopped', None)

    def capture(self, q, done):
        import pyaudiowpatch as pa
        from scipy.signal import resample_poly
        stream = None
        raw = queue.Queue(maxsize=120)
        overflow = threading.Event()

        def callback(data, count, timing, status):
            if self.stop_event.is_set():
                return None, pa.paComplete
            if status or offer_latest(raw, (data, time.monotonic())):
                overflow.set()
            return None, pa.paContinue

        try:
            with pa.PyAudio() as p:
                devices, _ = source_devices(p, self.input_kind)
                matches = [d for d in devices if d['name'] == self.device_name]
                if len(matches) != 1:
                    raise RuntimeError(f'无法唯一定位所选{self.audio_source}设备。请停止后刷新设备并重新选择。')
                device = matches[0]
                rate, channels = int(device['defaultSampleRate']), int(device['maxInputChannels'])
                divisor = math.gcd(rate, 16000)
                stream = p.open(format=pa.paFloat32, channels=channels, rate=rate, input=True,
                                input_device_index=device['index'], frames_per_buffer=rate // 10,
                                stream_callback=callback)
                mode = 'DeepSeek 翻译' if self.translator else '本地翻译'
                self.emit('status', f'正在监听 · {self.audio_source} · 英语 → 中文 · {mode}')
                last_frame = time.monotonic()
                waiting_for_audio = False
                while not self.stop_event.is_set():
                    try:
                        data, captured_at = raw.get(timeout=.2)
                    except queue.Empty:
                        if self.stop_event.is_set():
                            break
                        if not stream.is_active():
                            raise RuntimeError('音频设备已停止。请检查设备连接并重新开始。')
                        if time.monotonic() - last_frame > 15:
                            hint = ('尚未收到麦克风声音。请检查连接、静音开关及 Windows 麦克风访问设置。'
                                    if self.input_kind == 'microphone' else
                                    '尚未收到声音。请确认会议使用的播放设备与此处一致。')
                            self.emit('hint', hint)
                            waiting_for_audio = True
                            last_frame = time.monotonic()
                        continue
                    last_frame = time.monotonic()
                    if waiting_for_audio:
                        self.emit('hint', '已恢复接收声音。请核对人名、数字和专业词汇。')
                        waiting_for_audio = False
                    audio = np.frombuffer(data, dtype=np.float32).reshape(-1, channels).mean(axis=1)
                    audio = resample_poly(audio, 16000 // divisor, rate // divisor).astype(np.float32)
                    self.emit('level', min(1.0, float(np.sqrt(np.mean(audio * audio))) * 10))
                    if overflow.is_set():
                        offer_latest(q, (None, captured_at))
                        overflow.clear()
                        self.emit('warning', '音频缓冲区溢出，部分声音已跳过。')
                    if offer_latest(q, (audio, captured_at)):
                        self.dropped += 1
                        offer_latest(q, (None, captured_at))
                        self.emit('warning', '处理跟不上讲话速度，正在追赶。部分字幕可能缺失。')
                stream.stop_stream()
                stream.close()
                stream = None
        except Exception as exc:
            self.emit('error', f'声音采集失败：{exc}')
            self.stop_event.set()
        finally:
            done.set()


def export_text(captions):
    return '会议翻译记录（英语 → 中文）\n自动翻译，请核对专有名词及数字。\n\n' + '\n\n'.join(
        f'来源：{c.audio_source} · {c.translation_source}\n[{c.timestamp}]\n{c.original}\n{c.translated}' for c in captions) + '\n'
