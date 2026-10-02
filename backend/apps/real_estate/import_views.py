"""LIST.xlsx / CSV の dry-run 取込 API。取引の作成（本取込）は第 1 版では提供しない。

- 本番では無効（settings.REAL_ESTATE_IMPORT_DRY_RUN_ENABLED、既定は DEBUG と同じ）。
- 候補（顧客・会社・物件・担当者）は利用者の閲覧範囲の中だけで探し、自動で結び付けない。
"""
from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.audit.services import record
from apps.authentication.drf import BusinessScopedViewSetMixin
from .list_import import ListImportError, build_report, error_report_csv, file_sha256
from .models import RealEstateImportRun


def import_enabled():
    return getattr(settings, 'REAL_ESTATE_IMPORT_DRY_RUN_ENABLED', settings.DEBUG)


class RealEstateImportViewSet(BusinessScopedViewSetMixin, ReadOnlyModelViewSet):
    access_resource = 'real_estate_import'
    access_action_map = {'dry_run': 'create', 'error_report': 'export'}
    parser_classes = [MultiPartParser, FormParser]
    queryset = RealEstateImportRun.objects.all()

    def get_serializer_class(self):
        return None

    def list(self, request, *args, **kwargs):
        runs = self.get_queryset()[:50]
        return Response([
            {'id': r.id, 'file_name': r.file_name, 'sheet': r.sheet, 'summary': r.summary, 'created_at': r.created_at,
             'file_sha256': r.file_sha256}
            for r in runs
        ])

    def retrieve(self, request, *args, **kwargs):
        run = self.get_object()
        return Response({'id': run.id, 'file_name': run.file_name, 'created_at': run.created_at, **run.report})

    def _candidates(self):
        policy = self.business_policy

        def customer(name):
            if not name:
                return []
            return [{'id': c.id, 'name': c.name} for c in policy.queryset('customer', 'list').filter(name__icontains=name)[:5]]

        def company(name):
            if not name:
                return []
            return [{'id': c.id, 'name': c.name} for c in policy.queryset('company', 'list').filter(name__icontains=name)[:5]]

        def prop(name, room):
            if not name:
                return []
            qs = policy.queryset('real_estate', 'list').filter(property_name__iexact=name)
            if room:
                qs = qs.filter(room_number=room)
            return [{'id': t.id, 'number': t.transaction_number, 'property_name': t.property_name,
                     'room_number': t.room_number} for t in qs[:5]]

        def responsible(name):
            if not name:
                return []
            # アカウントや Employee は参照せず、既存記録の担当者文字列だけを候補にする。
            rows = policy.queryset('real_estate', 'list').exclude(responsible_name='').filter(
                responsible_name__icontains=name).order_by('responsible_name').values_list(
                'responsible_name', flat=True).distinct()[:5]
            return [{'name': value} for value in rows]

        def existing(values):
            if not (values.get('party_name') and values.get('property_name')):
                return []
            qs = policy.queryset('real_estate', 'list').filter(
                party_name=values['party_name'], property_name=values['property_name'],
                room_number=values.get('room_number') or '')
            return [{'id': t.id, 'number': t.transaction_number} for t in qs[:5]]

        return {'customer': customer, 'company': company, 'property': prop, 'responsible': responsible, 'existing': existing}

    @action(detail=False, methods=['post'], url_path='dry-run')
    def dry_run(self, request):
        if not import_enabled():
            raise PermissionDenied('この環境では取込（dry-run を含む）を使用できません。')
        upload = request.FILES.get('file')
        if upload is None:
            return Response({'file': ['ファイルを選択してください。']}, status=status.HTTP_400_BAD_REQUEST)
        content = upload.read()
        try:
            report = build_report(upload.name, content, candidates=self._candidates())
        except ListImportError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        digest = file_sha256(content)
        previous = list(RealEstateImportRun.objects.filter(file_sha256=digest).values_list('id', flat=True)[:10])
        run = RealEstateImportRun.objects.create(file_name=upload.name[:255], file_sha256=digest, sheet=report['sheet'],
                                                 summary=report['summary'], report=report, created_by=request.user)
        record(module='real_estate', action='import_dry_run', request=request, obj=run,
               extra={'file_name': upload.name, 'sha256': digest, **report['summary'], 'previous_runs': previous})
        return Response({'id': run.id, 'dry_run': True, 'previous_runs': previous, **report},
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='error-report')
    def error_report(self, request, pk=None):
        run = self.get_object()
        record(module='real_estate', action='import_error_report', request=request, obj=run)
        response = HttpResponse(error_report_csv(run.report), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="real_estate_dry_run_{run.id}.csv"'
        return response
