import json
from types import SimpleNamespace
from unittest.mock import patch
from django.http import Http404
from django.test import SimpleTestCase, RequestFactory
from core.api.common import api


class APIErrorTests(SimpleTestCase):
    def request(self):
        request=RequestFactory().post('/api/studio/collaboration/pairs/1/decision')
        request.user=SimpleNamespace(is_authenticated=True)
        return request

    def test_unexpected_error_is_logged_and_returns_safe_json(self):
        @api
        def failing(request):
            raise RuntimeError('private database diagnostic')

        with patch('core.api.common.logger.exception') as log:
            response=failing(self.request())
        self.assertEqual(response.status_code,500)
        self.assertEqual(response['Content-Type'],'application/json')
        body=json.loads(response.content)
        self.assertEqual(body['code'],'internal_error')
        self.assertNotIn('private database diagnostic',response.content.decode())
        log.assert_called_once()

    def test_missing_record_returns_json_404(self):
        @api
        def missing(request):
            raise Http404('private record details')

        response=missing(self.request())
        self.assertEqual(response.status_code,404)
        self.assertIn('error',json.loads(response.content))
        self.assertNotIn('private record details',response.content.decode())
