"""Reproducible local classifier training. Never select parameters on test."""
import csv, hashlib, json, time, unicodedata
from pathlib import Path
import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix, classification_report

def canonical(text):
    return ' '.join(unicodedata.normalize('NFC', str(text)).casefold().split())

def read_csv(path,label_keys=None):
    label_keys=label_keys or ['NON_TOXIC','TOXIC']
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows=list(csv.DictReader(f))
    out=[]
    for i,r in enumerate(rows):
        text=(r.get('Comment') or r.get('text') or '').strip()
        label=r.get('Toxicity',r.get('label',''))
        if label in label_keys:label=label_keys.index(label)
        try:label=int(label)
        except (ValueError,TypeError):raise ValueError(f'Dòng {i+2}: nhãn cần là key của dự án hoặc chỉ số lớp.')
        if text and label in range(len(label_keys)):out.append({'id':r.get('') or r.get('id') or str(i),'text':text,'label':label})
        else:raise ValueError(f'Dòng {i+2}: thiếu văn bản hoặc nhãn không hợp lệ.')
    if not out:raise ValueError('Tập dữ liệu rỗng.')
    if len(out)>100000:raise ValueError('Giới hạn 100.000 mẫu cho bản đồ án.')
    return out

def metrics(y,p,label_keys=None):
    label_keys=label_keys or ['NON_TOXIC','TOXIC'];classes=list(range(len(label_keys)))
    pr,re,f1,_=precision_recall_fscore_support(y,p,labels=classes,average='macro',zero_division=0)
    return {'accuracy':float(accuracy_score(y,p)),'precision':float(pr),'recall':float(re),'macro_f1':float(f1),
            'confusion_matrix':confusion_matrix(y,p,labels=classes).tolist(),
            'per_class':classification_report(y,p,labels=classes,target_names=label_keys,output_dict=True,zero_division=0),'n':len(y)}

def train(train_path,valid_path,test_path,output_dir,progress=None,dataset_name='CSV do nhóm cung cấp',algorithm_key='logistic_regression',label_keys=None):
    from experiments.algorithms.registry import algorithm
    spec=algorithm(algorithm_key);label_keys=label_keys or ['NON_TOXIC','TOXIC']
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    raw={k:read_csv(v,label_keys) for k,v in [('train',train_path),('validation',valid_path),('test',test_path)]}
    # Test stays intact. Remove overlaps from validation, then train, and deduplicate those splits.
    protected={canonical(r['text']) for r in raw['test']}
    clean={'test':raw['test']};removed={}
    for split in ('validation','train'):
        seen=set(protected);clean[split]=[]
        for r in raw[split]:
            h=canonical(r['text'])
            if h not in seen:clean[split].append(r);seen.add(h)
        removed[split]=len(raw[split])-len(clean[split]);protected|=seen
    if any(len({r['label'] for r in clean[k]})!=len(label_keys) for k in clean):raise ValueError('Mỗi split phải có đủ các lớp trong bộ nhãn dự án.')
    x={k:[r['text'] for r in v] for k,v in clean.items()};y={k:[r['label'] for r in v] for k,v in clean.items()}
    start=time.perf_counter();trials=[];best=None
    for i,c in enumerate(spec['values']):
        if progress:progress(15+i*20,f"Huấn luyện {spec['parameter']}={c}")
        model=Pipeline([('tfidf',TfidfVectorizer(analyzer='char',ngram_range=(3,5),min_df=2,max_features=60000,sublinear_tf=True)),('classifier',spec['factory'](c))])
        model.fit(x['train'],y['train'])
        m=metrics(y['validation'],model.predict(x['validation']),label_keys);trials.append({spec['parameter']:c,'validation_macro_f1':m['macro_f1']})
        if best is None or m['macro_f1']>best[0]:best=(m['macro_f1'],model,c)
    elapsed=time.perf_counter()-start
    model=best[1];t=time.perf_counter();pred=model.predict(x['test']);latency=(time.perf_counter()-t)/len(pred)*1000
    majority=max(set(y['train']),key=y['train'].count)
    report={'name':spec['name'],'algorithm':algorithm_key,'label_keys':label_keys,'selected_parameter':{spec['parameter']:best[2]},'dataset':dataset_name,'seed':42,'selected_C':best[2] if spec['parameter']=='C' else None,
            'raw_counts':{k:len(v) for k,v in raw.items()},'counts':{k:len(v) for k,v in clean.items()},'removed_duplicates_or_overlaps':removed,
            'selection':'Chọn siêu tham số bằng validation Macro-F1; test chỉ chấm cấu hình đã chọn, không fit thêm validation.',
            'trials':trials,'test':metrics(y['test'],pred,label_keys),'majority_baseline':metrics(y['test'],[majority]*len(y['test']),label_keys),'train_seconds':elapsed,'mean_prediction_ms':latency,
            'source':'https://github.com/tarudesu/ViCTSD' if dataset_name=='UIT-ViCTSD' else 'CSV do người dùng cung cấp','source_files_sha256':{k:hashlib.sha256(Path(v).read_bytes()).hexdigest() for k,v in [('train',train_path),('validation',valid_path),('test',test_path)]},
            'scope':'Kết quả chỉ áp dụng trên tập test đã cung cấp; chưa chứng minh tổng quát hóa sang nguồn khác.'}
    joblib.dump(model,out/'classifier.joblib',compress=3)
    (out/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'test_predictions.json').write_text(json.dumps([{'id':r['id'],'label':r['label'],'prediction':int(p)} for r,p in zip(clean['test'],pred)]),encoding='utf-8')
    if progress:progress(100,'Hoàn tất')
    return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--output',required=True);a=p.parse_args();r=Path(a.data)
    report=train(r/'ViCTSD_train.csv',r/'ViCTSD_valid.csv',r/'ViCTSD_test.csv',a.output,dataset_name='UIT-ViCTSD')
    print(json.dumps({'test':report['test'],'counts':report['counts'],'train_seconds':report['train_seconds']},ensure_ascii=False))
