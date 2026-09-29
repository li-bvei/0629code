"""権限を考慮した全体検索 /api/search/?q=。

- 各資源は BusinessAccessPolicy の範囲（policy.queryset）の中だけを検索する。
- 照合するのは名称・番号などの識別項目だけ（My Number・証件番号・住所・連絡先・金額では検索しない）。
- 返すのは最小限の要約：顧客・会社は氏名・カナ・表現レベルだけ（範囲外は開けない印を付ける）、
  書類はタイトルと案件だけ（保存パス・URL は返さない）、会計金額は返さない。
- 顧客・会社を返したときだけ監査に残す。記録するのは件数と検索語の長さで、検索語そのものは残さない。
"""
from django.db.models import Q
from rest_framework.response import Response

from apps.audit.services import record
from apps.authentication.access_rules import COMPANY_RULE, CUSTOMER_RULE, DETAIL_LEVELS, LEVEL_MINIMAL
from apps.authentication.drf import business_api_view

MIN_LENGTH = 2
LIMIT = 8


def _cases(policy, q):
    if not policy.module_allowed('case', 'list'):
        return None
    qs = policy.queryset('case', 'list').select_related('customer', 'company').filter(
        Q(case_number__icontains=q) | Q(customer__name__icontains=q) | Q(customer__name_kana__icontains=q)
        | Q(company__name__icontains=q)
    ).order_by('-id')[:LIMIT]
    return [{
        'id': c.id, 'title': c.case_number,
        'subtitle': ' / '.join(filter(None, [c.customer.name if c.customer_id else '', c.get_status_display(),
                                            'アーカイブ' if c.registration_status == 'archived' else ''])),
        'url': f'/cases/{c.id}', 'can_open': True,
    } for c in qs]


def _parties(policy, q, resource, rule, url_prefix):
    if not policy.module_allowed(resource, 'list'):
        return None
    qs = rule.annotate(policy, policy.queryset(resource, 'list').filter(
        Q(name__icontains=q) | Q(name_kana__icontains=q))).order_by('name', 'id')[:LIMIT]
    rows = []
    for obj in qs:
        level = rule.level(policy, obj)
        can_open = level in DETAIL_LEVELS
        rows.append({
            'id': obj.id, 'title': obj.name, 'subtitle': obj.name_kana or '',
            'access_level': level, 'can_open': can_open,
            'url': f'{url_prefix}/{obj.id}' if can_open else '',
            'note': '範囲外（最小識別情報のみ）' if level == LEVEL_MINIMAL else '',
        })
    return rows


def _documents(policy, q):
    if not policy.module_allowed('document', 'list'):
        return None
    qs = policy.queryset('document', 'list').select_related('case').filter(
        Q(title__icontains=q) | Q(file_name__icontains=q)).order_by('-id')[:LIMIT]
    return [{
        'id': d.id, 'title': d.title,
        'subtitle': ' / '.join(filter(None, [d.case.case_number if d.case_id else '', d.get_category_display(),
                                            'アーカイブ' if d.is_archived else ''])),
        'url': f'/cases/{d.case_id}', 'can_open': True,
    } for d in qs]


def _real_estate(policy, q):
    if not policy.module_allowed('real_estate', 'list'):
        return None
    qs = policy.queryset('real_estate', 'list').filter(
        Q(transaction_number__icontains=q) | Q(party_name__icontains=q) | Q(property_name__icontains=q)
        | Q(room_number__icontains=q)).order_by('-id')[:LIMIT]
    return [{
        'id': t.id, 'title': f'{t.transaction_number} {t.property_name} {t.room_number}'.strip(),
        'subtitle': f'{t.party_name} / {t.get_stage_display()}',
        'url': f'/real-estate/{t.id}', 'can_open': True,
    } for t in qs]


@business_api_view(['GET'], 'global_search')
def global_search(request):
    policy = request.business_policy
    q = (request.query_params.get('q') or '').strip()[:100]
    if len(q) < MIN_LENGTH:
        return Response({'query_too_short': True, 'min_length': MIN_LENGTH, 'groups': []})
    blocks = [
        ('case', '案件', _cases(policy, q)),
        ('customer', '顧客', _parties(policy, q, 'customer', CUSTOMER_RULE, '/customers')),
        ('company', '会社', _parties(policy, q, 'company', COMPANY_RULE, '/companies')),
        ('document', '書類', _documents(policy, q)),
        ('real_estate', '不動産', _real_estate(policy, q)),
    ]
    groups = [{'type': key, 'label': label, 'items': items} for key, label, items in blocks if items is not None]
    personal = {g['type']: len(g['items']) for g in groups if g['type'] in ('customer', 'company') and g['items']}
    if personal:
        minimal = sum(1 for g in groups if g['type'] in ('customer', 'company')
                      for item in g['items'] if item['access_level'] == LEVEL_MINIMAL)
        record(module='search', action='global_search_personal_results', request=request,
               extra={'query_length': len(q), 'counts': personal, 'minimal_results': minimal})
    return Response({'query_too_short': False, 'groups': groups})
