"""No Node/npm dependency: publish editable ES modules and static public assets."""
from pathlib import Path
import shutil
import hashlib
import re
root=Path(__file__).resolve().parent.parent
out=root/'dist';assets=out/'assets';assets.mkdir(parents=True,exist_ok=True)
# Remove generated assets only; source lives under frontend/.
for item in assets.iterdir():
    if item.is_dir():shutil.rmtree(item)
    else:item.unlink()
shutil.copyfile(root/'frontend/index.html',out/'index.html')
shutil.copytree(root/'frontend/src',assets,dirs_exist_ok=True)
shutil.copytree(root/'frontend/public',assets,dirs_exist_ok=True)
# Version every module import, not just app.js: browsers cache ES modules separately.
digest=hashlib.sha256()
for source in sorted((root/'frontend').rglob('*')):
    if source.is_file():
        digest.update(str(source.relative_to(root/'frontend')).encode())
        digest.update(source.read_bytes())
version=digest.hexdigest()[:12]
for module in assets.rglob('*.js'):
    text=module.read_text(encoding='utf-8-sig')
    text=re.sub(r"(['\"])(\.{1,2}/[^'\"?]+\.js)\1",lambda m:f'{m[1]}{m[2]}?v={version}{m[1]}',text)
    module.write_text(text,encoding='utf-8')
index=out/'index.html'
text=index.read_text(encoding='utf-8')
text=re.sub(r'(/assets/[^"?]+\.(?:js|css))',lambda m:f'{m[1]}?v={version}',text)
index.write_text(text,encoding='utf-8')
print('Built frontend/ → dist/ (no npm required).')
