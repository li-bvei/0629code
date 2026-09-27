import re

from .services import new_request_id

_REQUEST_ID_RE = re.compile(r'^[A-Za-z0-9._-]{8,64}$')


class RequestIdMiddleware:
    """各リクエストに request_id を付け、監査ログとレスポンスヘッダで追跡できるようにする。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get('HTTP_X_REQUEST_ID', '')
        request.request_id = incoming if _REQUEST_ID_RE.match(incoming or '') else new_request_id()
        response = self.get_response(request)
        response['X-Request-ID'] = request.request_id
        return response
