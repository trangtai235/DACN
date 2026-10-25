from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from .common import *
from integrations.secrets import encrypt

@api
@require_GET
def profile(request):
    p,_=UserProfile.objects.get_or_create(user=request.user)
    return JsonResponse({'name':request.user.first_name or request.user.username,'username':request.user.username,'email':request.user.email,'language':p.language,'email_verified':p.email_verified,'youtube_configured':bool(p.youtube_key or settings.YOUTUBE_API_KEY)})
@api
@require_POST
def profile_save(request):
    p=data(request);user=request.user;profile,_=UserProfile.objects.get_or_create(user=user)
    if 'name' in p:user.first_name=str(p['name']).strip()[:150]
    if p.get('language') in ('vi','en'):profile.language=p['language']
    if p.get('youtube_key'):profile.youtube_key=encrypt(str(p['youtube_key']))
    if p.get('clear_youtube_key'):profile.youtube_key=''
    if p.get('new_password'):
        if not user.check_password(p.get('current_password','')):raise ValueError('Mật khẩu hiện tại chưa đúng.')
        try:validate_password(p['new_password'],user)
        except ValidationError as e:raise ValueError(' '.join(e.messages))
        user.set_password(p['new_password'])
    user.save();profile.save();update_session_auth_hash(request,user);return JsonResponse({'ok':True})

def verification_mail(user):
    token=signing.dumps({'id':user.id,'email':user.email},salt='annotaflow-email-v1');url=settings.SITE_URL+'/#verify='+token
    send_mail('Xác minh email AnnotaFlow','Mở liên kết để xác minh email: '+url,settings.DEFAULT_FROM_EMAIL,[user.email]);return url
@api
@require_POST
def verification_send(request):
    if not request.user.email:raise ValueError('Tài khoản chưa có email.')
    url=verification_mail(request.user);return JsonResponse({'ok':True,**({'preview_url':url} if settings.DEBUG else {})})
@require_POST
def verification_accept(request):
    try:
        p=data(request);value=signing.loads(str(p.get('token','')),salt='annotaflow-email-v1',max_age=86400)
        user=get_object_or_404(User,pk=value['id'],email=value['email']);profile,_=UserProfile.objects.get_or_create(user=user);profile.email_verified=True;profile.save();user.is_active=True;user.save();return JsonResponse({'ok':True})
    except (signing.BadSignature,ValueError,KeyError):return JsonResponse({'error':'Liên kết xác minh không hợp lệ hoặc quá hạn.'},status=400)
@require_POST
def password_request(request):
    try:p=data(request)
    except ValueError:return JsonResponse({'error':'JSON không hợp lệ.'},status=400)
    email=str(p.get('email','')).strip();user=User.objects.filter(email__iexact=email,is_active=True).first()
    if user:
        token=default_token_generator.make_token(user);url=settings.SITE_URL+f'/#reset={user.id}~{token}'
        send_mail('Đặt lại mật khẩu AnnotaFlow','Mở liên kết để đặt lại mật khẩu: '+url,settings.DEFAULT_FROM_EMAIL,[user.email])
    return JsonResponse({'ok':True,'message':'Nếu tài khoản phù hợp tồn tại, hướng dẫn đã được gửi qua kênh email cấu hình.'})
@require_POST
def password_reset(request):
    try:
        p=data(request);user=get_object_or_404(User,pk=p['user_id'])
        if not default_token_generator.check_token(user,str(p.get('token',''))):raise ValueError('Liên kết đã hết hạn hoặc đã dùng.')
        if p.get('password')!=p.get('password_confirm'):raise ValueError('Mật khẩu xác nhận chưa khớp.')
        validate_password(p['password'],user);user.set_password(p['password']);user.save();return JsonResponse({'ok':True})
    except (ValidationError,ValueError,KeyError) as e:return JsonResponse({'error':' '.join(e.messages) if isinstance(e,ValidationError) else str(e)},status=400)
