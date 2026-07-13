from rest_framework import serializers

from apps.tasks.models import Task

from .models import Case


class CaseSerializer(serializers.ModelSerializer):
    case_number = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField()
    customer_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    responsible_employee_name = serializers.SerializerMethodField()
    task_total_count = serializers.SerializerMethodField()
    task_completed_count = serializers.SerializerMethodField()
    next_task_title = serializers.SerializerMethodField()
    next_task_responsible_employee_name = serializers.SerializerMethodField()

    class Meta:
        model = Case
        fields = [
            'id',
            'case_number',
            'case_type',
            'status',
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
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'customer_name',
            'company_name',
            'responsible_employee_name',
            'task_total_count',
            'task_completed_count',
            'next_task_title',
            'next_task_responsible_employee_name',
            'created_at',
            'updated_at',
        ]

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
