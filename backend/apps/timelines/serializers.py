from rest_framework import serializers

from .models import Timeline


class TimelineSerializer(serializers.ModelSerializer):
    case_number = serializers.CharField(source='case.case_number', read_only=True)

    class Meta:
        model = Timeline
        fields = [
            'id',
            'case',
            'case_number',
            'occurred_at',
            'title',
            'content',
            'is_visible_to_client',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'case_number', 'created_at', 'updated_at']
