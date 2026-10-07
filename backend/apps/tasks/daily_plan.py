"""毎日の計画（結転）と業務報告（生成）の処理（P3）。権限の判定は ViewSet（BusinessAccessPolicy）が行う。"""
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.audit.services import record

from .models import DailyWorkReport, Task


class PlanError(Exception):
    def __init__(self, detail, field=None, code='invalid', status=400):
        super().__init__(detail)
        self.detail, self.field, self.code, self.status = detail, field, code, status


def next_weekday(day):
    """結転先の既定：次の営業日（土日・日本の祝日・振替休日・国民の休日を除く。P6）。画面で変更できる。"""
    from .business_days import next_business_day

    return next_business_day(day)


def _repr(task):
    return f'計画 {task.work_date} {task.title}'[:255]


def next_sort_order(employee_id, work_date):
    current = Task.objects.filter(responsible_employee_id=employee_id, work_date=work_date).aggregate(m=Max('sort_order'))
    return (current['m'] or 0) + 10


def same_version(task, version):
    """画面で見ていた版（updated_at の ISO 文字列）と一致するか。版を送らない場合は確認しない。"""
    if not version:
        return True
    from django.utils.dateparse import parse_datetime

    seen = parse_datetime(str(version))
    return seen is not None and abs((task.updated_at - seen).total_seconds()) < 0.001


def carry_over(task_id, *, target_date, version, actor, request, batch_id=''):
    """未完了の計画項目を target_date へ結転する。元の項目は元の日に「結転済み」で残る。"""
    with transaction.atomic():
        task = Task.objects.select_for_update().select_related('case').filter(pk=task_id).first()
        if task is None:
            raise PlanError('この項目は削除されています。', code='not_found', status=404)
        if not same_version(task, version):
            raise PlanError('他の操作で内容が変わっています。画面を更新してからもう一度操作してください。',
                            code='conflict', status=409)
        if task.work_date is None:
            raise PlanError('案件タスクは結転できません（毎日の計画の項目だけ）。', code='not_plan')
        if task.status not in Task.OPEN_STATUSES:
            raise PlanError(f'「{task.get_status_display()}」の項目は結転できません。', code='not_open')
        if target_date <= task.work_date:
            raise PlanError('結転先は元の作業日より後の日付にしてください。', field='target_date', code='invalid_date')
        created = Task.objects.create(
            case=task.case, title=task.title, description=task.description, priority=task.priority,
            responsible_employee_id=task.responsible_employee_id, work_date=target_date,
            sort_order=next_sort_order(task.responsible_employee_id, target_date),
            status=Task.STATUS_PENDING if task.status != Task.STATUS_IN_PROGRESS else Task.STATUS_IN_PROGRESS,
            carried_from=task, created_by=actor if getattr(actor, 'is_authenticated', False) else None,
        )
        previous_status = task.status
        task.status = Task.STATUS_CARRIED_OVER
        task.save(update_fields=['status', 'updated_at'])
        record(module='tasks', action='plan_item_carried_over', request=request, obj=task, object_repr=_repr(task),
               changes={'status': {'from': previous_status, 'to': Task.STATUS_CARRIED_OVER}},
               extra={'target_date': target_date.isoformat(), 'new_task_id': created.pk, 'batch_id': batch_id,
                      'case_id': task.case_id})
    return task, created


# --- 業務報告 ---------------------------------------------------------------------------

def _case_summary(case):
    if case is None:
        return None
    return {
        'id': case.id, 'case_number': case.case_number,
        'customer_name': getattr(case.customer, 'name', '') if case.customer_id else '',
        'status_display': case.get_status_display(),
        'next_action': case.next_action if case.next_action and not case.next_action_completed_at else '',
    }


def build_snapshot(employee, report_date):
    """生成時点の計画項目を固定して保存する（後から項目を変えても報告は変わらない）。"""
    tasks = list(
        Task.objects.filter(responsible_employee=employee, work_date=report_date)  # 本人の計画だけ
        .select_related('case__customer', 'carried_from').order_by('sort_order', 'id')
    )
    carried_targets = {t.carried_from_id: t for t in Task.objects.filter(carried_from__in=tasks)}
    items = []
    for task in tasks:
        target = carried_targets.get(task.id)
        items.append({
            'id': task.id, 'title': task.title, 'description': task.description, 'result_note': task.result_note,
            'status': task.status, 'status_display': task.get_status_display(),
            'priority': task.priority, 'priority_display': task.get_priority_display(),
            'carried_from_date': task.carried_from.work_date.isoformat() if task.carried_from_id else None,
            'carried_to_date': target.work_date.isoformat() if target is not None else None,
            'case': _case_summary(task.case),
        })
    completed = [i for i in items if i['status'] == Task.STATUS_COMPLETED]
    carried = [i for i in items if i['status'] == Task.STATUS_CARRIED_OVER]
    unfinished = [i for i in items if i['status'] in Task.OPEN_STATUSES]
    return {
        'report_date': report_date.isoformat(),
        'employee': {'id': employee.id, 'name': employee.name},
        'generated_at': timezone.now().isoformat(),
        'items': items,
        'summary': {'total': len(items), 'completed': len(completed), 'unfinished': len(unfinished),
                    'carried_over': len(carried)},
    }


def render_text(snapshot):
    """コピーして使う報告文（社内保存のみ。外部送信はしない）。"""
    items = snapshot['items']

    def label(item):
        case = item.get('case')
        prefix = f'［{case["case_number"]}］' if case and case.get('case_number') else ''
        return f'{prefix}{item["title"]}'

    lines = [f'業務報告 {snapshot["report_date"]}（{snapshot["employee"]["name"]}）', '']
    sections = (
        ('■ 完了', [i for i in items if i['status'] == Task.STATUS_COMPLETED],
         lambda i: f'・{label(i)}' + (f'\n　結果：{i["result_note"]}' if i['result_note'] else '')),
        ('■ 未完了・結転', [i for i in items if i['status'] in (*Task.OPEN_STATUSES, Task.STATUS_CARRIED_OVER)],
         lambda i: f'・{label(i)}' + (f'（→ {i["carried_to_date"]} に結転）' if i['carried_to_date']
                                     else f'（{i["status_display"]}）')),
        ('■ 取消', [i for i in items if i['status'] == Task.STATUS_CANCELLED], lambda i: f'・{label(i)}'),
        ('■ 備考', [i for i in items if i['description']], lambda i: f'・{i["title"]}：{i["description"]}'),
    )
    for heading, rows, fmt in sections:
        if not rows and heading in ('■ 取消', '■ 備考'):
            continue
        lines.append(heading)
        lines.extend(fmt(row) for row in rows) if rows else lines.append('・なし')
        lines.append('')
    cases = {}
    for item in items:
        if item.get('case'):
            cases.setdefault(item['case']['id'], item['case'])
    if cases:
        lines.append('■ 関連案件')
        for case in cases.values():
            tail = f'（次の対応：{case["next_action"]}）' if case['next_action'] else ''
            lines.append(f'・{case["case_number"]} {case["customer_name"]}：{case["status_display"]}{tail}')
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def generate_report(employee, report_date, *, actor, request, version=None, overwrite_edits=False):
    """下書きを生成（無ければ作成、下書きなら作り直す）。確定済みは作り直さない。"""
    if report_date > timezone.localdate():
        raise PlanError('未来の日付の報告は作成できません。', field='report_date')
    with transaction.atomic():
        report = (DailyWorkReport.objects.select_for_update()
                  .filter(employee=employee, report_date=report_date).first())
        created = report is None
        if report is not None:
            if report.status == DailyWorkReport.STATUS_CONFIRMED:
                raise PlanError('確定済みの報告は再生成できません。本文の編集はできます。', code='confirmed')
            if not same_version(report, version):
                raise PlanError('他の操作で報告が変わっています。画面を更新してからもう一度操作してください。',
                                code='conflict', status=409)
            if report.final_text != report.generated_text and not overwrite_edits:
                raise PlanError('編集した本文があります。再生成すると編集内容は失われます。', code='edited_exists',
                                status=409)
        else:
            report = DailyWorkReport(employee=employee, report_date=report_date)
        snapshot = build_snapshot(employee, report_date)
        text = render_text(snapshot)
        report.snapshot, report.generated_text, report.final_text = snapshot, text, text
        report.generated_at = timezone.now()
        report.generated_by = report.updated_by = actor
        report.save()
        record(module='tasks', action='daily_report_generated' if created else 'daily_report_regenerated',
               request=request, obj=report, object_repr=f'業務報告 {report_date} {employee.name}'[:255],
               extra={'report_date': report_date.isoformat(), **snapshot['summary']})
    return report, created


def parse_date(value, field='date'):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise PlanError('日付の形式が正しくありません（YYYY-MM-DD）。', field=field)
