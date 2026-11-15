from .common import *

@api
@require_POST
def first_pass(request,comment_id):
    p=data(request);row=get_object_or_404(Comment,pk=comment_id);project=project_for(request,row.project_id)
    if in_blind(project,request.user):raise PermissionError('Hoàn tất lượt kiểm tra mù trước khi gán lượt đầu có AI.')
    label=p.get('label')
    if label not in ('TOXIC','NON_TOXIC'):raise ValueError('Chọn nhãn hợp lệ.')
    with transaction.atomic():
        from studio.services.projects import mutation_guard
        mutation_guard(project,request.user)
        row=Comment.objects.select_for_update().get(pk=row.id)
        if row.first_frozen_at:raise ValueError('Lượt đầu đã khóa. Dùng quy trình kiểm tra bổ sung.')
        if row.ai_label is None:raise ValueError('Cần có gợi ý hợp lệ trước khi gán lượt đầu.')
        if row.revision!=int(p.get('revision',-1)):raise ValueError('Bình luận đã thay đổi. Tải lại trước khi nộp.')
        row.first_label=label;row.first_actor=request.user;row.first_note=str(p.get('note',''))[:2000]
        row.first_seconds=max(0,min(3600,float(p.get('seconds',0))));row.first_frozen_at=timezone.now();row.origin_group=review.group_for(row.ai_label,label);row.revision+=1;row.save()
        audit(project,request.user,'first_pass',comment=row.id,label=label,group=row.origin_group)
    return JsonResponse({'comment':serialize_comment(row)})


@api
@require_POST
def create_run(request):
    p=data(request);project=project_for(request,p['project'],True);policy=p.get('policy','adaptive');minutes=int(p.get('minutes',30))
    if policy not in ('random','fixed','fixed_explore','adaptive') or not 1<=minutes<=600:raise ValueError('Cấu hình phiên chưa hợp lệ.')
    if not 0<=int(p.get('seed',42))<=4294967295:raise ValueError('Seed từ 0 đến 4294967295.')
    if p.get('grouping_strategy')=='local_api':
        from studio.models import AutoLabelRun
        from reviewing.paired import create
        batch=get_object_or_404(AutoLabelRun,project=project,pk=p['batch_id'],schema__isnull=False)
        obj=create(batch,policy,minutes*60,int(p.get('seed',42)),request.user)
        return JsonResponse({'run':run_json(obj)})
    if p.get('grouping_strategy','legacy_ai_human')!='legacy_ai_human':raise ValueError('grouping_strategy không hợp lệ.')
    ids=list(Comment.objects.filter(project=project,first_frozen_at__isnull=False).order_by('id').values_list('id',flat=True))
    if not ids:raise ValueError('Cần có bình luận đã hoàn tất lượt đầu.')
    obj=ReviewRun.objects.create(project=project,policy=policy,budget_seconds=minutes*60,seed=int(p.get('seed',42)),population=json.dumps(ids))
    audit(project,request.user,'run_created',run=obj.id,policy=policy);return JsonResponse({'run':run_json(obj)})


@api
@require_POST
def claim_review(request,run_id):
    run=get_object_or_404(ReviewRun,pk=run_id);project_for(request,run.project_id)
    from studio.models import PairDecision
    if PairDecision.objects.filter(pair__run__project=run.project,user=request.user,status__in=['blind','preliminary'],exposed_at__isnull=True).exists():
        raise PermissionError('Hoàn tất quyết định độc lập đang mở trước khi nhận lượt mù khác.')
    t=review.claim(run.id,request.user);return JsonResponse({'task':task_json(t)})


@api
@require_POST
def submit_review(request,task_id):
    t=get_object_or_404(ReviewTask,pk=task_id);project_for(request,t.run.project_id);p=data(request)
    t=review.submit(t.id,request.user,p.get('label'),str(p.get('note','')));return JsonResponse({'state':t.state})


@api
@require_POST
def adjudication(request,task_id):
    t=get_object_or_404(ReviewTask,pk=task_id);project_for(request,t.run.project_id);p=data(request)
    if in_blind(t.run.project,request.user):raise PermissionError('Hoàn tất lượt mù trước khi phân xử mẫu khác.')
    if p.get('action')=='open':t=review.start_adjudication(t.id,request.user);return JsonResponse({'task':task_json(t,False)})
    t=review.adjudicate(t.id,request.user,p.get('label'),str(p.get('note','')));return JsonResponse({'state':t.state})

