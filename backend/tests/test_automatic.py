import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, SimpleTestCase, override_settings
from django.contrib.auth.models import User
from core.models import Project, Membership, Source, Comment, Job
from core.jobs.runner import execute
from core.jobs.auto_label import run as run_branch
from core.services.transformer_models import artifact_digest
from experiments.models import ModelRun
from integrations.models import ProviderConnection
from integrations.registry import snapshot
from integrations.secrets import encrypt
from studio.models import AutoLabelRun, AutoLabelResult, ProjectLabel
from studio.services.projects import ensure, labels_for
from tests.model_fixture import local_model_fixture


class AutomaticTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='auto-manager')
        self.project = Project.objects.create(name='Automatic', owner=self.user)
        Membership.objects.create(project=self.project, user=self.user, role='manager')
        self.prefs = ensure(self.project)
        self.source = Source.objects.create(project=self.project, name='Source')
        self.comment = Comment.objects.create(project=self.project, source=self.source, text='thank you friend')
        self.fixture = local_model_fixture()
        self.root, self.report = self.fixture.__enter__()
        self.addCleanup(self.fixture.__exit__, None, None, None)
        self.model = ModelRun.objects.create(project=self.project, name='ML', artifact_path=str(self.root), report=json.dumps(self.report))
        self.client.force_login(self.user)

    def post(self, path, **values):
        return self.client.post('/api/studio/auto-label/' + path, json.dumps({'project': self.project.pk, **values}), content_type='application/json')

    def start(self):
        with patch('core.services.jobs.dispatch') as dispatch, self.captureOnCommitCallbacks(execute=True):
            response = self.post('start')
        self.assertEqual(response.status_code, 200, response.content)
        return AutoLabelRun.objects.get(pk=response.json()['id']), dispatch

    def api_connection(self):
        return ProviderConnection.objects.create(project=self.project, name='River', kind='openai_compatible',
            base_url='https://api.river.ai/v1', model='deepseek-ai/DeepSeek-V4.1-Flash')

    def test_without_key_only_local_and_inputs_are_frozen(self):
        self.api_connection()
        run, dispatch = self.start()
        self.assertIsNone(run.llm_job)
        self.assertEqual(dispatch.call_count, 1)
        self.comment.text = 'Changed after launch'; self.comment.save()
        Comment.objects.create(project=self.project, source=self.source, text='New comment')
        run_branch(run.local_job, json.loads(run.local_job.payload))
        result = run.results.get()
        self.assertEqual(result.label, 'NON_TOXIC')
        self.assertEqual(len(run.items), 1)
        self.assertEqual(run.items[0]['text'], 'thank you friend')
        self.assertFalse(self.comment.annotations.exists())

    @override_settings(AI_ALLOWED_HOSTS=['api.river.ai'])
    def test_api_key_dispatches_two_independent_jobs_with_same_labels(self):
        connection = self.api_connection(); connection.encrypted_key = encrypt('test-key'); connection.save()
        run, dispatch = self.start()
        self.assertIsNotNone(run.llm_job)
        self.assertEqual(dispatch.call_count, 2)
        self.assertNotEqual(run.local_job_id, run.llm_job_id)
        with patch('core.jobs.auto_label.api_predict', return_value={'label':'TOXIC','spans':[]}) as predict:
            run_branch(run.llm_job, json.loads(run.llm_job.payload))
        self.assertEqual(predict.call_args.args[1], run.items[0]['text'])
        self.assertEqual(predict.call_args.args[2], run.labels)
        run_branch(run.local_job, json.loads(run.local_job.payload))
        response = self.client.get(f'/api/studio/auto-label/runs/{run.pk}?different=1').json()
        self.assertEqual(response['different_count'], 1)
        self.assertEqual(response['paired_count'], 1)
        self.assertEqual(len(response['rows']), 1)
        self.assertEqual(response['run']['local']['distribution'][0]['count'], 1)
        self.assertGreater(response['run']['llm']['elapsed_ms'], 0)
        self.assertNotIn('test-key', json.dumps(response))

    @override_settings(AI_ALLOWED_HOSTS=['api.river.ai'])
    def test_resume_never_repeats_saved_calls_and_rejects_changed_configuration(self):
        connection = self.api_connection(); connection.encrypted_key=encrypt('key'); connection.save()
        run, _ = self.start()
        with patch('core.jobs.auto_label.api_predict', return_value={'label':'TOXIC','spans':[]}) as predict:
            run_branch(run.llm_job, json.loads(run.llm_job.payload))
            run_branch(run.llm_job, json.loads(run.llm_job.payload))
        self.assertEqual(predict.call_count, 1)
        connection.model='changed';connection.save()
        with self.assertRaisesMessage(ValueError, 'Cấu hình API đã đổi'):
            run_branch(run.llm_job, json.loads(run.llm_job.payload))

    def test_schema_mismatch_and_non_manager_cannot_start(self):
        ProjectLabel.objects.create(project=self.project, key='EXTRA', name='Extra')
        self.assertEqual(self.post('start').status_code, 400)
        user=User.objects.create_user(username='annotator')
        Membership.objects.create(project=self.project,user=user)
        self.client.force_login(user)
        self.assertEqual(self.post('start').status_code, 403)

    def test_partial_results_not_counted_as_disagreements_and_export_safe(self):
        run, _ = self.start()
        AutoLabelResult.objects.create(run=run, branch='local', item_index=0, label='TOXIC')
        result=self.client.get(f'/api/studio/auto-label/runs/{run.pk}?different=1').json()
        self.assertEqual(result['paired_count'],0)
        self.assertEqual(result['different_count'],0)
        self.assertEqual(result['rows'],[])
        run.items[0]['text']='=DANGEROUS()';run.save()
        export=self.client.get(f'/api/studio/auto-label/runs/{run.pk}?download=csv')
        self.assertIn("'=DANGEROUS()",export.content.decode('utf-8-sig'))
        outsider=User.objects.create_user(username='outsider');self.client.force_login(outsider)
        self.assertEqual(self.client.get(f'/api/studio/auto-label/runs/{run.pk}').status_code,404)

    def test_retry_updates_run_job_reference(self):
        run, _ = self.start()
        run.local_job.status='failed';run.local_job.save()
        with patch('core.services.jobs.dispatch'), self.captureOnCommitCallbacks(execute=True):
            response=self.post(f'runs/{run.pk}/control',branch='local',action='retry')
        self.assertEqual(response.status_code,200)
        old=run.local_job_id;run.refresh_from_db()
        self.assertNotEqual(old,run.local_job_id)


class AutomaticWorkerTests(TransactionTestCase):
    @override_settings(AI_ALLOWED_HOSTS=['api.river.ai'])
    def test_api_failure_keeps_local_results_and_local_worker_completes(self):
        user=User.objects.create_user(username='worker')
        project=Project.objects.create(name='Worker test',owner=user)
        Membership.objects.create(project=project,user=user,role='manager')
        ensure(project)
        connection=ProviderConnection.objects.create(project=project,name='API',kind='openai_compatible',
            base_url='https://api.river.ai/v1',model='test',encrypted_key=encrypt('key'))
        with local_model_fixture() as (root, report):
            run=AutoLabelRun.objects.create(project=project,actor=user,labels=labels_for(project),
                items=[{'id':1,'text':'thank you friend','source':'test'}],
                model_config={'id':1,'name':'Test ML','algorithm':'logistic_regression','artifact_path':str(root),
                              'label_keys':report['label_keys'],'artifact_sha256':artifact_digest(root)},
                connection_config=snapshot(connection))
            local=Job.objects.create(project=project,actor=user,kind='auto_label',payload=json.dumps({'run_id':run.pk,'branch':'local'}))
            llm=Job.objects.create(project=project,actor=user,kind='auto_label',payload=json.dumps({'run_id':run.pk,'branch':'llm'}))
            execute(local.pk)
            with patch('core.jobs.auto_label.api_predict',side_effect=ValueError('API test failure')):
                execute(llm.pk)
        local.refresh_from_db();llm.refresh_from_db()
        self.assertEqual(local.status,'complete',local.message)
        self.assertEqual(llm.status,'failed')
        self.assertEqual(run.results.filter(branch='local').count(),1)
        self.assertGreater(local.checkpoint['elapsed_ms'],0)


class ParallelDispatchTests(SimpleTestCase):
    @override_settings(JOB_RUNNER='threads')
    def test_native_jobs_overlap_in_two_threads(self):
        from core.services.jobs import dispatch
        barrier=Barrier(2)
        finished=[]
        def worker(job_id):
            barrier.wait(timeout=5)
            finished.append(job_id)
        with ThreadPoolExecutor(max_workers=2) as pool:
            with patch('core.services.jobs._pool',pool),patch('core.jobs.runner.execute',side_effect=worker):
                dispatch(101)
                dispatch(102)
                pool.shutdown(wait=True)
        self.assertEqual(set(finished),{101,102})
