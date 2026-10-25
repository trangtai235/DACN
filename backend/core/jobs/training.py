import json
from django.db import transaction
from django.conf import settings
from experiments.training import train
from experiments.models import ModelRun
from studio.services.projects import writable,mutation_guard
from .runner import tick

def run(job,p):
    writable(job.project);out=settings.PRIVATE_DATA/'models'/str(job.id)
    report=train(p['train'],p['validation'],p['test'],out,lambda n,m:tick(job,n,m),algorithm_key=p.get('algorithm','logistic_regression'),label_keys=p.get('label_keys'))
    with transaction.atomic():
        mutation_guard(job.project,job.actor,True)
        model=ModelRun.objects.create(project=job.project,name=p.get('name') or f"{report['name']} · {job.id}",algorithm=p.get('algorithm','logistic_regression'),test_path=p['test'],artifact_path=str(out),report=json.dumps(report,ensure_ascii=False))
    return {'model_id':model.id,'report':report}
