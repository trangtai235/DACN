from django.core.management.base import BaseCommand,CommandError
from django.conf import settings
from core.models import Job,Source
class Command(BaseCommand):
    help='Mark interrupted jobs recoverable before starting the single-process native server.'
    def handle(self,*args,**kwargs):
        if settings.JOB_RUNNER!='threads':raise CommandError('Only for a stopped native threads server, not Celery deployments.')
        n=Job.objects.filter(status__in=['queued','running']).update(status='failed',message='Server local da dung. Bam Tiep tuc de phuc hoi tu checkpoint.')
        Source.objects.filter(fetch_state='running').update(fetch_state='failed')
        self.stdout.write(f'Local recovery: {n} interrupted jobs now resumable.')
