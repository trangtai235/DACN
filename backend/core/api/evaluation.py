from .common import *

@api
@require_GET
def export(request):
    project=project_for(request,request.GET['project'],True)
    if in_blind(project,request.user):raise PermissionError('Hoàn tất lượt mù trước khi xuất nhãn.')
    run=get_object_or_404(ReviewRun,pk=request.GET['run'],project=project) if request.GET.get('run') else None
    labels=final_labels(project,run);rows=[]
    for r in Comment.objects.filter(project=project).select_related('source').order_by('id'):
        if not labels.get(r.id):continue
        rows.append({'id':r.id,'text':r.text,'source':r.source.name,'ai_label':r.ai_label,'first_label':r.first_label,'final_label':labels[r.id],'origin_group':r.origin_group,'review_run':run.id if run else '', 'reviewed':bool(run and run.tasks.filter(comment=r,state='complete').exists())})
    if request.GET.get('format')=='jsonl':body='\n'.join(json.dumps(r,ensure_ascii=False) for r in rows);ctype='application/x-ndjson';ext='jsonl'
    else:
        buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=['id','text','source','ai_label','first_label','final_label','origin_group','review_run','reviewed']);writer.writeheader()
        for r in rows:
            r={k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in r.items()};writer.writerow(r)
        body='\ufeff'+buf.getvalue();ctype='text/csv; charset=utf-8';ext='csv'
    content=body.encode('utf-8');digest=hashlib.sha256(content).hexdigest();audit(project,request.user,'export',rows=len(rows),sha256=digest,run=run.id if run else None)
    response=HttpResponse(content,content_type=ctype);response['Content-Disposition']=f'attachment; filename="annotaflow-project-{project.id}.{ext}"';response['X-Content-SHA256']=digest;return response


@api
@require_POST
def import_references(request):
    project=project_for(request,request.POST['project'],True)
    if in_blind(project,request.user):raise PermissionError('Hoàn tất lượt mù trước khi nhập tham chiếu.')
    f=request.FILES.get('file')
    if not f or f.size>5*1024*1024:raise ValueError('Cần CSV id,label tối đa 5 MB.')
    rows=list(csv.DictReader(io.StringIO(f.read().decode('utf-8-sig'))));count=0
    with transaction.atomic():
        for row in rows:
            c=get_object_or_404(Comment,project=project,pk=int(row['id']));label=row['label']
            if label not in ('TOXIC','NON_TOXIC'):raise ValueError('Nhãn tham chiếu phải là TOXIC hoặc NON_TOXIC.')
            if c.first_frozen_at:raise ValueError('Nhập và khóa tham chiếu trước khi có lượt đầu để hạn chế rò rỉ đánh giá.')
            ReferenceLabel.objects.update_or_create(comment=c,defaults={'label':label,'created_by':request.user,'provenance':'CSV tham chiếu do nhóm cung cấp'});count+=1
        audit(project,request.user,'reference_imported',count=count)
    return JsonResponse({'imported':count})


@api
@require_GET
def human_metrics(request):
    project=project_for(request,request.GET['project'],True)
    if in_blind(project,request.user):raise PermissionError('Không chấm nhãn khi đang làm lượt mù.')
    run=get_object_or_404(ReviewRun,project=project,pk=request.GET['run']) if request.GET.get('run') else None
    refs_qs=ReferenceLabel.objects.filter(comment__project=project,comment__first_frozen_at__isnull=False)
    if run:refs_qs=refs_qs.filter(comment_id__in=json.loads(run.population))
    refs=list(refs_qs.select_related('comment'))
    if not refs:return JsonResponse({'available':False,'message':'Chưa có mẫu có tham chiếu độc lập và lượt đầu đã khóa.'})
    final=final_labels(project,run);y=[int(r.label=='TOXIC') for r in refs];first=[int(r.comment.first_label=='TOXIC') for r in refs];last=[int(final[r.comment_id]=='TOXIC') for r in refs]
    fixed=sum(a!=b and c==b for a,b,c in zip(first,y,last));harmed=sum(a==b and c!=b for a,b,c in zip(first,y,last))
    return JsonResponse({'available':True,'n':len(refs),'first':metrics(y,first),'final':metrics(y,last),'net_fixes':fixed-harmed,'fixed':fixed,'harmed':harmed,'review_seconds':run.used_seconds if run else 0,'limitations':'Tham chiếu do nhóm nhập; ba thành viên kiêm nhiệm vẫn có giới hạn độc lập. Thời gian lượt đầu do client báo; lượt hai gồm thời gian từ claim đến nộp.'})

