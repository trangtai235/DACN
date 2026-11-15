import json
from io import StringIO
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase,override_settings
from core.models import Project,Membership,Source,Comment,Prediction,Job
from experiments.models import ModelRun
from integrations.models import ProviderConnection
from studio.models import Annotation,PairDecision,GoldAnnotation,AutoLabelRun,ProjectLabel
from studio.services.projects import ensure
from studio.services.collaboration import start_run,run_branch,pair_state,branch_statuses


class PredictionResumeTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='resume-manager')
        self.reader=User.objects.create_user(username='resume-reader')
        self.project=Project.objects.create(name='Interrupted predictions fixture',owner=self.user)
        for user,role in ((self.user,'manager'),(self.reader,'annotator')):Membership.objects.create(project=self.project,user=user,role=role)
        ensure(self.project)
        self.a=Source.objects.create(project=self.project,name='Video A');self.b=Source.objects.create(project=self.project,name='Video B')
        self.comments=[Comment.objects.create(project=self.project,source=source,text=f'Fixture {i}') for i,source in enumerate((self.a,self.a,self.a,self.b))]
        self.model=ModelRun.objects.create(project=self.project,name='Mock local',artifact_path='fixture-not-used',report=json.dumps({'label_keys':['NON_TOXIC','TOXIC']}))
        self.connection=ProviderConnection.objects.create(project=self.project,name='Mock API',model='mock',kind='openai_compatible',base_url='https://api.openai.com/v1')
        with patch('studio.services.collaboration.artifact_digest',return_value='fixture'):
            self.run=start_run(self.project,self.user,{'model_id':self.model.pk,'connection_id':self.connection.pk})
        Job.objects.filter(pk__in=[self.run.local_job_id,self.run.llm_job_id]).update(status='failed')
        self.client.force_login(self.user)

    def post(self,**payload):
        return self.client.post(f'/api/studio/collaboration/runs/{self.run.pk}/resume',json.dumps({'source_id':self.a.pk,'branches':['local'],**payload}),content_type='application/json')

    def test_job_state_overrides_stale_pending_but_keeps_completed_predictions(self):
        pair=self.run.pairs.select_related('run__local_job','run__llm_job').get(comment=self.comments[0])
        self.assertEqual(pair_state(pair),'interrupted')
        detail=self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}').json()
        self.assertEqual(detail['prediction_status']['local']['state'],'interrupted')
        self.assertTrue(detail['prediction_status']['local']['can_resume'])
        for status,expected in (('queued','queued'),('running','pending'),('complete','partial_error')):
            Job.objects.filter(pk=self.run.local_job_id).update(status=status)
            pair=self.run.pairs.select_related('run__local_job','run__llm_job').get(pk=pair.pk)
            # The other failed branch means a complete-but-missing result cannot look active.
            self.assertEqual(pair_state(pair),expected if status!='complete' else 'interrupted')
        for branch in ('local','api'):
            setattr(pair,branch+'_prediction',Prediction.objects.create(comment=pair.comment,provider=branch,model_version='mock',label='NON_TOXIC'))
            pair.branches[branch]['state']='complete'
        pair.save();self.assertEqual(pair_state(pair),'agreement')

    def test_resume_only_missing_selected_branch_in_selected_video(self):
        p1=self.run.pairs.get(comment=self.comments[0]);p3=self.run.pairs.get(comment=self.comments[2])
        p1.local_prediction=Prediction.objects.create(comment=p1.comment,provider='local',model_version='mock',label='NON_TOXIC')
        p1.branches['local']['state']='complete';p1.save()
        for branch in ('local','api'):
            setattr(p3,branch+'_prediction',Prediction.objects.create(comment=p3.comment,provider=branch,model_version='mock',label='NON_TOXIC'))
            p3.branches[branch]['state']='complete'
        p3.save()
        human=Annotation.objects.create(comment=p3.comment,user=self.user,label=ProjectLabel.objects.get(project=self.project,key='TOXIC'),status='submitted',note='human correction',revision=1)
        original=list(self.run.pairs.values('id','branches','local_prediction_id','api_prediction_id'))
        response=self.post(branches=['api'],request_key='api-explicit',comment_id=p1.comment_id)
        self.assertEqual(response.status_code,200,response.content)
        new=AutoLabelRun.objects.get(pk=response.json()['id'])
        self.assertEqual(set(new.pairs.values_list('comment_id',flat=True)),{c.pk for c in self.comments[:2]})
        self.assertIsNone(new.local_job_id);self.assertIsNotNone(new.llm_job_id)
        copied=new.pairs.get(comment=p1.comment);self.assertEqual(copied.local_prediction_id,p1.local_prediction_id)
        self.assertEqual(copied.branches['local']['source_pair_id'],p1.pk)
        self.assertEqual(original,list(self.run.pairs.values('id','branches','local_prediction_id','api_prediction_id')))
        self.assertFalse(PairDecision.objects.filter(pair__run=new).exists())
        with patch('studio.services.collaboration.api_predict',return_value={'label':'NON_TOXIC','spans':[]}) as predict:
            run_branch(new.llm_job,{'run_id':new.pk,'branch':'api'})
        self.assertEqual(predict.call_count,2)
        self.assertEqual(new.pairs.filter(api_prediction__isnull=False).count(),2)
        human.refresh_from_db();self.assertEqual((human.label.key,human.note,human.revision),('TOXIC','human correction',1))
        self.assertFalse(GoldAnnotation.objects.exists())

    def test_local_is_the_only_requested_job_and_resume_is_idempotent(self):
        count=Job.objects.count()
        first=self.post(request_key='local-only');second=self.post(request_key='local-only')
        self.assertEqual(first.status_code,200);self.assertEqual(first.json()['id'],second.json()['id'])
        new=AutoLabelRun.objects.get(pk=first.json()['id'])
        self.assertIsNotNone(new.local_job_id);self.assertIsNone(new.llm_job_id)
        self.assertEqual(Job.objects.count(),count+1)
        self.assertTrue(all(p.branches['api']['state']=='paused' for p in new.pairs.all()))
        self.assertFalse(Annotation.objects.exists())

    def test_resume_validates_permissions_scope_active_jobs_and_schema(self):
        self.client.force_login(self.reader);self.assertEqual(self.post().status_code,403)
        self.client.force_login(self.user)
        self.assertEqual(self.post(branches=[]).status_code,400)
        self.assertEqual(self.post(source_id='').status_code,400)
        self.assertEqual(self.post(source_id=99999999).status_code,404)
        Job.objects.filter(pk=self.run.local_job_id).update(status='running')
        self.assertEqual(self.post().status_code,400)
        Job.objects.filter(pk=self.run.local_job_id).update(status='failed')
        label=ProjectLabel.objects.get(project=self.project,key='TOXIC');label.description='Changed meaning';label.save()
        self.assertEqual(self.post().status_code,400)

    @override_settings(JOB_RUNNER='threads')
    def test_native_recovery_does_not_leave_a_fake_running_state(self):
        Job.objects.filter(pk=self.run.local_job_id).update(status='running')
        Job.objects.filter(pk=self.run.llm_job_id).update(status='queued')
        call_command('recover_local_jobs',stdout=StringIO())
        pair=self.run.pairs.select_related('run__local_job','run__llm_job').first()
        self.assertEqual(pair.branches['local']['state'],'pending')
        self.assertEqual(pair_state(pair),'interrupted')
        self.assertFalse(any(s['state'] in ('queued','running') for s in branch_statuses(pair).values()))
