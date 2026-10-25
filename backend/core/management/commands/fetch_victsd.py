from django.conf import settings
from django.core.management.base import BaseCommand
import httpx,hashlib,json
class Command(BaseCommand):
    help='Download official public ViCTSD CSV files; retain source and checksums.'
    def handle(self,*a,**kw):
        root=settings.PRIVATE_DATA/'victsd';root.mkdir(parents=True,exist_ok=True);manifest={}
        with httpx.Client(timeout=60,follow_redirects=True) as c:
            for split in ('train','valid','test'):
                name='ViCTSD_'+split+'.csv';url='https://raw.githubusercontent.com/tarudesu/ViCTSD/e1ffb854ef7b7b7ae45a56d132c1f125e02e55e2/'+name
                r=c.get(url);r.raise_for_status();(root/name).write_bytes(r.content)
                manifest[name]={'url':url,'sha256':hashlib.sha256(r.content).hexdigest()}
        (root/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        self.stdout.write(str(root))
