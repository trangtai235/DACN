import json,os
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from core.models import Project,Membership,Source,Comment,audit
from experiments.models import ModelRun
from reviewing.models import ReviewRun
class Command(BaseCommand):
    help='Create an explicit synthetic demo project and three users; never overwrite existing passwords.'
    def add_arguments(self,p):p.add_argument('--password',default=os.getenv('DEMO_PASSWORD',''))
    @transaction.atomic
    def handle(self,*args,**options):
        password=options['password']
        if len(password)<12:raise CommandError('Đặt DEMO_PASSWORD ít nhất 12 ký tự trong .env hoặc --password.')
        users=[]
        for username,name in [('tv1','Minh Anh'),('tv2','Quốc Bảo'),('tv3','Khánh Linh')]:
            u,created=User.objects.get_or_create(username=username,defaults={'first_name':name})
            if created:u.set_password(password);u.save()
            users.append(u)
        project,created=Project.objects.get_or_create(name='Bình luận YouTube tiếng Việt',owner=users[0],defaults={'description':'Dự án minh họa quy trình tạo dữ liệu có nhãn','is_demo':True})
        for i,u in enumerate(users):Membership.objects.get_or_create(project=project,user=u,defaults={'role':'manager' if i==0 else 'annotator'})
        source,_=Source.objects.get_or_create(project=project,name='Bình luận minh họa do ứng dụng tạo',kind='manual')
        rows=json.loads((settings.ROOT_DIR/'dist/assets/demo-data.json').read_text(encoding='utf-8'))
        import hashlib
        for r in rows:
            defaults={'source':source,'text':r['text'],'context':r['context'],'ai_label':r['ai_label'],'ai_provider':'local','first_label':r['first_label'],'first_actor':users[0] if r['first_label'] else None,'first_frozen_at':timezone.now() if r['first_label'] else None,'origin_group':r['group'],'revision':1}
            Comment.objects.get_or_create(project=project,digest=hashlib.sha256(r['text'].encode()).hexdigest(),defaults=defaults)
        from studio.services.projects import ensure
        from studio.models import Annotation,ProjectLabel
        from core.services.model_registry import register_bundled
        register_bundled(project)
        for c in project.comments.filter(first_frozen_at__isnull=False):
            Annotation.objects.get_or_create(comment=c,user=users[0],defaults={'label':ProjectLabel.objects.get(project=project,key=c.first_label),'status':'submitted','assisted':True,'note':'Mẫu minh họa có AI hỗ trợ; chưa phải nhãn gold.'})
        if not ReviewRun.objects.filter(project=project).exists():ReviewRun.objects.create(project=project,policy='adaptive',population=json.dumps(list(project.comments.filter(first_frozen_at__isnull=False).values_list('id',flat=True))))
        if created:audit(project,users[0],'project_created',synthetic=True)
        self.stdout.write('Đã chuẩn bị dự án minh họa và tv1 / tv2 / tv3. Dùng DEMO_PASSWORD đã cấu hình.')
