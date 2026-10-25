import json
from types import SimpleNamespace
from django.conf import settings
from django.core.management.base import BaseCommand
from core.models import Project
from core.services.transformer_models import predict,artifact_digest
from core.services.model_registry import register_bundled

class Command(BaseCommand):
    help='Validate local Transformer inference and replace legacy model choices.'
    def add_arguments(self,parser):
        parser.add_argument('--verify',action='store_true')
    def handle(self,*args,**options):
        root=settings.BASE_DIR/'artifacts'/'transformers'
        if options['verify']:
            for key in ['phobert-base','xlmr-large']:
                path=root/key
                if not (path/'model.safetensors').exists():
                    self.stdout.write(f'{key}: missing weights');continue
                run=SimpleNamespace(artifact_path=str(path),id=0,name=key,algorithm='transformer_bio')
                texts=['Video hay, cảm ơn bạn.','Mày là đồ ngu.','🙂 bình luận\n nhiều dòng']
                results=predict(run,texts)
                for text,result in zip(texts,results):
                    for span in result['spans']:
                        if not 0<=span['start']<span['end']<=len(text):raise ValueError('Invalid offsets')
                (path/'verified.json').write_text(json.dumps({'inference_passed':True,'artifact_sha256':artifact_digest(path),'samples':results},ensure_ascii=False,indent=2),encoding='utf-8')
                self.stdout.write(f'{key}: real inference passed ({len(texts)} samples)')
        for project in Project.objects.all():register_bundled(project)
        self.stdout.write('Project model registries updated; legacy records retained as retired.')
