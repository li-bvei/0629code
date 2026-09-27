"""（読み取りのみ）MEDIA_ROOT のファイルと Document の対応、および保存データ中の /media/ 参照を棚卸しする。

nginx で公開 /media/ を閉じる前（D9）に本番で実行し、結果を承認資料にする。何も変更・削除しない。
"""
import os

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models

from apps.documents.models import Document

# /media/ を含む可能性のある自由記述・JSON 項目
TEXT_FIELD_TYPES = (models.TextField, models.CharField, models.JSONField)


class Command(BaseCommand):
    help = 'MEDIA_ROOT の実ファイル・Document の不整合・DB 内の /media/ 参照を報告する（読み取りのみ）。'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=20, help='明細の表示件数')

    def handle(self, *args, **options):
        limit = options['limit']
        media_root = os.path.realpath(settings.MEDIA_ROOT)
        files = []
        for root, _dirs, names in os.walk(media_root):
            for name in names:
                files.append(os.path.relpath(os.path.join(root, name), media_root))
        referenced = set(Document.objects.exclude(file='').values_list('file', flat=True))
        by_top = {}
        for path in files:
            top = path.split(os.sep, 1)[0] if os.sep in path else '(root)'
            by_top[top] = by_top.get(top, 0) + 1
        orphans = sorted(set(files) - referenced)
        missing = sorted(name for name in referenced if name and not os.path.isfile(os.path.join(media_root, name)))

        self.stdout.write(f'MEDIA_ROOT: {media_root}')
        self.stdout.write(f'実ファイル数: {len(files)} / ディレクトリ別: {by_top}')
        self.stdout.write(f'Document 登録ファイル数: {len(referenced)}')
        self.stdout.write(f'Document に紐付かないファイル（削除しない・報告のみ）: {len(orphans)} 件 {orphans[:limit]}')
        self.stdout.write(f'Document はあるが実ファイルが無い: {len(missing)} 件 {missing[:limit]}')
        outside = [p for p in files if not p.startswith('case_documents' + os.sep)]
        self.stdout.write(f'case_documents/ 以外のファイル（受保護ダウンロード対象外）: {len(outside)} 件 {outside[:limit]}')

        self.stdout.write('--- DB 内の "/media/" 参照 ---')
        total_hits = 0
        for model in apps.get_models():
            if model._meta.app_label in ('admin', 'sessions', 'contenttypes', 'auth', 'axes', 'audit', 'authentication'):
                continue
            fields = [f for f in model._meta.get_fields() if isinstance(f, TEXT_FIELD_TYPES) and f.concrete]
            for field in fields:
                if isinstance(field, models.JSONField):
                    qs = model._default_manager.all()
                    hits = [obj.pk for obj in qs.only('pk', field.name) if '/media/' in str(getattr(obj, field.name) or '')]
                    count = len(hits)
                else:
                    qs = model._default_manager.filter(**{f'{field.name}__contains': '/media/'})
                    count = qs.count()
                    hits = list(qs.values_list('pk', flat=True)[:limit])
                if count:
                    total_hits += count
                    self.stdout.write(f'{model._meta.label}.{field.name}: {count} 件 pk={hits[:limit]}')
        self.stdout.write(f'/media/ 参照 合計: {total_hits} 件（0 件なら nginx 切替による既存リンク切れは無い）')
