import json
import socket
from unittest.mock import patch
import httpx
from django.test import TestCase,SimpleTestCase
from django.contrib.auth.models import User
from core.models import Project,Membership,Source,Comment,Job
from studio.models import ProjectSettings,DatasetVersion,Annotation,GoldAnnotation
from studio.services.projects import ensure
from integrations.models import ProviderConnection
from integrations.secrets import decrypt,encrypt
from integrations.secure_http import public_endpoint,public_addresses,PublicTransport
from integrations.provider_settings import probe,signature
from integrations.providers.base import parse_result,prompt


class ProviderSettingsTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='owner')
        self.project=Project.objects.create(name='Delete me',owner=self.user)
        Membership.objects.create(project=self.project,user=self.user,role='manager')
        ensure(self.project)
        self.client.force_login(self.user)
        self.body={'project':self.project.pk,'name':'River','kind':'openai_compatible',
                   'base_url':'https://api.river.ai/v1','model':'model-a','model_ids':['model-a','model-b'],
                   'enabled':True,'api_key':'private-test-key'}
    def post(self,path,body):
        return self.client.post('/api/studio/'+path,json.dumps(body),content_type='application/json')
    def create(self):
        response=self.post('connections/save',self.body)
        self.assertEqual(response.status_code,200,response.content)
        return ProviderConnection.objects.get(pk=response.json()['connection']['id'])
    def mock_client(self,status=200,data=None):
        client=httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(status,json=data or {},request=request)))
        return patch('integrations.provider_settings.public_client',return_value=client)
    def test_persist_key_blank_preserves_and_export_contains_no_secrets(self):
        c=self.create()
        self.assertNotEqual(c.encrypted_key,self.body['api_key'])
        self.assertEqual(decrypt(c.encrypted_key),self.body['api_key'])
        result=self.post('connections/save',{**self.body,'id':c.pk,'api_key':'','make_default':True})
        self.assertEqual(result.status_code,200)
        c.refresh_from_db();self.assertEqual(decrypt(c.encrypted_key),self.body['api_key'])
        self.assertEqual(ensure(self.project).active_connection_id,c.pk)
        for url in ['connections','connections/configuration','connections/configuration?download=1']:
            response=self.client.get('/api/studio/'+url,{'project':self.project.pk})
            self.assertEqual(response.status_code,200)
            self.assertNotIn(self.body['api_key'],response.content.decode())
            self.assertNotIn(c.encrypted_key,response.content.decode())
            self.assertNotIn('encrypted_key',response.content.decode())
    def test_validation_schema_key_and_default_model(self):
        for update in [{'name':''},{'base_url':'http://api.river.ai/v1'},{'base_url':'https://127.0.0.1/v1'},
                       {'api_key':''},{'model_ids':[]},{'model':'not-in-list'},{'enabled':'false'},
                       {'base_url':'https://api.river.ai/v1?key=hidden'},{'kind':'ollama','base_url':'http://127.0.0.1:11434'}]:
            response=self.post('connections/save',{**self.body,**update})
            self.assertEqual(response.status_code,400,update)
        self.assertFalse(self.project.connections.exists())
    def test_builtin_cannot_be_deleted_but_can_be_disabled(self):
        response=self.client.get('/api/studio/connections',{'project':self.project.pk})
        c=self.project.connections.get(builtin_key='deepseek')
        self.assertTrue(response.json()['connections'][0]['is_builtin'])
        self.assertEqual(self.post('connections/delete',{'project':self.project.pk,'id':c.pk,'confirm':c.name}).status_code,403)
        result=self.post('connections/save',{'project':self.project.pk,'id':c.pk,'enabled':False})
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(result.json()['connection']['check_status'],'unknown')
    def test_check_only_get_models_and_persist_status_without_changing_run_identity(self):
        c=self.create();before=c.updated_at;seen=[]
        def handler(request):
            seen.append((request.method,str(request.url)))
            self.assertEqual(request.headers['Authorization'],'Bearer private-test-key')
            return httpx.Response(200,json={'data':[{'id':'model-a'},{'id':'model-b'}]})
        with patch('integrations.provider_settings.public_client',return_value=httpx.Client(transport=httpx.MockTransport(handler))):
            response=self.post('connections/test',{'project':self.project.pk,'id':c.pk})
        self.assertEqual(response.json()['check']['status'],'success')
        self.assertEqual(seen,[('GET','https://api.river.ai/v1/models')])
        c.refresh_from_db();self.assertEqual(c.check_status,'success');self.assertEqual(c.updated_at,before)
        with self.mock_client(200,{'data':[{'id':'different-model'}]}):
            response=self.post('connections/test',{'project':self.project.pk,'id':c.pk})
        self.assertEqual(response.json()['check']['code'],'model_not_found')
    def test_check_errors_and_no_completion_fallback(self):
        c=self.create()
        for code,expected,status in [(401,'invalid_key','failed'),(403,'invalid_key','failed'),(429,'rate_limit','failed'),
                                     (404,'unsupported','unknown'),(302,'redirect_blocked','failed')]:
            with self.mock_client(code):result=probe(c,'key')
            self.assertEqual(result['code'],expected);self.assertEqual(result['status'],status)
        with patch('integrations.provider_settings.public_client',side_effect=httpx.ReadTimeout('private-test-key')):
            result=probe(c,'key')
        self.assertEqual(result['code'],'timeout');self.assertNotIn('private-test-key',json.dumps(result))
    def test_draft_test_save_proof_and_changed_key_resets_status(self):
        with self.mock_client(200,{'data':[{'id':'model-a'}]}):
            response=self.post('connections/test',self.body)
        self.assertFalse(self.project.connections.exists())
        token=response.json()['test_token']
        response=self.post('connections/save',{**self.body,'test_token':token})
        c=self.project.connections.get();self.assertEqual(c.check_status,'success')
        response=self.post('connections/save',{**self.body,'id':c.pk,'api_key':'new-key','test_token':token})
        self.assertEqual(response.json()['connection']['check_status'],'unknown')
    def test_custom_delete_confirmation_and_running_task(self):
        c=self.create()
        self.assertEqual(self.post('connections/delete',{'project':self.project.pk,'id':c.pk,'confirm':'wrong'}).status_code,400)
        job=Job.objects.create(project=self.project,actor=self.user,kind='auto_label')
        body={'project':self.project.pk,'id':c.pk,'confirm':c.name}
        self.assertEqual(self.post('connections/delete',body).status_code,400)
        job.delete();self.assertEqual(self.post('connections/delete',body).status_code,200)
        self.assertFalse(ProviderConnection.objects.filter(pk=c.pk).exists())
    def test_only_managers_can_access_settings_and_export(self):
        c=self.create()
        member=User.objects.create_user(username='member');Membership.objects.create(project=self.project,user=member)
        self.client.force_login(member)
        for url in ['connections','connections/configuration']:
            self.assertEqual(self.client.get('/api/studio/'+url,{'project':self.project.pk}).status_code,403)
        for path,body in [('connections/save',self.body),('connections/test',{'project':self.project.pk,'id':c.pk}),
                          ('connections/delete',{'project':self.project.pk,'id':c.pk,'confirm':c.name})]:
            self.assertEqual(self.post(path,body).status_code,403)
    def test_project_delete_requires_owner_confirmation_and_preserves_other_project(self):
        source=Source.objects.create(project=self.project,name='source')
        comment=Comment.objects.create(project=self.project,source=source,text='Delete comment')
        from reviewing.models import ReviewRun,ReviewTask
        run=ReviewRun.objects.create(project=self.project)
        ReviewTask.objects.create(run=run,comment=comment,reviewer=self.user)
        first=DatasetVersion.objects.create(project=self.project,name='first',snapshot={},sha256='a',created_by=self.user)
        DatasetVersion.objects.create(project=self.project,name='restored',snapshot={},sha256='b',created_by=self.user,restored_from=first)
        other=Project.objects.create(name='Keep',owner=self.user)
        self.create()
        manager=User.objects.create_user(username='manager');Membership.objects.create(project=self.project,user=manager,role='manager')
        body={'project':self.project.pk,'action':'delete','confirm':self.project.name}
        self.client.force_login(manager);self.assertEqual(self.post('project-settings',body).status_code,403)
        self.client.force_login(self.user)
        self.assertEqual(self.post('project-settings',{**body,'confirm':'wrong'}).status_code,403)
        job=Job.objects.create(project=self.project,actor=self.user,kind='auto_label')
        self.assertEqual(self.post('project-settings',body).status_code,400)
        job.delete();result=self.post('project-settings',body)
        self.assertEqual(result.status_code,200,result.content)
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())
        self.assertTrue(Project.objects.filter(pk=other.pk).exists())


class NetworkAndSentenceTests(SimpleTestCase):
    def test_private_and_metadata_urls_rejected(self):
        for url in ['http://api.river.ai/v1','https://169.254.169.254/latest','https://127.0.0.1/v1',
                    'https://[::1]/v1','https://10.0.0.1/v1','https://metadata.google.internal/v1',
                    'https://user:password@api.river.ai/v1','https://api.river.ai:8443/v1',
                    'https://api.river.ai/v1#x','https://localhost/v1','https://api.river.ai/../metadata']:
            with self.assertRaises(ValueError,msg=url):public_endpoint(url)
    def test_mixed_dns_blocks_request_and_public_transport_pins_ip_and_tls_name(self):
        mixed=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443)),(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]
        with patch('integrations.secure_http.socket.getaddrinfo',return_value=mixed):
            with self.assertRaises(ValueError):public_addresses('api.river.ai')
        with patch('integrations.secure_http.public_addresses',return_value=['93.184.216.34']),patch('httpx.HTTPTransport.handle_request',return_value=httpx.Response(200)) as send:
            transport=PublicTransport()
            request=httpx.Request('GET','https://api.river.ai/v1/models')
            transport.handle_request(request)
            pinned=send.call_args.args[0]
            self.assertEqual(pinned.url.host,'93.184.216.34')
            self.assertEqual(pinned.headers['Host'],'api.river.ai')
            self.assertEqual(pinned.extensions['sni_hostname'],'api.river.ai')
            transport.close()
    def test_sentence_only_accepts_label_without_offsets_but_span_mode_still_validates(self):
        labels=[{'key':'TOXIC','name':'Độc hại'}]
        value={'label':'TOXIC','spans':[{'start':999,'end':1000,'label':'TOXIC'}]}
        self.assertEqual(parse_result(value,'text',labels,sentence_only=True),{'label':'TOXIC','spans':[]})
        with self.assertRaises(ValueError):parse_result(value,'text',labels)
        with self.assertRaises(ValueError):parse_result({'label':'BAD'},'text',labels,sentence_only=True)
        self.assertIn('Không trả spans',prompt('text',labels,sentence_only=True))
