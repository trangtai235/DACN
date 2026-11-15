import json,os,subprocess
from pathlib import Path
from unittest import skipUnless
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client,override_settings
from core.models import Project,Membership,Source,Comment,Prediction
from experiments.models import ModelRun
from studio.models import ProjectLabel
from studio.services.projects import ensure
from studio.services.collaboration import start_run


@skipUnless(os.environ.get('ANNOTAFLOW_PLAYWRIGHT_MODULE'),'Set ANNOTAFLOW_PLAYWRIGHT_MODULE for browser tests.')
@override_settings(DEBUG=True,ALLOWED_HOSTS=['localhost','127.0.0.1','testserver'],SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False)
class LabelManagementBrowserTests(StaticLiveServerTestCase):
    def test_label_crud_reload_drafts_permissions_and_responsive(self):
        users={role:User.objects.create_user(username='label-browser-'+role) for role in ('owner','reader','other')}
        project=Project.objects.create(name='Dự án quản lý nhãn thật',owner=users['owner'],is_demo=True)
        for role in ('owner','reader'):Membership.objects.create(project=project,user=users[role],role='manager' if role=='owner' else 'annotator')
        prefs=ensure(project)
        model=ModelRun.objects.create(project=project,name='Binary metadata fixture',artifact_path='unused-no-inference',report=json.dumps({'label_keys':['NON_TOXIC','TOXIC']}))
        prefs.active_model=model;prefs.save()
        source=Source.objects.create(project=project,name='Nguồn nháp')
        manual=Comment.objects.create(project=project,source=source,text='Giữ bình luận 😀 có spans và bản nháp')
        paired=Comment.objects.create(project=project,source=source,text='Bình luận phối hợp giữ bản nháp')
        batch=start_run(project,users['owner'],{'model_id':None,'connection_id':None,'comment_ids':[paired.pk]})
        pair=batch.pairs.get()
        pair.local_prediction=Prediction.objects.create(comment=paired,provider='local',model_version='fixture',label='TOXIC')
        pair.api_prediction=Prediction.objects.create(comment=paired,provider='api',model_version='fixture',label='NON_TOXIC')
        pair.branches={'local':{'state':'complete'},'api':{'state':'complete'}};pair.save()
        other_project=Project.objects.create(name='Dự án khác',owner=users['other'])
        Membership.objects.create(project=other_project,user=users['other'],role='manager');ensure(other_project)
        ProjectLabel.objects.create(project=other_project,key='FEEDBACK',name='Nhãn riêng dự án khác')
        sessions={}
        for role,user in users.items():
            client=Client();client.force_login(user);sessions[role]=client.cookies['sessionid'].value
        env={**os.environ,'ANNOTAFLOW_BROWSER_SESSIONS':json.dumps(sessions),
             'ANNOTAFLOW_LABEL_FIXTURE':json.dumps({'project':project.pk,'other_project':other_project.pk,'manual':manual.pk,'pair':pair.pk})}
        result=subprocess.run(['node',str(settings.ROOT_DIR/'scripts/browser_label_management.mjs'),self.live_server_url],env=env,
                              capture_output=True,text=True,encoding='utf-8',timeout=150)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
        self.assertIn('LABEL_MANAGEMENT_BROWSER_OK',result.stdout)
