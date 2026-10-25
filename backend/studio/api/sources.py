from core.services.collection import collection_limit
from pathlib import Path
from reviewing.models import ReviewTask
from .common import *
from core.services.jobs import enqueue
from studio.models import UserProfile

@api
@require_POST
def import_csv(request):
    p=request.POST;project=project_for(request,p['project'],True);writable(project);f=request.FILES.get('file')
    if not f or f.size>20*1024*1024:raise ValueError('Cần CSV UTF-8 tối đa 20 MB.')
    folder=settings.PRIVATE_DATA/'uploads'/secrets.token_hex(12);folder.mkdir(parents=True);path=folder/'data.csv';path.write_bytes(f.read())
    try:
        import csv
        with path.open(encoding='utf-8-sig',newline='') as h:header=next(csv.reader(h))
    except (UnicodeDecodeError,StopIteration):raise ValueError('CSV cần có header và mã hóa UTF-8.')
    try:mapping=json.loads(p.get('mapping','{}'))
    except ValueError:raise ValueError('Mapping không hợp lệ.')
    if not isinstance(mapping,dict):raise ValueError('Mapping cần object.')
    if not any(v in header for v in (mapping.get('text','text'),'Comment')):raise ValueError('Không tìm thấy cột text / Comment hoặc cột đã chọn.')
    source=Source.objects.create(project=project,name=str(p.get('name') or f.name)[:200],kind='csv',metadata={'columns':header,'mapping':mapping})
    job=enqueue(project,request.user,'import_csv',{'file_path':str(path),'source_id':source.id,'mapping':mapping});return JsonResponse({'job':report_job(job),'source_id':source.id})

@api
@require_POST
def source_action(request,source_id):
    source=get_object_or_404(Source,pk=source_id);project=project_for(request,source.project_id,True);writable(project);p=data(request);action=p.get('action')
    if action=='rename':source.name=str(p.get('name','')).strip()[:200] or source.name;source.save();return JsonResponse({'ok':True})
    if action in ('fetch','continue'):
        if source.kind!='youtube':raise ValueError('Nguồn này không phải YouTube.')
        running=Job.objects.filter(project=project,kind='youtube',status__in=['queued','running'],payload__contains='"source_id": '+str(source.id)).exists()
        if running:raise ValueError('Nguồn đang có tác vụ thu thập.')
        job=enqueue(project,request.user,'youtube',{'video_id':source.external_id,'source_id':source.id,'limit':collection_limit(p.get('limit')),'include_replies':p.get('include_replies',True)},checkpoint=source.checkpoint if action=='continue' else {})
    elif action in ('annotate','reannotate'):
        prefs=ensure(project);provider=p.get('provider','local');payload={'provider':provider,'source_id':source.id,'replace_ai':action=='reannotate','model_id':prefs.active_model_id}
        if provider=='api':
            if not prefs.active_connection_id:raise ValueError('Chọn kết nối API trước.')
            payload['connection_id']=prefs.active_connection_id
        job=enqueue(project,request.user,'predict',payload)
    elif action=='delete':
        if p.get('confirm')!=source.name:raise ValueError('Cần nhập đúng tên nguồn.')
        if Job.objects.filter(project=project,status__in=['queued','running']).exists():raise ValueError('Dừng tác vụ dự án trước khi xóa nguồn.')
        with transaction.atomic():
            source_id=source.id;source_name=source.name
            comment_count=source.comments.count()
            ReviewTask.objects.filter(comment__source=source).delete()
            source.comments.all().delete()
            source.delete()
            audit(project,request.user,'source.delete',source_id=source_id,name=source_name,comments=comment_count)
        return JsonResponse({'ok':True})
    else:raise ValueError('Thao tác nguồn không hợp lệ.')
    return JsonResponse({'job':report_job(job)})

@api
@require_POST
def job_action(request,job_id):
    old=get_object_or_404(Job,pk=job_id);project=project_for(request,old.project_id,True);p=data(request)
    if p.get('action')=='cancel':
        if old.status not in ('queued','running'):raise ValueError('Tác vụ không còn chạy.')
        old.cancel_requested=True;old.save(update_fields=['cancel_requested','updated_at']);return JsonResponse({'ok':True,'message':'Sẽ dừng ở checkpoint tiếp theo, sau yêu cầu API đang chạy nếu có.'})
    if p.get('action')=='retry':
        if old.status not in ('failed','cancelled'):raise ValueError('Chỉ tiếp tục tác vụ lỗi/đã dừng.')
        writable(project);job=enqueue(project,request.user,old.kind,json.loads(old.payload),checkpoint=old.checkpoint);return JsonResponse({'job':report_job(job)})
    raise ValueError('Thao tác tác vụ không hợp lệ.')

@api
@require_GET
def jobs(request):
    project=project_for(request,request.GET['project']);qs=Job.objects.filter(project=project).order_by('-id')
    if not manager(project,request.user):qs=qs.filter(actor=request.user)
    return JsonResponse({'jobs':[report_job(x) for x in qs[:100]]})
