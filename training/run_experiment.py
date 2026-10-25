"""Run the supplied trainer/evaluator and record evidence of this actual run."""
import argparse
from datetime import datetime,timezone
import hashlib
from importlib.metadata import version,PackageNotFoundError
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parent.parent
CONFIG=ROOT/'training/configs/three_models.json'
DATA=ROOT/'datasets/ViHOS'
TRAINER=ROOT/'training/vihos/train_vihos.py'


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(4*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def stamp():return datetime.now(timezone.utc).isoformat()


def hashes(paths):
    return {p.relative_to(ROOT).as_posix():sha(p) for p in paths}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True,choices=['phobert-base','xlmr-base','xlmr-large'])
    parser.add_argument('--mode',choices=['train','smoke','evaluate'],default='train')
    parser.add_argument('--weights',help='Existing model directory for evaluate mode only')
    parser.add_argument('--dry-run',action='store_true',help='Show command; do not train, download or create run evidence')
    parser.add_argument('--allow-dirty',action='store_true',help='Allow uncommitted source; manifest marks this explicitly')
    args=parser.parse_args()
    if args.weights and args.mode!='evaluate':parser.error('--weights is only for evaluate mode')
    config=json.loads(CONFIG.read_text(encoding='utf-8'))[args.model]
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+args.model+'-'+args.mode+'-'+uuid.uuid4().hex[:6]
    evidence=ROOT/'training/evidence/runs'/run_id
    output=ROOT/'training/runs'/run_id/'model'
    dataset_files=sorted(DATA.rglob('*.csv'))
    if len(dataset_files)!=5:raise SystemExit('Expected exactly five supplied CSV files under datasets/ViHOS.')
    source_files=sorted((ROOT/'training/vihos').glob('*.py'))+[CONFIG,Path(__file__).resolve(),ROOT/'requirements/base.txt',ROOT/'requirements/transformers.txt',ROOT/'.gitattributes',ROOT/'scripts/verify_training_bundle.py']
    if args.mode=='evaluate':
        weights=Path(args.weights).resolve() if args.weights else ROOT/'backend/artifacts/transformers/vihos-full'/args.model
        command=[sys.executable,'-X','utf8',str(ROOT/'training/vihos/eval_model.py'),
                 '--model',str(weights),'--data-root',str(DATA),'--out',str(evidence/'evaluation.json')]
    else:
        weights=None
        command=[sys.executable,'-X','utf8',str(TRAINER),'--data-root',str(DATA),'--out',str(output)]
        for option in ['model','variant','epochs','batch_size','lr','grad_accum','max_len','seed']:
            command.extend(['--'+option.replace('_','-'),str(config[option])])
        command.append('--smoke' if args.mode=='smoke' else '--test')
    print('Mode:',args.mode)
    print('Command:',subprocess.list2cmdline(command))
    print('Evidence directory:',evidence.relative_to(ROOT))
    print('New model output:',output.relative_to(ROOT) if weights is None else '(existing weights are read only)')
    if args.dry_run:
        print('DRY RUN: no training, API call, download or evidence generation.');return
    if weights is not None and (not weights.is_dir() or not (weights/'model.safetensors').is_file()):
        raise SystemExit('Evaluation requires an existing model directory containing model.safetensors.')
    required=[p.relative_to(ROOT).as_posix() for p in source_files+dataset_files]
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=all','--',*required],cwd=ROOT,text=True).strip()
    tracked=set(subprocess.check_output(['git','ls-files','-z','--',*required],cwd=ROOT).decode().split('\0'))
    untracked=[p for p in required if p not in tracked]
    if (dirty or untracked) and not args.allow_dirty:
        raise SystemExit('Commit dataset, trainer, configuration and runner first. Use --allow-dirty only for a run explicitly marked as uncommitted.')
    packages={}
    for name in ['torch','transformers','numpy','safetensors','sentencepiece']:
        try:packages[name]=version(name)
        except PackageNotFoundError:packages[name]=None
    import torch
    hardware={'platform':platform.platform(),'python':sys.version,'cuda_available':torch.cuda.is_available(),
              'cuda_version':torch.version.cuda,'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}
    evidence.mkdir(parents=True,exist_ok=False)
    if weights is None:output.parent.mkdir(parents=True,exist_ok=False)
    effective={**config}
    if args.mode=='smoke':effective.update(epochs=1,train_limit=300,dev_limit=200)
    record={'event':'actual_process_execution','mode':args.mode,'status':'running','started_at_utc':stamp(),
            'git_commit':commit,'source_clean':not bool(dirty or untracked),'uncommitted_status':dirty,'untracked_required_files':untracked,
            'command':command,'configuration':effective,'source_sha256':hashes(source_files),
            'dataset_sha256':hashes(dataset_files),'packages':packages,'hardware':hardware,
            'output_directory':str(output.relative_to(ROOT)) if weights is None else None,
            'input_weights_directory':str(weights) if weights else None,
            'notes':['A smoke run is not full-data training. Evaluation is not training.',
                     'The supplied original trainer writes dev_best from the final epoch; use history to locate the best-dev epoch.']}
    if weights:
        record['input_artifact_sha256']={p.name:sha(p) for p in sorted(weights.iterdir()) if p.is_file() and p.suffix in ('.json','.safetensors','.txt','.codes')}
    target=evidence/'manifest.json'
    def save():target.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save();start=time.perf_counter();child=None
    env={**os.environ,'PYTHONUTF8':'1','PYTHONUNBUFFERED':'1'}
    try:
        with (evidence/'process.log').open('w',encoding='utf-8') as log:
            child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
            for line in child.stdout:
                print(line,end='',flush=True);log.write(line);log.flush()
            code=child.wait()
        record['return_code']=code;record['status']='completed' if code==0 else 'failed'
    except KeyboardInterrupt:
        if child is not None:child.terminate();child.wait()
        record['status']='interrupted';record['return_code']=130
    except Exception as error:
        record['status']='failed';record['error_type']=type(error).__name__;record['return_code']=1
    finally:
        record['finished_at_utc']=stamp();record['elapsed_seconds']=time.perf_counter()-start
        try:
            record['source_unchanged_during_run']=record['source_sha256']==hashes(source_files)
            record['dataset_unchanged_during_run']=record['dataset_sha256']==hashes(dataset_files)
        except OSError:
            record['source_unchanged_during_run']=False;record['dataset_unchanged_during_run']=False
        if output.exists():
            record['output_artifact_sha256']={p.relative_to(output).as_posix():sha(p) for p in sorted(output.rglob('*')) if p.is_file()}
            metrics=output/'metrics.json'
            if metrics.exists():
                original=metrics.read_bytes();(evidence/'metrics.json').write_bytes(original)
                record['metrics_copy_sha256']=hashlib.sha256(original).hexdigest()
                record['actual_n_train']=json.loads(original).get('n_train')
        record['full_data_training_complete']=(args.mode=='train' and record['status']=='completed'
            and record.get('actual_n_train')==8844 and record['source_unchanged_during_run'] and record['dataset_unchanged_during_run'])
        save()
    print('Evidence saved:',evidence.relative_to(ROOT))
    raise SystemExit(record['return_code'])


if __name__=='__main__':main()
