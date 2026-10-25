import csv
import io
from pathlib import Path
from collections import Counter
from core.services.jobs import enqueue
from core.services.providers import model_for
from core.services.transformer_models import artifact_digest
from integrations.models import ProviderConnection
from integrations.registry import snapshot
from integrations.providers.base import validate_endpoint
from .common import *


def configured_connection(project):
    prefs = ensure(project)
    qs = ProviderConnection.objects.filter(project=project, enabled=True).exclude(encrypted_key='').exclude(kind='ollama')
    return qs.filter(pk=prefs.active_connection_id).first() or qs.order_by('id').first()


def job_summary(job, run, branch):
    if job is None:
        return None
    results = run.results.filter(branch=branch)
    counts = Counter(results.values_list('label', flat=True))
    return {'id': job.pk, 'status': job.status, 'message': job.message, 'progress': job.progress,
            'completed': results.count(), 'elapsed_ms': job.checkpoint.get('elapsed_ms', 0),
            'distribution': [{'key': l['key'], 'name': l['name'], 'color': l['color'], 'count': counts[l['key']]} for l in run.labels]}


def summary(run):
    return {'id': run.pk, 'created_at': run.created_at.isoformat(), 'count': len(run.items), 'labels': run.labels,
            'model': run.model_config.get('name'), 'connection': run.connection_config.get('name'),
            'local': job_summary(run.local_job, run, 'local'), 'llm': job_summary(run.llm_job, run, 'llm')}


@api
@require_GET
def runs(request):
    project = project_for(request, request.GET['project'])
    connection = configured_connection(project)
    return JsonResponse({'runs': [summary(r) for r in project.auto_label_runs.select_related('local_job', 'llm_job').order_by('-id')[:30]],
                         'api_ready': bool(connection), 'connection': connection.name if connection else None})


@api
@require_POST
def start(request):
    p = data(request)
    project = project_for(request, p['project'], True)
    with transaction.atomic():
        mutation_guard(project, request.user, True)
        if Job.objects.filter(project=project, kind='auto_label', status__in=['queued', 'running']).exists():
            raise ValueError('Đang có lượt tự gán nhãn. Chờ hoàn tất hoặc dừng trước khi tạo lượt mới.')
        model = model_for(project, p.get('model_id'))
        if not model:
            raise ValueError('Chọn một model ML Local sẵn sàng trước khi chạy.')
        labels = labels_for(project)
        expected = json.loads(model.report).get('label_keys', ['NON_TOXIC', 'TOXIC'])
        if {l['key'] for l in labels} != set(expected):
            raise ValueError('Bộ nhãn dự án phải khớp chính xác với ML Local: ' + ', '.join(expected) + '. Hai luồng sẽ dùng cùng bộ nhãn này.')
        config = {'id': model.pk, 'name': model.name, 'algorithm': model.algorithm,
                  'artifact_path': model.artifact_path, 'label_keys': expected}
        path = Path(model.artifact_path).resolve()
        if not any(path.is_relative_to(root.resolve()) for root in (settings.BASE_DIR / 'artifacts', settings.PRIVATE_DATA)):
            raise ValueError('Đường dẫn model không hợp lệ.')
        marker = Path(model.artifact_path) / 'verified.json'
        if model.algorithm == 'transformer_bio' and marker.exists():
            config['artifact_sha256'] = json.loads(marker.read_text(encoding='utf-8'))['artifact_sha256']
        else:
            config['artifact_sha256'] = artifact_digest(model.artifact_path)
        qs = project.comments.filter(unusable=False).select_related('source').order_by('id')
        if p.get('source_id'):
            source = get_object_or_404(Source, pk=p['source_id'], project=project)
            qs = qs.filter(source=source)
        items = [{'id': c.pk, 'text': c.text, 'source': c.source.name} for c in qs]
        if not items:
            raise ValueError('Chưa có bình luận hợp lệ trong phạm vi đã chọn.')
        connection = configured_connection(project)
        if connection:
            validate_endpoint(connection.base_url)
        run = AutoLabelRun.objects.create(project=project, actor=request.user, labels=labels, items=items,
                                         model_config=config, connection_config=snapshot(connection) if connection else {})
        run.local_job = enqueue(project, request.user, 'auto_label', {'run_id': run.pk, 'branch': 'local'})
        if connection:
            run.llm_job = enqueue(project, request.user, 'auto_label', {'run_id': run.pk, 'branch': 'llm'})
        run.save(update_fields=['local_job', 'llm_job'])
        audit(project, request.user, 'auto_label.start', run=run.pk, count=len(items), paired=bool(connection))
    return JsonResponse({'id': run.pk})


def result_json(result):
    if result is None:
        return None
    return {'label': result.label, 'spans': result.spans, 'latency_ms': result.latency_ms}


def result_rows(run):
    results = {(r.item_index, r.branch): r for r in run.results.all()}
    for index, item in enumerate(run.items):
        local = results.get((index, 'local'))
        llm = results.get((index, 'llm'))
        different = local is not None and llm is not None and local.label != llm.label
        yield {**item, 'index': index, 'local': result_json(local), 'llm': result_json(llm), 'different': different}


@api
@require_GET
def detail(request, run_id):
    run = get_object_or_404(AutoLabelRun.objects.select_related('local_job', 'llm_job'), pk=run_id)
    project_for(request, run.project_id)
    rows = list(result_rows(run))
    paired = [r for r in rows if r['local'] and r['llm']]
    differences = sum(r['different'] for r in paired)
    if request.GET.get('download') == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['comment_id', 'text', 'source', 'ml_local', 'llm_api', 'different', 'ml_ms', 'llm_ms'])
        for row in rows:
            values = [row['id'], row['text'], row['source'], (row['local'] or {}).get('label', ''),
                      (row['llm'] or {}).get('label', ''), row['different'],
                      (row['local'] or {}).get('latency_ms', ''), (row['llm'] or {}).get('latency_ms', '')]
            writer.writerow(["'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@')) else v for v in values])
        response = HttpResponse('\ufeff' + output.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="auto-label-{run.pk}.csv"'
        return response
    if request.GET.get('different') == '1':
        rows = [r for r in rows if r['different']]
    query = request.GET.get('q', '').strip().casefold()
    if query:
        rows = [r for r in rows if query in r['text'].casefold()]
    page = max(1, int(request.GET.get('page', 1)))
    return JsonResponse({'run': summary(run), 'rows': rows[(page - 1) * 30:page * 30], 'total': len(rows),
                         'page': page, 'paired_count': len(paired), 'different_count': differences})


@api
@require_POST
def control(request, run_id):
    p = data(request)
    with transaction.atomic():
        run = get_object_or_404(AutoLabelRun.objects.select_for_update(), pk=run_id)
        project_for(request, run.project_id, True)
        branch = p.get('branch')
        if branch not in ('local', 'llm'):
            raise ValueError('Luồng không hợp lệ.')
        field = 'local_job' if branch == 'local' else 'llm_job'
        job = getattr(run, field)
        if not job:
            raise ValueError('Lượt này không có luồng API.')
        if p.get('action') == 'cancel' and job.status in ('queued', 'running'):
            job.cancel_requested = True
            job.save(update_fields=['cancel_requested'])
        elif p.get('action') == 'retry' and job.status in ('failed', 'cancelled'):
            writable(run.project)
            new_job = enqueue(run.project, request.user, 'auto_label', json.loads(job.payload), checkpoint=job.checkpoint)
            setattr(run, field, new_job)
            run.save(update_fields=[field])
        else:
            raise ValueError('Thao tác không phù hợp trạng thái hiện tại.')
    return JsonResponse({'ok': True})
