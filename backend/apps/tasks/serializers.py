from rest_framework import serializers

from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    status = serializers.CharField()
    case_number = serializers.CharField(source='case.case_number', read_only=True)

    class Meta:
        model = Task
        fields = [
            'id',
            'case',
            'case_number',
            'title',
            'description',
            'status',
            'due_date',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'case_number', 'created_at', 'updated_at']
