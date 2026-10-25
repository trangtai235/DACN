import csv,io,json,hashlib
from pathlib import Path
from core.models import Source,Comment,Prediction
from studio.services.projects import labels_for,writable,mutation_guard
from django.db import transaction
from .runner import tick

def run(job,p):
    writable(job.project);content=Path(p['file_path']).read_text(encoding='utf-8-sig');reader=csv.DictReader(io.StringIO(content));rows=list(reader)
    if not rows or len(rows)>100000:raise ValueError('CSV cần từ 1 đến 100.000 dòng.')
    source=Source.objects.get(project=job.project,pk=p['source_id']);keys={x['key'] for x in labels_for(job.project)};mapping=p.get('mapping',{});done=int(job.checkpoint.get('row',0));imported=int(job.checkpoint.get('imported',0));duplicates=0;rejected=[]
    for i,row in enumerate(rows[done:],start=done):
        tick(job,i/len(rows)*100,f'Nhập dòng {i+1}/{len(rows)}')
        text=(row.get(mapping.get('text','text')) or row.get('Comment') or '').strip()
        if not text or len(text)>20000:rejected.append(i+2);continue
        label=(row.get(mapping.get('label','label')) or '').strip()
        if label in ('0','1') and keys=={'NON_TOXIC','TOXIC'}:label=['NON_TOXIC','TOXIC'][int(label)]
        if label and label not in keys:rejected.append(i+2);continue
        with transaction.atomic():
            mutation_guard(job.project,job.actor,True)
            c,created=Comment.objects.get_or_create(project=job.project,digest=hashlib.sha256(text.encode()).hexdigest(),defaults={'source':source,'text':text,'author':str(row.get(mapping.get('author','author'),'') or '')[:200],'external_id':str(row.get(mapping.get('id','id'),'') or '')[:120]})
            if created:
                imported+=1
                if label:c.ai_label=label;c.ai_provider='csv_import';c.save()
            else:duplicates+=1
        tick(job,(i+1)/len(rows)*100,f'Đã nhập {imported} mẫu',{'row':i+1,'imported':imported})
    return {'imported':imported,'duplicates':duplicates,'rejected_count':len(rejected),'rejected_lines':rejected[:200],'labels_imported_as':'Gợi ý CSV, chưa phải nhãn người độc lập.'}
