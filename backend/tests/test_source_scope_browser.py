import json,os,subprocess
from unittest import skipUnless
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client,override_settings
from core.models import Project,Membership,Source,Comment,Prediction,Job
from experiments.models import ModelRun
from integrations.models import ProviderConnection
from studio.services.projects import ensure
from studio.services.collaboration import start_run
from tests.model_fixture import local_model_fixture


@skipUnless(os.environ.get('ANNOTAFLOW_PLAYWRIGHT_MODULE'),'Playwright is optional.')
@override_settings(DEBUG=True,ALLOWED_HOSTS=['localhost','127.0.0.1','testserver'],SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False)
class SourceScopeBrowserTests(StaticLiveServerTestCase):
    def test_video_selection_is_preserved_across_annotation_routes(self):
        with local_model_fixture() as (path,report),patch('core.services.jobs.dispatch'):
            user=User.objects.create_user(username='source-browser')
            project=Project.objects.create(name='Video scope browser fixture',owner=user)
            Membership.objects.create(project=project,user=user,role='manager');prefs=ensure(project)
            model=ModelRun.objects.create(project=project,name='Synthetic local',artifact_path=str(path),report=json.dumps(report));prefs.active_model=model;prefs.save()
            sources=[Source.objects.create(project=project,name='Video '+name,kind='youtube',external_id='fixture-'+name) for name in ('A','B','C','D')]
            comments=[]
            for source,count in zip(sources,(2,2,1,1)):
                comments.extend(Comment.objects.create(project=project,source=source,text=f'[{source.name}-{i+1}] bình luận tổng hợp') for i in range(count))
            mixed=start_run(project,user,{'model_id':None,'connection_id':None,'comment_ids':[c.pk for c in comments[:4]]})
            only_b=start_run(project,user,{'model_id':None,'connection_id':None,'source_id':sources[1].pk})
            for run in (mixed,only_b):
                for pair in run.pairs.all():
                    pair.local_prediction=Prediction.objects.create(comment=pair.comment,provider='local',model_version='mock',label='NON_TOXIC')
                    pair.api_prediction=Prediction.objects.create(comment=pair.comment,provider='api',model_version='mock',label='NON_TOXIC')
                    pair.branches={'local':{'state':'complete'},'api':{'state':'complete'}};pair.save()
            connection=ProviderConnection.objects.create(project=project,name='Mock API',kind='openai_compatible',model='mock',base_url='https://api.openai.com/v1')
            interrupted=start_run(project,user,{'model_id':model.pk,'connection_id':connection.pk,'source_id':sources[3].pk})
            Job.objects.filter(pk__in=[interrupted.local_job_id,interrupted.llm_job_id]).update(status='failed')
            client=Client();client.force_login(user)
            fixture={'project':project.pk,'sources':[s.pk for s in sources],'comments':[c.pk for c in comments],'mixed':mixed.pk,'only_b':only_b.pk,'interrupted':interrupted.pk}
            env={**os.environ,'ANNOTAFLOW_SOURCE_FIXTURE':json.dumps(fixture),'ANNOTAFLOW_SOURCE_SESSION':client.cookies['sessionid'].value}
            result=subprocess.run(['node',str(settings.ROOT_DIR/'scripts/browser_source_scope.mjs'),self.live_server_url],env=env,capture_output=True,text=True,encoding='utf-8',timeout=150)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
            self.assertIn('SOURCE_SCOPE_BROWSER_OK',result.stdout)
