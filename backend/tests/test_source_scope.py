import json
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from core.models import Project,Membership,Source,Comment
from experiments.models import ModelRun
from studio.models import AutoLabelRun,Annotation,AIExposure
from studio.services.projects import ensure
from studio.services.collaboration import start_run
from tests.model_fixture import local_model_fixture


class SourceScopeTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='video-scope')
        self.project=Project.objects.create(name='Scope fixtures',owner=self.user)
        Membership.objects.create(project=self.project,user=self.user,role='manager');ensure(self.project)
        self.a=Source.objects.create(project=self.project,name='Video A',kind='youtube')
        self.b=Source.objects.create(project=self.project,name='Video B',kind='youtube')
        self.empty=Source.objects.create(project=self.project,name='Empty video')
        self.ca=[Comment.objects.create(project=self.project,source=self.a,text=f'A {i}') for i in range(2)]
        self.cb=[Comment.objects.create(project=self.project,source=self.b,text=f'B {i}') for i in range(2)]
        other=Project.objects.create(name='Other project',owner=self.user)
        Membership.objects.create(project=other,user=self.user,role='manager');ensure(other)
        self.foreign=Source.objects.create(project=other,name='Other source')
        self.batch=start_run(self.project,self.user,{'model_id':None,'connection_id':None})
        self.client.force_login(self.user)

    def post(self,path,**data):
        return self.client.post('/api/studio/'+path,json.dumps(data),content_type='application/json')

    def test_dashboard_and_queue_only_include_selected_video(self):
        value=self.client.get('/api/studio/collaboration',{'project':self.project.pk,'source':self.a.pk}).json()
        run=next(r for r in value['runs'] if r['id']==self.batch.pk)
        self.assertEqual((run['count'],run['total_count']),(2,4))
        queue=self.client.get(f'/api/studio/collaboration/runs/{self.batch.pk}',{'source':self.a.pk}).json()
        self.assertEqual(queue['scope_source_id'],self.a.pk)
        self.assertEqual({r['comment_id'] for r in queue['rows']},{c.pk for c in self.ca})
        empty=self.client.get('/api/studio/collaboration',{'project':self.project.pk,'source':self.empty.pk}).json()
        self.assertEqual(empty['runs'],[])

    def test_detail_and_writes_reject_a_different_video(self):
        pair=self.batch.pairs.get(comment=self.cb[0])
        self.assertEqual(self.client.get(f'/api/studio/collaboration/pairs/{pair.pk}',{'source':self.a.pk}).status_code,404)
        self.assertEqual(self.post(f'collaboration/pairs/{pair.pk}/decision',source_id=self.a.pk,label='NON_TOXIC',revision=0,annotation_revision=0).status_code,400)
        self.assertEqual(self.post(f'collaboration/pairs/{pair.pk}/expose',source_id=self.a.pk).status_code,400)
        self.assertEqual(self.post(f'comments/{self.cb[0].pk}/annotation',project=self.project.pk,source_id=self.a.pk,label='NON_TOXIC',revision=0).status_code,400)
        self.assertFalse(Annotation.objects.exists());self.assertFalse(AIExposure.objects.exists())

    def test_new_paired_run_and_request_key_keep_video_scope(self):
        payload={'project':self.project.pk,'source_id':self.a.pk,'model_id':None,'connection_id':None,'request_key':'video-only'}
        response=self.post('collaboration/start',**payload)
        self.assertEqual(response.status_code,200)
        run=AutoLabelRun.objects.get(pk=response.json()['id'])
        self.assertEqual(run.options['source_id'],self.a.pk)
        self.assertEqual(set(run.pairs.values_list('comment_id',flat=True)),{c.pk for c in self.ca})
        self.assertEqual(self.post('collaboration/start',**{**payload,'source_id':self.b.pk}).status_code,400)

    def test_manual_queue_does_not_fall_through_when_video_finishes(self):
        url='/api/studio/workspace'
        params={'project':self.project.pk,'source':self.a.pk}
        self.assertEqual(self.client.get(url,params).json()['comment']['source_id'],self.a.pk)
        self.assertIsNone(self.client.get(url,{**params,'comment':self.cb[0].pk}).json()['comment'])
        for comment in self.ca:
            response=self.post(f'comments/{comment.pk}/annotation',project=self.project.pk,source_id=self.a.pk,label='NON_TOXIC',revision=0)
            self.assertEqual(response.status_code,200)
        self.assertIsNone(self.client.get(url,params).json()['comment'])
        self.assertFalse(Annotation.objects.filter(comment__source=self.b).exists())

    def test_foreign_or_deleted_source_cannot_be_used(self):
        for source in (self.foreign.pk,99999999):
            self.assertEqual(self.client.get('/api/studio/collaboration',{'project':self.project.pk,'source':source}).status_code,404)
            self.assertEqual(self.client.get('/api/studio/workspace',{'project':self.project.pk,'source':source}).status_code,404)
            self.assertEqual(self.post('collaboration/start',project=self.project.pk,source_id=source,model_id=None,connection_id=None).status_code,404)

    def test_automatic_listing_download_and_retry_do_not_mix_sources(self):
        def run(comments):
            return AutoLabelRun.objects.create(project=self.project,actor=self.user,items=[{'id':c.pk,'text':c.text,'source':c.source.name} for c in comments])
        mixed=run(self.ca+self.cb);only_a=run(self.ca);only_b=run(self.cb)
        listing=self.client.get('/api/studio/auto-label/runs',{'project':self.project.pk,'source':self.a.pk}).json()
        self.assertEqual([r['id'] for r in listing['runs']],[only_a.pk])
        self.assertEqual(self.client.get(f'/api/studio/auto-label/runs/{mixed.pk}',{'source':self.a.pk}).status_code,400)
        self.assertEqual(self.client.get(f'/api/studio/auto-label/runs/{only_b.pk}',{'source':self.a.pk,'download':'csv'}).status_code,400)
        csv=self.client.get(f'/api/studio/auto-label/runs/{only_a.pk}',{'source':self.a.pk,'download':'csv'})
        self.assertEqual(csv.status_code,200);self.assertNotIn('B 0',csv.content.decode())
        self.assertEqual(self.post(f'collaboration/runs/{self.batch.pk}/retry',source_id=self.a.pk,branch='local').status_code,400)

    def test_new_automatic_run_freezes_only_selected_video(self):
        with local_model_fixture() as (path,report),patch('core.services.jobs.dispatch'):
            model=ModelRun.objects.create(project=self.project,name='Synthetic',artifact_path=str(path),report=json.dumps(report))
            response=self.post('auto-label/start',project=self.project.pk,source_id=self.b.pk,model_id=model.pk)
        self.assertEqual(response.status_code,200,response.content)
        run=AutoLabelRun.objects.get(pk=response.json()['id'])
        self.assertEqual(run.options['source_id'],self.b.pk)
        self.assertEqual({c['id'] for c in run.items},{c.pk for c in self.cb})
