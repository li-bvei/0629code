from rest_framework.response import Response

from apps.authentication.drf import business_api_view

from .services import current_settings, set_fiscal_year_end_month


@business_api_view(['GET', 'PATCH'], 'office_settings')
def office_settings(request):
    """GET：業務利用者なら誰でも参照できる。PATCH：manage_office_settings（system_admin）だけ。"""
    if request.method == 'PATCH':
        return Response(set_fiscal_year_end_month(request.data.get('fiscal_year_end_month'), request))
    return Response(current_settings())
