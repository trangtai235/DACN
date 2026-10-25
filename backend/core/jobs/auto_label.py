"""Independent workers use one frozen corpus and label schema for a paired run."""
import time
from types import SimpleNamespace
from django.db import transaction
from core.services.transformer_models import artifact_digest, predict as transformer_predict
from core.services.providers import load_artifact
from integrations.models import ProviderConnection
from integrations.registry import predict as api_predict, snapshot
from integrations.providers.base import parse_result
from studio.models import AutoLabelRun, AutoLabelResult
from .runner import tick
from pathlib import Path


def run(job, payload):
    batch = AutoLabelRun.objects.get(pk=payload['run_id'], project=job.project)
    branch = payload['branch']
    if branch not in ('local', 'llm'):
        raise ValueError('Luồng gán nhãn không hợp lệ.')
    started = time.perf_counter()
    elapsed = job.checkpoint.get('elapsed_ms', 0)
    def progress(message):
        done = batch.results.filter(branch=branch).count()
        tick(job, done / max(1, len(batch.items)) * 100, message,
             {'elapsed_ms': elapsed + (time.perf_counter() - started) * 1000})
    try:
        progress('Đang chuẩn bị ' + branch)
        if branch == 'local':
            config = batch.model_config
            if artifact_digest(config['artifact_path']) != config['artifact_sha256']:
                raise ValueError('Trọng số đã đổi. Tạo lượt mới để không trộn kết quả.')
            model = SimpleNamespace(**config)
        else:
            connection = ProviderConnection.objects.get(pk=batch.connection_config['id'], project=batch.project)
            if snapshot(connection) != batch.connection_config:
                raise ValueError('Cấu hình API đã đổi. Tạo lượt mới để giữ cùng điều kiện.')
        completed = set(batch.results.filter(branch=branch).values_list('item_index', flat=True))
        for index, item in enumerate(batch.items):
            if index in completed:
                continue
            progress(f'{branch}: {index + 1}/{len(batch.items)}')
            t0 = time.perf_counter()
            if branch == 'llm':
                if snapshot(ProviderConnection.objects.get(pk=connection.pk)) != batch.connection_config:
                    raise ValueError('Cấu hình API đã đổi trong khi chạy. Tạo lượt mới.')
                value = api_predict(connection, item['text'], batch.labels, sentence_only=True)
            elif model.algorithm == 'transformer_bio':
                value = transformer_predict(model, [item['text']])[0]
            else:
                artifact = Path(model.artifact_path) / 'classifier.joblib'
                classifier = load_artifact(str(artifact), artifact.stat().st_mtime_ns)
                predicted = int(classifier.predict([item['text']])[0])
                value = {'label': config['label_keys'][predicted], 'spans': []}
            parsed = parse_result(value, item['text'], batch.labels)
            # Save successful calls before the next cancellation checkpoint.
            with transaction.atomic():
                AutoLabelResult.objects.get_or_create(run=batch, branch=branch, item_index=index, defaults={
                    **parsed, 'latency_ms': (time.perf_counter() - t0) * 1000,
                    'input_tokens': value.get('input_tokens', 0),
                    'output_tokens': value.get('output_tokens', 0),
                    'estimated_cost_usd': value.get('estimated_cost_usd', 0),
                })
            progress(f'{branch}: đã gán {index + 1}/{len(batch.items)}')
        return {'run_id': batch.id, 'branch': branch, 'processed': len(batch.items)}
    finally:
        from core.models import Job
        job.checkpoint['elapsed_ms'] = elapsed + (time.perf_counter() - started) * 1000
        Job.objects.filter(pk=job.pk).update(checkpoint=job.checkpoint)
