import hashlib,json,tempfile
from datetime import timedelta
from pathlib import Path
from django.test import TestCase,Client
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from core.models import Project,Membership,Source,Comment,Prediction
from experiments.models import ModelRun,ReferenceLabel
from experiments.training import metrics,canonical
from core.services.providers import local_predict
from reviewing.models import ReviewRun,ReviewTask
from reviewing.services import group_for,claim,submit,adjudicate,group_stats

class WorkflowTests(TestCase):
    def setUp(self):
        self.users=[User.objects.create_user(username=f'u{i}',password='test-pass-only') for i in range(4)]
        self.p=Project.objects.create(name='Isolated test project',owner=self.users[0])
        for i,u in enumerate(self.users[:3]):Membership.objects.create(project=self.p,user=u,role='manager' if i==0 else 'annotator')
        self.source=Source.objects.create(project=self.p,name='Synthetic test data')
        self.row=Comment.objects.create(project=self.p,source=self.source,text='Một ví dụ phê bình nội dung.',ai_label='NON_TOXIC')
        self.client.force_login(self.users[0])
    def post(self,path,p):return self.client.post('/api/'+path,json.dumps(p),content_type='application/json')
    def freeze(self,row=None,label='TOXIC'):
        r=row or self.row;r.first_label=label;r.first_actor=self.users[0];r.first_frozen_at=timezone.now();r.origin_group=group_for(r.ai_label,label);r.save();return r
    def make_run(self):return ReviewRun.objects.create(project=self.p,population=json.dumps([self.row.id]),budget_seconds=60)
    def test_four_immutable_groups(self):
        for a,b,g in [('TOXIC','TOXIC','A'),('NON_TOXIC','NON_TOXIC','B'),('NON_TOXIC','TOXIC','C'),('TOXIC','NON_TOXIC','D')]:self.assertEqual(group_for(a,b),g)
    def test_non_member_cannot_read_project(self):
        self.client.force_login(self.users[3]);r=self.client.get('/api/bootstrap',{'project':self.p.id});self.assertEqual(r.status_code,404)
    def test_revision_and_first_pass_freeze(self):
        r=self.post(f'comments/{self.row.id}/first',{'label':'TOXIC','revision':99});self.assertEqual(r.status_code,400)
        r=self.post(f'comments/{self.row.id}/first',{'label':'TOXIC','revision':0,'seconds':2});self.assertEqual(r.status_code,200)
        self.row.refresh_from_db();self.assertEqual(self.row.origin_group,'C');self.assertIsNotNone(self.row.first_frozen_at)
        r=self.post(f'comments/{self.row.id}/first',{'label':'NON_TOXIC','revision':1});self.assertEqual(r.status_code,400)
        self.row.refresh_from_db();self.assertEqual(self.row.first_label,'TOXIC')
    def test_null_ai_is_not_clean(self):
        self.row.ai_label=None;self.row.save();r=self.post(f'comments/{self.row.id}/first',{'label':'NON_TOXIC','revision':0});self.assertEqual(r.status_code,400)
    def test_same_actor_cannot_claim_and_other_actor_can(self):
        self.freeze();run=self.make_run()
        with self.assertRaises(ValueError):claim(run.id,self.users[0])
        t=claim(run.id,self.users[1]);self.assertEqual(t.comment_id,self.row.id)
        self.assertEqual(claim(run.id,self.users[1]).id,t.id)
    def test_blind_payload_and_other_routes_hide_labels(self):
        self.freeze();run=self.make_run();self.client.force_login(self.users[1]);r=self.post(f'runs/{run.id}/claim',{});self.assertEqual(r.status_code,200)
        task=r.json()['task']
        for secret in ['ai_label','first_label','group','origin_group','reason']:self.assertNotIn(secret,task)
        bootstrap=self.client.get('/api/bootstrap',{'project':self.p.id}).json();self.assertNotIn('ai_label',bootstrap['comments'][0]);self.assertFalse(bootstrap['events'])
    def test_disagreement_requires_third_actor(self):
        self.freeze();run=self.make_run();t=claim(run.id,self.users[1]);ReviewTask.objects.filter(pk=t.id).update(created_at=timezone.now()-timedelta(seconds=2));t=submit(t.id,self.users[1],'NON_TOXIC')
        self.assertEqual(t.state,'conflict')
        with self.assertRaises(PermissionError):adjudicate(t.id,self.users[0],'NON_TOXIC','Reason')
        t=adjudicate(t.id,self.users[2],'NON_TOXIC','Phê bình nội dung, không công kích.')
        self.assertEqual(t.state,'complete');self.row.refresh_from_db();self.assertEqual(self.row.first_label,'TOXIC');self.assertEqual(self.row.origin_group,'C')
        self.assertEqual(group_stats(run)['C']['changed'],1)
    def test_serial_claim_and_exhausted_budget(self):
        self.freeze();run=self.make_run();claim(run.id,self.users[1])
        with self.assertRaises(ValueError):claim(run.id,self.users[2])
        run.used_seconds=61;run.save()
        with self.assertRaises(ValueError):claim(run.id,self.users[2])
    def test_run_population_is_frozen(self):
        self.freeze();run=self.make_run();extra=Comment.objects.create(project=self.p,source=self.source,text='Mẫu được thêm sau phiên.',ai_label='TOXIC');self.freeze(extra)
        t=claim(run.id,self.users[1]);submit(t.id,self.users[1],'TOXIC')
        with self.assertRaises(ValueError):claim(run.id,self.users[1])
    def test_repeated_submit_is_rejected(self):
        self.freeze();run=self.make_run();t=claim(run.id,self.users[1]);submit(t.id,self.users[1],'TOXIC')
        with self.assertRaises(ValueError):submit(t.id,self.users[1],'TOXIC')
    def test_export_includes_only_labeled_and_preserves_first(self):
        self.freeze();Comment.objects.create(project=self.p,source=self.source,text='Mẫu chưa ai gán nhãn.')
        r=self.client.get('/api/export',{'project':self.p.id,'format':'jsonl'});self.assertEqual(r.status_code,200)
        rows=[json.loads(line) for line in r.content.decode().splitlines()];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['final_label'],'TOXIC');self.assertFalse(rows[0]['reviewed'])
    def test_metrics_count_harm_and_fix(self):
        self.freeze();ReferenceLabel.objects.create(comment=self.row,label='NON_TOXIC',created_by=self.users[2],provenance='Independent test reference')
        run=self.make_run();t=claim(run.id,self.users[1]);submit(t.id,self.users[1],'NON_TOXIC');adjudicate(t.id,self.users[2],'NON_TOXIC','Đã phân xử.')
        r=self.client.get('/api/human-metrics',{'project':self.p.id,'run':run.id});self.assertEqual(r.json()['net_fixes'],1)
    def test_gemini_missing_key_does_not_fabricate_prediction(self):
        with self.settings(GEMINI_API_KEY=''):
            r=self.post('predict',{'project':self.p.id,'provider':'gemini'});self.assertEqual(r.status_code,400);self.assertEqual(Prediction.objects.count(),0)
    def test_local_model_is_loadable_and_measured(self):
        artifact=settings.BASE_DIR/'artifacts/victsd-logreg-v1';report=json.loads((artifact/'metrics.json').read_text())
        ModelRun.objects.create(project=self.p,name='Measured model',artifact_path=str(artifact),report=json.dumps(report))
        result=local_predict(self.p,['Bạn giải thích rất dễ hiểu, cảm ơn bạn.'])[0]
        self.assertIn(result['label'],['TOXIC','NON_TOXIC']);self.assertEqual(result['input_tokens'],0);self.assertEqual(report['test']['n'],1000)
    def test_csrf_is_required_for_mutation(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.users[0]);r=client.post('/api/projects',json.dumps({'name':'CSRF rejected'}),content_type='application/json');self.assertEqual(r.status_code,403)

class MetricUnitTests(TestCase):
    def test_confusion_and_macro_are_not_accuracy(self):
        result=metrics([0,0,0,1],[0,0,0,0]);self.assertEqual(result['accuracy'],.75);self.assertLess(result['macro_f1'],.5);self.assertEqual(result['confusion_matrix'],[[3,0],[1,0]])
    def test_canonical_unicode_whitespace(self):self.assertEqual(canonical('  TiẾng   Việt '),canonical('tiếng việt'))
