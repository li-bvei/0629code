"""今日の作業台：自分の案件・自分の次の対応・自分の待機案件（管理者は全体表示）。

範囲は BusinessAccessPolicy（案件の閲覧範囲）と Employee–User 関連で決める。
"""
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.drf import BusinessAccessMixin
from apps.cases.models import Case

CLOSED = [Case.STATUS_COMPLETED, Case.STATUS_WITHDRAWN, Case.STATUS_REJECTED]
LIMIT = 200


def _row(case, today):
    due = case.next_action_due_at
    return {
        'id': case.id,
        'case_number': case.case_number,
        'case_type': case.case_type,
        'customer_name': getattr(case.customer, 'name', '') or '',
        'status': case.status,
        'status_display': case.get_status_display(),
        'responsible_employee_id': case.responsible_employee_id,
        'responsible_employee_name': case.responsible_employee.name if case.responsible_employee_id else '',
        'next_action': case.next_action,
        'next_action_due_at': due.isoformat() if due else None,
        'next_action_assignee_id': case.next_action_assignee_id,
        'next_action_assignee_name': case.next_action_assignee.name if case.next_action_assignee_id else '',
        'next_action_blocked_reason': case.next_action_blocked_reason,
        'next_action_state': 'none' if not case.next_action else ('done' if case.next_action_completed_at else 'open'),
        'due_status': (
            None if not due else 'overdue' if due < today else 'today' if due == today else 'upcoming'
        ),
        'work_status': case.work_status,
        'waiting_reason': case.waiting_reason,
        'waiting_reason_display': case.get_waiting_reason_display(),
        'waiting_since': case.waiting_since.isoformat() if case.waiting_since else None,
        'waiting_until': case.waiting_until.isoformat() if case.waiting_until else None,
        'waiting_days': (today - case.waiting_since).days if case.waiting_since else None,
        'updated_at': case.updated_at.isoformat(),
    }


class TodayWorkbenchView(BusinessAccessMixin, APIView):
    access_resource = 'case'

    def get(self, request):
        policy = self.business_policy
        scope = request.query_params.get('scope', 'mine')
        today = timezone.localdate()
        base = (
            policy.queryset('case', 'list')
            .filter(registration_status=Case.REGISTRATION_STATUS_ACTIVE)
            .exclude(status__in=CLOSED)
            .select_related('customer', 'responsible_employee', 'next_action_assignee')
        )
        if scope == 'all':
            if not self.access_rule.can_view_all(policy):
                raise PermissionDenied('全体表示の権限がありません。')
            cases = base
            actions = base.filter(next_action__gt='', next_action_completed_at__isnull=True)
        else:
            scope = 'mine'
            employee_id = policy.employee_id
            if employee_id is None:
                return Response({
                    'scope': scope, 'employee_linked': False, 'cases': [], 'next_actions': [], 'waiting': [],
                    'summary': {'cases': 0, 'next_actions': 0, 'overdue': 0, 'today': 0, 'waiting': 0,
                                'waiting_overdue': 0},
                })
            cases = base.filter(responsible_employee_id=employee_id)
            actions = base.filter(next_action__gt='', next_action_completed_at__isnull=True).filter(
                Q(next_action_assignee_id=employee_id)
                | Q(next_action_assignee__isnull=True, responsible_employee_id=employee_id)
            )
        waiting = cases.filter(work_status=Case.WORK_STATUS_WAITING)
        actions = actions.order_by('next_action_due_at', 'id')
        action_rows = [_row(c, today) for c in actions[:LIMIT]]
        # 期限なしは最後に
        action_rows.sort(key=lambda r: (r['next_action_due_at'] is None, r['next_action_due_at'] or '', r['id']))
        return Response({
            'scope': scope,
            'employee_linked': policy.employee_id is not None,
            'cases': [_row(c, today) for c in cases.order_by('-updated_at', '-id')[:LIMIT]],
            'next_actions': action_rows,
            'waiting': [_row(c, today) for c in waiting.order_by('waiting_until', 'waiting_since', 'id')[:LIMIT]],
            'summary': {
                'cases': cases.count(),
                'next_actions': actions.count(),
                'overdue': actions.filter(next_action_due_at__lt=today).count(),
                'today': actions.filter(next_action_due_at=today).count(),
                'waiting': waiting.count(),
                'waiting_overdue': waiting.filter(waiting_until__lt=today).count(),
            },
        })
