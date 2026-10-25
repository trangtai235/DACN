from .common import *

@api
@require_GET
def bootstrap(request):
    projects=list(Project.objects.filter(memberships__user=request.user).order_by('id'))
    if not projects:
        if request.GET.get('project'):raise Http404()
        return JsonResponse({'projects':[],'project':None,'user':{'id':request.user.id,'username':request.user.username,'name':request.user.first_name or request.user.username}})
    pid=request.GET.get('project') or projects[0].id;project=project_for(request,pid);is_manager=manager(project,request.user);blind=in_blind(project,request.user)
    from studio.api.common import studio_bootstrap
    extra=studio_bootstrap(project,request.user)
    from studio.services.projects import ensure as studio_ensure
    from studio.models import Annotation,AIExposure
    qs=Comment.objects.filter(project=project)
    stats={'total':qs.count(),'predicted':qs.filter(ai_label__isnull=False).count(),'first_pass':qs.filter(first_frozen_at__isnull=False).count(),'toxic':qs.filter(first_label='TOXIC').count()}
    models=list(ModelRun.objects.filter(project=project,state='ready').order_by('-id')[:50]);benchmarks=list(BenchmarkRun.objects.filter(project=project).order_by('-id')[:5]) if is_manager and not blind else []
    runs=list(ReviewRun.objects.filter(project=project).order_by('-id')[:10])
    conflicts=ReviewTask.objects.filter(run__project=project,state='conflict').select_related('comment').exclude(reviewer=request.user).exclude(comment__first_actor=request.user)
    members=[{'id':m.user_id,'name':m.user.first_name or m.user.username,'username':m.user.username,'role':m.role} for m in project.memberships.select_related('user')]
    events=[{'action':e.action,'actor':e.actor.first_name or e.actor.username if e.actor else 'Hệ thống','date':e.created_at.isoformat()} for e in AuditEvent.objects.filter(project=project).select_related('actor').order_by('-id')[:8]] if is_manager and not blind else []
    from studio.models import AIExposure,Annotation
    for row in qs[:500]:
        if row.ai_label and not blind and (not extra['preferences']['independent'] or Annotation.objects.filter(comment=row,user=request.user,status='submitted').exists()):AIExposure.objects.get_or_create(comment=row,user=request.user)
    return JsonResponse({**extra,'projects':[{'id':p.id,'name':p.name,'is_demo':p.is_demo,'archived':studio_ensure(p).archived} for p in projects],'project':{'id':project.id,'name':project.name,'description':project.description,'is_demo':project.is_demo,'can_manage':is_manager,'owner':project.owner_id},'stats':stats,'comments':[serialize_comment(r,blind or (extra['preferences']['independent'] and not Annotation.objects.filter(comment=r,user=request.user,status='submitted').exists())) for r in qs.select_related('source').order_by('id')[:500]],'models':[report_model(m) for m in models],'benchmarks':[{'id':b.id,'report':json.loads(b.report)} for b in benchmarks],'runs':[run_json(r) for r in runs] if is_manager and not blind else [{'id':r.id,'policy':r.policy,'budget_seconds':r.budget_seconds,'used_seconds':r.used_seconds,'state':r.state} for r in runs],
     'conflicts':[{'id':t.id,'comment_id':t.comment_id,'text':t.comment.text} for t in conflicts],'members':members,'events':events,'jobs':[report_job(j) for j in Job.objects.filter(project=project,actor=request.user).order_by('-id')[:5]],'api_configured':bool(settings.GEMINI_API_KEY),'youtube_configured':bool(settings.YOUTUBE_API_KEY),'gemini_model':settings.GEMINI_MODEL,'user':{'id':request.user.id,'username':request.user.username,'name':request.user.first_name or request.user.username}})


@api
@require_POST
def create_project(request):
    p=data(request);name=str(p.get('name','')).strip()
    if not name or len(name)>180:raise ValueError('Tên dự án từ 1 đến 180 ký tự.')
    with transaction.atomic():
        obj=Project.objects.create(name=name,description=str(p.get('description',''))[:2000],owner=request.user)
        Membership.objects.create(project=obj,user=request.user,role='manager');audit(obj,request.user,'project_created')
        from core.services.model_registry import register_bundled
        register_bundled(obj)
    return JsonResponse({'id':obj.id})


@api
@require_POST
def add_member(request):
    p=data(request);project=project_for(request,p['project'],True);u=get_object_or_404(User,username=p.get('username',''))
    Membership.objects.get_or_create(project=project,user=u,defaults={'role':'annotator'});return JsonResponse({'ok':True})

