import json
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TransactionTestCase
from core.models import Project, Membership, Source, Comment, Job, Prediction
from core.jobs.runner import execute
from experiments.models import ModelRun
from studio.services.projects import ensure


class JobExecutionTests(TransactionTestCase):
    # The worker closes old connections, so its fixtures must be committed,
    # rather than enclosed in TestCase's outer transaction.
    def test_real_local_prediction_job_without_redis(self):
        user = User.objects.create_user(username='job-manager')
        project = Project.objects.create(name='Job test', owner=user)
        Membership.objects.create(project=project, user=user, role='manager')
        ensure(project)
        source = Source.objects.create(project=project, name='Test source')
        Comment.objects.create(project=project, source=source, text='A test comment')
        root = settings.BASE_DIR / 'artifacts/victsd-logreg-v1'
        ModelRun.objects.create(project=project, name='Baseline', artifact_path=str(root),
                                report=(root / 'metrics.json').read_text(encoding='utf-8'))
        job = Job.objects.create(project=project, actor=user, kind='predict',
                                 payload=json.dumps({'provider': 'local', 'replace_ai': True}))
        execute(job.id)
        job.refresh_from_db()
        self.assertEqual(job.status, 'complete', job.message)
        self.assertEqual(Prediction.objects.filter(comment__project=project).count(), 1)
        self.assertIn('identity', job.checkpoint)
