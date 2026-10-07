import os

from django.db import transaction
from rest_framework import serializers

from .models import Document, DocumentReplacement
from .naming import (
    assign_display_name, download_name, has_party_name, legacy_content_label, normalize_content_label, party_name,
)
from .upload_policy import file_metadata, validate_upload


class DocumentSerializer(serializers.ModelSerializer):
    case_number = serializers.CharField(source='case.case_number', read_only=True)
    file_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    archived_by_name = serializers.SerializerMethodField()
    replacement_count = serializers.SerializerMethodField()
    checklist_items = serializers.SerializerMethodField()
    # 登録時に同じ案件の Checklist 項目へ関連付ける（任意・書き込み専用）
    checklist_item = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    replace_reason = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=255)
    # P6：資料内容（新しく登録するファイルは必須）。表示名は後端が「資料内容-顧客名.拡張子」で作る
    content_label = serializers.CharField(required=False, allow_blank=True, max_length=200)
    download_name = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id', 'case', 'case_number', 'title', 'category', 'category_display',
            'file', 'file_url', 'preview_url', 'file_name', 'content_label', 'display_name', 'download_name',
            'file_path', 'file_size', 'content_type', 'sha256',
            'source', 'is_visible_to_client',
            'uploaded_by', 'uploaded_by_name',
            'is_archived', 'archived_at', 'archived_by', 'archived_by_name', 'archive_reason',
            'replacement_count', 'checklist_items', 'checklist_item', 'replace_reason',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'case_number', 'file_url', 'preview_url', 'file_name', 'display_name', 'download_name',
            'file_path', 'file_size', 'content_type',
            'sha256', 'uploaded_by', 'uploaded_by_name', 'is_archived', 'archived_at', 'archived_by',
            'archived_by_name', 'archive_reason', 'replacement_count', 'checklist_items', 'category_display',
            'created_at', 'updated_at',
        ]

    # --- 表示 --------------------------------------------------------------
    def get_file_url(self, obj):
        """受保護ダウンロード API の URL。公開の /media/ URL は返さない。"""
        if not obj.file:
            return ''
        return self._api_url(obj, 'download')

    def get_preview_url(self, obj):
        if not obj.file:
            return ''
        return self._api_url(obj, 'preview')

    def _api_url(self, obj, kind):
        from django.urls import reverse

        path = reverse(f'document-{kind}', kwargs={'pk': obj.pk})
        request = self.context.get('request')
        return request.build_absolute_uri(path) if request else path

    @staticmethod
    def _user_name(user):
        if user is None:
            return ''
        employee = getattr(user, 'employee', None) if hasattr(user, 'employee') else None
        return employee.name if employee else (f'{user.last_name}{user.first_name}' or user.get_username())

    def get_uploaded_by_name(self, obj):
        return self._user_name(obj.uploaded_by)

    def get_archived_by_name(self, obj):
        return self._user_name(obj.archived_by)

    def get_download_name(self, obj):
        return download_name(obj)

    def get_replacement_count(self, obj):
        return obj.replacements.count()

    def get_checklist_items(self, obj):
        return [{'id': item.id, 'name': item.name, 'received_at': item.received_at}
                for item in obj.checklist_items.all()]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # FileField の既定表現（/media/... の公開 URL）を返さない。
        data['file'] = data.get('file_url') or ''
        return data

    # --- 検証・保存 -----------------------------------------------------------
    def validate_file(self, uploaded_file):
        if uploaded_file is None:
            return uploaded_file
        problem = validate_upload(uploaded_file)
        if problem:
            raise serializers.ValidationError(problem)
        return uploaded_file

    def validate_content_label(self, value):
        if value in (None, ''):
            return ''
        try:
            return normalize_content_label(value)
        except serializers.ValidationError as exc:
            raise serializers.ValidationError(exc.detail['content_label']) from exc

    def validate(self, attrs):
        new_file = self.instance is None and attrs.get('file') is not None
        if new_file and 'content_label' in self.initial_data:
            # P6 の登録画面（content_label を送る新しいクライアント）：資料内容は必須
            if not attrs.get('content_label'):
                raise serializers.ValidationError({'content_label': ['資料内容（例：住民票・在留カード）を入力してください。']})
            attrs['_content_label_source'] = 'user'
        elif new_file:
            # 旧クライアント互換：P6 以前の単ファイル登録 API は content_label を送らない。400 にせず、後で派生する
            attrs['_content_label_source'] = 'legacy_derived'
        item_id = attrs.get('checklist_item')
        if item_id:
            from apps.cases.models import CaseChecklistItem

            case = attrs.get('case') or getattr(self.instance, 'case', None)
            item = CaseChecklistItem.objects.filter(pk=item_id).first()
            if item is None or case is None or item.case_id != case.pk:
                raise serializers.ValidationError({'checklist_item': ['同じ案件の必要資料だけを関連付けできます。']})
            attrs['_checklist_item_obj'] = item
        return attrs

    def create(self, validated_data):
        validated_data.pop('checklist_item', None)
        validated_data.pop('replace_reason', None)
        item = validated_data.pop('_checklist_item_obj', None)
        label_source = validated_data.pop('_content_label_source', '')
        uploaded_file = validated_data.get('file')
        if label_source == 'legacy_derived':
            validated_data['content_label'], label_source = self._legacy_label(validated_data, item, uploaded_file)
        if uploaded_file:
            validated_data.update(file_metadata(uploaded_file))
            validated_data['file_path'] = ''
        case = validated_data.get('case')
        if validated_data.get('content_label') and case is not None:
            party_name(case)  # 顧客・会社が無い案件は保存前に字段エラー（推測しない）
        with transaction.atomic():
            if case is not None:
                # 同じ案件の表示名の重複確認を順番に行う（同時登録でも ID 付きの規則を守る）
                type(case).objects.select_for_update().filter(pk=case.pk).first()  # access-reviewed: 権限確認済みの親案件をロックするだけ
            document = super().create(validated_data)
            if uploaded_file:
                document.file_path = document.file.name
                document.save(update_fields=['file_path'])
            assign_display_name(document)
        document._content_label_source = label_source  # 監査用（document_upload の extra）
        return document

    @staticmethod
    def _legacy_label(validated_data, item, uploaded_file):
        """旧 API 互換の資料内容。顧客・会社が無い案件は資料内容も表示名も付けず、旧データと同じ扱いにする。"""
        case = validated_data.get('case')
        if case is None or not has_party_name(case):
            return '', 'legacy_no_party'
        original = getattr(uploaded_file, 'name', '') or ''
        stem, ext = os.path.splitext(os.path.basename(original.replace('\\', '/')))
        title = str(validated_data.get('title') or '')
        if ext and title.lower().endswith(ext.lower()):
            title = title[:-len(ext)]
        category = dict(Document._meta.get_field('category').choices).get(validated_data.get('category'), '')
        return legacy_content_label(getattr(item, 'name', ''), title, stem, category), 'legacy_derived'

    def update(self, instance, validated_data):
        validated_data.pop('checklist_item', None)
        validated_data.pop('_checklist_item_obj', None)
        reason = validated_data.pop('replace_reason', '')
        uploaded_file = validated_data.get('file')
        previous = None
        if uploaded_file and instance.file:
            previous = {
                'previous_file': instance.file.name,
                'previous_file_name': instance.file_name,
                'previous_size': instance.file_size,
                'previous_sha256': instance.sha256,
                'previous_content_type': instance.content_type,
            }
        if uploaded_file:
            validated_data.update(file_metadata(uploaded_file))
        label_changed = 'content_label' in validated_data and validated_data['content_label'] != instance.content_label
        label = validated_data.get('content_label', instance.content_label)
        rename = bool(label) and (label_changed or bool(uploaded_file) or not instance.display_name)
        case = validated_data.get('case') or instance.case
        if rename and case is not None:
            party_name(case)  # 顧客・会社が無い案件は書き込み前に字段エラー
        document = super().update(instance, validated_data)
        if uploaded_file:
            document.file_path = document.file.name
            document.save(update_fields=['file_path'])
        if rename:
            # 資料内容の追加・変更、差し替え（拡張子が変わることがある）のときだけ表示名を作り直す
            document.display_name = ''
            assign_display_name(document)
        if previous:
            # 差し替え前のファイルは削除せず残し、履歴に記録する（完全な版管理ではない）。資料内容の有無に関係なく残す
            request = self.context.get('request')
            actor = getattr(request, 'user', None)
            DocumentReplacement.objects.create(
                document=document, reason=reason,
                replaced_by=actor if getattr(actor, 'is_authenticated', False) else None, **previous,
            )
        return document


class DocumentReplacementSerializer(serializers.ModelSerializer):
    replaced_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentReplacement
        # 保存名（previous_file）は返さない：旧ファイルは画面から開かない
        fields = ['id', 'previous_file_name', 'previous_size', 'previous_sha256', 'previous_content_type',
                  'reason', 'replaced_by_name', 'replaced_at']

    def get_replaced_by_name(self, obj):
        return DocumentSerializer._user_name(obj.replaced_by)
