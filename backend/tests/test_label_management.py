import json
from django.contrib.auth.models import User
from django.test import TestCase
from core.models import Project,Membership,Source,Comment,Prediction
from studio.models import ProjectLabel,Annotation,AnnotationEvent,AutoLabelRun,DatasetVersion,PairDecision
from studio.services.projects import ensure
from studio.services.adaptation import current_schema
from studio.services.collaboration import start_run,decision
from experiments.models import ModelRun


class LabelManagementTests(TestCase):
    def setUp(self):
        self.owner=User.objects.create_user('labels-owner')
        self.reader=User.objects.create_user('labels-reader')
        self.other=User.objects.create_user('labels-other')
        self.project=Project.objects.create(name='Nhãn dự án 1',owner=self.owner)
        Membership.objects.create(project=self.project,user=self.owner,role='manager')
        Membership.objects.create(project=self.project,user=self.reader)
        ensure(self.project)
        self.source=Source.objects.create(project=self.project,name='Nguồn thử')
        self.comment=Comment.objects.create(project=self.project,source=self.source,text='Bình luận thử 😀')
        self.client.force_login(self.owner)

    def catalog(self):
        response=self.client.get('/api/studio/labels',{'project':self.project.pk})
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def post(self,**values):
        return self.client.post('/api/studio/labels',json.dumps({'project':self.project.pk,**values}),content_type='application/json')

    def create(self,key='CUSTOM'):
        response=self.post(action='create',key=key,name='Tên '+key,color='#123456',description='Hướng dẫn',order=5)
        self.assertEqual(response.status_code,200,response.content)
        return next(l for l in response.json()['labels'] if l['key']==key)

    def mutate(self,label,**values):
        return self.post(**{**label,'action':'update',**values})

    def test_crud_reload_order_disable_reactivate_and_delete_unused(self):
        label=self.create()
        response=self.mutate(label,name='Tên mới',color='#ff5500',order=0)
        self.assertEqual(response.status_code,200,response.content)
        updated=next(l for l in self.catalog()['labels'] if l['key']==label['key'])
        self.assertEqual((updated['name'],updated['color'],updated['order']),('Tên mới','#ff5500',0))
        self.assertGreater(updated['revision'],label['revision'])
        self.assertEqual(self.mutate(updated,enabled=False).status_code,200)
        stopped=next(l for l in self.catalog()['labels'] if l['key']==label['key'])
        self.assertFalse(stopped['enabled'])
        self.assertEqual(self.mutate(stopped,enabled=True).status_code,200)
        active=next(l for l in self.catalog()['labels'] if l['key']==label['key'])
        self.assertTrue(active['can_delete'])
        self.assertEqual(self.mutate(active,action='delete').status_code,200)
        self.assertNotIn(label['key'],[l['key'] for l in self.catalog()['labels']])

    def test_permissions_project_scope_and_same_key_in_two_projects(self):
        label=self.create()
        other_project=Project.objects.create(name='Dự án 2',owner=self.other)
        Membership.objects.create(project=other_project,user=self.other,role='manager');ensure(other_project)
        other_label=ProjectLabel.objects.create(project=other_project,key=label['key'],name='Nhãn riêng dự án 2')
        self.assertEqual(self.mutate({**label,'id':other_label.pk}).status_code,404)
        self.assertEqual(self.client.get('/api/studio/labels',{'project':other_project.pk}).status_code,404)
        other_label.refresh_from_db();self.assertEqual(other_label.name,'Nhãn riêng dự án 2')
        self.client.force_login(self.reader)
        self.assertFalse(self.catalog()['can_manage'])
        self.assertEqual(self.mutate(label,name='Không được sửa').status_code,403)
        self.assertEqual(self.post(action='create',key='FORBIDDEN',name='X').status_code,403)

    def test_locked_and_archived_projects_are_read_only(self):
        label=self.create();prefs=ensure(self.project)
        for field in ('locked','archived'):
            with self.subTest(field=field):
                setattr(prefs,field,True);prefs.save()
                self.assertTrue(self.catalog()[field])
                self.assertEqual(self.mutate(label,name='Không được sửa').status_code,403)
                setattr(prefs,field,False);prefs.save()

    def test_revision_conflict_and_stable_key(self):
        label=self.create()
        self.assertEqual(self.mutate(label,name='Phiên khác').status_code,200)
        self.assertEqual(self.mutate(label,name='Không được ghi đè').status_code,409)
        fresh=next(l for l in self.catalog()['labels'] if l['key']==label['key'])
        self.assertEqual(self.mutate(fresh,key='CHANGED').status_code,400)
        self.assertEqual(ProjectLabel.objects.get(pk=label['id']).name,'Phiên khác')
        self.assertFalse(ProjectLabel.objects.filter(project=self.project,key='CHANGED').exists())

    def test_validation_and_duplicate_key(self):
        self.create()
        for values in ({'key':'CUSTOM','name':'Trùng mã'},{'key':'EMPTY','name':'   '},
            {'key':'bad-key','name':'Tên'},{'key':'COLOR','name':'Tên','color':'red'},
            {'key':'ORDER','name':'Tên','order':-1},{'key':'ENABLED','name':'Tên','enabled':'false'}):
            with self.subTest(values=values):
                response=self.post(**{'action':'create','color':'#123456','order':0,**values})
                self.assertEqual(response.status_code,400,response.content)

    def test_used_labels_in_sentence_span_prediction_event_run_and_version_are_protected(self):
        for kind in ('sentence','span','prediction','event','run','version','first'):
            with self.subTest(kind=kind):
                label=self.create('USED_'+kind.upper());obj=ProjectLabel.objects.get(pk=label['id'])
                comment=Comment.objects.create(project=self.project,source=self.source,text='Nội dung '+kind)
                if kind=='sentence':Annotation.objects.create(comment=comment,user=self.owner,label=obj)
                elif kind=='span':Annotation.objects.create(comment=comment,user=self.owner,spans=[{'start':0,'end':3,'label':obj.key}])
                elif kind=='prediction':Prediction.objects.create(comment=comment,provider='fixture',model_version='test',label=obj.key)
                elif kind=='event':AnnotationEvent.objects.create(comment=comment,user=self.owner,action='undo',before={'label':obj.key},after={})
                elif kind=='run':AutoLabelRun.objects.create(project=self.project,actor=self.owner,labels=[{'key':obj.key}],items=[])
                elif kind=='version':DatasetVersion.objects.create(project=self.project,name='History',snapshot={'comments':[{'label':obj.key}]},sha256='fixture',created_by=self.owner)
                else:comment.first_label=obj.key;comment.save()
                self.assertEqual(self.mutate(label,action='delete').status_code,400)
                self.assertTrue(ProjectLabel.objects.filter(pk=obj.pk).exists())
                self.assertEqual(self.mutate(label,enabled=False).status_code,200)
                fresh=next(l for l in self.catalog()['labels'] if l['id']==obj.pk)
                self.assertTrue(fresh['used']);self.assertFalse(fresh['can_delete']);self.assertFalse(fresh['enabled'])

    def test_empty_schema_stays_empty_and_does_not_recreate_default_labels(self):
        for label in self.catalog()['labels']:
            self.assertEqual(self.mutate(label,action='delete').status_code,200)
        self.assertEqual(self.catalog()['labels'],[])
        response=self.client.get('/api/studio/workspace',{'project':self.project.pk,'comment':self.comment.pk})
        self.assertEqual(response.json()['labels'],[])

    def test_schema_history_and_model_compatibility_survive_edit(self):
        before=current_schema(self.project)
        model=ModelRun.objects.create(project=self.project,name='Binary fixture',artifact_path='unused',report=json.dumps({'label_keys':['NON_TOXIC','TOXIC']}))
        prefs=ensure(self.project);prefs.active_model=model;prefs.save()
        self.assertEqual(self.catalog()['local_model']['state'],'compatible')
        self.create('SPAM')
        self.assertEqual(self.catalog()['local_model']['state'],'incompatible')
        self.assertNotIn('SPAM',[l['key'] for l in before.snapshot['labels']])
        self.assertEqual(ModelRun.objects.get(pk=model.pk).report,model.report)

    def test_human_can_use_new_schema_without_reinterpreting_frozen_predictions(self):
        run=start_run(self.project,self.owner,{'model_id':None,'connection_id':None})
        pair=run.pairs.get()
        pair.local_prediction=Prediction.objects.create(comment=self.comment,provider='local',model_version='fixture',label='TOXIC')
        pair.api_prediction=Prediction.objects.create(comment=self.comment,provider='api',model_version='fixture',label='NON_TOXIC')
        pair.branches={'local':{'state':'complete'},'api':{'state':'complete'}};pair.save()
        path=f'/api/studio/collaboration/pairs/{pair.pk}'
        self.client.get(path)
        self.create('SPAM')
        self.assertEqual(self.client.post(path+'/expose','{}',content_type='application/json').status_code,400)
        d=decision(pair.pk,self.owner,{'action':'preliminary','label':'SPAM'})
        self.assertEqual(self.client.post(path+'/expose','{}',content_type='application/json').status_code,200)
        d=decision(pair.pk,self.owner,{'action':'confirm','label':'SPAM','revision':d.revision})
        self.assertEqual(d.annotation.label.key,'SPAM')
        self.assertEqual(d.schema_id,current_schema(self.project).pk)
        pair.refresh_from_db();self.assertEqual(pair.local_prediction.label,'TOXIC');self.assertEqual(pair.api_prediction.label,'NON_TOXIC')
        self.assertNotEqual(d.schema_id,run.schema_id)
        self.assertEqual(self.client.get(path).json()['state'],'stale')
        label=next(l for l in self.catalog()['labels'] if l['key']=='SPAM')
        self.assertEqual(self.mutate(label,enabled=False).status_code,200)
        response=self.client.post(path+'/decision',json.dumps({'label':'SPAM','action':'confirm','revision':d.revision,'annotation_revision':d.annotation.revision}),content_type='application/json')
        self.assertEqual(response.status_code,400)
        self.assertTrue(Annotation.objects.filter(pk=d.annotation_id,label__key='SPAM').exists())
