from core.services.transformer_models import artifact_digest
import json,hashlib
from pathlib import Path
from django.db import transaction
from django.conf import settings
from core.models import Comment
from experiments.models import BenchmarkRun,ModelRun
from experiments.training import read_csv,metrics
from core.services.providers import local_predict,gemini_predict,model_for
from integrations.models import ProviderConnection
from integrations.registry import predict,snapshot
from studio.services.projects import labels_for,writable,mutation_guard
from .runner import tick
from .pinning import pin,file_hash,connection_identity

def run(job,p):
    writable(job.project);model=model_for(job.project,p.get('model_id'));model_report=json.loads(model.report);keys=model_report.get('label_keys',['NON_TOXIC','TOXIC'])
    connection=ProviderConnection.objects.get(project=job.project,pk=p['connection_id']) if p.get('connection_id') else None
    labels=labels_for(job.project)
    if {x['key'] for x in labels}!=set(keys):raise ValueError('Bộ nhãn dự án và model cần trùng nhau khi so sánh.')
    path=Path(p['test_path'])
    identity={'model_id':model.id,'artifact_sha256':artifact_digest(model.artifact_path),'test_sha256':file_hash(path),'limit':p['limit'],'labels':labels,'connection':connection_identity(connection) or {'kind':'gemini_env','model':settings.GEMINI_MODEL,'input_price':settings.GEMINI_INPUT_PRICE,'output_price':settings.GEMINI_OUTPUT_PRICE}}
    pin(job,identity)
    rows=read_csv(path,keys)[:min(1000,int(p['limit']))];trained=local_predict(job.project,[r['text'] for r in rows],model.id)
    done=job.checkpoint.get('predictions',[]);times=[v['latency_ms'] for v in done];cost=sum(v['estimated_cost_usd'] for v in done);tokens=sum(v['input_tokens']+v['output_tokens'] for v in done)
    for i,row in enumerate(rows[len(done):],start=len(done)):
        tick(job,i/len(rows)*100,f'API {i+1}/{len(rows)}')
        v=predict(connection,row['text'],labels) if connection else gemini_predict(row['text']);done.append(v);times.append(v['latency_ms']);cost+=v['estimated_cost_usd'];tokens+=v['input_tokens']+v['output_tokens'];tick(job,(i+1)/len(rows)*100,f'API {i+1}/{len(rows)}',{'predictions':done})
    y=[r['label'] for r in rows];local=[keys.index(r['label']) for r in trained];remote=[keys.index(r['label']) for r in done]
    report={'dataset':model_report.get('dataset','CSV test'),'sample_count':len(rows),'paired':True,'label_keys':keys,'local':metrics(y,local,keys),'gemini':metrics(y,remote,keys),'api':metrics(y,remote,keys),'local_ms':sum(v['latency_ms'] for v in trained)/len(trained),'gemini_ms':sum(times)/len(times),'tokens':tokens,'estimated_cost_usd':cost,'model':connection.model if connection else 'Gemini .env','local_model_id':model.id,'connection':snapshot(connection) if connection else {'kind':'gemini_env'},'limitations':'Chấm cùng ID test; tự chọn prefix không bảo đảm đại diện. Chi phí API theo giá cấu hình, không phải hóa đơn.'}
    with transaction.atomic():
        mutation_guard(job.project,job.actor,True)
        obj=BenchmarkRun.objects.create(project=job.project,provider=connection.kind if connection else 'gemini',model_name=report['model'],dataset_hash=hashlib.sha256(path.read_bytes()).hexdigest(),report=json.dumps(report,ensure_ascii=False),predictions=json.dumps([{'id':r['id'],'label':r['label'],'local':l,'api':a} for r,l,a in zip(rows,local,remote)]))
    return {'benchmark_id':obj.id,'report':report}
