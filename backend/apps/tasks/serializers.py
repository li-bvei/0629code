from rest_framework import serializers
from django.utils import timezone

from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    status = serializers.CharField()
    case_number = serializers.CharField(source='case.case_number', read_only=True)
    responsible_employee_name = serializers.SerializerMethodField()
    planned_completion_date = serializers.DateField(
        source='due_date',
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Task
        fields = [
            'id',
            'case',
            'case_number',
            'title',
            'description',
            'responsible_employee',
            'responsible_employee_name',
            'status',
            'sort_order',
            'due_date',
            'planned_completion_date',
            'completed_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'case_number', 'responsible_employee_name', 'created_at', 'updated_at']

    def get_responsible_employee_name(self, obj):
        if obj.responsible_employee is None:
            return ''
        return obj.responsible_employee.name

    def validate_status(self, value):
        aliases = {
            'todo': Task.STATUS_PENDING,
            'done': Task.STATUS_COMPLETED,
            '未対応': Task.STATUS_PENDING,
            '対応中': Task.STATUS_IN_PROGRESS,
            '完了': Task.STATUS_COMPLETED,
            '保留': Task.STATUS_PAUSED,
        }
        value = aliases.get(value, value)
        valid_statuses = {choice[0] for choice in Task.STATUS_CHOICES}
        if value not in valid_statuses:
            raise serializers.ValidationError('ステータスを選択してください。')
        return value

    def _normalize_completion_date(self, instance, validated_data):
        status_value = validated_data.get('status', getattr(instance, 'status', Task.STATUS_PENDING))
        if status_value == Task.STATUS_COMPLETED:
            if not validated_data.get('completed_at') and not getattr(instance, 'completed_at', None):
                validated_data['completed_at'] = timezone.localdate()
        elif getattr(instance, 'status', None) == Task.STATUS_COMPLETED and 'completed_at' not in validated_data:
            validated_data['completed_at'] = None

    def create(self, validated_data):
        self._normalize_completion_date(None, validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._normalize_completion_date(instance, validated_data)
        return super().update(instance, validated_data)
