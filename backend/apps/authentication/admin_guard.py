"""Django Admin の入場制御（段階A/B）。

段階A（PROTECTED_ADMIN_ENFORCEMENT=False）：従来どおり is_active かつ is_staff。
段階B（True）：さらに ProtectedAccount であること。保護アカウントが空でも
「superuser 全員を許可」に戻すことはせず、全員を拒否する（復旧はサーバーの
protect_account コマンドで行う）。
"""
import logging

from django.conf import settings

from .access_policy import is_protected_account

logger = logging.getLogger(__name__)


def protected_admin_has_permission(request):
    user = request.user
    base = bool(user and user.is_active and user.is_staff)
    if not base:
        return False
    if not settings.PROTECTED_ADMIN_ENFORCEMENT:
        return True
    if is_protected_account(user):
        return True
    from .models import ProtectedAccount

    if not ProtectedAccount.objects.exists():
        logger.error('PROTECTED_ADMIN_ENFORCEMENT 有効だが保護アカウントが未登録。protect_account で復旧してください。')
    return False
