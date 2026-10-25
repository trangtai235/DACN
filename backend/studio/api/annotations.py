import re,math
from django.db.models import Q,Count
from .common import *
from studio.services.quality import quality

def annotation_state(comment,user):
    mine=Annotation.objects.filter(comment=comment,user=user).select_related('label').first()
    count=Annotation.objects.filter(comment=comment,status='submitted').count()
    return mine,count

@api
@require_GET
def comments(request):
    project=project_for(request,request.GET['project']);prefs=ensure(project);qs=project.comments.select_related('source').order_by('id')
    if request.GET.get('source'):qs=qs.filter(source_id=request.GET['source'])
    if request.GET.get('q'):qs=qs.filter(text__icontains=request.GET['q'][:200])
    status=request.GET.get('status','all');my=Annotation.objects.filter(comment__project=project,user=request.user)
    if status=='todo':qs=qs.exclude(pk__in=my.values('comment_id')).filter(unusable=False)
    elif status=='done':qs=qs.filter(pk__in=my.filter(status='submitted').values('comment_id'))
    elif status=='skipped':qs=qs.filter(pk__in=my.filter(status='skipped').values('comment_id'))
    elif status=='conflict':
        if not manager(project,request.user):raise PermissionError('Chỉ quản lý xem hàng đợi bất đồng.')
        qs=qs.filter(pk__in=quality(project)['conflict_ids'])
    total=qs.count();page=max(1,int(request.GET.get('page',1)));size=min(100,max(1,int(request.GET.get('size',20))));rows=[];blind=in_blind(project,request.user)
    for c in qs[(page-1)*size:page*size]:
        own,n=annotation_state(c,request.user);row=serialize_comment(c,hide=blind or (prefs.independent and not (own and own.status=='submitted')));row.update({'ai_hidden':blind or (prefs.independent and not (own and own.status=='submitted')),'author':c.author,'unusable':c.unusable,'annotation_count':n,'mine':annotation_json(own)})
        if not row['ai_hidden'] and c.ai_label:AIExposure.objects.get_or_create(comment=c,user=request.user)
        rows.append(row)
    return JsonResponse({'rows':rows,'total':total,'page':page,'size':size})

@api
@require_GET
def workspace(request):
    project=project_for(request,request.GET['project']);prefs=ensure(project);qs=project.comments.filter(unusable=False).order_by('id')
    if request.GET.get('source'):qs=qs.filter(source_id=request.GET['source'])
    if request.GET.get('comment'):qs=qs.filter(pk=request.GET['comment'])
    else:
        my=Annotation.objects.filter(comment__project=project,user=request.user).values('comment_id')
        qs=qs.exclude(pk__in=my).annotate(n=Count('annotations',filter=Q(annotations__status='submitted'))).filter(n__lt=prefs.redundancy)
        if request.GET.get('after'):qs=qs.filter(pk__gt=request.GET['after'])
    c=qs.first()
    if not c:return JsonResponse({'comment':None,'message':'Không còn mẫu trong hàng đợi. Có thể chọn mẫu từ trang Dữ liệu để xem lại.'})
    mine,n=annotation_state(c,request.user);hide=prefs.independent and not (mine and mine.status=='submitted')
    row_metadata={'source_kind':c.source.kind,'video_id':c.source.external_id if c.source.kind=='youtube' else '', 'external_id':c.external_id,'published_at':c.published_at.isoformat() if c.published_at else None}
    row=serialize_comment(c,hide=hide or in_blind(project,request.user));row.update({'author':c.author,'parent_external_id':c.parent_external_id,'mine':annotation_json(mine),'annotation_count':n,'ai_hidden':hide,'tokens':[{'text':m.group(),'start':m.start(),'end':m.end()} for m in re.finditer(r'\S+',c.text)]})
    row.update(row_metadata)
    if not hide and not in_blind(project,request.user):
        if c.ai_label:AIExposure.objects.get_or_create(comment=c,user=request.user)
        pred=c.predictions.order_by('-id').first();row['ai_spans']=pred.spans if pred else []
    return JsonResponse({'comment':row,'labels':labels_for(project),'preferences':pref_json(prefs)})

@api
@require_POST
def submit(request,comment_id):
    c=get_object_or_404(Comment,pk=comment_id);project=project_for(request,c.project_id);prefs=writable(project);p=data(request)
    with transaction.atomic():
        mutation_guard(project,request.user)
        # One row lock serializes revisions and redundancy assignment for this comment.
        c=Comment.objects.select_for_update().get(pk=c.pk)
        own=Annotation.objects.filter(comment=c,user=request.user).select_related('label').first();before=annotation_json(own) or {}
        expected=int(p.get('revision',0))
        if (own.revision if own else 0)!=expected:raise ValueError('Nhãn đã thay đổi ở phiên khác. Tải lại trước khi lưu.')
        if not own and Annotation.objects.filter(comment=c,status='submitted').count()>=prefs.redundancy:raise ValueError('Mẫu đã đủ số người gán. Tải mẫu khác.')
        status=p.get('status','submitted')
        if status not in ('submitted','skipped'):raise ValueError('Trạng thái không hợp lệ.')
        label=label_for(project,p.get('label'),nullable=True) if status=='submitted' else None
        spans=validate_spans(c.text,p.get('spans',[]),project) if status=='submitted' else []
        seconds=float(p.get('seconds',0))
        if not math.isfinite(seconds) or not 0<=seconds<=3600:raise ValueError('Thời gian gán nhãn từ 0 đến 3.600 giây.')
        defaults={'seconds':seconds,'label':label,'spans':spans,'note':str(p.get('note',''))[:4000],'status':status,'assisted':bool((own and own.assisted) or not prefs.independent or AIExposure.objects.filter(comment=c,user=request.user).exists()),'revision':expected+1}
        own,_=Annotation.objects.update_or_create(comment=c,user=request.user,defaults=defaults)
        AnnotationEvent.objects.create(comment=c,user=request.user,before=before,after=annotation_json(own),action='submit')
        audit(project,request.user,'annotation_saved',comment=c.id)
    return JsonResponse({'annotation':annotation_json(own)})

@api
@require_POST
def undo(request,comment_id):
    c=get_object_or_404(Comment,pk=comment_id);project=project_for(request,c.project_id);writable(project)
    with transaction.atomic():
        mutation_guard(project,request.user)
        c=Comment.objects.select_for_update().get(pk=c.pk)
        event=AnnotationEvent.objects.filter(comment=c,user=request.user).order_by('-id').first()
        if not event or event.action!='submit':raise ValueError('Chưa có thay đổi mới để hoàn tác.')
        current=Annotation.objects.filter(comment=c,user=request.user).select_related('label').first()
        if not current or current.revision!=event.after.get('revision'):raise ValueError('Chỉ hoàn tác thay đổi mới nhất chưa bị sửa tiếp.')
        before=annotation_json(current);old=event.before
        if old:
            current.label=ProjectLabel.objects.filter(project=project,key=old.get('label')).first() if old.get('label') else None;current.spans=old['spans'];current.note=old['note'];current.status=old['status'];current.assisted=old['assisted'];current.revision+=1;current.save()
        else:current.delete()
        AnnotationEvent.objects.create(comment=c,user=request.user,before=before,after=old,action='undo')
    return JsonResponse({'ok':True})

@api
@require_GET
def quality_view(request):
    project=project_for(request,request.GET['project'],True)
    if in_blind(project,request.user):raise PermissionError('Hoàn tất lượt mù trước khi xem chất lượng.')
    report=quality(project);ids=report['conflict_ids'];report['conflicts']=[{'id':c.id,'text':c.text,'annotations':[{'id':a.id,'user':a.user.first_name or a.user.username,'label':a.label.key if a.label else None,'spans':a.spans,'note':a.note} for a in c.annotations.filter(status='submitted').select_related('label','user')]} for c in project.comments.filter(pk__in=ids)[:50]]
    return JsonResponse(report)

@api
@require_POST
def adjudicate(request,comment_id):
    c=get_object_or_404(Comment,pk=comment_id);project=project_for(request,c.project_id,True);writable(project);p=data(request)
    if in_blind(project,request.user):raise PermissionError('Hoàn tất lượt mù trước khi phân xử chung.')
    note=str(p.get('note','')).strip()
    if not note:raise ValueError('Cần lý do phân xử.')
    label=label_for(project,p.get('label'),nullable=True);spans=validate_spans(c.text,p.get('spans',[]),project)
    with transaction.atomic():
        mutation_guard(project,request.user,True)
        c=Comment.objects.select_for_update().get(pk=c.pk)
        GoldAnnotation.objects.update_or_create(comment=c,defaults={'label':label,'spans':spans,'note':note[:4000],'adjudicator':request.user})
    audit(project,request.user,'gold_adjudicated',comment=c.id);return JsonResponse({'ok':True})
