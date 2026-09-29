"""旧コード（P0 以前、例：de95411）で実行する：最新スキーマに対し、旧コードの API・ORM で基本的な書き込みを行う。

作成：Case（API）、Document（API で作成・更新・ファイル差し替え）、請求書・領収書（API）、
     Expense・Timeline・Task（ORM）、未参照 Document の削除（ORM）。
結果（作成 ID・HTTP 状態・例外の種類）を JSON で出す。パスワード・個人情報は出力しない。
終了コード：失敗があれば 1。
"""
import io
import json
import secrets
from datetime import date

from _common import setup

db = setup()
from django.contrib.auth import get_user_model  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
results, failures = {}, []


def step(name, fn):
    try:
        results[name] = fn()
    except Exception as exc:  # 旧コードで失敗した内容（例外の種類と先頭のメッセージ）だけを記録する
        results[name] = {'error': type(exc).__name__, 'message': str(exc)[:200]}
        failures.append(name)


def api_ok(response, expected, label):
    if response.status_code != expected:
        raise RuntimeError(f'{label}: HTTP {response.status_code} {response.content[:200]!r}')
    return response.json()


User = get_user_model()
admin = User.objects.filter(username='rc_old_admin').first() or User.objects.create_superuser(
    username='rc_old_admin', password=secrets.token_urlsafe(16), email='')
client = APIClient(SERVER_NAME='127.0.0.1')
client.force_authenticate(admin)

from apps.cases.models import Case, CaseApplicationCategory, CaseTypeMaster  # noqa: E402
from apps.customers.models import Customer  # noqa: E402

ctype, _ = CaseTypeMaster.objects.get_or_create(code='rc', defaults={'name': '互換検証', 'number_abbreviation': 'RC'})
cat, _ = CaseApplicationCategory.objects.get_or_create(code='rc', defaults={'name': '互換検証区分', 'number_abbreviation': 'RC'})
customer = Customer.objects.create(name='互換検証 顧客', birth_date=date(1990, 1, 1))


def create_case():
    body = api_ok(client.post('/api/cases/', {'customer': customer.id, 'case_type_master': ctype.id,
                                              'application_category': cat.id, 'case_type': '互換検証'}, format='json'),
                  201, 'case create')
    return {'id': body['id'], 'case_number': body.get('case_number')}


step('case_api_create', create_case)
case_id = results['case_api_create'].get('id') if isinstance(results.get('case_api_create'), dict) else None


def create_document():
    body = api_ok(client.post('/api/documents/', {'case': case_id, 'title': '互換検証 書類',
                                                  'file': SimpleUploadedFile('rc.pdf', PDF, 'application/pdf')},
                              format='multipart'), 201, 'document create')
    return {'id': body['id']}


step('document_api_create', create_document)
doc_id = results['document_api_create'].get('id') if isinstance(results.get('document_api_create'), dict) else None


def update_document():
    api_ok(client.patch(f'/api/documents/{doc_id}/', {'title': '互換検証 書類（更新）'}, format='json'), 200, 'doc patch')
    api_ok(client.patch(f'/api/documents/{doc_id}/', {'case': case_id, 'title': '互換検証 書類（差替）',
                                                        'file': SimpleUploadedFile('rc2.pdf', PDF, 'application/pdf')},
                        format='multipart'), 200, 'doc replace')
    return {'id': doc_id}


step('document_api_update_and_replace', update_document)

LINES = [{'item_name': '互換検証 申請取次', 'quantity': 1, 'unit_price': 11000, 'tax_category': 'tax_10'}]


def create_voucher(kind):
    def run():
        body = api_ok(client.post('/api/accounting/vouchers/', {'voucher_type': kind, 'issue_date': str(date.today()),
                                                                'recipient_name': '互換検証', 'amount': 10000,
                                                                'line_items': LINES}, format='json'), 201, f'{kind} create')
        return {'id': body['id'], 'voucher_number': body.get('voucher_number')}
    return run


step('invoice_api_create', create_voucher('invoice'))
step('receipt_api_create', create_voucher('receipt'))


def orm_writes():
    from apps.accounting.models import Expense
    from apps.documents.models import Document
    from apps.tasks.models import Task
    from apps.timelines.models import Timeline

    case = Case.objects.create(customer=customer, case_type_master=ctype, application_category=cat, case_type='互換検証ORM')
    expense = Expense.objects.create(expense_date=date.today(), category='交通費', amount=500)
    timeline = Timeline.objects.create(case=case, title='互換検証 経過')
    task = Task.objects.create(case=case, title='互換検証 タスク')
    temp = Document.objects.create(case=case, title='互換検証 一時', file=SimpleUploadedFile('tmp.pdf', PDF))
    temp_id = temp.id
    temp.delete()
    return {'case_id': case.id, 'expense_id': expense.id, 'timeline_id': timeline.id, 'task_id': task.id,
            'deleted_document_id': temp_id}


step('orm_basic_writes', orm_writes)

print(json.dumps({'database': db, 'results': results, 'failures': failures}, ensure_ascii=False, indent=1, default=str))
raise SystemExit(1 if failures else 0)
