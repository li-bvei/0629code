from rest_framework import serializers

from .models import DismissedDeadline, Reminder


class DismissedDeadlineSerializer(serializers.ModelSerializer):
    dismissed_by_name = serializers.CharField(source='dismissed_by.username', read_only=True)

    class Meta:
        model = DismissedDeadline
        fields = [
            'id',
            'source_type',
            'source_id',
            'deadline_type',
            'deadline_date',
            'dismissed_by',
            'dismissed_by_name',
            'note',
            'created_at',
        ]
        read_only_fields = ['id', 'dismissed_by', 'dismissed_by_name', 'created_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['dismissed_by'] = request.user
        return super().create(validated_data)


class ReminderSerializer(serializers.ModelSerializer):
    case_number = serializers.CharField(source='case.case_number', read_only=True)

    class Meta:
        model = Reminder
        fields = [
            'id',
            'case',
            'case_number',
            'title',
            'remind_at',
            'note',
            'is_done',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'case_number', 'created_at', 'updated_at']
