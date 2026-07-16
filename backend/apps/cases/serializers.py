from rest_framework import serializers

from apps.tasks.models import Task

from .models import Case, CaseChecklistItem, CaseChecklistTemplate, CaseChecklistTemplateItem
from .status_service import get_required_checklist_progress


class CaseSerializer(serializers.ModelSerializer):
    case_number = serializers.CharField(read_only=True)
    status = serializers.CharField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    registration_status_display = serializers.CharField(source='get_registration_status_display', read_only=True)
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

    class Meta:
        model = Case
        fields = [
            'id',
            'case_number',
            'case_type',
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
            'accepted_at',
            'applied_at',
            'result_notified_at',
            'completed_at',
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
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'case_number',
            'registration_status',
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
            'created_at',
            'updated_at',
        ]

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
