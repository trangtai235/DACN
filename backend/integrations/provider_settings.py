import hashlib
import json
import re
from types import SimpleNamespace
from django.conf import settings
from django.core import signing
from django.utils import timezone
import httpx
from .models import ProviderConnection
from .secrets import decrypt
from .secure_http import public_endpoint,public_client

MODEL_ID=re.compile(r'[A-Za-z0-9_.:/-]{1,180}\Z')


def builtin_providers(project):
    return ProviderConnection.objects.get_or_create(project=project,builtin_key='deepseek',defaults={
        'name':'DeepSeek','kind':'openai_compatible','base_url':'https://api.deepseek.com/v1',
        'model':'deepseek-chat','model_ids':['deepseek-chat','deepseek-reasoner'],'enabled':False})[0]


def signature(connection,key=None):
    payload=[connection.name,connection.kind,connection.base_url,connection.model,connection.model_ids or [connection.model],connection.enabled,
             decrypt(connection.encrypted_key) if key is None else key]
    return hashlib.sha256((settings.SECRET_KEY+json.dumps(payload,ensure_ascii=False)).encode()).hexdigest()


def probe(connection,key):
    """GET metadata only. Never fall back to a completion or other billable call."""
    checked=timezone.now().isoformat()
    def response(status,code,message,models=None):
        return {'status':status,'code':code,'message':message,'models':models or [],'checked_at':checked}
    if not connection.enabled:return response('unknown','disabled','Nhà cung cấp đang tắt. Bật trước khi kiểm tra.')
    if not key:return response('failed','missing_key','Chưa cấu hình API key.')
    if connection.kind!='openai_compatible':
        return response('unknown','unsupported','Kết nối cũ này chưa hỗ trợ kiểm tra metadata. Không gửi yêu cầu sinh nội dung.')
    try:
        url=public_endpoint(connection.base_url)+'/models'
        with public_client(timeout=20) as client:
            with client.stream('GET',url,headers={'Authorization':'Bearer '+key,'Accept':'application/json'}) as result:
                status=result.status_code
                if status in (401,403):return response('failed','invalid_key','API key không hợp lệ hoặc không có quyền truy cập.')
                if status==429:return response('failed','rate_limit','Nhà cung cấp giới hạn yêu cầu hoặc tài khoản hết hạn mức.')
                if status in (404,405,501):return response('unknown','unsupported','Nhà cung cấp không hỗ trợ GET /models tại URL này; chưa thể xác minh. Không gọi sinh nội dung.')
                if 300<=status<400:return response('failed','redirect_blocked','Base URL chuyển hướng. Dùng URL API trực tiếp; chuyển hướng đã bị chặn.')
                if status!=200:return response('failed','http_error',f'Nhà cung cấp trả HTTP {status}.')
                body=bytearray()
                for chunk in result.iter_bytes():
                    body.extend(chunk)
                    if len(body)>2*1024*1024:return response('failed','invalid_response','Danh sách model vượt giới hạn cho phép.')
        data=json.loads(body)
        rows=data.get('data') if isinstance(data,dict) else None
        if not isinstance(rows,list):return response('failed','invalid_response','API không trả danh sách model OpenAI-compatible hợp lệ.')
        models=list(dict.fromkeys(r['id'] for r in rows if isinstance(r,dict) and isinstance(r.get('id'),str)
                                 and MODEL_ID.fullmatch(r['id']) and key not in r['id']))
        if connection.model not in models:
            return response('failed','model_not_found','Mô hình mặc định không tồn tại hoặc key không có quyền dùng model này.',models[:100])
        visible=models[:100]
        if connection.model not in visible:visible=[connection.model,*visible[:99]]
        return response('success','ok','Kết nối thành công. API key và mô hình mặc định đã được xác minh qua GET /models.',visible)
    except httpx.TimeoutException:return response('failed','timeout','Hết thời gian chờ nhà cung cấp (20 giây).')
    except ValueError as exc:
        # Never echo provider bodies or request headers, which may contain keys.
        message=str(exc) if not isinstance(exc,json.JSONDecodeError) else 'API không trả JSON hợp lệ.'
        return response('failed','invalid_url' if not isinstance(exc,json.JSONDecodeError) else 'invalid_response',message)
    except httpx.RequestError:return response('failed','network_error','Không kết nối được API; kiểm tra URL, DNS và chứng chỉ TLS.')


def proof(connection,result,user_id):
    return signing.dumps({'digest':signature(connection),'project':connection.project_id,'user':user_id,
                          'result':{k:result[k] for k in ('status','code','message','checked_at')}},salt='provider-check')


def apply_proof(connection,token,user_id):
    try:
        payload=signing.loads(token,salt='provider-check',max_age=600)
        if payload['project']!=connection.project_id or payload['user']!=user_id or payload['digest']!=signature(connection):return
        result=payload['result']
        connection.check_status=result['status'];connection.check_code=result['code'];connection.check_message=result['message']
        from django.utils.dateparse import parse_datetime
        connection.checked_at=parse_datetime(result['checked_at'])
    except (signing.BadSignature,KeyError,ValueError,TypeError):return
