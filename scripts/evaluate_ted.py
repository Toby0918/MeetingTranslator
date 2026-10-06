"""Reproduce file-audio evaluation. Reference subtitles never enter the models."""
import argparse
import hashlib
import html
import json
import re
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / 'app'))


def normalize_for_wer(text):
    text = re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', text)
    text = html.unescape(text).lower().replace('’', "'")
    return ' '.join(re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text))


def parse_vtt(path):
    cues = []
    for block in re.split(r'\n\s*\n', Path(path).read_text(encoding='utf-8-sig')):
        lines = block.strip().splitlines()
        timing = next((i for i, line in enumerate(lines) if '-->' in line), None)
        if timing is None:
            continue
        def seconds(value):
            return sum(float(part) * 60 ** i for i, part in enumerate(reversed(value.strip().split(':'))))
        start, end = lines[timing].split('-->')
        cues.append({'start': seconds(start), 'end': seconds(end.split()[0]),
                     'text': html.unescape(re.sub(r'<[^>]+>', '', ' '.join(lines[timing + 1:])))})
    return cues


def fetch_source(source, folder, download):
    import httpx
    folder.mkdir(parents=True, exist_ok=True)
    video, reference = folder / 'source.mp4', folder / 'en.vtt'
    if not video.exists() or not reference.exists():
        if not download:
            raise RuntimeError('Source missing; pass --download to fetch official TED media.')
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            response = client.get(source['url'])
            response.raise_for_status()
            data = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                                       response.text, re.S).group(1))['props']['pageProps']['videoData']
            resources = data['videoPlayerData']['resources']
            metadata = client.get(resources['hls']['metadata'])
            metadata.raise_for_status()
            if not video.exists():
                url = min(resources['h264'], key=lambda item: item['bitrate'])['file']
                with client.stream('GET', url) as media:
                    media.raise_for_status()
                    temporary = video.with_suffix('.download')
                    with temporary.open('wb') as output:
                        for block in media.iter_bytes():
                            output.write(block)
                    temporary.replace(video)
            if not reference.exists():
                track = next(item for item in metadata.json()['subtitles'] if item['code'] == 'en')
                response = client.get(track['webvtt'])
                response.raise_for_status()
                reference.write_text(response.text, encoding='utf-8')
    with video.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    if digest != source['sha256_video']:
        raise RuntimeError('TED source differs from the pinned benchmark; review before updating its manifest.')
    return video, reference


def legacy_segmenter():
    """Keep the pre-release segmentation policy for controlled comparisons."""
    import numpy as np
    from core import Segmenter
    class LegacySegmenter(Segmenter):
        def push(self, frame):
            loud = float(np.sqrt(np.mean(frame * frame))) >= self.threshold
            if not self.frames:
                self.pre.append(frame)
                if not loud:
                    return None
                self.frames = list(self.pre)
                self.samples = sum(len(part) for part in self.frames)
                self.voiced = len(frame)
                self.pre.clear()
            else:
                self.frames.append(frame)
                self.samples += len(frame)
                if loud:
                    self.voiced += len(frame)
            self.quiet = 0 if loud else self.quiet + len(frame)
            if self.quiet >= self.rate * .5 or self.samples >= self.rate * self.max_seconds:
                return self.flush()
            return None
    return LegacySegmenter()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--cache', type=Path, default=PROJECT / '.bench')
    parser.add_argument('--output', type=Path, default=PROJECT / '.bench' / 'rerun-summary.json')
    parser.add_argument('--talk', action='append', help='Talk ID, repeatable; defaults to all five')
    parser.add_argument('--baseline', action='store_true', help='Use the pre-release segmentation and single-sentence MT path')
    parser.add_argument('--mode', choices=['offline', 'cloud'], default='offline')
    parser.add_argument('--save-captions', action='store_true', help='Explicitly retain generated captions locally')
    parser.add_argument('--limit-seconds', type=float, help='Partial smoke run; no WER is reported')
    args = parser.parse_args()
    from core import Models, Segmenter
    from runtime import resolve_model_root
    from deepseek_translation import DeepSeekTranslator, TranslationError
    from credentials import load_api_key
    from faster_whisper.audio import decode_audio
    from jiwer import process_words
    manifest = json.loads((PROJECT / 'scripts' / 'ted_sources.json').read_text(encoding='utf-8'))
    selected = [source for source in manifest['talks'] if not args.talk or source['id'] in args.talk]
    if not selected:
        parser.error('No matching talk IDs.')
    models = Models(resolve_model_root())
    models.load()
    summaries = []
    for source in selected:
        folder = args.cache / source['id']
        video, reference = fetch_source(source, folder, args.download)
        audio = decode_audio(str(video), sampling_rate=16000)
        if args.limit_seconds:
            audio = audio[:int(args.limit_seconds * 16000)]
        segmenter = legacy_segmenter() if args.baseline else Segmenter()
        translator = DeepSeekTranslator(load_api_key()) if args.mode == 'cloud' else None
        rows = []
        started = time.perf_counter()
        def process(phrase, end):
            if phrase is None:
                return
            tick = time.perf_counter()
            text = models.recognize(phrase)
            asr_seconds = time.perf_counter() - tick
            if not text:
                return
            tick = time.perf_counter()
            failed = False
            try:
                if translator:
                    translated = translator.translate(text)
                elif args.baseline:
                    result = models.mt.translate_batch([models.sp.encode(text, out_type=str)],
                        beam_size=2, replace_unknowns=True, max_decoding_length=256)
                    translated = models.sp.decode(result[0].hypotheses[0]).replace('▁', ' ').strip()
                else:
                    translated = models.translate(text)
            except TranslationError:
                translated, failed = '【本句未翻译，请查看英文原文】', True
            rows.append({'start': max(0, end - len(phrase) / 16000), 'end': end,
                         'source': text, 'translation': translated, 'translation_failed': failed,
                         'asr_seconds': asr_seconds, 'mt_seconds': time.perf_counter() - tick})
        try:
            for end in range(1600, len(audio) + 1600, 1600):
                process(segmenter.push(audio[end - 1600:min(end, len(audio))]),
                        min(end, len(audio)) / 16000 - segmenter.samples / 16000)
            process(segmenter.flush(), len(audio) / 16000)
        finally:
            if translator:
                translator.close()
        summary = {'id': source['id'], 'url': source['url'], 'split': source['split'],
                   'audio_seconds': len(audio) / 16000, 'elapsed_seconds': time.perf_counter() - started,
                   'caption_count': len(rows), 'translation_failures': sum(row['translation_failed'] for row in rows),
                   'mode': args.mode, 'baseline': args.baseline, 'wer': None}
        if not args.limit_seconds:
            reference_text = normalize_for_wer(' '.join(cue['text'] for cue in parse_vtt(reference)))
            hypothesis = normalize_for_wer(' '.join(row['source'] for row in rows))
            errors = process_words(reference_text, hypothesis)
            summary.update(wer=errors.wer, reference_words=len(reference_text.split()),
                           substitutions=errors.substitutions, insertions=errors.insertions, deletions=errors.deletions)
        if args.save_captions:
            (folder / 'rerun-captions.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'date': manifest['evaluation_date'], 'talks': summaries},
                                     ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
