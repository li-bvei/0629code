"""本番で公開する唯一の診断：health（生存）と readiness（DB 接続）。業務データは返さない。"""
from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.authentication.drf import exempt_api_view

HEALTH_EXEMPT = '死活監視（業務データを返さない・未ログイン可）'


@exempt_api_view(['GET'], HEALTH_EXEMPT)
def health(request):
    return Response({'status': 'ok'})


@exempt_api_view(['GET'], HEALTH_EXEMPT)
def readiness(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        return Response({'status': 'unavailable'}, status=503)
    return Response({'status': 'ready'})


for _view in (health, readiness):
    _view.cls.permission_classes = [AllowAny]
    _view.cls.authentication_classes = []
