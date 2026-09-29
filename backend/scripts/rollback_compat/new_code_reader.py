"""最新コードで実行する：旧コードが作成した記録を新コードの API で読み、安全な業務既定値で扱えることを確認する。

引数：old_code_writer.py の JSON 出力ファイル。終了コード：不一致があれば 1。
"""
import json
import secrets
import sys

from _common import setup

db = setup()
import os  # noqa: E402

from django.conf import settings  # noqa: E402

# 本番では新旧コードが同じ media ボリュームを使う。検証では旧コードの media を読み取り専用で参照して再現する。
if os.environ.get('ROLLBACK_COMPAT_MEDIA_ROOT'):
    settings.MEDIA_ROOT = os.environ['ROLLBACK_COMPAT_MEDIA_ROOT']
from django.contrib.auth import get_user_model  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from apps.authentication.testing import grant_full_business_access  # noqa: E402

written = json.load(open(sys.argv[1]))['results']
User = get_user_model()
reader = User.objects.filter(username='rc_new_reader').first() or User.objects.create_user(
    username='rc_new_reader', password=secrets.token_urlsafe(16))
grant_full_business_access(reader, employee_name='互換検証 読取')
client = APIClient(SERVER_NAME='127.0.0.1')
client.force_authenticate(reader)
checks, failures = [], []


def expect(label, actual, expected):
    ok = actual == expected
    checks.append({'check': label, 'actual': actual, 'expected': expected, 'ok': ok})
    if not ok:
        failures.append(label)


def get(url):
    r = client.get(url)
    expect(f'GET {url}', r.status_code, 200)
    return r.json() if r.status_code == 200 else {}


case_id = written['case_api_create']['id']
case = get(f'/api/cases/{case_id}/')
expect('case.work_status', case.get('work_status'), 'active')
expect('case.waiting_reason', case.get('waiting_reason'), '')
expect('case.archive_reason', case.get('archive_reason'), '')
expect('case.registration_status', case.get('registration_status'), 'active')
workbench = client.get('/api/cases/', {'view': 'all', 'page_size': 100}).json()
expect('case in list', case_id in [c['id'] for c in workbench.get('results', [])], True)

doc_id = written['document_api_create']['id']
doc = get(f'/api/documents/{doc_id}/')
expect('document.category', doc.get('category'), 'other')
expect('document.is_archived', doc.get('is_archived'), False)
expect('document.title (old update)', doc.get('title'), '互換検証 書類（差替）')
docs = client.get('/api/documents/', {'page_size': 100}).json()
expect('document in default list (not archived)', doc_id in [d['id'] for d in docs.get('results', [])], True)
expect('document download', client.get(f'/api/documents/{doc_id}/download/').status_code, 200)

for key, status_field in (('invoice_api_create', 'invoice_status'), ('receipt_api_create', 'receipt_status')):
    vid = written[key]['id']
    v = get(f'/api/accounting/vouchers/{vid}/')
    expect(f'{key}.{status_field}', v.get(status_field), '')
    expect(f'{key}.status_display', v.get('status_display'), '状態未設定（旧データ）')
    expect(f'{key}.is_editable', v.get('is_editable'), True)
    expect(f'{key}.issued_snapshot', v.get('issued_snapshot'), {})

# 新コードで引き続き更新できること
r = client.patch(f'/api/cases/{case_id}/', {'note': '新コードで更新'}, format='json')
expect('new code PATCH case', r.status_code, 200)
inv = written['invoice_api_create']['id']
r = client.post(f'/api/accounting/vouchers/{inv}/transition/', {'status': 'issued'}, format='json')
expect('new code transition legacy invoice → issued', r.status_code, 200)

print(json.dumps({'database': db, 'checks': checks, 'failures': failures}, ensure_ascii=False, indent=1, default=str))
raise SystemExit(1 if failures else 0)
