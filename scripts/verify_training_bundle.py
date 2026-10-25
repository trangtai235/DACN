"""Verify imported files without claiming a historical training execution."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent


def file_sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def verify(weights=False):
    manifest=json.loads((ROOT/'training/provenance/import_manifest.json').read_text(encoding='utf-8'))
    failures=[]
    for record in manifest['files']:
        path=ROOT/record['path']
        ok=path.is_file() and file_sha(path)==record['sha256']
        print(('OK   ' if ok else 'FAIL ')+record['path'])
        if not ok:failures.append(record['path'])
    for model in manifest['model_comparison']:
        key=model['model'];folder=ROOT/model['app_artifact_directory']
        for name,group in [('metrics.json','metrics'),('config.json','config')]:
            reference=ROOT/'training/evidence/imported/after'/group/(key+'.json')
            target=folder/name
            if not target.exists():
                print('SKIP app file not installed:',target.relative_to(ROOT));continue
            ok=file_sha(reference)==file_sha(target)
            print(('OK   ' if ok else 'FAIL ')+key+' app '+name)
            if not ok:failures.append(str(target.relative_to(ROOT)))
        if weights:
            target=folder/'model.safetensors';prefix=model.get('provided_weight_sha256_prefix')
            if not target.exists():
                print('SKIP weights not installed:',key);continue
            if not prefix:
                print('SKIP no supplied hash to compare:',key);continue
            actual=file_sha(target);ok=actual.startswith(prefix)
            print(('OK   ' if ok else 'FAIL ')+key+' weights SHA-256 '+actual)
            if not ok:failures.append(str(target.relative_to(ROOT)))
    print('Notebook is excluded from the distributed source; archived metadata is retained for provenance.')
    print('This verifies file consistency, not who/where/when historical training ran.')
    if failures:raise SystemExit(1)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--weights',action='store_true',help='Also hash installed weights (about 3.9 GB)')
    args=parser.parse_args();verify(args.weights)
