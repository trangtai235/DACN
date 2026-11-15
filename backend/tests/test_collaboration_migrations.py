from django.test import TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class CollaborationMigrationTests(TransactionTestCase):
    def test_old_predictions_runs_and_abcd_survive_upgrade(self):
        executor = MigrationExecutor(connection)
        old = [('studio', '0004_autolabelrun_autolabelresult'), ('reviewing', '0002_reviewrun_population'), ('experiments', '0002_modelrun_algorithm_modelrun_test_path')]
        try:
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            user = apps.get_model('auth', 'User').objects.create(username='migration-fixture')
            project = apps.get_model('core', 'Project').objects.create(name='Legacy fixture', owner_id=user.pk)
            source = apps.get_model('core', 'Source').objects.create(project_id=project.pk, name='Legacy source')
            comment = apps.get_model('core', 'Comment').objects.create(project_id=project.pk, source_id=source.pk, text='Legacy text', digest='legacy-fixture', first_label='TOXIC', origin_group='C')
            prediction = apps.get_model('core', 'Prediction').objects.create(comment_id=comment.pk, provider='local', model_version='old', label='NON_TOXIC')
            run = apps.get_model('reviewing', 'ReviewRun').objects.create(project_id=project.pk, population='[' + str(comment.pk) + ']')
            batch = apps.get_model('studio', 'AutoLabelRun').objects.create(project_id=project.pk, actor_id=user.pk, items=[{'id': comment.pk, 'text': 'Legacy text'}], labels=[{'key': 'TOXIC', 'name': 'Old name'}])
            executor = MigrationExecutor(connection); latest = executor.loader.graph.leaf_nodes(); executor.migrate(latest)
            from core.models import Comment, Prediction
            from reviewing.models import ReviewRun
            from studio.models import AutoLabelRun
            self.assertEqual(Comment.objects.get(pk=comment.pk).origin_group, 'C')
            self.assertEqual(Prediction.objects.get(pk=prediction.pk).label, 'NON_TOXIC')
            self.assertEqual(ReviewRun.objects.get(pk=run.pk).grouping_strategy, 'legacy_ai_human')
            self.assertIsNone(AutoLabelRun.objects.get(pk=batch.pk).schema_id)
            self.assertEqual(AutoLabelRun.objects.get(pk=batch.pk).labels[0]['name'], 'Old name')
        finally:
            executor = MigrationExecutor(connection); executor.migrate(executor.loader.graph.leaf_nodes())
