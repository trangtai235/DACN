from pathlib import Path
from .common import *
from studio.services.quality import quality
from studio.services.exports import records,render,FORMATS

def snapshot(project):
    return {'schema':1,'project':{'name':project.name,'description':project.description},'labels':labels_for(project,False),'comments':records(project,'all'),'captured_at':timezone.now().isoformat()}
def create_version(project,user,name,restored_from=None):
    snap=snapshot(project);raw=json.dumps(snap,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return DatasetVersion.objects.create(project=project,name=name[:160],snapshot=snap,sha256=hashlib.sha256(raw).hexdigest(),metrics=quality(project),created_by=user,restored_from=restored_from)

@api
@require_POST
def version_create(request):
    p=data(request);project=project_for(request,p['project'],True)
    if in_blind(project,request.user):raise PermissionError('Hoàn tất lượt mù trước khi chụp phiên bản.')
    name=str(p.get('name','')).strip()
    if not name:raise ValueError('Cần tên phiên bản.')
    obj=create_version(project,request.user,name);audit(project,request.user,'version_created',version=obj.id)
    return JsonResponse({'id':obj.id,'sha256':obj.sha256})

@api
@require_GET
def version_download(request,version_id):
    v=get_object_or_404(DatasetVersion,pk=version_id);project_for(request,v.project_id,True)
    if in_blind(v.project,request.user):raise PermissionError('Hoàn tất lượt mù trước khi tải phiên bản.')
    body=json.dumps({'snapshot':v.snapshot,'metrics':v.metrics,'sha256':v.sha256},ensure_ascii=False,indent=2)
    response=HttpResponse(body,content_type='application/json');response['Content-Disposition']=f'attachment; filename="annotaflow-version-{v.id}.json"';return response

@api
@require_POST
def version_restore(request,version_id):
    v=get_object_or_404(DatasetVersion,pk=version_id);project=project_for(request,v.project_id,True);writable(project);p=data(request)
    if in_blind(project,request.user):raise PermissionError('Hoàn tất lượt mù trước khi khôi phục.')
    if p.get('confirm')!=v.name:raise ValueError('Nhập tên phiên bản để xác nhận khôi phục lớp nhãn.')
    with transaction.atomic():
        mutation_guard(project,request.user,True)
        backup=create_version(project,request.user,'Trước khôi phục · '+timezone.now().isoformat())
        for l in v.snapshot['labels']:
            ProjectLabel.objects.update_or_create(project=project,key=l['key'],defaults={k:l[k] for k in ('name','description','color','enabled','order')})
        count=0
        for row in v.snapshot['comments']:
            c=Comment.objects.select_for_update().filter(project=project,pk=row['id'],text=row['text']).first()
            if not c:continue
            revisions=dict(Annotation.objects.filter(comment=c).values_list('user_id','revision'))
            Annotation.objects.filter(comment=c).delete();GoldAnnotation.objects.filter(comment=c).delete()
            for a in row['annotators']:
                u=User.objects.filter(pk=a['user_id']).first()
                if not u:continue
                lab=ProjectLabel.objects.filter(project=project,key=a['label']).first() if a['label'] else None
                Annotation.objects.create(comment=c,user=u,label=lab,spans=a['spans'],note=a['note'],status=a.get('status','submitted'),assisted=a['assisted'],seconds=a.get('seconds',0),revision=max(a['revision'],revisions.get(u.id,0))+1)
            if row.get('gold_label') and row['review_status']=='adjudicated':
                lab=ProjectLabel.objects.get(project=project,key=row['gold_label']) if row['gold_label']!='O' else None;GoldAnnotation.objects.create(comment=c,label=lab,spans=[{k:s[k] for k in ('start','end','label')} for s in row['spans']],note='Khôi phục phiên bản '+v.name,adjudicator=request.user)
            count+=1
        result=create_version(project,request.user,'Khôi phục · '+v.name,restored_from=v);audit(project,request.user,'version_restored',source=v.id,backup=backup.id,version=result.id)
    return JsonResponse({'restored_comments':count,'backup_version':backup.id,'version':result.id,'scope':'Khôi phục lớp nhãn trên mẫu cùng ID và văn bản; giữ mẫu khác và nhãn lượt đầu nghiên cứu.'})

@api
@require_GET
def export_dataset(request):
    project=project_for(request,request.GET['project'],True)
    if in_blind(project,request.user):raise PermissionError('Hoàn tất lượt mù trước khi xuất dữ liệu.')
    fmt=request.GET.get('format','jsonl');scope=request.GET.get('scope','human');rows=records(project,scope,request.GET.get('source'));body,ext,mime=render(project,rows,fmt);sha=hashlib.sha256(body).hexdigest()
    folder=settings.PRIVATE_DATA/'exports'/str(project.id);folder.mkdir(parents=True,exist_ok=True);name=secrets.token_hex(12)+'.'+ext;path=folder/name;path.write_bytes(body)
    obj=ExportArtifact.objects.create(project=project,created_by=request.user,format=fmt,scope=scope,sha256=sha,row_count=len(rows),file_path=str(path));audit(project,request.user,'export_created',export=obj.id,rows=len(rows),sha256=sha)
    response=HttpResponse(body,content_type=mime);response['Content-Disposition']=f'attachment; filename="annotaflow-{project.id}-{fmt}.{ext}"';response['X-Content-SHA256']=sha;return response

@api
@require_GET
def export_history(request):
    project=project_for(request,request.GET['project'],True)
    return JsonResponse({'formats':[{'id':k,'name':v[0],'extension':v[1]} for k,v in FORMATS.items()],'history':[{'id':x.id,'format':x.format,'scope':x.scope,'rows':x.row_count,'sha256':x.sha256,'created_at':x.created_at.isoformat()} for x in ExportArtifact.objects.filter(project=project).order_by('-id')[:50]]})
