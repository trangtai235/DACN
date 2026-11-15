"""Explicit synthetic fixtures; no network calls and no invented study outcomes."""
from unittest.mock import patch
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from core.models import Project, Membership, Source, Comment, Job
from studio.models import ProjectLabel, FeedbackApproval
from integrations.models import ProviderConnection
from studio.services.projects import ensure, PRESETS
from studio.services.adaptation import current_schema, freeze_dataset
from studio.services.collaboration import start_run, decision, run_branch
from core.jobs.feedback_train import run as train_feedback


class Command(BaseCommand):
    help = 'Tạo dự án MINH HỌA M1–M3 riêng; cần tài khoản đã có; không đổi mật khẩu, không gọi API thật.'

    def add_arguments(self, parser):
        parser.add_argument('--owner', default='tv1')
        parser.add_argument('--reviewer', default='tv2')
        parser.add_argument('--judge', default='tv3')

    def handle(self, *args, **options):
        users = []
        for key in ('owner', 'reviewer', 'judge'):
            user = User.objects.filter(username=options[key]).first()
            if not user: raise CommandError('Chạy seed_demo trước hoặc cung cấp tài khoản đã có: ' + options[key])
            users.append(user)
        if len({u.pk for u in users}) != 3: raise CommandError('Cần ba tài khoản khác nhau.')
        project = Project.objects.create(name='MINH HỌA · Phối hợp hai mô hình', owner=users[0], is_demo=True,
            description='Dữ liệu tổng hợp, API mock cố định, quyết định hỗ trợ được tạo bằng script. Không phải thực nghiệm người dùng.')
        for index, user in enumerate(users): Membership.objects.create(project=project, user=user, role='annotator' if index == 1 else 'manager')
        ensure(project); ProjectLabel.objects.filter(project=project).update(enabled=False)
        for index, (key, name, color, description) in enumerate(PRESETS['moderation']):
            ProjectLabel.objects.update_or_create(project=project, key=key, defaults={'name': name, 'color': color,
                'description': description, 'order': index, 'enabled': True,
                'exclusions': 'Nếu vừa quảng cáo vừa công kích, chọn TOXIC.'})
        schema = current_schema(project)
        texts = {'NON_TOXIC': 'Cảm ơn bạn đã chia sẻ video bổ ích', 'TOXIC': 'Đồ ngu đừng mở miệng nữa', 'SPAM': 'Mua hàng giảm giá liên hệ cửa hàng ngay'}
        for source_index in range(6):
            source = Source.objects.create(project=project, name='Nguồn tổng hợp ' + str(source_index), metadata={'demo': True})
            for label, text in texts.items():
                for repeat in range(2): Comment.objects.create(project=project, source=source, text=f'{text} (minh họa nguồn {source_index}, mẫu {repeat})')
        # No dispatch is allowed during fixture generation; all handlers are called explicitly.
        with patch('core.services.jobs.dispatch'):
            support = start_run(project, users[0], {'model_id': None, 'connection_id': None})
            for pair in support.pairs.select_related('comment'):
                label = next(key for key, text in texts.items() if pair.text.startswith(text))
                d = decision(pair.pk, users[0], {'action': 'confirm', 'label': label,
                    'note': 'MINH HỌA: quyết định tạo bằng script, không phải quan sát người dùng.'})
                FeedbackApproval.objects.create(comment=pair.comment, schema=schema, decision=d, decision_revision=d.revision,label=label, text=pair.text,
                    text_hash=pair.text_hash, source_id_snapshot=pair.comment.source_id, approved_by=users[0])
            dataset = freeze_dataset(project, schema, 42)
            job = Job.objects.create(project=project, actor=users[0], kind='feedback_train')
            result = train_feedback(job, {'dataset_id': dataset.pk, 'algorithm': 'complement_nb'})
            job.status = 'complete'; job.progress = 100; job.message = 'MINH HỌA: train dữ liệu tổng hợp'; job.save()
            source = Source.objects.create(project=project, name='Bốn tình huống M1 (MINH HỌA)', metadata={'demo': True})
            cases = [('Cảm ơn bài viết hữu ích [đồng thuận]', 'NON_TOXIC', 'NON_TOXIC'),
                     ('Mua hàng ở cửa hàng của tôi [bất đồng]', 'SPAM', 'NON_TOXIC'),
                     ('Đồ ngu im đi [hai model cùng sai]', 'NON_TOXIC', 'NON_TOXIC'),
                     ('Bình luận cần xử lý khi API lỗi [lỗi dịch vụ]', 'NON_TOXIC', None)]
            for text, _, _ in cases: Comment.objects.create(project=project, source=source, text=text)
            connection = ProviderConnection.objects.create(project=project, name='MINH HỌA API mock (không có key)',
                kind='openai_compatible', model='scripted-fixture-v1', base_url='https://api.openai.com/v1', enabled=False)
            # Temporarily enable only inside this command; no credentials or real requests.
            connection.enabled = True; connection.save()
            batch = start_run(project, users[0], {'source_id': source.pk, 'model_id': result['model_id'], 'connection_id': connection.pk})
            batch.options['mock_predictions'] = True; batch.save(update_fields=['options'])
            local = {text: left for text, left, right in cases}; remote = {text: right for text, left, right in cases}
            def mock_api(connection, text, labels, **kwargs):
                if remote[text] is None: raise ValueError('MINH HỌA: API timeout cố định; không sinh nhãn.')
                return {'label': remote[text], 'model_version': 'MOCK-fixture', 'spans': []}
            with patch('studio.services.collaboration.local_predict', side_effect=lambda project, texts, model: [{'label': local[t], 'spans': [], 'model_version': 'MOCK-fixture'} for t in texts]), \
                 patch('studio.services.collaboration.api_predict', side_effect=mock_api):
                run_branch(batch.local_job, {'run_id': batch.pk, 'branch': 'local'})
                run_branch(batch.llm_job, {'run_id': batch.pk, 'branch': 'api'})
            for worker in (batch.local_job, batch.llm_job):
                worker.status = 'complete'; worker.progress = 100; worker.message = 'MINH HỌA: nhánh mock cố định'; worker.save()
            connection.enabled = False; connection.save()
        self.stdout.write(self.style.SUCCESS(f'DEMO (synthetic fixtures): project={project.pk}, run={batch.pk}, model={result["model_id"]}, dataset={dataset.pk}.'))
        self.stdout.write('Open #collaboration and select the new demo project. API disabled. Synthetic data is NOT experimental evidence. Existing passwords unchanged.')
