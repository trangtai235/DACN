import re
from django.db import transaction
from studio.models import ProjectSettings,ProjectLabel
PRESETS={
 'toxicity':[('NON_TOXIC','Không độc hại','#169878','Trao đổi hoặc phê bình nội dung không công kích.'),('TOXIC','Độc hại','#df6675','Lăng mạ, hạ nhục, đe dọa hoặc công kích.')],
 'hate_speech':[('CLEAN','Bình thường','#169878','Không xúc phạm hoặc thù ghét.'),('OFFENSIVE','Xúc phạm','#e7a645','Ngôn từ xúc phạm hoặc thô tục.'),('HATE','Thù ghét','#df6675','Tấn công nhóm người theo đặc điểm nhóm.')]}
def ensure(project):
    prefs,_=ProjectSettings.objects.get_or_create(project=project)
    if not ProjectLabel.objects.filter(project=project).exists():
        for i,(key,name,color,description) in enumerate(PRESETS['toxicity']):
            ProjectLabel.objects.get_or_create(project=project,key=key,defaults={'name':name,'color':color,'description':description,'order':i})
    return prefs

def labels_for(project,enabled=True):
    ensure(project);qs=ProjectLabel.objects.filter(project=project)
    if enabled:qs=qs.filter(enabled=True)
    return [{'id':x.id,'key':x.key,'name':x.name,'description':x.description,'color':x.color,'enabled':x.enabled,'order':x.order} for x in qs]
def writable(project):
    p=ensure(project)
    if p.locked or p.archived:raise PermissionError('Dự án đã khóa/lưu trữ. Quản lý cần mở lại trước khi thay đổi dữ liệu.')
    return p
def label_for(project,key,nullable=False):
    if key is None and nullable:return None
    try:return ProjectLabel.objects.get(project=project,key=key,enabled=True)
    except ProjectLabel.DoesNotExist:raise ValueError('Nhãn không thuộc bộ nhãn đang hoạt động của dự án.')
def validate_spans(text,spans,project):
    if not isinstance(spans,list) or len(spans)>200 or any(not isinstance(s,dict) for s in spans):raise ValueError('Spans cần là danh sách tối đa 200 đoạn.')
    keys={x['key'] for x in labels_for(project)};out=[];last=0
    for sp in sorted(spans,key=lambda s:s.get('start',-1)):
        start,end=sp.get('start'),sp.get('end');key=sp.get('label')
        if type(start) is not int or type(end) is not int or not 0<=start<end<=len(text) or start<last or key not in keys:raise ValueError('Offset span không hợp lệ hoặc các đoạn chồng nhau.')
        out.append({'start':start,'end':end,'label':key});last=end
    return out

# Call inside an atomic block. Shared order: project prefs → membership → data row.
def mutation_guard(project,user,manage=False):
    from core.models import Membership
    prefs=ProjectSettings.objects.select_for_update().get(project=project)
    member=Membership.objects.select_for_update().filter(project=project,user=user).first()
    if not member or (manage and member.role!='manager' and project.owner_id!=user.id):raise PermissionError('Quyền truy cập dự án đã thay đổi.')
    if prefs.locked or prefs.archived:raise PermissionError('Dự án đã khóa hoặc lưu trữ.')
    return prefs
