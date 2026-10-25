import csv,hashlib,io,json,re,uuid
from functools import wraps
from pathlib import Path
from django.conf import settings
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.models import User
from django.db import transaction,connection,IntegrityError
from django.http import JsonResponse,HttpResponse,Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET,require_POST
from core.models import Project,Membership,Source,Comment,Prediction,Job,AuditEvent,audit
from core.services.jobs import enqueue
from core.forms import RegistrationForm
from experiments.models import ModelRun,BenchmarkRun,ReferenceLabel
from experiments.training import metrics
from reviewing.models import ReviewRun,ReviewTask
from reviewing import services as review


def data(request):
    if request.content_type=='application/json':
        try:
            value=json.loads(request.body or '{}')
            if not isinstance(value,dict):raise ValueError('JSON cần là một object.')
            return value
        except (ValueError,TypeError):raise ValueError('JSON không hợp lệ.')
    return request.POST


def api(fn):
    @wraps(fn)
    def wrapped(request,*a,**kw):
        if not request.user.is_authenticated:return JsonResponse({'error':'Vui lòng đăng nhập.'},status=401)
        try:return fn(request,*a,**kw)
        except PermissionError as e:return JsonResponse({'error':str(e)},status=403)
        except (ValueError,KeyError,TypeError) as e:return JsonResponse({'error':str(e)},status=400)
    return wrapped


def project_for(request,pid,manage=False):
    project=get_object_or_404(Project,pk=pid,memberships__user=request.user)
    if manage and not manager(project,request.user):raise PermissionError('Chức năng dành cho người quản lý dự án.')
    if request.method=='POST' and request.path not in ('/api/studio/project-settings','/api/studio/profile/save','/api/studio/jobs/'+str(0)+'/action'):
        # Controls that do not alter annotation data remain available while locked.
        allowed=('/api/studio/connections','/api/studio/selection','/api/studio/members','/api/studio/invite','/api/studio/jobs/','/api/studio/auto-label/runs/')
        if not request.path.startswith(allowed):
            from studio.services.projects import writable
            writable(project)
    return project


def manager(project,user):return project.owner_id==user.id or Membership.objects.filter(project=project,user=user,role='manager').exists()


def in_blind(project,user):return ReviewTask.objects.filter(run__project=project,reviewer=user,state='claimed').exists()


def serialize_comment(row,hide=False):
    result={'id':row.id,'text':row.text,'source':row.source.name,'context':row.context,'revision':row.revision,'created_at':row.created_at.isoformat()}
    if not hide:result.update({'ai_label':row.ai_label,'ai_provider':row.ai_provider,'first_label':row.first_label,'group':row.origin_group,'first_actor':row.first_actor_id})
    return result


def report_model(m):return {'algorithm':m.algorithm,'id':m.id,'name':m.name,'state':m.state,'report':json.loads(m.report),'created_at':m.created_at.isoformat()}


def report_job(j):return {'id':j.id,'kind':j.kind,'status':j.status,'progress':j.progress,'message':j.message,'result':json.loads(j.result),'cancel_requested':j.cancel_requested,'updated_at':j.updated_at.isoformat()}


def run_json(run):return {'id':run.id,'policy':run.policy,'budget_seconds':run.budget_seconds,'used_seconds':run.used_seconds,'state':run.state,'stats':review.group_stats(run),'completed':run.tasks.filter(state='complete').count(),'conflicts':run.tasks.filter(state='conflict').count()}


def task_json(t,blind=True):
    result={'id':t.id,'run_id':t.run_id,'comment_id':t.comment_id,'text':t.comment.text,'context':t.comment.context,'state':t.state,'started_at':t.created_at.isoformat()}
    if not blind:result.update({'first_label':t.comment.first_label,'blind_label':t.blind_label,'first_note':t.comment.first_note,'note':t.note,'reason':t.reason})
    return result


def final_labels(project,run=None):
    rows=Comment.objects.filter(project=project)
    if run:rows=rows.filter(pk__in=json.loads(run.population))
    results={r.id:r.first_label for r in rows}
    if run:
        for t in run.tasks.filter(state='complete'):results[t.comment_id]=t.final_label
    return results

