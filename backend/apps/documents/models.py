import os
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def document_upload_to(instance, filename):
    """保存名は推測できない UUID にする（元のファイル名は file_name に保持）。"""
    ext = os.path.splitext(filename or '')[1].lower()[:10]
    today = timezone.localdate()
    return f'case_documents/{today:%Y/%m}/{uuid.uuid4().hex}{ext}'


class Document(models.Model):
    SOURCE_INTERNAL = 'internal'
    SOURCE_CLIENT = 'client'
    SOURCE_SYSTEM = 'system'

    SOURCE_CHOICES = [
        (SOURCE_INTERNAL, '内部アップロード'),
        (SOURCE_CLIENT, '顧客アップロード'),
        (SOURCE_SYSTEM, 'システム生成'),
    ]

    CATEGORY_IDENTITY = 'identity'
    CATEGORY_RESIDENCE = 'residence'
    CATEGORY_APPLICATION = 'application'
    CATEGORY_CERTIFICATE = 'certificate'
    CATEGORY_COMPANY = 'company'
    CATEGORY_CONTRACT = 'contract'
    CATEGORY_CORRESPONDENCE = 'correspondence'
    CATEGORY_OTHER = 'other'
    CATEGORY_CHOICES = [
        (CATEGORY_IDENTITY, '本人確認書類'),
        (CATEGORY_RESIDENCE, '在留関係'),
        (CATEGORY_APPLICATION, '申請書類'),
        (CATEGORY_CERTIFICATE, '証明書'),
        (CATEGORY_COMPANY, '会社書類'),
        (CATEGORY_CONTRACT, '契約・請求'),
        (CATEGORY_CORRESPONDENCE, '連絡・通知'),
        (CATEGORY_OTHER, 'その他'),
    ]

    case = models.ForeignKey(
        'cases.Case',
        on_delete=models.CASCADE,
        related_name='documents',
    )
    title = models.CharField(max_length=150)
    file = models.FileField(upload_to=document_upload_to, null=True, blank=True, max_length=255)
    category = models.CharField('分類', max_length=30, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    sha256 = models.CharField('SHA-256', max_length=64, blank=True, db_index=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='登録者', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='uploaded_documents',
    )
    # 物理削除の代わりに使う「アーカイブ」。一覧の既定表示から外すだけで、ファイルは残る。
    is_archived = models.BooleanField('アーカイブ済み', default=False)
    archived_at = models.DateTimeField('アーカイブ日時', null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='アーカイブ実行者', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='archived_documents',
    )
    archive_reason = models.CharField('アーカイブ理由', max_length=255, blank=True)
    file_name = models.CharField(max_length=255)  # アップロード時の元のファイル名
    # P6：登録者が入力する「資料内容」（例：住民票）と、後端が作る表示用ファイル名「資料内容-顧客名.拡張子」。
    # 実際の保存名は file（UUID）のまま。旧データは空（ダウンロード名は従来どおり元のファイル名）。
    content_label = models.CharField('資料内容', max_length=60, blank=True, default='')
    display_name = models.CharField('表示ファイル名', max_length=255, blank=True, default='')
    file_path = models.CharField(max_length=500)
    file_size = models.PositiveIntegerField(blank=True, null=True)
    content_type = models.CharField(max_length=100, blank=True)
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_INTERNAL,
    )
    is_visible_to_client = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'case_documents'
        permissions = [
            ('document_view_all', '担当外を含む全ファイルのメタデータ閲覧'),
            ('document_download_all', '担当外のファイルのダウンロード・プレビュー'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def delete(self, *args, **kwargs):
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)


class DocumentReplacement(models.Model):
    """ファイル差し替えの履歴（完全な版管理ではない）。

    差し替え前のファイルは削除せずストレージに残し、ここに元の情報を記録する。
    画面から旧ファイルを開く機能は提供しない（必要時はサーバー側で復旧）。
    """

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='replacements')
    previous_file = models.CharField('差し替え前の保存名', max_length=255)
    previous_file_name = models.CharField('差し替え前の元ファイル名', max_length=255, blank=True)
    previous_size = models.PositiveIntegerField('差し替え前のサイズ', null=True, blank=True)
    previous_sha256 = models.CharField('差し替え前の SHA-256', max_length=64, blank=True)
    previous_content_type = models.CharField('差し替え前の MIME', max_length=100, blank=True)
    reason = models.CharField('理由', max_length=255, blank=True)
    replaced_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='差し替え実行者', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='document_replacements',
    )
    replaced_at = models.DateTimeField('差し替え日時', auto_now_add=True)

    class Meta:
        db_table = 'case_document_replacements'
        ordering = ['-replaced_at', '-id']

    def __str__(self):
        return f'{self.document_id}: {self.previous_file_name}'
