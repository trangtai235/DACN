import json,os,subprocess
from unittest import skipUnless
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import TestCase,Client,override_settings
from django.test.utils import CaptureQueriesContext
from core.models import Project,Membership,Source,Comment
from experiments.models import ModelRun,BenchmarkRun
from reviewing.models import ReviewRun,ReviewTask
from studio.models import AIExposure,Annotation,ProjectLabel
from studio.services.projects import ensure


class CompactBootstrapTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='startup-manager')
        self.project=Project.objects.create(name='Startup fixture',owner=self.user)
        Membership.objects.create(project=self.project,user=self.user,role='manager')
        ensure(self.project)
        self.source=Source.objects.create(project=self.project,name='One source')
        self.comment=Comment.objects.create(project=self.project,source=self.source,text='Private original comment',ai_label='TOXIC')
        self.model=ModelRun.objects.create(project=self.project,name='Model metadata',artifact_path='unused',report=json.dumps({'test':{'n':1},'large_payload':'x'*100000}))
        self.client.force_login(self.user)

    def compact(self):return self.client.get('/api/bootstrap',{'project':self.project.pk,'compact':1})

    def test_compact_bootstrap_omits_heavy_data_and_does_not_record_exposure(self):
        response=self.compact();value=response.json()
        self.assertEqual(response.status_code,200);self.assertEqual(value['bootstrap_mode'],'compact')
        self.assertEqual(value['comments'],[]);self.assertEqual(value['versions'],[])
        self.assertNotIn('report',value['models'][0]);self.assertNotIn('Private original comment',response.content.decode())
        self.assertLess(len(response.content),10000)
        self.assertEqual(value['sources'][0]['count'],1)
        self.assertFalse(AIExposure.objects.exists())
        label=ProjectLabel.objects.get(project=self.project,key='TOXIC')
        Annotation.objects.create(comment=self.comment,user=self.user,label=label)
        value=self.compact().json()
        self.assertEqual(value['annotation_stats']['annotations'],1)
        self.assertEqual(value['annotation_stats']['annotated_comments'],1)
        self.assertEqual(value['my_annotations'],1)

    def test_source_comment_and_project_counts_do_not_add_queries_per_row(self):
        with CaptureQueriesContext(connection) as small:self.compact()
        for i in range(50):
            source=Source.objects.create(project=self.project,name=f'Source {i}')
            Comment.objects.create(project=self.project,source=source,text=f'Comment {i}',ai_label='NON_TOXIC')
        with CaptureQueriesContext(connection) as large:response=self.compact()
        self.assertEqual(response.json()['stats']['total'],51)
        self.assertEqual(len(response.json()['sources']),51)
        self.assertLessEqual(len(large),len(small)+1)
        self.assertFalse(AIExposure.objects.exists())
        print(f'COMPACT_BOOTSTRAP_QUERIES synthetic: 1 source={len(small)}, 51 sources={len(large)}')

    def test_reports_load_separately_with_permissions_and_blind_rules(self):
        BenchmarkRun.objects.create(project=self.project,provider='mock',report='{"mock":true}')
        url='/api/model-reports'
        value=self.client.get(url,{'project':self.project.pk}).json()
        self.assertEqual(value['models'][0]['report']['test']['n'],1)
        self.assertEqual(len(value['benchmarks']),1)
        self.assertEqual(self.client.get(url,{'project':999999}).status_code,404)
        blind=ReviewRun.objects.create(project=self.project)
        ReviewTask.objects.create(run=blind,comment=self.comment,reviewer=self.user)
        self.assertEqual(self.compact().json()['models'],[])
        self.assertEqual(self.client.get(url,{'project':self.project.pk}).json(),{'models':[],'benchmarks':[]})

    def test_empty_account_and_legacy_bootstrap_remain_compatible(self):
        legacy=self.client.get('/api/bootstrap',{'project':self.project.pk}).json()
        self.assertEqual(legacy['comments'][0]['text'],self.comment.text)
        self.assertIn('report',legacy['models'][0])
        user=User.objects.create_user(username='empty-startup');self.client.force_login(user)
        self.assertEqual(self.compact().status_code,404)
        self.assertIsNone(self.client.get('/api/bootstrap',{'compact':1}).json()['project'])


@skipUnless(os.environ.get('ANNOTAFLOW_PLAYWRIGHT_MODULE'),'Playwright is optional.')
@override_settings(DEBUG=True,ALLOWED_HOSTS=['localhost','127.0.0.1','testserver'],SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False)
class StartupBrowserTests(StaticLiveServerTestCase):
    def test_lazy_loading_fast_navigation_and_error_recovery(self):
        user=User.objects.create_user(username='startup-browser')
        project=Project.objects.create(name='Startup browser fixture',owner=user)
        Membership.objects.create(project=project,user=user,role='manager');ensure(project)
        client=Client();client.force_login(user)
        env={**os.environ,'ANNOTAFLOW_STARTUP_SESSION':client.cookies['sessionid'].value,'ANNOTAFLOW_STARTUP_PROJECT':str(project.pk)}
        result=subprocess.run(['node',str(settings.ROOT_DIR/'scripts/browser_startup.mjs'),self.live_server_url],env=env,capture_output=True,text=True,encoding='utf-8',timeout=120)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        self.assertIn('STARTUP_BROWSER_OK',result.stdout)
