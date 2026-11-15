import hashlib,json,re,secrets
from django.conf import settings
from django.db import transaction
from django.db.models import Count,Q
from django.http import JsonResponse,HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET,require_POST
from django.contrib.auth.models import User
from core.api import api,data,project_for,manager,in_blind,serialize_comment,report_job
from core.models import Project,Membership,Source,Comment,Prediction,Job,audit
from studio.models import *
from studio.services.projects import ensure,labels_for,writable,label_for,validate_spans,mutation_guard,resolve_source

def pref_json(p):return {'guidelines':p.guidelines,'locked':p.locked,'archived':p.archived,'redundancy':p.redundancy,'independent':p.independent,'active_model_id':p.active_model_id,'active_connection_id':p.active_connection_id}
def annotation_json(a):
    if not a:return None
    return {'id':a.id,'comment_id':a.comment_id,'user_id':a.user_id,'label':a.label.key if a.label else None,'spans':a.spans,'note':a.note,'status':a.status,'assisted':a.assisted,'seconds':a.seconds,'revision':a.revision,'updated_at':a.updated_at.isoformat()}
def studio_bootstrap(project,user,compact=False):
    p=ensure(project);can_manage=manager(project,user);blind=in_blind(project,user)
    sources=[{'id':x.id,'name':x.name,'kind':x.kind,'url':x.url,'metadata':x.metadata,'fetch_state':x.fetch_state,'count':x.comment_count} for x in project.sources.annotate(comment_count=Count('comments')).order_by('-id')]
    totals=Annotation.objects.filter(comment__project=project,status='submitted').aggregate(annotations=Count('id'),annotated_comments=Count('comment_id',distinct=True),mine=Count('id',filter=Q(user=user)))
    return {'annotation_stats':{'annotations':totals['annotations'],'annotated_comments':totals['annotated_comments'],'gold':GoldAnnotation.objects.filter(comment__project=project).count()},'preferences':pref_json(p),'labels':labels_for(project,False),'sources':sources,'my_annotations':totals['mine'],
            'versions':[{'id':v.id,'name':v.name,'sha256':v.sha256,'created_at':v.created_at.isoformat(),'count':len(v.snapshot.get('comments',[]))} for v in project.dataset_versions.order_by('-id')[:30]] if can_manage and not blind and not compact else []}
