from datetime import timedelta
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from .common import *
from studio.services.projects import PRESETS,label_json,label_used

@api
@require_POST
@transaction.atomic
def settings_view(request):
    p=data(request);project=project_for(request,p['project'],True);prefs=ensure(project)
    from studio.services.adaptation import current_schema
    current_schema(project)
    if p.get('action')=='delete':
        if project.owner_id!=request.user.id or p.get('confirm')!=project.name:raise PermissionError('Chủ dự án cần nhập đúng tên để xóa.')
        with transaction.atomic():
            ProjectSettings.objects.select_for_update().get(project=project)
            if Job.objects.filter(project=project,status__in=['queued','running']).exists():
                raise ValueError('Dừng các tác vụ đang chạy trước khi xóa dự án.')
            from reviewing.models import ReviewTask
            # Explicit order handles legacy PROTECT links between comments,
            # sources and restored dataset versions before the project cascade.
            ReviewTask.objects.filter(comment__project=project).delete()
            project.comments.all().delete()
            project.dataset_versions.update(restored_from=None)
            deleted_id=project.pk
            project.delete()
        return JsonResponse({'ok':True,'deleted':deleted_id})
    if 'name' in p:
        name=str(p['name']).strip()
        if not 1<=len(name)<=180:raise ValueError('Tên dự án từ 1 đến 180 ký tự.')
        project.name=name
    if 'description' in p:project.description=str(p['description'])[:3000]
    project.save()
    for key in ('locked','archived','independent'):
        if key in p:
            if type(p[key]) is not bool:raise ValueError('Giá trị checkbox cần boolean.')
            setattr(prefs,key,p[key])
    if 'guidelines' in p:prefs.guidelines=str(p['guidelines'])[:15000]
    if 'redundancy' in p:
        n=int(p['redundancy'])
        if not 1<=n<=5:raise ValueError('Số người trên mỗi mẫu từ 1 đến 5.')
        prefs.redundancy=n
    prefs.save();current_schema(project);audit(project,request.user,'project_settings_updated')
    return JsonResponse({'preferences':pref_json(prefs)})

@api
@require_http_methods(['GET','POST'])
@transaction.atomic
def label_settings(request):
    p=request.GET if request.method=='GET' else data(request)
    project=project_for(request,p['project'],request.method=='POST');prefs=ensure(project)
    from studio.services.adaptation import current_schema
    schema=current_schema(project)
    if request.method=='GET':
        from studio.services.adaptation import compatibility
        can_manage=manager(project,request.user);rows=[]
        for label in ProjectLabel.objects.filter(project=project):
            used=label_used(project,label) if can_manage else None
            rows.append({**label_json(label),'used':used,'can_delete':can_manage and not used})
        return JsonResponse({'project':{'id':project.pk,'name':project.name},'labels':rows,
            'can_manage':can_manage,'locked':prefs.locked,'archived':prefs.archived,
            'schema':{'id':schema.pk,'version':schema.version,'sha256':schema.sha256},
            'local_model':{'name':prefs.active_model.name if prefs.active_model_id else None,**compatibility(prefs.active_model,schema)}})
    mutation_guard(project,request.user,True)
    if p.get('preset'):
        preset=PRESETS.get(p['preset'])
        if not preset:raise ValueError('Preset không hợp lệ.')
        if Annotation.objects.filter(comment__project=project).exists() or project.comments.filter(first_frozen_at__isnull=False).exists():raise ValueError('Dự án đã có nhãn người. Tạo dự án khác để đổi preset.')
        with transaction.atomic():
            for label in ProjectLabel.objects.filter(project=project):label.enabled=False;label.save()
            for i,(key,name,color,description) in enumerate(preset):ProjectLabel.objects.update_or_create(project=project,key=key,defaults={'name':name,'color':color,'description':description,'order':i,'enabled':True})
    else:
        key=str(p.get('key','')).strip().upper();name=str(p.get('name','')).strip();color=str(p.get('color','#4f78a5'))
        obj=get_object_or_404(ProjectLabel.objects.select_for_update(),project=project,pk=p['id']) if p.get('id') else ProjectLabel.objects.filter(project=project,key=key).first()
        if obj and key!=obj.key:raise ValueError('Mã nhãn được giữ ổn định; tạo nhãn mới thay vì đổi mã.')
        if p.get('id') and 'revision' not in p:raise ValueError('Cần revision của nhãn. Tải lại trước khi sửa.')
        if obj and 'revision' in p and int(p['revision'])!=obj.revision:
            return JsonResponse({'error':'Nhãn đã thay đổi ở phiên khác. Nội dung đang soạn được giữ; tải lại nhãn trước khi lưu.'},status=409)
        if obj and p.get('action')=='create':raise ValueError('Mã nhãn đã tồn tại trong dự án.')
        before=label_json(obj) if obj else None
        if p.get('action')=='delete':
            if not obj:raise ValueError('Không tìm thấy nhãn trong dự án.')
            if label_used(project,obj):raise ValueError('Nhãn đã dùng trong câu, spans, dự đoán hoặc lịch sử: chỉ ngừng dùng để giữ dữ liệu.')
            obj.delete()
        else:
            if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}',key) or not name or len(name)>120 or not re.fullmatch('#[0-9A-Fa-f]{6}',color):raise ValueError('Mã gồm A-Z/0-9/_, tên từ 1–120 ký tự, màu #RRGGBB.')
            enabled=p.get('enabled',obj.enabled if obj else True);order=p.get('order',obj.order if obj else 0)
            if type(enabled) is not bool or type(order) is bool or not 0<=int(order)<=9999:raise ValueError('Trạng thái phải là boolean và thứ tự từ 0 đến 9999.')
            obj=obj or ProjectLabel(project=project,key=key)
            for field,value in {'name':name,'description':str(p.get('description',''))[:3000],'exclusions':str(p.get('exclusions',''))[:3000],'color':color,'enabled':enabled,'order':int(order)}.items():setattr(obj,field,value)
            obj.save()
        audit(project,request.user,'label_deleted' if p.get('action')=='delete' else 'label_saved',before=before,after=label_json(obj) if obj.pk else None)
    schema=current_schema(project)
    audit(project,request.user,'labels_updated',schema=schema.pk);return JsonResponse({'labels':labels_for(project,False),'schema_version':schema.version})

@api
@require_POST
def member_settings(request):
    p=data(request);project=project_for(request,p['project'],True);member=get_object_or_404(Membership,project=project,user_id=p['user_id'])
    if member.user_id==project.owner_id:raise ValueError('Không thay đổi vai trò hoặc xóa chủ dự án.')
    if p.get('action')=='remove':member.delete()
    else:
        if p.get('role') not in ('manager','annotator'):raise ValueError('Vai trò không hợp lệ.')
        member.role=p['role'];member.save()
    audit(project,request.user,'membership_updated',user=member.user_id);return JsonResponse({'ok':True})

@api
@require_http_methods(['GET','POST'])
def invite(request):
    p=request.GET if request.method=='GET' else data(request);project=project_for(request,p['project'],True)
    if request.method=='GET':return JsonResponse({'invitations':[{'id':x.id,'email':x.email,'role':x.role,'expires_at':x.expires_at.isoformat(),'accepted':bool(x.accepted_at),'revoked':x.revoked} for x in ProjectInvitation.objects.filter(project=project).order_by('-id')[:100]]})
    if p.get('action')=='revoke':
        obj=get_object_or_404(ProjectInvitation,project=project,pk=p['id']);obj.revoked=True;obj.save();return JsonResponse({'ok':True})
    email=str(p.get('email','')).strip().lower()
    try:validate_email(email)
    except ValidationError:raise ValueError('Email không hợp lệ.')
    role=p.get('role','annotator')
    if role not in ('manager','annotator'):raise ValueError('Vai trò không hợp lệ.')
    token=secrets.token_urlsafe(32)
    obj=ProjectInvitation.objects.create(project=project,email=email,role=role,invited_by=request.user,expires_at=timezone.now()+timedelta(days=7),token_hash=hashlib.sha256(token.encode()).hexdigest())
    url=settings.SITE_URL+'/#invite='+token
    sent=False
    if p.get('send_email') is True:
        send_mail('Lời mời dự án '+project.name,'Bạn được mời tham gia dự án AnnotaFlow. Đăng ký bằng đúng email này rồi mở '+url,settings.DEFAULT_FROM_EMAIL,[email]);sent=True
    audit(project,request.user,'invitation_created',invitation=obj.id)
    return JsonResponse({'id':obj.id,'url':url,'email_sent':sent,'expires_at':obj.expires_at.isoformat(),'email_backend':settings.EMAIL_BACKEND.rsplit('.',1)[-1]})

@api
@require_POST
def accept_invite(request):
    p=data(request);digest=hashlib.sha256(str(p.get('token','')).encode()).hexdigest()
    with transaction.atomic():
        obj=get_object_or_404(ProjectInvitation.objects.select_for_update(),token_hash=digest)
        if obj.revoked or obj.accepted_at or obj.expires_at<timezone.now():raise ValueError('Lời mời đã hết hạn, bị thu hồi hoặc đã sử dụng.')
        if request.user.email.lower()!=obj.email.lower():raise PermissionError('Đăng nhập tài khoản có email trùng lời mời.')
        profile,_=UserProfile.objects.get_or_create(user=request.user)
        if settings.REQUIRE_EMAIL_VERIFICATION and not profile.email_verified:raise PermissionError('Xác minh email trước khi nhận lời mời.')
        Membership.objects.get_or_create(project=obj.project,user=request.user,defaults={'role':obj.role})
        obj.accepted_by=request.user;obj.accepted_at=timezone.now();obj.save();audit(obj.project,request.user,'invitation_accepted')
    return JsonResponse({'project':obj.project_id})
