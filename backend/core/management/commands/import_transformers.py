import json
from types import SimpleNamespace
from django.conf import settings
from django.core.management.base import BaseCommand
from core.models import Project
from core.services.transformer_models import predict,artifact_digest
from core.services.model_registry import register_bundled,BUNDLED_MODELS,BUNDLE_DIRECTORY

class Command(BaseCommand):
    help='Validate local Transformer inference and replace legacy model choices.'
    def add_arguments(self,parser):
        parser.add_argument('--verify',action='store_true')
    def handle(self,*args,**options):
        root=settings.BASE_DIR/'artifacts'/'transformers'/BUNDLE_DIRECTORY
        if options['verify']:
            for key,_ in BUNDLED_MODELS:
                path=root/key
                if not (path/'model.safetensors').exists():
                    self.stdout.write(f'{key}: missing weights');continue
                run=SimpleNamespace(artifact_path=str(path),id=0,name=key,algorithm='transformer_bio')
                texts=['Video hay, cảm ơn bạn.','Mày là đồ ngu.','🙂 bình luận\n nhiều dòng','','bình luận dài ' * 300]
                results=predict(run,texts)
                if len(results)!=len(texts):raise ValueError('Incomplete inference results')
                for text,result in zip(texts,results):
                    if result['label'] not in ('TOXIC','NON_TOXIC'):raise ValueError('Invalid sentence label')
                    for span in result['spans']:
                        if not 0<=span['start']<span['end']<=len(text):raise ValueError('Invalid offsets')
                (path/'verified.json').write_text(json.dumps({'inference_passed':True,'artifact_sha256':artifact_digest(path),'samples':results},ensure_ascii=False,indent=2),encoding='utf-8')
                self.stdout.write(f'{key}: real inference passed ({len(texts)} samples)')
        for project in Project.objects.all():register_bundled(project)
        self.stdout.write('Project model registries updated; legacy records retained as retired.')
