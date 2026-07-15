from django.db import transaction
from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import (
    AccountingProject,
    AccountingProjectExpense,
    AccountingProjectIncome,
    AccountingVoucher,
    Expense,
    ExpenseCategory,
    IncomeSource,
    SeifuNoticePdfRecord,
    TaxRenewalAgentTemplate,
    TaxRenewalVoucherRecord,
    VehicleUsage,
    VisaGuarantorTemplate,
    VisaReturnApplication,
    VoucherItemTemplate,
)
from .excel import expenses_excel_response, project_excel_response
from .pdf import voucher_pdf_response
from .serializers import (
    AccountingProjectDetailSerializer,
    AccountingProjectExpenseSerializer,
    AccountingProjectIncomeSerializer,
    AccountingProjectSerializer,
    AccountingVoucherSerializer,
    ExpenseCategorySerializer,
    ExpenseSerializer,
    IncomeSourceSerializer,
    SeifuNoticePdfRecordSerializer,
    TaxRenewalAgentTemplateSerializer,
    TaxRenewalVoucherRecordSerializer,
    VehicleUsageSerializer,
    VisaGuarantorTemplateSerializer,
    VisaReturnApplicationSerializer,
    VoucherItemTemplateSerializer,
)
from .seifu_notice_pdf import seifu_notice_pdf_response
from .tax_renewal_pdf import SUPPORTED_TEMPLATE_KEY, tax_renewal_pdf_response
from .tax_renewal_templates import get_tax_renewal_templates
from .visa_return_pdf import visa_return_pdf_response


def parse_bool(value):
    if value in (None, ''):
        return None
    return str(value).lower() in ('1', 'true', 'yes', 'on')


def decimal_to_number(value):
    if value is None:
        return 0
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def sum_decimal(queryset, field_name, decimal_places=0):
    return queryset.aggregate(
        total=Coalesce(
            Sum(field_name),
            Value(0),
            output_field=DecimalField(max_digits=12, decimal_places=decimal_places),
        )
    )['total']


def build_expense_chart(group_field):
    rows = Expense.objects.values(group_field).annotate(total=Sum('amount')).order_by('-total')
    grouped = {}

    for row in rows:
        name = (row[group_field] or '').strip() or '未填写'
        grouped[name] = grouped.get(name, 0) + row['total']

    chart_items = [
        {'name': name, 'amount': amount}
        for name, amount in grouped.items()
    ]
    chart_items.sort(key=lambda item: item['amount'], reverse=True)

    if len(chart_items) > 8:
        top_items = chart_items[:7]
        other_amount = sum(item['amount'] for item in chart_items[7:])
        chart_items = top_items + [{'name': '其他', 'amount': other_amount}]

    return [
        {
            'name': item['name'],
            'amount': decimal_to_number(item['amount']),
        }
        for item in chart_items
    ]


def project_amount_summary(project):
    income_total = sum((income.amount for income in project.project_incomes.all()), Decimal('0'))
    expense_total = sum((expense.amount for expense in project.project_expenses.all()), Decimal('0'))
    return {
        'project_id': project.id,
        'project_name': project.name,
        'income': income_total,
        'expense': expense_total,
        'balance': income_total - expense_total,
    }


def build_project_expense_category_chart(projects):
    grouped = {}
    for project in projects:
        for expense in project.project_expenses.all():
            name = (expense.category_name or '').strip() or '未分類'
            grouped[name] = grouped.get(name, Decimal('0')) + expense.amount
    items = sorted(
        [{'name': name, 'amount': amount} for name, amount in grouped.items() if amount],
        key=lambda item: item['amount'],
        reverse=True,
    )
    if len(items) > 8:
        top_items = items[:7]
        other_amount = sum((item['amount'] for item in items[7:]), Decimal('0'))
        items = top_items + [{'name': 'その他', 'amount': other_amount}]
    return [{'name': item['name'], 'amount': decimal_to_number(item['amount'])} for item in items]


class ExpenseCategoryViewSet(ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        is_active = parse_bool(self.request.query_params.get('is_active'))
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by('sort_order', 'id')


class ExpenseViewSet(ModelViewSet):
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        if params.get('start_date'):
            queryset = queryset.filter(expense_date__gte=params['start_date'])
        if params.get('end_date'):
            queryset = queryset.filter(expense_date__lte=params['end_date'])
        if params.get('category'):
            queryset = queryset.filter(category=params['category'])
        if params.get('payment_method'):
            queryset = queryset.filter(payment_method=params['payment_method'])
        is_reimbursed = parse_bool(params.get('is_reimbursed'))
        if is_reimbursed is not None:
            queryset = queryset.filter(is_reimbursed=is_reimbursed)
        is_exported = parse_bool(params.get('is_exported'))
        if is_exported is not None:
            queryset = queryset.filter(is_exported=is_exported)
        if params.get('search'):
            keyword = params['search']
            queryset = queryset.filter(
                Q(place__icontains=keyword)
                | Q(category__icontains=keyword)
                | Q(payment_method__icontains=keyword)
                | Q(expense_target__icontains=keyword)
                | Q(note__icontains=keyword)
            )
        return queryset.order_by('-expense_date', '-created_at')

    def build_excel_filter_summary(self):
        params = self.request.query_params
        period = 'すべて'
        if params.get('start_date') or params.get('end_date'):
            period = f'{params.get("start_date") or "開始日なし"} ～ {params.get("end_date") or "終了日なし"}'
        is_reimbursed = parse_bool(params.get('is_reimbursed'))
        reimbursed_label = 'すべて'
        if is_reimbursed is not None:
            reimbursed_label = 'はい' if is_reimbursed else 'いいえ'
        return [
            ('対象期間', period),
            ('支出カテゴリ', params.get('category') or 'すべて'),
            ('支払方法', params.get('payment_method') or 'すべて'),
            ('精算済み', reimbursed_label),
            ('キーワード', params.get('search') or 'すべて'),
        ]

    @action(detail=False, methods=['get'], url_path='excel')
    def excel(self, request):
        expenses = self.get_queryset()
        return expenses_excel_response(
            expenses,
            filters=self.build_excel_filter_summary(),
            generated_at=timezone.localtime(timezone.now()),
        )


class IncomeSourceViewSet(ModelViewSet):
    queryset = IncomeSource.objects.all()
    serializer_class = IncomeSourceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        if params.get('start_date'):
            queryset = queryset.filter(source_date__gte=params['start_date'])
        if params.get('end_date'):
            queryset = queryset.filter(source_date__lte=params['end_date'])
        is_exported = parse_bool(params.get('is_exported'))
        if is_exported is not None:
            queryset = queryset.filter(is_exported=is_exported)
        if params.get('search'):
            keyword = params['search']
            queryset = queryset.filter(
                Q(source_target__icontains=keyword) | Q(note__icontains=keyword)
            )
        return queryset.order_by('-source_date', '-created_at')


class VehicleUsageViewSet(ModelViewSet):
    queryset = VehicleUsage.objects.all()
    serializer_class = VehicleUsageSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        if params.get('start_date'):
            queryset = queryset.filter(usage_date__gte=params['start_date'])
        if params.get('end_date'):
            queryset = queryset.filter(usage_date__lte=params['end_date'])
        if params.get('purpose'):
            queryset = queryset.filter(purpose=params['purpose'])
        is_exported = parse_bool(params.get('is_exported'))
        if is_exported is not None:
            queryset = queryset.filter(is_exported=is_exported)
        if params.get('search'):
            keyword = params['search']
            queryset = queryset.filter(
                Q(place__icontains=keyword)
                | Q(usage_target__icontains=keyword)
                | Q(purpose__icontains=keyword)
                | Q(note__icontains=keyword)
            )
        return queryset.order_by('-usage_date', '-created_at')


class AccountingProjectViewSet(ModelViewSet):
    queryset = AccountingProject.objects.prefetch_related('project_incomes', 'project_expenses')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AccountingProjectDetailSerializer
        return AccountingProjectSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        is_active = parse_bool(self.request.query_params.get('is_active'))
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        if self.request.query_params.get('search'):
            keyword = self.request.query_params['search']
            queryset = queryset.filter(
                Q(name__icontains=keyword)
                | Q(description__icontains=keyword)
                | Q(note__icontains=keyword)
            )
        return queryset.order_by('-created_at')

    @action(detail=True, methods=['post'], url_path='copy-expenses')
    def copy_expenses(self, request, pk=None):
        project = self.get_object()
        expense_ids = request.data.get('expense_ids', [])
        if not isinstance(expense_ids, list):
            expense_ids = []

        expenses = Expense.objects.filter(id__in=expense_ids)
        created_count = 0

        with transaction.atomic():
            for expense in expenses:
                AccountingProjectExpense.objects.create(
                    project=project,
                    expense_date=expense.expense_date,
                    place=expense.place,
                    category_name=expense.category,
                    amount=expense.amount,
                    payment_method=expense.payment_method,
                    expense_target=expense.expense_target,
                    note=expense.note,
                    source_expense=expense,
                )
                created_count += 1

        return Response({'created': created_count})

    @action(detail=False, methods=['get'], url_path='report')
    def report(self, request):
        projects = list(self.get_queryset().prefetch_related('project_incomes', 'project_expenses'))
        project_rows = [project_amount_summary(project) for project in projects]
        total_income = sum((row['income'] for row in project_rows), Decimal('0'))
        total_expense = sum((row['expense'] for row in project_rows), Decimal('0'))
        project_chart = sorted(project_rows, key=lambda row: row['income'], reverse=True)[:10]

        return Response({
            'summary': {
                'total_income': decimal_to_number(total_income),
                'project_count': len(projects),
                'total_expense': decimal_to_number(total_expense),
                'balance': decimal_to_number(total_income - total_expense),
            },
            'project_chart': [
                {
                    'project_id': row['project_id'],
                    'project_name': row['project_name'],
                    'income': decimal_to_number(row['income']),
                    'expense': decimal_to_number(row['expense']),
                    'balance': decimal_to_number(row['balance']),
                }
                for row in project_chart
            ],
            'expense_category_chart': build_project_expense_category_chart(projects),
        })

    @action(detail=True, methods=['get'], url_path='excel')
    def excel(self, request, pk=None):
        project = self.get_object()
        incomes = project.project_incomes.order_by('income_date', 'id')
        expenses = project.project_expenses.order_by('expense_date', 'id')
        return project_excel_response(project, incomes, expenses)


class AccountingProjectIncomeViewSet(ModelViewSet):
    queryset = AccountingProjectIncome.objects.select_related('project')
    serializer_class = AccountingProjectIncomeSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        if params.get('project'):
            queryset = queryset.filter(project_id=params['project'])
        if params.get('start_date'):
            queryset = queryset.filter(income_date__gte=params['start_date'])
        if params.get('end_date'):
            queryset = queryset.filter(income_date__lte=params['end_date'])
        if params.get('search'):
            keyword = params['search']
            queryset = queryset.filter(
                Q(income_target__icontains=keyword) | Q(note__icontains=keyword)
            )
        return queryset.order_by('-income_date', '-id')


class AccountingProjectExpenseViewSet(ModelViewSet):
    queryset = AccountingProjectExpense.objects.select_related('project', 'source_expense')
    serializer_class = AccountingProjectExpenseSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        if params.get('project'):
            queryset = queryset.filter(project_id=params['project'])
        if params.get('start_date'):
            queryset = queryset.filter(expense_date__gte=params['start_date'])
        if params.get('end_date'):
            queryset = queryset.filter(expense_date__lte=params['end_date'])
        if params.get('search'):
            keyword = params['search']
            queryset = queryset.filter(
                Q(place__icontains=keyword)
                | Q(category_name__icontains=keyword)
                | Q(payment_method__icontains=keyword)
                | Q(expense_target__icontains=keyword)
                | Q(note__icontains=keyword)
            )
        return queryset.order_by('-expense_date', '-id')


class AccountingVoucherViewSet(ModelViewSet):
    queryset = AccountingVoucher.objects.select_related('created_by')
    serializer_class = AccountingVoucherSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        if params.get('voucher_type'):
            queryset = queryset.filter(voucher_type=params['voucher_type'])

        issue_date_from = params.get('issue_date_from') or params.get('start_date')
        issue_date_to = params.get('issue_date_to') or params.get('end_date')
        if issue_date_from:
            queryset = queryset.filter(issue_date__gte=issue_date_from)
        if issue_date_to:
            queryset = queryset.filter(issue_date__lte=issue_date_to)

        if params.get('recipient_name'):
            queryset = queryset.filter(recipient_name__icontains=params['recipient_name'])
        if params.get('title'):
            keyword = params['title']
            queryset = queryset.filter(Q(title__icontains=keyword) | Q(line_items__icontains=keyword))
        if params.get('amount_min'):
            queryset = queryset.filter(total_amount__gte=params['amount_min'])
        if params.get('amount_max'):
            queryset = queryset.filter(total_amount__lte=params['amount_max'])
        if params.get('payment_due_date_from'):
            queryset = queryset.filter(payment_due_date__gte=params['payment_due_date_from'])
        if params.get('payment_due_date_to'):
            queryset = queryset.filter(payment_due_date__lte=params['payment_due_date_to'])

        keyword = params.get('keyword') or params.get('search')
        if keyword:
            queryset = queryset.filter(
                Q(voucher_number__icontains=keyword)
                | Q(recipient_name__icontains=keyword)
                | Q(title__icontains=keyword)
                | Q(details__icontains=keyword)
                | Q(note__icontains=keyword)
                | Q(bank_info__icontains=keyword)
                | Q(line_items__icontains=keyword)
            )
        return queryset.order_by('-issue_date', '-id')

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        voucher = self.get_object()
        with_seal = parse_bool(request.query_params.get('with_seal')) is True
        return voucher_pdf_response(voucher, with_seal=with_seal)


class VoucherItemTemplateViewSet(ModelViewSet):
    queryset = VoucherItemTemplate.objects.all()
    serializer_class = VoucherItemTemplateSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        include_inactive = str(self.request.query_params.get('include_inactive', '')).lower() in ('1', 'true', 'yes')
        if self.action == 'list' and not include_inactive:
            queryset = queryset.filter(is_active=True)
        return queryset.order_by('sort_order', 'id')


class VisaReturnApplicationViewSet(ModelViewSet):
    queryset = VisaReturnApplication.objects.select_related('created_by')
    serializer_class = VisaReturnApplicationSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        keyword = self.request.query_params.get('search')
        if keyword:
            queryset = queryset.filter(
                Q(applicant_name__icontains=keyword)
                | Q(passport_number__icontains=keyword)
                | Q(phone__icontains=keyword)
                | Q(email__icontains=keyword)
                | Q(guarantor_name__icontains=keyword)
            )
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user)

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None):
        application = self.get_object()
        return visa_return_pdf_response(application)


class VisaGuarantorTemplateViewSet(ModelViewSet):
    queryset = VisaGuarantorTemplate.objects.all()
    serializer_class = VisaGuarantorTemplateSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        include_inactive = str(self.request.query_params.get('include_inactive', '')).lower() in ('1', 'true', 'yes')
        keyword = self.request.query_params.get('search')
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword)
                | Q(guarantor_name__icontains=keyword)
                | Q(guarantor_name_en__icontains=keyword)
                | Q(guarantor_phone__icontains=keyword)
                | Q(guarantor_address__icontains=keyword)
                | Q(guarantor_occupation__icontains=keyword)
                | Q(guarantor_relationship__icontains=keyword)
            )
        return queryset.order_by('sort_order', 'id')

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])


class SeifuNoticePdfRecordViewSet(ModelViewSet):
    queryset = SeifuNoticePdfRecord.objects.select_related('created_by')
    serializer_class = SeifuNoticePdfRecordSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        keyword = self.request.query_params.get('search')
        if keyword:
            queryset = queryset.filter(Q(title__icontains=keyword) | Q(note__icontains=keyword))
        return queryset.order_by('-updated_at', '-id')

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user)

    @action(detail=True, methods=['post'], url_path='generate_pdf')
    def generate_pdf(self, request, pk=None):
        record = self.get_object()
        try:
            return seifu_notice_pdf_response(record.text_items, title=record.title)
        except FileNotFoundError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class TaxRenewalVoucherRecordViewSet(ModelViewSet):
    queryset = TaxRenewalVoucherRecord.objects.select_related('company', 'customer', 'employee', 'created_by')
    serializer_class = TaxRenewalVoucherRecordSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get('category'):
            queryset = queryset.filter(category=params['category'])
        if params.get('company'):
            queryset = queryset.filter(company_id=params['company'])
        if params.get('customer'):
            queryset = queryset.filter(customer_id=params['customer'])
        keyword = params.get('search') or params.get('keyword')
        if keyword:
            queryset = queryset.filter(
                Q(title__icontains=keyword)
                | Q(note__icontains=keyword)
                | Q(company__name__icontains=keyword)
                | Q(customer__name__icontains=keyword)
            )
        return queryset.order_by('-updated_at', '-id')

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user)

    @action(detail=True, methods=['post'], url_path='generate_pdf')
    def generate_pdf(self, request, pk=None):
        record = self.get_object()
        template_key = request.data.get('template_key') if isinstance(request.data, dict) else None
        if template_key != SUPPORTED_TEMPLATE_KEY:
            return Response({'detail': 'PDF字段映射未完成'}, status=status.HTTP_400_BAD_REQUEST)
        if template_key not in (record.selected_templates or []):
            return Response({'detail': '该记录未选择社会保险纳入证明兼委任状。'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return tax_renewal_pdf_response(record, template_key)
        except FileNotFoundError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class TaxRenewalAgentTemplateViewSet(ModelViewSet):
    queryset = TaxRenewalAgentTemplate.objects.all()
    serializer_class = TaxRenewalAgentTemplateSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        include_inactive = str(self.request.query_params.get('include_inactive', '')).lower() in ('1', 'true', 'yes')
        keyword = self.request.query_params.get('search')
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword)
                | Q(agent_name__icontains=keyword)
                | Q(agent_kana__icontains=keyword)
                | Q(agent_company_name__icontains=keyword)
                | Q(agent_phone__icontains=keyword)
            )
        return queryset.order_by('sort_order', 'id')

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])


@api_view(['GET'])
def tax_renewal_templates(request):
    return Response(get_tax_renewal_templates())


@api_view(['GET'])
def dashboard(request):
    today = timezone.localdate()
    start_date = today.replace(day=1)
    end_date = today

    monthly_expense_total = sum_decimal(
        Expense.objects.filter(expense_date__gte=start_date, expense_date__lte=end_date),
        'amount',
    )
    monthly_income_source_total = sum_decimal(
        IncomeSource.objects.filter(source_date__gte=start_date, source_date__lte=end_date),
        'amount',
    )
    monthly_vehicle_km_total = sum_decimal(
        VehicleUsage.objects.filter(usage_date__gte=start_date, usage_date__lte=end_date),
        'distance_km',
        decimal_places=1,
    )
    monthly_unreimbursed_total = sum_decimal(
        Expense.objects.filter(
            expense_date__gte=start_date,
            expense_date__lte=end_date,
            is_reimbursed=False,
        ),
        'amount',
    )
    total_expense_amount = sum_decimal(Expense.objects.all(), 'amount')
    total_income_source_amount = sum_decimal(IncomeSource.objects.all(), 'amount')
    current_balance = total_income_source_amount - total_expense_amount

    recent_expenses = list(
        Expense.objects.order_by('-expense_date', '-created_at').values(
            'id',
            'expense_date',
            'place',
            'category',
            'amount',
            'payment_method',
            'expense_target',
            'note',
            'is_reimbursed',
            'is_exported',
        )[:10]
    )
    recent_income_sources = list(
        IncomeSource.objects.order_by('-source_date', '-created_at').values(
            'id',
            'source_date',
            'source_target',
            'amount',
            'note',
            'is_exported',
        )[:10]
    )
    recent_vehicle_usages = list(
        VehicleUsage.objects.order_by('-usage_date', '-created_at').values(
            'id',
            'usage_date',
            'place',
            'distance_km',
            'usage_target',
            'purpose',
            'note',
            'is_exported',
        )[:10]
    )

    for item in recent_expenses:
        item['amount'] = decimal_to_number(item['amount'])
    for item in recent_income_sources:
        item['amount'] = decimal_to_number(item['amount'])
    for item in recent_vehicle_usages:
        item['distance_km'] = decimal_to_number(item['distance_km'])

    return Response({
        'monthly_expense_total': decimal_to_number(monthly_expense_total),
        'monthly_income_source_total': decimal_to_number(monthly_income_source_total),
        'monthly_vehicle_km_total': decimal_to_number(monthly_vehicle_km_total),
        'monthly_unreimbursed_total': decimal_to_number(monthly_unreimbursed_total),
        'total_expense_amount': decimal_to_number(total_expense_amount),
        'total_income_source_amount': decimal_to_number(total_income_source_amount),
        'current_balance': decimal_to_number(current_balance),
        'expense_target_chart': build_expense_chart('expense_target'),
        'expense_category_chart': build_expense_chart('category'),
        'recent_expenses': recent_expenses,
        'recent_income_sources': recent_income_sources,
        'recent_vehicle_usages': recent_vehicle_usages,
    })
