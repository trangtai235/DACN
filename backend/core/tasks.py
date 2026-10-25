from celery import shared_task
@shared_task
def execute_job(job_id):
    from core.jobs.runner import execute
    execute(job_id)
