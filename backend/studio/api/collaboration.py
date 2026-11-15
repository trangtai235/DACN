"""Sentence-level paired workflow; legacy auto-label endpoints remain readable."""
import re
from django.http import Http404
from .common import *
from experiments.models import ModelRun, ReferenceLabel
from integrations.models import ProviderConnection
from reviewing.models import ReviewTask
from studio.services import collaboration as service
from studio.services.adaptation import current_schema, compatibility, readiness, freeze_dataset, schema_labels, checksum
from core.services.jobs import enqueue
from django.db.models import F


def visible(project, user):
    if in_blind(project, user): raise PermissionError('Hoàn tất lượt mù trước khi xem dự đoán, nhãn khác hoặc báo cáo.')


def decision_json(d):
    return {'id': d.pk, 'label': d.label, 'preliminary_label': d.preliminary_label, 'status': d.status,
            'schema_id':d.schema_id,'schema_snapshot':d.schema.snapshot,
            'revision': d.revision, 'exposed_at': d.exposed_at.isoformat() if d.exposed_at else None,
            'viewed_predictions': d.viewed_predictions, 'history': d.history, 'note': d.note} if d else None


def prediction_json(pred):
    return {'id': pred.id, 'label': pred.label, 'spans': pred.spans, 'source': pred.provider, 'model': pred.model_version,
            'latency_ms': pred.latency_ms, 'input_tokens': pred.input_tokens, 'output_tokens': pred.output_tokens,
            'estimated_cost_usd': pred.estimated_cost_usd} if pred else None


@api
@require_GET
def dashboard(request):
    project = project_for(request, request.GET['project'])
    source=resolve_source(project,request.GET.get('source'))
    if in_blind(project, request.user):
        decisions=PairDecision.objects.filter(pair__run__project=project,user=request.user,status__in=['blind','preliminary'],exposed_at__isnull=True)
        if source:decisions=decisions.filter(pair__comment__source=source)
        return JsonResponse({'blind_pairs':list(decisions.values_list('pair_id',flat=True)),'blind':True,'scope_source_id':source.pk if source else None})
    schema = current_schema(project)
    runs=project.auto_label_runs.filter(schema__isnull=False)
    if source:runs=runs.filter(pairs__comment__source=source).distinct()
    return JsonResponse({'scope_source_id':source.pk if source else None,'schema': {'id': schema.pk, 'version': schema.version, 'sha256': schema.sha256, **schema.snapshot},
        'schemas': [{'id': s.id, 'version': s.version, 'sha256': s.sha256, 'snapshot': s.snapshot} for s in project.label_schemas.order_by('-version')[:20]],
        'runs': [{'id': r.pk, 'count':r.pairs.filter(comment__source=source).count() if source else r.pairs.count(),'total_count':r.pairs.count(), 'schema_id': r.schema_id, 'options': r.options,
                  'local_job': report_job(r.local_job) if r.local_job else None, 'api_job': report_job(r.llm_job) if r.llm_job else None}
                 for r in runs.order_by('-id')[:30]],
        'models': [{'id': m.pk, 'name': m.name, 'compatibility': compatibility(m, schema),
                    'validation': json.loads(m.report).get('validation'), 'incumbent_validation': json.loads(m.report).get('incumbent_validation'), 'dataset_id': json.loads(m.report).get('feedback_dataset_id')}
                   for m in project.model_runs.filter(state='ready').order_by('-id')],
        'connections': [{'id': c.pk, 'name': c.name, 'model': c.model} for c in project.connections.filter(enabled=True)],
        'readiness': readiness(project, schema),
        'datasets': [{'id': d.pk, 'sha256': d.sha256, 'counts': {k: len(v) for k, v in d.snapshot['splits'].items()}}
                     for d in project.feedback_datasets.order_by('-id')[:20]]})


@api
@require_POST
def start(request):
    p = data(request); project = project_for(request, p['project'], True); visible(project, request.user)
    run = service.start_run(project, request.user, p)
    return JsonResponse({'id': run.id})


@api
@require_GET
def pairs(request, run_id):
    run = get_object_or_404(AutoLabelRun, pk=run_id, schema__isnull=False); project_for(request, run.project_id)
    visible(run.project, request.user)
    source=resolve_source(run.project,request.GET.get('source'))
    pairs=run.pairs.all()
    if source:pairs=pairs.filter(comment__source=source)
    rows = []
    for pair in pairs.select_related('comment', 'run__schema','run__local_job','run__llm_job', 'local_prediction', 'api_prediction').order_by('id'):
        state = service.pair_state(pair)
        escalated=pair.decisions.filter(status__in=['escalated','needs_context','undecidable']).exists()
        gold=GoldAnnotation.objects.filter(comment=pair.comment).exists()
        confirmed=pair.decisions.filter(status='confirmed').exists()
        review_state='awaiting_adjudication' if escalated else 'adjudicated' if gold else 'reviewed' if confirmed else 'awaiting_review'
        # Listing never reveals model labels before opening the dedicated flow.
        rows.append({'id': pair.id, 'comment_id': pair.comment_id,'source_id':pair.comment.source_id, 'text': pair.text, 'state': state,
                     'mine': decision_json(pair.decisions.filter(user=request.user).first()),
                     'escalated': escalated,'review_state':review_state,
                     'feedback_approved':FeedbackApproval.objects.filter(comment=pair.comment,revoked=False,decision__schema_id=F('schema_id'),
                         decision_revision=F('decision__revision'),decision__status='confirmed',text_hash=pair.text_hash).exists(),
                     'can_adjudicate':manager(run.project,request.user) and not pair.decisions.filter(user=request.user).exclude(status='draft').exists()
                                      and not pair.comment.annotations.filter(user=request.user).exists()})
    return JsonResponse({'scope_source_id':source.pk if source else None,'rows': rows, 'schema': run.schema.snapshot, 'demo': run.options.get('demo', False)})


@api
@require_GET
def detail(request, pair_id):
    pair = get_object_or_404(PredictionPair.objects.select_related('run__schema', 'run__project','run__local_job','run__llm_job', 'comment__source'), pk=pair_id)
    project_for(request, pair.run.project_id)
    source=resolve_source(pair.run.project,request.GET.get('source'))
    if source and pair.comment.source_id!=source.pk:raise Http404()
    if ReviewTask.objects.filter(run__project=pair.run.project, reviewer=request.user, state='claimed').exists():
        raise PermissionError('Không xem cặp/nhãn con người trong lượt kiểm tra mù.')
    statuses=service.branch_statuses(pair)
    state = service.pair_state(pair,statuses)
    if PairDecision.objects.filter(pair__run__project=pair.run.project,user=request.user,status__in=['blind','preliminary'],exposed_at__isnull=True).exclude(pair=pair).exists():
        raise PermissionError('Hoàn tất mẫu độc lập đang mở trước khi nhận mẫu khác.')
    if request.GET.get('supervision')=='1':
        project_for(request,pair.run.project_id,True);visible(pair.run.project,request.user)
        gold=GoldAnnotation.objects.filter(comment=pair.comment).select_related('label').first()
        if gold or pair.decisions.exists():audit(pair.run.project,request.user,'human_supervision_view',comment=pair.comment_id,pair=pair.pk)
        return JsonResponse({'id':pair.pk,'text':pair.text,'schema':current_schema(pair.run.project).snapshot,
            'decisions':[{'user_id':d.user_id,'user_name':d.user.first_name or d.user.username,**decision_json(d),
                          'approved':FeedbackApproval.objects.filter(decision=d,decision_revision=d.revision,revoked=False).exists()}
                         for d in pair.decisions.select_related('user')],
            'gold':{'label':gold.label.key if gold.label_id else None,'note':gold.note,'revision':gold.revision} if gold else None})
    if request.GET.get('adjudication') == '1':
        project_for(request, pair.run.project_id, True); visible(pair.run.project, request.user)
        if pair.decisions.filter(user=request.user).exclude(status='draft').exists() or pair.comment.annotations.filter(user=request.user).exists():
            raise PermissionError('Người phân xử phải khác những người đã gán.')
        audit(pair.run.project,request.user,'human_supervision_view',comment=pair.comment_id,pair=pair.pk)
        return JsonResponse({'id': pair.pk, 'text': pair.text, 'schema':current_schema(pair.run.project).snapshot, 'annotation_revision': 0,
            'gold_revision': GoldAnnotation.objects.filter(comment=pair.comment).values_list('revision', flat=True).first() or 0,
            'decisions': [{'user_id': d.user_id, **decision_json(d)} for d in pair.decisions.all()]})
    with transaction.atomic():
        from reviewing.paired import clock_tick
        d,_=PairDecision.objects.select_for_update().get_or_create(pair=pair,user=request.user,
            defaults={'schema':pair.run.schema,'status':'blind' if service.pair_disagrees(pair) else 'draft'})
        # Start only while an undecided record is visible; reopening a confirmed record is not labor yet.
        if d.status in ('blind','draft','preliminary') and d.clock.get('state')!='active':
            clock_tick(d,'start','first_decision');d.save(update_fields=['clock'])
    own = Annotation.objects.filter(comment=pair.comment, user=request.user).first()
    reveal = bool(d and d.exposed_at and d.viewed_predictions == [pk for pk in (pair.local_prediction_id, pair.api_prediction_id) if pk]) and not in_blind(pair.run.project, request.user)
    return JsonResponse({'workspace_version':1,'prediction_status':statuses,'id': pair.id, 'text': pair.text, 'context': pair.context, 'state': state,
        'comment_id':pair.comment_id,'source_id':pair.comment.source_id,'source':pair.comment.source.name,'source_kind':pair.comment.source.kind,
        'video_id':pair.comment.source.external_id if pair.comment.source.kind=='youtube' else '',
        'external_id':pair.comment.external_id,'author':pair.comment.author,
        'published_at':pair.comment.published_at.isoformat() if pair.comment.published_at else None,
        'tokens':[{'text':m.group(),'start':m.start(),'end':m.end()} for m in re.finditer(r'\S+',pair.text)],
        'my_spans':own.spans if own else [],'annotation_count':pair.comment.annotations.filter(status='submitted').count(),
        'requires_preliminary':service.pair_disagrees(pair) and not d.preliminary_label and not d.exposed_at,
        'human_schema':current_schema(pair.run.project).snapshot,
        'schema': pair.run.schema.snapshot, 'mine': decision_json(d), 'annotation_revision': own.revision if own else 0,
        'clock':d.clock,'prior_assistance':not bool(d.exposed_at) and (AIExposure.objects.filter(comment=pair.comment,user=request.user).exists()
            or pair.comment_id in service.human_label_exposures(pair.run.project,request.user)),
        'revealed': reveal, 'local': prediction_json(pair.local_prediction) if reveal else None,
        'api': prediction_json(pair.api_prediction) if reveal else None,
        'branches': pair.branches if reveal else {b: {'state': v['state']} for b, v in pair.branches.items()}})


@api
@require_POST
def expose(request, pair_id):
    pair = get_object_or_404(PredictionPair.objects.select_related('run__schema', 'run__project', 'comment'), pk=pair_id)
    project_for(request, pair.run.project_id)
    source=resolve_source(pair.run.project,data(request).get('source_id'))
    if source and pair.comment.source_id!=source.pk:raise ValueError('Bình luận không thuộc video/nguồn đã chọn.')
    if ReviewTask.objects.filter(run__project=pair.run.project, reviewer=request.user, state='claimed').exists():
        raise PermissionError('Đang có lượt kiểm tra mù theo ngân sách.')
    if PairDecision.objects.filter(pair__run__project=pair.run.project, user=request.user, exposed_at__isnull=True,
                                   status__in=['blind', 'preliminary']).exclude(pair=pair).exists():
        raise PermissionError('Hoàn tất lượt mù khác trước khi mở gợi ý.')
    with transaction.atomic():
        d, _ = PairDecision.objects.select_for_update().get_or_create(pair=pair, user=request.user, defaults={'schema': pair.run.schema, 'status': 'draft'})
        if service.pair_disagrees(pair) and not d.preliminary_label and not d.exposed_at:
            raise ValueError('Chọn nhãn độc lập và lưu trước khi xem hai gợi ý.')
        if not d.exposed_at: d.exposed_at = timezone.now()
        d.viewed_predictions = [pk for pk in (pair.local_prediction_id, pair.api_prediction_id) if pk]
        d.save(); AIExposure.objects.get_or_create(comment=pair.comment, user=request.user)
        audit(pair.run.project, request.user, 'pair_exposure', pair=pair.pk, predictions=d.viewed_predictions)
    return JsonResponse({'ok': True})


@api
@require_POST
def decision_clock(request,pair_id):
    from reviewing.paired import clock_tick
    pair=get_object_or_404(PredictionPair,pk=pair_id);project_for(request,pair.run.project_id)
    source=resolve_source(pair.run.project,data(request).get('source_id'))
    if source and pair.comment.source_id!=source.pk:raise ValueError('Bình luận không thuộc video/nguồn đã chọn.')
    with transaction.atomic():
        d=get_object_or_404(PairDecision.objects.select_for_update(),pair=pair,user=request.user)
        action=data(request).get('action')
        if d.status not in ('blind','draft','preliminary'):raise ValueError('Quyết định đã hoàn tất; mở bản sửa riêng khi cần.')
        value=clock_tick(d,action,'first_decision');d.save(update_fields=['clock'])
    return JsonResponse({'clock':value})


@api
@require_POST
def retry(request, run_id):
    run = get_object_or_404(AutoLabelRun, pk=run_id, schema__isnull=False)
    project_for(request, run.project_id, True); visible(run.project, request.user)
    source=resolve_source(run.project,data(request).get('source_id'))
    if source and run.pairs.exclude(comment__source=source).exists():raise ValueError('Lượt cũ chứa nhiều video. Tạo lượt riêng cho video đã chọn trước khi chạy lại model.')
    branch = data(request).get('branch')
    if branch not in ('local', 'api'): raise ValueError('Nhánh không hợp lệ.')
    field = 'local_job' if branch == 'local' else 'llm_job'
    with transaction.atomic():
        run = AutoLabelRun.objects.select_for_update().get(pk=run.pk)
        old = getattr(run, field)
        if not old: raise ValueError('Nhánh chưa được cấu hình; tạo lượt mới.')
        if old.status in ('queued', 'running'): raise ValueError('Chờ/dừng job cũ trước khi retry.')
        for pair in run.pairs.select_for_update():
            if pair.branches[branch]['state'] in ('error', 'running'):
                pair.branches[branch]['state'] = 'pending'; pair.save(update_fields=['branches'])
        job = enqueue(run.project, request.user, 'paired_predict', {'run_id': run.pk, 'branch': branch})
        setattr(run, field, job); run.save(update_fields=[field])
        audit(run.project, request.user, 'pair_retry', run=run.pk, branch=branch, job=job.pk)
    return JsonResponse({'job_id': job.pk})


@api
@require_POST
def resume(request,run_id):
    old=get_object_or_404(AutoLabelRun,pk=run_id,schema__isnull=False)
    project_for(request,old.project_id,True);visible(old.project,request.user)
    payload=data(request)
    run=service.resume_run(old.pk,request.user,payload)
    pair_id=run.pairs.filter(comment_id=payload.get('comment_id')).values_list('id',flat=True).first()
    return JsonResponse({'id':run.pk,'count':run.pairs.count(),'pair_id':pair_id})


@api
@require_POST
def save(request, pair_id):
    pair = get_object_or_404(PredictionPair, pk=pair_id); project_for(request, pair.run.project_id)
    if ReviewTask.objects.filter(run__project=pair.run.project, reviewer=request.user, state='claimed').exists():
        raise PermissionError('Hoàn tất lượt kiểm tra mù trước.')
    return JsonResponse({'decision': decision_json(service.decision(pair_id, request.user, data(request)))})


@api
@require_POST
def adjudicate(request, pair_id):
    pair = get_object_or_404(PredictionPair, pk=pair_id); project_for(request, pair.run.project_id, True); visible(pair.run.project, request.user)
    p = data(request)
    if pair.decisions.filter(user=request.user).exclude(status='draft').exists() or pair.comment.annotations.filter(user=request.user).exists():
        raise PermissionError('Người phân xử phải khác những người đã gán mẫu.')
    if not str(p.get('note', '')).strip(): raise ValueError('Cần lý do phân xử.')
    with transaction.atomic():
        old=GoldAnnotation.objects.select_for_update().filter(comment=pair.comment).first()
        if (old.revision if old else 0)!=int(p.get('gold_revision',0)):raise ValueError('Gold đã đổi; tải lại trước khi phân xử.')
        d = service.decision(pair.pk, request.user, {**p, 'action': 'confirm'}, adjudicating=True)
        GoldAnnotation.objects.update_or_create(comment=pair.comment, defaults={'label': d.annotation.label, 'note': d.note, 'adjudicator': request.user,'revision':(old.revision if old else 0)+1})
        pair.decisions.exclude(pk=d.pk).filter(status__in=['escalated', 'needs_context', 'undecidable']).update(status='resolved')
        audit(pair.run.project, request.user, 'pair_gold', pair=pair.pk, decision=d.pk)
    return JsonResponse({'ok': True})


@api
@require_POST
def approve(request, decision_id):
    d = get_object_or_404(PairDecision.objects.select_related('pair__run__project', 'pair__comment', 'schema'), pk=decision_id)
    project = project_for(request, d.pair.run.project_id, True); visible(project, request.user)
    p = data(request)
    with transaction.atomic():
        mutation_guard(project, request.user, True)
        if p.get('revoke'):
            FeedbackApproval.objects.filter(decision=d).update(revoked=True)
        else:
            from studio.services.adaptation import text_hash
            if d.status != 'confirmed' or d.schema.sha256!=current_schema(project).sha256 or d.pair.text_hash!=text_hash(d.pair.comment.text,d.pair.comment.context):
                raise ValueError('Chỉ duyệt quyết định con người hiện hành, đã xác nhận.')
            gold=GoldAnnotation.objects.filter(comment=d.pair.comment).first()
            if gold and (not gold.label_id or gold.label.key!=d.label):raise ValueError('Quyết định khác gold hiện hành; không duyệt phản hồi này.')
            if d.pair.comment.annotations.filter(status='submitted').exclude(label__key=d.label).exists():
                gold = GoldAnnotation.objects.filter(comment=d.pair.comment, label__key=d.label).first()
                if not gold: raise ValueError('Đang có nhãn người bất đồng; cần phân xử trước.')
            FeedbackApproval.objects.update_or_create(decision=d, defaults={'comment': d.pair.comment, 'schema': d.schema,
                'decision_revision':d.revision,
                'label': d.label, 'text': d.pair.text, 'text_hash': d.pair.text_hash,
                'source_id_snapshot': d.pair.comment.source_id, 'approved_by': request.user, 'revoked': False})
        audit(project, request.user, 'feedback_approval', decision=d.pk, revoke=bool(p.get('revoke')))
    return JsonResponse({'ok': True})


@api
@require_POST
def partition(request):
    p = data(request); project = project_for(request, p['project'], True); visible(project, request.user)
    if p.get('role') not in ('support', 'pilot', 'test', 'reference'): raise ValueError('Vai trò dữ liệu không hợp lệ.')
    with transaction.atomic():
        for c in project.comments.filter(pk__in=p.get('comment_ids', [])):
            if c.prediction_pairs.exists() or FeedbackApproval.objects.filter(comment=c).exists():
                raise ValueError('Chốt partition trước khi dùng mẫu; không đổi test đã dùng thành support.')
            DataPartition.objects.update_or_create(comment=c, defaults={'role': p['role']})
    return JsonResponse({'ok': True})


@api
@require_POST
def dataset(request):
    p = data(request); project = project_for(request, p['project'], True); visible(project, request.user)
    d = freeze_dataset(project, current_schema(project), int(p.get('seed', 42)))
    return JsonResponse({'id': d.pk, 'sha256': d.sha256})


@api
@require_POST
def training(request):
    p = data(request); project = project_for(request, p['project'], True); visible(project, request.user)
    d = get_object_or_404(FeedbackDataset, project=project, pk=p['dataset_id'])
    if d.schema.sha256 != current_schema(project).sha256: raise ValueError('Dataset thuộc schema cũ.')
    job = enqueue(project, request.user, 'feedback_train', {'dataset_id': d.pk, 'algorithm': p.get('algorithm', 'logistic_regression')})
    return JsonResponse({'job_id': job.pk})


@api
@require_POST
def activate(request):
    p = data(request); project = project_for(request, p['project'], True); visible(project, request.user)
    with transaction.atomic():
        prefs = mutation_guard(project, request.user, True)
        model = get_object_or_404(ModelRun, project=project, pk=p['model_id'], state='ready')
        if compatibility(model, current_schema(project))['state'] != 'compatible': raise ValueError('Model chưa tương thích schema.')
        if not str(p.get('note', '')).strip(): raise ValueError('Ghi lý do kích hoạt/rollback sau khi xem validation.')
        previous = prefs.active_model_id; prefs.active_model = model; prefs.save(update_fields=['active_model'])
        audit(project, request.user, 'model_activated', previous=previous, model=model.pk, note=p['note'], selection='validation + manager; not test')
    return JsonResponse({'ok': True})


@api
@require_GET
def experiment_report(request):
    from studio.services.experiment_reports import comparison
    project = project_for(request, request.GET['project'], True); visible(project, request.user)
    ids = [int(v) for v in request.GET.get('runs', '').split(',') if v][:20]
    batches = list(project.auto_label_runs.filter(pk__in=ids, schema__isnull=False).order_by('id'))
    if len(batches) != len(set(ids)): raise ValueError('Một lượt không thuộc dự án hoặc là dữ liệu cũ chưa có schema.')
    response = JsonResponse(comparison(batches, request.GET.get('bootstrap') == '1'), json_dumps_params={'ensure_ascii': False, 'indent': 2})
    response['Content-Disposition'] = 'attachment; filename="paired-experiment.json"'
    return response
