"""AuditLog の唯一の書き込み口。"""
import uuid

from .models import AuditLog

# 変更差分に値を残してはいけない項目（「変更あり」だけを記録する）。
SENSITIVE_FIELDS = {
    'password',
    'my_number',
    'residence_card_no',
    'passport_no',
    'bank_account',
    'bank_account_number',
}


def new_request_id():
    return uuid.uuid4().hex


def get_request_id(request):
    if request is None:
        return ''
    raw = getattr(request, '_request', request)
    return getattr(raw, 'request_id', '') or ''


def client_ip(request):
    if request is None:
        return None
    meta = getattr(request, 'META', {}) or {}
    forwarded = meta.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip() or None
    return meta.get('REMOTE_ADDR') or None


def safe_changes(before, after):
    """変更前後の辞書から、機微項目の値を伏せた差分を作る。"""
    changes = {}
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old == new:
            continue
        if key in SENSITIVE_FIELDS:
            changes[key] = {'changed': True}
        else:
            changes[key] = {'from': _jsonable(old), 'to': _jsonable(new)}
    return changes


def _jsonable(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def record(
    *,
    module,
    action,
    request=None,
    user=None,
    obj=None,
    object_type='',
    object_id='',
    object_repr='',
    result=AuditLog.RESULT_SUCCESS,
    changes=None,
    reason='',
    via_permission='',
    extra=None,
):
    """監査ログを1件書く。request を渡すと利用者・IP・UA・request_id を補完する。"""
    if user is None and request is not None:
        candidate = getattr(request, 'user', None)
        if candidate is not None and getattr(candidate, 'is_authenticated', False):
            user = candidate
    employee = getattr(user, 'employee', None) if user is not None else None
    if obj is not None:
        object_type = object_type or obj._meta.label_lower
        object_id = object_id or str(obj.pk)
    meta = getattr(request, 'META', {}) if request is not None else {}
    return AuditLog.objects.create(
        user=user,
        username_snapshot=user.get_username() if user is not None else '',
        employee=employee,
        ip=client_ip(request),
        user_agent=(meta.get('HTTP_USER_AGENT') or '')[:300],
        request_id=get_request_id(request),
        module=module,
        action=action,
        object_type=object_type[:60],
        object_id=str(object_id)[:64],
        object_repr=(object_repr or '')[:200],
        result=result,
        changes=changes or {},
        reason=reason or '',
        via_permission=via_permission or '',
        extra=extra or {},
    )
