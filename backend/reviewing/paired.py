"""New multiclass grouping, explicit clocks and replay. Legacy A/B/C/D is unchanged."""
import json
import random
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from core.models import audit
from experiments.models import ReferenceLabel
from experiments.training import metrics
from reviewing.models import ReviewRun, ReviewTask
from studio.services.adaptation import checksum, schema_labels
from studio.services.collaboration import pair_state

HEARTBEAT_CAP = 20.0


def population(run):
    return {row['id']: row for row in run.input_snapshot['rows']}


def stats(run, tasks=None):
    result = {g: {'n': 0, 'changed': 0, 'seconds': 0, 'score': 0} for g in ('agreement', 'disagreement')}
    rows = population(run)
    for name, group in result.items():
        group['population']=sum(row['group']==name for row in rows.values())
        group['class_distribution']={l['key']:sum(row['group']==name and row['first_label']==l['key'] for row in rows.values())
                                     for l in run.input_snapshot['schema']['labels'] if l['enabled']}
    tasks = list(run.tasks.filter(state='complete').order_by('id')) if tasks is None else tasks
    # P3 updates after a full batch of five observed outcomes, as in the legacy policy.
    for task in tasks[:len(tasks)//5*5]:
        row = rows[task.comment_id]; group = result[row['group']]
        group['n'] += 1; group['changed'] += int(task.final_label != row['first_label'])
        group['seconds'] += task.review_seconds + task.adjudication_seconds
    for group in result.values():
        group['score'] = ((group['changed'] + .75)/(group['n'] + 5)) / max(1, (group['seconds'] + 100)/(group['n'] + 5))
    return result


def select(rows, policy, seed, assigned, observed):
    candidates = sorted(rows, key=lambda r: r['id']); rng = random.Random(seed + assigned * 7919)
    if not candidates: raise ValueError('Không còn mẫu phù hợp.')
    reason = 'P0: random'
    if policy in ('fixed', 'fixed_explore'):
        target = 'agreement' if policy == 'fixed_explore' and assigned % 5 == 4 else 'disagreement'
        pool = [r for r in candidates if r['group'] == target] or candidates
        reason = 'P1/P2: ' + target
    elif policy == 'adaptive':
        available = sorted({r['group'] for r in candidates})
        warm = [g for g in available if not observed[g]['n']]
        target = warm[assigned % len(warm)] if warm else (available[(assigned//5) % len(available)] if assigned % 5 == 4 else max(available, key=lambda g: observed[g]['score']))
        pool = [r for r in candidates if r['group'] == target]; reason = 'P3 proxy change/active-second: ' + target
    else: pool = candidates
    return rng.choice(pool), reason


@transaction.atomic
def create(batch, policy, seconds, seed, actor):
    rows = []
    for pair in batch.pairs.select_related('comment', 'run__schema', 'local_prediction', 'api_prediction').order_by('id'):
        state = pair_state(pair)
        if state not in ('agreement', 'disagreement'): continue
        decision = pair.decisions.filter(status='confirmed').order_by('id').first()
        if not decision: continue
        rows.append({'id': pair.comment_id, 'pair_id': pair.id, 'text': pair.text, 'context': pair.context,
                     'text_hash': pair.text_hash, 'source': pair.comment.source_id, 'first_label': decision.label,
                     'first_actor': decision.user_id, 'decision_id': decision.pk, 'decision_revision': decision.revision,
                     'first_active_seconds':decision.clock.get('active',0),'first_idle_seconds':decision.clock.get('idle',0),
                     'local': pair.local_prediction.label, 'api': pair.api_prediction.label,
                     'local_prediction': pair.local_prediction_id, 'api_prediction': pair.api_prediction_id,
                     'group': state})
    if not rows: raise ValueError('Cần cặp hợp lệ và quyết định lượt đầu đã xác nhận.')
    snapshot = {'rows': rows, 'schema': batch.schema.snapshot, 'schema_sha256': batch.schema.sha256,
                'batch_id': batch.pk, 'demo': batch.options.get('demo', False), 'clock_protocol': 'heartbeat-cap-20s-v1',
                'selection': 'P3 uses observed label changes per active second, not probability of correct fixes'}
    snapshot['sha256'] = checksum(snapshot)
    run = ReviewRun.objects.create(project=batch.project, grouping_strategy='local_api', policy=policy, seed=seed,
        budget_seconds=seconds, population=json.dumps([r['id'] for r in rows]), input_snapshot=snapshot)
    audit(batch.project, actor, 'paired_review_created', run=run.pk, snapshot_sha256=snapshot['sha256'])
    return run


def clock_tick(task, action, phase='review'):
    now = timezone.now(); clock = task.clock or {'state': 'paused', 'active': 0, 'idle': 0, 'events': [], 'phase': phase}
    if clock.get('last_at'):
        delta = max(0, (now - datetime.fromisoformat(clock['last_at'])).total_seconds())
        credit = min(delta, HEARTBEAT_CAP) if clock['state'] == 'active' else 0
        clock['active'] += credit; clock['idle'] += delta-credit
    if action in ('resume', 'start'): clock['state'] = 'active'
    elif action in ('pause', 'finish'): clock['state'] = 'paused'
    elif action != 'heartbeat': raise ValueError('Thao tác đồng hồ không hợp lệ.')
    clock['last_at'] = now.isoformat(); clock['phase'] = phase
    if action != 'heartbeat': clock['events'].append({'action': action, 'at': now.isoformat(), 'phase': phase})
    task.clock = clock
    return clock


@transaction.atomic
def claim(run_id, user):
    run = ReviewRun.objects.select_for_update().get(pk=run_id)
    existing = run.tasks.filter(reviewer=user, state='claimed').first()
    if existing: return existing
    if run.state != 'active' or run.used_seconds >= run.budget_seconds: raise ValueError('Phiên dừng hoặc hết ngân sách; không cấp việc mới.')
    if run.tasks.filter(state__in=['claimed', 'conflict']).exists(): raise ValueError('Hoàn thành mẫu đang làm/phân xử trước khi cấp mẫu tiếp.')
    assigned = list(run.tasks.values_list('comment_id', flat=True))
    from studio.models import Annotation, AIExposure
    seen = set(Annotation.objects.filter(comment__project=run.project, user=user).values_list('comment_id', flat=True))
    seen.update(AIExposure.objects.filter(comment__project=run.project, user=user).values_list('comment_id', flat=True))
    from studio.services.collaboration import human_label_exposures
    seen.update(human_label_exposures(run.project,user))
    rows = [r for r in population(run).values() if r['id'] not in assigned and r['first_actor'] != user.id and r['id'] not in seen]
    row, reason = select(rows, run.policy, run.seed, len(assigned), stats(run))
    task = ReviewTask.objects.create(run=run, comment_id=row['id'], reviewer=user, reason=reason)
    clock_tick(task, 'start'); task.save(update_fields=['clock'])
    audit(run.project, user, 'paired_review_claim', task=task.pk, reason=reason, ordinal=len(assigned), seed=run.seed)
    return task


@transaction.atomic
def submit(task_id, user, label, note):
    task = ReviewTask.objects.select_for_update().select_related('run').get(pk=task_id)
    if task.reviewer_id != user.id: raise PermissionError('Không phải mẫu được giao.')
    if task.state != 'claimed': raise ValueError('Mẫu đã nộp.')
    if label not in {r['key'] for r in task.run.input_snapshot['schema']['labels'] if r['enabled']}:
        raise ValueError('Nhãn không thuộc schema đã chụp.')
    clock = clock_tick(task, 'finish'); task.review_seconds = clock['active']; task.blind_label = label; task.note = note[:2000]
    if label == population(task.run)[task.comment_id]['first_label']:
        task.final_label = label; task.state = 'complete'; task.completed_at = timezone.now()
    else: task.state = 'conflict'
    task.save(); charge(task.run_id, task.review_seconds)
    audit(task.run.project, user, 'paired_review_submit', task=task.pk, active=task.review_seconds, idle=clock['idle'])
    return task


def charge(run_id, seconds):
    run = ReviewRun.objects.select_for_update().get(pk=run_id); run.used_seconds += seconds
    if run.used_seconds >= run.budget_seconds: run.state = 'exhausted'
    run.save()


@transaction.atomic
def open_adjudication(task_id, user):
    task = ReviewTask.objects.select_for_update().select_related('run').get(pk=task_id)
    row = population(task.run)[task.comment_id]
    if task.state != 'conflict': raise ValueError('Không chờ phân xử.')
    if user.id in (task.reviewer_id, row['first_actor']): raise PermissionError('Người thứ ba phải khác hai người gán.')
    if task.adjudicator_id and task.adjudicator_id != user.id: raise PermissionError('Đã có người phân xử.')
    if not task.adjudication_started_at:
        task.adjudicator = user; task.adjudication_started_at = timezone.now()
        queue_wait=max(0,(task.adjudication_started_at-datetime.fromisoformat(task.clock['last_at'])).total_seconds()) if task.clock.get('last_at') else 0
        task.clock = {**task.clock, 'review_idle': task.clock.get('idle', 0)+queue_wait, 'active': 0, 'idle': 0, 'last_at': None}
        clock_tick(task, 'start', 'adjudication'); task.save()
    return task


@transaction.atomic
def adjudicate(task_id, user, label, note):
    task = open_adjudication(task_id, user)
    if not note.strip() or label not in {r['key'] for r in task.run.input_snapshot['schema']['labels'] if r['enabled']}:
        raise ValueError('Chọn nhãn và ghi lý do.')
    clock_tick(task, 'finish', 'adjudication'); task.adjudication_seconds = task.clock['active']
    task.final_label = label; task.state = 'complete'; task.completed_at = timezone.now(); task.note += '\nPhân xử: ' + note[:2000]
    task.save(); charge(task.run_id, task.adjudication_seconds)
    return task


def report(run):
    rows = list(population(run).values()); tasks = {t.comment_id: t for t in run.tasks.all()}
    refs = dict(ReferenceLabel.objects.filter(comment_id__in=[r['id'] for r in rows]).values_list('comment_id', 'label'))
    keys = [r['key'] for r in run.input_snapshot['schema']['labels'] if r['enabled']]
    paired = [r for r in rows if refs.get(r['id']) in keys]
    def final(row):
        t = tasks.get(row['id']); return t.final_label if t and t.state == 'complete' else row['first_label']
    comparisons = {}
    for name in ('local', 'api', 'first_label', 'final'):
        if paired: comparisons[name] = metrics([keys.index(refs[r['id']]) for r in paired], [keys.index(final(r) if name == 'final' else r[name]) for r in paired], keys)
    fixed = sum(r['first_label'] != refs[r['id']] and final(r) == refs[r['id']] for r in paired)
    harmed = sum(r['first_label'] == refs[r['id']] and final(r) != refs[r['id']] for r in paired)
    agreements = [r for r in paired if r['group'] == 'agreement']
    return {'run_id': run.pk, 'demo': run.input_snapshot.get('demo', False), 'grouping_strategy': run.grouping_strategy,
        'snapshot_sha256': run.input_snapshot['sha256'], 'seed': run.seed, 'policy': run.policy,
        'population': len(rows), 'reference_coverage': len(paired)/max(1, len(rows)), 'metrics': comparisons,
        'fixed': fixed if paired else None, 'harmed': harmed if paired else None, 'net_fixes': fixed-harmed if paired else None,
        'both_wrong': sum(r['local'] != refs[r['id']] for r in agreements), 'agreement_reference_n': len(agreements),
        'both_wrong_rate': sum(r['local'] != refs[r['id']] for r in agreements)/len(agreements) if agreements else None,
        'pending': sum(not tasks.get(r['id']) or tasks[r['id']].state != 'complete' for r in rows),
        'budget_seconds': run.budget_seconds, 'active_seconds': run.used_seconds,
        'first_decision_active_seconds':sum(r.get('first_active_seconds',0) for r in rows),
        'first_decision_idle_seconds':sum(r.get('first_idle_seconds',0) for r in rows),
        'overrun_seconds': max(0, run.used_seconds-run.budget_seconds),
        'idle_seconds': sum(t.clock.get('idle', 0)+t.clock.get('review_idle', 0) for t in tasks.values()),
        'adjudication_seconds': sum(t.adjudication_seconds for t in tasks.values()),
        'limitations': 'Heartbeat-capped activity is an operational proxy, not standardized labor. Missing references are not scored. No independent human study or confidence interval is inferred.'}


def replay(run, policy, seed, budget):
    rows = list(population(run).values())
    observed = {t.comment_id: t for t in run.tasks.filter(state='complete')}
    if set(observed) != {r['id'] for r in rows}: raise ValueError('Replay yêu cầu đã quan sát đầy đủ kết quả con người của toàn bộ quần thể; không mô phỏng nhãn.')
    order = []; consumed = 0; completed = []
    while rows and consumed < budget:
        row, reason = select(rows, policy, seed, len(order), stats(run, completed)); task = observed[row['id']]
        consumed += task.review_seconds + task.adjudication_seconds
        order.append({'id': row['id'], 'reason': reason, 'cumulative_active_seconds': consumed})
        completed.append(task); rows = [r for r in rows if r['id'] != row['id']]
    refs = dict(ReferenceLabel.objects.filter(comment_id__in=observed).values_list('comment_id','label'))
    original=list(population(run).values()); selected={t.comment_id for t in completed}
    scored=[r for r in original if r['id'] in refs]
    final=lambda r: observed[r['id']].final_label if r['id'] in selected else r['first_label']
    fixed=sum(r['first_label']!=refs[r['id']] and final(r)==refs[r['id']] for r in scored)
    harmed=sum(r['first_label']==refs[r['id']] and final(r)!=refs[r['id']] for r in scored)
    keys=[r['key'] for r in run.input_snapshot['schema']['labels'] if r['enabled']]
    return {'seed': seed, 'policy': policy, 'budget_seconds': budget, 'order': order, 'active_seconds': consumed,
            'overrun_seconds': max(0, consumed-budget), 'pending':len(rows),
            'net_fixes':fixed-harmed if scored else None,'fixed':fixed if scored else None,'harmed':harmed if scored else None,
            'final_metrics':metrics([keys.index(refs[r['id']]) for r in scored],[keys.index(final(r)) for r in scored],keys) if scored else None,
            'kind': 'replay of fully observed history, not a new human experiment'}
