from django.utils import timezone
from rest_framework import serializers

from apps.tasks.models import Task

from .utils import auto_apply_default_checklist_template
from .models import (
    AcquisitionPlacePreset,
    Case,
    CaseApplicationCategory,
    CaseChecklistItem,
    CaseChecklistTemplate,
    CaseChecklistTemplateItem,
    CaseStatusSetting,
    CaseTypeMaster,
    ChecklistItemPreset,
    ResponsiblePartyPreset,
    WorkflowStage,
    WorkflowTemplate,
)
from .status_service import get_required_checklist_progress


WORKFLOW_LOCKED_MESSAGE = (
    '案件で使われている業務フローは変更できません（段階の追加・名称・順番・有効状態・削除を含む）。'
    '「複製」で新しいフローを作り、案件種別を新しいフローに結び付け直してください。既存の案件は元のフローのまま使います。'
)


def workflow_in_use(template_id):
    """案件がこのフローで作られているか。使われているフローは内容を固定する（既存案件の意味を変えない）。"""
    return template_id is not None and Case.objects.filter(workflow_template_id=template_id).exists()  # access-reviewed: 設定の整合性確認（件数のみ）


class WorkflowStageSerializer(serializers.ModelSerializer):
    base_status_display = serializers.CharField(source='get_base_status_display', read_only=True)
    is_withdrawn = serializers.BooleanField(read_only=True)
    case_count = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowStage
        fields = ['id', 'template', 'code', 'name', 'base_status', 'base_status_display', 'is_withdrawn',
                  'sort_order', 'is_active', 'case_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_case_count(self, obj):
        return obj.cases.count()

    def validate(self, attrs):
        template = attrs.get('template') or getattr(self.instance, 'template', None)
        if template is not None and workflow_in_use(template.pk):
            # 案件で使われているフローの段階は、まだどの案件の現在の段階でなくても追加・変更しない
            raise serializers.ValidationError({'detail': WORKFLOW_LOCKED_MESSAGE, 'code': 'workflow_in_use'})
        if self.instance is not None:
            # 段階の所属フローとコードは作成後に変えない（既存案件の段階の意味を変えないため）
            for name in ('template', 'code'):
                if name in attrs and attrs[name] != getattr(self.instance, name):
                    raise serializers.ValidationError({name: '作成後は変更できません。'})
            if 'base_status' in attrs and attrs['base_status'] != self.instance.base_status and self.instance.cases.exists():
                raise serializers.ValidationError({'base_status': '案件で使われている段階の対応する進捗は変更できません。'})
        return attrs


class WorkflowTemplateSerializer(serializers.ModelSerializer):
    family_display = serializers.CharField(source='get_family_display', read_only=True)
    stages = WorkflowStageSerializer(many=True, read_only=True)
    case_type_names = serializers.SerializerMethodField()
    case_count = serializers.SerializerMethodField()
    in_use = serializers.SerializerMethodField()

    # 案件で使われた後も変更できるのは説明と並び順だけ（案件の意味に関わらない）
    LOCKED_FIELDS = ('code', 'name', 'family', 'is_active')

    class Meta:
        model = WorkflowTemplate
        fields = ['id', 'code', 'name', 'family', 'family_display', 'description', 'is_active', 'sort_order',
                  'stages', 'case_type_names', 'case_count', 'in_use', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_case_type_names(self, obj):
        return [case_type.name for case_type in obj.case_types.all()]

    def get_case_count(self, obj):
        return obj.cases.count()

    def get_in_use(self, obj):
        return workflow_in_use(obj.pk)

    def validate(self, attrs):
        if self.instance is not None and 'code' in attrs and attrs['code'] != self.instance.code:
            raise serializers.ValidationError({'code': '作成後は変更できません。'})
        if self.instance is not None and workflow_in_use(self.instance.pk):
            changed = [name for name in self.LOCKED_FIELDS
                       if name in attrs and attrs[name] != getattr(self.instance, name)]
            if changed:
                raise serializers.ValidationError({'detail': WORKFLOW_LOCKED_MESSAGE, 'code': 'workflow_in_use',
                                                   'locked_fields': changed})
        return attrs


class CaseTypeMasterSerializer(serializers.ModelSerializer):
    workflow_template_name = serializers.CharField(source='workflow_template.name', read_only=True, default='')

    class Meta:
        model = CaseTypeMaster
        fields = ['id', 'name', 'code', 'number_abbreviation', 'sort_order', 'is_active', 'workflow_template',
                  'workflow_template_name', 'requires_application_category', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'code': {'read_only': True}}

    def validate_workflow_template(self, value):
        if value is not None and not value.is_active and getattr(self.instance, 'workflow_template_id', None) != value.pk:
            raise serializers.ValidationError('無効な業務フローは選べません。')
        return value

    def create(self, validated_data):
        name = validated_data.get('name', '')
        validated_data['code'] = self.initial_data.get('code') or name.lower().replace(' ', '_')
        return super().create(validated_data)


class CaseApplicationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseApplicationCategory
        fields = ['id', 'name', 'code', 'number_abbreviation', 'sort_order', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'code': {'read_only': True}}

    def create(self, validated_data):
        name = validated_data.get('name', '')
        validated_data['code'] = self.initial_data.get('code') or name.lower().replace(' ', '_')
        return super().create(validated_data)


class CaseStatusSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseStatusSetting
        fields = ['id', 'code', 'display_name', 'sort_order', 'is_visible', 'created_at', 'updated_at']
        read_only_fields = ['id', 'code', 'created_at', 'updated_at']


class AcquisitionPlacePresetSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcquisitionPlacePreset
        fields = ['id', 'name', 'sort_order', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ResponsiblePartyPresetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResponsiblePartyPreset
        fields = ['id', 'name', 'code', 'sort_order', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'code': {'read_only': True}}

    def create(self, validated_data):
        name = validated_data.get('name', '')
        validated_data['code'] = self.initial_data.get('code') or name.lower().replace(' ', '_')
        return super().create(validated_data)


class ChecklistItemPresetSerializer(serializers.ModelSerializer):
    responsible_party_display = serializers.CharField(source='get_responsible_party_display', read_only=True)

    class Meta:
        model = ChecklistItemPreset
        fields = [
            'id', 'name', 'category', 'acquisition_place', 'responsible_party',
            'responsible_party_display', 'required_details', 'sort_order', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CaseSerializer(serializers.ModelSerializer):
    case_number = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(
        choices=Case.STATUS_CHOICES,
        required=False,
        default=Case.STATUS_COLLECTING_DOCUMENTS,
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    registration_status_display = serializers.CharField(source='get_registration_status_display', read_only=True)
    archived_by_name = serializers.CharField(source='archived_by.username', read_only=True, default='')
    case_type_master_name = serializers.CharField(source='case_type_master.name', read_only=True)
    case_type_number_abbreviation = serializers.CharField(source='case_type_master.number_abbreviation', read_only=True)
    application_category_name = serializers.CharField(source='application_category.name', read_only=True)
    application_category_number_abbreviation = serializers.CharField(source='application_category.number_abbreviation', read_only=True)
    customer_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    responsible_employee_name = serializers.SerializerMethodField()
    task_total_count = serializers.SerializerMethodField()
    task_completed_count = serializers.SerializerMethodField()
    next_task_title = serializers.SerializerMethodField()
    next_task_responsible_employee_name = serializers.SerializerMethodField()
    required_items_total = serializers.SerializerMethodField()
    required_items_completed = serializers.SerializerMethodField()
    required_items_remaining = serializers.SerializerMethodField()
    required_items_progress_percent = serializers.SerializerMethodField()
    all_required_items_completed = serializers.SerializerMethodField()
    suggested_case_status = serializers.SerializerMethodField()
    suggestion_message = serializers.SerializerMethodField()
    progress_started_at = serializers.SerializerMethodField()
    progress_elapsed_days = serializers.SerializerMethodField()
    progress_remaining_days = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    attention_priority = serializers.SerializerMethodField()
    review_duration_days = serializers.SerializerMethodField()
    days_until_additional_request = serializers.SerializerMethodField()
    additional_documents_duration_days = serializers.SerializerMethodField()
    total_processing_days = serializers.SerializerMethodField()
    # --- Next Action / 待機（読み取り専用。変更は専用 action → work_service） ---
    next_action_assignee_name = serializers.CharField(source='next_action_assignee.name', read_only=True, default='')
    next_action_state = serializers.SerializerMethodField()
    work_status_display = serializers.CharField(source='get_work_status_display', read_only=True)
    waiting_reason_display = serializers.CharField(source='get_waiting_reason_display', read_only=True)
    waiting_days = serializers.SerializerMethodField()
    # --- 業務フロー・関連案件・サービス項目（P4） ---
    workflow_template_name = serializers.CharField(source='workflow_template.name', read_only=True, default='')
    workflow_family = serializers.CharField(source='workflow_template.family', read_only=True, default='')
    workflow_stage_name = serializers.CharField(source='workflow_stage.name', read_only=True, default='')
    parent_case = serializers.PrimaryKeyRelatedField(
        queryset=Case.objects.all(), required=False, allow_null=True,  # access-reviewed: validate_parent_case で閲覧範囲を確認する
        # 存在しない案件と見られない案件で同じ文言にする（存在を推測させない）
        error_messages={'does_not_exist': '関連元の案件が見つかりません。', 'incorrect_type': '関連元の案件が見つかりません。'},
    )
    parent_case_number = serializers.SerializerMethodField()

    class Meta:
        model = Case
        fields = [
            'id',
            'case_number',
            'workflow_template',
            'workflow_template_name',
            'workflow_family',
            'workflow_stage',
            'workflow_stage_name',
            'parent_case',
            'parent_case_number',
            'service_items',
            'case_type',
            'case_type_master',
            'case_type_master_name',
            'case_type_number_abbreviation',
            'application_category',
            'application_category_name',
            'application_category_number_abbreviation',
            'registration_status',
            'registration_status_display',
            'status',
            'status_display',
            'customer',
            'customer_name',
            'company',
            'company_name',
            'responsible_employee',
            'responsible_employee_name',
            'consulted_at',
            'accepted_at',
            'document_collection_started_at',
            'documents_completed_at',
            'application_ready_at',
            'applied_at',
            'application_authority',
            'application_receipt_number',
            'permission_number',
            'review_started_at',
            'expected_result_at',
            'additional_documents_requested_at',
            'additional_documents_due_at',
            'additional_documents_submitted_at',
            'additional_documents_detail',
            'result_notified_at',
            'result_received_at',
            'result_note',
            'residence_card_received_at',
            'withdrawn_at',
            'completed_at',
            'archived_at',
            'archived_by_name',
            'archive_reason',
            'restored_at',
            'status_changed_at',
            'next_action',
            'next_action_due_at',
            'next_action_assignee',
            'next_action_assignee_name',
            'next_action_blocked_reason',
            'next_action_completed_at',
            'next_action_completed_by',
            'next_action_state',
            'work_status',
            'work_status_display',
            'waiting_reason',
            'waiting_reason_display',
            'waiting_note',
            'waiting_since',
            'waiting_until',
            'waiting_days',
            'task_total_count',
            'task_completed_count',
            'next_task_title',
            'next_task_responsible_employee_name',
            'required_items_total',
            'required_items_completed',
            'required_items_remaining',
            'required_items_progress_percent',
            'all_required_items_completed',
            'suggested_case_status',
            'suggestion_message',
            'progress_started_at',
            'progress_elapsed_days',
            'progress_remaining_days',
            'is_overdue',
            'attention_priority',
            'review_duration_days',
            'days_until_additional_request',
            'additional_documents_duration_days',
            'total_processing_days',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'case_number',
            # 業務フロー・段階は作成時に固定し、段階は専用 action（change-stage）でのみ変更する
            'workflow_template',
            'workflow_stage',
            # サービス項目（参考）は新規受付で選んだ時点のスナップショット
            'service_items',
            'case_type',
            # registration_status / status は通常の PUT/PATCH では変更させない。
            # 状態遷移チェック・warning・Timeline 記録・操作者記録が必要なため、
            # 専用アクション（change-registration-status / change-status）経由でのみ変更する。
            'registration_status',
            'registration_status_display',
            'status',
            'status_display',
            # アーカイブ関連は専用 action（archive / restore）でのみ変更する。
            'archived_at',
            'archived_by_name',
            'archive_reason',
            'restored_at',
            # 次の対応・待機も専用 action（work_service：事務・Timeline・AuditLog）でのみ変更する。
            'next_action',
            'next_action_due_at',
            'next_action_assignee',
            'next_action_assignee_name',
            'next_action_blocked_reason',
            'next_action_completed_at',
            'next_action_completed_by',
            'next_action_state',
            'work_status',
            'work_status_display',
            'waiting_reason',
            'waiting_reason_display',
            'waiting_note',
            'waiting_since',
            'waiting_until',
            'waiting_days',
            'customer_name',
            'company_name',
            'responsible_employee_name',
            'task_total_count',
            'task_completed_count',
            'next_task_title',
            'next_task_responsible_employee_name',
            'required_items_total',
            'required_items_completed',
            'required_items_remaining',
            'required_items_progress_percent',
            'all_required_items_completed',
            'suggested_case_status',
            'suggestion_message',
            'progress_started_at',
            'progress_elapsed_days',
            'progress_remaining_days',
            'is_overdue',
            'attention_priority',
            'review_duration_days',
            'days_until_additional_request',
            'additional_documents_duration_days',
            'total_processing_days',
            'created_at',
            'updated_at',
        ]

    def get_parent_case_number(self, obj):
        return obj.parent_case.case_number if obj.parent_case_id else ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.workflow_stage_id:
            # フローを持つ案件は段階名を進捗として表示する（status は既存処理用の対応先）
            data['status_display'] = instance.workflow_stage.name
        if self.context.get('include_related'):
            stages = []
            if instance.workflow_template_id:
                stages = [
                    {'id': stage.id, 'name': stage.name, 'code': stage.code, 'base_status': stage.base_status,
                     'is_withdrawn': stage.is_withdrawn, 'is_active': stage.is_active}
                    for stage in instance.workflow_template.stages.order_by('sort_order', 'id')
                    if stage.is_active or stage.pk == instance.workflow_stage_id
                ]
            data['workflow_stages'] = stages
            policy = self.context.get('policy')
            children = policy.queryset('case', 'list').filter(parent_case=instance) if policy is not None else []
            data['child_cases'] = [
                {'id': child.id, 'case_number': child.case_number, 'case_type': child.case_type,
                 'status_display': child.workflow_stage.name if child.workflow_stage_id else child.get_status_display()}
                for child in (children.select_related('workflow_stage').order_by('created_at') if policy is not None else [])
            ]
        return data

    def validate_parent_case(self, value):
        if value is None:
            return value
        policy = self.context.get('policy')
        if policy is None or not policy.queryset('case', 'view').filter(pk=value.pk).exists():
            raise serializers.ValidationError('関連元の案件が見つかりません。')
        # 関連元をたどって循環しないことを確かめる（段数の上限なし。既存データに循環があっても止まる）
        own_id = getattr(self.instance, 'pk', None)
        seen = set()
        current_id = value.pk
        while current_id is not None:
            if current_id == own_id:
                raise serializers.ValidationError('この案件自身や、この案件から作られた案件は関連元にできません。')
            if current_id in seen:
                raise serializers.ValidationError('関連元の案件の関連が循環しています。管理者に確認してください。')
            seen.add(current_id)
            current_id = Case.objects.filter(pk=current_id).values_list('parent_case_id', flat=True).first()  # access-reviewed: 関連の循環確認（ID のみ。応答には出さない）
        return value

    def validate(self, attrs):
        if self.instance is None:
            if not attrs.get('case_type_master'):
                raise serializers.ValidationError({'case_type_master': '案件種別を選択してください。'})
            if attrs['case_type_master'].requires_application_category and not attrs.get('application_category'):
                raise serializers.ValidationError({'application_category': '申請区分を選択してください。'})
        elif self.instance.workflow_template_id:
            # 業務フローを持つ案件の status は段階で決まる（通常の保存では変えない）
            attrs.pop('status', None)
        case_type_master = attrs.get('case_type_master') or getattr(self.instance, 'case_type_master', None)
        application_category = attrs.get('application_category') or getattr(self.instance, 'application_category', None)
        if case_type_master and case_type_master.is_active and not case_type_master.number_abbreviation.strip():
            raise serializers.ValidationError({'case_type_master': '案件種別の案件番号略称が未設定です。'})
        if application_category and application_category.is_active and not application_category.number_abbreviation.strip():
            raise serializers.ValidationError({'application_category': '申請区分の案件番号略称が未設定です。'})
        return attrs

    def create(self, validated_data):
        case_type_master = validated_data.get('case_type_master')
        if case_type_master:
            validated_data['case_type'] = case_type_master.name
        instance = super().create(validated_data)
        auto_apply_default_checklist_template(instance)
        return instance

    def update(self, instance, validated_data):
        case_type_master = validated_data.get('case_type_master')
        if case_type_master:
            validated_data['case_type'] = case_type_master.name
        return super().update(instance, validated_data)

    progress_start_fields = {
        Case.STATUS_CONSULTATION: 'consulted_at',
        Case.STATUS_ACCEPTED: 'accepted_at',
        Case.STATUS_COLLECTING_DOCUMENTS: 'document_collection_started_at',
        Case.STATUS_PREPARING_DOCUMENTS: 'documents_completed_at',
        Case.STATUS_READY_TO_APPLY: 'application_ready_at',
        Case.STATUS_APPLIED: 'applied_at',
        Case.STATUS_UNDER_REVIEW: 'review_started_at',
        Case.STATUS_ADDITIONAL_DOCUMENTS: 'additional_documents_requested_at',
        Case.STATUS_ADDITIONAL_DOCUMENTS_SUBMITTED: 'additional_documents_submitted_at',
        Case.STATUS_APPROVED: 'result_received_at',
        Case.STATUS_REJECTED: 'result_received_at',
        Case.STATUS_WITHDRAWN: 'withdrawn_at',
        Case.STATUS_COMPLETED: 'completed_at',
    }

    terminal_statuses = {
        Case.STATUS_APPROVED,
        Case.STATUS_REJECTED,
        Case.STATUS_WITHDRAWN,
        Case.STATUS_COMPLETED,
    }

    priority_map = {
        Case.STATUS_ADDITIONAL_DOCUMENTS: 20,
        Case.STATUS_ADDITIONAL_DOCUMENTS_SUBMITTED: 25,
        Case.STATUS_READY_TO_APPLY: 30,
        Case.STATUS_PREPARING_DOCUMENTS: 40,
        Case.STATUS_COLLECTING_DOCUMENTS: 50,
        Case.STATUS_ACCEPTED: 60,
        Case.STATUS_APPLIED: 70,
        Case.STATUS_UNDER_REVIEW: 80,
        Case.STATUS_CONSULTATION: 90,
        Case.STATUS_APPROVED: 100,
        Case.STATUS_REJECTED: 110,
        Case.STATUS_WITHDRAWN: 120,
        Case.STATUS_COMPLETED: 130,
    }

    def get_progress_start_date(self, obj):
        field_name = self.progress_start_fields.get(obj.status)
        value = getattr(obj, field_name, None) if field_name else None
        if obj.status == Case.STATUS_UNDER_REVIEW and not value:
            value = obj.applied_at
        if obj.status == Case.STATUS_PREPARING_DOCUMENTS and not value:
            value = obj.status_changed_at
        return value or obj.status_changed_at or obj.updated_at.date()

    def get_due_date(self, obj):
        if obj.status == Case.STATUS_ADDITIONAL_DOCUMENTS and obj.additional_documents_due_at:
            return obj.additional_documents_due_at
        if obj.status == Case.STATUS_UNDER_REVIEW and obj.expected_result_at:
            return obj.expected_result_at
        return obj.next_action_due_at

    def validate_customer(self, value):
        if not (value.name or '').strip():
            raise serializers.ValidationError('顧客氏名が未入力のため、案件番号を生成できません。')
        return value

    def get_required_progress(self, obj):
        cached_name = '_case_serializer_required_progress'
        if hasattr(obj, cached_name):
            return getattr(obj, cached_name)
        progress = get_required_checklist_progress(obj)
        setattr(obj, cached_name, progress)
        return progress

    def get_next_action_state(self, obj):
        if not obj.next_action:
            return 'none'
        return 'done' if obj.next_action_completed_at else 'open'

    def get_waiting_days(self, obj):
        if obj.work_status != Case.WORK_STATUS_WAITING or not obj.waiting_since:
            return None
        return (timezone.localdate() - obj.waiting_since).days

    def get_customer_name(self, obj):
        return obj.customer.name

    def get_company_name(self, obj):
        if obj.company is None:
            return ''
        return obj.company.name

    def get_responsible_employee_name(self, obj):
        if obj.responsible_employee is None:
            return ''
        return obj.responsible_employee.name

    @staticmethod
    def _case_tasks(obj):
        # 案件タスクだけを数える。毎日の計画の項目（work_date あり・P3）は案件に関連付いていても含めない
        return obj.tasks.filter(work_date__isnull=True)

    def get_task_total_count(self, obj):
        return self._case_tasks(obj).count()

    def get_task_completed_count(self, obj):
        return self._case_tasks(obj).filter(status=Task.STATUS_COMPLETED).count()

    def get_next_task(self, obj):
        cached_name = '_case_serializer_next_task'
        if hasattr(obj, cached_name):
            return getattr(obj, cached_name)
        task = (
            self._case_tasks(obj)
            .exclude(status__in=[Task.STATUS_COMPLETED, Task.STATUS_CANCELLED])
            .select_related('responsible_employee')
            .order_by('sort_order', 'id')
            .first()
        )
        setattr(obj, cached_name, task)
        return task

    def get_next_task_title(self, obj):
        task = self.get_next_task(obj)
        if task is None:
            return ''
        return task.title

    def get_next_task_responsible_employee_name(self, obj):
        task = self.get_next_task(obj)
        if task is None or task.responsible_employee is None:
            return ''
        return task.responsible_employee.name

    def get_required_items_total(self, obj):
        return self.get_required_progress(obj)['required_items_total']

    def get_required_items_completed(self, obj):
        return self.get_required_progress(obj)['required_items_completed']

    def get_required_items_remaining(self, obj):
        return self.get_required_progress(obj)['required_items_remaining']

    def get_required_items_progress_percent(self, obj):
        return self.get_required_progress(obj)['required_items_progress_percent']

    def get_all_required_items_completed(self, obj):
        return self.get_required_progress(obj)['all_required_items_completed']

    def get_suggested_case_status(self, obj):
        return self.get_required_progress(obj)['suggested_case_status']

    def get_suggestion_message(self, obj):
        return self.get_required_progress(obj)['suggestion_message']

    def get_progress_started_at(self, obj):
        return self.get_progress_start_date(obj)

    def get_progress_elapsed_days(self, obj):
        start_date = self.get_progress_start_date(obj)
        end_date = timezone.localdate()
        if obj.status in self.terminal_statuses:
            end_date = obj.result_received_at or obj.completed_at or obj.updated_at.date()
        return max((end_date - start_date).days, 0)

    def get_progress_remaining_days(self, obj):
        due_date = self.get_due_date(obj)
        if not due_date:
            return None
        return (due_date - timezone.localdate()).days

    def get_is_overdue(self, obj):
        if obj.status in self.terminal_statuses:
            return False
        remaining_days = self.get_progress_remaining_days(obj)
        return remaining_days is not None and remaining_days < 0

    def get_attention_priority(self, obj):
        base = self.priority_map.get(obj.status, 999)
        return 0 if self.get_is_overdue(obj) else base

    def calculate_days(self, start_date, end_date):
        if not start_date or not end_date:
            return None
        days = (end_date - start_date).days
        return days if days >= 0 else None

    def get_review_duration_days(self, obj):
        end_date = obj.result_received_at
        if not end_date and obj.status not in self.terminal_statuses:
            end_date = timezone.localdate()
        return self.calculate_days(obj.applied_at, end_date)

    def get_days_until_additional_request(self, obj):
        return self.calculate_days(obj.applied_at, obj.additional_documents_requested_at)

    def get_additional_documents_duration_days(self, obj):
        return self.calculate_days(obj.additional_documents_requested_at, obj.additional_documents_submitted_at)

    def get_total_processing_days(self, obj):
        return self.calculate_days(obj.accepted_at, obj.completed_at)


class CaseChecklistTemplateItemSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    item_type_display = serializers.CharField(source='get_item_type_display', read_only=True)
    can_move_up = serializers.SerializerMethodField()
    can_move_down = serializers.SerializerMethodField()

    class Meta:
        model = CaseChecklistTemplateItem
        fields = [
            'id',
            'template',
            'template_name',
            'category',
            'name',
            'item_type',
            'item_type_display',
            'quantity',
            'unit',
            'is_required',
            'description',
            'responsible_party',
            'acquisition_place',
            'required_details',
            'internal_note',
            'customer_note',
            'is_visible_to_customer',
            'importance_level',
            'sort_order',
            'is_active',
            'can_move_up',
            'can_move_down',
            'deleted_at',
            'deleted_with_template',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'template_name',
            'item_type_display',
            'can_move_up',
            'can_move_down',
            'deleted_at',
            'deleted_with_template',
            'created_at',
            'updated_at',
        ]

    def _get_order_info(self, obj):
        cache = self.context.setdefault('_template_item_order_cache', {})
        if obj.template_id not in cache:
            ordered_ids = list(
                CaseChecklistTemplateItem.objects
                .filter(template_id=obj.template_id, deleted_at__isnull=True)
                .order_by('sort_order', 'id')
                .values_list('id', flat=True)
            )
            cache[obj.template_id] = {
                'positions': {item_id: index + 1 for index, item_id in enumerate(ordered_ids)},
                'total': len(ordered_ids),
            }
        return cache[obj.template_id]

    def get_can_move_up(self, obj):
        order_info = self._get_order_info(obj)
        return order_info['positions'].get(obj.id, 1) > 1

    def get_can_move_down(self, obj):
        order_info = self._get_order_info(obj)
        return order_info['positions'].get(obj.id, order_info['total']) < order_info['total']


class CaseChecklistTemplateSerializer(serializers.ModelSerializer):
    items = CaseChecklistTemplateItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()
    case_type_master_name = serializers.CharField(source='case_type_master.name', read_only=True)
    application_category_name = serializers.CharField(source='application_category.name', read_only=True)

    class Meta:
        model = CaseChecklistTemplate
        fields = [
            'id',
            'name',
            'description',
            'case_type_master',
            'case_type_master_name',
            'application_category',
            'application_category_name',
            'is_active',
            'sort_order',
            'deleted_at',
            'items',
            'item_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'deleted_at', 'items', 'item_count', 'created_at', 'updated_at']

    def get_item_count(self, obj):
        if hasattr(obj, '_prefetched_objects_cache') and 'items' in obj._prefetched_objects_cache:
            return len([item for item in obj.items.all() if item.is_active])
        return obj.items.filter(is_active=True).count()


class CaseChecklistItemSerializer(serializers.ModelSerializer):
    case_number = serializers.CharField(source='case.case_number', read_only=True)
    completed_by_name = serializers.SerializerMethodField()
    item_type_display = serializers.CharField(source='get_item_type_display', read_only=True)
    document_title = serializers.CharField(source='document.title', read_only=True, default='')

    class Meta:
        model = CaseChecklistItem
        fields = [
            'id',
            'case',
            'case_number',
            'source_template_item',
            'category',
            'name',
            'item_type',
            'item_type_display',
            'quantity',
            'unit',
            'is_required',
            'is_completed',
            'completed_at',
            'completed_by',
            'completed_by_name',
            'note',
            'responsible_party',
            'acquisition_place',
            'required_details',
            'internal_note',
            'customer_note',
            'is_visible_to_customer',
            'importance_level',
            'sort_order',
            'received_at',
            'document',
            'document_title',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'case_number',
            'completed_by_name',
            'item_type_display',
            # 受領日・関連ファイルは receive action（同一案件の Document のみ・Timeline・監査）でのみ設定する。
            'received_at',
            'document',
            'document_title',
            'created_at',
            'updated_at',
        ]

    def get_completed_by_name(self, obj):
        if obj.completed_by is None:
            return ''
        return obj.completed_by.name


class CaseChecklistDeletionHistorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    object_type = serializers.CharField()
    name = serializers.CharField()
    template_name = serializers.CharField(allow_blank=True)
    deleted_at = serializers.DateTimeField()
    can_restore = serializers.BooleanField()
