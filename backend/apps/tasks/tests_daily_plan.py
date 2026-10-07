"""P3：毎日の計画（Task 拡張）と業務報告。権限・版の確認・結転・並べ替え・報告のスナップショット・監査・旧データ互換。"""
from datetime import date, timedelta

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.authentication.tests.test_case_party_access import AccessFixtureMixin
from apps.cases.models import Case
from apps.tasks.daily_plan import next_weekday
from apps.tasks.models import DailyWorkReport, Task

TASKS = '/api/tasks/'
REPORTS = '/api/daily-reports/'


class PlanFixture(AccessFixtureMixin):
    def setUp(self):
        super().setUp()
        self.day = timezone.localdate()

    def post(self, user, url, body):
        self.as_user(user)
        return self.client.post(url, body, content_type='application/json')

    def patch(self, user, url, body):
        self.as_user(user)
        return self.client.patch(url, body, content_type='application/json')

    def get(self, user, url, params=None):
        self.as_user(user)
        return self.client.get(url, params or {})

    def add(self, user, title, **extra):
        response = self.post(user, TASKS, {'title': title, 'work_date': str(self.day), **extra})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()


class DailyPlanTests(PlanFixture, TestCase):
    def test_create_internal_and_case_items_owner_is_forced_and_order_appends(self):
        internal = self.add(self.staff_a, '社内：申請書類の整理', priority='high', responsible_employee=self.emp_b.id)
        linked = self.add(self.staff_a, '入管へ提出', case=self.case_a.id, description='午後')
        self.assertEqual(internal['responsible_employee'], self.emp_a.id)  # 画面から指定しても本人
        self.assertIsNone(internal['case'])
        self.assertEqual((internal['priority'], internal['status']), ('high', 'pending'))
        self.assertGreater(linked['sort_order'], internal['sort_order'])
        self.assertEqual(linked['case_number'], self.case_a.case_number)
        self.assertEqual(AuditLog.objects.filter(action='plan_item_created', user=self.staff_a).count(), 2)

    def test_case_link_requires_case_change_permission_and_unlinked_account_is_refused(self):
        response = self.post(self.staff_a, TASKS, {'title': 'x', 'work_date': str(self.day), 'case': self.case_b.id})
        self.assertEqual(response.status_code, 403)  # 他担当の案件
        Case.objects.filter(pk=self.case_a.pk).update(registration_status=Case.REGISTRATION_STATUS_ARCHIVED)
        response = self.post(self.staff_a, TASKS, {'title': 'x', 'work_date': str(self.day), 'case': self.case_a.id})
        self.assertEqual(response.status_code, 403)  # アーカイブ済み案件
        response = self.post(self.unlinked, TASKS, {'title': 'x', 'work_date': str(self.day)})
        self.assertEqual(response.status_code, 403)
        self.assertIn('担当者に関連付いていない', response.json()['detail'])
        self.assertFalse(Task.objects.filter(work_date__isnull=False).exists())

    def test_visibility_own_edit_view_all_read_only_others_not_found(self):
        item = self.add(self.staff_a, '自分の作業')
        url = f'{TASKS}{item["id"]}/'
        # 他の担当者：一覧に出ず、詳細は 404
        self.assertNotIn(item['id'], [r['id'] for r in self.rows(self.get(self.staff_b, TASKS, {'plan': '1'}))])
        self.assertEqual(self.get(self.staff_b, url).status_code, 404)
        self.assertEqual(self.patch(self.staff_b, url, {'title': 'x'}).status_code, 404)
        # 全件閲覧（焦）：見られるが変更は 403
        self.assertIn(item['id'], [r['id'] for r in self.rows(self.get(self.jiao, TASKS, {'plan': '1', 'employee': self.emp_a.id}))])
        self.assertEqual(self.get(self.jiao, url).status_code, 200)
        self.assertEqual(self.patch(self.jiao, url, {'title': 'x'}).status_code, 403)
        # 全件変更権限（李）でも他人の計画は変更できない（is_superuser でも通らない）
        self.assertEqual(self.patch(self.li, url, {'title': 'x'}).status_code, 403)
        self.assertEqual(Task.objects.get(pk=item['id']).title, '自分の作業')
        # 本人は変更できる
        self.assertEqual(self.patch(self.staff_a, url, {'title': '変更'}).status_code, 200)

    def test_complete_with_result_note_and_stale_version_is_rejected(self):
        item = self.add(self.staff_a, '書類作成')
        url = f'{TASKS}{item["id"]}/'
        done = self.patch(self.staff_a, url, {'status': 'completed', 'result_note': '提出済み', 'version': item['updated_at']})
        self.assertEqual(done.status_code, 200, done.content)
        self.assertEqual((done.json()['status'], done.json()['completed_at']), ('completed', str(self.day)))
        stale = self.patch(self.staff_a, url, {'result_note': '古い画面から', 'version': item['updated_at']})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(Task.objects.get(pk=item['id']).result_note, '提出済み')
        log = AuditLog.objects.filter(action='plan_item_updated').latest('id')
        self.assertEqual(log.changes['status'], {'from': 'pending', 'to': 'completed'})
        self.assertIn('書類作成', log.object_repr)
        # 結転済みは画面から直接設定できない
        self.assertEqual(self.patch(self.staff_a, url, {'status': 'carried_over'}).status_code, 400)

    def test_invalid_input(self):
        self.assertEqual(self.post(self.staff_a, TASKS, {'title': '  ', 'work_date': str(self.day)}).status_code, 400)
        self.assertEqual(self.post(self.staff_a, TASKS, {'title': 'x', 'work_date': 'not-a-date'}).status_code, 400)
        self.assertEqual(self.post(self.staff_a, TASKS, {'title': 'x', 'work_date': str(self.day), 'priority': 'urgent'}).status_code, 400)
        item = self.add(self.staff_a, 'x')
        url = f'{TASKS}{item["id"]}/'
        self.assertEqual(self.patch(self.staff_a, url, {'work_date': None}).status_code, 400)
        self.assertEqual(self.patch(self.staff_a, url, {'responsible_employee': self.emp_b.id}).status_code, 400)


class CarryOverTests(PlanFixture, TestCase):
    def test_carry_over_keeps_original_trace(self):
        item = self.add(self.staff_a, '未完了の作業', case=self.case_a.id, priority='high')
        target = next_weekday(self.day)
        response = self.post(self.staff_a, f'{TASKS}{item["id"]}/carry-over/', {'target_date': str(target), 'version': item['updated_at']})
        self.assertEqual(response.status_code, 201, response.content)
        original, created = response.json()['original'], response.json()['created']
        self.assertEqual((original['status'], original['work_date']), ('carried_over', str(self.day)))
        self.assertEqual(original['carried_to'], {'id': created['id'], 'work_date': str(target)})
        self.assertEqual((created['work_date'], created['carried_from_date'], created['status']), (str(target), str(self.day), 'pending'))
        self.assertEqual((created['case'], created['priority'], created['title']), (self.case_a.id, 'high', '未完了の作業'))
        self.assertTrue(AuditLog.objects.filter(action='plan_item_carried_over', object_id=str(item['id'])).exists())
        # 同じ項目を再び結転できない／元の日以前は不可／完了済みは不可／古い版は 409
        again = self.post(self.staff_a, f'{TASKS}{item["id"]}/carry-over/', {'target_date': str(target)})
        self.assertEqual((again.status_code, again.json()['code']), (400, 'not_open'))
        other = self.add(self.staff_a, '別')
        self.assertEqual(self.post(self.staff_a, f'{TASKS}{other["id"]}/carry-over/', {'target_date': str(self.day)}).status_code, 400)
        self.patch(self.staff_a, f'{TASKS}{other["id"]}/', {'status': 'completed'})
        self.assertEqual(self.post(self.staff_a, f'{TASKS}{other["id"]}/carry-over/', {'target_date': str(target)}).json()['code'], 'not_open')
        third = self.add(self.staff_a, '三つ目')
        self.patch(self.staff_a, f'{TASKS}{third["id"]}/', {'description': '更新'})
        stale = self.post(self.staff_a, f'{TASKS}{third["id"]}/carry-over/', {'target_date': str(target), 'version': third['updated_at']})
        self.assertEqual(stale.status_code, 409)
        # 他人の項目
        self.assertEqual(self.post(self.staff_b, f'{TASKS}{third["id"]}/carry-over/', {'target_date': str(target)}).status_code, 404)
        self.assertEqual(self.post(self.jiao, f'{TASKS}{third["id"]}/carry-over/', {'target_date': str(target)}).status_code, 403)

    def test_batch_carry_over_partial_success_with_batch_audit(self):
        a = self.add(self.staff_a, 'A')
        b = self.add(self.staff_a, 'B')
        done = self.add(self.staff_a, 'C')
        self.patch(self.staff_a, f'{TASKS}{done["id"]}/', {'status': 'completed'})
        stale = self.add(self.staff_a, 'D')
        self.patch(self.staff_a, f'{TASKS}{stale["id"]}/', {'description': 'changed'})
        others = self.add(self.staff_b, 'E（他人）')
        target = next_weekday(self.day)
        response = self.post(self.staff_a, f'{TASKS}carry-over-batch/', {'target_date': str(target), 'items': [
            {'id': a['id'], 'version': a['updated_at']}, {'id': b['id']}, {'id': done['id']},
            {'id': stale['id'], 'version': stale['updated_at']}, {'id': others['id']},
        ]})
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual((body['succeeded'], body['failed']), (2, 3))
        codes = {r['id']: r.get('code') for r in body['results'] if r['status'] == 'failed'}
        self.assertEqual(codes, {done['id']: 'not_open', stale['id']: 'conflict', others['id']: 'not_found'})
        self.assertEqual(Task.objects.filter(work_date=target, responsible_employee=self.emp_a).count(), 2)
        self.assertEqual(Task.objects.get(pk=a['id']).status, 'carried_over')  # 成功分は取り消されない
        log = AuditLog.objects.get(action='plan_items_carried_over_batch')
        self.assertEqual((log.extra['succeeded'], log.extra['failed']), (2, 3))
        self.assertEqual(AuditLog.objects.filter(action='plan_item_carried_over', extra__batch_id=body['batch_id']).count(), 2)

    def test_next_weekday(self):
        self.assertEqual(next_weekday(date(2026, 10, 2)), date(2026, 10, 5))  # 金 → 月
        self.assertEqual(next_weekday(date(2026, 10, 3)), date(2026, 10, 5))  # 土 → 月
        self.assertEqual(next_weekday(date(2026, 10, 5)), date(2026, 10, 6))  # 月 → 火


class ReorderTests(PlanFixture, TestCase):
    def test_reorder_is_all_or_nothing_with_versions(self):
        items = [self.add(self.staff_a, f'項目{i}') for i in range(3)]
        body = {'work_date': str(self.day), 'items': [{'id': i['id'], 'version': i['updated_at']} for i in reversed(items)]}
        response = self.post(self.staff_a, f'{TASKS}reorder/', body)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([r['title'] for r in response.json()], ['項目2', '項目1', '項目0'])
        self.assertTrue(AuditLog.objects.filter(action='plan_items_reordered').exists())
        # 古い版が 1 件でもあれば全体を取りやめる（並び順は変わらない）
        before = list(Task.objects.filter(pk__in=[i['id'] for i in items]).order_by('sort_order').values_list('id', flat=True))
        stale = self.post(self.staff_a, f'{TASKS}reorder/', {'work_date': str(self.day), 'items': [{'id': i['id'], 'version': i['updated_at']} for i in items]})
        self.assertEqual(stale.status_code, 409)
        after = list(Task.objects.filter(pk__in=[i['id'] for i in items]).order_by('sort_order').values_list('id', flat=True))
        self.assertEqual(before, after)
        # 他の日の項目・他人の項目
        tomorrow = self.post(self.staff_a, TASKS, {'title': '明日', 'work_date': str(self.day + timedelta(days=1))}).json()
        self.assertEqual(self.post(self.staff_a, f'{TASKS}reorder/', {'work_date': str(self.day), 'items': [{'id': tomorrow['id']}]}).status_code, 400)
        self.assertEqual(self.post(self.jiao, f'{TASKS}reorder/', {'work_date': str(self.day), 'items': [{'id': items[0]['id']}]}).status_code, 403)


class DailyReportTests(PlanFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.done = self.add(self.staff_a, '入管提出', case=self.case_a.id)
        self.patch(self.staff_a, f'{TASKS}{self.done["id"]}/', {'status': 'completed', 'result_note': '受理番号あり'})
        self.open = self.add(self.staff_a, '社内：資料整理', description='続きは明日')
        self.carried = self.add(self.staff_a, '電話連絡')
        self.post(self.staff_a, f'{TASKS}{self.carried["id"]}/carry-over/', {'target_date': str(next_weekday(self.day))})

    def generate(self, user, **extra):
        return self.post(user, f'{REPORTS}generate/', {'report_date': str(self.day), **extra})

    def test_generate_snapshot_text_and_snapshot_is_frozen(self):
        response = self.generate(self.staff_a)
        self.assertEqual(response.status_code, 201, response.content)
        report = response.json()
        self.assertEqual((report['status'], report['employee'], report['is_edited']), ('draft', self.emp_a.id, False))
        self.assertEqual(report['snapshot']['summary'], {'total': 3, 'completed': 1, 'unfinished': 1, 'carried_over': 1})
        text = report['final_text']
        for fragment in ('■ 完了', '入管提出', '結果：受理番号あり', '■ 未完了・結転', '電話連絡', 'に結転）',
                         '■ 備考', '続きは明日', '■ 関連案件', self.case_a.case_number):
            self.assertIn(fragment, text)
        # 後から計画を変えても保存済みの報告は変わらない
        self.patch(self.staff_a, f'{TASKS}{self.done["id"]}/', {'title': '変更後のタイトル'})
        again = self.get(self.staff_a, f'{REPORTS}{report["id"]}/').json()
        self.assertIn('入管提出', again['final_text'])
        self.assertEqual(again['snapshot']['items'][0]['title'], '入管提出')
        self.assertTrue(AuditLog.objects.filter(action='daily_report_generated').exists())

    def test_edit_regenerate_confirm_rules(self):
        report = self.generate(self.staff_a).json()
        url = f'{REPORTS}{report["id"]}/'
        edited = self.patch(self.staff_a, url, {'final_text': '手で直した本文', 'version': report['updated_at']})
        self.assertEqual(edited.status_code, 200, edited.content)
        self.assertTrue(edited.json()['is_edited'])
        self.assertEqual(self.patch(self.staff_a, url, {'final_text': '古い画面', 'version': report['updated_at']}).status_code, 409)
        # 編集済みの下書きは、上書きの確認なしでは再生成しない
        blocked = self.generate(self.staff_a, version=edited.json()['updated_at'])
        self.assertEqual((blocked.status_code, blocked.json()['code']), (409, 'edited_exists'))
        regenerated = self.generate(self.staff_a, version=edited.json()['updated_at'], overwrite_edits=True)
        self.assertEqual(regenerated.status_code, 200, regenerated.content)
        self.assertFalse(regenerated.json()['is_edited'])
        confirmed = self.post(self.staff_a, f'{url}confirm/', {'version': regenerated.json()['updated_at']})
        self.assertEqual(confirmed.json()['status'], 'confirmed')
        self.assertEqual(self.generate(self.staff_a, overwrite_edits=True).json()['code'], 'confirmed')
        # 確定後も本文は編集できる（スナップショットは固定）
        final = self.patch(self.staff_a, url, {'final_text': '確定後の修正', 'version': confirmed.json()['updated_at']})
        self.assertEqual(final.status_code, 200)
        self.assertEqual(DailyWorkReport.objects.get(pk=report['id']).snapshot['summary']['total'], 3)
        for action_name in ('daily_report_edited', 'daily_report_regenerated', 'daily_report_confirmed'):
            self.assertTrue(AuditLog.objects.filter(action=action_name).exists(), action_name)

    def test_report_permissions_and_invalid_input(self):
        report = self.generate(self.staff_a).json()
        url = f'{REPORTS}{report["id"]}/'
        self.assertEqual(self.get(self.staff_b, url).status_code, 404)
        self.assertEqual(self.get(self.jiao, url).status_code, 200)       # 全件閲覧は閲覧だけ
        self.assertEqual(self.patch(self.jiao, url, {'final_text': 'x'}).status_code, 403)
        self.assertEqual(self.patch(self.li, url, {'final_text': 'x'}).status_code, 403)
        self.assertEqual(self.post(self.jiao, f'{url}confirm/', {}).status_code, 403)
        self.assertEqual(self.post(self.unlinked, f'{REPORTS}generate/', {'report_date': str(self.day)}).status_code, 403)
        future = self.post(self.staff_a, f'{REPORTS}generate/', {'report_date': str(self.day + timedelta(days=3))})
        self.assertEqual(future.status_code, 400)
        self.assertEqual(self.post(self.staff_a, f'{REPORTS}generate/', {'report_date': 'xx'}).status_code, 400)
        self.assertEqual(self.client.post(REPORTS, {}, content_type='application/json').status_code, 405)  # 作成は generate だけ
        # 1 人 1 日 1 件：staff_b は自分の報告を別に作れる
        self.assertEqual(self.generate(self.staff_b).status_code, 201)
        self.assertEqual(DailyWorkReport.objects.filter(report_date=self.day).count(), 2)


class LegacyCompatibilityTests(PlanFixture, TestCase):
    def test_legacy_case_tasks_unchanged(self):
        self.as_user(self.staff_a)
        missing_case = self.client.post(TASKS, {'title': '案件タスク', 'status': 'pending'}, content_type='application/json')
        self.assertEqual(missing_case.status_code, 400)  # 作業日の無いタスクは従来どおり案件が必須
        created = self.client.post(TASKS, {'title': '案件タスク', 'status': 'todo', 'case': self.case_a.id},
                                   content_type='application/json')
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual((created.json()['status'], created.json()['work_date']), ('pending', None))
        self.assertEqual(self.client.post(TASKS, {'title': 'x', 'case': self.case_b.id}, content_type='application/json').status_code, 403)
        # 全件変更権限（李）は従来どおり他担当の案件タスクを変更できる
        self.assertEqual(self.patch(self.li, f'{TASKS}{created.json()["id"]}/', {'title': '李が変更'}).status_code, 200)
        # 案件タスクを計画の項目に変えることはできない
        self.assertEqual(self.patch(self.staff_a, f'{TASKS}{created.json()["id"]}/', {'work_date': str(self.day)}).status_code, 400)
        case = self.get(self.staff_a, f'/api/cases/{self.case_a.id}/').json()
        self.assertEqual((case['task_total_count'], case['task_completed_count'], case['next_task_title']),
                         (1, 0, '李が変更'))

    def test_case_linked_plan_item_does_not_leak_into_case_tasks(self):
        """案件に関連付けた計画の項目は、既定のタスク一覧・案件のタスク数・「次の対応」に入らない。"""
        self.as_user(self.staff_a)
        legacy = self.client.post(TASKS, {'title': '案件タスク（従来）', 'case': self.case_a.id, 'sort_order': 5},
                                  content_type='application/json').json()
        url = f'/api/cases/{self.case_a.id}/'
        before = self.get(self.staff_a, url).json()
        self.assertEqual((before['task_total_count'], before['task_completed_count'], before['next_task_title']),
                         (1, 0, '案件タスク（従来）'))
        # sort_order を小さくして、混ざっていれば「次の対応」になってしまう計画の項目を作る
        plan_open = self.add(self.staff_a, '計画：入管へ電話', case=self.case_a.id, sort_order=0)
        plan_done = self.add(self.staff_a, '計画：書類受領', case=self.case_a.id, sort_order=1)
        self.patch(self.staff_a, f'{TASKS}{plan_done["id"]}/', {'status': 'completed'})

        default_ids = [row['id'] for row in self.rows(self.get(self.staff_a, TASKS))]
        self.assertEqual(default_ids, [legacy['id']])  # 既定の一覧は従来の案件タスクだけ
        self.assertEqual([row['id'] for row in self.rows(self.get(self.staff_a, TASKS, {'case': self.case_a.id}))],
                         [legacy['id']])
        plan_ids = {row['id'] for row in self.rows(self.get(self.staff_a, TASKS, {'plan': '1'}))}
        self.assertEqual(plan_ids, {plan_open['id'], plan_done['id']})  # plan=1 では見つかる
        self.assertEqual(self.get(self.staff_a, f'{TASKS}{plan_open["id"]}/').status_code, 200)  # 詳細は従来どおり

        after = self.get(self.staff_a, url).json()
        self.assertEqual((after['task_total_count'], after['task_completed_count'], after['next_task_title']),
                         (1, 0, '案件タスク（従来）'))
        listed = next(row for row in self.rows(self.get(self.staff_a, '/api/cases/')) if row['id'] == self.case_a.id)
        self.assertEqual((listed['task_total_count'], listed['task_completed_count'], listed['next_task_title']),
                         (1, 0, '案件タスク（従来）'))

    def test_old_style_insert_without_new_columns(self):
        """新しい列を含めない INSERT（P3 以前のコードと同じ形）が成功すること（rollback 互換）。"""
        with connection.cursor() as cursor:
            cursor.execute(
                'INSERT INTO case_tasks (case_id, title, description, status, sort_order, created_at, updated_at) '
                "VALUES (%s, '旧コードのタスク', '', 'pending', 0, NOW(), NOW())", [self.case_a.id])
        task = Task.objects.get(title='旧コードのタスク')
        self.assertEqual((task.priority, task.result_note, task.work_date), ('normal', '', None))

    def test_workbench_api_still_works(self):
        response = self.get(self.staff_a, '/api/workbench/today/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['employee_linked'])
