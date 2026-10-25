from core.services.collection import collection_limit
from .common import *

@api
@require_POST
def import_comments(request):
    p=data(request);project=project_for(request,p['project'],True)
    text=str(p.get('text',''));rows=[]
    if 'file' in request.FILES:
        f=request.FILES['file']
        if f.size>5*1024*1024:raise ValueError('File CSV tối đa 5 MB.')
        try:reader=csv.DictReader(io.StringIO(f.read().decode('utf-8-sig')));rows=[(r.get('text') or r.get('Comment') or '').strip() for r in reader]
        except UnicodeDecodeError:raise ValueError('CSV cần mã hóa UTF-8 và cột text hoặc Comment.')
    else:rows=[r.strip() for r in text.splitlines() if r.strip()]
    if not rows or len(rows)>10000:raise ValueError('Cần từ 1 đến 10.000 bình luận.')
    with transaction.atomic():
        source=Source.objects.create(project=project,name=str(p.get('name','Dữ liệu nhập'))[:200],kind='csv' if request.FILES else 'manual');count=0
        for text in rows:
            if not text:continue
            if len(text)>20000:raise ValueError('Một bình luận vượt 20.000 ký tự.')
            _,created=Comment.objects.get_or_create(project=project,digest=hashlib.sha256(text.encode()).hexdigest(),defaults={'source':source,'text':text});count+=int(created)
        audit(project,request.user,'comments_imported',count=count)
    return JsonResponse({'imported':count,'duplicates':len(rows)-count})


@api
@require_POST
def youtube(request):
    p=data(request);project=project_for(request,p['project'],True);url=str(p.get('url',''))
    match=re.search(r'(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})',url)
    video=match.group(1) if match else url
    if not re.fullmatch('[A-Za-z0-9_-]{11}',video):raise ValueError('URL hoặc video ID chưa đúng.')
    from studio.models import UserProfile
    profile=UserProfile.objects.filter(user=request.user).first()
    if not settings.YOUTUBE_API_KEY and not (profile and profile.youtube_key):raise ValueError('Cần cấu hình YouTube API key tại tài khoản hoặc máy chủ.')
    limit=collection_limit(p.get('limit'))
    source=Source.objects.create(project=project,name=video,kind='youtube',external_id=video,url='https://www.youtube.com/watch?v='+video)
    job=enqueue(project,request.user,'youtube',{'video_id':video,'source_id':source.id,'include_replies':p.get('include_replies',True),'limit':limit});return JsonResponse({'job':report_job(job)})

