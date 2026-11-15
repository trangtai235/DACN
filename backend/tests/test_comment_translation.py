import json
from datetime import timedelta
from unittest.mock import patch
import httpx
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase,SimpleTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from core.models import Project,Membership,Source,Comment,Prediction
from integrations.models import ProviderConnection
from integrations.secrets import encrypt
from integrations.translation import translate
from reviewing.models import ReviewRun,ReviewTask
from studio.models import Annotation,GoldAnnotation,AIExposure,CommentTranslation,PairDecision
from studio.services.adaptation import text_hash
from studio.services.collaboration import start_run
from studio.services.projects import ensure


class CommentTranslationTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='translator')
        self.project=Project.objects.create(name='Translation fixtures',owner=self.user)
        Membership.objects.create(project=self.project,user=self.user,role='manager')
        self.source=Source.objects.create(project=self.project,name='Video A')
        self.other=Source.objects.create(project=self.project,name='Video B')
        self.comment=Comment.objects.create(project=self.project,source=self.source,text='PORISSO QUE ESTÃO MORRENDO NA CHINA 😀')
        self.provider=ProviderConnection.objects.create(project=self.project,name='Mock translator',kind='openai_compatible',base_url='https://api.openai.com/v1',model='mock-translation',encrypted_key=encrypt('synthetic-key'))
        prefs=ensure(self.project);prefs.active_connection=self.provider;prefs.save()
        self.client.force_login(self.user)
        self.url=f'/api/studio/comments/{self.comment.pk}/translation'
        self.payload={'project':self.project.pk,'source_id':self.source.pk,'text_hash':text_hash(self.comment.text,self.comment.context)}

    def post(self,**extra):return self.client.post(self.url,json.dumps({**self.payload,**extra}),content_type='application/json')

    def test_cached_translation_survives_reload_without_changing_labels_or_original(self):
        original=(self.comment.text,self.comment.digest,self.comment.original_text)
        with patch('studio.api.translations.translate',return_value='Vì vậy mà họ đang chết ở Trung Quốc 😀') as translator:
            first=self.post();second=self.post();read=self.client.get(self.url,self.payload)
        self.assertEqual(first.status_code,200,first.content);self.assertTrue(second.json()['cached'])
        self.assertEqual(read.json()['translated_text'],first.json()['translated_text']);self.assertEqual(translator.call_count,1)
        self.assertNotIn('synthetic-key',first.content.decode())
        self.comment.refresh_from_db();self.assertEqual(original,(self.comment.text,self.comment.digest,self.comment.original_text))
        self.assertFalse(Annotation.objects.exists());self.assertFalse(Prediction.objects.exists());self.assertFalse(GoldAnnotation.objects.exists())
        self.assertTrue(AIExposure.objects.filter(comment=self.comment,user=self.user).exists())

    def test_translation_checks_project_scope_text_and_blind_review(self):
        self.assertEqual(self.post(source_id=self.other.pk).status_code,404)
        self.assertEqual(self.post(project=999999).status_code,404)
        self.assertEqual(self.post(text_hash='old-text').status_code,400)
        run=ReviewRun.objects.create(project=self.project)
        ReviewTask.objects.create(run=run,comment=self.comment,reviewer=self.user)
        self.assertEqual(self.post().status_code,403)
        self.assertFalse(CommentTranslation.objects.exists())
        self.client.logout();self.assertEqual(self.post().status_code,401)

    def test_missing_configuration_and_provider_failure_are_retryable(self):
        prefs=ensure(self.project);prefs.active_connection=None;prefs.save()
        self.assertEqual(self.post().status_code,400);self.assertFalse(CommentTranslation.objects.exists())
        prefs.active_connection=self.provider;prefs.save()
        with patch('studio.api.translations.translate',side_effect=ValueError('API timeout')):
            self.assertEqual(self.post().status_code,400)
        self.assertEqual(CommentTranslation.objects.get().status,'failed')
        with patch('studio.api.translations.translate',return_value='Bản dịch thử lại'):
            self.assertEqual(self.post().json()['translated_text'],'Bản dịch thử lại')

    def test_concurrent_or_interrupted_request_does_not_duplicate_api_work(self):
        row=CommentTranslation.objects.create(comment=self.comment,text_hash=text_hash(self.comment.text,''),request_token='other-request')
        with patch('studio.api.translations.translate',return_value='Đã dịch') as translator:
            self.assertEqual(self.post().status_code,202);translator.assert_not_called()
            self.assertEqual(self.client.get(self.url,self.payload).json()['status'],'running')
            CommentTranslation.objects.filter(pk=row.pk).update(updated_at=timezone.now()-timedelta(minutes=3))
            self.assertEqual(self.client.get(self.url,self.payload).json()['status'],'interrupted')
            self.assertEqual(self.post().status_code,200);self.assertEqual(translator.call_count,1)

    def test_text_edited_during_translation_is_not_shown_as_current(self):
        def changed(*args):
            Comment.objects.filter(pk=self.comment.pk).update(text='Changed original')
            return 'Old translation'
        with patch('studio.api.translations.translate',side_effect=changed):self.assertEqual(self.post().status_code,400)
        self.assertEqual(CommentTranslation.objects.get().status,'failed')

    def test_assisted_disagreement_shows_exact_predictions_without_preliminary_or_gold(self):
        run=start_run(self.project,self.user,{'model_id':None,'connection_id':None})
        pair=run.pairs.get()
        pair.local_prediction=Prediction.objects.create(comment=self.comment,provider='local',model_version='mock-local',label='NON_TOXIC')
        pair.api_prediction=Prediction.objects.create(comment=self.comment,provider='api',model_version='mock-api',label='TOXIC')
        pair.branches={'local':{'state':'complete'},'api':{'state':'complete'}};pair.save()
        url=f'/api/studio/collaboration/pairs/{pair.pk}'
        before=self.client.get(url).json();self.assertTrue(before['requires_preliminary']);self.assertIsNone(before['local'])
        response=self.client.post(url+'/expose',json.dumps({'source_id':self.source.pk,'assisted_view':True,'include_workspace':True}),content_type='application/json')
        value=response.json();self.assertEqual(response.status_code,200,response.content)
        self.assertEqual((value['local']['id'],value['api']['id']),(pair.local_prediction_id,pair.api_prediction_id))
        self.assertEqual(value['state'],'disagreement');self.assertFalse(value['requires_preliminary'])
        self.assertEqual(value['mine']['preliminary_label'],'');self.assertEqual(value['mine']['status'],'draft')
        self.assertFalse(Annotation.objects.exists());self.assertFalse(GoldAnnotation.objects.exists())
        self.assertTrue(AIExposure.objects.filter(comment=self.comment,user=self.user).exists())
        blind=ReviewRun.objects.create(project=self.project)
        ReviewTask.objects.create(run=blind,comment=self.comment,reviewer=self.user)
        self.assertEqual(self.client.post(url+'/expose',json.dumps({'assisted_view':True}),content_type='application/json').status_code,403)

    def test_queue_queries_do_not_grow_per_comment(self):
        small=start_run(self.project,self.user,{'model_id':None,'connection_id':None})
        with CaptureQueriesContext(connection) as before:
            self.assertEqual(self.client.get(f'/api/studio/collaboration/runs/{small.pk}').status_code,200)
        Comment.objects.bulk_create([Comment(project=self.project,source=self.source,text=f'Fixture {i}',digest=f'{i:064x}') for i in range(40)])
        large=start_run(self.project,self.user,{'model_id':None,'connection_id':None})
        with CaptureQueriesContext(connection) as after:
            response=self.client.get(f'/api/studio/collaboration/runs/{large.pk}')
        self.assertEqual(len(response.json()['rows']),41)
        self.assertLessEqual(len(after),len(before)+2,f'Queue queries grew from {len(before)} to {len(after)}')
        print(f'QUEUE_QUERY_COUNTS synthetic: 1 sample={len(before)}, 41 samples={len(after)}')


class TranslationAdapterTests(SimpleTestCase):
    def test_provider_protocols_and_json_translation(self):
        responses={
            'openai_compatible':{'choices':[{'message':{'content':'{"translated_text":"Xin chào 😀"}'}}]},
            'gemini':{'candidates':[{'content':{'parts':[{'text':'{"translated_text":"Xin chào 😀"}'}]}}]},
            'ollama':{'message':{'content':'{"translated_text":"Xin chào 😀"}'}}}
        for kind,value in responses.items():
            seen=[]
            def handler(request):
                seen.append(json.loads(request.content))
                return httpx.Response(200,json=value,request=request)
            provider=ProviderConnection(kind=kind,base_url='https://api.openai.com/v1',model='mock',encrypted_key=encrypt('synthetic-key'),enabled=True)
            with self.subTest(kind=kind),patch('integrations.translation.public_client',return_value=httpx.Client(transport=httpx.MockTransport(handler))):
                self.assertEqual(translate(provider,'Hello 😀'),'Xin chào 😀')
                self.assertEqual(len(seen),1);self.assertNotIn('label',json.dumps(seen[0]))

    def test_invalid_translation_and_missing_key_do_not_fabricate_a_result(self):
        provider=ProviderConnection(kind='openai_compatible',base_url='https://api.openai.com/v1',model='mock',encrypted_key=encrypt('synthetic-key'),enabled=True)
        for content in ('not JSON','{}','{"translated_text":""}'):
            client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'choices':[{'message':{'content':content}}]},request=req)))
            with patch('integrations.translation.public_client',return_value=client),self.assertRaises(ValueError):translate(provider,'Hello')
        provider.encrypted_key=''
        with self.assertRaises(ValueError):translate(provider,'Hello')
