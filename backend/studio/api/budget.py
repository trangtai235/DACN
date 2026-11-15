from .common import *
from reviewing.models import ReviewRun, ReviewTask
from reviewing.paired import clock_tick, replay, report, population
from core.api.common import run_json, task_json


@api
@require_GET
def overview(request):
    project = project_for(request, request.GET['project'])
    runs = project.review_runs.filter(grouping_strategy='local_api').order_by('-id')
    tasks = ReviewTask.objects.filter(run__project=project, run__grouping_strategy='local_api')
    reports=[run_json(r) for r in runs[:30]]
    if not manager(project,request.user) or in_blind(project,request.user):
        for value in reports:value.pop('stats',None)
    return JsonResponse({'runs': reports,
        'claimed': [task_json(t) for t in tasks.filter(reviewer=request.user, state='claimed')],
        'conflicts': [{'id': t.pk, 'text': population(t.run)[t.comment_id]['text']} for t in tasks.filter(state='conflict')
                      if request.user.id not in (t.reviewer_id, population(t.run)[t.comment_id]['first_actor'])]})


@api
@require_POST
def control(request, run_id):
    run = get_object_or_404(ReviewRun, pk=run_id, grouping_strategy='local_api'); project_for(request, run.project_id, True)
    action = data(request).get('action')
    if action not in ('pause', 'resume'): raise ValueError('Chỉ pause/resume.')
    with transaction.atomic():
        run = ReviewRun.objects.select_for_update().get(pk=run.pk)
        if action == 'resume' and run.used_seconds >= run.budget_seconds: raise ValueError('Đã hết ngân sách.')
        run.state = 'paused' if action == 'pause' else 'active'; run.save(update_fields=['state'])
        if action == 'pause':
            for task in run.tasks.select_for_update().filter(state__in=['claimed', 'conflict']):
                if task.clock.get('state') == 'active': clock_tick(task, 'pause', task.clock.get('phase', 'review')); task.save(update_fields=['clock'])
        audit(run.project, request.user, 'review_' + action, run=run.pk)
    return JsonResponse({'run': run_json(run)})


@api
@require_POST
def clock(request, task_id):
    t = get_object_or_404(ReviewTask, pk=task_id, run__grouping_strategy='local_api'); project_for(request, t.run.project_id)
    if request.user.id != (t.reviewer_id if t.state == 'claimed' else t.adjudicator_id): raise PermissionError('Không có quyền trên đồng hồ này.')
    if t.state not in ('claimed', 'conflict'): raise ValueError('Mẫu đã hoàn tất.')
    action = data(request).get('action')
    if t.run.state == 'paused' and action in ('resume', 'heartbeat'): raise ValueError('Phiên đang tạm dừng.')
    with transaction.atomic():
        t = ReviewTask.objects.select_for_update().get(pk=t.pk)
        value = clock_tick(t, action, 'review' if t.state == 'claimed' else 'adjudication'); t.save(update_fields=['clock'])
    return JsonResponse({'clock': value})


@api
@require_GET
def evaluation(request, run_id):
    run = get_object_or_404(ReviewRun, pk=run_id, grouping_strategy='local_api'); project_for(request, run.project_id, True)
    if in_blind(run.project, request.user): raise PermissionError('Không xem tham chiếu/báo cáo trong lượt mù.')
    value = report(run)
    if request.GET.get('replay') == '1':
        seeds = [int(v) for v in request.GET.get('seeds', str(run.seed)).split(',')[:20]]
        policies = ('random', 'fixed', 'fixed_explore', 'adaptive')
        value['replays'] = [replay(run, policy, seed, run.budget_seconds) for policy in policies for seed in seeds]
    response = JsonResponse(value, json_dumps_params={'ensure_ascii': False, 'indent': 2})
    if request.GET.get('download') == '1': response['Content-Disposition'] = f'attachment; filename="review-{run.pk}.json"'
    return response
