from rest_framework import serializers
from django.utils import timezone

from .models import DailyWorkReport, Task


class TaskSerializer(serializers.ModelSerializer):
    status = serializers.CharField(required=False)
    case_number = serializers.CharField(source='case.case_number', read_only=True)
    case_customer_name = serializers.SerializerMethodField()
    responsible_employee_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    carried_from_date = serializers.DateField(source='carried_from.work_date', read_only=True, default=None)
    carried_to = serializers.SerializerMethodField()
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
            'case_customer_name',
            'title',
            'description',
            'responsible_employee',
            'responsible_employee_name',
            'status',
            'status_display',
            'sort_order',
            'due_date',
            'planned_completion_date',
            'completed_at',
            # 毎日の計画（P3）
            'work_date',
            'priority',
            'priority_display',
            'result_note',
            'carried_from',
            'carried_from_date',
            'carried_to',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'case_number', 'responsible_employee_name', 'carried_from', 'created_at', 'updated_at']

    def get_responsible_employee_name(self, obj):
        if obj.responsible_employee is None:
            return ''
        return obj.responsible_employee.name

    def get_case_customer_name(self, obj):
        case = obj.case
        return getattr(case.customer, 'name', '') if case is not None and case.customer_id else ''

    def get_carried_to(self, obj):
        target = getattr(obj, 'carried_to', None) if hasattr(obj, 'carried_to') else None
        if target is None:
            return None
        return {'id': target.id, 'work_date': target.work_date.isoformat() if target.work_date else None}

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
        if value == Task.STATUS_CARRIED_OVER and getattr(self.instance, 'status', None) != Task.STATUS_CARRIED_OVER:
            raise serializers.ValidationError('結転は「結転」の操作で行ってください。')
        return value

    def validate_title(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('内容を入力してください。')
        return value

    def validate(self, attrs):
        instance = self.instance
        work_date = attrs.get('work_date', getattr(instance, 'work_date', None))
        case = attrs.get('case', getattr(instance, 'case', None))
        # 従来の案件タスクは案件が必須（案件の無い作業は「毎日の計画」で作業日を付けて登録する）
        if work_date is None and case is None:
            raise serializers.ValidationError({'case': ['案件を選択してください（社内作業は毎日の計画に作業日付きで登録します）。']})
        if instance is not None and instance.status == Task.STATUS_CARRIED_OVER:
            locked = {'status', 'work_date', 'case', 'title', 'priority'} & {k for k, v in attrs.items()
                                                                           if v != getattr(instance, k, None)}
            if locked:
                raise serializers.ValidationError({'status': ['結転済みの項目は、メモ以外を変更できません（結転先で操作してください）。']})
        return attrs

    def _normalize_completion_date(self, instance, validated_data):
        status_value = validated_data.get('status', getattr(instance, 'status', Task.STATUS_PENDING))
        if status_value == Task.STATUS_COMPLETED:
            if not validated_data.get('completed_at') and not getattr(instance, 'completed_at', None):
                validated_data['completed_at'] = timezone.localdate()
        elif getattr(instance, 'status', None) == Task.STATUS_COMPLETED and 'completed_at' not in validated_data:
            validated_data['completed_at'] = None

    def create(self, validated_data):
        validated_data.setdefault('status', Task.STATUS_PENDING)
        self._normalize_completion_date(None, validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._normalize_completion_date(instance, validated_data)
        return super().update(instance, validated_data)


class DailyWorkReportSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_edited = serializers.SerializerMethodField()

    class Meta:
        model = DailyWorkReport
        fields = [
            'id', 'employee', 'employee_name', 'report_date', 'status', 'status_display', 'snapshot',
            'generated_text', 'final_text', 'is_edited', 'generated_at', 'confirmed_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [f for f in fields if f != 'final_text']

    def get_is_edited(self, obj):
        return obj.final_text != obj.generated_text
