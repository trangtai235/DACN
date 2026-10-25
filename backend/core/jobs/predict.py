from core.services.transformer_models import artifact_digest
from django.db import transaction
from django.conf import settings
from core.models import Comment,Prediction
from core.services.providers import local_predict,gemini_predict,model_for
from integrations.models import ProviderConnection
from integrations.registry import predict,snapshot
from studio.services.projects import labels_for,writable,mutation_guard
from .runner import tick
from .pinning import pin,file_hash,connection_identity
from pathlib import Path

def run(job,p):
    writable(job.project);provider=p.get('provider','local');labels=labels_for(job.project);keys={x['key'] for x in labels}
    completed=set(job.checkpoint.get('completed_ids',[]));qs=Comment.objects.filter(project=job.project,unusable=False)
    if p.get('source_id'):qs=qs.filter(source_id=p['source_id'])
    if not p.get('replace_ai'):qs=qs.filter(ai_label__isnull=True)
    # Frozen research labels/groups must remain invariant even when re-annotating AI.
    qs=qs.filter(first_frozen_at__isnull=True).exclude(id__in=completed);rows=list(qs.order_by('id'))
    connection=ProviderConnection.objects.get(project=job.project,pk=p['connection_id']) if p.get('connection_id') else None
    model_id=p.get('model_id') or (model_for(job.project).id if provider=='local' and model_for(job.project) else None)
    run=model_for(job.project,model_id) if provider=='local' else None
    tick(job,0,'Đang chuẩn bị model và kiểm tra cấu hình')
    pin(job,{'model_id':model_id,'artifact_sha256':artifact_digest(run.artifact_path) if run else None,'labels':labels,'connection':connection_identity(connection) or ({'kind':'gemini_env','model':settings.GEMINI_MODEL} if provider!='local' else None)})
    # Persist small batches before doing more inference. Transformer weights stay
    # cached, while cancellation and saved suggestions no longer wait for all rows.
    batch_size=8 if run and run.algorithm=='transformer_bio' else 128
    local={}
    for i,row in enumerate(rows):
        tick(job,i/max(1,len(rows))*100,f'Gợi ý {i+1}/{len(rows)}')
        value=job.checkpoint.get('pending',{}).get(str(row.id))
        if value is None:
            if provider=='local':
                if row.id not in local:
                    batch=rows[i:i+batch_size]
                    tick(job,i/max(1,len(rows))*100,f'Đang chạy model: {i+1}–{i+len(batch)}/{len(rows)}')
                    values=local_predict(job.project,[r.text for r in batch],model_id)
                    local={r.id:v for r,v in zip(batch,values,strict=True)}
                value=local.pop(row.id)
            else:value=predict(connection,row.text,labels) if connection else gemini_predict(row.text)
        tick(job,i/max(1,len(rows))*100,'Đã nhận kết quả suy luận',{'pending':{str(row.id):value}})
        if value['label'] not in keys:raise ValueError('Model không tương thích bộ nhãn dự án. Chọn model/API khác.')
        config=value.pop('config_snapshot',{})
        if connection:config=snapshot(connection)
        with transaction.atomic():
            mutation_guard(job.project,job.actor,True)
            locked=Comment.objects.select_for_update().get(pk=row.pk)
            if locked.first_frozen_at:continue
            Prediction.objects.create(comment=locked,provider=connection.kind if connection else provider,config_snapshot=config,**value)
            locked.ai_label=value['label'];locked.ai_provider=connection.kind if connection else provider;locked.revision+=1;locked.save()
        completed.add(row.id);tick(job,(i+1)/max(1,len(rows))*100,f'Đã gợi ý {i+1}/{len(rows)}',{'completed_ids':sorted(completed),'pending':{}})
    return {'processed':len(rows),'provider':connection.kind if connection else provider,'model_id':model_id}
