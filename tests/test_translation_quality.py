import unittest
from pathlib import Path
from types import SimpleNamespace

from core import Models
from deepseek_translation import TranslationError
from translation_quality import sentence_units, preserve_word_count


class TextTokens:
    def encode(self, text, out_type=str):
        return [text]

    def decode(self, tokens):
        return ''.join(tokens)


class SentenceTranslator:
    """Boundary double for a single-sentence translation model."""
    def translate_batch(self, batches, **kwargs):
        translations = {
            'This is not the conclusion.': '这不是结论。',
            'The trial may fail.': '试验可能失败。',
            'Dr. Lee paid 12.5 dollars.': '李博士支付了12.5美元。',
            'It was not free.': '这不是免费的。',
            'Write 500 words.': '写500字。',
            'Write 500 characters.': '写500字。',
            'Use 500 words and keep the file below 1024 bytes.': '使用500字,文件不得超过1024字节。',
            'Write 500 words and 100 characters.': '写500字和100字。',
            'Write 500 words and 500 characters.': '写500字和500字。',
            'Write 50,000 words.': '写五万字。',
            'You may be short of sleep.': '你可能睡不着。',
            'You may have insufficient sleep.': '你可能睡眠不足。',
            'You may be sleep deprived.': '你可能失眠。',
            'They are a lot of fun.': '它们很有趣。',
            'They are a ton of fun.': '它们是一吨乐趣。',
        }
        return [SimpleNamespace(hypotheses=[[translations.get(tokens[0], '这不是结论。')]])
                for tokens in batches]


class TranslationQualityTests(unittest.TestCase):
    def model(self):
        model = Models(Path('unused'))
        model.sp = TextTokens()
        model.mt = SentenceTranslator()
        return model

    def test_multi_sentence_caption_preserves_later_uncertainty(self):
        self.assertEqual(self.model().translate('This is not the conclusion. The trial may fail.'),
                         '这不是结论。 试验可能失败。')

    def test_abbreviation_and_decimal_are_not_sentence_boundaries(self):
        self.assertEqual(self.model().translate('Dr. Lee paid 12.5 dollars. It was not free.'),
                         '李博士支付了12.5美元。 这不是免费的。')

    def test_english_word_count_does_not_become_character_count(self):
        self.assertEqual(self.model().translate('Write 500 words.'), '写500个单词。')

    def test_explicit_character_count_is_preserved(self):
        self.assertEqual(self.model().translate('Write 500 characters.'), '写500字。')

    def test_sleep_deprivation_is_not_insomnia(self):
        self.assertEqual(self.model().translate('You may be sleep deprived.'), '你可能睡眠不足。')

    def test_fun_idiom_does_not_become_a_unit_of_mass(self):
        self.assertEqual(self.model().translate('They are a ton of fun.'), '它们很有趣。')

    def test_invalid_model_characters_trigger_a_clean_alternative(self):
        model = self.model()
        class InvalidFirst:
            def translate_batch(self, batches, **kwargs):
                value = '瞷\ue000и' if kwargs.get('beam_size') == 2 else '现在有了动力。'
                return [SimpleNamespace(hypotheses=[[value]]) for _ in batches]
        model.mt = InvalidFirst()
        self.assertEqual(model.translate('We have momentum.'), '现在有了动力。')

    def test_all_invalid_decodings_are_reported_as_translation_failure(self):
        model = self.model()
        class AlwaysInvalid:
            def translate_batch(self, batches, **kwargs):
                return [SimpleNamespace(hypotheses=[['\ufffd\ue001']]) for _ in batches]
        model.mt = AlwaysInvalid()
        with self.assertRaises(TranslationError):
            model.translate('We have momentum.')

    def test_word_count_does_not_corrupt_bytes_in_same_sentence(self):
        self.assertEqual(self.model().translate('Use 500 words and keep the file below 1024 bytes.'),
                         '使用500个单词,文件不得超过1024字节。')

    def test_distinct_word_and_character_counts_remain_distinct(self):
        self.assertEqual(self.model().translate('Write 500 words and 100 characters.'),
                         '写500个单词和100字。')

    def test_ambiguous_equal_counts_are_not_blindly_relabelled(self):
        self.assertEqual(self.model().translate('Write 500 words and 500 characters.'), '写500字和500字。')

    def test_chinese_written_number_preserves_english_word_unit(self):
        self.assertEqual(self.model().translate('Write 50,000 words.'), '写五万个单词。')

    def test_leading_punctuation_does_not_abort_sentence_processing(self):
        try:
            units = sentence_units('. Do not approve the order.')
        except Exception as exc:
            self.fail(f'Punctuation-prefixed ASR output stopped translation: {type(exc).__name__}')
        self.assertEqual(units, ['Do not approve the order.'])

    def test_digit_spelled_character_count_does_not_match_four_words(self):
        self.assertEqual(preserve_word_count('Write 4 words and 1024 characters.', '写四字和一零二四字。'),
                         '写四个单词和一零二四字。')

    def test_unsupported_nested_number_is_not_mislabelled_as_word_count(self):
        self.assertEqual(preserve_word_count('Write 10,000 words and 1000000000000 characters.',
                         '写一万字和一万亿字。'), '写一万个单词和一万亿字。')

    def test_ambiguous_colloquial_number_is_not_guessed(self):
        self.assertEqual(preserve_word_count('Write 105 words and 150 characters.', '写一百五字。'), '写一百五字。')

    def test_mixed_numeral_is_not_partially_matched(self):
        self.assertEqual(preserve_word_count('Write 5000 words and 15000 characters.', '写5000字和1万5千字。'),
                         '写5000个单词和1万5千字。')
        self.assertEqual(preserve_word_count('Write 50 words and 150 characters.', '写50字和一百50字。'),
                         '写50个单词和一百50字。')

    def test_counted_character_phrase_does_not_change_english_word_unit(self):
        self.assertEqual(preserve_word_count('Write 500 words.', '写五百个字。'), '写五百个单词。')
        self.assertEqual(preserve_word_count('Write 500 words.', '写500个字。'), '写500个单词。')

    def test_counted_words_do_not_corrupt_explicit_bytes_or_other_characters(self):
        self.assertEqual(preserve_word_count('Write 500 words and 100 characters, below 1024 bytes.',
                         '写500个字和100个字,少于1024个字节。'), '写500个单词和100个字,少于1024个字节。')
        self.assertEqual(preserve_word_count('Write 500 words.', '500个字节和500个字符。'),
                         '500个字节和500个字符。')


if __name__ == '__main__':
    unittest.main()
