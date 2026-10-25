import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
BASE_DIR=Path(__file__).resolve().parent.parent
ROOT_DIR=BASE_DIR.parent
load_dotenv(Path(os.getenv('ANNOTAFLOW_ENV_FILE',str(ROOT_DIR/'.env'))))
SECRET_KEY=os.getenv('DJANGO_SECRET_KEY','')
if not SECRET_KEY:raise ImproperlyConfigured('Đặt DJANGO_SECRET_KEY trong .env hoặc môi trường.')
DEBUG=os.getenv('DEBUG','0')=='1'
ALLOWED_HOSTS=os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1').split(',')
CSRF_TRUSTED_ORIGINS=[s for s in os.getenv('CSRF_TRUSTED_ORIGINS','').split(',') if s]
INSTALLED_APPS=['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','core','reviewing','experiments','integrations','studio']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF='config.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='config.wsgi.application'
DATABASES={'default':{'ENGINE':'django.db.backends.postgresql','NAME':os.getenv('DB_NAME','annotaflow'),'USER':os.getenv('DB_USER','annotaflow_app'),'PASSWORD':os.getenv('DB_PASSWORD',''),'HOST':os.getenv('DB_HOST','localhost'),'PORT':os.getenv('DB_PORT','5432'),
 'CONN_MAX_AGE':0,'OPTIONS':{'connect_timeout':10,'sslmode':os.getenv('DB_SSLMODE','prefer')}}}
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}]
LANGUAGE_CODE='vi';TIME_ZONE='Asia/Ho_Chi_Minh';USE_I18N=True;USE_TZ=True
STATIC_URL='/assets/';STATICFILES_DIRS=[ROOT_DIR/'dist'/'assets'];STATIC_ROOT=BASE_DIR/'staticfiles'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
SESSION_COOKIE_HTTPONLY=True;SESSION_COOKIE_SAMESITE='Lax';CSRF_COOKIE_SAMESITE='Lax'
SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','0')=='1';CSRF_COOKIE_SECURE=SESSION_COOKIE_SECURE
SECURE_CONTENT_TYPE_NOSNIFF=True;X_FRAME_OPTIONS='DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE=20*1024*1024;FILE_UPLOAD_MAX_MEMORY_SIZE=5*1024*1024
PRIVATE_DATA=BASE_DIR/'private_data';PRIVATE_DATA.mkdir(exist_ok=True)
GEMINI_API_KEY=os.getenv('GEMINI_API_KEY','');GEMINI_MODEL=os.getenv('GEMINI_MODEL','')
GEMINI_INPUT_PRICE=float(os.getenv('GEMINI_INPUT_PRICE','0'));GEMINI_OUTPUT_PRICE=float(os.getenv('GEMINI_OUTPUT_PRICE','0'))
YOUTUBE_API_KEY=os.getenv('YOUTUBE_API_KEY','')
CELERY_BROKER_URL=os.getenv('REDIS_URL','redis://localhost:6379/0')
CELERY_TASK_ALWAYS_EAGER=os.getenv('TASK_ALWAYS_EAGER','0')=='1'
CELERY_TASK_EAGER_PROPAGATES=True;CELERY_TASK_TIME_LIMIT=3600;CELERY_TASK_SOFT_TIME_LIMIT=3500

# Runtime profiles: native local mode uses threads and needs no Redis/WSL/Docker.
JOB_RUNNER=os.getenv('JOB_RUNNER','celery')
AI_ALLOWED_HOSTS=[v.strip().lower() for v in os.getenv('AI_ALLOWED_HOSTS','localhost,127.0.0.1,host.docker.internal,api.openai.com,generativelanguage.googleapis.com').split(',') if v.strip()]
EMAIL_BACKEND=os.getenv('EMAIL_BACKEND','django.core.mail.backends.filebased.EmailBackend')
EMAIL_FILE_PATH=PRIVATE_DATA/'emails'
EMAIL_HOST=os.getenv('EMAIL_HOST','');EMAIL_PORT=int(os.getenv('EMAIL_PORT','587'))
EMAIL_HOST_USER=os.getenv('EMAIL_HOST_USER','');EMAIL_HOST_PASSWORD=os.getenv('EMAIL_HOST_PASSWORD','')
EMAIL_USE_TLS=os.getenv('EMAIL_USE_TLS','1')=='1'
DEFAULT_FROM_EMAIL=os.getenv('DEFAULT_FROM_EMAIL','AnnotaFlow <noreply@localhost>')
SITE_URL=os.getenv('SITE_URL','http://127.0.0.1:8000').rstrip('/')
REQUIRE_EMAIL_VERIFICATION=os.getenv('REQUIRE_EMAIL_VERIFICATION','0')=='1'
