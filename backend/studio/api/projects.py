from datetime import timedelta
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from .common import *
from studio.services.projects import PRESETS

@api
@require_POST
def settings_view(request):
    p=data(request);project=project_for(request,p['project'],True);prefs=ensure(project)
    if p.get('action')=='delete':
        if project.owner_id!=request.user.id or p.get('confirm')!=project.name:raise PermissionError('Chủ dự án cần nhập đúng tên để xóa.')
        # Archive is reversible; database records and version history are retained.
        prefs.archived=True;prefs.locked=True;prefs.save();return JsonResponse({'ok':True,'archived':True})
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
    prefs.save();audit(project,request.user,'project_settings_updated')
    return JsonResponse({'preferences':pref_json(prefs)})

@api
@require_POST
def label_settings(request):
    p=data(request);project=project_for(request,p['project'],True);writable(project)
    if p.get('preset'):
        preset=PRESETS.get(p['preset'])
        if not preset:raise ValueError('Preset không hợp lệ.')
        if Annotation.objects.filter(comment__project=project).exists() or project.comments.filter(first_frozen_at__isnull=False).exists():raise ValueError('Dự án đã có nhãn người. Tạo dự án khác để đổi preset.')
        with transaction.atomic():
            ProjectLabel.objects.filter(project=project).update(enabled=False)
            for i,(key,name,color,description) in enumerate(preset):ProjectLabel.objects.update_or_create(project=project,key=key,defaults={'name':name,'color':color,'description':description,'order':i,'enabled':True})
    else:
        key=str(p.get('key','')).strip().upper();name=str(p.get('name','')).strip();color=str(p.get('color','#4f78a5'))
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}',key) or not name or len(name)>120 or not re.fullmatch('#[0-9A-Fa-f]{6}',color):raise ValueError('Key gồm A-Z/0-9/_, tên tối đa 120 ký tự, màu #RRGGBB.')
        obj=ProjectLabel.objects.filter(project=project,key=key).first()
        if obj and p.get('action')=='delete':
            used=Annotation.objects.filter(label=obj).exists() or GoldAnnotation.objects.filter(label=obj).exists()
            if not used:
                pools=[Annotation.objects.filter(comment__project=project).values_list('spans',flat=True),GoldAnnotation.objects.filter(comment__project=project).values_list('spans',flat=True),Prediction.objects.filter(comment__project=project).values_list('spans',flat=True)]
                used=any(any(s.get('label')==key for s in spans) for pool in pools for spans in pool)
            if used:raise ValueError('Nhãn đã dùng trong câu hoặc spans: chỉ tắt để giữ lịch sử.')
            obj.delete()
        else:ProjectLabel.objects.update_or_create(project=project,key=key,defaults={'name':name,'description':str(p.get('description',''))[:3000],'color':color,'enabled':p.get('enabled',True),'order':int(p.get('order',0))})
    audit(project,request.user,'labels_updated');return JsonResponse({'labels':labels_for(project,False)})

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
