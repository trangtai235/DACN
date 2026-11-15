import uuid
from datetime import timedelta
from django.http import Http404
from .common import *
from integrations.translation import translate
from integrations.registry import snapshot
from studio.services.adaptation import text_hash
from reviewing.models import ReviewTask


def json_translation(row, cached=False):
    expired=row.status=='running' and row.updated_at<timezone.now()-timedelta(seconds=150)
    return {'id':row.pk,'comment_id':row.comment_id,'text_hash':row.text_hash,'target_language':'vi',
        'status':'interrupted' if expired else row.status,'translated_text':row.translated_text if row.status=='complete' else '',
        'provider':row.provider.get('name',''),'model':row.provider.get('model',''),'cached':cached,
        'error':'Lượt dịch đã dừng. Bấm thử lại.' if expired else row.error}


@api
def comment_translation(request,comment_id):
    if request.method not in ('GET','POST'):return JsonResponse({'error':'Chỉ hỗ trợ GET/POST.'},status=405)
    p=data(request) if request.method=='POST' else request.GET
    project=project_for(request,p['project'])
    comment=get_object_or_404(Comment,pk=comment_id,project=project)
    source=resolve_source(project,p.get('source_id'))
    if source and comment.source_id!=source.pk:raise Http404()
    if ReviewTask.objects.filter(run__project=project,reviewer=request.user,state='claimed').exists():raise PermissionError('Không dùng dịch máy trong lượt kiểm tra mù.')
    if p.get('text_hash')!=text_hash(comment.text,comment.context):raise ValueError('Bình luận đã thay đổi. Tải lại trước khi dịch.')
    digest=text_hash(comment.text,'')
    row=CommentTranslation.objects.filter(comment=comment,text_hash=digest,target_language='vi').first()
    if request.method=='GET':
        if row and row.status=='complete':
            AIExposure.objects.get_or_create(comment=comment,user=request.user)
            audit(project,request.user,'translation_view',translation=row.pk,comment=comment.pk,cached=True)
        return JsonResponse(json_translation(row,True) if row else {'status':'missing'})
    if not comment.text.strip() or len(comment.text)>12000:raise ValueError('Chỉ dịch bình luận từ 1 đến 12.000 ký tự; nội dung gốc không bị cắt.')
    token=str(uuid.uuid4())
    with transaction.atomic():
        row,_=CommentTranslation.objects.get_or_create(comment=comment,text_hash=digest,target_language='vi',defaults={'request_token':token})
        row=CommentTranslation.objects.select_for_update().get(pk=row.pk)
        if row.status=='complete':
            AIExposure.objects.get_or_create(comment=comment,user=request.user)
            audit(project,request.user,'translation_view',translation=row.pk,comment=comment.pk,cached=True)
            return JsonResponse(json_translation(row,True))
        if row.request_token!=token and json_translation(row)['status']=='running':return JsonResponse(json_translation(row),status=202)
        connection=ensure(project).active_connection
        if not connection or not connection.enabled:raise ValueError('Chọn một kết nối API đang bật trong Mô hình & API để dịch.')
        row.status='running';row.request_token=token;row.error='';row.provider=snapshot(connection)
        row.save()
    # Do not hold comment/annotation locks while waiting for the provider.
    try:
        translated=translate(connection,comment.text)
    except ValueError as exc:
        CommentTranslation.objects.filter(pk=row.pk,request_token=token).update(status='failed',error=str(exc)[:300],updated_at=timezone.now())
        raise
    except Exception:
        CommentTranslation.objects.filter(pk=row.pk,request_token=token).update(status='failed',error='Dịch vụ dịch gặp lỗi. Hãy thử lại.',updated_at=timezone.now())
        raise
    comment.refresh_from_db()
    if p.get('text_hash')!=text_hash(comment.text,comment.context):
        CommentTranslation.objects.filter(pk=row.pk,request_token=token).update(status='failed',error='Nội dung đã đổi trong khi dịch.',updated_at=timezone.now())
        raise ValueError('Nội dung đã đổi trong khi dịch. Tải lại để dịch đúng bình luận.')
    CommentTranslation.objects.filter(pk=row.pk,request_token=token).update(status='complete',translated_text=translated,updated_at=timezone.now())
    row.refresh_from_db()
    project_for(request,project.pk)
    if row.status!='complete':return JsonResponse(json_translation(row),status=202)
    # Translation is assistance, never a content label or a human annotation.
    AIExposure.objects.get_or_create(comment=comment,user=request.user)
    audit(project,request.user,'translation_view',translation=row.pk,comment=comment.pk,cached=False)
    return JsonResponse(json_translation(row))
