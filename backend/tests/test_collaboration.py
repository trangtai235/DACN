"""M1–M3 integration tests. Synthetic outcomes are fixtures, never study results."""
import json
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from core.models import Project, Membership, Source, Comment, Prediction, Job
from experiments.models import ModelRun, ReferenceLabel
from integrations.models import ProviderConnection
from studio.models import (AutoLabelRun, ProjectLabel, Annotation, GoldAnnotation, AIExposure, PairDecision,
                           FeedbackApproval, DataPartition, FeedbackDataset)
from studio.services.projects import ensure
from studio.services.adaptation import (current_schema, compatibility, retrieve, text_hash, freeze_dataset,
                                        eligible_feedback)
from studio.services.collaboration import start_run, run_branch, pair_state, decision
from reviewing.models import ReviewTask, ReviewRun
from reviewing import paired


class CollaborationTests(TestCase):
    def setUp(self):
        self.users = [User.objects.create_user(username='paired-' + str(i)) for i in range(3)]
        self.owner, self.reviewer, self.judge = self.users
        self.project = Project.objects.create(name='M1–M3 fixtures', owner=self.owner, is_demo=True)
        for user in self.users: Membership.objects.create(project=self.project, user=user, role='manager' if user != self.reviewer else 'annotator')
        ensure(self.project)
        self.source = Source.objects.create(project=self.project, name='Video fixture')
        self.comment = Comment.objects.create(project=self.project, source=self.source, text='thank you friend')
        self.model = ModelRun.objects.create(project=self.project, name='Mock local', artifact_path='unused', report=json.dumps({'label_keys': ['NON_TOXIC', 'TOXIC']}))
        self.connection = ProviderConnection.objects.create(project=self.project, name='Mock remote', model='fixture', kind='openai_compatible', base_url='https://api.openai.com/v1')
        self.client.force_login(self.owner)

    def post(self, path, **payload):
        return self.client.post('/api/' + path, json.dumps(payload), content_type='application/json')

    def batch(self, **extra):
        with patch('studio.services.collaboration.artifact_digest', return_value='fixed-digest'):
            return start_run(self.project, self.owner, {'model_id': self.model.pk, 'connection_id': self.connection.pk, **extra})

    def execute(self, batch, order=('local', 'api'), local='NON_TOXIC', api='TOXIC'):
        with patch('studio.services.collaboration.artifact_digest', return_value='fixed-digest'), \
             patch('studio.services.collaboration.artifact_signature', return_value=()), \
             patch('studio.services.collaboration.local_predict', return_value=[{'label': local, 'spans': [], 'model_version': 'fixture'}]), \
             patch('studio.services.collaboration.api_predict', return_value={'label': api, 'spans': []}):
            for branch in order:
                run_branch(batch.local_job if branch == 'local' else batch.llm_job, {'run_id': batch.pk, 'branch': branch})
        return batch.pairs.get(comment=self.comment)

    def confirm(self, pair, user=None, label='NON_TOXIC'):
        user = user or self.owner
        if pair_state(pair) == 'disagreement':
            d = decision(pair.id, user, {'action': 'preliminary', 'label': label})
            return decision(pair.id, user, {'action': 'confirm', 'label': label, 'revision': d.revision})
        return decision(pair.id, user, {'action': 'confirm', 'label': label})

    def approve_feedback(self, comment, schema, label):
        batch = self.batch(comment_ids=[comment.pk], model_id=None, connection_id=None)
        d = decision(batch.pairs.get().pk, self.owner, {'action': 'confirm', 'label': label})
        return FeedbackApproval.objects.create(comment=comment, schema=schema, decision=d, decision_revision=d.revision,label=label, text=comment.text,
            text_hash=text_hash(comment.text, comment.context), source_id_snapshot=comment.source_id, approved_by=self.owner)

    def test_comment_workspace_metadata_and_unicode_tokens(self):
        self.comment.text='😀 cảm ơn'; self.comment.author='@nguoi-dung'; self.comment.external_id='comment-1'; self.comment.save()
        self.source.kind='youtube'; self.source.external_id='video-1'; self.source.save()
        pair=self.execute(self.batch(), local='NON_TOXIC', api='NON_TOXIC')
        value=self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}').json()
        self.assertEqual(value['comment_id'], self.comment.pk)
        self.assertEqual(value['source'], self.source.name)
        self.assertEqual(value['source_kind'], 'youtube')
        self.assertEqual(value['video_id'], 'video-1')
        self.assertEqual(value['author'], '@nguoi-dung')
        self.assertEqual(value['tokens'], [{'text':'😀','start':0,'end':1},{'text':'cảm','start':2,'end':5},{'text':'ơn','start':6,'end':8}])
        self.assertFalse(value['revealed']); self.assertIsNone(value['local'])
        self.assertEqual(self.post(f'studio/collaboration/pairs/{pair.pk}/expose').status_code,200)
        exposed=self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}').json()
        self.assertEqual(exposed['local']['label'], exposed['api']['label'])
        self.assertTrue(AIExposure.objects.filter(comment=self.comment,user=self.owner).exists())
        self.assertFalse(Annotation.objects.filter(comment=self.comment).exists())
        self.assertFalse(GoldAnnotation.objects.filter(comment=self.comment).exists())
        self.assertEqual(Prediction.objects.count(),2)

    def test_save_with_nullable_legacy_run_schema_returns_json(self):
        # The schema FK stays nullable for legacy runs. PostgreSQL rejects a
        # blanket FOR UPDATE across that outer join even on a versioned run.
        legacy=AutoLabelRun.objects.create(project=self.project,actor=self.owner,schema=None)
        pair=self.batch(model_id=None,connection_id=None).pairs.get()
        detail=self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}').json()
        self.assertEqual(detail['workspace_version'],1)
        response=self.post(f'studio/collaboration/pairs/{pair.pk}/decision',action='confirm',
            label='NON_TOXIC',revision=detail['mine']['revision'],annotation_revision=detail['annotation_revision'],spans=[])
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'application/json')
        self.assertEqual(response.json()['decision']['status'],'confirmed')
        self.assertEqual(Annotation.objects.get(comment=self.comment,user=self.owner).label.key,'NON_TOXIC')
        saved=self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}').json()
        self.assertEqual(saved['comment_id'],self.comment.pk)
        self.assertEqual(saved['annotation_revision'],1)
        legacy.refresh_from_db();self.assertIsNone(legacy.schema_id)
        self.assertFalse(GoldAnnotation.objects.exists())

    def test_workspace_saves_human_spans_and_preserves_omitted_spans(self):
        pair=self.execute(self.batch(), local='NON_TOXIC', api='NON_TOXIC')
        spans=[{'start':0,'end':5,'label':'TOXIC'}]
        d=decision(pair.pk,self.owner,{'label':'TOXIC','spans':spans,'note':'Human correction'})
        self.assertEqual(d.annotation.spans,spans)
        value=self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}').json()
        self.assertEqual(value['my_spans'],spans)
        d=decision(pair.pk,self.owner,{'label':'NON_TOXIC','revision':d.revision,'annotation_revision':d.annotation.revision})
        self.assertEqual(d.annotation.spans,spans)
        d=decision(pair.pk,self.owner,{'label':'TOXIC','spans':[],'revision':d.revision,'annotation_revision':d.annotation.revision})
        self.assertEqual(d.annotation.spans,[])
        self.assertEqual(Prediction.objects.count(),2)

    def test_workspace_rejects_invalid_or_disabled_spans_without_saving(self):
        pair=self.execute(self.batch(), local='NON_TOXIC', api='NON_TOXIC')
        for span in [{'start':-1,'end':5,'label':'TOXIC'},{'start':0,'end':999,'label':'TOXIC'},{'start':0,'end':5,'label':'OTHER_PROJECT'}]:
            with self.assertRaises(ValueError):decision(pair.pk,self.owner,{'label':'TOXIC','spans':[span]})
        label=ProjectLabel.objects.get(project=self.project,key='TOXIC');label.enabled=False;label.save()
        with self.assertRaises(ValueError):decision(pair.pk,self.owner,{'label':'NON_TOXIC','spans':[{'start':0,'end':5,'label':'TOXIC'}]})
        self.assertFalse(Annotation.objects.filter(comment=self.comment).exists())

    def test_branch_order_retry_and_request_idempotency(self):
        for order in (('local', 'api'), ('api', 'local')):
            batch = self.batch(request_key='-'.join(order))
            pair = self.execute(batch, order)
            ids = (pair.local_prediction_id, pair.api_prediction_id)
            self.execute(batch, order); pair.refresh_from_db()
            self.assertEqual(ids, (pair.local_prediction_id, pair.api_prediction_id))
            self.assertEqual(pair_state(pair), 'disagreement')
            self.assertEqual(self.batch(request_key='-'.join(order)).pk, batch.pk)
        self.assertEqual(Prediction.objects.count(), 4)
        self.comment.refresh_from_db(); self.assertIsNone(self.comment.ai_label)

    def test_api_failure_invalid_output_not_false_agreement(self):
        batch = self.batch(); self.execute(batch, order=('local',))
        with patch('studio.services.collaboration.api_predict', return_value={'label': 'INVALID'}):
            run_branch(batch.llm_job, {'run_id': batch.pk, 'branch': 'api'})
        pair = batch.pairs.get(); self.assertEqual(pair_state(pair), 'partial_error')
        self.assertIsNone(pair.api_prediction_id)
        self.assertEqual(pair.branches['api']['state'], 'error')
        self.assertEqual(Prediction.objects.count(), 1)

    def test_stale_text_context_and_schema_history(self):
        batch = self.batch(); pair = self.execute(batch)
        old = batch.schema.snapshot
        self.comment.context = 'changed context'; self.comment.save(); pair.comment.refresh_from_db()
        self.assertEqual(pair_state(pair), 'stale')
        with self.assertRaisesMessage(ValueError, 'đã đổi'): self.confirm(pair)
        self.comment.context = ''; self.comment.save(); pair.comment.refresh_from_db()
        response = self.post('studio/labels', project=self.project.pk, key='TOXIC', name='Tên mới', description='Nghĩa mới')
        self.assertEqual(response.status_code, 200)
        batch.schema.refresh_from_db(); self.assertEqual(batch.schema.snapshot, old)
        self.assertEqual(pair_state(pair), 'stale')
        self.assertEqual(compatibility(self.model, current_schema(self.project))['state'], 'needs_evaluation')
        with self.assertRaisesMessage(ValueError, 'bất biến'): batch.schema.save()

    def test_blind_exposure_decision_revision_and_no_auto_gold(self):
        batch = self.batch(); pair = self.execute(batch)
        detail = self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}').json()
        self.assertIsNone(detail['local']); self.assertIsNone(detail['api'])
        self.assertEqual(self.post(f'studio/collaboration/pairs/{pair.pk}/expose').status_code, 400)
        self.assertEqual(self.client.get(f'/api/studio/auto-label/runs/{batch.pk}').status_code, 403)
        self.assertEqual(self.client.get('/api/studio/quality', {'project': self.project.pk}).status_code, 403)
        self.assertEqual(self.client.get('/api/human-metrics', {'project': self.project.pk}).status_code, 403)
        self.assertEqual(self.client.get('/api/studio/jobs', {'project': self.project.pk}).status_code, 403)
        self.assertEqual(self.client.get('/api/bootstrap', {'project': self.project.pk}).json()['models'], [])
        self.assertEqual(self.post('predict-one', project=self.project.pk, text=self.comment.text).status_code, 403)
        result = self.post(f'studio/collaboration/pairs/{pair.pk}/decision', action='preliminary', label='TOXIC', revision=0)
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(self.post(f'studio/collaboration/pairs/{pair.pk}/expose').status_code, 200)
        shown = self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}').json()
        self.assertEqual(shown['mine']['viewed_predictions'], [pair.local_prediction_id, pair.api_prediction_id])
        response = self.post(f'studio/collaboration/pairs/{pair.pk}/decision', action='confirm', label='NON_TOXIC', revision=1)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Annotation.objects.get().assisted)
        self.assertFalse(GoldAnnotation.objects.exists()); self.assertFalse(self.comment.first_frozen_at)
        self.assertEqual(self.post(f'studio/collaboration/pairs/{pair.pk}/decision', action='confirm', label='TOXIC', revision=1).status_code, 400)

    def test_agreement_can_be_both_wrong_and_human_corrects(self):
        batch = self.batch(); pair = self.execute(batch, local='TOXIC', api='TOXIC')
        self.assertEqual(pair_state(pair), 'agreement'); self.assertFalse(Annotation.objects.exists())
        d = self.confirm(pair, label='NON_TOXIC')
        self.assertEqual(d.annotation.label.key, 'NON_TOXIC')
        self.assertFalse(GoldAnnotation.objects.exists())

    def test_first_decision_clock_is_saved_separately_from_review_budget(self):
        batch=self.batch();pair=self.execute(batch,local='TOXIC',api='TOXIC')
        response=self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}')
        self.assertEqual(response.status_code,200)
        d=PairDecision.objects.get(pair=pair,user=self.owner)
        d.clock['last_at']=(timezone.now()-timedelta(seconds=4)).isoformat();d.save(update_fields=['clock'])
        result=self.post(f'studio/collaboration/pairs/{pair.pk}/clock',action='pause')
        self.assertEqual(result.status_code,200);self.assertGreaterEqual(result.json()['clock']['active'],4)
        d=decision(pair.pk,self.owner,{'action':'confirm','label':'NON_TOXIC'})
        self.assertGreaterEqual(d.annotation.seconds,4)
        self.assertEqual(d.clock['state'],'paused')

    def test_cross_project_and_binary_model_incompatible(self):
        ProjectLabel.objects.create(project=self.project, key='SPAM', name='Quảng cáo')
        batch = self.batch(); pair = batch.pairs.get()
        self.assertEqual(pair_state(pair), 'incompatible'); self.assertIsNone(batch.local_job)
        self.assertIsNotNone(batch.llm_job)
        outsider = User.objects.create_user(username='outsider'); self.client.force_login(outsider)
        self.assertEqual(self.client.get(f'/api/studio/collaboration/pairs/{pair.id}').status_code, 404)
        self.assertEqual(self.post('studio/collaboration/start', project=self.project.pk).status_code, 404)

    def test_human_only_and_uncertainty_are_not_content_classes(self):
        batch = self.batch(model_id=None, connection_id=None); pair = batch.pairs.get()
        d = decision(pair.id, self.owner, {'action': 'needs_context'})
        self.assertEqual(d.label, ''); self.assertIsNone(d.annotation.label)
        self.assertEqual(d.annotation.status, 'skipped')
        self.assertEqual(self.post(f'studio/collaboration/decisions/{d.id}/approve').status_code, 400)

    def test_retrieval_excludes_self_duplicate_heldout_unapproved_and_cross_project(self):
        schema = current_schema(self.project)
        approved = self.approve_feedback(self.comment, schema, 'NON_TOXIC')
        held_source=Source.objects.create(project=self.project,name='held-out source')
        held = Comment.objects.create(project=self.project, source=held_source, text='thank you held out')
        self.approve_feedback(held, schema, 'TOXIC'); DataPartition.objects.create(comment=held, role='test')
        target = Comment.objects.create(project=self.project, source=self.source, text='thank you target')
        first = retrieve(self.project, schema, target)
        self.assertEqual([r['approval_id'] for r in first], [approved.id])
        self.assertEqual(first, retrieve(self.project, schema, target))
        duplicate = Comment.objects.create(project=self.project, source=self.source, text='THANK YOU FRIEND', digest='different-test-id')
        self.assertEqual(retrieve(self.project, schema, duplicate), [])
        self.assertEqual(retrieve(self.project, schema, self.comment), [])
        ReferenceLabel.objects.create(comment=self.comment, label='NON_TOXIC', created_by=self.owner, provenance='fixture')
        self.assertEqual(eligible_feedback(self.project, schema), [])

    def test_retrieval_records_examples_and_prompt_mode(self):
        schema = current_schema(self.project); approval = self.approve_feedback(self.comment, schema, 'NON_TOXIC')
        target = Comment.objects.create(project=self.project, source=self.source, text='thank you new friend')
        batch = self.batch(comment_ids=[target.pk])
        with patch('studio.services.collaboration.api_predict', return_value={'label': 'NON_TOXIC'}) as call:
            run_branch(batch.llm_job, {'run_id': batch.pk, 'branch': 'api'})
        context = call.call_args.kwargs['prompt_context']
        self.assertEqual(context['examples'][0]['approval_id'], approval.pk)
        self.assertEqual(batch.pairs.get().api_prediction.config_snapshot['prompt_version'], 'project-sentence-fewshot-v1')
        description_only = self.batch(comment_ids=[target.pk], few_shot=False)
        self.assertEqual(description_only.pairs.get().branches['api']['examples'], [])

    def test_source_grouped_multiclass_train_activation_and_rollback(self):
        ProjectLabel.objects.create(project=self.project, key='SPAM', name='Quảng cáo', description='Bán hàng')
        schema = current_schema(self.project)
        for source_index in range(6):
            source = Source.objects.create(project=self.project, name='video-' + str(source_index))
            for key, text in [('NON_TOXIC', 'cảm ơn video bổ ích'), ('TOXIC', 'đồ ngu câm đi'), ('SPAM', 'mua hàng giảm giá ngay')]:
                for repeat in range(2):
                    c = Comment.objects.create(project=self.project, source=source, text=f'{text} nguồn {source_index} mẫu {repeat}')
                    self.approve_feedback(c, schema, key)
        # Original example was not approved, so it does not enter training.
        dataset = freeze_dataset(self.project, schema, 7)
        sources = {k: {r['source'] for r in rows} for k, rows in dataset.snapshot['splits'].items()}
        self.assertFalse(sources['train'] & sources['test']); self.assertFalse(sources['validation'] & sources['test'])
        from core.jobs.feedback_train import run as train_job
        with TemporaryDirectory() as folder, override_settings(PRIVATE_DATA=Path(folder)):
            job = Job.objects.create(project=self.project, actor=self.owner, kind='feedback_train')
            result = train_job(job, {'dataset_id': dataset.pk, 'algorithm': 'complement_nb'})
            model = ModelRun.objects.get(pk=result['model_id']); report = json.loads(model.report)
            self.assertEqual(report['schema_sha256'], schema.sha256)
            self.assertEqual(report['feedback_dataset_sha256'], dataset.sha256)
            self.assertIn('validation', report)
            self.assertIsNone(ensure(self.project).active_model_id)
            activated = self.post('studio/collaboration/activate', project=self.project.pk, model_id=model.pk, note='Validation checked fixture')
            self.assertEqual(activated.status_code, 200, activated.content)
            from core.services.providers import local_predict
            predictions=local_predict(self.project,['cảm ơn video bổ ích','đồ ngu câm đi','mua hàng giảm giá ngay'],model.pk)
            self.assertEqual([row['label'] for row in predictions],['NON_TOXIC','TOXIC','SPAM'])
            old = ModelRun.objects.create(project=self.project, name='rollback fixture', artifact_path=model.artifact_path, report=model.report)
            self.assertEqual(self.post('studio/collaboration/activate', project=self.project.pk, model_id=old.pk, note='Rollback fixture').status_code, 200)
            self.assertEqual(ensure(self.project).active_model_id, old.pk)

    def test_budget_clock_pause_resume_exhaustion_and_blind_guard(self):
        batch = self.batch(); pair = self.execute(batch); self.confirm(pair)
        run = paired.create(batch, 'fixed_explore', 1, 42, self.owner)
        task = paired.claim(run.pk, self.reviewer)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}').status_code, 403)
        self.assertEqual(self.client.get(f'/api/studio/budget/runs/{run.pk}/report').status_code, 403)
        task.clock['last_at'] = (timezone.now()-timedelta(seconds=5)).isoformat(); task.save()
        paired.clock_tick(task, 'pause'); task.save()
        active = task.clock['active']; task.clock['last_at'] = (timezone.now()-timedelta(seconds=100)).isoformat()
        paired.clock_tick(task, 'resume'); task.save()
        self.assertAlmostEqual(task.clock['active'], active, delta=.1); self.assertGreaterEqual(task.clock['idle'], 100)
        paired.submit(task.pk, self.reviewer, 'NON_TOXIC', '')
        run.refresh_from_db(); self.assertEqual(run.state, 'exhausted')
        self.assertGreater(run.used_seconds, run.budget_seconds)
        with self.assertRaisesMessage(ValueError, 'hết ngân sách'): paired.claim(run.pk, self.reviewer)

    def test_policy_seed_explores_agreements_and_replay_requires_full_observation(self):
        rows = [{'id': i, 'group': 'agreement' if i % 2 else 'disagreement'} for i in range(1, 21)]
        observed = {g: {'n': 0, 'score': .1} for g in ('agreement', 'disagreement')}
        self.assertEqual(paired.select(rows, 'random', 42, 0, observed), paired.select(rows, 'random', 42, 0, observed))
        self.assertEqual(paired.select(rows, 'fixed_explore', 42, 4, observed)[0]['group'], 'agreement')
        batch = self.batch(); pair = self.execute(batch); self.confirm(pair)
        run = paired.create(batch, 'random', 60, 42, self.owner)
        with self.assertRaisesMessage(ValueError, 'đầy đủ'): paired.replay(run, 'random', 42, 60)
        task = paired.claim(run.pk, self.reviewer); paired.submit(task.pk, self.reviewer, 'NON_TOXIC', '')
        self.assertEqual(paired.replay(run, 'random', 42, 60), paired.replay(run, 'random', 42, 60))

    def test_net_fixes_counts_harm_and_entire_population(self):
        batch = self.batch(); pair = self.execute(batch); self.confirm(pair, label='NON_TOXIC')
        ReferenceLabel.objects.create(comment=self.comment, label='NON_TOXIC', created_by=self.judge, provenance='test fixture only')
        run = paired.create(batch, 'random', 60, 42, self.owner)
        task = paired.claim(run.pk, self.reviewer); paired.submit(task.pk, self.reviewer, 'TOXIC', 'fixture harm')
        with self.assertRaises(PermissionError): paired.open_adjudication(task.pk, self.owner)
        paired.adjudicate(task.pk, self.judge, 'TOXIC', 'fixture intentional wrong final')
        report = paired.report(run)
        self.assertEqual(report['net_fixes'], -1); self.assertEqual(report['harmed'], 1)
        self.assertEqual(report['metrics']['final']['n'], 1)
        self.assertTrue(report['demo'])

    def test_legacy_grouping_and_prediction_history_are_preserved(self):
        from reviewing.services import group_for
        self.assertEqual(group_for('TOXIC', 'NON_TOXIC'), 'D')
        legacy = ReviewRun.objects.create(project=self.project)
        self.assertEqual(legacy.grouping_strategy, 'legacy_ai_human')
        self.assertEqual(legacy.input_snapshot, {})

    def test_seed_demo_is_explicit_mock_no_network_and_real_sklearn_artifact(self):
        from django.core.management import call_command
        from io import StringIO
        with TemporaryDirectory() as folder, override_settings(PRIVATE_DATA=Path(folder)), patch('httpx.Client.send', side_effect=AssertionError('Demo must not access network')):
            output = StringIO()
            call_command('seed_collaboration_demo', owner=self.owner.username, reviewer=self.reviewer.username,
                         judge=self.judge.username, stdout=output)
            from studio.models import AutoLabelRun
            batch = AutoLabelRun.objects.filter(options__mock_predictions=True).get()
            self.assertTrue(batch.options['demo'])
            self.assertEqual({pair_state(p) for p in batch.pairs.all()}, {'agreement', 'disagreement', 'partial_error'})
            self.assertFalse(ProviderConnection.objects.get(pk=batch.connection_config['id']).enabled)
            model=ModelRun.objects.get(pk=batch.model_config['id'])
            self.assertTrue((Path(model.artifact_path)/'classifier.joblib').exists())

    def test_paired_report_same_ids_errors_no_fake_metrics(self):
        from studio.services.experiment_reports import comparison
        baseline = self.batch(few_shot=False); self.execute(baseline)
        adapted = self.batch(few_shot=True); self.execute(adapted, order=('local',))
        result=comparison([baseline,adapted],True)
        self.assertEqual(result['common_id_text_count'],1)
        self.assertTrue(result['demo'])
        self.assertTrue(all(c['metrics'] is None for c in result['conditions']))
        self.assertEqual(result['conditions'][-1]['coverage'],0)
        self.assertEqual(result['conditions'][-1]['condition'],'api-fewshot-retrieval')

    def test_pause_run_cannot_claim_but_inflight_can_finish(self):
        batch=self.batch(); pair=self.execute(batch); self.confirm(pair)
        run=paired.create(batch,'random',60,42,self.owner)
        task=paired.claim(run.pk,self.reviewer)
        response=self.post(f'studio/budget/runs/{run.pk}/control',action='pause')
        self.assertEqual(response.status_code,200)
        self.assertEqual(ReviewTask.objects.get(pk=task.pk).clock['state'],'paused')
        paired.submit(task.pk,self.reviewer,'NON_TOXIC','')
        run.refresh_from_db(); self.assertEqual(run.state,'paused')
        with self.assertRaises(ValueError):paired.claim(run.pk,self.judge)

    def test_explicit_project_deletion_with_paired_history_keeps_accounts(self):
        batch=self.batch();pair=self.execute(batch);d=self.confirm(pair)
        FeedbackApproval.objects.create(comment=self.comment,schema=d.schema,decision=d,decision_revision=d.revision,
            label=d.label,text=pair.text,text_hash=pair.text_hash,source_id_snapshot=self.source.pk,approved_by=self.owner)
        FeedbackDataset.objects.create(project=self.project,schema=d.schema,sha256='fixture',snapshot={'splits':{}})
        Job.objects.filter(project=self.project).update(status='complete')
        response=self.post('studio/project-settings',project=self.project.pk,action='delete',confirm=self.project.name)
        self.assertEqual(response.status_code,200,response.content)
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())
        self.assertEqual(User.objects.count(),3)

    def test_human_queue_supervision_and_manager_approval_of_another_user(self):
        batch=self.batch();pair=self.execute(batch,api='NON_TOXIC')
        response=self.client.get(f'/api/studio/collaboration/runs/{batch.pk}').json()
        self.assertEqual(response['rows'][0]['review_state'],'awaiting_review')
        d=self.confirm(pair,user=self.reviewer,label='NON_TOXIC')
        before=PairDecision.objects.count()
        response=self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}?supervision=1')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['decisions'][0]['label'],'NON_TOXIC')
        self.assertEqual(PairDecision.objects.count(),before)
        self.assertEqual(self.post(f'studio/collaboration/decisions/{d.pk}/approve').status_code,200)
        row=self.client.get(f'/api/studio/collaboration/runs/{batch.pk}').json()['rows'][0]
        self.assertEqual(row['review_state'],'reviewed');self.assertTrue(row['feedback_approved'])
        self.assertNotIn('local',row);self.assertFalse(GoldAnnotation.objects.exists())
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}?supervision=1').status_code,403)
        decision(pair.pk,self.reviewer,{'action':'confirm','label':'NON_TOXIC','revision':d.revision,'annotation_revision':d.annotation.revision})
        row=self.client.get(f'/api/studio/collaboration/runs/{batch.pk}').json()['rows'][0]
        self.assertFalse(row['feedback_approved'])

    def test_supervision_does_not_bypass_blind_decision(self):
        batch=self.batch();pair=self.execute(batch)
        self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}')
        response=self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}?supervision=1')
        self.assertEqual(response.status_code,403)

    def test_legacy_automatic_list_does_not_mix_in_human_review_runs(self):
        from studio.models import AutoLabelRun
        batch=self.batch()
        old=AutoLabelRun.objects.create(project=self.project,actor=self.owner,labels=[],items=[])
        response=self.client.get('/api/studio/auto-label/runs',{'project':self.project.pk})
        self.assertEqual(response.status_code,200)
        self.assertEqual([r['id'] for r in response.json()['runs']],[old.pk])
        self.assertNotIn(batch.pk,[r['id'] for r in response.json()['runs']])

    def test_supervisor_who_saw_human_labels_cannot_claim_independent_review(self):
        batch=self.batch();pair=self.execute(batch,api='NON_TOXIC');self.confirm(pair)
        run=paired.create(batch,'random',60,42,self.owner)
        self.client.force_login(self.judge)
        self.assertEqual(self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}?supervision=1').status_code,200)
        with self.assertRaisesMessage(ValueError,'Không còn mẫu'):paired.claim(run.pk,self.judge)
