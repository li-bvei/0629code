"""P4：案件種別と業務フロー。新しい種別は 13 段階を使わず、作成時にフローを固定し、種別ごとの空テンプレートを使う。

段階変更（取下げ・復帰を含む）の権限・監査・経過、従来案件の不変、テンプレート変更の権限と監査、関連案件。
すべて合成データ。
"""
from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.authentication.tests.test_case_party_access import AccessFixtureMixin
from apps.cases.models import (
    Case,
    CaseChecklistItem,
    CaseChecklistTemplate,
    CaseChecklistTemplateItem,
    CaseTypeMaster,
    WorkflowStage,
    WorkflowTemplate,
)
from apps.timelines.models import Timeline

RECEPTIONS = '/api/receptions/'


class WorkflowFixture(AccessFixtureMixin):
    def post(self, user, url, body=None):
        self.as_user(user)
        return self.client.post(url, body or {}, content_type='application/json')

    def patch(self, user, url, body):
        self.as_user(user)
        return self.client.patch(url, body, content_type='application/json')

    def get(self, user, url):
        self.as_user(user)
        return self.client.get(url)

    def receive(self, user, type_code, customer=None, **case_extra):
        case_type = CaseTypeMaster.objects.get(code=type_code)
        response = self.post(user, RECEPTIONS, {
            'existing_customer_id': (customer or self.cust_a).id,
            'case': {'case_type_master': case_type.id, **case_extra},
        })
        return response

    def stage(self, workflow_code, stage_code):
        return WorkflowStage.objects.get(template__code=workflow_code, code=stage_code)


class SeedTests(TestCase):
    def test_workflows_types_and_empty_templates_are_seeded(self):
        stages = lambda code: list(WorkflowStage.objects.filter(template__code=code).order_by('sort_order').values_list('name', flat=True))  # noqa: E731
        self.assertEqual(stages('general'), ['受付', '対応中', '完了', '取下げ'])
        self.assertEqual(stages('professional'), ['受付', '資料収集', '専門家へ依頼', '専門家対応中', '結果受領', '完了', '取下げ'])
        self.assertEqual(stages('employee_procedure'), ['受付', '資料収集', '書類作成', '窓口提出', '受理確認', '完了', '取下げ'])
        expected = {
            'other': 'general', 'tax_accountant_commission': 'professional', 'company_dissolution': 'professional',
            'employee_onboarding': 'employee_procedure', 'pension_procedure': 'employee_procedure',
        }
        for code, workflow in expected.items():
            case_type = CaseTypeMaster.objects.get(code=code)
            self.assertEqual(case_type.workflow_template.code, workflow)
            self.assertFalse(case_type.requires_application_category)
            template = CaseChecklistTemplate.objects.get(case_type_master=case_type, application_category__isnull=True)
            self.assertEqual(template.items.count(), 0)  # 必要資料は業務確認前のため空
        self.assertEqual(CaseTypeMaster.objects.filter(name='その他').count(), 1)  # 重複した種別を作らない
        # 入管の種別は従来どおり（フローなし＝13 段階）
        self.assertIsNone(CaseTypeMaster.objects.get(code='business_manager').workflow_template)
        self.assertTrue(CaseTypeMaster.objects.get(code='business_manager').requires_application_category)


class CaseCreationTests(WorkflowFixture, TestCase):
    def test_new_type_uses_its_own_flow_without_category_and_assigns_reception_user(self):
        response = self.receive(self.staff_a, 'tax_accountant_commission')
        self.assertEqual(response.status_code, 201, response.content)
        case = Case.objects.get(pk=response.json()['case'])
        self.assertEqual(case.workflow_template.code, 'professional')
        self.assertEqual((case.workflow_stage.name, case.status), ('受付', Case.STATUS_ACCEPTED))
        self.assertIsNone(case.application_category)
        self.assertEqual(case.responsible_employee, self.emp_a)  # 未指定は受付者本人（未割当を作らない）
        month = timezone.localdate().strftime('%Y%m')
        self.assertEqual(case.case_number, f'税理士-{month}-顧客A-0001')
        self.assertEqual(CaseChecklistItem.objects.filter(case=case).count(), 0)  # 入管の資料は入らない
        detail = self.get(self.staff_a, f'/api/cases/{case.id}/').json()
        self.assertEqual(detail['status_display'], '受付')
        self.assertEqual([s['name'] for s in detail['workflow_stages']][:2], ['受付', '資料収集'])

    def test_other_type_uses_general_flow_and_visa_type_keeps_thirteen_stages(self):
        other = self.receive(self.staff_a, 'other')
        self.assertEqual(other.status_code, 201, other.content)
        self.assertEqual(Case.objects.get(pk=other.json()['case']).workflow_template.code, 'general')
        visa = self.receive(self.staff_a, 'acc')
        self.assertEqual(visa.status_code, 400)  # 入管の種別は申請区分が必要
        visa = self.receive(self.staff_a, 'acc', application_category=self.category.id)
        self.assertEqual(visa.status_code, 201, visa.content)
        case = Case.objects.get(pk=visa.json()['case'])
        self.assertIsNone(case.workflow_template)
        self.assertIsNone(case.workflow_stage)

    def test_template_items_are_copied_at_creation_and_later_template_edits_do_not_change_case(self):
        template = CaseChecklistTemplate.objects.get(case_type_master__code='company_dissolution', application_category__isnull=True)
        item = CaseChecklistTemplateItem.objects.create(template=template, name='合成：解散の資料', sort_order=1)
        case_id = self.receive(self.staff_a, 'company_dissolution').json()['case']
        self.assertEqual(list(CaseChecklistItem.objects.filter(case_id=case_id).values_list('name', flat=True)), ['合成：解散の資料'])
        item.name = '変更後'
        item.save()
        CaseChecklistTemplateItem.objects.create(template=template, name='追加', sort_order=2)
        self.assertEqual(list(CaseChecklistItem.objects.filter(case_id=case_id).values_list('name', flat=True)), ['合成：解散の資料'])

    def test_changing_type_binding_does_not_change_existing_cases(self):
        case_id = self.receive(self.staff_a, 'pension_procedure').json()['case']
        CaseTypeMaster.objects.filter(code='pension_procedure').update(workflow_template=WorkflowTemplate.objects.get(code='general'))
        case = Case.objects.get(pk=case_id)
        self.assertEqual(case.workflow_template.code, 'employee_procedure')
        # 既存の 13 段階の案件も変わらない
        self.case_a.refresh_from_db()
        self.assertIsNone(self.case_a.workflow_template)


class StageChangeTests(WorkflowFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.case = Case.objects.get(pk=self.receive(self.staff_a, 'employee_onboarding').json()['case'])
        self.url = f'/api/cases/{self.case.id}/change-stage/'

    def test_any_stage_withdraw_and_restore_with_audit_and_timeline(self):
        submitted = self.stage('employee_procedure', 'submitted')
        response = self.post(self.staff_a, self.url, {'stage': submitted.id, 'expected_stage': self.case.workflow_stage_id})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()['status_display'], response.json()['status']), ('窓口提出', 'applied'))
        withdrawn = self.stage('employee_procedure', 'withdrawn')
        response = self.post(self.staff_a, self.url, {'stage': withdrawn.id, 'note': '顧客の都合'})
        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual((self.case.status, self.case.withdrawn_at), (Case.STATUS_WITHDRAWN, timezone.localdate()))
        back = self.stage('employee_procedure', 'collecting')
        response = self.post(self.staff_a, self.url, {'stage': back.id})
        self.assertEqual(response.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual((self.case.workflow_stage, self.case.withdrawn_at), (back, None))
        logs = AuditLog.objects.filter(action='case_stage_changed', object_id=str(self.case.id)).order_by('id')
        self.assertEqual([log.changes['workflow_stage'] for log in logs], [
            {'from': '受付', 'to': '窓口提出'}, {'from': '窓口提出', 'to': '取下げ'}, {'from': '取下げ', 'to': '資料収集'},
        ])
        self.assertEqual(logs[1].reason, '顧客の都合')
        self.assertEqual(Timeline.objects.filter(case=self.case, event_type=Timeline.EVENT_STATUS_CHANGED).count(), 3)

    def test_cancel_moves_workflow_case_to_its_withdrawn_stage(self):
        response = self.post(self.staff_a, f'/api/cases/{self.case.id}/cancel/', {'reason': '顧客の都合（合成）'})
        self.assertEqual(response.status_code, 200, response.content)
        self.case.refresh_from_db()
        self.assertEqual((self.case.workflow_stage.code, self.case.status), ('withdrawn', Case.STATUS_WITHDRAWN))
        log = AuditLog.objects.get(action='case_stage_changed', object_id=str(self.case.id))
        self.assertEqual(log.extra['source'], 'cancel')

    def test_completed_date_is_set_and_cleared(self):
        done = self.stage('employee_procedure', 'completed')
        self.post(self.staff_a, self.url, {'stage': done.id})
        self.case.refresh_from_db()
        self.assertEqual(self.case.completed_at, timezone.localdate())
        self.post(self.staff_a, self.url, {'stage': self.stage('employee_procedure', 'preparing').id})
        self.case.refresh_from_db()
        self.assertIsNone(self.case.completed_at)

    def test_errors_conflict_permissions_and_legacy_separation(self):
        other_flow = self.stage('professional', 'requested')
        self.assertEqual(self.post(self.staff_a, self.url, {'stage': other_flow.id}).status_code, 400)
        stale = self.post(self.staff_a, self.url, {'stage': self.stage('employee_procedure', 'preparing').id,
                                                   'expected_stage': self.stage('employee_procedure', 'collecting').id})
        self.assertEqual(stale.status_code, 409)
        WorkflowStage.objects.filter(pk=self.stage('employee_procedure', 'preparing').pk).update(is_active=False)
        self.assertEqual(self.post(self.staff_a, self.url, {'stage': self.stage('employee_procedure', 'preparing').id}).status_code, 400)
        self.assertEqual(self.post(self.staff_b, self.url, {'stage': self.stage('employee_procedure', 'collecting').id}).status_code, 404)
        self.assertEqual(self.post(self.jiao, self.url, {'stage': self.stage('employee_procedure', 'collecting').id}).status_code, 403)
        # 13 段階の進捗変更はフローを持つ案件では使えない／段階変更は従来案件では使えない
        legacy = self.post(self.staff_a, f'/api/cases/{self.case.id}/change-status/', {'new_status': 'completed', 'force': True})
        self.assertEqual(legacy.status_code, 400)
        response = self.post(self.staff_a, f'/api/cases/{self.case_a.id}/change-stage/', {'stage': other_flow.id})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'legacy_workflow')
        # 通常の保存で status を送っても段階と食い違わない
        self.patch(self.staff_a, f'/api/cases/{self.case.id}/', {'status': 'completed'})
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, Case.STATUS_ACCEPTED)


class SettingsTests(WorkflowFixture, TestCase):
    def test_only_case_settings_permission_can_edit_templates_and_changes_are_audited(self):
        workflow = WorkflowTemplate.objects.get(code='general')
        body = {'template': workflow.id, 'code': 'synthetic_check', 'name': '合成確認', 'base_status': 'preparing_documents',
                'sort_order': 25}
        self.assertEqual(self.post(self.staff_a, '/api/workflow-stages/', body).status_code, 403)
        self.assertEqual(self.post(self.jiao, '/api/workflow-stages/', body).status_code, 403)
        self.assertEqual(self.post(self.su_only, '/api/workflow-stages/', body).status_code, 403)
        response = self.post(self.li, '/api/workflow-stages/', body)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(AuditLog.objects.filter(module='case_settings', action='workflowstage_created').exists())
        case_type = CaseTypeMaster.objects.get(code='tax_accountant_commission')
        response = self.patch(self.li, f'/api/case-type-masters/{case_type.id}/', {'workflow_template': workflow.id})
        self.assertEqual(response.status_code, 200, response.content)
        log = AuditLog.objects.get(module='case_settings', action='casetypemaster_updated')
        self.assertEqual(log.changes['workflow_template_id']['to'], workflow.id)
        template = CaseChecklistTemplate.objects.get(case_type_master=case_type, application_category__isnull=True)
        response = self.post(self.li, '/api/case-checklist-template-items/', {'template': template.id, 'name': '合成資料'})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(AuditLog.objects.filter(module='case_settings', action='casechecklisttemplateitem_created').exists())

    def test_template_in_use_and_all_its_stages_are_locked(self):
        workflow = WorkflowTemplate.objects.get(code='general')
        url = f'/api/workflow-templates/{workflow.id}/'
        # 案件で使われる前は段階を追加・変更できる
        added = self.post(self.li, '/api/workflow-stages/', {'template': workflow.id, 'code': 'extra', 'name': '追加段階',
                                                             'base_status': 'preparing_documents', 'sort_order': 25})
        self.assertEqual(added.status_code, 201, added.content)
        self.receive(self.staff_a, 'other')  # 汎用フローの案件ができる（現在の段階は「受付」）
        # テンプレート：名称・系統・有効状態は変えられない（説明・並び順は可）
        for body in ({'name': '汎用（改）'}, {'family': 'professional'}, {'is_active': False}):
            response = self.patch(self.li, url, body)
            self.assertEqual(response.status_code, 400, body)
            self.assertEqual(response.json()['code'], ['workflow_in_use'])
        self.assertEqual(self.patch(self.li, url, {'description': '説明だけ変更'}).status_code, 200)
        # 段階：追加できない
        response = self.post(self.li, '/api/workflow-stages/', {'template': workflow.id, 'code': 'more', 'name': '更に追加',
                                                                'base_status': 'preparing_documents'})
        self.assertEqual(response.status_code, 400)
        # どの案件の現在の段階でもない段階（「完了」「追加段階」）も、名称・順番・有効状態の変更と削除ができない
        done = self.stage('general', 'completed')
        extra = self.stage('general', 'extra')
        self.assertEqual(done.cases.count(), 0)
        for stage in (done, extra, self.stage('general', 'reception')):
            for body in ({'name': '改名'}, {'sort_order': 99}, {'is_active': False}, {'base_status': 'completed'}):
                self.assertEqual(self.patch(self.li, f'/api/workflow-stages/{stage.id}/', body).status_code, 400, (stage.code, body))
            self.as_user(self.li)
            self.assertEqual(self.client.delete(f'/api/workflow-stages/{stage.id}/').status_code, 400)
        self.assertEqual(self.client.delete(url).status_code, 400)
        self.assertEqual(WorkflowStage.objects.filter(template=workflow).count(), 5)
        self.assertEqual(self.stage('general', 'completed').name, '完了')
        detail = self.get(self.li, url).json()
        self.assertTrue(detail['in_use'])

    def test_duplicate_then_rebind_new_cases_use_new_flow_old_cases_keep_old(self):
        old_case_id = self.receive(self.staff_a, 'other').json()['case']
        workflow = WorkflowTemplate.objects.get(code='general')
        response = self.post(self.li, f'/api/workflow-templates/{workflow.id}/duplicate/', {'code': 'general_v2', 'name': '汎用（第 2 版）'})
        self.assertEqual(response.status_code, 201, response.content)
        copy = response.json()
        self.assertEqual([s['code'] for s in copy['stages']], ['reception', 'in_progress', 'completed', 'withdrawn'])
        self.assertFalse(copy['in_use'])
        self.assertTrue(AuditLog.objects.filter(module='case_settings', action='workflowtemplate_created',
                                                object_id=str(copy['id'])).exists())
        # 新しいフローは使われる前なので段階を変更できる
        stage_id = next(s['id'] for s in copy['stages'] if s['code'] == 'in_progress')
        self.assertEqual(self.patch(self.li, f'/api/workflow-stages/{stage_id}/', {'name': '作業中'}).status_code, 200)
        case_type = CaseTypeMaster.objects.get(code='other')
        self.assertEqual(self.patch(self.li, f'/api/case-type-masters/{case_type.id}/', {'workflow_template': copy['id']}).status_code, 200)
        new_case = Case.objects.get(pk=self.receive(self.staff_a, 'other').json()['case'])
        old_case = Case.objects.get(pk=old_case_id)
        self.assertEqual(new_case.workflow_template_id, copy['id'])
        self.assertEqual(old_case.workflow_template_id, workflow.id)
        self.assertEqual(old_case.workflow_stage.template_id, workflow.id)
        # 旧フローの案件の段階変更は旧フローの段階だけ
        self.assertEqual(self.post(self.staff_a, f'/api/cases/{old_case.id}/change-stage/', {'stage': stage_id}).status_code, 400)
        detail = self.get(self.staff_a, f'/api/cases/{new_case.id}/').json()
        self.assertIn('作業中', [s['name'] for s in detail['workflow_stages']])
        self.assertNotIn('作業中', [s['name'] for s in self.get(self.staff_a, f'/api/cases/{old_case.id}/').json()['workflow_stages']])
        # 複製は案件設定の権限者だけ
        self.assertEqual(self.post(self.staff_a, f'/api/workflow-templates/{workflow.id}/duplicate/', {'code': 'x'}).status_code, 403)


class RelatedCaseTests(WorkflowFixture, TestCase):
    def test_parent_case_is_optional_scoped_and_listed_for_visible_children(self):
        response = self.receive(self.staff_a, 'pension_procedure', parent_case=self.case_a.id)
        self.assertEqual(response.status_code, 201, response.content)
        child = Case.objects.get(pk=response.json()['case'])
        self.assertEqual(child.parent_case, self.case_a)
        standalone = self.receive(self.staff_a, 'employee_onboarding')
        self.assertEqual(standalone.status_code, 201)
        self.assertIsNone(Case.objects.get(pk=standalone.json()['case']).parent_case)
        # 見られない案件は関連元にできない（存在も明かさない）
        hidden = self.receive(self.staff_a, 'pension_procedure', parent_case=self.case_b.id)
        self.assertEqual(hidden.status_code, 400)
        detail = self.get(self.staff_a, f'/api/cases/{self.case_a.id}/').json()
        self.assertEqual([c['id'] for c in detail['child_cases']], [child.id])
        self.assertEqual(self.get(self.staff_a, f'/api/cases/{child.id}/').json()['parent_case_number'], self.case_a.case_number)
        # 元の在留案件の進捗・履歴は変わらない
        self.case_a.refresh_from_db()
        self.assertIsNone(self.case_a.workflow_template)
        # 存在しない案件と見られない案件は同じ応答（存在を推測させない）
        missing = self.patch(self.staff_a, f'/api/cases/{child.id}/', {'parent_case': 999999})
        hidden_patch = self.patch(self.staff_a, f'/api/cases/{child.id}/', {'parent_case': self.case_b.id})
        self.assertEqual((missing.status_code, missing.json()), (hidden_patch.status_code, hidden_patch.json()))
        # 自分自身・子孫を関連元にはできない
        self.assertEqual(self.patch(self.staff_a, f'/api/cases/{self.case_a.id}/', {'parent_case': child.id}).status_code, 400)
        self.assertEqual(self.patch(self.staff_a, f'/api/cases/{child.id}/', {'parent_case': child.id}).status_code, 400)
        # 他の担当者からは子案件が見えない（以下は循環の確認を別テストで行う）
        other_child = self.receive(self.staff_b, 'pension_procedure', customer=self.cust_b, parent_case=self.case_b.id)
        self.assertEqual(other_child.status_code, 201, other_child.content)
        self.assertEqual(self.get(self.jiao, f'/api/cases/{self.case_b.id}/').json()['child_cases'][0]['id'],
                         other_child.json()['case'])

    def chain(self, length, employee_user=None):
        """関連元をたどる長い鎖を作る（合成データ。作成は ORM で直接）。先頭が一番古い。"""
        cases = []
        parent = None
        for _ in range(length):
            case = Case.objects.create(case_type_master=CaseTypeMaster.objects.get(code='other'), customer=self.cust_a,
                                       responsible_employee=self.emp_a, parent_case=parent)
            cases.append(case)
            parent = case
        return cases

    def test_cycles_are_rejected_at_any_depth_including_existing_anomalies(self):
        cases = self.chain(25)
        root, leaf = cases[0], cases[-1]
        url = f'/api/cases/{root.id}/'
        # 自分自身
        self.assertEqual(self.patch(self.staff_a, url, {'parent_case': root.id}).status_code, 400)
        # 直下の子・孫・20 段を超える子孫
        for descendant in (cases[1], cases[2], cases[21], leaf):
            response = self.patch(self.staff_a, url, {'parent_case': descendant.id})
            self.assertEqual(response.status_code, 400, descendant.id)
            self.assertIn('この案件自身', response.json()['parent_case'][0])
        root.refresh_from_db()
        self.assertIsNone(root.parent_case_id)
        # 循環しない付け替えは通る（25 段の鎖の末端を別の案件の下へ）
        other = Case.objects.create(case_type_master=CaseTypeMaster.objects.get(code='other'), customer=self.cust_a,
                                    responsible_employee=self.emp_a)
        self.assertEqual(self.patch(self.staff_a, f'/api/cases/{other.id}/', {'parent_case': leaf.id}).status_code, 200)
        # 既存データの異常な循環（X↔Y）：たどっても止まり、関連元にはできない
        x, y = self.chain(2)
        Case.objects.filter(pk=x.pk).update(parent_case=y)
        z = Case.objects.create(case_type_master=CaseTypeMaster.objects.get(code='other'), customer=self.cust_a,
                                responsible_employee=self.emp_a)
        response = self.patch(self.staff_a, f'/api/cases/{z.id}/', {'parent_case': x.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn('循環', response.json()['parent_case'][0])
        # 存在しない案件と見られない案件は同じ応答のまま
        missing = self.patch(self.staff_a, f'/api/cases/{z.id}/', {'parent_case': 999999})
        hidden = self.patch(self.staff_a, f'/api/cases/{z.id}/', {'parent_case': self.case_b.id})
        self.assertEqual((missing.status_code, missing.json()), (hidden.status_code, hidden.json()))

