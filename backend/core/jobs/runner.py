import json,logging
from django.db import transaction,close_old_connections
from django.utils import timezone
from core.models import Job,audit
class Cancelled(Exception):pass

def tick(job,pct,message,checkpoint=None):
    # Persist completed responses before cancellation to avoid paid-work loss on retry.
    if checkpoint is not None:
        job.checkpoint={**job.checkpoint,**checkpoint}
        Job.objects.filter(pk=job.id).update(checkpoint=job.checkpoint,updated_at=timezone.now())
    if Job.objects.filter(pk=job.id,cancel_requested=True).exists():raise Cancelled('Đã yêu cầu dừng.')
    from studio.models import ProjectSettings
    from core.models import Membership
    prefs=ProjectSettings.objects.filter(project=job.project).first()
    if prefs and (prefs.locked or prefs.archived):raise Cancelled('Dự án đã khóa/lưu trữ; có thể tiếp tục sau khi mở lại.')
    member=Membership.objects.filter(project=job.project,user=job.actor).first()
    if not member or (member.role!='manager' and job.project.owner_id!=job.actor_id):raise Cancelled('Quyền quản lý đã thay đổi.')
    Job.objects.filter(pk=job.id).update(progress=min(99,max(0,int(pct))),message=message[:450],updated_at=timezone.now())

def execute(job_id):
    close_old_connections()
    try:
        with transaction.atomic():
            job=Job.objects.select_for_update().select_related('project','actor').get(pk=job_id)
            if job.status!='queued':return
            if job.cancel_requested:job.status='cancelled';job.save(update_fields=['status','progress','message','result','updated_at']);return
            job.status='running';job.save(update_fields=['status','progress','message','result','updated_at'])
        try:
            from .predict import run as predict
            from .training import run as training
            from .youtube import run as youtube
            from .benchmark import run as benchmark
            from .imports import run as imports
            from .auto_label import run as auto_label
            handlers={'predict':predict,'train':training,'youtube':youtube,'benchmark_api':benchmark,'import_csv':imports,'auto_label':auto_label}
            if job.kind not in handlers:raise ValueError('Loại tác vụ chưa đăng ký.')
            payload=json.loads(job.payload);result=handlers[job.kind](job,payload)
            tick(job,99,'Đang hoàn tất');job.status='complete';job.progress=100;job.message='Hoàn tất';job.result=json.dumps(result,ensure_ascii=False);job.save(update_fields=['status','progress','message','result','updated_at'])
            audit(job.project,job.actor,'job_complete',kind=job.kind,job=job.id)
        except Cancelled as exc:
            job.status='cancelled';job.message=str(exc) or 'Đã dừng tại checkpoint. Có thể tiếp tục.';job.save(update_fields=['status','progress','message','result','updated_at'])
        except Exception as exc:
            job.status='failed';job.message=str(exc)[:450] if isinstance(exc,ValueError) else 'Tác vụ thất bại. Kiểm tra kết nối, dữ liệu và cấu hình máy chủ.';job.save(update_fields=['status','progress','message','result','updated_at'])
            logging.getLogger(__name__).error('Job %s failed (%s)',job.id,type(exc).__name__)
    finally:
        if 'job' in locals() and job.kind=='youtube' and job.status in ('failed','cancelled'):
            from core.models import Source
            try:Source.objects.filter(pk=json.loads(job.payload).get('source_id')).update(fetch_state=job.status)
            except (ValueError,TypeError):pass
        close_old_connections()
