from datetime import date
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from django.test import SimpleTestCase
from openpyxl import load_workbook

from .excel import ACCOUNTING_NUMBER_FORMAT, build_expenses_excel, build_project_excel


class ProjectExcelExportTests(SimpleTestCase):
    def test_project_excel_contains_summary_numeric_amounts_and_charts(self):
        project = SimpleNamespace(
            name='テスト案件',
            start_date=date(2026, 1, 1),
            end_date=date(2026, 7, 31),
        )
        incomes = [
            SimpleNamespace(income_date=date(2026, 1, 10), income_target='着手金', amount=Decimal('150000'), note=''),
        ]
        expenses = [
            SimpleNamespace(
                expense_date=date(2026, 1, 12),
                place='役所',
                category_name='証明書',
                amount=Decimal('12000'),
                payment_method='现金',
                expense_target='王小明',
                note='',
            ),
            SimpleNamespace(
                expense_date=date(2026, 1, 13),
                place='交通',
                category_name='交通費',
                amount=Decimal('3500'),
                payment_method='ICOCA',
                expense_target='',
                note='',
            ),
        ]

        workbook_bytes = build_project_excel(project, incomes, expenses)
        workbook = load_workbook(BytesIO(workbook_bytes))
        sheet = workbook['プロジェクト収支表']

        self.assertEqual(sheet['A5'].value, 150000)
        self.assertEqual(sheet['C5'].value, 3)
        self.assertEqual(sheet['E5'].value, 15500)
        self.assertEqual(sheet['G5'].value, 134500)
        self.assertEqual(sheet['A5'].number_format, ACCOUNTING_NUMBER_FORMAT)
        self.assertEqual(sheet['E5'].number_format, ACCOUNTING_NUMBER_FORMAT)
        self.assertEqual(len(sheet._charts), 2)
        self.assertEqual(workbook['ChartData'].sheet_state, 'hidden')


class ExpenseExcelExportTests(SimpleTestCase):
    def test_expenses_excel_contains_summary_filter_table_and_chart(self):
        expenses = [
            SimpleNamespace(
                expense_date=date(2026, 7, 1),
                place='役所',
                category='証明書',
                amount=Decimal('1200'),
                payment_method='现金',
                expense_target='王小明',
                note='住民票',
                is_reimbursed=False,
            ),
            SimpleNamespace(
                expense_date=date(2026, 7, 2),
                place='交通',
                category='交通費',
                amount=Decimal('500'),
                payment_method='ICOCA',
                expense_target='王小明',
                note='',
                is_reimbursed=True,
            ),
            SimpleNamespace(
                expense_date=date(2026, 7, 3),
                place='返金',
                category='交通費',
                amount=Decimal('-200'),
                payment_method='现金',
                expense_target='王小明',
                note='調整',
                is_reimbursed=False,
            ),
        ]

        workbook_bytes = build_expenses_excel(
            expenses,
            filters=[('対象期間', '2026-07-01 ～ 2026-07-31'), ('支出カテゴリ', 'すべて')],
        )
        workbook = load_workbook(BytesIO(workbook_bytes))
        sheet = workbook['支出記録']

        self.assertEqual(sheet['A1'].value, '支出記録')
        self.assertEqual(sheet['A5'].value, 1500)
        self.assertEqual(sheet['C5'].value, 3)
        self.assertEqual(sheet['E5'].value, 500)
        self.assertEqual(sheet['A5'].number_format, ACCOUNTING_NUMBER_FORMAT)
        self.assertEqual(sheet['E5'].number_format, ACCOUNTING_NUMBER_FORMAT)
        self.assertEqual(sheet['D29'].value, 1200)
        self.assertEqual(sheet['D29'].number_format, ACCOUNTING_NUMBER_FORMAT)
        self.assertEqual(sheet.freeze_panes, 'A29')
        self.assertEqual(sheet.auto_filter.ref, 'A28:H31')
        self.assertEqual(sheet.print_title_rows, '$28:$28')
        self.assertEqual(len(sheet._charts), 1)
        self.assertEqual(workbook['ChartData'].sheet_state, 'hidden')

        text_values = [
            cell.value
            for row in sheet.iter_rows()
            for cell in row
            if isinstance(cell.value, str)
        ]
        self.assertFalse(any('¥' in value or '￥' in value or '円' in value or 'JPY' in value for value in text_values))

    def test_expenses_excel_without_rows_is_valid_without_empty_chart(self):
        workbook_bytes = build_expenses_excel([])
        workbook = load_workbook(BytesIO(workbook_bytes))
        sheet = workbook['支出記録']

        self.assertEqual(sheet['A5'].value, 0)
        self.assertEqual(sheet['C5'].value, 0)
        self.assertEqual(sheet['E5'].value, 0)
        self.assertEqual(len(sheet._charts), 0)
        self.assertNotIn('ChartData', workbook.sheetnames)
