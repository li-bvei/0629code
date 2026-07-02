from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.cases.models import Case
from apps.companies.models import Company, CompanyStaff
from apps.customers.models import Customer, FamilyMember
from apps.documents.models import Document
from apps.employees.models import Employee
from apps.reminders.models import Reminder
from apps.tasks.models import Task
from apps.timelines.models import Timeline


class Command(BaseCommand):
    help = 'Create demo data for local development.'

    def handle(self, *args, **options):
        self.clear_demo_data()

        employees = self.create_employees()
        customers = self.create_customers()
        self.create_family_members(customers)
        companies = self.create_companies(customers)
        self.create_company_staff(companies)
        cases = self.create_cases(customers, companies, employees)
        self.create_workflow_data(cases)

        self.stdout.write(
            self.style.SUCCESS(
                'Demo data created: 2 employees, 5 customers, 3 companies, '
                '5 cases, family members, company staff, tasks, reminders, timelines, and documents.'
            )
        )

    def clear_demo_data(self):
        Case.objects.filter(case_number__startswith='DEMO-').delete()
        Customer.objects.filter(name__startswith='デモ顧客').delete()
        Company.objects.filter(name__startswith='デモ会社').delete()
        Employee.objects.filter(name__in=[
            '担当A',
            '担当B',
            'デモ担当 佐藤',
            'デモ担当 鈴木',
        ]).delete()

    def create_employees(self):
        return [
            Employee.objects.create(
                name='担当A',
                email='tanto-a.demo@example.com',
                phone='03-0000-1001',
            ),
            Employee.objects.create(
                name='担当B',
                email='tanto-b.demo@example.com',
                phone='03-0000-1002',
            ),
        ]

    def create_customers(self):
        customers = [
            {
                'name': 'デモ顧客 山田太郎',
                'name_kana': 'ヤマダ タロウ',
                'birth_date': date(1985, 4, 12),
                'gender': Customer.GENDER_MALE,
                'nationality': '中国',
                'residence_status': '技術・人文知識・国際業務',
                'residence_card_no': 'AB12345678CD',
                'residence_expiry': date(2027, 5, 31),
                'passport_no': 'E12345678',
                'passport_expiry': date(2030, 4, 30),
                'email': 'yamada.demo@example.com',
                'phone': '090-1111-0001',
                'postal_code': '160-0023',
                'address': '東京都新宿区西新宿1-1-1',
                'my_number': 'TEST-1000-0001',
                'note': '在留資格更新の相談あり。',
            },
            {
                'name': 'デモ顧客 田中花子',
                'name_kana': 'タナカ ハナコ',
                'birth_date': date(1990, 8, 3),
                'gender': Customer.GENDER_FEMALE,
                'nationality': '日本',
                'email': 'tanaka.demo@example.com',
                'phone': '090-1111-0002',
                'postal_code': '150-0002',
                'address': '東京都渋谷区渋谷2-2-2',
                'my_number': 'TEST-1000-0002',
            },
            {
                'name': 'デモ顧客 王小明',
                'name_kana': 'オウ ショウメイ',
                'birth_date': date(1988, 1, 20),
                'gender': Customer.GENDER_MALE,
                'nationality': '中国',
                'residence_status': '経営・管理',
                'residence_card_no': 'CD22334455EF',
                'residence_expiry': date(2026, 12, 15),
                'passport_no': 'G98765432',
                'passport_expiry': date(2029, 9, 20),
                'email': 'wang.demo@example.com',
                'phone': '090-1111-0003',
                'postal_code': '170-0013',
                'address': '東京都豊島区東池袋3-3-3',
                'my_number': 'TEST-1000-0003',
                'note': '会社設立後の経営管理ビザ申請予定。',
            },
            {
                'name': 'デモ顧客 李美玲',
                'name_kana': 'リ ビレイ',
                'birth_date': date(1992, 11, 5),
                'gender': Customer.GENDER_FEMALE,
                'nationality': '中国',
                'residence_status': '日本人の配偶者等',
                'residence_card_no': 'EF99887766GH',
                'residence_expiry': date(2028, 3, 10),
                'passport_no': 'H11223344',
                'passport_expiry': date(2031, 7, 1),
                'email': 'li.demo@example.com',
                'phone': '090-1111-0004',
                'postal_code': '231-0011',
                'address': '神奈川県横浜市中区4-4-4',
                'my_number': 'TEST-1000-0004',
            },
            {
                'name': 'デモ顧客 高橋一郎',
                'name_kana': 'タカハシ イチロウ',
                'birth_date': date(1979, 6, 18),
                'gender': Customer.GENDER_MALE,
                'nationality': '日本',
                'email': 'takahashi.demo@example.com',
                'phone': '090-1111-0005',
                'postal_code': '272-0034',
                'address': '千葉県市川市5-5-5',
                'my_number': 'TEST-1000-0005',
            },
        ]
        return [Customer.objects.create(**customer) for customer in customers]

    def create_family_members(self, customers):
        family_members = [
            {
                'customer': customers[0],
                'relationship': FamilyMember.RELATIONSHIP_SPOUSE,
                'name': '山田美咲',
                'name_kana': 'ヤマダ ミサキ',
                'birth_date': date(1987, 9, 14),
                'gender': Customer.GENDER_FEMALE,
                'nationality': '中国',
                'residence_status': '家族滞在',
                'residence_card_no': 'FM12345678AA',
                'residence_expiry': date(2027, 5, 31),
                'phone': '090-2222-0001',
                'postal_code': '160-0023',
                'address': '東京都新宿区西新宿1-1-1',
                'my_number': 'TEST-2000-0001',
                'is_dependent': True,
                'note': '同居家族。',
            },
            {
                'customer': customers[0],
                'relationship': FamilyMember.RELATIONSHIP_CHILD,
                'name': '山田陽翔',
                'name_kana': 'ヤマダ ハルト',
                'birth_date': date(2018, 2, 8),
                'gender': Customer.GENDER_MALE,
                'nationality': '中国',
                'residence_status': '家族滞在',
                'residence_card_no': 'FM22345678BB',
                'residence_expiry': date(2027, 5, 31),
                'postal_code': '160-0023',
                'address': '東京都新宿区西新宿1-1-1',
                'my_number': 'TEST-2000-0002',
                'is_dependent': True,
            },
            {
                'customer': customers[2],
                'relationship': FamilyMember.RELATIONSHIP_SPOUSE,
                'name': '王丽',
                'name_kana': 'オウ レイ',
                'birth_date': date(1991, 6, 22),
                'gender': Customer.GENDER_FEMALE,
                'nationality': '中国',
                'phone': '090-2222-0003',
                'postal_code': '170-0013',
                'address': '東京都豊島区東池袋3-3-3',
                'my_number': 'TEST-2000-0003',
                'is_dependent': False,
            },
        ]
        return [FamilyMember.objects.create(**family_member) for family_member in family_members]

    def create_companies(self, customers):
        companies = [
            {
                'name': 'デモ会社 未来貿易株式会社',
                'name_kana': 'ミライボウエキカブシキガイシャ',
                'representative_customer': customers[2],
                'representative_name': '陳 未来',
                'representative_name_kana': 'チン ミライ',
                'corporate_number': '1000000000011',
                'email': 'info@mirai-demo.jp',
                'phone': '03-2222-0001',
                'postal_code': '105-0011',
                'address': '東京都港区芝公園1-2-3',
                'fiscal_month': '3',
                'bank_name': 'みずほ銀行',
                'bank_branch': '新宿支店',
                'bank_account_type': '普通',
                'bank_account_number': '1234567',
            },
            {
                'name': 'デモ会社 Sakura Tech合同会社',
                'name_kana': 'サクラテックゴウドウガイシャ',
                'representative_name': '中村 桜',
                'representative_name_kana': 'ナカムラ サクラ',
                'corporate_number': '1000000000022',
                'email': 'contact@sakura-demo.jp',
                'phone': '03-2222-0002',
                'postal_code': '103-0027',
                'address': '東京都中央区日本橋2-3-4',
                'fiscal_month': '12',
                'bank_name': '三井住友銀行',
                'bank_branch': '日本橋支店',
                'bank_account_type': '当座',
                'bank_account_number': '7654321',
            },
            {
                'name': 'デモ会社 東海食品株式会社',
                'name_kana': 'トウカイショクヒンカブシキガイシャ',
                'representative_customer': customers[4],
                'corporate_number': '1000000000033',
                'email': 'office@tokai-demo.jp',
                'phone': '052-222-0003',
                'postal_code': '460-0008',
                'address': '愛知県名古屋市中区3-4-5',
                'fiscal_month': '6',
                'bank_name': '三菱UFJ銀行',
                'bank_branch': '名古屋支店',
                'bank_account_type': '普通',
                'bank_account_number': '2468135',
            },
        ]
        return [Company.objects.create(**company) for company in companies]

    def create_company_staff(self, companies):
        staff_members = [
            {
                'company': companies[0],
                'name': '張 健',
                'name_kana': 'チョウ ケン',
                'position': '代表取締役',
                'birth_date': date(1984, 5, 12),
                'gender': '男性',
                'nationality': '中国',
                'residence_status': '経営・管理',
                'residence_card_no': 'CS12345678AA',
                'residence_expiry': date(2027, 8, 31),
                'passport_no': 'P12345678',
                'passport_expiry': date(2030, 8, 31),
                'phone': '090-3333-0001',
                'email': 'zhang.demo@mirai-demo.jp',
                'postal_code': '105-0011',
                'address': '東京都港区芝公園1-2-3',
                'my_number': 'TEST-3000-0001',
                'employment_start_date': date(2024, 4, 1),
                'note': 'デモ会社代表者。',
            },
            {
                'company': companies[0],
                'name': '李 明',
                'name_kana': 'リ メイ',
                'position': '社員',
                'birth_date': date(1992, 2, 18),
                'gender': '男性',
                'nationality': '中国',
                'residence_status': '技術・人文知識・国際業務',
                'residence_card_no': 'CS22345678BB',
                'residence_expiry': date(2026, 11, 30),
                'passport_no': 'P22345678',
                'passport_expiry': date(2029, 11, 30),
                'phone': '090-3333-0002',
                'email': 'li.demo@mirai-demo.jp',
                'postal_code': '105-0011',
                'address': '東京都港区芝公園1-2-3',
                'my_number': 'TEST-3000-0002',
                'employment_start_date': date(2025, 1, 15),
            },
            {
                'company': companies[1],
                'name': '佐藤 桜',
                'name_kana': 'サトウ サクラ',
                'position': '社員',
                'birth_date': date(1995, 7, 7),
                'gender': '女性',
                'nationality': '日本',
                'passport_no': 'P32345678',
                'passport_expiry': date(2031, 7, 7),
                'phone': '090-3333-0003',
                'email': 'sato.demo@sakura-demo.jp',
                'postal_code': '103-0027',
                'address': '東京都中央区日本橋2-3-4',
                'my_number': 'TEST-3000-0003',
                'employment_start_date': date(2023, 10, 1),
            },
            {
                'company': companies[2],
                'name': '王 芳',
                'name_kana': 'オウ ホウ',
                'position': '社員',
                'birth_date': date(1990, 9, 21),
                'gender': '女性',
                'nationality': '中国',
                'residence_status': '技能',
                'residence_card_no': 'CS42345678CC',
                'residence_expiry': date(2027, 3, 31),
                'passport_no': 'P42345678',
                'passport_expiry': date(2030, 3, 31),
                'phone': '090-3333-0004',
                'email': 'wang.demo@tokai-demo.jp',
                'postal_code': '460-0008',
                'address': '愛知県名古屋市中区3-4-5',
                'my_number': 'TEST-3000-0004',
                'employment_start_date': date(2024, 6, 1),
            },
        ]
        return [CompanyStaff.objects.create(**staff_member) for staff_member in staff_members]

    def create_cases(self, customers, companies, employees):
        today = timezone.localdate()
        case_data = [
            {
                'case_number': 'DEMO-2026-001',
                'case_type': '在留資格更新',
                'status': Case.STATUS_IN_PROGRESS,
                'customer': customers[0],
                'company': companies[0],
                'responsible_employee': employees[0],
                'accepted_at': today - timedelta(days=12),
                'applied_at': today - timedelta(days=7),
            },
            {
                'case_number': 'DEMO-2026-002',
                'case_type': '会社設立',
                'status': Case.STATUS_OPEN,
                'customer': customers[1],
                'company': companies[1],
                'responsible_employee': employees[1],
                'accepted_at': today - timedelta(days=8),
            },
            {
                'case_number': 'DEMO-2026-003',
                'case_type': '経営管理ビザ',
                'status': Case.STATUS_IN_PROGRESS,
                'customer': customers[2],
                'company': companies[0],
                'responsible_employee': employees[0],
                'accepted_at': today - timedelta(days=5),
                'applied_at': today - timedelta(days=2),
            },
            {
                'case_number': 'DEMO-2026-004',
                'case_type': '帰化申請',
                'status': Case.STATUS_OPEN,
                'customer': customers[3],
                'company': None,
                'responsible_employee': employees[1],
                'accepted_at': today - timedelta(days=3),
            },
            {
                'case_number': 'DEMO-2026-005',
                'case_type': '建設業許可',
                'status': Case.STATUS_COMPLETED,
                'customer': customers[4],
                'company': companies[2],
                'responsible_employee': employees[0],
                'accepted_at': today - timedelta(days=20),
                'applied_at': today - timedelta(days=15),
                'result_notified_at': today - timedelta(days=3),
                'completed_at': today - timedelta(days=1),
            },
        ]
        return [Case.objects.create(**case) for case in case_data]

    def create_workflow_data(self, cases):
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)
        yesterday = today - timedelta(days=1)

        def reminder_at(target_date, hour=9):
            return timezone.make_aware(datetime.combine(target_date, time(hour, 0)))

        for index, case in enumerate(cases, start=1):
            task_due_date = {
                1: yesterday - timedelta(days=1),
                2: yesterday,
                3: today,
                4: today,
                5: tomorrow,
            }[index]
            task_status = Task.STATUS_IN_PROGRESS if index in (1, 2) else Task.STATUS_TODO
            reminder_date = {
                1: yesterday - timedelta(days=2),
                2: yesterday,
                3: today,
                4: tomorrow,
                5: today + timedelta(days=2),
            }[index]

            Task.objects.create(
                case=case,
                title=f'必要書類の確認 {index}',
                description='顧客から提出された資料を確認する。',
                status=task_status,
                due_date=task_due_date,
            )
            if index % 2 == 0:
                Task.objects.create(
                    case=case,
                    title=f'申請書類の作成 {index}',
                    description='申請書類のドラフトを作成する。',
                    status=Task.STATUS_IN_PROGRESS,
                    due_date=today + timedelta(days=index + 2),
                )

            Reminder.objects.create(
                case=case,
                title=f'期限確認 {index}',
                remind_at=reminder_at(reminder_date, 9 + index),
                note='案件の次回対応期限を確認する。',
                is_done=False,
            )

            Timeline.objects.create(
                case=case,
                occurred_at=case.accepted_at,
                title='案件を受任しました',
                content='顧客から依頼内容を確認し、案件を登録しました。',
                is_visible_to_client=True,
            )
            Timeline.objects.create(
                case=case,
                occurred_at=case.accepted_at + timedelta(days=1) if case.accepted_at else None,
                title='資料確認を開始しました',
                content='提出済み資料の確認を開始しました。',
                is_visible_to_client=index % 2 == 1,
            )

            Document.objects.create(
                case=case,
                title=f'本人確認書類 {index}',
                file_name=f'demo_document_{index}.pdf',
                file_path=f'demo/cases/{case.case_number}/demo_document_{index}.pdf',
                file_size=1024 * index,
                content_type='application/pdf',
                source=Document.SOURCE_INTERNAL,
                is_visible_to_client=index % 2 == 0,
            )
