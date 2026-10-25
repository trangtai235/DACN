"""Dispatch contract shared by native Windows threads and Celery deployments."""
import json
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings
from django.db import transaction
from core.models import Job
_pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='annotaflow-job')

def dispatch(job_id):
    if settings.JOB_RUNNER=='threads':
        from core.jobs.runner import execute
        _pool.submit(execute,job_id)
    elif settings.JOB_RUNNER=='sync':
        from core.jobs.runner import execute
        execute(job_id)
    else:
        from core.tasks import execute_job
        execute_job.delay(job_id)

def enqueue(project,actor,kind,payload,checkpoint=None):
    job=Job.objects.create(project=project,actor=actor,kind=kind,payload=json.dumps(payload,ensure_ascii=False),checkpoint=checkpoint or {})
    transaction.on_commit(lambda:dispatch(job.id));return job
