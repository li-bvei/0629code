from rest_framework import serializers

from .models import Reminder


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
