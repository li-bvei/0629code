from rest_framework import serializers

from .models import Timeline


class TimelineSerializer(serializers.ModelSerializer):
    case_number = serializers.CharField(source='case.case_number', read_only=True)
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = Timeline
        fields = [
            'id',
            'case',
            'case_number',
            'occurred_at',
            'title',
            'content',
            'event_type',
            'actor',
            'actor_name',
            'metadata',
            'is_visible_to_client',
            'created_at',
            'updated_at',
        ]
        # event_type / actor / metadata は自動記録サービス（record_case_event 等）が
        # 設定するもので、API からの手入力記録では常に空。
        read_only_fields = [
            'id', 'case_number', 'event_type', 'actor', 'actor_name',
            'metadata', 'created_at', 'updated_at',
        ]

    def get_actor_name(self, obj):
        if not obj.actor_id:
            return ''
        return obj.actor.get_full_name() or obj.actor.get_username()
