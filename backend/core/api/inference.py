from .common import *

@api
@require_POST
def predict(request):
    p=data(request);project=project_for(request,p['project'],True);provider=p.get('provider','local')
    from studio.services.projects import ensure
    from integrations.models import ProviderConnection
    prefs=ensure(project);payload={'provider':provider,'replace_ai':bool(p.get('replace_ai',True))}
    if provider not in ('local','gemini','api'):raise ValueError('Provider không hợp lệ.')
    if provider=='gemini' and not settings.GEMINI_API_KEY:raise ValueError('Chưa cấu hình GEMINI_API_KEY.')
    if provider=='local':
        mid=p.get('model_id') or prefs.active_model_id
        if mid:get_object_or_404(ModelRun,project=project,state='ready',pk=mid);payload['model_id']=mid
    if provider=='api':
        cid=p.get('connection_id') or prefs.active_connection_id
        if not cid:raise ValueError('Chọn kết nối API cho dự án trước.')
        get_object_or_404(ProviderConnection,project=project,pk=cid,enabled=True);payload['connection_id']=cid
    job=enqueue(project,request.user,'predict',payload);return JsonResponse({'job':report_job(job)})


@api
@require_POST
def predict_one(request):
    p=data(request);project=project_for(request,p['project']);text=str(p.get('text','')).strip()
    if not text or len(text)>20000:raise ValueError('Nội dung từ 1 đến 20.000 ký tự.')
    if in_blind(project,request.user):raise PermissionError('Hoàn tất lượt kiểm tra mù trước khi xem gợi ý model/API.')
    from core.services.providers import local_predict
    if p.get('provider')=='api':
        from studio.services.projects import ensure,labels_for
        from integrations.models import ProviderConnection
        from integrations.registry import predict as external_predict
        cid=p.get('connection_id') or ensure(project).active_connection_id
        connection=get_object_or_404(ProviderConnection,project=project,pk=cid,enabled=True)
        return JsonResponse(external_predict(connection,text,labels_for(project)))
    return JsonResponse(local_predict(project,[text],p.get('model_id'))[0])


@api
@require_POST
def training(request):
    p=request.POST;project=project_for(request,p['project'],True);paths={};root=settings.PRIVATE_DATA/'uploads'/uuid.uuid4().hex;root.mkdir(parents=True)
    for key in ('train','validation','test'):
        f=request.FILES.get(key)
        if not f or f.size>10*1024*1024:raise ValueError('Cần 3 file CSV train, validation và test; mỗi file tối đa 10 MB.')
        path=root/(key+'.csv');path.write_bytes(f.read());paths[key]=str(path)
    from experiments.algorithms.registry import algorithm
    from studio.services.projects import labels_for
    key=p.get('algorithm','logistic_regression');algorithm(key);paths.update({'algorithm':key,'label_keys':[l['key'] for l in labels_for(project)],'name':str(p.get('name',''))[:160]})
    job=enqueue(project,request.user,'train',paths);return JsonResponse({'job':report_job(job)})


@api
@require_POST
def benchmark(request):
    p=data(request);project=project_for(request,p['project'],True)
    from studio.services.projects import ensure
    from core.services.providers import model_for
    from integrations.models import ProviderConnection
    prefs=ensure(project);model=model_for(project,p.get('model_id'))
    if not model:raise ValueError('Cần chọn model đã train.')
    cid=p.get('connection_id') or prefs.active_connection_id
    if cid:get_object_or_404(ProviderConnection,project=project,enabled=True,pk=cid)
    elif not settings.GEMINI_API_KEY:raise ValueError('Chọn kết nối API trước. Chưa phát sinh yêu cầu API.')
    path=Path(model.test_path) if model.test_path else settings.PRIVATE_DATA/'victsd'/'ViCTSD_test.csv'
    if not path.exists():raise ValueError('Model baseline cần chạy fetch_victsd; model tự train dùng tập test đã upload.')
    n=int(p.get('limit',50))
    if not 1<=n<=1000:raise ValueError('Số mẫu đánh giá từ 1 đến 1.000.')
    job=enqueue(project,request.user,'benchmark_api',{'test_path':str(path),'limit':n,'model_id':model.id,'connection_id':cid});return JsonResponse({'job':report_job(job)})


@api
@require_GET
def job_status(request,job_id):
    j=get_object_or_404(Job,pk=job_id,actor=request.user);project_for(request,j.project_id);return JsonResponse(report_job(j))

