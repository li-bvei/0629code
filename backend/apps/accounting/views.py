from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Expense, ExpenseCategory, IncomeSource, VehicleUsage
from .serializers import (
    ExpenseCategorySerializer,
    ExpenseSerializer,
    IncomeSourceSerializer,
    VehicleUsageSerializer,
)


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
