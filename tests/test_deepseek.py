import json
import threading
import unittest
import httpx
from deepseek_translation import DeepSeekTranslator, TranslationError, ENDPOINT


class DeepSeekTests(unittest.TestCase):
    def service(self, handler):
        return DeepSeekTranslator('test-placeholder', httpx.Client(transport=httpx.MockTransport(handler)))

    def test_current_text_and_bounded_context_are_text_only(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '测试译文'}}]})
        t = self.service(handler)
        for i in range(6):
            t.translate(f'{i} ' + 'a' * 700)
        body = json.loads(requests[-1].content)
        data = json.loads(body['messages'][1]['content'])
        self.assertLessEqual(len(data['previous_source_context']), 1400)
        self.assertTrue(data['current_source'].startswith('5 '))
        self.assertNotIn('audio', body)
        self.assertEqual(body['thinking'], {'type': 'disabled'})
        self.assertEqual(str(requests[-1].url), ENDPOINT)

    def test_auth_failure_is_redacted_and_blocks_repeated_requests(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(401, text='sensitive response text and test-placeholder')
        t = self.service(handler)
        for _ in range(2):
            with self.assertRaises(TranslationError) as error:
                t.translate('hello')
            self.assertNotIn('test-placeholder', str(error.exception))
            self.assertNotIn('sensitive', str(error.exception))
        self.assertEqual(len(calls), 1)

    def test_cancelled_session_makes_no_network_request(self):
        calls = []
        t = self.service(lambda request: calls.append(request))
        stop = threading.Event()
        stop.set()
        self.assertEqual(t.translate('hello', stop), '')
        self.assertEqual(calls, [])

    def test_truncated_translation_is_not_presented_as_complete(self):
        t = self.service(lambda request: httpx.Response(200, json={'choices': [
            {'finish_reason': 'length', 'message': {'content': '不完整'}}]}))
        with self.assertRaises(TranslationError):
            t.translate('hello')

    def test_timeout_has_actionable_redacted_error(self):
        def handler(request):
            raise httpx.ReadTimeout('test-placeholder')
        t = self.service(handler)
        with self.assertRaisesRegex(TranslationError, '超时'):
            t.translate('hello')

    def test_redirect_is_not_accepted_as_translation(self):
        t = self.service(lambda request: httpx.Response(302, headers={'Location': 'https://example.com/'}))
        with self.assertRaises(TranslationError):
            t.translate('hello')


if __name__ == '__main__':
    unittest.main()
