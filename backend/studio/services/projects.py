import re
from django.db import transaction
from django.shortcuts import get_object_or_404
from core.models import Source
from studio.models import ProjectSettings,ProjectLabel

def resolve_source(project,value):
    return get_object_or_404(Source,project=project,pk=value) if value not in (None,'') else None
PRESETS={
 'moderation':[('NON_TOXIC','Bình thường','#169878','Trao đổi hoặc phê bình nội dung không công kích và không quảng cáo.'),('TOXIC','Độc hại','#df6675','Lăng mạ, hạ nhục, đe dọa hoặc công kích; ưu tiên TOXIC nếu đồng thời quảng cáo.'),('SPAM','Quảng cáo / Spam','#e7a645','Quảng cáo, bán hàng hoặc lặp nội dung không liên quan; không dùng nếu có công kích.')],
 'toxicity':[('NON_TOXIC','Không độc hại','#169878','Trao đổi hoặc phê bình nội dung không công kích.'),('TOXIC','Độc hại','#df6675','Lăng mạ, hạ nhục, đe dọa hoặc công kích.')],
 'hate_speech':[('CLEAN','Bình thường','#169878','Không xúc phạm hoặc thù ghét.'),('OFFENSIVE','Xúc phạm','#e7a645','Ngôn từ xúc phạm hoặc thô tục.'),('HATE','Thù ghét','#df6675','Tấn công nhóm người theo đặc điểm nhóm.')]}
def ensure(project):
    prefs,created=ProjectSettings.objects.get_or_create(project=project)
    if created and not ProjectLabel.objects.filter(project=project).exists():
        for i,(key,name,color,description) in enumerate(PRESETS['toxicity']):
            ProjectLabel.objects.get_or_create(project=project,key=key,defaults={'name':name,'color':color,'description':description,'order':i})
    return prefs

def labels_for(project,enabled=True):
    ensure(project);qs=ProjectLabel.objects.filter(project=project)
    if enabled:qs=qs.filter(enabled=True)
    return [label_json(x) for x in qs]

def label_json(x):
    return {'id':x.id,'key':x.key,'name':x.name,'description':x.description,'exclusions':x.exclusions,'color':x.color,'enabled':x.enabled,'order':x.order,'revision':x.revision}

def label_used(project,label):
    """History and frozen runs count as use, even after a live annotation is undone."""
    from core.models import Prediction
    from studio.models import Annotation,GoldAnnotation,AnnotationEvent,AutoLabelRun,AutoLabelResult,DatasetVersion,LabelSchema
    key=label.key
    if (Annotation.objects.filter(label=label).exists() or GoldAnnotation.objects.filter(label=label).exists()
        or project.comments.filter(first_label=key).exists()
        or Prediction.objects.filter(comment__project=project,label=key).exists()
        or AutoLabelResult.objects.filter(run__project=project,label=key).exists()):return True
    def mentions(value):
        if isinstance(value,dict):
            if value.get('label')==key or value.get('key')==key:return True
            return any(mentions(v) for v in value.values())
        return isinstance(value,list) and any(mentions(v) for v in value)
    for model,lookup,fields in [(Annotation,'comment__project',['spans']),(GoldAnnotation,'comment__project',['spans']),
        (Prediction,'comment__project',['spans','config_snapshot']),(AnnotationEvent,'comment__project',['before','after']),
        (AutoLabelRun,'project',['labels']),(DatasetVersion,'project',['snapshot'])]:
        if any(mentions(value) for values in model.objects.filter(**{lookup:project}).values_list(*fields) for value in values):return True
    # An immutable schema by itself is a definition, not usage; a decision/dataset makes it history.
    for schema in LabelSchema.objects.filter(project=project):
        if mentions(schema.snapshot) and (schema.pairdecision_set.exists() or schema.feedbackdataset_set.exists()):return True
    return False
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
