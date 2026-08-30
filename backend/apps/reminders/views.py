from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import DismissedDeadline, Reminder
from .serializers import DismissedDeadlineSerializer, ReminderSerializer


class ReminderViewSet(ModelViewSet):
    queryset = Reminder.objects.select_related('case')
    serializer_class = ReminderSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        case_id = self.request.query_params.get('case')
        if case_id:
            queryset = queryset.filter(case_id=case_id)
        return queryset


class DismissedDeadlineViewSet(ModelViewSet):
    """ダッシュボード「期限提醒」の個別「非表示」を管理する。更新は想定しないため
    list/create/retrieve/destroy のみ使う（update系はUIから呼ばない）。"""
    queryset = DismissedDeadline.objects.select_related('dismissed_by')
    serializer_class = DismissedDeadlineSerializer

    @action(detail=False, methods=['post'], url_path='bulk-dismiss-overdue')
    def bulk_dismiss_overdue(self, request):
        """今まさに「期限切れ」として表示されている項目をまとめて非表示にする
        （新しい案件がその人物／会社について作られれば自動的に再表示される）。"""
        from api.views import build_dashboard_deadlines

        today = timezone.localdate()
        items = build_dashboard_deadlines(today)
        overdue_items = [item for item in items if item['status'] == 'overdue']

        user = request.user if request.user.is_authenticated else None
        created = 0
        for item in overdue_items:
            _, was_created = DismissedDeadline.objects.get_or_create(
                source_type=item['target_type'],
                source_id=item['target_id'],
                deadline_type=item['type'],
                deadline_date=item['deadline_date'],
                defaults={'dismissed_by': user, 'note': '一括非表示（期限切れ分）'},
            )
            if was_created:
                created += 1

        return Response({'dismissed_count': created, 'checked_count': len(overdue_items)})
