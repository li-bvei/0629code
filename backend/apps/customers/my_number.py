"""マイナンバーの表示（P6）。

- 表示できるのは、customers.reveal_my_number を明示的に付与された人が、その顧客・家族を見られる場合だけ。
  顧客は詳細を見られる範囲（FULL・MASKED）に限る。案件の無い顧客の基本情報（BASIC）しか見られない場合は 403。
  家族は親の顧客の詳細を見られる場合（家族の行の取得規則と同じ）に限る。
  会社職員は親の会社の詳細を見られる場合（職員の行の取得規則と同じ）に限る。既存顧客に関連付いた職員は
  その顧客の値を返すが、その顧客自体が見えない（MINIMAL）場合は 403（職員関係で顧客の範囲を広げない）。
  関連付いていない旧形式の職員は CompanyStaff 自身の値。
  is_superuser は判定に使わない。この権限で顧客・家族・案件・会社の見える範囲は広がらない。
- 見られない対象は 404（存在を推測させない）、見られるが表示権限が無い場合は 403。
- 成功・拒否とも監査ログに残す。監査・例外・ログには平文を一切書かない。
- 平文は専用の応答でだけ返す。通常の serializer（一覧・詳細・検索・出力）は has_my_number だけ。
"""
from apps.audit.services import record

REVEAL_PERMISSION = 'customers.reveal_my_number'


class MyNumberUnavailable(Exception):
    """復号できない等（理由に平文・暗号文を含めない）。"""


def _plain(value):
    if value in (None, ''):
        return ''
    return str(value)


def customer_value(customer):
    try:
        return _plain(customer.my_number)
    except Exception:  # noqa: BLE001 復号の失敗は詳細を出さずに扱う
        raise MyNumberUnavailable() from None


def family_member_value(member):
    """家族の行に既存顧客が関連付いていれば、その顧客の値（family_customer が正）。"""
    try:
        if member.family_customer_id:
            return _plain(member.family_customer.my_number)
        return _plain(member.my_number)
    except Exception:  # noqa: BLE001
        raise MyNumberUnavailable() from None


def company_staff_value(staff):
    """会社職員：既存顧客に関連付いていればその顧客の値、旧形式（未関連）は職員自身の値。"""
    try:
        if staff.customer_id:
            return _plain(staff.customer.my_number)
        return _plain(staff.my_number)
    except Exception:  # noqa: BLE001
        raise MyNumberUnavailable() from None


VALUE_READERS = {
    'customer': customer_value,
    'family_member': family_member_value,
    'company_staff': company_staff_value,
}
OBJECT_LABELS = {
    'customer': 'customers.customer',
    'family_member': 'customers.familymember',
    'company_staff': 'companies.companystaff',
}


def audit_reveal(request, obj, result, reason='', extra=None):
    record(
        module='customers', action='my_number_reveal' if result == 'success' else 'my_number_reveal_denied',
        request=request, obj=obj, result=result, reason=reason, via_permission=REVEAL_PERMISSION,
        extra={'target': obj._meta.model_name, **(extra or {})} if obj is not None else extra,
    )


def reveal_response(view, request, pk, kind):
    """顧客（customer）・家族（family_member）・会社職員（company_staff）のマイナンバーを返す共通処理。"""
    from django.http import Http404
    from rest_framework import status
    from rest_framework.response import Response

    from apps.authentication.access_rules import CUSTOMER_RULE, DETAIL_LEVELS, VISIBLE_LEVELS

    label = OBJECT_LABELS[kind]
    try:
        obj = view.get_object()  # 見られない対象は 404（規則が判定する）
    except Http404:
        record(module='customers', action='my_number_reveal_denied', request=request, result='denied',
               object_type=label, object_id=str(pk)[:64], reason='not_visible', via_permission=REVEAL_PERMISSION)
        raise
    policy = view.business_policy
    if not policy.has(REVEAL_PERMISSION):
        audit_reveal(request, obj, 'denied', reason='missing_permission')
        return Response({'code': 'my_number_permission_required',
                         'detail': 'マイナンバーを表示する権限がありません。'}, status=status.HTTP_403_FORBIDDEN)
    if kind == 'customer' and CUSTOMER_RULE.level(policy, obj) not in DETAIL_LEVELS:
        # 基本情報だけ見られる顧客（案件が無い等）：表示権限で機微情報の範囲を広げない
        audit_reveal(request, obj, 'denied', reason='detail_scope_required')
        return Response({'code': 'my_number_scope_required',
                         'detail': 'この顧客の詳細を見る範囲外のため、マイナンバーは表示できません。'},
                        status=status.HTTP_403_FORBIDDEN)
    if kind == 'family_member' and obj.family_customer_id:
        # 関連付いた人物そのものを見られない場合は表示しない（表示権限で範囲を広げない）
        if CUSTOMER_RULE.level(policy, obj.family_customer) not in VISIBLE_LEVELS:
            audit_reveal(request, obj, 'denied', reason='linked_person_not_visible')
            return Response({'code': 'my_number_permission_required',
                             'detail': '関連付いている人物のマイナンバーを表示する権限がありません。'},
                            status=status.HTTP_403_FORBIDDEN)
    if kind == 'company_staff' and obj.customer_id:
        # 関連付いた顧客そのものが見えない場合は表示しない（職員関係で顧客の範囲を広げない）
        if CUSTOMER_RULE.level(policy, obj.customer) not in VISIBLE_LEVELS:
            audit_reveal(request, obj, 'denied', reason='linked_person_not_visible')
            return Response({'code': 'my_number_scope_required',
                             'detail': '関連付いている人物を見る範囲外のため、マイナンバーは表示できません。'},
                            status=status.HTTP_403_FORBIDDEN)
    try:
        value = VALUE_READERS[kind](obj)
    except MyNumberUnavailable:
        audit_reveal(request, obj, 'error', reason='unavailable')
        return Response({'code': 'my_number_unavailable', 'detail': 'マイナンバーを読み出せませんでした。管理者に連絡してください。'},
                        status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    extra = {'registered': bool(value)}
    if kind == 'company_staff':
        extra['linked_customer'] = bool(obj.customer_id)
    audit_reveal(request, obj, 'success', extra=extra)
    response = Response({'registered': bool(value), 'my_number': value})
    # 画面の一時表示専用：保存・キャッシュさせない
    response['Cache-Control'] = 'no-store, private'
    response['Pragma'] = 'no-cache'
    return response
