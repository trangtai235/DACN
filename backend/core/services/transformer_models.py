"""Offline BIO token classifiers; only one set of weights resident at a time."""
import hashlib
import json
import re
import threading
import time
import os
from pathlib import Path

_lock=threading.RLock()
_loaded=None

def artifact_digest(path):
    path=Path(path)
    files=sorted(path.glob('*.safetensors')) if (path/'config.json').exists() else [path/'classifier.joblib']
    files += [p for p in sorted(path.iterdir()) if p.suffix in ('.json','.txt','.codes') and p.name not in ('metrics.json','verified.json')]
    digest=hashlib.sha256()
    for file in files:
        digest.update(file.name.encode())
        with file.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()

def bio_spans(words,tags):
    spans=[]
    for word,tag in zip(words,tags):
        if tag=='B-T' or (tag=='I-T' and (not spans or previous=='O')):
            spans.append({'start':word.start(),'end':word.end(),'label':'TOXIC'})
        elif tag=='I-T':spans[-1]['end']=word.end()
        previous=tag
    return spans

def load_model(path):
    global _loaded
    if _loaded and _loaded[0]==str(path):return _loaded[1:]
    try:
        import torch
        from transformers import AutoModelForTokenClassification,AutoTokenizer
    except ImportError as exc:
        raise ValueError('Cài requirements/transformers.txt trước khi chạy model mới.') from exc
    _loaded=None
    torch.set_num_threads(max(1,int(os.getenv('TRANSFORMER_CPU_THREADS','4'))))
    tokenizer=AutoTokenizer.from_pretrained(str(path),local_files_only=True,trust_remote_code=False,use_fast=(path/'tokenizer.json').exists())
    model,info=AutoModelForTokenClassification.from_pretrained(str(path),local_files_only=True,trust_remote_code=False,use_safetensors=True,output_loading_info=True)
    if info.get('missing_keys') or info.get('unexpected_keys') or info.get('mismatched_keys'):
        raise ValueError('Trọng số không khớp cấu hình model; không dùng trọng số khởi tạo ngẫu nhiên.')
    if set(model.config.id2label.values())!={'O','B-T','I-T'}:raise ValueError('Model cần bộ nhãn BIO: O, B-T, I-T.')
    model.eval()
    _loaded=(str(path),tokenizer,model,torch)
    return tokenizer,model,torch

def predict(run,texts):
    with _lock:
        tokenizer,model,torch=load_model(Path(run.artifact_path))
        limit=model.config.max_position_embeddings-model.config.pad_token_id-1
        budget=limit-tokenizer.num_special_tokens_to_add(False)
        results=[]
        for text in texts:
            start=time.perf_counter()
            words=list(re.finditer(r'\S+',text));tags=[];ids=[];positions=[]
            def flush():
                if not ids:return
                # Both uploaded RoBERTa architectures use <s> tokens </s>.
                encoded=[tokenizer.bos_token_id,*ids,tokenizer.eos_token_id]
                inputs={'input_ids':torch.tensor([encoded]),'attention_mask':torch.ones((1,len(encoded)),dtype=torch.long)}
                with torch.inference_mode():pred=model(**inputs).logits.argmax(-1)[0].tolist()
                raw=pred[1:-1]
                tags.extend(model.config.id2label[raw[pos]] for pos in positions)
                ids.clear();positions.clear()
            # Uploaded metrics specify syllable input. Preserve original whitespace
            # offsets, and use the first subtoken prediction for each syllable.
            for word in words:
                pieces=tokenizer.encode(word.group(),add_special_tokens=False)
                if not pieces:pieces=[tokenizer.unk_token_id]
                if len(pieces)>budget:raise ValueError('Một từ vượt giới hạn token của model.')
                if len(ids)+len(pieces)>budget:flush()
                positions.append(len(ids));ids.extend(pieces)
            flush()
            spans=bio_spans(words,tags)
            results.append({'label':'TOXIC' if spans else 'NON_TOXIC','spans':spans,'latency_ms':(time.perf_counter()-start)*1000,'model_version':run.name,'input_tokens':0,'output_tokens':0,'estimated_cost_usd':0,'config_snapshot':{'model_run_id':run.id,'algorithm':run.algorithm,'sentence_rule':'TOXIC if any predicted toxic span, otherwise NON_TOXIC','alignment':'whitespace syllables; first subtoken; full input in bounded windows'}})
        return results
