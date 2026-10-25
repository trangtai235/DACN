from copy import copy
from .common import *
from integrations.models import ProviderConnection
from integrations.secrets import encrypt, decrypt
from integrations.registry import snapshot
from integrations.providers.base import validate_endpoint
from integrations.secure_http import public_endpoint
from integrations.provider_settings import builtin_providers, MODEL_ID, probe, signature, proof, apply_proof
from experiments.models import ModelRun
from experiments.algorithms.registry import ALGORITHMS


def connection_json(c):
    return {**snapshot(c), 'enabled': c.enabled, 'key_configured': bool(c.encrypted_key),
            'model_ids': c.model_ids or [c.model], 'is_builtin': bool(c.builtin_key),
            'check_status': c.check_status if c.enabled else 'unknown',
            'check_code': c.check_code, 'check_message': c.check_message,
            'checked_at': c.checked_at.isoformat() if c.checked_at else None}


def editable(request, p):
    project = project_for(request, p['project'], True)
    existing = get_object_or_404(ProviderConnection, project=project, pk=p['id']) if p.get('id') else None
    c = copy(existing) if existing else ProviderConnection(project=project)
    c.name = str(p.get('name', c.name)).strip()
    c.kind = p.get('kind', c.kind or 'openai_compatible')
    if c.kind not in ('openai_compatible', 'gemini', 'ollama'):
        raise ValueError('Loại API không được hỗ trợ.')
    if existing is None and c.kind != 'openai_compatible':
        raise ValueError('Nhà cung cấp mới cần dùng OpenAI-compatible.')
    c.base_url = str(p.get('base_url', c.base_url)).strip()
    if c.kind == 'ollama':
        if existing.kind!='ollama' or c.base_url!=existing.base_url:
            raise ValueError('Không thay Base URL nội bộ của kết nối Ollama cũ.')
        c.base_url = validate_endpoint(c.base_url)
    else:
        c.base_url = public_endpoint(c.base_url)
    if not c.name or len(c.name) > 120:
        raise ValueError('Tên hiển thị bắt buộc, tối đa 120 ký tự.')
    ids = p.get('model_ids', c.model_ids or [p.get('model', c.model)])
    if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or any(not isinstance(m, str) or not MODEL_ID.fullmatch(m) for m in ids):
        raise ValueError('Cần danh sách 1–100 Model ID hợp lệ, mỗi ID tối đa 180 ký tự.')
    c.model_ids = list(dict.fromkeys(ids))
    c.model = str(p.get('model', c.model or c.model_ids[0])).strip()
    if c.model not in c.model_ids:
        raise ValueError('Mô hình mặc định phải nằm trong danh sách Model ID.')
    enabled = p.get('enabled', c.enabled)
    if type(enabled) is not bool:
        raise ValueError('Trạng thái bật/tắt phải là boolean.')
    c.enabled = enabled
    if p.get('clear_key'):
        c.encrypted_key = ''
    elif p.get('api_key'):
        key = str(p['api_key']).strip()
        if len(key) > 4096 or any(ord(x)<33 or ord(x)>126 for x in key):
            raise ValueError('API key không hợp lệ.')
        c.encrypted_key = encrypt(key)
    if c.enabled and c.kind != 'ollama' and not c.encrypted_key:
        raise ValueError('Cần nhập API key trước khi bật nhà cung cấp.')
    for key in ('input_price', 'output_price'):
        value = float(p.get(key, getattr(c, key)))
        if not 0 <= value <= 10000:
            raise ValueError('Giá cấu hình cần từ 0 đến 10.000 USD / triệu token.')
        setattr(c, key, value)
    if existing and existing.builtin_key and (c.kind != existing.kind or c.base_url != existing.base_url):
        raise ValueError('Không thay đổi giao thức hoặc Base URL của nhà cung cấp tích hợp sẵn. Hãy thêm nhà cung cấp tùy chỉnh.')
    return project, c, existing


def busy(project):
    if Job.objects.filter(project=project, status__in=['queued', 'running']).exists():
        raise ValueError('Dừng hoặc chờ tác vụ dự án hoàn tất trước khi thay đổi nhà cung cấp.')


@api
@require_GET
def connections(request):
    project = project_for(request, request.GET['project'], True)
    builtin_providers(project)
    prefs = ensure(project)
    return JsonResponse({'connections': [connection_json(c) for c in project.connections.order_by('-builtin_key', 'id')],
                         'active_connection_id': prefs.active_connection_id,
                         'algorithms': [{'id': k, 'name': v['name'], 'parameter': v['parameter'], 'values': v['values']} for k, v in ALGORITHMS.items()],
                         'allowed_hosts': settings.AI_ALLOWED_HOSTS})


@api
@require_POST
def connection_save(request):
    p = data(request)
    with transaction.atomic():
        project, c, old = editable(request, p)
        ensure(project)
        ProjectSettings.objects.select_for_update().get(project=project)
        busy(project)
        changed = old is None or signature(old) != signature(c)
        if changed:
            c.check_status = 'unknown'; c.check_code = ''; c.check_message = ''; c.checked_at = None
        if p.get('test_token'):
            apply_proof(c, p['test_token'], request.user.pk)
        if not c.enabled:
            c.check_status = 'unknown'
        c.save()
        prefs = ensure(project)
        if p.get('make_default') is True:
            if not c.enabled or (c.kind != 'ollama' and not c.encrypted_key):
                raise ValueError('Chỉ chọn mặc định một nhà cung cấp đang bật và đã có key.')
            prefs.active_connection = c; prefs.save(update_fields=['active_connection'])
        elif (not c.enabled or p.get('make_default') is False) and prefs.active_connection_id == c.pk:
            prefs.active_connection = None; prefs.save(update_fields=['active_connection'])
        audit(project, request.user, 'provider_saved', connection=c.pk, kind=c.kind)
    return JsonResponse({'connection': connection_json(c)})


@api
@require_POST
def connection_test(request):
    p = data(request)
    # A payload containing only an ID tests saved credentials; a form payload
    # tests a draft without persisting a new key or other settings.
    project, c, old = editable(request, p)
    result = probe(c, decrypt(c.encrypted_key))
    token = proof(c, result, request.user.pk)
    if old and signature(old) == signature(c):
        from django.utils.dateparse import parse_datetime
        ProviderConnection.objects.filter(pk=old.pk, updated_at=old.updated_at).update(
            check_status=result['status'], check_code=result['code'], check_message=result['message'],
            checked_at=parse_datetime(result['checked_at']))
    return JsonResponse({'check': result, 'test_token': token})


@api
@require_POST
def connection_delete(request):
    p = data(request)
    project = project_for(request, p['project'], True)
    with transaction.atomic():
        ensure(project)
        ProjectSettings.objects.select_for_update().get(project=project)
        c = get_object_or_404(ProviderConnection, project=project, pk=p.get('id'))
        if c.builtin_key:
            raise PermissionError('Không thể xóa nhà cung cấp tích hợp sẵn. Bạn có thể tắt nhà cung cấp.')
        if p.get('confirm') != c.name:
            raise ValueError('Nhập đúng tên nhà cung cấp để xác nhận xóa.')
        busy(project)
        cid = c.pk
        c.delete()
        audit(project, request.user, 'provider_deleted', connection=cid)
    return JsonResponse({'ok': True})


@api
@require_GET
def configuration(request):
    project = project_for(request, request.GET['project'], True)
    builtin_providers(project)
    prefs = ensure(project)
    # Explicit export allowlist: no encrypted credentials, keys, user data or env.
    value = {'version': 1, 'project': {'id': project.pk, 'name': project.name},
             'default_provider_id': prefs.active_connection_id,
             'default_local_model_id': prefs.active_model_id,
             'providers': [{k: row[k] for k in ('id', 'name', 'kind', 'base_url', 'model', 'model_ids', 'enabled', 'is_builtin', 'key_configured')}
                           for row in [connection_json(c) for c in project.connections.order_by('id')]]}
    response = JsonResponse(value, json_dumps_params={'ensure_ascii': False, 'indent': 2})
    if request.GET.get('download') == '1':
        response['Content-Disposition'] = 'attachment; filename="annotaflow-providers.json"'
    return response


@api
@require_POST
def select_model(request):
    p = data(request); project = project_for(request, p['project'], True); prefs = ensure(project)
    if 'model_id' in p:
        prefs.active_model = get_object_or_404(ModelRun, project=project, state='ready', pk=p['model_id'])
    if 'connection_id' in p:
        c = get_object_or_404(ProviderConnection, project=project, enabled=True, pk=p['connection_id']) if p['connection_id'] else None
        if c and c.kind != 'ollama' and not c.encrypted_key:
            raise ValueError('Nhà cung cấp chưa có API key.')
        prefs.active_connection = c
    prefs.save()
    return JsonResponse({'preferences': pref_json(prefs)})
