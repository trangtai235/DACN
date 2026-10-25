import re
from django.test import SimpleTestCase
from core.services.transformer_models import bio_spans

class BIOTests(SimpleTestCase):
    def test_unicode_whitespace_and_phrase_boundaries(self):
        text='🙂 bạn\n  ngu quá đồ tồi'
        words=list(re.finditer(r'\S+',text))
        spans=bio_spans(words,['O','O','B-T','I-T','B-T','I-T'])
        self.assertEqual([text[s['start']:s['end']] for s in spans],['ngu quá','đồ tồi'])
    def test_orphan_inside_starts_span(self):
        text='bad fine worse'
        spans=bio_spans(list(re.finditer(r'\S+',text)),['I-T','O','I-T'])
        self.assertEqual([text[s['start']:s['end']] for s in spans],['bad','worse'])
    def test_clean_and_empty(self):
        self.assertEqual(bio_spans([],[]),[])
        self.assertEqual(bio_spans(list(re.finditer(r'\S+','hello')),['O']),[])
