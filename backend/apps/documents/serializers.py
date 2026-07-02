from rest_framework import serializers

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    case_number = serializers.CharField(source='case.case_number', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id',
            'case',
            'case_number',
            'title',
            'file',
            'file_url',
            'file_name',
            'file_path',
            'file_size',
            'content_type',
            'source',
            'is_visible_to_client',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'case_number',
            'file_url',
            'file_name',
            'file_path',
            'file_size',
            'content_type',
            'created_at',
            'updated_at',
        ]

    def get_file_url(self, obj):
        if not obj.file:
            return ''
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url

    def set_file_metadata(self, data, uploaded_file):
        data['file_name'] = uploaded_file.name
        data['file_size'] = uploaded_file.size
        data['content_type'] = getattr(uploaded_file, 'content_type', '') or ''
        data['file_path'] = ''

    def create(self, validated_data):
        uploaded_file = validated_data.get('file')
        if uploaded_file:
            self.set_file_metadata(validated_data, uploaded_file)

        document = super().create(validated_data)
        if uploaded_file:
            document.file_path = document.file.name
            document.save(update_fields=['file_path'])
        return document

    def update(self, instance, validated_data):
        uploaded_file = validated_data.get('file')
        old_file = instance.file if uploaded_file and instance.file else None
        old_file_name = old_file.name if old_file else ''

        if uploaded_file:
            self.set_file_metadata(validated_data, uploaded_file)

        document = super().update(instance, validated_data)
        if uploaded_file:
            document.file_path = document.file.name
            document.save(update_fields=['file_path'])
            if old_file_name and old_file_name != document.file.name:
                old_file.storage.delete(old_file_name)
        return document
