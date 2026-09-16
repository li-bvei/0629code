from django.utils import timezone

from .models import Timeline


def _resolve_actor(actor):
    """auth User インスタンス or None を返す。DRF の request.user（AnonymousUser）も吸収する。"""
    if actor is None:
        return None
    if getattr(actor, 'is_authenticated', False):
        return actor
    return None


def record_case_event(case, event_type, title, *, description='', actor=None,
                      metadata=None, occurred_at=None, is_visible_to_client=False):
    """案件のタイムラインに1件イベントを追加する共通サービス。

    人手の記録に依存せず、状態変更・資料受領・入金などの重要操作から呼び出す。
    metadata には最小限の識別情報のみ入れる（業務データ本体は複製しない）。
    """
    if case is None:
        return None
    return Timeline.objects.create(
        case=case,
        event_type=event_type or '',
        title=title,
        content=description or '',
        actor=_resolve_actor(actor),
        metadata=metadata or {},
        occurred_at=occurred_at or timezone.localdate(),
        is_visible_to_client=is_visible_to_client,
    )
