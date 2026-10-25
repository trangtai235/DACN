"""Register verified, complete Transformer artifacts; retire legacy choices."""
import json
from django.conf import settings
from django.db import transaction
from experiments.models import ModelRun

BUNDLED_MODELS = [('phobert-base','PhoBERT-base'),('xlmr-base','XLM-R base'),('xlmr-large','XLM-R large')]
BUNDLE_DIRECTORY = 'vihos-full'
@transaction.atomic
def register_bundled(project):
    from studio.services.projects import ensure
    prefs=ensure(project)
    root=settings.BASE_DIR/'artifacts'/'transformers'/BUNDLE_DIRECTORY
    ready=[]
    for key,name in BUNDLED_MODELS:
        path=root/key
        marker=path/'verified.json'
        if not marker.exists():continue
        verification=json.loads(marker.read_text(encoding='utf-8'))
        if not verification.get('inference_passed'):continue
        metrics=json.loads((path/'metrics.json').read_text(encoding='utf-8')) if (path/'metrics.json').exists() else {}
        report={'label_keys':['NON_TOXIC','TOXIC'],'task':'token_classification','sentence_rule':'TOXIC if any toxic span; otherwise NON_TOXIC','counts':{'train':metrics.get('n_train',0)},'span_metrics':metrics.get('test',{}),'original_metrics':metrics,'verification':verification}
        model,_=ModelRun.objects.update_or_create(project=project,algorithm='transformer_bio',artifact_path=str(path),defaults={'name':name,'state':'ready','report':json.dumps(report,ensure_ascii=False)})
        ready.append(model)
    if ready:
        ready_ids=[model.pk for model in ready]
        ModelRun.objects.filter(project=project).exclude(pk__in=ready_ids).update(state='retired')
        if prefs.active_model_id not in ready_ids:
            prefs.active_model=ready[0];prefs.save(update_fields=['active_model'])
