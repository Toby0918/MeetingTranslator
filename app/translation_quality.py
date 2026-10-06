"""Conservative preparation for an offline model trained on single sentences."""
import re
from decimal import Decimal

ABBREVIATIONS = {'dr', 'mr', 'mrs', 'ms', 'prof', 'sr', 'jr', 'st', 'vs', 'etc', 'e.g', 'i.e', 'u.s', 'u.k'}


def sentence_units(text):
    """Retain every sentence, without breaking decimals, initials or titles."""
    text = text.strip()
    if not text:
        return []
    units, start = [], 0
    for match in re.finditer(r'[.!?]+[\"\u201d\u2019]?\s+(?=[A-Z\"\u201c])', text):
        prefix = text[:match.start()].rsplit(None, 1)
        if not prefix:
            start = match.end()
            continue
        ending = prefix[-1].strip('\"(\u201c').lower()
        if match.group().startswith('.') and (ending in ABBREVIATIONS or
                re.fullmatch(r'(?:[a-z]\.)*[a-z]', ending)):
            continue
        units.append(text[start:match.start() + len(match.group().rstrip())].strip())
        start = match.end()
    if text[start:].strip():
        units.append(text[start:].strip())
    return units


def prepare_source(text):
    # These are explicit idioms; never rewrite literal mass or clinical insomnia.
    sleep_verbs = {'be': 'have', 'is': 'has', 'am': 'have', 'are': 'have', 'was': 'had', 'were': 'had'}
    text = re.sub(r'\b(be|is|am|are|was|were) sleep[- ]deprived\b',
        lambda m: sleep_verbs[m.group(1).lower()] + ' insufficient sleep', text, flags=re.I)
    text = re.sub(r'\ba ton of fun\b', 'a lot of fun', text, flags=re.I)
    return text


def preserve_word_count(source, translation):
    # English words and Chinese characters are different counting units.
    number = r'(\d[\d,]*(?:\.\d+)?)\s*[- ]\s*'
    word_counts = {Decimal(m.group(1).replace(',', '')) for m in
                   re.finditer(number + r'words?\b', source, re.I)}
    other_counts = {Decimal(m.group(1).replace(',', '')) for m in
                    re.finditer(number + r'(?:characters?|letters?|bytes?|symbols?|bits?)\b', source, re.I)}
    word_counts -= other_counts  # Equal mixed units are ambiguous; never guess.
    if word_counts:
        def replace(match):
            if count_value(match.group(1)) in word_counts:
                return match.group(1) + '个单词'
            return match.group()
        target_number = r'((?:\d{1,3}(?:[, ]\d{3})+|\d+)(?:\.\d+)?[万亿千百]?|[一二三四五六七八九十百千万亿零两]+)'
        boundary = r'(?<![\d.,一二三四五六七八九十百千万亿零两])'
        translation = re.sub(boundary + target_number + r'\s*(?:个)?字(?![节符母体串])', replace, translation)
    return translation


def count_value(value):
    """Compare a numeric Chinese count with the explicitly spoken word count."""
    digits = dict(zip('零一二三四五六七八九两', (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 2)))
    multipliers = {'十': 10, '百': 100, '千': 1000, '万': 10000, '亿': 100000000}
    value = value.replace(',', '').replace(' ', '')
    numeric = re.fullmatch(r'(\d+(?:\.\d+)?)([十百千万亿]?)', value)
    if numeric:
        return Decimal(numeric.group(1)) * multipliers.get(numeric.group(2), 1)
    if value and all(ch in digits for ch in value):
        return Decimal(''.join(str(digits[ch]) for ch in value))
    simple = re.fullmatch(r'([零一二三四五六七八九两]?)([十百千万亿])', value)
    if simple:
        return Decimal(digits[simple.group(1)] if simple.group(1) else 1) * multipliers[simple.group(2)]
    # Complex and colloquial counts can be ambiguous. Preserve them unchanged.
    return None


def valid_translation(text):
    return bool(text.strip()) and not any(
        ch == '\ufffd' or 0xE000 <= ord(ch) <= 0xF8FF or
        0xF0000 <= ord(ch) <= 0xFFFFD or 0x100000 <= ord(ch) <= 0x10FFFD
        for ch in text)
