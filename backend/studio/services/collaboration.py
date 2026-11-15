import json
import time
import uuid
from pathlib import Path
from django.db import transaction
from django.utils import timezone
from core.models import Comment, Prediction, AuditEvent, audit
from core.services.jobs import enqueue
from core.services.providers import local_predict, model_for
from core.services.transformer_models import artifact_digest
from integrations.models import ProviderConnection
from integrations.registry import snapshot, predict as api_predict
from integrations.providers.base import parse_result
from studio.models import (AutoLabelRun, PredictionPair, PairDecision, Annotation, AnnotationEvent,
                           AIExposure, GoldAnnotation, ProjectLabel)
from studio.services.projects import mutation_guard, ensure, validate_spans, resolve_source
from .adaptation import current_schema, schema_labels, compatibility, text_hash, retrieve, PROMPT_VERSION


def human_label_exposures(project,user):
    """Reading another person's decision also disqualifies an independent review."""
    return {json.loads(detail)['comment'] for detail in AuditEvent.objects.filter(project=project,actor=user,
        action='human_supervision_view').values_list('detail',flat=True)}


def pair_state(pair):
    if pair.text_hash != text_hash(pair.comment.text, pair.comment.context) or pair.run.schema.sha256 != current_schema(pair.run.project).sha256:
        return 'stale'
    states = [pair.branches.get(b, {}).get('state', 'missing') for b in ('local', 'api')]
    if 'incompatible' in states: return 'incompatible'
    if any(s in ('pending', 'running') for s in states): return 'pending'
    if any(s != 'complete' for s in states): return 'partial_error'
    if not pair.local_prediction_id or not pair.api_prediction_id: return 'partial_error'
    return 'agreement' if pair.local_prediction.label == pair.api_prediction.label else 'disagreement'


def pair_disagrees(pair):
    return bool(pair.local_prediction_id and pair.api_prediction_id and
        all(pair.branches.get(b,{}).get('state')=='complete' for b in ('local','api')) and
        pair.local_prediction.label!=pair.api_prediction.label)


@transaction.atomic
def start_run(project, actor, payload):
    mutation_guard(project, actor, True)
    source=resolve_source(project,payload.get('source_id'))
    key = str(payload.get('request_key') or uuid.uuid4())
    if len(key) > 80: raise ValueError('request_key tối đa 80 ký tự.')
    previous = AutoLabelRun.objects.filter(project=project, request_key=key).first()
    if previous:
        if source and previous.pairs.exclude(comment__source=source).exists():raise ValueError('Mã yêu cầu đã được dùng cho video/nguồn khác.')
        return previous
    schema = current_schema(project)
    if len(schema_labels(schema)) < 2: raise ValueError('Cần ít nhất hai nhãn câu đang bật.')
    model_id = payload.get('model_id', ensure(project).active_model_id)
    model = model_for(project, model_id) if model_id else None
    connection_id = payload.get('connection_id', ensure(project).active_connection_id)
    connection = ProviderConnection.objects.filter(project=project, pk=connection_id, enabled=True).first() if connection_id else None
    if connection_id and not connection: raise ValueError('API không thuộc dự án hoặc đang tắt.')
    compatible = compatibility(model, schema)
    config = {}
    if compatible['state'] == 'compatible':
        config = {'id': model.pk, 'name': model.name, 'algorithm': model.algorithm, 'artifact_path': model.artifact_path,
                  'artifact_sha256': artifact_digest(model.artifact_path)}
    qs = project.comments.filter(unusable=False).order_by('id')
    if source: qs = qs.filter(source=source)
    if payload.get('comment_ids'): qs = qs.filter(pk__in=payload['comment_ids'])
    comments = list(qs[:2000])
    if not comments: raise ValueError('Không có bình luận trong phạm vi đã chọn (tối đa 2.000/lượt).')
    run = AutoLabelRun.objects.create(project=project, actor=actor, schema=schema, request_key=key,
        labels=schema_labels(schema), items=[{'id': c.id, 'text': c.text, 'context': c.context} for c in comments],
        model_config=config, connection_config=snapshot(connection) if connection else {},
        options={'few_shot': bool(payload.get('few_shot', True)), 'prompt_version': PROMPT_VERSION,
                 'compatibility': compatible, 'demo': project.is_demo,'source_id':source.pk if source else None})
    for c in comments:
        examples = retrieve(project, schema, c) if connection and run.options['few_shot'] else []
        PredictionPair.objects.create(run=run, comment=c, text=c.text, context=c.context, text_hash=text_hash(c.text, c.context),
            branches={'local': {'state': 'pending' if config else ('missing' if not model else 'incompatible'), 'message': compatible['reason']},
                      'api': {'state': 'pending' if connection else 'missing', 'examples': examples}})
    if config: run.local_job = enqueue(project, actor, 'paired_predict', {'run_id': run.id, 'branch': 'local'})
    if connection: run.llm_job = enqueue(project, actor, 'paired_predict', {'run_id': run.id, 'branch': 'api'})
    run.save(update_fields=['local_job', 'llm_job'])
    audit(project, actor, 'pair_run_created', run=run.pk, schema=schema.pk, request_key=key)
    return run


def artifact_signature(path):
    return tuple((p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in sorted(Path(path).iterdir()) if p.is_file())


def run_branch(job, payload):
    from core.jobs.runner import tick, Cancelled
    run = AutoLabelRun.objects.get(pk=payload['run_id'], project=job.project)
    branch = payload['branch']
    if branch not in ('local', 'api'): raise ValueError('Nhánh không hợp lệ.')
    local_error=None; signature=None
    if branch=='local':
        try:
            if artifact_digest(run.model_config['artifact_path'])!=run.model_config['artifact_sha256']:raise ValueError('Artifact đã đổi; tạo lượt mới.')
            signature=artifact_signature(run.model_config['artifact_path'])
        except (OSError,ValueError):local_error='Không có artifact hoặc artifact đã đổi; tạo lượt mới/cài đúng trọng số.'
    for index, pair_id in enumerate(run.pairs.order_by('id').values_list('id', flat=True)):
        tick(job, index / max(1, run.pairs.count()) * 100, 'Đang chạy nhánh ' + branch)
        with transaction.atomic():
            pair = PredictionPair.objects.select_for_update().select_related('comment').get(pk=pair_id)
            state = pair.branches[branch]
            if state['state'] not in ('pending', 'error'): continue
            state.update(state='running', started_at=timezone.now().isoformat(), attempts=state.get('attempts', 0) + 1)
            pair.save(update_fields=['branches'])
        started = time.perf_counter()
        try:
            if branch == 'local':
                if local_error:raise ValueError(local_error)
                if artifact_signature(run.model_config['artifact_path'])!=signature:raise ValueError('Artifact thay đổi trong khi chạy; tạo lượt mới.')
                if current_schema(run.project).sha256 != run.schema.sha256:
                    raise ValueError('Schema đã đổi; tạo lượt mới.')
                value = local_predict(run.project, [pair.text], run.model_config['id'])[0]
                config = run.model_config
            else:
                connection = ProviderConnection.objects.get(pk=run.connection_config['id'], project=run.project)
                if snapshot(connection) != run.connection_config: raise ValueError('Cấu hình API đã đổi; tạo lượt mới.')
                prompt_context = {'guidelines': run.schema.snapshot['guidelines'], 'examples': state.get('examples', []),
                                  'context': pair.context, 'prompt_version': PROMPT_VERSION}
                value = api_predict(connection, pair.text, run.labels, sentence_only=True, prompt_context=prompt_context)
                config = {**run.connection_config, **prompt_context}
            parsed = parse_result(value, pair.text, run.labels, sentence_only=branch == 'api')
            # Keep local Unicode offsets; sentence comparison does not compare spans.
            with transaction.atomic():
                pair = PredictionPair.objects.select_for_update().get(pk=pair.pk)
                mutation_guard(run.project, job.actor, True)
                field = 'local_prediction' if branch == 'local' else 'api_prediction'
                if not getattr(pair, field + '_id'):
                    pred = Prediction.objects.create(comment=pair.comment, provider=branch,
                        model_version=value.get('model_version', config.get('name', config.get('model', branch))),
                        config_snapshot={**config, 'schema_id': run.schema_id, 'schema_sha256': run.schema.sha256,
                                         'text_hash': pair.text_hash, 'run_id': run.id, 'level': 'sentence_single'},
                        **parsed, latency_ms=(time.perf_counter()-started)*1000,
                        input_tokens=value.get('input_tokens', 0), output_tokens=value.get('output_tokens', 0),
                        estimated_cost_usd=value.get('estimated_cost_usd', 0))
                    setattr(pair, field, pred)
                pair.branches[branch].update(state='complete', finished_at=timezone.now().isoformat(), error='')
                pair.save()
        except Cancelled:
            raise
        except Exception as exc:
            with transaction.atomic():
                pair = PredictionPair.objects.select_for_update().get(pk=pair.pk)
                pair.branches[branch].update(state='error', error=str(exc)[:300] if isinstance(exc, ValueError) else 'Dịch vụ lỗi/timeout; chưa có nhãn.', finished_at=timezone.now().isoformat())
                pair.save(update_fields=['branches'])
    return {'run_id': run.id, 'branch': branch, 'errors': sum(p.branches[branch]['state'] == 'error' for p in run.pairs.all())}


@transaction.atomic
def decision(pair_id, user, payload, adjudicating=False):
    # AutoLabelRun.schema is nullable for legacy runs. PostgreSQL cannot lock the
    # nullable side of its outer join; lock the pair only, then prefs/comment below.
    pair = PredictionPair.objects.select_for_update(of=('self',)).select_related('run__project', 'run__schema', 'comment').get(pk=pair_id)
    source=resolve_source(pair.run.project,payload.get('source_id'))
    if source and pair.comment.source_id!=source.pk:raise ValueError('Bình luận không thuộc video/nguồn đã chọn.')
    mutation_guard(pair.run.project, user)
    # Lock the shared annotation row through its comment just like the original workspace.
    Comment.objects.select_for_update().get(pk=pair.comment_id)
    if pair.text_hash!=text_hash(pair.comment.text,pair.comment.context) and payload.get('action','confirm') not in ('skip','escalate','needs_context','undecidable'):
        raise ValueError('Văn bản/ngữ cảnh đã đổi. Tạo lượt mới trước khi quyết định.')
    d, _ = PairDecision.objects.select_for_update().get_or_create(pair=pair, user=user, defaults={'schema': pair.run.schema, 'status': 'draft'})
    if d.revision != int(payload.get('revision', 0)): raise ValueError('Quyết định đã đổi ở phiên khác; tải lại.')
    action = payload.get('action', 'confirm'); label = payload.get('label', '')
    from reviewing.paired import clock_tick
    schema=current_schema(pair.run.project)
    keys = {x['key'] for x in schema_labels(schema)}
    if action in ('preliminary', 'confirm') and label not in keys: raise ValueError('Chọn đúng một nhãn trong schema.')
    if d.schema_id!=schema.pk:
        for event in d.history:
            event.setdefault('schema_id',d.schema_id);event.setdefault('schema_snapshot',d.schema.snapshot)
    d.schema=schema
    if action == 'preliminary':
        if d.exposed_at: raise ValueError('Đã xem gợi ý; không ghi lại thành lượt độc lập.')
        d.preliminary_label = label; d.status = 'preliminary'
        clock_tick(d,'heartbeat','first_decision')
    elif action in ('confirm', 'skip', 'escalate', 'needs_context', 'undecidable'):
        if pair_disagrees(pair) and action == 'confirm' and not d.preliminary_label and not d.exposed_at and not adjudicating:
            raise ValueError('Cần chọn nhãn độc lập trước khi xem/giữ quyết định bất đồng.')
        own = Annotation.objects.filter(comment=pair.comment, user=user).select_related('label').first()
        if (own.revision if own else 0) != int(payload.get('annotation_revision', 0)):
            raise ValueError('Nhãn đã đổi ở phiên khác; tải lại.')
        before = {'label': own.label.key if own and own.label else None, 'revision': own.revision if own else 0,
                  'spans': own.spans if own else []}
        # Human spans are independent of model spans. Older clients that omit them preserve existing work.
        spans = own.spans if own else []
        if action == 'confirm' and 'spans' in payload:
            spans = validate_spans(pair.text, payload['spans'], pair.run.project)
        d.status = {'confirm': 'confirmed', 'skip': 'skipped', 'escalate': 'escalated'}.get(action, action)
        d.label = label if action == 'confirm' else ''
        clock_tick(d,'finish','first_decision')
        own, _ = Annotation.objects.update_or_create(comment=pair.comment, user=user, defaults={
            'label': ProjectLabel.objects.get(project=pair.run.project, key=label,enabled=True) if action == 'confirm' else None,
            'status': 'submitted' if action == 'confirm' else 'skipped', 'note': str(payload.get('note', ''))[:4000],
            'spans': spans,
            'seconds':d.clock.get('active',0),
            'assisted': bool(d.exposed_at or (own and own.assisted) or AIExposure.objects.filter(comment=pair.comment, user=user).exists()
                             or pair.comment_id in human_label_exposures(pair.run.project,user)),
            'revision': before['revision'] + 1})
        d.annotation = own
        AnnotationEvent.objects.create(comment=pair.comment, user=user, action='pair_decision', before=before,
            after={'label': d.label, 'spans': own.spans, 'revision': own.revision, 'pair_id': pair.pk, 'schema_id': d.schema_id, 'predictions': d.viewed_predictions})
    else: raise ValueError('Thao tác quyết định không hợp lệ.')
    d.note = str(payload.get('note', ''))[:4000]; d.revision += 1
    d.history.append({'revision': d.revision, 'action': action, 'label': label, 'at': timezone.now().isoformat(), 'predictions': d.viewed_predictions,
                      'schema_id':schema.pk,'schema_snapshot':schema.snapshot,
                      'annotation_revision': d.annotation.revision if d.annotation_id else None})
    d.save(); audit(pair.run.project, user, 'pair_decision', pair=pair.pk, decision=d.pk, revision=d.revision, action_type=action)
    return d
