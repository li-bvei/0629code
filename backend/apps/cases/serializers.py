from django.utils import timezone
from rest_framework import serializers

from apps.tasks.models import Task

from .models import (
    AcquisitionPlacePreset,
    Case,
    CaseApplicationCategory,
    CaseChecklistItem,
    CaseChecklistTemplate,
    CaseChecklistTemplateItem,
    CaseStatusSetting,
    CaseTypeMaster,
    ResponsiblePartyPreset,
)
from .status_service import get_required_checklist_progress


class CaseTypeMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseTypeMaster
        fields = ['id', 'name', 'code', 'number_abbreviation', 'sort_order', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'code': {'read_only': True}}

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


class CaseSerializer(serializers.ModelSerializer):
    case_number = serializers.CharField(read_only=True)
    status = serializers.ChoiceField(
        choices=Case.STATUS_CHOICES,
        required=False,
        default=Case.STATUS_COLLECTING_DOCUMENTS,
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    registration_status_display = serializers.CharField(source='get_registration_status_display', read_only=True)
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

    class Meta:
        model = Case
        fields = [
            'id',
            'case_number',
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
            'withdrawn_at',
            'completed_at',
            'archived_at',
            'status_changed_at',
            'next_action',
            'next_action_due_at',
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
            'case_type',
            'registration_status_display',
            'status',
            'status_display',
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

    def validate(self, attrs):
        if self.instance is None:
            if not attrs.get('case_type_master'):
                raise serializers.ValidationError({'case_type_master': '案件種別を選択してください。'})
            if not attrs.get('application_category'):
                raise serializers.ValidationError({'application_category': '申請区分を選択してください。'})
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
        return super().create(validated_data)

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

    def get_task_total_count(self, obj):
        return obj.tasks.count()

    def get_task_completed_count(self, obj):
        return obj.tasks.filter(status=Task.STATUS_COMPLETED).count()

    def get_next_task(self, obj):
        cached_name = '_case_serializer_next_task'
        if hasattr(obj, cached_name):
            return getattr(obj, cached_name)
        task = (
            obj.tasks
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
        return self.calculate_days(obj.applied_at, obj.result_received_at)

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

    class Meta:
        model = CaseChecklistTemplate
        fields = [
            'id',
            'name',
            'description',
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
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'case_number',
            'completed_by_name',
            'item_type_display',
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
