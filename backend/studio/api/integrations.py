from .common import *
from integrations.models import ProviderConnection
from integrations.secrets import encrypt
from integrations.registry import predict,snapshot
from integrations.providers.base import validate_endpoint
from experiments.models import ModelRun
from experiments.algorithms.registry import ALGORITHMS

def connection_json(c):return {**snapshot(c),'enabled':c.enabled,'key_configured':bool(c.encrypted_key)}
@api
@require_GET
def connections(request):
    project=project_for(request,request.GET['project'],True)
    return JsonResponse({'connections':[connection_json(c) for c in ProviderConnection.objects.filter(project=project).order_by('id')],'algorithms':[{'id':k,'name':v['name'],'parameter':v['parameter'],'values':v['values']} for k,v in ALGORITHMS.items()],'allowed_hosts':settings.AI_ALLOWED_HOSTS})
@api
@require_POST
def connection_save(request):
    p=data(request);project=project_for(request,p['project'],True)
    kind=p.get('kind')
    if kind not in ('gemini','openai_compatible','ollama'):raise ValueError('Provider không hợp lệ.')
    name=str(p.get('name','')).strip();model=str(p.get('model','')).strip();url=validate_endpoint(str(p.get('base_url','')))
    if not name or len(name)>120 or not model or len(model)>180 or not re.fullmatch(r'[A-Za-z0-9_.:/-]+',model):raise ValueError('Tên kết nối hoặc model ID chưa hợp lệ.')
    c=get_object_or_404(ProviderConnection,project=project,pk=p['id']) if p.get('id') else ProviderConnection(project=project)
    c.name=name;c.model=model;c.kind=kind;c.base_url=url;c.enabled=bool(p.get('enabled',True))
    for key in ('input_price','output_price'):
        v=float(p.get(key,0))
        if not 0<=v<=10000:raise ValueError('Giá cấu hình cần từ 0 đến 10.000 USD / triệu token.')
        setattr(c,key,v)
    if p.get('clear_key'):c.encrypted_key=''
    elif p.get('api_key'):c.encrypted_key=encrypt(str(p['api_key']))
    c.save();audit(project,request.user,'provider_saved',connection=c.id,kind=c.kind);return JsonResponse({'connection':connection_json(c)})
@api
@require_POST
def connection_test(request):
    p=data(request);project=project_for(request,p['project'],True);c=get_object_or_404(ProviderConnection,project=project,pk=p['id'])
    value=predict(c,'Cảm ơn bạn đã giải thích.',labels_for(project));return JsonResponse({'result':value})
@api
@require_POST
def select_model(request):
    p=data(request);project=project_for(request,p['project'],True);prefs=ensure(project)
    if 'model_id' in p:prefs.active_model=get_object_or_404(ModelRun,project=project,state='ready',pk=p['model_id'])
    if 'connection_id' in p:prefs.active_connection=get_object_or_404(ProviderConnection,project=project,enabled=True,pk=p['connection_id']) if p['connection_id'] else None
    prefs.save();return JsonResponse({'preferences':pref_json(prefs)})
