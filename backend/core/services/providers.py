"""Compatibility facade; new integrations live in integrations/providers/."""
import json,time
from pathlib import Path
from functools import lru_cache
import joblib
from django.conf import settings
from experiments.models import ModelRun

@lru_cache(maxsize=8)
def load_artifact(path,modified):return joblib.load(path)

def model_for(project,model_id=None):
    if model_id:
        run=ModelRun.objects.filter(project=project,state='ready',pk=model_id).first()
        if not run:raise ValueError('Model không thuộc dự án hoặc chưa sẵn sàng.')
        return run
    from studio.services.projects import ensure
    prefs=ensure(project)
    return (prefs.active_model if prefs.active_model and prefs.active_model.state=='ready' else None) or ModelRun.objects.filter(project=project,state='ready').order_by('-id').first()

def local_predict(project,texts,model_id=None):
    run=model_for(project,model_id)
    if not run:raise ValueError('Chưa có mô hình đã huấn luyện.')
    path=Path(run.artifact_path).resolve();allowed=[(settings.BASE_DIR/'artifacts').resolve(),settings.PRIVATE_DATA.resolve()]
    if not any(path.is_relative_to(p) for p in allowed):raise ValueError('Đường dẫn model không hợp lệ.')
    if run.algorithm=='transformer_bio':
        from studio.services.projects import labels_for
        if not {'TOXIC','NON_TOXIC'}.issubset({l['key'] for l in labels_for(project)}):raise ValueError('Model BIO cần hai nhãn TOXIC và NON_TOXIC đang bật.')
        from .transformer_models import predict
        return predict(run,texts)
    artifact=path/'classifier.joblib';model=load_artifact(str(artifact),artifact.stat().st_mtime_ns)
    report=json.loads(run.report);keys=report.get('label_keys',['NON_TOXIC','TOXIC'])
    start=time.perf_counter();pred=model.predict(texts);ms=(time.perf_counter()-start)*1000/max(1,len(texts))
    return [{'label':keys[int(v)],'spans':[],'latency_ms':ms,'model_version':run.name,'input_tokens':0,'output_tokens':0,'estimated_cost_usd':0,'config_snapshot':{'model_run_id':run.id,'algorithm':run.algorithm}} for v in pred]

def gemini_predict(text):
    if not settings.GEMINI_API_KEY:raise ValueError('Chưa cấu hình GEMINI_API_KEY trên máy chủ.')
    if not settings.GEMINI_MODEL:raise ValueError('Cần đặt GEMINI_MODEL hoặc chọn kết nối API trong dự án.')
    from integrations.models import ProviderConnection
    from integrations.providers.gemini import GeminiAdapter
    c=ProviderConnection(kind='gemini',name='Gemini .env',model=settings.GEMINI_MODEL,base_url='https://generativelanguage.googleapis.com/v1beta',input_price=settings.GEMINI_INPUT_PRICE,output_price=settings.GEMINI_OUTPUT_PRICE)
    labels=[{'key':'NON_TOXIC','name':'Không độc hại'},{'key':'TOXIC','name':'Độc hại'}]
    return GeminiAdapter().predict(text,labels,c,settings.GEMINI_API_KEY)
