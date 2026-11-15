"""Batch learning uses the existing sklearn pipeline and frozen, source-grouped feedback."""
import csv
import json
from django.conf import settings
from django.db import transaction
from experiments.training import train, metrics
from experiments.models import ModelRun
from core.services.providers import local_predict
from core.models import audit
from studio.models import FeedbackDataset
from studio.services.adaptation import current_schema, schema_labels, compatibility
from studio.services.projects import mutation_guard
from .runner import tick


def run(job, payload):
    dataset = FeedbackDataset.objects.get(pk=payload['dataset_id'], project=job.project)
    if current_schema(job.project).sha256 != dataset.schema.sha256: raise ValueError('Schema đã đổi; không train trộn schema.')
    out = settings.PRIVATE_DATA / 'models' / ('feedback-' + str(job.id)); out.mkdir(parents=True, exist_ok=True)
    keys = [l['key'] for l in schema_labels(dataset.schema)]
    paths = {}
    for split, rows in dataset.snapshot['splits'].items():
        path = out / (split + '.csv'); paths[split] = path
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['id', 'text', 'label', 'source']); writer.writeheader(); writer.writerows([{k: r[k] for k in writer.fieldnames} for r in rows])
    report = train(paths['train'], paths['validation'], paths['test'], out,
                   lambda n, m: tick(job, n, m), algorithm_key=payload.get('algorithm', 'logistic_regression'), label_keys=keys, seed=dataset.seed)
    report.update(schema_sha256=dataset.schema.sha256, feedback_dataset_id=dataset.pk, feedback_dataset_sha256=dataset.sha256,
                  seed=dataset.seed, demo=dataset.snapshot['demo'], source='Approved human feedback; frozen IDs and source groups',
                  activation='Manager must compare validation; no automatic replacement; test is reporting only.')
    with transaction.atomic():
        prefs = mutation_guard(job.project, job.actor, True)
        incumbent = prefs.active_model
        if incumbent and compatibility(incumbent, dataset.schema)['state'] == 'compatible':
            rows = dataset.snapshot['splits']['validation']
            pred = local_predict(job.project, [r['text'] for r in rows], incumbent.pk)
            report['incumbent_validation'] = {'model_id': incumbent.pk, **metrics([keys.index(r['label']) for r in rows], [keys.index(v['label']) for v in pred], keys)}
        (out / 'metrics.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        model = ModelRun.objects.create(project=job.project, name='Phản hồi duyệt · ' + str(job.id),
            algorithm=report['algorithm'], artifact_path=str(out), test_path=str(paths['test']), report=json.dumps(report, ensure_ascii=False))
        audit(job.project, job.actor, 'feedback_model_candidate', model=model.pk, dataset=dataset.pk)
    return {'model_id': model.pk, 'dataset_id': dataset.pk, 'validation': report['validation'], 'incumbent_validation': report.get('incumbent_validation')}
