import random,json
from django.db import transaction
from django.utils import timezone
from core.models import Comment,audit
from .models import ReviewRun,ReviewTask

def group_for(ai,human):
    return {('TOXIC','TOXIC'):'A',('NON_TOXIC','NON_TOXIC'):'B',('NON_TOXIC','TOXIC'):'C',('TOXIC','NON_TOXIC'):'D'}[(ai,human)]
def group_stats(run,batched=False):
    stats={g:{'n':0,'changed':0,'seconds':0,'score':0} for g in 'ABCD'}
    tasks=list(run.tasks.filter(state='complete').select_related('comment').order_by('id'))
    if batched:tasks=tasks[:len(tasks)//5*5]
    for t in tasks:
        s=stats[t.comment.origin_group];s['n']+=1;s['changed']+=int(t.final_label!=t.comment.first_label);s['seconds']+=t.review_seconds+t.adjudication_seconds
    for g,s in stats.items():
        p=(s['changed']+5*.15)/(s['n']+5);cost=(s['seconds']+5*20)/(s['n']+5)
        s['score']=p/max(cost,1)
    return stats
@transaction.atomic
def claim(run_id,user):
    run=ReviewRun.objects.select_for_update().get(pk=run_id)
    existing=run.tasks.filter(reviewer=user,state='claimed').select_related('comment').first()
    if existing:return existing
    if run.state!='active' or run.used_seconds>=run.budget_seconds:raise ValueError('Phiên đã dừng hoặc hết ngân sách.')
    if run.tasks.filter(state__in=['claimed','conflict']).exists():raise ValueError('Phiên đo cấp việc tuần tự. Hoàn tất lượt đang làm hoặc phân xử trước khi cấp mẫu tiếp.')
    assigned=list(run.tasks.values_list('comment_id',flat=True))
    candidates=list(Comment.objects.filter(project=run.project,pk__in=json.loads(run.population),first_frozen_at__isnull=False).exclude(first_actor=user).exclude(pk__in=assigned).order_by('pk'))
    if not candidates:raise ValueError('Không còn mẫu phù hợp. Người kiểm tra thêm phải khác người lượt đầu.')
    rng=random.Random(run.seed+len(assigned)*7919);stats=group_stats(run,batched=True)
    groups={g:[c for c in candidates if c.origin_group==g] for g in 'ABCD'};available=[g for g in 'ABCD' if groups[g]]
    if run.policy=='random':chosen=rng.choice(candidates);reason='P0 · Lấy ngẫu nhiên'
    elif run.policy=='fixed':
        pool=[c for c in candidates if c.origin_group in 'CD'] or candidates;chosen=rng.choice(pool);reason='P1 · Ưu tiên nhóm sửa AI'
    elif run.policy=='fixed_explore':
        explore=len(assigned)%5==4;pool=[c for c in candidates if c.origin_group in ('AB' if explore else 'CD')] or candidates
        chosen=rng.choice(pool);reason='P2 · Thăm dò cố định' if explore else 'P2 · Ưu tiên sửa AI'
    else:
        warm=[g for g in available if not run.tasks.filter(comment__origin_group=g).exists()]
        if warm:g=warm[0];reason='P3 · Khởi động nhóm '+g
        elif len(assigned)%5==4:g=available[(len(assigned)//5)%len(available)];reason='P3 · Thăm dò nhóm '+g
        else:g=max(available,key=lambda v:stats[v]['score']);reason='P3 · Điểm đổi nhãn trên thời gian'
        chosen=rng.choice(groups[g])
    task=ReviewTask.objects.create(run=run,comment=chosen,reviewer=user,reason=reason)
    audit(run.project,user,'review_claim',task=task.id,run=run.id)
    return task
@transaction.atomic
def submit(task_id,user,label,note=''):
    task=ReviewTask.objects.select_for_update().select_related('comment','run').get(pk=task_id)
    if task.reviewer_id!=user.id:raise PermissionError('Không phải lượt kiểm tra được giao.')
    if task.state!='claimed':raise ValueError('Lượt này đã được nộp; không ghi lại lần hai.')
    if label not in ('TOXIC','NON_TOXIC'):raise ValueError('Nhãn không hợp lệ.')
    now=timezone.now();elapsed=max(.001,(now-task.created_at).total_seconds())
    task.blind_label=label;task.note=note[:2000];task.review_seconds=elapsed
    if label==task.comment.first_label:task.state='complete';task.final_label=label;task.completed_at=now
    else:task.state='conflict'
    task.save();run=ReviewRun.objects.select_for_update().get(pk=task.run_id);run.used_seconds+=elapsed
    if run.used_seconds>=run.budget_seconds:run.state='exhausted'
    run.save();audit(run.project,user,'review_submit',task=task.id,label=label,seconds=round(elapsed,3))
    return task
@transaction.atomic
def start_adjudication(task_id,user):
    task=ReviewTask.objects.select_for_update().select_related('comment','run').get(pk=task_id)
    if task.state!='conflict':raise ValueError('Mẫu không còn chờ phân xử.')
    if user.id in (task.reviewer_id,task.comment.first_actor_id):raise PermissionError('Người phân xử phải khác hai người đã gán nhãn.')
    if task.adjudicator_id and task.adjudicator_id!=user.id:raise ValueError('Mẫu đã có người đang phân xử.')
    if not task.adjudication_started_at:task.adjudicator=user;task.adjudication_started_at=timezone.now();task.save()
    return task
@transaction.atomic
def adjudicate(task_id,user,label,note):
    task=start_adjudication(task_id,user)
    if label not in ('TOXIC','NON_TOXIC') or not note.strip():raise ValueError('Chọn nhãn và ghi lý do phân xử.')
    elapsed=max(.001,(timezone.now()-task.adjudication_started_at).total_seconds())
    task.final_label=label;task.state='complete';task.adjudication_seconds=elapsed;task.completed_at=timezone.now();task.note+='\nPhân xử: '+note[:2000];task.save()
    run=ReviewRun.objects.select_for_update().get(pk=task.run_id);run.used_seconds+=elapsed
    if run.used_seconds>=run.budget_seconds:run.state='exhausted'
    run.save();audit(run.project,user,'adjudicate',task=task.id,label=label,seconds=elapsed)
    return task
