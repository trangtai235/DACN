from .common import *

@ensure_csrf_cookie
def index(request):
    html=(settings.ROOT_DIR/'dist/index.html').read_text(encoding='utf-8').replace('data-mode="demo"','data-mode="api"')
    return HttpResponse(html)


@ensure_csrf_cookie
@require_GET
def session(request):
    user=request.user
    return JsonResponse({'user':{'id':user.id,'username':user.username,'name':user.first_name or user.username} if user.is_authenticated else None,'mode':'api','database':'PostgreSQL 15','api_configured':bool(settings.GEMINI_API_KEY),'youtube_configured':bool(settings.YOUTUBE_API_KEY)})


@require_POST
def sign_in(request):
    try:p=data(request)
    except ValueError as e:return JsonResponse({'error':str(e)},status=400)
    user=authenticate(request,username=p.get('username',''),password=p.get('password',''))
    if not user:return JsonResponse({'error':'Tên đăng nhập hoặc mật khẩu chưa đúng.'},status=401)
    login(request,user)
    request.session.set_expiry(14*24*60*60 if p.get('remember') in (True,'on','true','1') else 0)
    return JsonResponse({'ok':True})


@require_POST
def sign_up(request):
    try:
        p=data(request)
        form=RegistrationForm({'username':str(p.get('username','')).strip(),'first_name':str(p.get('first_name','')).strip(),
                               'email':str(p.get('email','')).strip(),'password1':p.get('password',''),'password2':p.get('password_confirm','')})
        if not form.is_valid():
            errors={k:[str(message) for message in messages] for k,messages in form.errors.items()}
            return JsonResponse({'error':' '.join(message for messages in errors.values() for message in messages),'fields':errors},status=400)
        with transaction.atomic():
            user=form.save()
        if settings.REQUIRE_EMAIL_VERIFICATION:
            user.is_active=False;user.save()
            from studio.api.accounts import verification_mail
            link=verification_mail(user)
            return JsonResponse({'ok':True,'verification_required':True,**({'preview_url':link} if settings.DEBUG else {})},status=201)
        login(request,user)
        request.session.set_expiry(0)
        return JsonResponse({'ok':True},status=201)
    except IntegrityError:
        return JsonResponse({'error':'Tên đăng nhập đã được sử dụng.'},status=400)
    except (ValueError,TypeError) as e:
        return JsonResponse({'error':str(e)},status=400)


@require_POST
def sign_out(request):logout(request);return JsonResponse({'ok':True})

